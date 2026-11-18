"""Start a user-installed llama-server with the models selected in AI Director.

python 03_Code/start_model_server.py --server /path/to/llama-server
For separate VLM: run another instance with --role vlm.
No model downloads or server installation are performed here.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from path_utils import get_project_root, load_local_settings, resolve_project_path
from hardware_monitor import detect_engine_devices, device_arguments
from context_settings import DEFAULT_CONTEXT, validate_context


def server_command(settings, executable, role="llm", gpu_layers="auto"):
    if role not in ("llm", "vlm"):
        raise ValueError("未知角色")
    if role == "vlm" and settings.get("model_mode") == "llm_only":
        raise ValueError("只用 LLM 模式不需啟動獨立 VLM")
    selected = settings.get(f"{role}_path", "")
    model = str(resolve_project_path(selected)) if selected else ""
    selected_projector = settings.get("llm_mmproj_path" if role == "llm" else "mmproj_path", "")
    projector = str(resolve_project_path(selected_projector)) if selected_projector else ""
    if not model or not Path(model).is_file():
        raise ValueError(f"找不到所選 {role.upper()} 主模型，請重新選檔")
    load_mode = settings.get("load_mode", "none")
    if load_mode not in ("none", "auto", "mmap"):
        raise ValueError("無效的模型記憶體載入模式")
    command = [str(executable), "-m", model, "--alias", Path(model).name,
               "--host", "127.0.0.1", "--port", "8080" if role == "llm" else "8081",
               "--jinja", "-c", str(validate_context(settings.get("context_size", DEFAULT_CONTEXT))), "-ngl", str(gpu_layers), "--parallel", "1",
               "--load-mode", load_mode]
    if projector:
        if not Path(projector).is_file():
            raise ValueError("找不到所選 mmproj")
        command.extend(["--mmproj", projector])
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=shutil.which("llama-server"), help="已安裝的 llama-server.exe 完整路徑")
    parser.add_argument("--role", choices=("llm", "vlm"), default="llm")
    parser.add_argument("--gpu-layers", type=int, default=None, help="預設自動適配保留後餘量；可指定層數，0 為 CPU")
    parser.add_argument("--load-mode", choices=("none", "auto", "mmap"), help="none 關閉 mmap（預設）；auto 使用引擎預設")
    args = parser.parse_args()
    if not args.server or not Path(args.server).is_file():
        parser.error("尚未找到 llama-server.exe；請用 --server 指定支援 Gemma 4 的已安裝版本。")
    try:
        settings = load_local_settings("model_settings.json")
        if args.load_mode:
            settings["load_mode"] = args.load_mode
        layers = args.gpu_layers if args.gpu_layers is not None else settings.get("gpu_layers", "auto")
        command = server_command(settings, args.server, args.role, layers)
        devices = detect_engine_devices(args.server) if layers != 0 else []
        command += device_arguments(devices, settings, print, model_path=command[command.index('-m')+1])
        if not devices:
            command[command.index("-ngl") + 1] = "0"
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print("模型服務將持續執行，請保留此終端，再回 GUI 啟動監看。")
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
