#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_apply_markers.py
DaVinci Resolve 自動標記注入模組 (v3.2 官方 API 重構)
"""

import os
import sys
import subprocess
from pathlib import Path

# 獲取專案根目錄
ROOT_DIR = Path(__file__).resolve().parents[2]

EDL_PATH = ROOT_DIR / "05_Output" / "reports" / "davinci_markers.edl"

def apply_markers_auto():
    if not EDL_PATH.exists():
        print(f"[Error] EDL 檔案不存在: {EDL_PATH}")
        return False

    resolve_script_path = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
    if resolve_script_path not in sys.path:
        sys.path.append(resolve_script_path)

    resolve = None
    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
    except Exception as e:
        resolve = None

    if resolve:
        try:
            pm = resolve.GetProjectManager()
            proj = pm.GetCurrentProject()
            timeline = proj.GetCurrentTimeline() if proj else None
            if timeline:
                success = timeline.ImportIntoTimeline(str(EDL_PATH))
                print(f"✅ 成功自動將標記注入當前時間軸！結果: {success}")
            else:
                print("⚠️ 已連線 DaVinci，但當前未開啟任何時間軸。")
        except Exception as e:
            print(f"⚠️ API 呼叫失敗: {e}")
    else:
        print("ℹ️ 未能直接調用 API (請確認 Resolve 設定中是否開啟腳本支援)。")

    print("\n" + "="*40)
    print("🎉 AI 分析流程完成！")
    print(f"📄 EDL 檔案已就緒：{EDL_PATH}")
    print(f"📥 請開啟 DaVinci Resolve 並確認標記已自動注入 / 或手動匯入")
    print("="*40 + "\n")
    return True

if __name__ == "__main__":
    apply_markers_auto()
