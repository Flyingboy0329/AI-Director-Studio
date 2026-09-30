#!/usr/bin/env python3
"""
director.py
AI Director -> LLM Decision Engine
"""

import os
import json
import torch
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# 獲取專案根目錄
ROOT_DIR = Path(__file__).resolve().parents[2]

def load_director_model(model_name="Qwen/Qwen2.5-7B-Instruct"):
    print(f"[Director] 載入 AI 導演大腦 ({model_name}) 至 GPU (4-bit 模式)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="cuda"
    )
    return model, tokenizer

def run_director_llm(segment, model, tokenizer):
    visual = segment.get("visual_summary") or segment.get("visual_text") or "(無畫面資訊)"
    audio = segment.get("audio_text") or segment.get("audio_summary") or segment.get("text") or "(無音訊)"
    time_str = segment["time"]

    if "assistant\n" in visual: visual = visual.split("assistant\n")[-1].strip()
    elif "assistant:" in visual: visual = visual.split("assistant:")[-1].strip()

    system_prompt = (
        "你是一名經驗豐富的專業影音剪輯導演與剪輯決策顧問。"
        "你會根據素材的畫面內容與聲音狀態，提供客觀且具備剪輯思維的決策建議。"
        "請務必以嚴格的 JSON 格式回傳，格式如下：\n"
        "{\n"
        '  "recommendation": "保留" 或 "刪除" 或 "縮短/轉場",\n'
        '  "reason": "說明剪輯思維與理由（例如鏡頭功能、節奏、資訊量）",\n'
        '  "confidence": 0.85 (0.0到1.0之間的數字)\n'
        "}"
    )

    user_prompt = f"【素材時間點】：{time_str}\n【畫面視覺內容】：{visual}\n【音訊語音內容】：{audio}\n\n請針對這個片段給出剪輯決策："
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to("cuda")

    with torch.no_grad():
        generated_ids = model.generate(**model_inputs, max_new_tokens=256, temperature=0.3)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    try:
        clean_res = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_res)
    except Exception:
        data = {"recommendation": "待人工檢視", "reason": response, "confidence": 0.5}

    return {
        "time": time_str, "visual": visual, "audio": audio,
        "recommendation": data.get("recommendation", "保留"),
        "reason": data.get("reason", ""), "confidence": data.get("confidence", 0.8)
    }

def run_director_pipeline(input_path=None, output_path=None, model=None, tokenizer=None):
    if input_path is None: input_path = ROOT_DIR / "05_Output" / "analysis" / "timeline_integrated.json"
    if output_path is None: output_path = ROOT_DIR / "05_Output" / "reports" / "director_decisions.json"
    
    print("[Director] 啟動 AI 導演決策管線...")
    if model is None or tokenizer is None:
        model, tokenizer = load_director_model()
        
    if not input_path.exists():
        print(f"[Director] 找不到中間資料表: {input_path}")
        return False
        
    with open(input_path, "r", encoding="utf-8") as f:
        timeline_segments = json.load(f)
        
    decisions = []
    for seg in timeline_segments:
        print(f"-> 正在審查 [{seg['time']}] 片段...")
        d = run_director_llm(seg, model, tokenizer)
        decisions.append(d)
        
    print(f"\n[Director] 共處理 {len(decisions)} 筆決策，正在寫入報告...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 決策報告已儲存至: {output_path}")
    return decisions

if __name__ == '__main__':
    run_director_pipeline()
