import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.audio_analyzer import select_audio_device, load_audio_model
from whisper_resources import ram_budget, process_rss_gib


class WhisperRamTests(unittest.TestCase):
    def test_available_not_total_drives_budget_and_reserve(self):
        memory=SimpleNamespace(total=32*1024**3,available=10*1024**3)
        with patch('whisper_resources.psutil.virtual_memory',return_value=memory):
            available,reserve,budget=ram_budget()
        self.assertEqual(available,10)
        self.assertAlmostEqual(reserve,6.4)
        self.assertAlmostEqual(budget,3.6)

    def test_auto_falls_back_by_ram_and_refuses_exhaustion(self):
        for budget,expected in ((8,'small'),(2,'small'),(1,'base'),(.5,'tiny')):
            with patch('ai.audio_analyzer.ram_budget',return_value=(budget+2,2,budget)):
                self.assertEqual(select_audio_device(lambda _:None)[2],expected)
        with patch('ai.audio_analyzer.ram_budget',return_value=(2.1,2,.1)):
            with self.assertRaises(RuntimeError):select_audio_device(lambda _:None)

    def test_insufficient_manual_budget_does_not_download_or_load(self):
        with patch('ai.audio_analyzer.ram_budget',return_value=(5,2,3)), \
             patch('ai.audio_analyzer.resolve_whisper_model') as download,patch('ai.audio_analyzer.WhisperModel') as model:
            with self.assertRaisesRegex(RuntimeError,'RAM'):load_audio_model('medium',notify=lambda _:None)
            download.assert_not_called();model.assert_not_called()

    def test_actual_load_rss_delta_is_logged_and_audited(self):
        logs=[]
        with patch('ai.audio_analyzer.ram_budget',return_value=(10,2,8)), \
             patch('ai.audio_analyzer.resolve_whisper_model',return_value=('cache','project_local')), \
             patch('ai.audio_analyzer.WhisperModel'), \
             patch('ai.audio_analyzer.process_rss_gib',side_effect=[1.,1.8]):
            _,metadata=load_audio_model('small',notify=logs.append)
        self.assertAlmostEqual(metadata['load_rss_delta_gib'],.8)
        self.assertEqual(metadata['asr_ram_budget_gib'],8)
        self.assertTrue(any('非 Whisper 專用' in line for line in logs))
        self.assertFalse(any('語音可用預算=0.00' in line for line in logs))

    def test_rss_probe_failure_is_unavailable(self):
        with patch('whisper_resources.psutil.Process',side_effect=OSError('unavailable')):
            self.assertIsNone(process_rss_gib())


if __name__=='__main__':unittest.main()
