import sys
from pathlib import Path
import unittest
import tempfile
import stat
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hardware_monitor import device_arguments
from gpu_memory_policy import system_headroom_mb, whisper_headroom_mb
from start_model_server import server_command


def devices(primary_free=14336, secondary_free=11264):
    return [{'id':'CUDA0','name':'main','total_mb':20480,'free_mb':primary_free},
            {'id':'CUDA1','name':'aux','total_mb':12288,'free_mb':secondary_free}]


class AdaptiveGpuTests(unittest.TestCase):
    def test_auxiliary_target_uses_total_usage_and_model_size(self):
        with tempfile.TemporaryDirectory() as tmp, patch('hardware_monitor.Path.stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_size=16*1024**3)):
            model=Path(tmp)/'model.gguf'
            logs=[]
            args=device_arguments(devices(),notify=logs.append,model_path=model)
            ratio=[float(v) for v in args[args.index('--tensor-split')+1].split(',')]
            expected_aux=int(12288*.9)-(12288-11264)-512
            expected_main=16*1024-expected_aux
            self.assertAlmostEqual(ratio[1]/sum(ratio),expected_aux/(expected_aux+expected_main))
            self.assertTrue(any('90%' in line for line in logs))
            margin=[int(v) for v in args[args.index('--fit-target')+1].split(',')]
            self.assertGreaterEqual(margin[0],4096)
            self.assertGreaterEqual(margin[1],12288*.1)

    def test_small_model_does_not_artificially_fill_auxiliary(self):
        with tempfile.TemporaryDirectory() as tmp, patch('hardware_monitor.Path.stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_size=2*1024**3)):
            model=Path(tmp)/'model.gguf'
            args=device_arguments(devices(),model_path=model)
            ratio=[float(v) for v in args[args.index('--tensor-split')+1].split(',')]
            self.assertGreater(ratio[1]/sum(ratio),.99)

    def test_busy_auxiliary_reduces_assigned_share(self):
        with tempfile.TemporaryDirectory() as tmp, patch('hardware_monitor.Path.stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_size=16*1024**3)):
            model=Path(tmp)/'model.gguf'
            idle=device_arguments(devices(),model_path=model)
            busy=device_arguments(devices(secondary_free=6144),model_path=model)
            def share(args):
                ratio=[float(v) for v in args[args.index('--tensor-split')+1].split(',')]
                return ratio[1]/sum(ratio)
            self.assertLess(share(busy),share(idle))

    def test_default_layers_auto_allows_fit_and_explicit_layers_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.gguf';path.touch()
            settings={'llm_path':str(path)}
            auto=server_command(settings,'server')
            self.assertEqual(auto[auto.index('-ngl')+1],'auto')
            manual=server_command(settings,'server',gpu_layers=12)
            self.assertEqual(manual[manual.index('-ngl')+1],'12')

    def test_more_resolve_use_reduces_primary_share(self):
        first=device_arguments(devices())
        busy=device_arguments(devices(primary_free=10240))
        ratio=lambda args:[float(v) for v in args[args.index('--tensor-split')+1].split(',')]
        a,b=ratio(first),ratio(busy)
        self.assertLess(b[0]/sum(b),a[0]/sum(a))
        self.assertEqual(first[first.index('--fit')+1],'on')
        reserve=[int(v) for v in first[first.index('--fit-target')+1].split(',')]
        self.assertEqual(reserve[0],4096)
        self.assertGreater(reserve[0],reserve[1])

    def test_full_primary_excluded_but_secondary_retained(self):
        args=device_arguments(devices(primary_free=4096))
        self.assertEqual(args[args.index('--device')+1],'CUDA1')
        self.assertNotIn('--tensor-split',args)
        self.assertEqual(args[args.index('--split-mode')+1],'none')

    def test_no_budget_or_missing_data_does_not_guess_equal_split(self):
        for data in (devices(1024,512),[{'id':'CUDA0'},{'id':'CUDA1'}]):
            args=device_arguments(data)
            self.assertEqual(args[args.index('--device')+1],'none')
            self.assertNotIn('--tensor-split',args)

    def test_cpu_whisper_size_does_not_reserve_gpu_budget(self):
        logs=[]
        small=device_arguments(devices(),{'whisper_model':'small'})
        medium=device_arguments(devices(),{'whisper_model':'medium'},logs.append)
        self.assertEqual(small[small.index('--tensor-split')+1],medium[medium.index('--tensor-split')+1])
        self.assertTrue(any('目前可用' in line and 'Whisper 預留' in line for line in logs))
        self.assertEqual(whisper_headroom_mb('medium'),0)
        self.assertEqual(system_headroom_mb(20480),4096)

if __name__=='__main__':unittest.main()
