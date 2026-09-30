import time
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent
DATA_DIR = PROJECT_ROOT / "02_Data"

sys.path.insert(0, str(CODE_DIR))
from main import run_main_pipeline

SUPPORTED_EXT = {".mp4", ".mov", ".mkv", ".avi"}

def wait_for_file_ready(file_path, check_interval=1.0, retries=3):
    """確認檔案複製完畢（大小穩定未被鎖定）"""
    last_size = -1
    stable_count = 0
    while stable_count < retries:
        try:
            current_size = file_path.stat().st_size
            if current_size == last_size and current_size > 0:
                stable_count += 1
            else:
                stable_count = 0
            last_size = current_size
        except Exception:
            stable_count = 0
        time.sleep(check_interval)
    return True

def start_watching():
    print("=" * 60)
    print("👀 【AI Director 哨兵守護進程啟動】")
    print(f"📂 正在監看資料夾: {DATA_DIR}")
    print("💡 使用方式：只要把影片放進 02_Data，系統會自動分析並匯入 Resolve！")
    print("按 Ctrl + C 可隨時停止監看。")
    print("=" * 60)

    # 紀錄既有檔案，避免重複處理歷史舊片
    processed_files = set()
    for f in DATA_DIR.glob("*.*"):
        if f.suffix.lower() in SUPPORTED_EXT:
            processed_files.add(f.resolve())

    while True:
        try:
            time.sleep(2)
            current_files = [f for f in DATA_DIR.glob("*.*") if f.suffix.lower() in SUPPORTED_EXT]
            
            for file_path in current_files:
                resolved_path = file_path.resolve()
                if resolved_path not in processed_files:
                    print(f"\n🔔 [發現新素材] 偵測到新丟入的影片: {file_path.name}")
                    print("⏳ 正在等待檔案寫入就緒...")
                    wait_for_file_ready(file_path)
                    
                    print(f"🚀 開始自動執行 AI 分析與 Resolve 匯入...")
                    success = run_main_pipeline(str(resolved_path))
                    
                    if success:
                        processed_files.add(resolved_path)
                        print(f"✨ 素材 [{file_path.name}] 已全自動處理完畢並匯入 DaVinci Resolve！")
                    else:
                        print(f"⚠️ 處理失敗，稍後可手動重試。")

        except KeyboardInterrupt:
            print("\n🛑 哨兵守護進程已手動停止。")
            break
        except Exception as e:
            print(f"⚠️ 監聽異常: {e}")
            time.sleep(2)

if __name__ == "__main__":
    start_watching()