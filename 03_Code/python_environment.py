"""Select an existing app environment without installing packages or changing PATH."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import shutil

REQUIRED = ("torch", "cv2", "faster_whisper", "PyQt6", "psutil", "pyautogui", "pyperclip", "filelock")
if sys.platform == "win32":
    REQUIRED += ("pythonnet", "clr_loader")


def missing_modules():
    return [name for name in REQUIRED if importlib.util.find_spec(name) is None]


def find_application_python():
    root = Path(__file__).resolve().parent.parent
    candidates = []
    if os.environ.get("AI_DIRECTOR_PYTHON"):
        candidates.append(Path(os.environ["AI_DIRECTOR_PYTHON"]))
    candidates += [root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += sorted((Path(local) / "Programs" / "Python").glob("Python*/python.exe"), reverse=True)
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    code = ("import importlib.util,sys; "
            f"sys.exit(0 if all(importlib.util.find_spec(x) is not None for x in {REQUIRED!r}) else 1)")
    for candidate in candidates:
        if not candidate.is_file() or candidate.resolve() == Path(sys.executable).resolve():
            continue
        try:
            result = subprocess.run([str(candidate), "-c", code], capture_output=True, timeout=15)
            if result.returncode == 0:
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def ensure_environment():
    missing = missing_modules()
    if not missing:
        return
    candidate = find_application_python()
    if candidate:
        print(f"[Environment] Current Python is missing: {', '.join(missing)}", flush=True)
        print(f"[Environment] Starting AI Director with {candidate}", flush=True)
        raise SystemExit(subprocess.call([str(candidate), "-X", "utf8", *sys.argv]))
    raise SystemExit(
        f"AI Director cannot start.\nPython: {sys.executable}\n"
        f"Missing modules: {', '.join(missing)}\n"
        "No installed application environment was found. Use the Python environment containing these packages.")
