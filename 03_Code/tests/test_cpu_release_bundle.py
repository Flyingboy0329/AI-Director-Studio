import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_cpu_sensor import check_bundle
from cpu_temperature import sensor_directory


class CpuReleaseBundleTests(unittest.TestCase):
    def test_public_path_and_all_sensor_hashes(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(sensor_directory(), root / "third_party" / "cpu-sensor")
        self.assertEqual(check_bundle(), [])

    def test_missing_and_corrupt_dll_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SHA256.json").write_text(json.dumps({"LibreHardwareMonitorLib.dll":hashlib.sha256(b"correct").hexdigest()}))
            self.assertTrue(check_bundle(root)[0].startswith("Missing:"))
            (root / "LibreHardwareMonitorLib.dll").write_bytes(b"wrong")
            self.assertTrue(check_bundle(root)[0].startswith("SHA256 mismatch:"))

    def test_default_windows_sensor_dependency_is_declared(self):
        root = Path(__file__).resolve().parents[2]
        self.assertIn("-r requirements-cpu-sensor.txt", (root / "requirements.txt").read_text())
        self.assertIn('platform_system == "Windows"', (root / "requirements-cpu-sensor.txt").read_text())


if __name__ == "__main__":
    unittest.main()
