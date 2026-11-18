import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware_monitor import HardwareMonitor, device_arguments, detect_engine_devices, shared_memory_device
from install_model_runtime import choose_assets, safe_extract
from path_utils import load_local_settings, resolve_project_path


class PortabilityTests(unittest.TestCase):
    def test_single_dual_shared_and_cpu_device_policies(self):
        self.assertEqual(device_arguments([]), ["--device", "none", "--split-mode", "none"])
        self.assertEqual(device_arguments([{"id": "CUDA0"}])[-1], "none")
        self.assertEqual(device_arguments([{"id": "CUDA0"}, {"id": "CUDA1"}]),
                         ["--device", "none", "--split-mode", "none"])
        self.assertNotIn("--tensor-split",device_arguments([{"id":"CUDA0"},{"id":"Vulkan0"}]))
        self.assertEqual(device_arguments([{"id": "Metal"}]), ["--device", "Metal", "--split-mode", "none"])

    def test_engine_inventory_parser(self):
        with patch("hardware_monitor.run_output", return_value="Available devices:\n CUDA0: Example GPU (8192 MiB, 6144 MiB free)\n Metal: Apple GPU (32768 MiB, 16000 MiB free)\n"):
            result = detect_engine_devices("server")
        self.assertEqual([d["id"] for d in result], ["CUDA0", "Metal"])
        self.assertEqual(result[0]["free_mb"], 6144)

    def test_shared_memory_is_labeled_as_system_scope(self):
        monitor = HardwareMonitor.__new__(HardwareMonitor)
        monitor.nvml = None
        monitor.other_names = None
        memory = SimpleNamespace(total=32 * 1024**3, used=16 * 1024**3, percent=50)
        with patch.object(monitor, "nvidia", return_value=[]), \
                patch.object(monitor, "discover_other_names", return_value=["Apple M4"]), \
                patch("hardware_monitor.platform.system", return_value="Darwin"), \
                patch("hardware_monitor.platform.machine", return_value="arm64"), \
                patch("hardware_monitor.psutil.virtual_memory", return_value=memory), \
                patch("hardware_monitor.psutil.disk_partitions", return_value=[]):
            result = monitor.snapshot()
        card = result["gpus"][0]
        self.assertEqual(card["kind"], "shared")
        self.assertEqual(card["total_gb"], 32)
        self.assertIn("系統", card["scope"])
        self.assertIsNone(card["compute_percent"])
        self.assertIsNone(card["temperature"])
        self.assertTrue(shared_memory_device("Radeon 8060S", "Windows", "AMD64"))
        self.assertFalse(shared_memory_device("Example discrete GPU", "Windows", "AMD64"))

    def test_os_asset_selection(self):
        names = ["llama-test-bin-macos-arm64.tar.gz", "llama-test-bin-win-cpu-x64.zip",
                 "llama-test-bin-win-cuda-13.5-x64.zip", "cudart-llama-bin-win-cuda-13.5-x64.zip",
                 "llama-test-bin-ubuntu-vulkan-x64.tar.gz"]
        assets = [{"name": n} for n in names]
        self.assertEqual(choose_assets(assets, "test", "Darwin", "arm64", "auto")[1], "metal")
        self.assertEqual(len(choose_assets(assets, "test", "Windows", "AMD64", "cuda")[0]), 2)
        self.assertEqual(choose_assets(assets, "test", "Windows", "AMD64", "cpu")[0][0]["name"], names[1])

    def test_preferences_migrate_and_paths_relocate(self):
        with tempfile.TemporaryDirectory() as tmp, patch("path_utils.get_project_root", return_value=Path(tmp)):
            project = Path(tmp) / "01_Project"
            project.mkdir()
            source = project / "model_settings.json"
            source.write_text(json.dumps({"model_dir": "04_Models", "custom": "preserved"}))
            loaded = load_local_settings("model_settings.json")
            self.assertEqual(loaded["custom"], "preserved")
            self.assertTrue((Path(tmp) / ".local" / "model_settings.json").is_file())
            source.write_text('{}')
            self.assertEqual(load_local_settings("model_settings.json")["custom"], "preserved")
            self.assertEqual(resolve_project_path("04_Models"), Path(tmp) / "04_Models")

    def test_archive_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bad.zip"
            target = Path(tmp) / "runtime"
            target.mkdir()
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../outside.txt", "invalid")
            with self.assertRaises(ValueError):
                safe_extract(archive, target)
            self.assertFalse((Path(tmp) / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
