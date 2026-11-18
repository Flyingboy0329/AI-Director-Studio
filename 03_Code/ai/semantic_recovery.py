"""Bounded model retries and explicit, non-fabricated fallback decisions."""
import json
import time

from cancellation import AnalysisCancelled, check_cancelled


class RetryExhausted(RuntimeError):
    def __init__(self, stage, last_error, errors):
        super().__init__(f"{stage} 已重試，仍無法完成：{last_error}")
        self.stage = stage
        self.last_error = last_error
        self.errors = errors


def run_with_retries(stage, operation, *, attempts=3, delay=1, cancel_event=None, errors=None):
    records = errors if errors is not None else []
    last_error = None
    for attempt in range(1, attempts + 1):
        check_cancelled(cancel_event)
        try:
            result = operation(str(last_error) if last_error else "")
            check_cancelled(cancel_event)
            return result
        except AnalysisCancelled:
            raise
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, IndexError) as exc:
            check_cancelled(cancel_event)
            last_error = exc
            records.append({"stage": stage, "attempt": attempt, "error": str(exc)[:300]})
            if attempt < attempts:
                print(f"[自動恢復] {stage} 第 {attempt}/{attempts} 次未完成：{exc}；正在重試。")
                seconds = delay * attempt
                if cancel_event is not None:
                    if cancel_event.wait(seconds):
                        check_cancelled(cancel_event)
                elif seconds:
                    time.sleep(seconds)
    raise RetryExhausted(stage, last_error, records)


def retry_content(content, error):
    if not error:
        return content
    instruction = (f"前次回應未通過檢查：{error[:300]}。請重新分析本區間並修正輸出；"
                   "只回傳 JSON。event 最多 40 字、edit_suggestion 最多 150 字、"
                   "strengths/weaknesses 各最多 3 項且每項最多 100 字，其它文字欄位最多 800 字。縮短文字但保留具體證據，不新增猜測。")
    if isinstance(content, list):
        return [*content, {"type": "text", "text": instruction}]
    source = json.loads(content)
    source["output_repair_request"] = instruction
    return json.dumps(source, ensure_ascii=False)


def fallback_decision(observation, transcript):
    text = "；".join(str(s.get("text", "")) for s in transcript if s.get("text"))
    return {
        "event": "此區間 AI 分析待確認",
        "visual_summary": observation.get("visual_summary", "畫面語義未完成；僅有技術抽樣。"),
        "audio_summary": ("Whisper 逐字稿（未經語義確認）：" + text[:600]) if text else "此區間無辨識語音；不代表原音無聲。",
        "relationship": "聲畫關聯未能確認",
        "strengths": [], "weaknesses": [],
        "edit_suggestion": "本區間已自動重試但未取得有效分析；保留素材，剪輯時回看確認，勿據此刪除。",
        "recommendation": "待確認", "score": 50, "confidence": 0,
        "reason": "自動分析未完成，這不是素材品質評價。",
    }
