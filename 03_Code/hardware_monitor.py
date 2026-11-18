"""Hardware telemetry with explicit distinctions between VRAM and shared system RAM."""
import csv
import json
import math
from pathlib import Path
import platform
import re
import shutil
import subprocess

import psutil
from cpu_temperature import CpuTemperature
from storage_inventory import storage_inventory
from gpu_memory_policy import system_headroom_mb, whisper_headroom_mb


def run_output(command, timeout=4):
    return subprocess.check_output(command, timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")


def shared_memory_device(name, system=None, machine=None):
    system, machine = system or platform.system(), machine or platform.machine()
    return ((system == "Darwin" and machine.lower() in ("arm64", "aarch64")) or
            bool(re.search(r"Apple|GB10|Adreno|Intel.*(?:UHD|Iris|HD Graphics)|Radeon.*(?:[6789]\d\dM|80[56]0S)|^AMD Radeon(?:\(TM\))? Graphics$", name, re.I)))


def shared_snapshot(name, memory):
    return {"id": "shared:" + name, "name": name, "kind": "shared",
            "memory_percent": memory.percent, "used_gb": memory.used / 1024**3,
            "total_gb": memory.total / 1024**3, "temperature": None,
            "compute_percent": None, "scope": "系統共享記憶體，非 GPU 專用用量"}


class HardwareMonitor:
    def __init__(self):
        self.nvml = None
        self.cpu_sensor = CpuTemperature()
        self.other_names = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml = pynvml
        except Exception:
            pass

    def close(self):
        if getattr(self, "cpu_sensor", None):
            self.cpu_sensor.close()
        if self.nvml:
            try:
                self.nvml.nvmlShutdown()
            except Exception:
                pass
            self.nvml = None

    def nvidia(self):
        cards = []
        if self.nvml:
            try:
                for index in range(self.nvml.nvmlDeviceGetCount()):
                    handle = self.nvml.nvmlDeviceGetHandleByIndex(index)
                    info = self.nvml.nvmlDeviceGetMemoryInfo(handle)
                    name = self.nvml.nvmlDeviceGetName(handle)
                    name = name.decode() if isinstance(name, bytes) else name
                    try:
                        temp = self.nvml.nvmlDeviceGetTemperature(handle, self.nvml.NVML_TEMPERATURE_GPU)
                    except Exception:
                        temp = None
                    try:
                        compute = self.nvml.nvmlDeviceGetUtilizationRates(handle).gpu
                    except Exception:
                        compute = None
                    cards.append({"id": f"nvidia:{index}", "name": name, "kind": "dedicated",
                        "memory_percent": info.used / info.total * 100 if info.total else None,
                        "used_gb": info.used / 1024**3, "total_gb": info.total / 1024**3,
                        "temperature": temp, "compute_percent": compute, "scope": "獨立顯存"})
                return cards
            except Exception:
                cards = []
        if shutil.which("nvidia-smi"):
            try:
                output = run_output(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"])
                for index, row in enumerate(csv.reader(output.splitlines())):
                    name, used, total, temp, compute = [v.strip() for v in row]
                    used, total = float(used), float(total)
                    cards.append({"id": f"nvidia:{index}", "name": name, "kind": "dedicated",
                        "memory_percent": used / total * 100 if total else None,
                        "used_gb": used / 1024, "total_gb": total / 1024,
                        "temperature": float(temp) if temp.replace(".", "").isdigit() else None,
                        "compute_percent": float(compute) if compute.replace(".", "").isdigit() else None,
                        "scope": "獨立顯存"})
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        return cards

    def discover_other_names(self):
        if self.other_names is not None:
            return self.other_names
        names = []
        try:
            if platform.system() == "Darwin":
                data = json.loads(run_output(["system_profiler", "SPDisplaysDataType", "-json"], timeout=8))
                names = [d.get("sppci_model", "Apple GPU") for d in data.get("SPDisplaysDataType", [])]
            elif platform.system() == "Windows":
                command = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) | ConvertTo-Json -Compress"
                value = json.loads(run_output(["powershell", "-NoProfile", "-Command", command]))
                names = [value] if isinstance(value, str) else value or []
            elif shutil.which("lspci"):
                lines = run_output(["lspci"]).splitlines()
                names = [line.split(": ", 1)[-1] for line in lines if re.search(r"VGA|3D controller|Display controller", line)]
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        if not names and platform.system() == "Darwin" and platform.machine().lower() in ("arm64", "aarch64"):
            names = ["Apple Silicon GPU"]
        self.other_names = names
        return names

    def snapshot(self):
        memory = psutil.virtual_memory()
        cards = self.nvidia()
        names = self.discover_other_names()
        if cards:
            names = [n for n in names if "nvidia" not in n.lower() and all(n.lower() != c["name"].lower() for c in cards)]
        for index, name in enumerate(names):
            if shared_memory_device(name):
                cards.append(shared_snapshot(name, memory))
            else:
                cards.append({"id": f"other:{index}", "name": name, "kind": "unknown",
                    "memory_percent": None, "used_gb": None, "total_gb": None,
                    "temperature": None, "compute_percent": None, "scope": "此後端未提供 GPU 用量"})
        # NVIDIA integrated unified-memory systems must not look like discrete VRAM.
        cards = [shared_snapshot(c["name"], memory) if shared_memory_device(c["name"]) else c for c in cards]
        if not hasattr(self, "cpu_sensor"):
            self.cpu_sensor = CpuTemperature()
        cpu_temp = self.cpu_sensor.read()
        disk_details = storage_inventory()
        disks = [(d["mount"], d["total_gb"], d["free_gb"], d["percent"]) for d in disk_details]
        return {"cpu_percent": psutil.cpu_percent(), "cpu_temp": cpu_temp, "cpu_temp_status": self.cpu_sensor.status,
                "ram_percent": memory.percent, "ram_text": f"{memory.used/1024**3:.1f}/{memory.total/1024**3:.1f}G",
                "gpus": cards, "disks": disks, "disk_details": disk_details}


def detect_engine_devices(executable):
    output = run_output([str(executable), "--list-devices"], timeout=20)
    return [{"id": match.group(1), "name": match.group(2).strip(), "total_mb": int(match.group(3)),
             "free_mb": int(match.group(4))}
            for match in re.finditer(r"^\s*(\w+\d*):\s*(.*?)\s*\((\d+) MiB,\s*(\d+) MiB free\)", output, re.M)]


def device_arguments(devices, settings=None, notify=lambda message: None, model_path=None):
    """Budget live free memory first; ratios follow available model budgets."""
    settings = settings or {}
    if not devices:
        return ["--device", "none", "--split-mode", "none"]
    # Avoid mixing incompatible backend families when a build exposes several.
    family = re.sub(r"\d+$", "", devices[0]["id"])
    chosen = [d for d in devices if re.sub(r"\d+$", "", d["id"]) == family]
    valid = all(isinstance(d.get("total_mb"), (int, float)) and isinstance(d.get("free_mb"), (int, float))
                and math.isfinite(d["total_mb"]) and math.isfinite(d["free_mb"])
                and 0 <= d["free_mb"] <= d["total_mb"] and d["total_mb"] > 0 for d in chosen)
    if not valid:
        if family.upper() == "CUDA":
            notify("顯存資料不完整，無法確認主卡預留；本次保守使用 CPU，不猜測分層比例。")
            return ["--device", "none", "--split-mode", "none"]
        # Unknown/shared backends keep their existing engine placement behavior.
        notify("此後端缺少完整顯存資料，保留引擎配置；無法確認預留量。")
        return ["--device", ",".join(d["id"] for d in chosen), "--split-mode", "layer" if len(chosen)>1 else "none"]
    asr_mb = whisper_headroom_mb(settings.get("whisper_model", ""))
    usable, margins, budgets = [], [], []
    for index, device in enumerate(chosen):
        primary = device["id"] == "CUDA0" if family.upper() == "CUDA" else index == 0
        # Current OS/Resolve allocations are ALREADY absent from free_mb.
        # Reserve additional growth/workspace; CPU ASR needs no CUDA weights.
        growth = system_headroom_mb(device["total_mb"], primary)
        speech = asr_mb if primary and family.upper() == "CUDA" else 0
        reserve = growth + speech
        budget = max(0, math.floor(device["free_mb"] - reserve))
        notify(f"[顯存預算] {device['id']} {device.get('name', '')}：總量 {device['total_mb']/1024:.2f}GiB，"
               f"目前可用 {device['free_mb']/1024:.2f}GiB，額外系統／Resolve／緩衝預留 {growth/1024:.2f}GiB，"
               f"Whisper 預留 {speech/1024:.2f}GiB，模型預算 {budget/1024:.2f}GiB（估算）。")
        if budget > 0:
            usable.append(device)
            margins.append(reserve)
            budgets.append(budget)
        else:
            notify(f"[顯存預算] {device['id']} 沒有剩餘模型預算，本次不放 GGUF 層。")
    chosen = usable
    if not chosen:
        notify("預留後沒有 GPU 模型空間，本次使用 CPU；保留 GPU 給系統與 Resolve。")
        return ["--device", "none", "--split-mode", "none"]
    # Two discrete CUDA cards: prefer filling the auxiliary to a total 90%
    # target, counting its current usage and leaving runtime workspace.
    if len(chosen) == 2 and {d['id'] for d in chosen} == {'CUDA0', 'CUDA1'}:
        aux = next(i for i,d in enumerate(chosen) if d['id'] == 'CUDA1')
        primary = 1 - aux
        device = chosen[aux]
        used = device['total_mb'] - device['free_mb']
        target = math.floor(device['total_mb'] * .90)
        workspace = max(512, math.ceil(device['total_mb'] * .02))
        capacity = max(0, math.floor(target - used - workspace))
        try:
            selected = Path(model_path or settings.get('llm_path', ''))
            if not selected.is_absolute():
                selected = Path(__file__).resolve().parents[1] / selected
            size = selected.stat().st_size / 1024**2 if selected.is_file() else 0
            # Summation only for complete numbered GGUF shard sets.
            shard = re.match(r'^(.*)-(\d{5})-of-(\d{5})\.gguf$', selected.name, re.I)
            if shard:
                parts = [selected.with_name(f'{shard[1]}-{n:05d}-of-{shard[3]}.gguf')
                         for n in range(1, int(shard[3]) + 1)]
                size = sum(p.stat().st_size for p in parts) / 1024**2
        except OSError:
            size = 0
        if size > 1 and capacity > 0:
            # File size is a weight estimate, not a VRAM measurement. Fit still
            # handles non-layer tensors, KV/cache and CPU overflow.
            aux_weight = min(capacity, max(1, math.floor(size) - 1))
            main_weight = min(budgets[primary], max(1, math.ceil(size - aux_weight)))
            budgets[aux], budgets[primary] = aux_weight, main_weight
            margins[aux] = math.ceil(device['total_mb'] * .10)
            notify(f"[分層規劃] GPU1／CUDA1 優先：總顯存目標約90%（{target/1024:.2f}GiB），"
                   f"目前已用 {used/1024:.2f}GiB，另留工作空間 {workspace/1024:.2f}GiB；"
                   f"權重配置估算 {aux_weight/1024:.2f}GiB，主卡承接其餘並保留系統／Resolve 餘裕。"
                   "依 GGUF 檔案大小估算，非精準占用保證；小模型不會為湊90%而額外配置。")
        else:
            notify("[分層規劃] GPU1 無90%目標餘量或模型大小不可用，沿用保守預算比例。")
    arguments = ["--device", ",".join(d["id"] for d in chosen),
                 "--split-mode", "layer" if len(chosen) > 1 else "none"]
    if len(chosen) > 1:
        divisor = math.gcd(*budgets)
        ratio = ",".join(str(value//divisor) for value in budgets)
        arguments += ["--tensor-split", ratio]
        notify("[分層規劃] 按預留後模型預算分層，tensor-split=" + ratio + "（裝置順序 " + ",".join(d['id'] for d in chosen) + "）。")
    arguments += ["--fit", "on", "--fit-target", ",".join(map(str, margins))]
    return arguments
