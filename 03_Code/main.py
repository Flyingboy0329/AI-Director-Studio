import sys
import os
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent

sys.path.insert(0, str(CODE_DIR))
sys.path.append(str(CODE_DIR / "ai"))
sys.path.append(str(CODE_DIR / "pipeline"))
sys.path.append(str(CODE_DIR / "bridge"))

from video_extract import split_media
from audio_analyzer import analyze_audio
from vision_analyzer import analyze_video
import director_decision
import auto_injector

def log_task_result(task_log, logs_dir):
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"task_{timestamp}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(task_log, f, ensure_ascii=False, indent=2)
    print(f"\n[日誌] 任務執行紀錄已留存: {log_file.name}")

def run_main_pipeline(input_video_path, context_prompt=None):
    start_total_time = time.time()
    input_file = Path(input_video_path).resolve()
    clip_base_name = input_file.stem
    
    data_dir = (PROJECT_ROOT / "02_Data").resolve()
    output_dir = (PROJECT_ROOT / "05_Output").resolve()
    logs_dir = output_dir / "logs"

    task_log = {
        "task_id": datetime.now().strftime(f"{clip_base_name}_%Y%m%d_%H%M%S"),
        "clip_name": clip_base_name,
        "input_video": str(input_file),
        "status": "PROCESSING",
        "stages": {},
        "error_message": None,
        "total_duration_sec": 0
    }

    print("=" * 60)
    print("🎬 【AI Director 智慧導演管線】任務啟動")
    print(f"📁 輸入素材名稱: {clip_base_name}")
    print(f"📁 檔案絕對路徑: {input_file}")
    print(f"🕒 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not input_file.exists():
        err = f"找不到輸入影片檔案: {input_file}"
        print(f"❌ [錯誤] {err}")
        task_log["status"] = "FAILED_INPUT_NOT_FOUND"
        task_log["error_message"] = err
        log_task_result(task_log, logs_dir)
        return False

    valid_extensions = [".mp4", ".mov", ".mkv", ".avi"]
    if input_file.suffix.lower() not in valid_extensions:
        err = f"不支援的格式: {input_file.suffix}"
        print(f"❌ [錯誤] {err}")
        task_log["status"] = "FAILED_INVALID_FORMAT"
        task_log["error_message"] = err
        log_task_result(task_log, logs_dir)
        return False

    try:
        # Step 1: 媒體拆分
        t0 = time.time()
        print("\n[1/4] 🔨 FFmpeg 影音分離中...")
        v_out, a_out = split_media(str(input_file), str(data_dir))
        if not v_out or not a_out or not Path(v_out).exists():
            raise RuntimeError("FFmpeg 分離產物遺失或執行失敗")
        task_log["stages"]["step1_ffmpeg"] = {"status": "SUCCESS", "duration_sec": round(time.time() - t0, 2)}
        print(f"  └─ 完成！耗時: {time.time() - t0:.2f} 秒")

        # Step 2: 雙軌特徵抽取
        t0 = time.time()
        print("\n[2/4] 🧠 影音特徵抽取推論中...")
        audio_json_path = (data_dir / "audio_analysis.json").resolve()
        vision_json_path = (data_dir / "vision_analysis.json").resolve()
        
        analyze_audio(a_out, str(audio_json_path), context_prompt=context_prompt)
        analyze_video(v_out, str(vision_json_path), sample_interval_sec=2.0)
        task_log["stages"]["step2_ai_analysis"] = {"status": "SUCCESS", "duration_sec": round(time.time() - t0, 2)}
        print(f"  └─ 完成！推論耗時: {time.time() - t0:.2f} 秒")

        # Step 3: 動態透傳素材名稱與實體路徑給導演決策層
        t0 = time.time()
        print("\n[3/4] 👑 導演決策層：動態品級映射與連續色譜建構...")
        director_decision.build_markers(
            video_clip_name=clip_base_name,
            video_path=Path(v_out),
            raw_video_file=input_file,
            vision_json=vision_json_path,
            audio_json=audio_json_path
        )
        task_log["stages"]["step3_director_decision"] = {"status": "SUCCESS", "duration_sec": round(time.time() - t0, 2)}
        print(f"  └─ 完成！決策耗時: {time.time() - t0:.2f} 秒")

        # Step 4: DaVinci Resolve 自動注入
        t0 = time.time()
        print("\n[4/4] 🚀 跨進程喚起 DaVinci Resolve 進行標記注入...")
        inject_success = auto_injector.run_auto_inject()
        
        if not inject_success:
            raise RuntimeError("無法連線至 DaVinci Resolve，請確認軟體是否啟動。")

        task_log["stages"]["step4_resolve_injection"] = {"status": "SUCCESS", "duration_sec": round(time.time() - t0, 2)}

        total_time = time.time() - start_total_time
        task_log["status"] = "SUCCESS"
        task_log["total_duration_sec"] = round(total_time, 2)

        print("\n" + "=" * 60)
        print("🎉 【AI Director】全管線處理完畢，無感閉環成功！")
        print(f"⏱️ 總運算耗時: {total_time:.2f} 秒")
        print("📊 標記注入: ✅ 已完成動態精確刷新")
        print("=" * 60)

        log_task_result(task_log, logs_dir)
        return True

    except Exception as e:
        total_time = time.time() - start_total_time
        task_log["status"] = "FAILED"
        task_log["error_message"] = str(e)
        task_log["total_duration_sec"] = round(total_time, 2)
        print(f"\n❌ Pipeline 執行異常: {e}")
        log_task_result(task_log, logs_dir)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Director 一鍵式自動化標記管線")
    parser.add_argument(
        "video",
        nargs="?",
        default=str((PROJECT_ROOT / "02_Data" / "japan_walk.mp4").resolve()),
        help="輸入影片檔案路徑"
    )
    args = parser.parse_args()
    run_main_pipeline(args.video)