from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_runtime import ModelRuntime


class RuntimeTests(unittest.TestCase):
    def test_stop_reaps_real_owned_process(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        runtime = ModelRuntime()
        runtime.processes["llm"] = (process, Path("unused.log"), ())
        try:
            runtime.stop()
            self.assertIsNotNone(process.poll())
            self.assertEqual(runtime.processes, {})
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    def test_timeout_uses_kill_and_wait(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("server", 5), 0]
        runtime = ModelRuntime()
        runtime.processes["llm"] = (process, Path("unused.log"), ())
        runtime.stop()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)
        self.assertFalse(runtime.processes)

    def test_failed_stop_preserves_handle_and_stops_other_role(self):
        failed, other = MagicMock(), MagicMock()
        failed.poll.return_value = None
        failed.wait.side_effect = OSError("stop failed")
        other.poll.return_value = 0
        runtime = ModelRuntime()
        runtime.processes = {"llm": (failed, Path("unused.log"), ()), "vlm": (other, Path("unused.log"), ())}
        with self.assertRaises(RuntimeError):
            runtime.stop()
        self.assertIn("llm", runtime.processes)
        self.assertNotIn("vlm", runtime.processes)

    def test_owned_service_starts_checks_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp, patch("model_runtime.get_project_root", return_value=Path(tmp)), \
                patch("model_runtime.detect_engine_devices", return_value=[{"id": "CUDA0", "name": "Test GPU"}]), \
                patch("model_runtime.port_in_use", return_value=False), \
                patch("model_runtime.find_server", return_value=str(Path(tmp) / "llama-server.exe")), \
                patch("model_runtime.server_command", return_value=["server", "--port", "8080"]), \
                patch("model_runtime.subprocess.Popen") as popen, \
                patch("model_runtime.LocalModelClient") as client, patch('model_runtime.check_cpu_ram'):
            popen.return_value.poll.return_value = None
            runtime = ModelRuntime()
            settings = {"llm_path": "gemma.gguf", "llm_mmproj_path": "mmproj.gguf", "model_mode": "llm_only"}
            runtime.ensure_ready(settings)
            client.return_value.check.assert_called_with(require_images=True)
            self.assertIn("llm", runtime.processes)
            runtime.ensure_ready(settings)
            self.assertEqual(popen.call_count, 1, "Reuse own matching process")
            runtime.stop()
            popen.return_value.terminate.assert_called_once()
            self.assertEqual(runtime.processes, {})

    def test_external_service_is_never_terminated_or_replaced(self):
        with patch("model_runtime.port_in_use", return_value=True), \
                patch("model_runtime.LocalModelClient") as client, \
                patch("model_runtime.subprocess.Popen") as popen:
            runtime = ModelRuntime()
            runtime.ensure_ready({"llm_path": "gemma.gguf", "model_mode": "llm_only"})
            runtime.stop()
            popen.assert_not_called()
            client.return_value.check.side_effect = ValueError("Wrong model")
            with self.assertRaisesRegex(ValueError, "Wrong model"):
                runtime.ensure_ready({"llm_path": "gemma.gguf"})
            popen.assert_not_called()

    def test_startup_exit_reports_engine_log(self):
        with tempfile.TemporaryDirectory() as tmp, patch("model_runtime.get_project_root", return_value=Path(tmp)), \
                patch("model_runtime.detect_engine_devices", return_value=[{"id": "CUDA0", "name": "Test GPU"}]), \
                patch("model_runtime.port_in_use", return_value=False), \
                patch("model_runtime.find_server", return_value=str(Path(tmp) / "server.exe")), \
                patch("model_runtime.server_command", return_value=["server", "--port", "8080"]), \
                patch("model_runtime.subprocess.Popen") as popen, \
                patch("model_runtime.LocalModelClient"), patch('model_runtime.check_cpu_ram'):
            popen.return_value.poll.return_value = 1
            runtime = ModelRuntime()
            with self.assertRaisesRegex(RuntimeError, "引擎退出"):
                runtime.ensure_ready({"llm_path": "gemma.gguf"})
            self.assertFalse(runtime.processes)


if __name__ == "__main__":
    unittest.main()
