import json
from pathlib import Path
import sys
import tempfile
import unittest
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.semantic_analyzer import analyze_semantics, LocalModelClient, validate_decision
from start_model_server import server_command
from cancellation import AnalysisCancelled


def decision():
    return {"event": "沿街道前進並說明路線", "strengths": ["街道可辨識，可交代路線"], "weaknesses": [],
            "edit_suggestion": "保留街道畫面配合路線說明，作為移動過場。",
            "visual_summary": "街道", "audio_summary": "說明路線", "relationship": "互相補充",
            "recommendation": "備選", "score": 65, "confidence": 0.7, "reason": "街道畫面可補充路線說明"}


class SemanticTests(unittest.TestCase):
    def test_images_and_short_speech_reach_model_with_exact_windows(self):
        calls = []
        class Client:
            model_id = "test.gguf"
            def __init__(self, *args):
                pass
            def check(self, **kwargs):
                calls.append(("check", kwargs))
            def analyze(self, name, content):
                calls.append((name, content))
                return {"visual_summary": "街道", "uncertainties": []} if name == "visual_observer.md" else {
                    **decision(), "start_frame": 99999, "end_frame": 999999,
                    "start_sec": 999, "end_sec": 9999}
        vision = {"fps": 30, "total_frames": 210, "frames": [
            {"frame_idx": 0, "score": 60, "comment": "技術"},
            {"frame_idx": 180, "score": 50, "comment": "技術"}]}
        audio = [{"start": 1.1, "end": 1.3, "text": "右轉"}]
        result = analyze_semantics("fake.mp4", vision, audio,
            {"llm_path": "gemma.gguf", "llm_mmproj_path": "mmproj.gguf", "model_mode": "llm_only"},
            client_factory=Client, image_loader=lambda *args: [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,fake"}}])
        requests = [content for name, content in calls if name == "director.md"]
        self.assertEqual(json.loads(requests[0])["transcript"][0]["text"], "右轉")
        self.assertEqual(result["frames"][1]["frame_idx"], 180)
        self.assertEqual(json.loads(requests[-1])["end_sec"], 7)
        self.assertEqual(result["semantic_windows"][-1]["end_frame"], 210)
        self.assertIn("無辨識語音", result["frames"][1]["semantic"]["audio_summary"])
        self.assertEqual(vision["frames"][0].get("semantic"), None)
        self.assertEqual(len([c for name, c in calls if name == "visual_observer.md"]), 2)

    def test_text_only_does_not_claim_visual_understanding(self):
        class Client:
            model_id = "test.gguf"
            def __init__(self, *args):
                pass
            def check(self, **kwargs):
                pass
            def analyze(self, name, content):
                return decision()
        result = analyze_semantics("fake", {"fps": 30, "total_frames": 30,
            "frames": [{"frame_idx": 0, "score": 50}]}, [],
            {"llm_path": "gemma.gguf", "model_mode": "llm_only"}, client_factory=Client,
            image_loader=lambda *args: self.fail("Text mode must not read images"))
        self.assertIn("未啟用影像理解", result["frames"][0]["semantic"]["visual_summary"])

    def test_invalid_outputs_and_nonlocal_service_rejected(self):
        for value in (-1, 101, float("nan"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_decision({**decision(), "score": value})
        with self.assertRaises(ValueError):
            LocalModelClient("https://example.com", "gemma.gguf")
        client = LocalModelClient("http://127.0.0.1:8080", "gemma.gguf")
        client.request = lambda *args: {"data": [{"id": "wrong.gguf"}]}
        with self.assertRaises(ValueError):
            client.check()
        client.request = lambda *args: {"data": [{"id": "gemma.gguf", "architecture": {"input_modalities": ["text"]}}]}
        with self.assertRaises(ValueError):
            client.check(require_images=True)

    def test_launcher_uses_exact_model_and_projector(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, projector = Path(tmp) / "gemma.gguf", Path(tmp) / "mmproj.gguf"
            model.touch(); projector.touch()
            command = server_command({"llm_path": str(model), "llm_mmproj_path": str(projector)}, "llama-server.exe")
            self.assertEqual(command[command.index("--alias") + 1], model.name)
            self.assertEqual(command[command.index("--mmproj") + 1], str(projector))
            self.assertEqual(command[command.index("--load-mode") + 1], "none")
            command = server_command({"llm_path": str(model), "load_mode": "auto"}, "server")
            self.assertEqual(command[command.index("--load-mode") + 1], "auto")

    def test_cancel_after_image_request_prevents_more_inference(self):
        event = threading.Event()
        calls = []
        class Client:
            model_id = "test.gguf"
            def __init__(self, *args):
                pass
            def check(self, **kwargs):
                pass
            def analyze(self, name, content):
                calls.append(name)
                event.set()
                return {"visual_summary": "test"}
        with self.assertRaises(AnalysisCancelled):
            analyze_semantics("unused", {"fps": 30, "total_frames": 180, "frames": []}, [],
                {"llm_path": "test.gguf", "llm_mmproj_path": "projector.gguf", "model_mode": "llm_only"},
                client_factory=Client, image_loader=lambda *args: [], cancel_event=event)
        self.assertEqual(calls, ["visual_observer.md"])


class ReceiptTests(unittest.TestCase):
    def test_fusion_table_and_invalid_receipts(self):
        from bridge.auto_injector import read_receipt
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text('{ expected = 28, written = 28, coverage_ok = true, }')
            self.assertEqual(read_receipt(path), {"expected": 28, "written": 28, "coverage_ok": True})
            path.write_text('{ expected = 28, written = 10, }')
            with self.assertRaises(ValueError):
                read_receipt(path)


if __name__ == "__main__":
    unittest.main()
