import sys
import os
from pathlib import Path

def get_base_dir() -> Path:
    """取得執行基礎目錄，相容原始碼執行與 PyInstaller 打包環境"""
    if getattr(sys, 'frozen', False):
        # 打包成 exe 時的根目錄
        return Path(sys.executable).resolve().parent
    else:
        # 開發原始碼時的 03_Code 所在目錄
        return Path(__file__).resolve().parent

def get_project_root() -> Path:
    """取得 AI_Director 專案根目錄"""
    base = get_base_dir()
    if base.name == "03_Code":
        return base.parent
    return base


def get_settings_file(name: str) -> Path:
    """Machine-specific preferences live in an ignored local directory."""
    return get_project_root() / ".local" / name


def get_resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", get_project_root()))


def load_local_settings(name: str) -> dict:
    import json
    import shutil
    target = get_settings_file(name)
    if not target.exists():
        legacy = get_project_root() / "01_Project" / name
        if legacy.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def resolve_project_path(value, default="") -> Path:
    path = Path(value or default).expanduser()
    return path.resolve() if path.is_absolute() else (get_project_root() / path).resolve()
