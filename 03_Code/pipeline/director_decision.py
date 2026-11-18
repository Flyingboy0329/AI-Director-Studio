import os
import json
import cv2
import uuid
from pathlib import Path
from path_utils import get_project_root

PROJ_ROOT = get_project_root()
OUTPUT_DIR = PROJ_ROOT / "05_Output"


def lua_string(value):
    """Model-generated notes are data, never executable Lua."""
    text = str(value)
    equals = "=="
    while f"]{equals}]" in text:
        equals += "="
    return f"[{equals}[{text}]{equals}]"

def score_to_rpg_tier(final_score):
    if final_score >= 80:
        return "Yellow", "【🟡️ 傳說・黃】"
    elif final_score >= 60:
        return "Purple", "【🟣 史詩・紫】"
    elif final_score >= 40:
        return "Blue", "【🔵️ 精良・藍】"
    elif final_score >= 20:
        return "Green", "【🟢 優秀・綠】"
    else:
        return "Cream", "【⚪ 普通・白灰】"

def get_video_exact_info(video_path):
    """精準探測影片原檔的真實 FPS 與總影格數"""
    try:
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            return fps, total_frames
    except Exception:
        pass
    return 30.0, 0

def build_markers(video_path=None, vision_analysis_path=None, audio_analysis_path=None, fps=30.0, **kwargs):
    v_path = video_path or kwargs.get("raw_video_file") or kwargs.get("video_file")
    v_path_resolved = str(Path(v_path).resolve()).replace("\\", "/") if v_path else ""
    clip_name = kwargs.get("video_clip_name") or (Path(v_path).name if v_path else "clip")
    v_json = vision_analysis_path or kwargs.get("vision_json")
    a_json = audio_analysis_path or kwargs.get("audio_json")

    # 探測原片總影格數
    real_fps, total_video_frames = get_video_exact_info(v_path)
    if real_fps > 0:
        fps = real_fps
    if total_video_frames <= 0:
        raise ValueError("無法取得原片總影格數，停止產生標記，避免不完整覆蓋。")

    vision_frames = []
    if v_json and Path(v_json).exists():
        with open(v_json, "r", encoding="utf-8") as f:
            v_data = json.load(f)
            vision_frames = v_data.get("frames", []) if isinstance(v_data, dict) else v_data

    audio_segments = []
    if a_json and Path(a_json).exists():
        with open(a_json, "r", encoding="utf-8") as f:
            a_data = json.load(f)
            audio_segments = a_data.get("segments", []) if isinstance(a_data, dict) else a_data

    raw_points = []
    for vf in vision_frames:
        time_sec = vf.get("start_sec", vf.get("time_sec", 0.0))
        v_score = vf.get("score", 50.0)
        v_comment = vf.get("comment", "畫面過渡")

        a_score = 50.0
        has_speech = False
        for seg in audio_segments:
            if seg.get("start", 0) <= time_sec <= seg.get("end", 0):
                a_score = seg.get("score", 65.0)
                text = seg.get("text", "").strip()
                if text and len(text) > 2 and "Vlog" not in text:
                    has_speech = True
                break

        fused_score = (v_score * 0.65) + (a_score * 0.35)
        color, tier_label = score_to_rpg_tier(fused_score)
        # Preserve the original sample index: rounded seconds lose frames at 29.97 fps.
        start_frame = int(vf["frame_idx"]) if "frame_idx" in vf else round(time_sec * fps)
        start_frame = max(0, min(total_video_frames - 1, start_frame))

        shot_name = f"評級：{tier_label}"
        note = f"建議：{v_comment}（僅技術抽樣，尚無語義分析）"
        if has_speech:
            note += " (含人聲)"
        semantic = vf.get("semantic")
        if semantic:
            fused_score = semantic["score"] * 0.7 + fused_score * 0.3
            color, tier_label = score_to_rpg_tier(fused_score)
            shot_name = f"評級：{tier_label}"
            note = f"建議：{semantic.get('edit_suggestion') or semantic['reason']}"
            if semantic.get("status") == "degraded":
                color = "Orange"
                shot_name = "評級：【🟠 待確認】"
                note = "建議：本區間 AI 分析未完成，請回看素材後決定；不代表素材品質差。"

        raw_points.append({
            "start_frame": start_frame,
            "color": color,
            "name": shot_name,
            "note": note,
            "semantic": bool(semantic),
            "score": fused_score
        })

    if not raw_points:
        raise ValueError("沒有畫面分析結果，停止產生標記，不能以預設評分代替分析。")

    raw_points.sort(key=lambda x: x["start_frame"])
    raw_points = list({pt["start_frame"]: pt for pt in raw_points}.values())
    raw_points[0]["start_frame"] = 0 # 保證第 0 格起點

    # 1. 預先融合相鄰同色點
    compressed = []
    for pt in raw_points:
        if not compressed:
            compressed.append(pt)
            continue
        prev = compressed[-1]
        if prev["color"] == pt["color"] and (
                (not prev["semantic"] and not pt["semantic"]) or prev["note"] == pt["note"]):
            prev["score"] = round((prev["score"] + pt["score"]) / 2, 1)
        else:
            compressed.append(pt)

    # 2. 算滿版時長：Snap to Next，且最後一段直達影片終點影格
    full_markers = []
    for i in range(len(compressed)):
        cur = compressed[i]
        if i < len(compressed) - 1:
            next_pt = compressed[i + 1]
            dur = max(1, next_pt["start_frame"] - cur["start_frame"])
        else:
            # 最後一段吸附到影片最後一格
            if total_video_frames > cur["start_frame"]:
                dur = total_video_frames - cur["start_frame"]
            else:
                dur = int(fps * 3.0)

        full_markers.append({
            "start_frame": cur["start_frame"],
            "duration": dur,
            "color": cur["color"],
            "name": cur["name"],
            "note": cur["note"]
        })

    cursor = 0
    for marker in full_markers:
        if marker["start_frame"] != cursor or marker["duration"] <= 0:
            raise ValueError("標記有重疊或缺口，已停止輸出。")
        cursor += marker["duration"]
    if cursor != total_video_frames:
        raise ValueError("標記未覆蓋原片總影格數，已停止輸出。")

    tail = full_markers[-1]
    print(f"[標記覆蓋] 尾段 [{tail['start_frame']}, {cursor}) 格，"
          f"{tail['duration']/fps:.3f} 秒；已覆蓋 {cursor}/{total_video_frames} 格。")

    output_lua = Path(kwargs.get("output_lua_path") or OUTPUT_DIR / "test_marker_task.lua")
    output_lua.parent.mkdir(parents=True, exist_ok=True)
    output_lua.with_name("marker_coverage.json").write_text(json.dumps({
        "fps": fps, "total_frames": total_video_frames, "covered_frames": cursor,
        "tail_start_frame": tail["start_frame"], "tail_end_frame_exclusive": cursor,
        "markers": full_markers}, ensure_ascii=False, indent=2), encoding="utf-8")
    result_path = OUTPUT_DIR / "receipts" / f"{uuid.uuid4().hex}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_lua, "w", encoding="utf-8") as f:
        f.write("-- AI Director Marker Task (True Full-Coverage)\n")
        f.write("local task = {\n")
        f.write(f'  video_path = [==[{v_path_resolved}]==],\n')
        f.write(f'  video_file_path = [==[{v_path_resolved}]==],\n')
        f.write(f'  video_clip_name = [==[{clip_name}]==],\n')
        f.write(f'  total_frames = {total_video_frames},\n')
        f.write(f'  result_path = [==[{result_path.as_posix()}]==],\n')
        f.write("  video_markers = {\n")
        for m in full_markers:
            f.write(f'    {{ start_frame = {m["start_frame"]}, duration_frames = {m["duration"]}, color = "{m["color"]}", name = {lua_string(m["name"])}, note = {lua_string(m["note"])} }},\n')
        f.write("  }\n}\nreturn task\n")

    print(f"[Decision] 👑 原片母帶長度: {total_video_frames} 格，無縫滿版生成 {len(full_markers)} 筆標記 -> {output_lua.name}")
    return str(output_lua)
