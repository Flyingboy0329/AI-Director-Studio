import importlib
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.semantic_analyzer import analyze_semantics
from cancellation import AnalysisCancelled
from pipeline.submission import submit_markers


def good_decision(index):
    return {"event": f"區間 {index} 的街道事件", "visual_summary": f"區間 {index} 街道",
            "audio_summary": "無辨識語音", "relationship": "證據不足", "reason": "可交代步行路徑",
            "edit_suggestion": "保留能交代路徑的街道畫面，接續抵達目的地的鏡頭。",
            "strengths": ["街道路徑可辨識 → 交代移動方向"], "weaknesses": [],
            "recommendation": "備選", "score": 65, "confidence": 0.6}


def vision(seconds=268.87):
    total = round(seconds * 30)
    return {"fps": 30, "total_frames": total, "frames": [
        {"frame_idx": i, "score": 60, "comment": "技術抽樣"} for i in range(0, total, 60)]}


SETTINGS = {"model_mode": "llm_only", "llm_path": "test.gguf", "llm_mmproj_path": "mmproj.gguf",
            "semantic_retry_delay": 0}


class RecoveryTests(unittest.TestCase):
    def test_original_eighth_window_length_failure_recovers_and_finishes_all_45(self):
        calls = {}
        visual_calls = []
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "semantic_progress.json"
            class Client:
                def __init__(self, *args):
                    pass
                def check(self, **kwargs):
                    pass
                def analyze(self, name, content):
                    if name == "visual_observer.md":
                        visual_calls.append(name)
                        return {"visual_summary": "街道"}
                    source = json.loads(content)
                    index = int(source["start_sec"] / 6) + 1
                    calls[index] = calls.get(index, 0) + 1
                    result = good_decision(index)
                    if index == 8 and calls[index] == 1:
                        result["edit_suggestion"] = "x" * 151
                    elif index == 8:
                        assert "151/150" in source["output_repair_request"]
                        assert json.loads(progress.read_text(encoding="utf-8"))["completed_windows"] == 7
                    return result
            result = analyze_semantics("sample.mp4", vision(), [], SETTINGS,
                client_factory=Client, image_loader=lambda *args: [], progress_path=progress)
            self.assertEqual(len(result["semantic_windows"]), 45)
            self.assertEqual(result["degraded_windows"], 0)
            self.assertEqual(calls[8], 2)
            self.assertTrue(all(calls[i] == 1 for i in range(1, 8)))
            self.assertEqual(len(visual_calls), 45, "Successful visual analysis must not repeat for a director format error")
            saved = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual((saved["status"], saved["completed_windows"]), ("complete", 45))

    def test_exhausted_window_is_orange_and_full_clip_still_covered(self):
        calls = {}
        class Client:
            def __init__(self, *args):
                pass
            def check(self, **kwargs):
                pass
            def analyze(self, name, content):
                if name == "visual_observer.md":
                    return {"visual_summary": "街道"}
                index = int(json.loads(content)["start_sec"] / 6) + 1
                calls[index] = calls.get(index, 0) + 1
                result = good_decision(index)
                if index == 8:
                    result["event"] = "x" * 41
                return result
        result = analyze_semantics("sample.mp4", vision(), [], SETTINGS,
            client_factory=Client, image_loader=lambda *args: [])
        self.assertEqual(calls[8], 3)
        self.assertEqual(result["degraded_windows"], 1)
        self.assertEqual(result["semantic_windows"][7]["status"], "degraded")
        self.assertEqual(calls[9], 1, "The next interval must still run")
        with patch.dict(sys.modules, {"cv2": types.ModuleType("cv2")}):
            decision = importlib.import_module("pipeline.director_decision")
        with tempfile.TemporaryDirectory() as tmp, patch.object(decision, "OUTPUT_DIR", Path(tmp)), \
                patch.object(decision, "get_video_exact_info", return_value=(30, result["total_frames"])):
            path = Path(tmp) / "vision.json"
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            task = decision.build_markers(video_path="sample.mp4", vision_analysis_path=path)
            text = Path(task).read_text(encoding="utf-8")
            intervals = [(int(a), int(b)) for a, b in re.findall(r"start_frame = (\d+), duration_frames = (\d+)", text)]
            self.assertIn('start_frame = 1260, duration_frames = 180, color = "Orange"', text)
            self.assertEqual(sum(length for _, length in intervals), result["total_frames"])
            self.assertEqual(intervals[-1][0] + intervals[-1][1], result["total_frames"])

    def test_persistent_service_error_does_not_timeout_again_for_every_window(self):
        calls = []
        class Client:
            def __init__(self, *args):
                pass
            def check(self, **kwargs):
                pass
            def analyze(self, name, content):
                calls.append(name)
                raise RuntimeError("service unavailable")
        result = analyze_semantics("sample", vision(18), [], SETTINGS,
            client_factory=Client, image_loader=lambda *args: [])
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["degraded_windows"], 3)

    def test_cancel_preserves_finished_windows_and_is_not_retried(self):
        event = threading.Event()
        calls = []
        class Client:
            def __init__(self, *args):
                pass
            def check(self, **kwargs):
                pass
            def analyze(self, name, content):
                source = json.loads(content)
                index = int(source["start_sec"] / 6) + 1
                calls.append(index)
                if index == 2:
                    event.set()
                    raise ValueError("cancel test")
                return good_decision(index)
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            with self.assertRaises(AnalysisCancelled):
                analyze_semantics("sample", vision(18), [], {"llm_path": "test.gguf", "model_mode": "llm_only"},
                    client_factory=Client, cancel_event=event, progress_path=progress)
            saved = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual((saved["status"], saved["completed_windows"]), ("cancelled", 1))
            self.assertEqual(calls, [1, 2])

    def test_resolve_submission_only_once_even_when_acknowledgement_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "task.lua"
            task.touch()
            replies = iter([(False, "busy"), (True, "confirmed")])
            calls = []
            def submit(path):
                calls.append(path)
                return next(replies)
            self.assertFalse(submit_markers(task, submit, delay=0))
            self.assertFalse(submit_markers(task, submit, delay=0))
            self.assertEqual(len(calls), 1)
            self.assertFalse(submit_markers(task, lambda path: (False, "offline"), delay=0))
            self.assertEqual(json.loads((Path(tmp) / "resolve_submission.json").read_text())["status"], "pending_resolve")


if __name__ == "__main__":
    unittest.main()
