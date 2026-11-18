"""Dependency-light regression tests; no GPU, model downloads or Resolve side effects."""
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from model_selection import scan_gguf, ModelSelectionPanel
from PyQt6.QtWidgets import QApplication


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_recursive_scan_separates_projector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested").mkdir()
            for name in ("Qwen.gguf", "Gemma.GGUF", "nested/mmproj-BF16.gguf", "ignore.txt"):
                (root / name).touch()
            models, projectors = scan_gguf(root)
            self.assertEqual(len(models), 2)
            self.assertEqual([p.name for p in projectors], ["mmproj-BF16.gguf"])

    def test_actual_whisper_size_and_lifecycle_are_visible(self):
        with patch.object(ModelSelectionPanel,"start_scan"):
            panel=ModelSelectionPanel()
            panel.update_whisper_status("[Faster-Whisper] 選型完成：medium | cuda:1 | float16")
            self.assertIn("medium",panel.whisper_actual.text())
            self.assertNotIn("READY",panel.whisper_actual.text())
            panel.update_whisper_status("[Faster-Whisper] READY：medium | cuda:1 | float16")
            self.assertIn("READY",panel.whisper_actual.text())
            panel.update_whisper_status("[Faster-Whisper] 稽核完成 | 狀態=complete")
            self.assertIn("medium",panel.whisper_actual.text())
            self.assertIn("本次轉錄完成",panel.whisper_actual.text())
            panel.close()

    def test_settings_survive_rescan_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp, patch("model_selection.get_project_root", return_value=Path(tmp)), patch("path_utils.get_project_root", return_value=Path(tmp)):
            root = Path(tmp) / "04_Models"
            root.mkdir()
            model = root / "Gemma.gguf"
            model.touch()
            (root / "mmproj-BF16.gguf").touch()
            panel = ModelSelectionPanel()
            panel.wait_for_scan()
            self.app.processEvents()
            panel.selectors["vlm_path"].setCurrentIndex(1)
            panel.selectors["llm_mmproj_path"].setCurrentIndex(1)
            panel.mode.setCurrentIndex(panel.mode.findData("llm_only"))
            self.assertFalse(panel.selectors["vlm_path"].isEnabled())
            self.assertFalse(panel.selectors["mmproj_path"].isEnabled())
            self.assertTrue(panel.selectors["llm_mmproj_path"].isEnabled())
            panel.whisper.setCurrentIndex(panel.whisper.findData("medium"))
            panel.start_scan()
            panel.wait_for_scan()
            self.app.processEvents()
            self.assertEqual(panel.values()["vlm_path"], str(model.resolve()))
            restarted = ModelSelectionPanel()
            restarted.wait_for_scan()
            self.app.processEvents()
            self.assertEqual(restarted.values(), panel.values())
            self.assertFalse(restarted.selectors["vlm_path"].isEnabled())
            restarted.mode.setCurrentIndex(restarted.mode.findData("separate"))
            self.assertTrue(restarted.selectors["vlm_path"].isEnabled())
            self.assertEqual(restarted.selectors["vlm_path"].currentData(), str(model.resolve()))
            panel.close()
            restarted.close()

    def test_runtime_load_finishes_without_blocking_panel(self):
        with tempfile.TemporaryDirectory() as tmp, patch("model_selection.get_project_root", return_value=Path(tmp)), patch("path_utils.get_project_root", return_value=Path(tmp)):
            (Path(tmp) / "04_Models").mkdir()
            panel = ModelSelectionPanel()
            panel.wait_for_scan()
            self.app.processEvents()
            with patch.object(panel.runtime, "ensure_ready"), patch.object(panel.runtime, "ensure_audio_ready"):
                deployment_logs=[]
                panel.runtime_log.connect(deployment_logs.append)
                panel.load_runtime()
                self.assertEqual(deployment_logs[0], "=" * 48)
                self.assertFalse(panel.load_button.isEnabled())
                panel.runtime_loader.wait()
                self.app.processEvents()
                self.assertEqual(panel.runtime_status.text(), "MODEL: 技術模式")
                self.assertTrue(panel.load_button.isEnabled())
            panel.shutdown_runtime()
            panel.close()

    def test_background_unload_updates_ui_only_after_stop(self):
        with tempfile.TemporaryDirectory() as tmp, patch("model_selection.get_project_root", return_value=Path(tmp)), patch("path_utils.get_project_root", return_value=Path(tmp)):
            (Path(tmp) / "04_Models").mkdir()
            panel = ModelSelectionPanel()
            panel.wait_for_scan()
            self.app.processEvents()
            with patch.object(panel.runtime, "stop") as stop:
                panel.unload_runtime()
                self.assertFalse(panel.load_button.isEnabled())
                panel.runtime_unloader.wait()
                self.app.processEvents()
                stop.assert_called_once()
                self.assertEqual(panel.runtime_status.text(), "MODEL: 未載入")
                self.assertTrue(panel.load_button.isEnabled())
            self.assertEqual(panel.values()["load_mode"], "none")
            panel.disable_mmap.setChecked(False)
            self.assertEqual(panel.values()["load_mode"], "auto")
            panel.close()


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock only the unavailable media boundary, not marker generation.
        with patch.dict(sys.modules, {"cv2": types.ModuleType("cv2")}):
            cls.decision = importlib.import_module("pipeline.director_decision")

    def generate(self, frames, total=217):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vision = root / "vision.json"
            vision.write_text(json.dumps({"frames": frames}), encoding="utf-8")
            with patch.object(self.decision, "OUTPUT_DIR", root), patch.object(
                    self.decision, "get_video_exact_info", return_value=(30000 / 1001, total)):
                task = self.decision.build_markers(video_path="sample.mp4", vision_analysis_path=vision)
                text = Path(task).read_text(encoding="utf-8")
            return [(int(a), int(b)) for a, b in re.findall(
                r"start_frame = (\d+), duration_frames = (\d+)", text)]

    def test_fractional_fps_uses_frame_index_and_covers_tail(self):
        intervals = self.generate([
            {"frame_idx": 0, "start_sec": 0, "score": 90},
            {"frame_idx": 59, "start_sec": 1.97, "score": 30},
            {"frame_idx": 118, "start_sec": 3.94, "score": 30},
            {"frame_idx": 236, "start_sec": 7.87, "score": 90},
        ], total=300)
        self.assertEqual(intervals, [(0, 59), (59, 177), (236, 64)])

    def test_one_frame_and_out_of_range_duplicate_samples(self):
        self.assertEqual(self.generate([
            {"frame_idx": 9, "score": 90}, {"frame_idx": 10, "score": 30}
        ], total=1), [(0, 1)])

    def test_empty_analysis_and_unknown_length_rejected(self):
        with self.assertRaises(ValueError):
            self.generate([])
        with self.assertRaises(ValueError):
            self.generate([{"frame_idx": 0}], total=0)

    def test_semantic_notes_survive_same_color_and_lua_delimiters(self):
        semantic = {"score": 60, "recommendation": "備選", "visual_summary": "街道",
                    "audio_summary": "路線", "relationship": "補充", "confidence": 0.7,
                    "reason": "過場"}
        intervals = self.generate([
            {"frame_idx": 0, "score": 60, "semantic": semantic},
            {"frame_idx": 60, "score": 60, "semantic": {**semantic, "reason": "另一事件"}},
        ])
        self.assertEqual(intervals, [(0, 60), (60, 157)])
        self.assertEqual(self.decision.lua_string('內容 ]==] 不可執行'),
                         '[===[內容 ]==] 不可執行]===]')


class BridgeTests(unittest.TestCase):
    def test_default_dispatch_does_not_wait_for_receipt(self):
        from bridge import auto_injector as bridge
        from pipeline.submission import submit_markers
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            task = root / "task.lua"
            task.write_text(f'result_path = [==[{(root/"receipt.json").as_posix()}]==]')
            commands, keys = [], []
            keyboard = types.ModuleType("pyautogui")
            keyboard.press = keys.append
            keyboard.click = lambda *args: None
            keyboard.hotkey = lambda *args: None
            clipboard = types.ModuleType("pyperclip")
            clipboard.copy = commands.append
            stack.enter_context(patch.dict(sys.modules, {"pyautogui":keyboard,"pyperclip":clipboard}))
            stack.enter_context(patch.object(bridge,"find_all_resolve_windows",return_value=(1,2)))
            stack.enter_context(patch.object(bridge,"force_activate_window"))
            center = stack.enter_context(patch.object(bridge,"center_window",return_value=(0,0,100,100)))
            stack.enter_context(patch.object(bridge.time,"sleep"))
            receipt = stack.enter_context(patch.object(bridge,"read_receipt",side_effect=AssertionError("must not wait")))
            self.assertTrue(submit_markers(task,bridge.trigger_resolve_injection))
            self.assertTrue(submit_markers(task,bridge.trigger_resolve_injection))
            self.assertEqual(keys,["enter"])
            self.assertEqual(len(commands),1)
            self.assertIn('AI_DIRECTOR_TASK_DATA',commands[0])
            self.assertIn('AI_DIRECTOR_NO_RECEIPT = true',commands[0])
            self.assertNotIn('loadfile',commands[0])
            center.assert_called_once_with(2)
            receipt.assert_not_called()
            state=json.loads((root/"resolve_submission.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"],"submitted")
            self.assertFalse(state["write_verified"])

    def test_clipboard_receipt_without_lua_file_writer(self):
        from bridge import auto_injector as bridge
        for stale in (False, True):
            with self.subTest(stale=stale), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                receipt = Path(tmp) / "receipt.json"
                task = Path(tmp) / "task.lua"
                task.write_text(f'result_path = [==[{receipt.as_posix()}]==]', encoding="utf-8")
                commands = []
                keyboard = types.ModuleType("pyautogui")
                keyboard.hotkey = lambda *args: None
                keyboard.click = lambda *args: None
                keyboard.press = lambda *args: None
                clipboard = types.ModuleType("pyperclip")
                clipboard.copy = commands.append
                def paste():
                    token = "old-token" if stale else re.search(r'AI_DIRECTOR_RECEIPT_TOKEN = "(.*?)"', commands[-1]).group(1)
                    return f'AI_DIRECTOR_RECEIPT:{token}:' + json.dumps({"expected": 45, "written": 45, "coverage_ok": True})
                clipboard.paste = paste
                stack.enter_context(patch.dict(sys.modules, {"pyautogui": keyboard, "pyperclip": clipboard}))
                stack.enter_context(patch.object(bridge, "find_all_resolve_windows", return_value=(1, 2)))
                stack.enter_context(patch.object(bridge, "force_activate_window"))
                stack.enter_context(patch.object(bridge, "center_window", return_value=(0, 0, 100, 100)))
                stack.enter_context(patch.object(bridge.time, "sleep"))
                if stale:
                    stack.enter_context(patch.object(bridge.time, "monotonic", side_effect=[0, 0, 11]))
                ok, _ = bridge.trigger_resolve_injection(task, wait_for_receipt=True)
                self.assertEqual(ok, not stale)
                self.assertEqual(len(commands), 1)
                self.assertEqual(receipt.exists(), not stale)

    def test_submission_once_uses_fresh_receipt_and_ignores_old_success(self):
        from bridge import auto_injector as bridge
        from pipeline.submission import submit_markers
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            old_receipt = root / "old.json"
            old_receipt.write_text(json.dumps({"expected": 2, "written": 2, "coverage_ok": True}))
            task = root / "task.lua"
            task.write_text(f'result_path = [==[{old_receipt.as_posix()}]==]', encoding="utf-8")
            commands, receipts = [], []
            keyboard = types.ModuleType("pyautogui")
            keyboard.hotkey = lambda *args: None
            keyboard.click = lambda *args: None
            def press(key):
                if key == "enter":
                    path = Path(re.search(r'AI_DIRECTOR_RESULT_PATH = \[\[(.*?)\]\]', commands[-1]).group(1))
                    receipts.append(path)
                    ok = len(receipts) > 1
                    path.write_text(json.dumps({"expected": 2, "written": 2 if ok else 1, "coverage_ok": ok}))
            keyboard.press = press
            clipboard = types.ModuleType("pyperclip")
            clipboard.copy = commands.append
            stack.enter_context(patch.dict(sys.modules, {"pyautogui": keyboard, "pyperclip": clipboard}))
            stack.enter_context(patch.object(bridge, "find_all_resolve_windows", return_value=(1, 2)))
            stack.enter_context(patch.object(bridge, "force_activate_window"))
            stack.enter_context(patch.object(bridge, "center_window", return_value=(0, 0, 100, 100)))
            stack.enter_context(patch.object(bridge.time, "sleep"))
            self.assertFalse(submit_markers(task, lambda path: bridge.trigger_resolve_injection(path, fresh_receipt=True, wait_for_receipt=True), delay=0))
            self.assertFalse(submit_markers(task, lambda path: bridge.trigger_resolve_injection(path, fresh_receipt=True, wait_for_receipt=True), delay=0))
            self.assertEqual(len(set(receipts)), 1)
            self.assertNotIn(old_receipt, receipts)

    def test_receipt_required_for_success(self):
        from bridge import auto_injector as bridge
        for written, coverage, expected_success in ((2, True, True), (1, False, False)):
            with self.subTest(written=written), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                root = Path(tmp)
                receipt = root / "receipt.json"
                task = root / "task.lua"
                task.write_text(f'result_path = [==[{receipt.as_posix()}]==]', encoding="utf-8")
                keyboard = types.ModuleType("pyautogui")
                keyboard.hotkey = lambda *args: None
                keyboard.click = lambda *args: None
                def press(key):
                    if key == "enter":
                        receipt.write_text(json.dumps({"expected": 2, "written": written,
                                                      "coverage_ok": coverage}))
                keyboard.press = press
                clipboard = types.ModuleType("pyperclip")
                clipboard.copy = lambda text: None
                stack.enter_context(patch.dict(sys.modules, {"pyautogui": keyboard, "pyperclip": clipboard}))
                stack.enter_context(patch.object(bridge, "find_all_resolve_windows", return_value=(1, 2)))
                stack.enter_context(patch.object(bridge, "force_activate_window"))
                stack.enter_context(patch.object(bridge, "center_window", return_value=(0, 0, 100, 100)))
                stack.enter_context(patch.object(bridge.time, "sleep"))
                self.assertEqual(bridge.trigger_resolve_injection(task, wait_for_receipt=True)[0], expected_success)
                self.assertFalse(bridge.trigger_resolve_injection(task, wait_for_receipt=True)[0], "Must reject stale receipt")

    def test_missing_task_rejected(self):
        from bridge.auto_injector import trigger_resolve_injection
        self.assertFalse(trigger_resolve_injection("nonexistent-test-task.lua")[0])


if __name__ == "__main__":
    unittest.main()
