import os
import sys
import time
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_EXCEPTION
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from path_utils import get_project_root, load_local_settings
PROJ_ROOT = get_project_root()

from ai.video_extract import split_media
from ai.audio_analyzer import analyze_audio, get_whisper_runtime
from ai.vision_analyzer import analyze_vision
from pipeline.director_decision import build_markers
from bridge.auto_injector import trigger_resolve_injection
from ai.semantic_analyzer import analyze_semantics, prepare_clients, prepare_visual_observations
from cancellation import check_cancelled, LinkedCancellation
from pipeline.submission import submit_markers
from job_cleanup import mark_job_owned, cleanup_job

def run_main_pipeline(input_video_path, context_prompt=None, whisper_model=None, model_settings=None, cancel_event=None):
    check_cancelled(cancel_event)
    raw_video = Path(input_video_path).resolve()
    if not raw_video.exists():
        print(f"[Pipeline] ❌ 找不到素材檔案: {raw_video}")
        return False

    print("=" * 60)
    print(f"🎬 【AI Director 智慧導演管線】任務啟動")
    print(f"📁 輸入素材母帶 (含完整影音): {raw_video.name}")
    print(f"🕒 啟動時間: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 拆分特徵提取用暫存檔 (精確傳入 input_path 與 output_dir 兩個參數)
    if model_settings is None:
        model_settings = load_local_settings("model_settings.json")
    # Own intermediates per job until dispatch; successful jobs are cleaned below.
    data_dir = PROJ_ROOT / "05_Output" / "jobs" / uuid.uuid4().hex
    data_dir.mkdir(parents=True, exist_ok=True)
    mark_job_owned(data_dir, raw_video)
    print(f"[Pipeline] Whisper 計畫：{whisper_model or '依 RAM 自動選型'}；CPU／RAM、INT8，與視覺工作並行。")
    v_temp, a_temp = split_media(str(raw_video), str(data_dir))
    check_cancelled(cancel_event)

    if not v_temp or not a_temp:
        print("[Pipeline] ❌ 影音分離失敗，終止任務。")
        return False

    # 2. 影音特徵抽取推論
    cancel_event = LinkedCancellation(cancel_event)
    a_json = data_dir / "audio_analysis.json"
    v_json = data_dir / "vision_analysis.json"
    separate = (model_settings.get("model_mode", "separate") == "separate" and
                bool(model_settings.get("llm_path") and model_settings.get("vlm_path") and model_settings.get("mmproj_path")))
    def visual_work():
        result = analyze_vision(v_temp, str(v_json), cancel_event=cancel_event)
        if not result or not result.get("frames"):
            raise ValueError("畫面分析未產生有效結果，停止處理。")
        observations = prepare_visual_observations(raw_video, result, model_settings,
                            cancel_event=cancel_event) if separate else None
        return result, observations
    print("[並行] A 方案：CPU 語音＋獨立 VLM 畫面理解。" if separate else
          "[並行] B／技術方案：CPU 語音＋影格技術分析；主模型等待兩者完成。")
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="director-media") as executor:
        audio_future = executor.submit(analyze_audio, a_temp, str(a_json), model_name=whisper_model,
                          context_prompt=model_settings.get("whisper_prompt", ""),
                          cancel_event=cancel_event, runtime=get_whisper_runtime())
        visual_future = executor.submit(visual_work)
        done, _ = wait((audio_future, visual_future), return_when=FIRST_EXCEPTION)
        for future in done:
            if future.exception() is not None:
                cancel_event.set()
                future.result()
        # A failure propagates, never masquerades as an empty transcript.
        audio = audio_future.result()
        vision, visual_cache = visual_future.result()
    check_cancelled(cancel_event)
    print(f"[同步完成] 語音轉錄完成（{len(audio)} 段），視覺工作完成；現在才允許影音整合。")
    if model_settings.get("llm_path"):
        print("[Pipeline] 已選擇 LLM：啟動畫面／語音區間理解，不以技術評分冒充語義分析。")
        vision = analyze_semantics(raw_video, vision, audio, model_settings, context_prompt, cancel_event=cancel_event,
                                   progress_path=data_dir / "semantic_progress.json", visual_cache=visual_cache)
        v_json.write_text(json.dumps(vision, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[完成摘要] {len(vision['semantic_windows'])} 個區間已處理，其中 {vision['degraded_windows']} 個需確認；待確認區間會明確標色。")

    # 3. 導演決策層 (傳入 raw_video 保留母帶音訊)
    check_cancelled(cancel_event)
    task_lua = build_markers(
        video_path=str(raw_video),
        video_clip_name=raw_video.name,
        vision_analysis_path=str(v_json),
        audio_analysis_path=str(a_json),
        output_lua_path=str(data_dir / "marker_task.lua")
    )

    # 4. 喚起 Resolve 自動置中注入
    check_cancelled(cancel_event)
    submitted = submit_markers(task_lua, lambda task: trigger_resolve_injection(task, fresh_receipt=True), cancel_event)
    if submitted:
        # The default bridge embeds task data into its command before delivery.
        # No model/Resolve consumer needs files in this job after dispatch.
        try:
            cleanup_job(data_dir, raw_video, PROJ_ROOT)
        except Exception as exc:
            print(f"[暫存清理] 清理未完成：{exc}；保留暫存並繼續下一序列，原掃描檔案不會被刪除。")
    else:
        print(f"[暫存清理] 此序列未確認送出，保留 job「{data_dir.name}」，不刪除暫存。")
    return submitted

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_main_pipeline(sys.argv[1])
