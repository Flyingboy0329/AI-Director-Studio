#!/usr/bin/env python3
"""
audio_transcribe.py
AI Director -> Audio Transcription Module
"""

import json
import os
import sys
from pathlib import Path

# 獲取專案根目錄
ROOT_DIR = Path(__file__).resolve().parents[2]

try:
    import whisper
except ImportError:
    print("[Error] 請先安裝 whisper: pip install openai-whisper")
    sys.exit(1)

NO_SPEECH_THRESHOLD = 0.65
OUTPUT_PATH = ROOT_DIR / "05_Output" / "analysis" / "audio_segments.json"

def transcribe_audio(audio_path, output_path=OUTPUT_PATH):
    print(f"[Step] 正在轉錄音訊: {audio_path}")
    if not os.path.exists(audio_path):
        print(f"[Error] 找不到音訊檔案: {audio_path}")
        return False

    try:
        print("[Step] 載入 Whisper 模型...")
        model = whisper.load_model("base")
    except Exception as e:
        print(f"[Error] 載入模型失敗: {e}")
        return False

    try:
        print("[Step] 執行 CPU 轉錄...")
        result = model.transcribe(audio_path)
    except Exception as e:
        print(f"[Error] 轉錄失敗: {e}")
        return False

    segments_data = []
    print(f"[Info] 取得 {len(result['segments'])} 個音訊片段。")

    for segment in result["segments"]:
        text = segment["text"].strip()
        no_speech_prob = segment.get("no_speech_prob", 0)
        if no_speech_prob > NO_SPEECH_THRESHOLD:
            text = "(無人聲/環境音)"
        segments_data.append({
            "start": round(segment["start"], 2),
            "end": round(segment["end"], 2),
            "text": text
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(segments_data, f, indent=2, ensure_ascii=False)

    print(f"[Success] 音訊轉錄完成，已儲存至: {OUTPUT_PATH}")
    return True

if __name__ == "__main__":
    audio_file = str(ROOT_DIR / "06_Test" / "test_videos" / "audio.wav")
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    transcribe_audio(audio_file)
