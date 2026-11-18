import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import sys
import json
import time
import threading
import psutil
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
import torch
from pathlib import Path
from faster_whisper import WhisperModel
from cancellation import check_cancelled
from gpu_memory_policy import system_headroom_mb
from whisper_resources import RAM_GIB, ram_budget, process_rss_gib
from whisper_storage import resolve_whisper_model

DEFAULT_PROMPT = ""  # Optional vocabulary hints only; do not inject editing instructions into ASR.

def select_audio_device(notify=print):
    """CPU policy: keep ASR weights in system RAM, leaving CUDA for vision."""
    available, reserve, budget = ram_budget()
    selected = next((name for name in ("small", "base", "tiny") if budget >= RAM_GIB[name]), None)
    notify(f"[Faster-Whisper] 系統可用 RAM={available:.2f}GiB；額外預留={reserve:.2f}GiB；語音 RAM 預算={budget:.2f}GiB（保守政策，非硬隔離）。")
    if selected is None:
        raise RuntimeError("RAM 預留後不足 tiny 的 0.5GiB 規劃預算，請先釋放記憶體。")
    return "cpu", "int8", selected, 0, budget


def audio_cpu_threads():
    # Leave logical capacity for decoding, GUI and Resolve during parallel work.
    logical = os.cpu_count() or 1
    physical = psutil.cpu_count(logical=False) or logical
    return max(1, min(4, physical, logical // 2))


def detect_device_and_model():
    return select_audio_device()[:3]

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

def release_whisper(model, record=None, notify=print):
    backend = getattr(model, "model", None)
    unload = getattr(backend, "unload_model", None)
    try:
        if not callable(unload):
            raise RuntimeError("此後端未提供明確卸載 API")
        unload(to_cpu=False)
        if record:record("releasing", release_status="unloaded")
        notify("[Faster-Whisper] UNLOADED：語音模型權重已釋放。")
        return True
    except Exception as exc:
        if record:record("releasing", release_status="unconfirmed", release_error=type(exc).__name__)
        notify(f"[Faster-Whisper] 釋放失敗：{exc}；保留狀態供重試，未宣稱顯存歸零。")
        return False


def load_audio_model(model_name=None, record=None, notify=print):
    auto_device, auto_compute, auto_model, device_index, free_gb = select_audio_device(notify)
    target_model = model_name or auto_model
    required_gb = RAM_GIB.get(str(target_model))
    if required_gb is None and Path(target_model).is_dir():
        weights = Path(target_model) / "model.bin"
        if weights.is_file():
            required_gb = max(1., weights.stat().st_size / 1024**3 * 2 + 1)
    if required_gb is not None and free_gb < required_gb:
        raise RuntimeError(f"所選 Whisper {target_model} 規劃需 RAM 約 {required_gb:g}GiB，預留後僅 {free_gb:.2f}GiB；保留選擇，請釋放 RAM 或改選較小模型。")
    notify(f"[Faster-Whisper] 選型完成：{target_model} | {auto_device}:{device_index} | {auto_compute} | 語音 RAM 預算={free_gb:.2f}GiB | 規劃需求={required_gb if required_gb is not None else '未估算'}GiB")
    
    notify(f"[Faster-Whisper] 🚀 硬體探測就緒: 裝置={auto_device}:{device_index} | 精度={auto_compute} | 模型={target_model}")
    notify(f"[Faster-Whisper] 🎙 正在載入模型推論中...")
    
    resolved_model, source = resolve_whisper_model(str(target_model), notify)
    if record:
        record("loading", selected_model=str(target_model), resolved_model=str(resolved_model),
               source=source, device=auto_device, device_index=device_index, compute_type=auto_compute,
               asr_ram_budget_gib=free_gb, ram_planning_gib=required_gb)
    load_start = time.monotonic()
    threads = audio_cpu_threads()
    notify(f"[Faster-Whisper] CPU 執行緒={threads}；其餘容量保留給解碼、介面與 Resolve。")
    rss_before = process_rss_gib()
    model = WhisperModel(resolved_model, device=auto_device, device_index=device_index,
                         compute_type=auto_compute, cpu_threads=threads, num_workers=1)
    rss_after = process_rss_gib()
    delta = rss_after - rss_before if rss_after is not None and rss_before is not None else None
    fmt = lambda value: f"{value:.3f}GiB" if value is not None else "不可用"
    notify(f"[Faster-Whisper] RAM 實測：載入前程式 RSS={fmt(rss_before)}；載入後={fmt(rss_after)}；載入期間增量={fmt(delta)}。增量為近似值，非 Whisper 專用或峰值。")
    metadata = dict(selected_model=str(target_model), resolved_model=str(resolved_model), source=source,
                    device=auto_device, device_index=device_index, compute_type=auto_compute,
                    asr_ram_budget_gib=free_gb, ram_planning_gib=required_gb,
                    process_rss_before_gib=rss_before, process_rss_after_gib=rss_after,
                    load_rss_delta_gib=delta, cpu_threads=threads, load_seconds=round(time.monotonic()-load_start,3))
    notify(f"[Faster-Whisper] READY：{target_model} | {auto_device}:{device_index} | {auto_compute} | {metadata['load_seconds']:.2f}s")
    if record:record("ready", **metadata)
    return model, metadata


class WhisperRuntime:
    """One resident ASR model shared by deployment and the serial video worker."""
    def __init__(self):
        self.model = None
        self.metadata = {}
        self.requested = None
        self.lock = threading.RLock()

    def ensure_ready(self, model_name=None, notify=print):
        with self.lock:
            requested = model_name or ""
            if self.model is not None and self.requested == requested:
                m = self.metadata
                notify(f"[Faster-Whisper] READY：{m['selected_model']} | {m['device']}:{m['device_index']} | {m['compute_type']} | 重用已載入模型")
                return self.model, dict(m)
            self.unload(notify)
            notify(f"[Faster-Whisper] LOADING：{model_name or '自動選型'}")
            try:
                model, metadata = load_audio_model(model_name, notify=notify)
            except Exception as exc:
                notify(f"[Faster-Whisper] failed：{type(exc).__name__}: {exc}")
                raise
            self.model, self.metadata, self.requested = model, metadata, requested
            return self.model, dict(self.metadata)

    def unload(self, notify=print):
        with self.lock:
            if self.model is None:
                notify("[Faster-Whisper] UNLOADED：目前沒有已載入的語音模型。")
                return
            if not release_whisper(self.model, notify=notify):
                raise RuntimeError("Whisper 卸除未完成，請重試卸除模型。")
            self.model = None
            self.metadata = {}
            self.requested = None


_WHISPER_RUNTIME = WhisperRuntime()


def get_whisper_runtime():
    return _WHISPER_RUNTIME


def _analyze_audio(wav_path, output_json_path, model_name=None, context_prompt=None, cancel_event=None, record=None, runtime=None):
    check_cancelled(cancel_event)
    wav_file = Path(wav_path).resolve()
    if not wav_file.exists():
        raise FileNotFoundError(f"音訊檔案不存在: {wav_file}")

    final_prompt = context_prompt.strip() if context_prompt and context_prompt.strip() else DEFAULT_PROMPT
    if runtime is None:
        model, metadata = load_audio_model(model_name, record, print)
    else:
        model, metadata = runtime.ensure_ready(model_name, print)
        if record:record("transcribing", **metadata, lifecycle="session-resident")
    try:
        segments, info = model.transcribe(
            str(wav_file),
            initial_prompt=final_prompt or None,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False
        )
    
        print(f"[Faster-Whisper] 🌐 自動偵測語言: {info.language} (信心度: {info.language_probability:.2f})")
        if record:
            record("transcribing", language=info.language, language_probability=float(info.language_probability))
    
        analyzed_data = []
        for seg in segments:
            check_cancelled(cancel_event)
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
                    "text": text,
                    "no_speech_prob": seg.no_speech_prob,
                    "avg_logprob": seg.avg_logprob,
                    "compression_ratio": seg.compression_ratio
                })

        out_p = Path(output_json_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(analyzed_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ [Faster-Whisper] 轉錄完成：{len(analyzed_data)} 個含文字段落，已存入: {out_p.name}")
        rss = process_rss_gib()
        print(f"[Faster-Whisper] RAM 轉錄後：程式 RSS={f'{rss:.3f}GiB' if rss is not None else '不可用'}；包含 GUI 與並行視覺工作，非 Whisper 專用用量。")
        if record:record("transcribed", process_rss_transcribed_gib=rss)
        if not analyzed_data:
            print("[Faster-Whisper] 未辨識出語音；不代表原音靜音。")
        return analyzed_data
    finally:
        if runtime is None:
            release_whisper(model, record)



def analyze_audio(wav_path, output_json_path, model_name=None, context_prompt=None, cancel_event=None, runtime=None):
    """Persist loader/transcription evidence even if model loading fails."""
    destination = Path(output_json_path).with_suffix(".metadata.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        package_version = version("faster-whisper")
    except PackageNotFoundError:
        package_version = "unknown"
    audit = {"requested_model": str(model_name or "auto"), "input_audio": str(Path(wav_path).resolve()),
             "faster_whisper_version": package_version, "started_at": datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    def record(status, **values):
        audit.update(values, status=status, elapsed_seconds=round(time.monotonic()-started, 3))
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)
    record("starting")
    print(f"[Faster-Whisper] 載入偵測開始 | 選擇={audit['requested_model']} | 套件={package_version} | 紀錄={destination.name}")
    try:
        result = _analyze_audio(wav_path, output_json_path, model_name, context_prompt, cancel_event, record, runtime)
        record("complete", segments=len(result))
        print(f"[Faster-Whisper] 稽核完成 | 耗時={audit['elapsed_seconds']:.2f}s | 狀態=complete")
        return result
    except Exception as exc:
        from cancellation import AnalysisCancelled
        record("cancelled" if isinstance(exc, AnalysisCancelled) else "failed", error_type=type(exc).__name__, error=str(exc))
        print(f"[Faster-Whisper] {audit['status']}：{type(exc).__name__}；詳見 {destination.name}")
        raise

if __name__ == "__main__":
    proj_root = Path(__file__).resolve().parent.parent.parent
    sample_wav = proj_root / "02_Data" / "audio" / "test_audio.wav"
    out_json = proj_root / "02_Data" / "audio_analysis.json"
    if sample_wav.exists():
        analyze_audio(sample_wav, out_json)
