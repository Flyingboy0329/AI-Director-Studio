from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_source import export_source


class ReleaseExportTests(unittest.TestCase):
    def test_readme_assets_notes_and_public_sensor_resources_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=['README.md','RELEASE_NOTES.md','docs/assets/project-banner.svg',
                   'docs/release/TEST_ENVIRONMENT.json','docs/release/FILE_COMPARISON.csv',
                   'docs/release/PROPOSED_UPLOAD_FILES.txt',
                   'third_party/cpu-sensor/LibreHardwareMonitorLib.dll',
                   'third_party/cpu-sensor/licenses/LibreHardwareMonitor-MPL-2.0.txt']
            for name in names:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test')
            with patch('export_source.get_project_root',return_value=root):archive=export_source()
            with ZipFile(archive) as z:
                self.assertTrue(set(names)<=set(z.namelist()))

    def test_private_state_weights_and_old_audit_manifests_are_not_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=['.local/settings.json','.env','04_Models/model.gguf','02_Data/clip.mp4',
                   'docs/ORIGINAL_SOURCE_HASHES.json','docs/RELEASE_FILES_SHA256.txt',
                   '03_Code/__pycache__/example.pyc']
            for name in names:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'private')
            with patch('export_source.get_project_root',return_value=root):archive=export_source()
            with ZipFile(archive) as z:
                self.assertFalse(set(names)&set(z.namelist()))


if __name__=='__main__':unittest.main()
