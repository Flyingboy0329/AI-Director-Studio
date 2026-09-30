import os
import sys
import time
import win32gui
import win32con
import pyperclip
import pyautogui

pyautogui.FAILSAFE = False

LUA_SCRIPT_PATH = "C:/Users/pan/Desktop/AI_Director/03_Code/resolve_lua/davinci_marker_injector.lua"

def find_resolve_windows():
    """搜尋 Resolve 主視窗與 Console 控制台視窗"""
    resolve_main = None
    resolve_console = None

    def enum_cb(hwnd, extra):
        nonlocal resolve_main, resolve_console
        title = win32gui.GetWindowText(hwnd)
        if not win32gui.IsWindowVisible(hwnd):
            return

        if "DaVinci Resolve" in title:
            resolve_main = hwnd
        elif title in ["Resolve", "Console"]:
            resolve_console = hwnd

    win32gui.EnumWindows(enum_cb, None)
    return resolve_main, resolve_console

def check_resolve_running():
    main_hwnd, console_hwnd = find_resolve_windows()
    if main_hwnd or console_hwnd:
        return True, main_hwnd
    return False, None

def get_bmd_resolve():
    """相容付費版與心跳檢測接口"""
    try:
        import DaVinciResolveScript as dvr_script
        return dvr_script.scriptapp("Resolve")
    except Exception:
        pass
    return None

def bring_to_front(hwnd):
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pyautogui.press('alt')
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    time.sleep(0.3)

def run_auto_inject():
    print("🎬 [Injector] 啟動 Resolve 標記自動注入流程...")
    main_hwnd, console_hwnd = find_resolve_windows()

    if not main_hwnd and not console_hwnd:
        print("❌ [Injector] 找不到 DaVinci Resolve，請先啟動軟體！")
        return False

    # 若 Console 尚未打開，先喚醒主視窗並按下 F6
    if not console_hwnd:
        print("⌨️ [Injector] 喚醒主視窗並叫出控制台 (F6)...")
        bring_to_front(main_hwnd)
        pyautogui.press('f6')
        time.sleep(1.0)
        _, console_hwnd = find_resolve_windows()

    target_hwnd = console_hwnd if console_hwnd else main_hwnd
    bring_to_front(target_hwnd)

    # 獲取控制台視窗邊界，強制滑鼠點擊「底部輸入欄」
    rect = win32gui.GetWindowRect(target_hwnd)
    click_x = rect[0] + (rect[2] - rect[0]) // 2
    click_y = rect[3] - 25

    print(f"🎯 [Injector] 滑鼠精準鎖定輸入欄: ({click_x}, {click_y})")
    pyautogui.click(click_x, click_y)
    time.sleep(0.2)

    # 複製指令並貼上送出
    cmd = f'dofile("{LUA_SCRIPT_PATH}")'
    pyperclip.copy(cmd)
    
    print(f"🚀 [Injector] 送出指令: {cmd}")
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.15)
    pyautogui.press('enter')
    
    print("✅ [Injector] 注入指令已成功派送至 Resolve 控制台！")
    return True

if __name__ == "__main__":
    run_auto_inject()