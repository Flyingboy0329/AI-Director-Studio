"""At-most-once Resolve submission; unknown acknowledgement is never retried."""
import json
from pathlib import Path

from cancellation import AnalysisCancelled, check_cancelled


def submit_markers(task_path, submit, cancel_event=None, delay=1):
    check_cancelled(cancel_event)
    destination = Path(task_path).parent / "resolve_submission.json"
    status = {"status": "submission_started", "task_path": str(task_path), "attempts": 1}
    # Reserve before calling code that may modify Resolve. A timeout is ambiguous.
    try:
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(status, stream, ensure_ascii=False, indent=2)
    except FileExistsError:
        try:
            previous = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        print("[Resolve] 此任務已提交過；不再導入。")
        return previous.get("status") in ("submitted", "confirmed")
    try:
        ok, message = submit(task_path)
    except AnalysisCancelled:
        raise
    except Exception as exc:
        ok, message = False, f"提交後無法確認：{exc}"
    status.update(status="submitted" if ok else "pending_resolve", write_verified=False, message=message)
    temporary = destination.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)
    except OSError as exc:
        print(f"[Resolve] 完成狀態保存失敗，提交鎖仍保留：{exc}")
    print(f"[Resolve] {message}")
    if not ok:
        print("[Resolve] 指令未完整送出或狀態不明；保留任務供核對，本次不重送。")
    return ok
