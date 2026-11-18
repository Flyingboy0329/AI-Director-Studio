import os
import sys
import time
import psutil
import subprocess
from pathlib import Path
import ctypes
import json
import re
import uuid

user32 = getattr(getattr(ctypes, "windll", None), "user32", None)

from path_utils import get_project_root, get_base_dir, get_resource_root
from pipeline.director_decision import lua_string
PROJ_ROOT = get_project_root()
OUTPUT_DIR = PROJ_ROOT / "05_Output"

# 自動偵測 resolve_lua 位置 (支援根目錄與 03_Code 內)
possible_lua_dirs = [
    get_resource_root() / "resolve_lua",
    PROJ_ROOT / "resolve_lua",
    get_base_dir() / "resolve_lua",
    PROJ_ROOT / "03_Code" / "resolve_lua"
]
LUA_DIR = next((d for d in possible_lua_dirs if d.exists()), PROJ_ROOT / "resolve_lua")

def check_resolve_running():
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() in ('resolve.exe', 'resolve'):
                return True, "Running"
        return False, "Offline"
    except Exception:
        return False, "Offline"

def force_activate_window(hwnd):
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)
    user32.SwitchToThisWindow(hwnd, True)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.3)
    return True

def center_window(hwnd):
    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                    ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    new_x = int((screen_w - w) / 2)
    new_y = int((screen_h - h) / 2)
    user32.SetWindowPos(hwnd, 0, new_x, new_y, w, h, 0x0004)
    time.sleep(0.2)
    return new_x, new_y, w, h

def find_all_resolve_windows():
    main_hwnd = None
    console_hwnd = None
    def enum_cb(hwnd, extra):
        nonlocal main_hwnd, console_hwnd
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if title.lower() == "resolve":
                    console_hwnd = hwnd
                elif "davinci resolve" in title.lower():
                    main_hwnd = hwnd
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return main_hwnd, console_hwnd


def read_receipt(path):
    """Read JSON or Fusion's scalar Lua table without executing Lua code."""
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        result = json.loads(text)
    except ValueError:
        result = {}
        for key in ("expected", "written", "coverage_ok"):
            match = re.search(r'\b' + key + r'\s*=\s*(true|false|\d+)\s*[,}]', text)
            if not match:
                raise ValueError("回執格式不完整")
            value = match.group(1)
            result[key] = value == "true" if value in ("true", "false") else int(value)
    if (not isinstance(result, dict) or type(result.get("expected")) is not int or
            type(result.get("written")) is not int or type(result.get("coverage_ok")) is not bool):
        raise ValueError("回執欄位無效")
    return result

def trigger_resolve_injection(task_lua_path=None, fresh_receipt=False, wait_for_receipt=False):
    if user32 is None:
        return False, "分析與標記任務已保存；此平台尚不支援自動操作 Resolve 控制台，請手動執行 Lua 任務。"
    task_file = Path(task_lua_path or OUTPUT_DIR / "test_marker_task.lua").resolve()
    # Unique receipt path comes from the generated task, never a stale previous run.
    try:
        task_text = task_file.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return False, f"無法讀取標記任務：{exc}"
    receipt_match = re.search(r'result_path = \[==\[(.*?)\]==\]', task_text)
    if not receipt_match:
        return False, "任務缺少 Resolve 完成回執路徑，請重新分析素材。"
    receipt = Path(receipt_match.group(1))
    if fresh_receipt:
        receipt = receipt.parent / f"{uuid.uuid4().hex}.json"
    if receipt.exists():
        return False, "此任務已有完成回執，請重新分析以產生新任務。"
    print("[Bridge] 🔍 正在尋找 DaVinci Resolve 視窗...")
    main_hwnd, console_hwnd = find_all_resolve_windows()

    if not main_hwnd and not console_hwnd:
        print("[Bridge] ⚠️ 未偵測到 Resolve 視窗，請先開啟專案！")
        return False, "Resolve window not found"

    if main_hwnd:
        print("[Bridge] 🚀 置頂主視窗...")
        force_activate_window(main_hwnd)
        time.sleep(0.4)

    if not console_hwnd:
        print("[Bridge] ⌨️ 發送 [F6] 鍵呼叫控制台...")
        try:
            import pyautogui
            pyautogui.press('f6')
        except Exception:
            ps_cmd = '$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys("{F6}")'
            subprocess.run(["powershell", "-Command", ps_cmd], creationflags=subprocess.CREATE_NO_WINDOW)

    time.sleep(1.0)
    _, console_hwnd = find_all_resolve_windows()
    if not console_hwnd:
        return False, "未找到 Lua 控制台，本次未貼上指令；保留任務，不重送"
    if console_hwnd:
        print(f"[Bridge] 🎯 捕捉到控制台，居中定位視窗...")
        force_activate_window(console_hwnd)
        new_x, new_y, w, h = center_window(console_hwnd)
        click_x = new_x + int(w / 2)
        click_y = new_y + h - 20
        try:
            import pyautogui
            print(f"[Bridge] 🖱️ 點擊居中輸入框: ({click_x}, {click_y})")
            pyautogui.click(click_x, click_y)
            time.sleep(0.2)
        except Exception:
            return False, "無法點擊控制台輸入框；本次未貼上指令"

    injector_lua = (LUA_DIR / "davinci_marker_injector.lua").resolve().as_posix()
    task_file = task_file.as_posix()
    lua_cmd = f'AI_DIRECTOR_TASK_PATH = [[{task_file}]]; dofile([[{injector_lua}]])'
    if fresh_receipt:
        lua_cmd = f'AI_DIRECTOR_TASK_PATH = [[{task_file}]]; AI_DIRECTOR_RESULT_PATH = [[{receipt.as_posix()}]]; dofile([[{injector_lua}]])'
    if not wait_for_receipt:
        # Snapshot the task into the command before dispatch. The job can then be
        # deleted without racing Resolve's later task-file read. The injector
        # itself stays in the project's resource directory, outside the job.
        lua_cmd = (f'AI_DIRECTOR_TASK_PATH = {lua_string(task_file)}; '
                   f'AI_DIRECTOR_TASK_DATA = assert((loadstring or load)({lua_string(task_text)}, "AI_Director_task"))(); '
                   f'AI_DIRECTOR_NO_RECEIPT = true; dofile({lua_string(injector_lua)})')
    token = uuid.uuid4().hex
    if wait_for_receipt:
        lua_cmd = f'AI_DIRECTOR_RECEIPT_TOKEN = "{token}"; ' + lua_cmd

    print(f"[Bridge] 📝 準備向控制台輸入指令...")
    delivery_started = False
    try:
        import pyperclip
        import pyautogui
        pyperclip.copy(lua_cmd)
        time.sleep(0.1)
        delivery_started = True
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)
        pyautogui.press('enter')
        print("[Bridge] 🚀 Lua 指令已送出。")
    except Exception:
        if delivery_started:
            return False, "控制台輸入過程發生錯誤；可能已送出，本次不重送"
        escaped_command = lua_cmd.replace("'", "''")
        ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Clipboard]::SetText('{escaped_command}')
Start-Sleep -Milliseconds 150
$wshell = New-Object -ComObject wscript.shell
$wshell.SendKeys("^v")
Start-Sleep -Milliseconds 200
$wshell.SendKeys("~")
'''
        result = subprocess.run(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            return False, "控制台指令傳送失敗"

    if not wait_for_receipt:
        return True, "Lua 指令已送出；本次不等待寫入確認，繼續分析下一支素材。"

    deadline = time.monotonic() + 10.0
    last_receipt_error = "尚未收到回執"
    while time.monotonic() < deadline:
        try:
            try:
                result = read_receipt(receipt)
                receipt_source = "檔案"
            except (OSError, ValueError):
                import pyperclip
                prefix = f"AI_DIRECTOR_RECEIPT:{token}:"
                packet = pyperclip.paste()
                if not isinstance(packet, str) or not packet.startswith(prefix):
                    raise ValueError("尚未收到本次回執")
                receipt.write_text(packet[len(prefix):], encoding="utf-8")
                result = read_receipt(receipt)
                receipt_source = "Fusion 剪貼簿"
            confirmed = (result.get("expected", 0) > 0 and
                         result.get("written") == result.get("expected") and
                         result.get("coverage_ok") is True)
            msg = f"Resolve 回執（{receipt_source}）：{result.get('written', 0)}/{result.get('expected', 0)} 筆，完整覆蓋={result.get('coverage_ok')}"
            if result.get("clip_frames") is not None:
                msg += f"，尾格={result.get('last_end_frame')}/{result['clip_frames']}（分析格數={result.get('planned_frames')}）"
            print(f"[Bridge] {msg}")
            return confirmed, msg
        except Exception as exc:
            last_receipt_error = type(exc).__name__
            time.sleep(0.1)
    try:
        diagnostic = {"status": "unconfirmed", "receipt_path": str(receipt),
                      "receipt_file_exists": receipt.exists(), "last_error_type": last_receipt_error,
                      "resubmission_allowed": False}
        (Path(task_file).parent / "bridge_receipt_status.json").write_text(
            json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    print("[Bridge] ❌ Resolve 回執逾時：檔案／Fusion 剪貼簿皆未回傳有效確認；不代表標記一定未寫入。")
    return False, "Resolve 確認逾時；本次只提交一次，不會重複導入"

def run_auto_inject(task_lua_path=None):
    ok, msg = trigger_resolve_injection(task_lua_path)
    return ok

if __name__ == "__main__":
    trigger_resolve_injection()
