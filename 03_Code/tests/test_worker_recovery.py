import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if importlib.util.find_spec("torch") and importlib.util.find_spec("faster_whisper"):
    import app_gui
else:
    app_gui = None


@unittest.skipIf(app_gui is None, "Run in the documented application environment")
class WorkerRecoveryTests(unittest.TestCase):
    def test_file_transient_failure_retries_and_restores_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = app_gui.WorkerThread(tmp, "")
            original = sys.stdout
            with patch("app_gui.wait_for_file_ready"), \
                    patch("app_gui.run_main_pipeline", side_effect=[ValueError("transient"), True]) as pipeline, \
                    patch.object(worker.cancel_event, "wait"):
                self.assertTrue(worker.process_file(Path(tmp) / "sample.mp4"))
            self.assertEqual(pipeline.call_count, 2)
            self.assertIs(sys.stdout, original)

    def test_exhausted_file_does_not_block_next_file_and_queue_is_acknowledged(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = app_gui.WorkerThread(tmp, "")
            worker.task_queue.put(Path(tmp) / "bad.mp4")
            worker.task_queue.put(Path(tmp) / "good.mp4")
            calls = []
            def pipeline(path, **kwargs):
                calls.append(Path(path).name)
                if Path(path).name == "bad.mp4":
                    raise ValueError("unreadable media")
                worker.is_watching = False
                return True
            with patch("app_gui.wait_for_file_ready"), patch("app_gui.run_main_pipeline", side_effect=pipeline), \
                    patch.object(worker.cancel_event, "wait"):
                worker.run()
            self.assertEqual(calls, ["bad.mp4"] * 3 + ["good.mp4"])
            self.assertEqual(worker.task_queue.unfinished_tasks, 0)
            self.assertTrue(worker.task_queue.empty())


if __name__ == "__main__":
    unittest.main()
