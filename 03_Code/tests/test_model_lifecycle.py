import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_runtime import ModelRuntime
from model_process_registry import ModelProcessRegistry
from model_selection import ModelSelectionPanel, RuntimeLoadThread
from app_gui import MidnightDashboardWindow
from ai.audio_analyzer import release_whisper, WhisperRuntime
from PyQt6.QtWidgets import QApplication


class ModelLifecycleTests(unittest.TestCase):
    def test_deployment_waits_for_whisper_and_reports_failure(self):
        runtime=Mock();events=[]
        runtime.ensure_ready.side_effect=lambda *_:events.append('gguf')
        runtime.ensure_audio_ready.side_effect=lambda *_:events.append('whisper')
        loader=RuntimeLoadThread(runtime,{'llm_path':'test.gguf'})
        loader.ready.connect(lambda ok,_:events.append(ok))
        loader.run()
        self.assertEqual(events,['gguf','whisper',True])
        events.clear()
        runtime.ensure_audio_ready.side_effect=RuntimeError('ASR load failed')
        loader.run()
        self.assertEqual(events,['gguf',False])

    def test_whisper_deploy_reuse_and_explicit_unload(self):
        runtime=WhisperRuntime(); model=Mock()
        metadata=dict(selected_model='medium', device='cuda', device_index=0, compute_type='float16')
        messages=[]
        with patch('ai.audio_analyzer.load_audio_model',return_value=(model,metadata)) as loader:
            runtime.ensure_ready('medium',messages.append)
            runtime.ensure_ready('medium',messages.append)
            loader.assert_called_once()
            self.assertIs(runtime.model,model)
            self.assertTrue(any('READY' in line and 'medium' in line for line in messages))
            runtime.unload(messages.append)
            model.model.unload_model.assert_called_once_with(to_cpu=False)
            self.assertIsNone(runtime.model)
            self.assertTrue(any('UNLOADED' in line for line in messages))

    def test_whisper_failed_release_retains_model_for_retry(self):
        runtime=WhisperRuntime(); model=Mock();runtime.model=model
        model.model.unload_model.side_effect=RuntimeError('busy')
        with self.assertRaises(RuntimeError):runtime.unload(lambda _:None)
        self.assertIs(runtime.model,model)
        model.model.unload_model.side_effect=None
        runtime.unload(lambda _:None)
        self.assertIsNone(runtime.model)

    def test_model_unload_releases_whisper_without_any_gguf(self):
        runtime=ModelRuntime(); runtime.audio_runtime=WhisperRuntime()
        model=Mock();runtime.audio_runtime.model=model
        self.assertTrue(runtime.has_audio_model())
        runtime.stop(lambda _:None)
        model.model.unload_model.assert_called_once_with(to_cpu=False)
        self.assertFalse(runtime.has_audio_model())

    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def fake_process(self, root):
        live=Mock();live.create_time.return_value=123.5
        live.exe.return_value=str(root/'llama-server.exe')
        live.cmdline.return_value=[str(root/'llama-server.exe'),'-m','model.gguf']
        live.is_running.return_value=True;live.wait.return_value=0
        return live

    def test_owned_process_survives_close_and_recovered_process_can_really_be_terminated(self):
        with tempfile.TemporaryDirectory() as tmp,patch('model_runtime.get_project_root',return_value=Path(tmp)):
            root=Path(tmp);live=self.fake_process(root);handle=Mock(pid=1234);handle.poll.return_value=None
            with patch('model_process_registry.psutil.Process',return_value=live):
                first=ModelRuntime();first.processes['llm']=(handle,root/'model.log',('config',))
                first.preserve_background()
                handle.terminate.assert_not_called()
                second=ModelRuntime();second.recover()
                self.assertIn('llm',second.processes)
                second.stop()
                live.terminate.assert_called_once();live.wait.assert_called_once()
                self.assertEqual(second.registry.read(),{})

    def test_pid_reuse_or_command_mismatch_is_not_adopted_or_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);live=self.fake_process(root);registry=ModelProcessRegistry(root/'registry.json')
            with patch('model_process_registry.psutil.Process',return_value=live):
                registry.add('llm',Mock(pid=1234),root/'log',('config',))
                live.create_time.return_value=999
                self.assertEqual(registry.recover(lambda msg:None),{})
                live.create_time.return_value=123.5;live.cmdline.return_value=['another-program']
                self.assertEqual(registry.recover(lambda msg:None),{})
                live.terminate.assert_not_called()

    def test_stop_sentinel_preserves_model_and_manual_unload_waits_for_worker(self):
        with patch.object(MidnightDashboardWindow,'start_telemetry'),patch.object(ModelSelectionPanel,'start_scan'), \
             patch.object(ModelSelectionPanel,'save_settings'):
            window=MidnightDashboardWindow()
            window.model_panel.runtime.processes['llm']=(Mock(),Path('unused'),())
            worker=Mock();worker.isRunning.return_value=True;window.worker=worker
            with patch.object(window.model_panel,'unload_runtime') as unload,patch.object(window.model_panel.runtime,'stop') as stop:
                window.toggle_watching();worker.stop.assert_called_once();stop.assert_not_called()
                window.on_worker_finished();unload.assert_not_called()
                self.assertEqual(window.model_panel.load_button.text(),'卸除模型')
                self.assertIn('#E11D48',window.model_panel.load_button.styleSheet())
                window.worker=worker;window.request_model_unload();unload.assert_not_called()
                window.on_worker_finished();unload.assert_called_once()
            with patch.object(window.model_panel.runtime,'preserve_background') as keep,patch.object(window.model_panel,'shutdown_runtime') as shutdown:
                window.close();keep.assert_called_once();shutdown.assert_not_called()

    def test_whisper_selection_and_recovery_button_are_logged(self):
        with patch.object(ModelSelectionPanel,'start_scan'),patch.object(ModelSelectionPanel,'save_settings'):
            panel=ModelSelectionPanel();messages=[];panel.runtime_log.connect(messages.append)
            panel.whisper.setCurrentIndex(panel.whisper.findData('tiny'))
            panel.whisper.setCurrentIndex(panel.whisper.findData('medium'))
            self.assertTrue(any('medium' in m and '未載入' in m for m in messages))
            panel.runtime.processes['llm']=(Mock(),Path('unused'),())
            panel.on_recovered(True,'recovered')
            self.assertEqual(panel.load_button.text(),'卸除模型')
            self.assertIn('#E11D48',panel.load_button.styleSheet());panel.close()

    def test_whisper_uses_explicit_full_weight_unload(self):
        model=Mock();record=Mock()
        release_whisper(model,record)
        model.model.unload_model.assert_called_once_with(to_cpu=False)
        record.assert_called_once_with('releasing',release_status='unloaded')

if __name__=='__main__':unittest.main()
