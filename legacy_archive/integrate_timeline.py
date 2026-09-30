#!/usr/bin/env python3
"""
integrate_timeline.py
AI Director -> Timeline Integration Module
"""

import os
import json
import sys
from pathlib import Path

# 獲取專案根目錄
ROOT_DIR = Path(__file__).resolve().parents[2]

AUDIO_JSON_PATH = ROOT_DIR / "05_Output" / "analysis" / "audio_segments.json"
VISUAL_JSON_PATH = ROOT_DIR / "05_Output" / "analysis" / "visual_data.json"
OUTPUT_PATH = ROOT_DIR / "05_Output" / "analysis" / "timeline_integrated.json"

def align_segments():
    print("[Step] 正在讀取音訊與視覺資料...")
    if not AUDIO_JSON_PATH.exists():
        print(f"[Error] 找不到音訊轉錄檔案: {AUDIO_JSON_PATH}")
        print("[Hint] 請先執行 audio_transcribe.py")
        return False
    with open(AUDIO_JSON_PATH, "r", encoding="utf-8") as f:
        audio_segments = json.load(f)

    if not VISUAL_JSON_PATH.exists():
        print(f"[Error] 找不到視覺分析檔案: {VISUAL_JSON_PATH}")
        print("[Hint] 請先執行 vision_analyze.py")
        return False
    with open(VISUAL_JSON_PATH, "r", encoding="utf-8") as f:
        visual_data = json.load(f)

    timeline_data = []
    for vis_frame in visual_data:
        vis_time = vis_frame.get("time") or vis_frame.get("timestamp", "00:00")
        time_offset = float(vis_time.split(":")[0])
        frame_start, frame_end = time_offset, time_offset + 1.0
        overlapping_audio = []
        for audio_seg in audio_segments:
            start_t = max(frame_start, audio_seg["start"])
            end_t = min(frame_end, audio_seg["end"])
            if start_t < end_t:
                overlapping_audio.append(audio_seg["text"])
        combined_text = " ".join(overlapping_audio) if overlapping_audio else "(無對應音訊)"
        timeline_data.append({
            "time": vis_time,
            "visual_summary": vis_frame["visual_summary"],
            "audio_text": combined_text,
            "confidence": 0.9
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(timeline_data, f, indent=2, ensure_ascii=False)
    print(f"[Success] 時間軸整合完成，已儲存至: {OUTPUT_PATH}")
    return True

def integrate_timeline(*args, **kwargs):
    return align_segments(*args, **kwargs)

if __name__ == "__main__":
    integrate_timeline()
