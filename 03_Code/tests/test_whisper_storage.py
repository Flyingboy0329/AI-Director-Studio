import json
from pathlib import Path
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_storage import resolve_whisper_model, complete_model


def write_model(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    (root/'model.bin').write_bytes(b'weights')
    (root/'config.json').write_text('{}')
    (root/'tokenizer.json').write_text('{}')
    return root


class WhisperStorageTests(unittest.TestCase):
    def test_first_download_then_offline_reuse_even_across_callers(self):
        with tempfile.TemporaryDirectory() as tmp,patch('whisper_storage.get_project_root',return_value=Path(tmp)):
            online=[]
            def download(name,local_files_only=False,output_dir=None):
                if local_files_only:raise OSError('not cached')
                online.append(name);return str(write_model(output_dir))
            with patch('whisper_storage.download_model',side_effect=download) as downloader:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(lambda _:resolve_whisper_model('small',lambda _:None),range(2)))
                self.assertEqual(online,['small'])
                self.assertEqual(results[0][0],results[1][0])
                downloader.reset_mock()
                resolve_whisper_model('small',lambda _:None)
                downloader.assert_not_called()
                self.assertTrue(complete_model(results[0][0]))

    def test_complete_system_cache_is_copied_without_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch('whisper_storage.get_project_root',return_value=Path(tmp)):
            cached=write_model(Path(tmp)/'cache')
            with patch('whisper_storage.download_model',return_value=str(cached)) as downloader:
                result,source=resolve_whisper_model('medium',lambda _:None)
            downloader.assert_called_once_with('medium',local_files_only=True)
            self.assertEqual(source,'cache_import')
            self.assertIn('04_Models',result)
            self.assertTrue(cached.exists())

    def test_partial_download_is_not_ready_and_retry_completes_it(self):
        with tempfile.TemporaryDirectory() as tmp,patch('whisper_storage.get_project_root',return_value=Path(tmp)):
            target=Path(tmp)/'04_Models'/'Whisper'/'small';target.mkdir(parents=True)
            (target/'model.bin').write_bytes(b'partial')
            def download(name,local_files_only=False,output_dir=None):
                if local_files_only:raise OSError('not cached')
                write_model(output_dir);return output_dir
            with patch('whisper_storage.download_model',side_effect=download):
                result,_=resolve_whisper_model('small',lambda _:None)
            self.assertTrue(complete_model(result))
            (target/'model.bin').write_bytes(b'x')
            self.assertFalse(complete_model(target))

    def test_custom_incomplete_directory_never_downloads(self):
        with tempfile.TemporaryDirectory() as tmp,patch('whisper_storage.download_model') as downloader:
            with self.assertRaises(ValueError):resolve_whisper_model(tmp,lambda _:None)
            downloader.assert_not_called()

    def test_alias_and_repo_share_project_directory(self):
        with tempfile.TemporaryDirectory() as tmp,patch('whisper_storage.get_project_root',return_value=Path(tmp)):
            write_model(Path(tmp)/'04_Models'/'Whisper'/'small')
            with patch('whisper_storage.download_model') as downloader:
                first,_=resolve_whisper_model('small',lambda _:None)
                second,_=resolve_whisper_model('Systran/faster-whisper-small',lambda _:None)
                self.assertEqual(first,second);downloader.assert_not_called()


if __name__=='__main__':unittest.main()
