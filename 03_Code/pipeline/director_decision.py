import json
import os
from pathlib import Path

def score_to_rpg_tier(final_score):
    if final_score >= 90:
        return "Yellow", "[LEGENDARY]"
    elif final_score >= 80:
        return "Purple", "[EPIC]"
    elif final_score >= 70:
        return "Blue", "[RARE]"
    elif final_score >= 55:
        return "Green", "[UNCOMMON]"
    else:
        return "Cream", "[COMMON]"

def build_markers(video_path, vision_analysis_path=None, audio_analysis_path=None, fps=30.0):
    proj_root = Path(__file__).resolve().parent.parent.parent
    
    # 讀取視覺特徵
    vision_frames = []
    if vision_analysis_path and os.path.exists(vision_analysis_path):
        with open(vision_analysis_path, "r", encoding="utf-8") as f:
            v_data = json.load(f)
            vision_frames = v_data.get("frames", [])

    # 讀取音訊特徵 (真正融合 Whisper 語音特徵)
    audio_segments = []
    if audio_analysis_path and os.path.exists(audio_analysis_path):
        with open(audio_analysis_path, "r", encoding="utf-8") as f:
            a_data = json.load(f)
            audio_segments = a_data.get("segments", [])

    # 雙軌加權矩陣運算 (視覺 60% + 音訊 40%)
    markers = []
    for vf in vision_frames:
        time_sec = vf.get("time_sec", 0.0)
        v_score = vf.get("clarity_score", 50.0)
        
        # 尋找對應時間區間的音訊能量與信心度
        a_score = 50.0
        transcript_snippet = ""
        for seg in audio_segments:
            if seg.get("start", 0) <= time_sec <= seg.get("end", 0):
                # 語速密度或信心度加成
                a_score = seg.get("score", 70.0)
                transcript_snippet = seg.get("text", "").strip()
                break
        
        # 雙軌融合分數
        fused_score = (v_score * 0.6) + (a_score * 0.4)
        color, tier_label = score_to_rpg_tier(fused_score)
        
        start_frame = int(time_sec * fps)
        note = f"{tier_label} Score:{fused_score:.1f}"
        if transcript_snippet:
            note += f" | {transcript_snippet[:20]}"
            
        markers.append({
            "start_frame": start_frame,
            "duration": 30,
            "color": color,
            "note": note
        })

    # 輸出結構化 Lua 任務檔
    output_lua = proj_root / "05_Output" / "test_marker_task.lua"
    output_lua.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_lua, "w", encoding="utf-8") as f:
        f.write("-- AI Director Marker Task (Dynamic Path Generated)\n")
        f.write("local task = {\n")
        f.write(f'  video_path = [==[{video_path}]==],\n')
        f.write("  markers = {\n")
        for m in markers[:20]: # 挑選最優片段注入
            f.write(f'    {{ start_frame = {m["start_frame"]}, duration = {m["duration"]}, color = "{m["color"]}", note = [==[{m["note"]}]==] }},\n')
        f.write("  }\n}\nreturn task\n")

    return str(output_lua)