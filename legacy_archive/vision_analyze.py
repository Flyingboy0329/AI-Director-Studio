#!/usr/bin/env python3
"""
vision_analyze.py
AI Director -> Vision Analysis Module (Qwen2-VL)
"""

import os
import json
import glob
import sys
import re
from pathlib import Path

# 獲取專案根目錄
ROOT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = "Qwen/Qwen2-VL-2B-Instruct"
DEFAULT_FRAMES_DIR = ROOT_DIR / "02_Data" / "frames"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "05_Output" / "analysis" / "visual_data.json"

def run_vision_analysis(frames_dir=DEFAULT_FRAMES_DIR, output_file=DEFAULT_OUTPUT_FILE):
    print(f"[Step] 正在分析影格: {frames_dir}")
    if not os.path.exists(frames_dir):
        print(f"[Error] 找不到影格資料夾: {frames_dir}")
        print("[Hint] 請先執行 main.py 或 video_extract.py 進行抽幀。")
        return False

    frame_paths = sorted(glob.glob(str(frames_dir / "*.jpg")))
    if not frame_paths:
        print(f"[Error] 在 {frames_dir} 中找不到 .jpg 檔案。")
        return False

    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
    except Exception as e:
        print(f"[Error] 視覺依賴載入失敗，詳細原因: {type(e).__name__} - {str(e)}")
        return False

    print(f"[Info] 找到 {len(frame_paths)} 張影格，開始載入模型...")
    try:
        processor = AutoProcessor.from_pretrained(DEFAULT_MODEL)
        model = Qwen2VLForConditionalGeneration.from_pretrained(DEFAULT_MODEL, device_map="auto")
    except Exception as e:
        print(f"[Error] 模型載入失敗: {e}")
        return False

    visual_data = []
    total_frames = len(frame_paths)

    for i, img_path in enumerate(frame_paths):
        print(f"\r  [Progress] 分析進度 {i+1}/{total_frames}...", end="", flush=True)
        from PIL import Image
        image = Image.open(img_path).convert("RGB")

        messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": "請簡短描述這張圖片的內容 (包含物體、動作、場景)。"}]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], return_tensors="pt")
        inputs = inputs.to(model.device)

        generated_ids = model.generate(**inputs, max_new_tokens=128)
        generated_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        match = re.search(r'<\|assistant\|>(.*)', generated_texts, re.DOTALL)
        analysis = match.group(1).strip() if match else generated_texts

        time_offset = i
        visual_data.append({
            "time": f"{time_offset:02d}:00",
            "visual_summary": analysis,
            "image_path": img_path
        })

    print("\n[Step] 視覺分析完成，正在寫入 JSON...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(visual_data, f, indent=2, ensure_ascii=False)
    print(f"[Success] 視覺分析報告已儲存至: {output_file}")
    return True

if __name__ == "__main__":
    run_vision_analysis()
