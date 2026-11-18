import os
import json
import cv2
import numpy as np
from pathlib import Path
from cancellation import check_cancelled

def evaluate_frame_quality(image):
    """基礎 CV 畫面特徵分析（光影、清晰度、對比度）"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    mean_brightness = np.mean(gray)
    
    score = 60.0
    tags = []

    # 模糊/失焦判定
    if laplacian_var < 80.0:
        score -= 20.0
        tags.append("邊緣細節少（可能模糊或低紋理）")
    elif laplacian_var > 300.0:
        score += 15.0
        tags.append("邊緣細節豐富")

    # 曝光光影判定
    if 70.0 <= mean_brightness <= 170.0:
        score += 15.0
        tags.append("平均亮度在參考範圍")
    elif mean_brightness < 40.0:
        score -= 15.0
        tags.append("畫面暗部過深")
    elif mean_brightness > 210.0:
        score -= 15.0
        tags.append("過曝微沖")

    score = max(30.0, min(95.0, score))
    comment = " / ".join(tags) if tags else "常規過渡空鏡"
    return score, comment

def analyze_vision(video_path, output_json_path, sample_interval_sec=2.0, cancel_event=None):
    """標準視覺分析入口函式，輸出結構化 json"""
    v_file = Path(video_path).resolve()
    if not v_file.exists():
        print(f"[Vision] ❌ 找不到視訊檔案: {v_file}")
        return {}

    cap = cv2.VideoCapture(str(v_file))
    if not cap.isOpened():
        print(f"[Vision] ❌ 無法開啟視訊解碼: {v_file}")
        return {}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_duration = total_frames / fps if fps > 0 else 0.0

    print(f"[Vision] 🎬 分析視訊: {v_file.name} (FPS: {fps:.2f}, 總時長: {total_duration:.2f}s)")
    print(f"[Vision] ⏱️ 採樣頻率: 每 {sample_interval_sec} 秒抽樣一影格...")

    sample_step_frames = max(1, int(fps * sample_interval_sec))
    frames_data = []

    current_frame_idx = 0
    while current_frame_idx < total_frames:
        if cancel_event is not None and cancel_event.is_set():
            cap.release()
            check_cancelled(cancel_event)
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        time_sec = current_frame_idx / fps
        score, comment = evaluate_frame_quality(frame)

        frames_data.append({
            "frame_idx": current_frame_idx,
            "start_sec": round(time_sec, 2),
            "time_sec": round(time_sec, 2),
            "duration_frames": sample_step_frames,
            "score": score,
            "comment": comment
        })

        current_frame_idx += sample_step_frames

    cap.release()

    result = {
        "video_file": str(v_file),
        "total_duration_sec": round(total_duration, 2),
        "total_frames": total_frames,
        "fps": fps,
        "frames": frames_data
    }

    out_path = Path(output_json_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ [Vision] 視覺分析完成，已儲存至: {out_path.name}")
    return result

# 兼容舊命名
analyze_video_frames = analyze_vision
analyze_video = analyze_vision

# 匯入相容別名映射
analyze_vision = analyze_video
