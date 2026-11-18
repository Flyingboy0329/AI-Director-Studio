"""Delete only this application's newly owned job, never original media."""
import json
import os
from pathlib import Path
import re
import shutil
import stat

MANIFEST = ".ai_director_job.json"


def mark_job_owned(job, original):
    data = {"owner": "AI_Director", "job_id": Path(job).name,
            "original_video": str(Path(original).resolve())}
    with (Path(job)/MANIFEST).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def _linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def cleanup_job(job, original, project_root):
    """Return false on unsafe targets/IO failure; never retry media processing."""
    target = Path(job)
    files = []
    try:
        project = Path(project_root).resolve()
        jobs = project/"05_Output"/"jobs"
        resolved_jobs = jobs.resolve()
        resolved = target.resolve()
        original = Path(original).resolve()
        # Validate resolved absolute paths BEFORE any recursive deletion.
        if (not resolved_jobs.is_relative_to(project) or resolved.parent != resolved_jobs
                or not re.fullmatch(r"[0-9a-f]{32}", target.name)
                or _linked(jobs) or _linked(target)):
            raise ValueError("目標不是專案內的直接 job 子目錄")
        if original == resolved or original.is_relative_to(resolved):
            raise ValueError("原掃描檔案位於清理目錄，拒絕刪除")
        data = json.loads((resolved/MANIFEST).read_text(encoding="utf-8"))
        if data != {"owner":"AI_Director", "job_id":target.name, "original_video":str(original)}:
            raise ValueError("job 所有權紀錄不符")
        for folder, directories, filenames in os.walk(resolved, topdown=True, followlinks=False):
            for name in directories + filenames:
                path = Path(folder)/name
                if _linked(path) or not path.resolve().is_relative_to(resolved):
                    raise ValueError("job 內含連結或 junction，拒絕遞迴清理")
            files.extend(Path(folder)/name for name in filenames)
        print(f"[暫存清理] 當前影片序列處理完成：{original.name}；清理對應 job「{target.name}」。原掃描檔案不會被刪除。")
        shutil.rmtree(resolved)
    except (OSError, ValueError, TypeError) as exc:
        print(f"[暫存清理] 未完整清理 job「{target.name}」：{exc}；保留可用檔案，繼續後續序列。原掃描檔案不會被刪除。")
        return False
    for path in files:
        print(f"[暫存清理] 已刪除系統產生之暫存檔「{path.relative_to(resolved).as_posix()}」。原掃描檔案不會被刪除。")
    print(f"[暫存清理] job「{target.name}」清理完成，共 {len(files)} 個暫存檔；準備接續下一個序列。")
    return True
