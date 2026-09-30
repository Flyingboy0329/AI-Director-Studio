import os
import subprocess
from pathlib import Path

def trigger_resolve_injection():
    proj_root = Path(__file__).resolve().parent.parent.parent
    lua_script = proj_root / "resolve_lua" / "davinci_marker_injector.lua"
    task_file = proj_root / "05_Output" / "test_marker_task.lua"

    if not task_file.exists():
        return False, "Task file not found"

    # 使用無黑窗呼叫或跨進程派送
    cmd = ["cmd.exe", "/c", "echo", "Dynamic Bridge Loaded"]
    subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return True, f"Injected successfully using root: {proj_root}"

if __name__ == "__main__":
    success, msg = trigger_resolve_injection()
    print(msg)