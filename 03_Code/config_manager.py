import json
from pathlib import Path
from path_utils import get_project_root, get_settings_file, get_resource_root

PROJ_ROOT = get_project_root()
CONFIG_FILE = get_settings_file("user_settings.json")
CONFIG_DIR = CONFIG_FILE.parent

DEFAULT_CONFIG = {
    "context_prompt": (get_resource_root() / "01_Project/prompts/travel_default.txt").read_text(encoding="utf-8"),
    "sample_interval_sec": 2.0,
    "ai_sampling_fps": 1.0,
    "watch_dir": str((PROJ_ROOT / "02_Data").resolve())
}

def load_user_config():
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        save_user_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_user_config(config_dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
