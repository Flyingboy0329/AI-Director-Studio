import os
import cv2
import json
import numpy as np
from pathlib import Path

def evaluate_frame_quality(frame):
    # 1. 轉灰階
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 2. 清晰度 (Laplacian 方差，數值越小越模糊/晃動)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # 3. 亮度與過曝/死黑檢測 (夜景適中亮度約 40-120)
    mean_brightness = np.mean(gray)
    
    # 基礎分 60 (優秀空鏡)
    score = 65
    tags = []
    
    # 清晰度加減分
    if laplacian_var > 150:
        score += 25  # 細節極其清晰銳利
        tags.append("細節銳利")
    elif laplacian_var > 80:
        score += 15  # 正常清晰
        tags.append("畫面穩定")
    elif laplacian_var < 35:
        score -= 25  # 手持晃動模糊
        tags.append("運鏡晃動失焦")
        
    # 亮度加減分
    if 45 <= mean_brightness <= 110:
        score += 10  # 理想夜景氛圍光影
        tags.append("夜景光影層次佳")
    elif mean_brightness < 25:
        score -= 20  # 畫面過暗死黑
        tags.append("欠曝死黑")
    elif mean_brightness > 180:
        score -= 20  # 強光過曝
        tags.append("過曝溢光")
        
    score = max(20, min(98, score))
    comment = " / ".join(tags) if tags else "常規過渡空鏡"
    return score, comment

def analyze_video(video_path, output_json, sample_interval_sec=2.0):
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"❌ 找不到視訊檔案: {video_file}")
        return None
        
    cap = cv2.VideoCapture(str(video_file))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps
    
    print(f"[Vision] 🎬 分析視訊: {video_file.name} (FPS: {fps:.2f}, 總時長: {duration_sec:.2f}s)")
    print(f"[Vision] ⏱️ 取樣頻率: 每 {sample_interval_sec} 秒抽樣一影格進行視覺評鑑...")
    
    frame_step = int(fps * sample_interval_sec)
    results = []
    
    current_frame = 0
    while current_frame < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()
        if not ret:
            break
            
        score, comment = evaluate_frame_quality(frame)
        sec = current_frame / fps
        results.append({
            "start_frame": current_frame,
            "duration_frames": int(fps * sample_interval_sec),
            "start_sec": round(sec, 2),
            "score": score,
            "comment": comment
        })
        
        # 終端即時顯示
        tier_symbol = "🟡 傳說" if score >= 90 else ("🟣 史詩" if score >= 80 else ("🟢 優秀" if score >= 55 else "⚪ 普通"))
        print(f"   ► [{sec:.1f}s / 格數: {current_frame}] 分數: {score} | {tier_symbol} | {comment}")
        
        current_frame += frame_step
        
    cap.release()
    
    out_path = Path(output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"✅ [Vision] 視覺分析完成，已儲存至: {out_path.name}")
    return results

if __name__ == "__main__":
    v_target = r"C:\Users\pan\Desktop\AI_Director\02_Data\video\japan_walk_video.mp4"
    j_out = r"C:\Users\pan\Desktop\AI_Director\02_Data\vision_analysis.json"
    analyze_video(v_target, j_out)