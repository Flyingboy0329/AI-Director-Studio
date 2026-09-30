import os
import sys
import json
import cv2
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "05_Output"
LUA_TASK_OUT = OUTPUT_DIR / "test_marker_task.lua"

def score_to_rpg_tier(score):
    # 嚴格遵循非直覺對調規則：傳說掛藍球 🔵，精良掛黃球 🟡
    if score >= 90:
        return "Yellow", "【傳說 🔵】"
    elif score >= 80:
        return "Purple", "【史詩 🟣】"
    elif score >= 70:
        return "Blue", "【精良 🟡】"
    elif score >= 55:
        return "Green", "【優秀 🟢】"
    else:
        return "Cream", "【普通 ⚪】"

def clean_comment_text(comments):
    parts = []
    for c in comments:
        for sub in c.replace("，", "/").replace("、", "/").split("/"):
            s = sub.strip()
            if s and s not in parts:
                parts.append(s)
    short_summary = "/".join(parts[:2])
    return short_summary if short_summary else "品質平穩"

def build_continuous_segments(raw_items, total_frames, fps):
    if not raw_items:
        return [{
            "start_frame": 0,
            "duration_frames": total_frames,
            "color": "Blue",
            "name": "V_Default",
            "note": "[AI-V] 評分 70 【精良 🟡】 | 常規素材"
        }]

    clusters = []
    current = {
        "start_frame": 0,
        "score": raw_items[0]["score"],
        "comments": [raw_items[0]["comment"]]
    }

    for item in raw_items[1:]:
        color_curr, _ = score_to_rpg_tier(current["score"])
        color_next, _ = score_to_rpg_tier(item["score"])
        
        if color_curr != color_next:
            current["end_frame"] = item["start_frame"]
            clusters.append(current)
            current = {
                "start_frame": item["start_frame"],
                "score": item["score"],
                "comments": [item["comment"]]
            }
        else:
            current["comments"].append(item["comment"])

    current["end_frame"] = total_frames
    clusters.append(current)

    markers = []
    for c in clusters:
        start_f = c["start_frame"]
        dur_f = max(1, c["end_frame"] - start_f)
        color, tier_tag = score_to_rpg_tier(c["score"])
        comment_str = clean_comment_text(c["comments"])
        
        note = f"[AI-V] 評分 {c['score']} {tier_tag} | {comment_str}"
        
        markers.append({
            "start_frame": start_f,
            "duration_frames": dur_f,
            "color": color,
            "name": f"V_{c['score']}",
            "note": note
        })
    return markers

def build_markers(video_clip_name="japan_walk", video_path=None, raw_video_file=None, vision_json=None, audio_json=None):
    data_dir = PROJECT_ROOT / "02_Data"
    
    if vision_json is None:
        vision_json = data_dir / "vision_analysis.json"
    if audio_json is None:
        audio_json = data_dir / "audio_analysis.json"
    if video_path is None:
        video_path = data_dir / "video" / f"{video_clip_name}_video.mp4"

    raw_path_str = str(raw_video_file).replace("\\", "/") if raw_video_file else ""

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1048
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    cap.release()
    
    with open(vision_json, "r", encoding="utf-8") as f:
        v_data = json.load(f)
        
    video_markers = build_continuous_segments(v_data, total_frames, fps)

    lua_lines = [
        "return {",
        "    schema_version = 2,",
        f'    task_id = "ai_director_{video_clip_name}",',
        f'    video_clip_name = "{video_clip_name}",',
        f'    video_file_path = "{raw_path_str}",',
        "    video_markers = {"
    ]
    for m in video_markers:
        lua_lines.append(f"        {{ start_frame = {m['start_frame']}, duration_frames = {m['duration_frames']}, color = \"{m['color']}\", name = \"{m['name']}\", note = \"{m['note']}\" }},")
    lua_lines.append("    }")
    lua_lines.append("}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LUA_TASK_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lua_lines))
    print(f"✅ [Director] 任務檔已校準（金色傳說 🔵 / 藍色精良 🟡）: {LUA_TASK_OUT.name}")

if __name__ == "__main__":
    build_markers()