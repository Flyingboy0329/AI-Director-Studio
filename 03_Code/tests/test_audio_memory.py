import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class AudioMemoryTests(unittest.TestCase):
    def load_audio(self, free_gb):
        torch = MagicMock()
        torch.cuda.is_available.return_value = True
        torch.cuda.device_count.return_value = len(free_gb)
        torch.cuda.mem_get_info.side_effect = lambda index: (free_gb[index] * 1024**3, 16 * 1024**3)
        faster = types.ModuleType("faster_whisper")
        faster.WhisperModel = MagicMock()
        source = Path(__file__).resolve().parents[1] / "ai" / "audio_analyzer.py"
        spec = importlib.util.spec_from_file_location("audio_memory_test_subject", source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"torch": torch, "faster_whisper": faster}):
            spec.loader.exec_module(module)
        module.ram_budget = lambda: (16, 4, 12)
        return module

    def test_cpu_used_even_when_auxiliary_has_more_free_memory(self):
        audio = self.load_audio([7, 10])
        self.assertEqual(audio.select_audio_device()[:4], ("cpu", "int8", "small", 0))
        audio.torch.cuda.mem_get_info.assert_not_called()

    def test_primary_insufficient_after_system_reserve_does_not_spill_to_auxiliary(self):
        audio = self.load_audio([5,12])
        self.assertEqual(audio.select_audio_device()[:4],("cpu","int8","small",0))
        audio.torch.cuda.mem_get_info.assert_not_called()

    def test_large_gpu_budget_does_not_change_cpu_policy(self):
        audio = self.load_audio([10,12])
        self.assertEqual(audio.select_audio_device()[:4],("cpu","int8","small",0))

    def test_threads_leave_capacity_on_small_and_large_cpus(self):
        audio=self.load_audio([10])
        for logical,physical,expected in ((1,1,1),(4,2,2),(24,12,4)):
            with patch.object(audio.os,'cpu_count',return_value=logical), patch.object(audio.psutil,'cpu_count',return_value=physical):
                self.assertEqual(audio.audio_cpu_threads(),expected)

    def test_manual_medium_is_loaded_on_cpu_with_bounded_threads(self):
        audio=self.load_audio([20,20])
        with patch.object(audio,'resolve_whisper_model',return_value=('cache','project_local')), patch.object(audio,'audio_cpu_threads',return_value=2):
            _,metadata=audio.load_audio_model('medium',notify=lambda _:None)
        audio.WhisperModel.assert_called_once_with('cache',device='cpu',device_index=0,
                                                 compute_type='int8',cpu_threads=2,num_workers=1)
        self.assertEqual(metadata['selected_model'],'medium')
        self.assertEqual(metadata['cpu_threads'],2)

    def test_uses_cpu_when_both_cards_are_full(self):
        audio = self.load_audio([1, 2])
        self.assertEqual(audio.select_audio_device()[:3], ("cpu", "int8", "small"))

    def test_rocm_does_not_request_ctranslate_cuda(self):
        audio = self.load_audio([20])
        audio.torch.version.hip = "test-rocm"
        self.assertEqual(audio.select_audio_device()[:3], ("cpu", "int8", "small"))


if __name__ == "__main__":
    unittest.main()
