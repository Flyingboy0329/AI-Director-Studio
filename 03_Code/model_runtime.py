"""Owned local model processes, startup validation and actionable diagnostics."""
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse

from ai.semantic_analyzer import LocalModelClient
from path_utils import get_project_root
from start_model_server import server_command
from context_settings import DEFAULT_CONTEXT, validate_context
from hardware_monitor import detect_engine_devices, device_arguments
import os
import psutil
import re
from model_process_registry import ModelProcessRegistry


class GpuMemoryStartupError(RuntimeError):
    def __init__(self, role, message):
        super().__init__(message)
        self.role = role


def gpu_memory_failure(text):
    lower = text.lower()
    return any(marker in lower for marker in ('cuda out of memory', 'cuda error: out of memory',
               'cudamalloc failed', 'hip out of memory', 'error_out_of_device_memory',
               'vulkan out of memory', 'failed to allocate cuda', 'cuda_error_out_of_memory'))


def check_cpu_ram(settings, role, notify):
    """Preflight CPU fallback; conservative estimate, not an allocation guarantee."""
    total_bytes = 0
    for key in (f'{role}_path', 'llm_mmproj_path' if role == 'llm' else 'mmproj_path'):
        value = settings.get(key)
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():path = get_project_root() / path
        if not path.is_file():raise ValueError(f'CPU 備選缺少模型檔：{path}')
        shard = re.match(r'^(.*)-(\d{5})-of-(\d{5})\.gguf$',path.name,re.I)
        parts = ([path.with_name(f'{shard[1]}-{n:05d}-of-{shard[3]}.gguf') for n in range(1,int(shard[3])+1)]
                 if shard else [path])
        total_bytes += sum(p.stat().st_size for p in parts)
    memory=psutil.virtual_memory()
    reserve=max(2.,memory.total/1024**3*.20)
    budget=max(0.,memory.available/1024**3-reserve)
    required=total_bytes/1024**3*1.2 + 1 + validate_context(settings.get('context_size',DEFAULT_CONTEXT))/8192
    notify(f'[CPU 備選] {role.upper()} RAM 預算={budget:.2f}GiB，規劃需求約={required:.2f}GiB（權重／投影與緩衝估算，非峰值保證）。')
    if budget < required:raise RuntimeError('CPU／RAM 備選預算不足；請選較小模型／Context 或釋放記憶體。')


def find_server(saved=""):
    override = os.environ.get("AI_DIRECTOR_LLAMA_SERVER", "")
    candidates = [Path(p).expanduser() for p in (saved, override) if p]
    root = get_project_root()
    candidates += [p for p in (root / "tools").glob("**/llama-server*") if p.name in ("llama-server", "llama-server.exe")]
    on_path = shutil.which("llama-server")
    if on_path:
        candidates.append(Path(on_path))
    return next((str(p.resolve()) for p in candidates if p.is_file()), "")


def port_in_use(url):
    parsed = urllib.parse.urlsplit(url)
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((parsed.hostname, parsed.port or 80)) == 0


class ModelRuntime:
    def __init__(self):
        self.processes = {}
        self.cancel = threading.Event()
        self.external_services = {}
        self.registry = ModelProcessRegistry(get_project_root()/".local"/"model_processes.json")
        self.record_ids = {}
        self.audio_runtime = None
        self.cpu_fallback_roles = set()

    def has_audio_model(self):
        return self.audio_runtime is not None and self.audio_runtime.model is not None

    def ensure_audio_ready(self, settings, notify=print):
        from ai.audio_analyzer import get_whisper_runtime
        self.audio_runtime = get_whisper_runtime()
        return self.audio_runtime.ensure_ready(settings.get("whisper_model") or None, notify)

    def release_audio(self, notify=print):
        if self.audio_runtime is not None:
            self.audio_runtime.unload(notify)
        else:
            notify("[Faster-Whisper] UNLOADED：目前沒有已載入的語音模型。")

    def recover(self, notify=lambda message: None):
        for role,(handle,log_path,signature,key) in self.registry.recover(notify).items():
            if role not in self.processes:
                self.processes[role]=(handle,log_path,signature)
                self.record_ids[role]=key
                if signature and signature[-1] == 'cpu-fallback':self.cpu_fallback_roles.add(role)

    def preserve_background(self):
        if not self.processes:
            return
        recorded = self.registry.read()
        for role,(process,log_path,signature) in self.processes.items():
            if process.poll() is None and self.record_ids.get(role) not in recorded:
                key=self.registry.add(role,process,log_path,signature)
                if key:self.record_ids[role]=key

    def ensure_ready(self, settings, notify=lambda message: None, timeout=300):
        # At most one GPU->CPU retry per role; external listeners are never replaced.
        for _ in range(3):
            try:
                return self._ensure_ready(settings, notify, timeout)
            except GpuMemoryStartupError as exc:
                if self.cancel.is_set() or exc.role in self.cpu_fallback_roles:
                    raise
                notify(f'[CPU 備選] {exc.role.upper()} GPU 顯存配置失敗；失敗程序已清理，檢查 RAM 後以 CPU 重試一次。原錯誤：{exc}')
                check_cpu_ram(settings, exc.role, notify)
                self.cpu_fallback_roles.add(exc.role)
        raise RuntimeError('模型備選次數已用盡。')

    def _ensure_ready(self, settings, notify=lambda message: None, timeout=300):
        if not settings.get("llm_path"):
            self.stop()
            notify("未選 LLM，使用技術分析模式。")
            return
        roles = ["llm"]
        if settings.get("model_mode", "separate") == "separate" and settings.get("vlm_path"):
            if not settings.get("mmproj_path"):
                raise ValueError("已選 VLM，但未選擇其 mmproj")
            roles.append("vlm")
        for unused in set(self.processes) - set(roles):
            self.stop_role(unused)
        for role in roles:
            attempted_gpu = False
            url = settings.get(f"{role}_url", f"http://127.0.0.1:{8080 if role == 'llm' else 8081}")
            projector = settings.get("llm_mmproj_path" if role == "llm" else "mmproj_path")
            client = LocalModelClient(url, settings[f"{role}_path"], timeout=2)
            image_input = bool(projector) and (role == "vlm" or settings.get("model_mode") == "llm_only")
            # Reuse an externally started service only after checking the exact model.
            if role not in self.processes and port_in_use(url):
                client.check(require_images=image_input)
                self.external_services[role] = url
                notify(f"{role.upper()} 已連接外部服務：{client.model_id}；Context／mmap／分層／卸載需由該服務管理，本機選項不會套用。")
                continue
            existing = self.processes.get(role)
            signature = (settings[f"{role}_path"], projector, url, settings.get("gpu_layers", "auto"),
                         settings.get("server_path", ""), os.environ.get("AI_DIRECTOR_LLAMA_SERVER", ""))
            signature += (settings.get("load_mode", "none"), validate_context(settings.get("context_size", DEFAULT_CONTEXT)), "auxiliary-90-v2", str(settings.get("whisper_model", "")))
            signature += ('cpu-fallback' if role in self.cpu_fallback_roles else 'gpu-preferred',)
            if existing and (existing[0].poll() is not None or existing[2] != signature):
                self.stop_role(role)
                existing = None
            if existing is None:
                executable = find_server(settings.get("server_path", ""))
                if not executable:
                    raise ValueError("找不到 llama-server.exe。請按「選引擎」指定，或執行 03_Code/install_model_runtime.py。")
                command = server_command(settings, executable, role, settings.get("gpu_layers", "auto"))
                devices = [] if role in self.cpu_fallback_roles or settings.get("gpu_layers") == 0 else detect_engine_devices(executable)
                placement = device_arguments(devices, settings, notify, model_path=settings.get(f'{role}_path'))
                command += placement
                selected_ids = placement[placement.index("--device")+1].split(",")
                attempted_gpu = selected_ids != ['none']
                if selected_ids == ["none"]:
                    if role not in self.cpu_fallback_roles:
                        check_cpu_ram(settings, role, notify)
                    if "-ngl" in command:
                        command[command.index("-ngl")+1] = "0"
                    else:
                        command += ["-ngl", "0"]
                    if image_input:
                        command += ['--no-mmproj-offload']
                    if role in self.cpu_fallback_roles:
                        notify(f'[CPU 備選] {role.upper()} 使用 CPU／RAM；GPU 層數0、投影亦不卸載至 GPU。推論可能較慢。')
                notify("推論裝置：" + (", ".join(d["name"] for d in devices if d["id"] in selected_ids) if selected_ids != ["none"] else "CPU（無可用模型顯存預算）"))
                notify("[分層規劃] 預設自動層數配合預留目標適配，必要時使用 CPU；手動指定層數不保證能適配。預留為估算，非顯存硬隔離。")
                parsed = urllib.parse.urlsplit(url)
                # Command and API must address the same endpoint; never bind a LAN address.
                command[command.index("--port") + 1] = str(parsed.port or 80)
                if port_in_use(url):
                    raise ValueError(f"{url} 已被其他服務占用；不會關閉其他程式。")
                log_dir = get_project_root() / "05_Output" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / f"model_{role}_{time.time_ns()}.log"
                with log_path.open("wb") as log:
                    process = subprocess.Popen(command, cwd=str(Path(executable).parent),
                        stdout=log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.processes[role] = (process, log_path, signature)
                try:
                    key = self.registry.add(role,process,log_path,signature)
                    if key:self.record_ids[role]=key
                except Exception as exc:
                    self.stop_role(role)
                    raise RuntimeError(f"模型程序紀錄無法保存，已停止新引擎，避免無法卸載：{exc}") from exc
                self.external_services.pop(role, None)
                notify(f"正在載入 {role.upper()}：{client.model_id}，首次可能需要數分鐘。")
                notify(f"模型載入模式：{settings.get('load_mode', 'none')}（none 為停用 mmap）")
                notify(f"{role.upper()} 要求 Context：{validate_context(settings.get('context_size', DEFAULT_CONTEXT))} tokens（每個服務；仍受模型與引擎支援限制）")
            process, log_path, _ = self.processes[role]
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.cancel.is_set():
                    self.stop()
                    raise RuntimeError("模型載入已取消")
                if process.poll() is not None:
                    tail = log_path.read_text(encoding="utf-8", errors="replace")[-2500:]
                    self.stop_role(role)
                    if attempted_gpu and gpu_memory_failure(tail):
                        raise GpuMemoryStartupError(role, f'{role.upper()} 引擎退出：{tail}')
                    raise RuntimeError(f"{role.upper()} 引擎退出，請查看 {log_path}。\n{tail}")
                try:
                    client.check(require_images=image_input)
                    notify(f"{role.upper()} READY：{client.model_id}")
                    break
                except RuntimeError:
                    time.sleep(0.5)
                except ValueError:
                    self.stop_role(role)
                    raise
            else:
                tail = log_path.read_text(encoding='utf-8', errors='replace')[-2500:]
                self.stop_role(role)
                if attempted_gpu and gpu_memory_failure(tail):
                    raise GpuMemoryStartupError(role, f'{role.upper()} GPU 記憶體錯誤後載入逾時：{tail}')
                raise RuntimeError(f"{role.upper()} 載入逾時，請查看 {log_path}")

    def stop_role(self, role):
        entry = self.processes.get(role)
        if entry:
            process = entry[0]
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            self.processes.pop(role, None)
            self.registry.remove(self.record_ids.pop(role,None))

    def stop(self, notify=print):
        errors = []
        try:
            self.release_audio(notify)
        except Exception as exc:
            errors.append(f"Whisper: {exc}")
        for role in list(self.processes):
            try:
                self.stop_role(role)
            except Exception as exc:
                errors.append(f"{role}: {exc}")
        if errors:
            raise RuntimeError("部分引擎尚未退出：" + "; ".join(errors))
        self.cpu_fallback_roles.clear()
