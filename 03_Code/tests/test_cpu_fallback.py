from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_runtime import ModelRuntime


class CpuFallbackTests(unittest.TestCase):
    def run_case(self,root,tail,cpu_success=True,available_gib=24, gpu_available=True):
        (root/'model.gguf').write_bytes(b'weights');(root/'mmproj.gguf').write_bytes(b'projection')
        commands=[];processes=[]
        def start(command,**kwargs):
            commands.append(list(command));process=Mock()
            failed=len(commands)==1 or not cpu_success
            process.poll.return_value=1 if failed else None
            if failed:kwargs['stdout'].write(tail.encode());kwargs['stdout'].flush()
            processes.append(process);return process
        settings=dict(llm_path=str(root/'model.gguf'),llm_mmproj_path=str(root/'mmproj.gguf'),model_mode='llm_only')
        logs=[]
        with patch('model_runtime.get_project_root',return_value=root), \
             patch('model_runtime.find_server',return_value='server'), \
             patch('model_runtime.detect_engine_devices',return_value=[dict(id='CUDA0',name='GPU',total_mb=8192,free_mb=6144)] if gpu_available else []), \
             patch('model_runtime.port_in_use',return_value=False), \
             patch('model_runtime.server_command',side_effect=lambda *args:['server','--port','8080','-ngl','auto']), \
             patch('model_runtime.LocalModelClient'),patch('model_runtime.subprocess.Popen',side_effect=start), \
             patch('model_runtime.psutil.virtual_memory',return_value=SimpleNamespace(total=32*1024**3,available=available_gib*1024**3)):
            runtime=ModelRuntime()
            if cpu_success and available_gib>10 and 'out of memory' in tail.lower():
                runtime.ensure_ready(settings,logs.append)
                runtime.ensure_ready(settings,logs.append)
                self.assertEqual(len(commands),2)
                self.assertEqual(commands[1][commands[1].index('--device')+1],'none')
                self.assertEqual(commands[1][commands[1].index('-ngl')+1],'0')
                self.assertIn('--no-mmproj-offload',commands[1])
                self.assertIn('llm',runtime.cpu_fallback_roles)
                runtime.stop()
            else:
                with self.assertRaises((RuntimeError,ValueError)):runtime.ensure_ready(settings,logs.append)
                self.assertFalse(runtime.processes)
        return commands,logs

    def test_gpu_oom_retries_once_on_cpu_and_reuses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands,logs=self.run_case(Path(tmp),'CUDA error: out of memory')
            self.assertEqual(len(commands),2)
            self.assertTrue(any('[CPU 備選]' in line for line in logs))

    def test_bad_model_is_not_retried_as_cpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands,_=self.run_case(Path(tmp),'invalid model format')
            self.assertEqual(len(commands),1)

    def test_low_ram_does_not_start_cpu_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands,_=self.run_case(Path(tmp),'CUDA error: out of memory',available_gib=1)
            self.assertEqual(len(commands),1)

    def test_failed_cpu_attempt_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands,_=self.run_case(Path(tmp),'CUDA error: out of memory',cpu_success=False)
            self.assertEqual(len(commands),2)

    def test_no_gpu_and_insufficient_ram_refuses_before_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands,_=self.run_case(Path(tmp),'CPU budget',available_gib=1,gpu_available=False)
            self.assertEqual(commands,[])

    def test_scheme_a_retries_only_failed_vlm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'model.gguf').write_bytes(b'weights')
            commands=[]
            def start(command,**kwargs):
                commands.append(command);process=Mock()
                process.poll.return_value=1 if len(commands)==2 else None
                if len(commands)==2:
                    kwargs['stdout'].write(b'CUDA error: out of memory');kwargs['stdout'].flush()
                return process
            with patch('model_runtime.get_project_root',return_value=root), \
                 patch('model_runtime.find_server',return_value='server'),patch('model_runtime.port_in_use',return_value=False), \
                 patch('model_runtime.detect_engine_devices',return_value=[dict(id='CUDA0',name='GPU',total_mb=8192,free_mb=6144)]), \
                 patch('model_runtime.server_command',side_effect=lambda *args:['server','--port','8080','-ngl','auto']), \
                 patch('model_runtime.LocalModelClient'),patch('model_runtime.check_cpu_ram'), \
                 patch('model_runtime.subprocess.Popen',side_effect=start):
                runtime=ModelRuntime()
                runtime.ensure_ready(dict(llm_path=str(root/'model.gguf'),vlm_path=str(root/'model.gguf'),
                                          mmproj_path=str(root/'model.gguf'),model_mode='separate'))
                self.assertEqual(len(commands),3)
                self.assertEqual(runtime.cpu_fallback_roles,{'vlm'})
                self.assertEqual(commands[0][commands[0].index('--port')+1],'8080')
                self.assertEqual(commands[2][commands[2].index('--port')+1],'8081')
                runtime.stop()


if __name__=='__main__':unittest.main()
