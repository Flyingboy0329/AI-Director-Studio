#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_run.py
快速測試腳本：模擬運行 main pipeline 並驗證 auto_injector 串接
"""
import os
import sys
import logging
from pathlib import Path

# 設定路徑
ROOT_DIR = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_pipeline():
    logging.info("=== 開始測試 AI Director 全流程 (Mock Mode) ===")
    
    # 1. 載入模組
    try:
        from ai.video_extract import extract_video_assets
        from ai.audio_transcribe import transcribe_audio
        from ai.vision_analyze import run_vision_analysis
        from bridge.integrate_timeline import integrate_timeline
        from ai.director import run_director_pipeline
        from bridge.export_markers import generate_shot_region_edl, aggregate_shot_regions, generate_mock_seconds_data
        from bridge.auto_injector import auto_inject_resolve
        logging.info("✅ 所有模組導入成功")
    except ImportError as e:
        logging.error(f"❌ 模組導入失敗: {e}")
        return False

    # 2. 模擬 Step 1-6
    logging.info("[Step 1] Mock 資料生成...")
    audio_dir = ROOT_DIR / "02_Data" / "audio"
    frames_dir = ROOT_DIR / "02_Data" / "frames"
    audio_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "input_audio.wav").write_text("dummy")
    (frames_dir / "frame_0001.jpg").write_text("dummy")
    
    logging.info("[Step 2-3] 跳過 Audio/Vision (Mock)")
    logging.info("[Step 4] 整合時間軸...")
    integrate_timeline()
    logging.info("[Step 5] 模擬導演推理...")
    run_director_pipeline()
    
    logging.info("[Step 6] 匯出 EDL 與聚合標記...")
    decisions_path = ROOT_DIR / "05_Output" / "reports" / "director_decisions.json"
    mock_data = generate_mock_seconds_data()
    aggregated_shots = aggregate_shot_regions(mock_data)
    generate_shot_region_edl(aggregated_shots)
    logging.info(f"✅ 已產出 {len(aggregated_shots)} 筆聚合標記")

    # 3. 測試 Step 7: Auto Injector
    logging.info("[Step 7] 測試自動化注入控制器...")
    try:
        auto_inject_resolve()
        logging.info("✅ Step 7 測試成功")
    except Exception as e:
        logging.warning(f"⚠️ Step 7 觸發例外 (預期內，因沙盒無 GUI): {e}")

    logging.info("=== 全流程測試完成 ===")
    return True

if __name__ == "__main__":
    test_pipeline()
