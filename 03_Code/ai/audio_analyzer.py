import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import sys
import json
import torch
from pathlib import Path
from faster_whisper import WhisperModel

DEFAULT_PROMPT = "這是一段日常生活旅遊 Vlog，包含中英文混雜對話、日文地名與生活環境音開箱。"

def detect_device_and_model():
    if torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        device = "cuda"
        compute_type = "float16"
        if vram_gb >= 6.0:
            model_size = "medium"
        elif vram_gb >= 3.0:
            model_size = "small"
        else:
            model_size = "base"
            compute_type = "int8"
    else:
        device = "cpu"
        compute_type = "int8"
        model_size = "small"
    return device, compute_type, model_size

def calculate_speech_score(text, duration, no_speech_prob=0.0):
    char_len = len(text)
    if char_len == 0 or no_speech_prob > 0.6:
        return 30
    dur = max(0.1, duration)
    cps = char_len / dur
    if 2.0 <= cps <= 6.0 and char_len >= 4:
        return 85
    elif char_len >= 2:
        return 70
    else:
        return 50

def analyze_audio(wav_path, output_json_path, model_name=None, context_prompt=None):
    auto_device, auto_compute, auto_model = detect_device_and_model()
    target_model = model_name or auto_model
    final_prompt = context_prompt.strip() if context_prompt and context_prompt.strip() else DEFAULT_PROMPT
    
    print(f"[Faster-Whisper] 🚀 硬體探測就緒: 裝置={auto_device} | 精度={auto_compute} | 模型={target_model}")
    print(f"[Faster-Whisper] 📝 使用領域情境 Prompt: {final_prompt}")
    print(f"[Faster-Whisper] 🎙 正在載入模型推論中...")
    
    model = WhisperModel(target_model, device=auto_device, compute_type=auto_compute)
    
    segments, info = model.transcribe(
        str(wav_path),
        initial_prompt=final_prompt,
        beam_size=5,
        vad_filter=True
    )
    
    print(f"[Faster-Whisper] 🌐 自動偵測語言: {info.language} (信心度: {info.language_probability:.2f})")
    print(f"[Faster-Whisper] 🔍 語音片段解析與評分中...")
    
    analyzed_data = []
    for seg in segments:
        text = seg.text.strip()
        dur = seg.end - seg.start
        score = calculate_speech_score(text, dur, seg.no_speech_prob)
        start_t = round(seg.start, 2)
        end_t = round(seg.end, 2)
        
        if text:
            analyzed_data.append({
                "start": start_t,
                "end": end_t,
                "duration": round(dur, 2),
                "score": score,
                "text": text
            })
            print(f"  ► [{start_t:.1f}s - {end_t:.1f}s] 分數: {score} | 台詞: {text}")

    Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(analyzed_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ [Faster-Whisper] 分析完成，已存入: {Path(output_json_path).name}")
    return analyzed_data

if __name__ == "__main__":
    test_wav = r"C:\Users\pan\Desktop\AI_Director\02_Data\audio\japan_walk_audio.wav"
    out_json = r"C:\Users\pan\Desktop\AI_Director\02_Data\audio_analysis.json"
    if os.path.exists(test_wav):
        analyze_audio(test_wav, out_json)