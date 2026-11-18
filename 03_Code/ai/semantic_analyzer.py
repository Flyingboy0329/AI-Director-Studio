"""Grounded, windowed image + transcript analysis through a local llama-server."""
import base64
import json
import math
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from path_utils import get_project_root, get_resource_root
from cancellation import check_cancelled, AnalysisCancelled
from ai.semantic_recovery import run_with_retries, retry_content, fallback_decision, RetryExhausted
from frame_windows import frame_windows
from ai_sampling import validate_rate, sample_times

PROMPT_DIR = get_resource_root() / "01_Project" / "prompts"


class LocalModelClient:
    def __init__(self, base_url, model_path, timeout=180):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("影音推論服務必須使用本機 HTTP 位址")
        self.base_url = base_url.rstrip("/").removesuffix("/v1")
        self.model_id = Path(model_path).name
        self.timeout = timeout

    def request(self, route, payload=None):
        request = urllib.request.Request(
            self.base_url + route,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json"})
        try:
            # No proxy: source footage stays on the explicitly selected local service.
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=self.timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            detail = str(exc).strip() or repr(exc)
            raise RuntimeError(f"本機模型服務 {self.base_url} 無法使用：{type(exc).__name__}: {detail}。請先載入模型。") from exc

    def check(self, require_images=False):
        original_timeout = self.timeout
        try:
            self.timeout = min(self.timeout, 5)
            models = self.request("/v1/models").get("data", [])
        finally:
            self.timeout = original_timeout
        match = next((m for m in models if Path(m.get("id", "")).name == self.model_id), None)
        if not match:
            raise ValueError(f"服務未載入選定模型 {self.model_id}；請以 --alias 設為此檔名，避免分析時用錯模型。")
        modalities = match.get("architecture", {}).get("input_modalities")
        if require_images and modalities is not None and "image" not in modalities:
            raise ValueError("模型服務不支援影像輸入，請確認主模型與 mmproj 相容且已載入。")

    def analyze(self, prompt_name, content):
        prompt = (PROMPT_DIR / prompt_name).read_text(encoding="utf-8")
        result = self.request("/v1/chat/completions", {
            "model": self.model_id,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": content}],
            "temperature": 0.1, "max_tokens": 1600,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_object"},
        })
        choice = result["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("模型輸出被截斷，停止寫入標記。")
        text = choice["message"].get("content", "")
        try:
            value = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise ValueError("模型未回傳有效 JSON，停止寫入標記。") from exc
        if not isinstance(value, dict):
            raise ValueError("模型輸出必須為 JSON 物件")
        return value


def overlapping_transcript(segments, start, end):
    return [{k: seg[k] for k in ("start", "end", "text", "no_speech_prob", "avg_logprob") if k in seg}
            for seg in segments if seg.get("start", 0) < end and seg.get("end", 0) > start]


def extract_images(video_path, start, end, sampling_fps=1.0):
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    images = []
    try:
        if not cap.isOpened():
            raise ValueError("語義分析無法開啟影片")
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for second in sample_times(start, end, sampling_fps):
            if fps > 0 and total_frames > 0:
                frame_index = min(total_frames-1, max(0, math.floor(second*fps + 1e-7)))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            else:
                cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"無法抽取 {second:.2f} 秒畫面，停止語義分析")
            h, w = frame.shape[:2]
            if max(w, h) > 768:
                scale = 768 / max(w, h)
                frame = cv2.resize(frame, (max(1, round(w * scale)), max(1, round(h * scale))))
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                raise ValueError("畫面 JPEG 編碼失敗")
            images.extend([
                {"type": "text", "text": f"影格時間 {second:.3f} 秒"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")}},
            ])
    finally:
        cap.release()
    return images


def validate_decision(result):
    for key in ("visual_summary", "audio_summary", "relationship", "reason", "event", "edit_suggestion"):
        if not isinstance(result.get(key), str) or not result[key].strip() or len(result[key]) > 800:
            raise ValueError(f"模型欄位 {key} 缺漏或過長")
    if len(result["event"]) > 40 or len(result["edit_suggestion"]) > 150:
        raise ValueError(f"模型標題或剪輯建議過長：event={len(result['event'])}/40 字，edit_suggestion={len(result['edit_suggestion'])}/150 字")
    for key in ("strengths", "weaknesses"):
        items = result.get(key)
        if not isinstance(items, list) or len(items) > 3 or any(not isinstance(x, str) or not x.strip() or len(x) > 100 for x in items):
            raise ValueError(f"模型欄位 {key} 必須包含至多三項具體內容")
    for key, maximum in (("score", 100), ("confidence", 1)):
        value = result.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError(f"模型欄位 {key} 超出範圍")
    if result.get("recommendation") not in ("保留", "備選", "略過", "待確認"):
        raise ValueError("模型 recommendation 無效")
    return result


def prepare_clients(settings, client_factory=LocalModelClient):
    llm_path = settings.get("llm_path", "")
    llm = client_factory(settings.get("llm_url", "http://127.0.0.1:8080"), llm_path)
    separate = settings.get("model_mode", "separate") == "separate"
    visual_path = settings.get("vlm_path", "") if separate else llm_path
    projector = settings.get("mmproj_path", "") if separate else settings.get("llm_mmproj_path", "")
    use_images = bool(visual_path and projector)
    if separate and bool(visual_path) != bool(projector):
        raise ValueError("VLM 主檔與 mmproj 必須同時選擇")
    visual = (client_factory(settings.get("vlm_url", "http://127.0.0.1:8081"), visual_path)
              if separate and use_images else llm)
    llm.check(require_images=not separate and use_images)
    if separate and use_images:
        visual.check(require_images=True)
    return llm, visual, visual_path, use_images


def prepare_visual_observations(video_path, vision, settings, cancel_event=None,
                                client_factory=LocalModelClient, image_loader=extract_images):
    """Scheme A only: independent VLM observations, never director decisions."""
    cache = {}
    if not (settings.get("model_mode", "separate") == "separate" and
            settings.get("llm_path") and settings.get("vlm_path") and settings.get("mmproj_path")):
        return cache
    rate = validate_rate(settings.get("ai_sampling_fps", 1.0))
    try:
        attempts = max(1, min(5, int(settings.get("semantic_attempts", 3))))
        delay = max(0, min(5, float(settings.get("semantic_retry_delay", 1))))
    except (TypeError, ValueError, OverflowError):
        attempts, delay = 3, 1
    options = dict(attempts=attempts, delay=delay if math.isfinite(delay) else 1,
                   cancel_event=cancel_event)
    visual = client_factory(settings.get("vlm_url", "http://127.0.0.1:8081"), settings["vlm_path"])
    unavailable = None
    try:
        run_with_retries("VLM 服務檢查", lambda _: visual.check(require_images=True), **options)
    except RetryExhausted as exc:
        unavailable = exc
    for index, (first, last) in enumerate(frame_windows(vision["total_frames"], vision["fps"])):
        check_cancelled(cancel_event)
        errors = []; entry = {"errors": errors, "sent_images": 0}
        try:
            if unavailable:
                raise unavailable
            start, end = first / vision["fps"], last / vision["fps"]
            images = run_with_retries("VLM 擷取畫面", lambda _: image_loader(video_path, start, end, rate),
                                      errors=errors, **options)
            entry["sent_images"] = sum(item.get("type") == "image_url" for item in images)
            content = [{"type": "text", "text": json.dumps({"start_sec": start, "end_sec": end})}, *images]
            def observe(feedback):
                value = visual.analyze("visual_observer.md", retry_content(content, feedback))
                if not isinstance(value.get("visual_summary"), str) or not value["visual_summary"].strip():
                    raise ValueError("模型未提供畫面觀察")
                return value
            entry["observation"] = run_with_retries("VLM 畫面理解", observe, errors=errors, **options)
        except RetryExhausted as exc:
            entry["error"] = exc
            if isinstance(exc.last_error, RuntimeError):
                unavailable = exc
        cache[index] = entry
        print(f"[並行視覺] A 方案 VLM 區間 {index+1} 完成；尚未產生影音整合建議。")
    return cache


def analyze_semantics(video_path, vision, audio, settings, context_prompt="", client_factory=LocalModelClient,
                      image_loader=extract_images, cancel_event=None, progress_path=None, visual_cache=None):
    """Model never controls timing. Every result belongs to a program-assigned window."""
    llm_path = settings.get("llm_path", "")
    if not llm_path:
        return vision
    duration = vision.get("total_frames", 0) / vision["fps"]
    if duration <= 0:
        raise ValueError("影片時長無效")
    window_sec = 6.0
    sampling_fps = validate_rate(settings.get("ai_sampling_fps", 1.0))
    print(f"[AI 取樣] 每秒 {sampling_fps:g} 張；每 6 秒約 {6*sampling_fps:g} 張；技術分析仍每 2 秒一張。")
    if sampling_fps >= 2:
        print("[AI 取樣] 高頻率會增加影像編碼、推論時間與上下文用量；不會自動降頻，失敗區間明確標為待確認。")
    windows = []
    intervals = frame_windows(vision["total_frames"], vision["fps"], window_sec)
    count = len(intervals)
    tail_start, tail_end = intervals[-1]
    print(f"[區間規劃] 共 {count} 段；尾段 [{tail_start}, {tail_end}) 格，"
          f"{(tail_end-tail_start)/vision['fps']:.3f} 秒；不足 6 秒仍獨立分析並標記。")
    try:
        attempts = max(1, min(5, int(settings.get("semantic_attempts", 3))))
        delay = max(0, min(5, float(settings.get("semantic_retry_delay", 1))))
        if not math.isfinite(delay):
            delay = 1
    except (TypeError, ValueError, OverflowError):
        attempts, delay = 3, 1
    retry_options = {"attempts": attempts, "delay": delay, "cancel_event": cancel_event}
    readiness_errors = []
    unavailable = None
    visual_path, use_images = None, False
    try:
        llm, visual, visual_path, use_images = run_with_retries(
            "模型服務檢查", lambda feedback: prepare_clients(settings, client_factory),
            errors=readiness_errors, **retry_options)
    except RetryExhausted as exc:
        unavailable = exc
        print("[自動恢復] 模型服務未恢復；保留技術抽樣與逐字稿，將區間標為待確認。")

    progress_error_reported = False
    def save_progress(status):
        nonlocal progress_error_reported
        if progress_path is None:
            return
        destination = Path(progress_path)
        data = {"status": status, "video_file": str(video_path), "semantic_model": llm_path,
                "ai_sampling_fps": sampling_fps,
                "total_windows": count, "completed_windows": len(windows),
                "degraded_windows": sum(w["status"] == "degraded" for w in windows),
                "semantic_windows": windows, "readiness_errors": readiness_errors}
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(destination)
        except OSError as exc:
            if not progress_error_reported:
                print(f"[自動恢復] 進度暫存無法寫入，仍繼續分析：{exc}")
                progress_error_reported = True

    try:
        save_progress("running")
        for index in range(count):
            check_cancelled(cancel_event)
            start_frame, end_frame = intervals[index]
            start, end = start_frame / vision["fps"], end_frame / vision["fps"]
            transcript = overlapping_transcript(audio, start, end)
            source = {"start_sec": start, "end_sec": end,
                      "editor_context": context_prompt or "",
                      "transcript": transcript, "audio_input": "Whisper 逐字稿，未直接聆聽原音"}
            observation = {"visual_summary": "未啟用影像理解，無法判斷畫面內容", "uncertainties": ["僅文字模式"]}
            errors = []
            requested_times = sample_times(start, end, sampling_fps)
            sent_images = 0
            status = "analyzed"
            skipped_service = unavailable is not None
            try:
                if unavailable:
                    observation = {}
                    errors = list(unavailable.errors)
                    raise unavailable
                if use_images and visual_cache is not None:
                    entry = visual_cache[index]
                    errors.extend(entry["errors"])
                    sent_images = entry["sent_images"]
                    if "error" in entry:
                        raise entry["error"]
                    observation = entry["observation"]
                elif use_images:
                    observation = {}
                    images = run_with_retries(f"區間 {index + 1}/{count} 擷取畫面",
                        lambda feedback: image_loader(video_path, start, end, sampling_fps), errors=errors, **retry_options)
                    sent_images = sum(item.get("type") == "image_url" for item in images)
                    print(f"[AI 取樣] 區間 {index+1}/{count} [{start:.3f}, {end:.3f})s：每秒 {sampling_fps:g} 張，實際送入 {sent_images} 張。")
                    visual_content = [{"type": "text", "text": json.dumps({"start_sec": start, "end_sec": end}, ensure_ascii=False)}, *images]
                    def observe(feedback):
                        value = visual.analyze("visual_observer.md", retry_content(visual_content, feedback))
                        if not isinstance(value.get("visual_summary"), str) or not value["visual_summary"].strip():
                            raise ValueError("模型未提供畫面觀察")
                        return value
                    observation = run_with_retries(f"區間 {index + 1}/{count} 畫面理解", observe, errors=errors, **retry_options)
                source["visual_observation"] = observation
                decision = run_with_retries(f"區間 {index + 1}/{count} 導演決策",
                    lambda feedback: validate_decision(llm.analyze("director.md", retry_content(json.dumps(source, ensure_ascii=False), feedback))),
                    errors=errors, **retry_options)
            except RetryExhausted as exc:
                status = "degraded"
                if isinstance(exc.last_error, RuntimeError) and "擷取畫面" not in exc.stage:
                    unavailable = exc  # Do not repeat long timeouts for every remaining window.
                decision = fallback_decision(observation, transcript)
                cause = "服務持續不可用，跳過重複請求" if skipped_service else "重試後仍未完成"
                print(f"[自動恢復] 區間 {index + 1}/{count} {cause}，將寫入待確認標記，繼續下一區間。")
            check_cancelled(cancel_event)
            if not use_images and not unavailable:
                decision["visual_summary"] = observation["visual_summary"]
            if not transcript:
                decision["audio_summary"] = "此區間無辨識語音；不代表原音無聲。"
            windows.append({**decision, "start_sec": start, "end_sec": end, "start_frame": start_frame,
                            "end_frame": end_frame, "transcript": transcript,
                            "ai_sampling_fps": sampling_fps, "requested_sample_times_sec": requested_times,
                            "sent_image_count": sent_images,
                            "status": status, "retry_errors": errors, "model_calls_skipped": skipped_service})
            save_progress("running")
            if status == "analyzed" and errors:
                print(f"[自動恢復] 區間 {index + 1}/{count} 已恢復，保留先前已完成區間。")
            print(f"[LLM:{Path(llm_path).name}] 語義分析 {index + 1}/{count} [{status}]：{decision['event']} | {decision['edit_suggestion']}")
        save_progress("complete_with_warnings" if any(w["status"] == "degraded" for w in windows) else "complete")
    except AnalysisCancelled:
        save_progress("cancelled")
        raise
    result = {**vision, "frames": [], "technical_frames": vision["frames"],
              "semantic_windows": windows, "semantic_model": llm_path, "ai_sampling_fps": sampling_fps,
              "visual_model": visual_path if use_images else None,
              "degraded_windows": sum(w["status"] == "degraded" for w in windows)}
    for window in windows:
        samples = [f for f in vision["frames"]
                   if window["start_sec"] <= f["frame_idx"] / vision["fps"] < window["end_sec"]]
        # Keep semantic boundaries on their assigned time, not the next CV sample.
        result["frames"].append({
            "frame_idx": window["start_frame"],
            "start_sec": window["start_sec"],
            "score": sum(f["score"] for f in samples) / len(samples) if samples else 50,
            "comment": " / ".join(dict.fromkeys(f.get("comment", "") for f in samples)) or "無技術抽樣",
            "semantic": {k: v for k, v in window.items() if k != "transcript"},
        })
    return result
