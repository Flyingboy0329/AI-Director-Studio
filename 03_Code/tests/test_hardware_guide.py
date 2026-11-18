import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hardware_guide import ROWS, ARCHITECTURES, guide_text, render_markdown
from context_settings import CONTEXT_SIZES, validate_context
from start_model_server import server_command
from model_selection import ModelSelectionPanel
from model_runtime import ModelRuntime
from app_gui import HardwareGuideDialog
from PyQt6.QtWidgets import QApplication


class HardwareGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_generated_document_matches_shared_data(self):
        self.assertEqual([r['vram'] for r in ROWS],[4,6,8,12,16,24,32,48])
        self.assertEqual((Path(__file__).resolve().parents[2]/'docs/HARDWARE_CONFIGURATION_GUIDE.md').read_text(encoding='utf-8'),render_markdown())
        for row in ROWS:
            for arch in ARCHITECTURES:
                self.assertIn(row[arch][1],('Estimated','Experimental'))
                self.assertIn(row[arch][0],guide_text(row['vram'],arch))

    def test_guide_all_switches_have_no_runtime_or_scan_or_settings_side_effects(self):
        with patch('subprocess.Popen',side_effect=AssertionError('process forbidden')), \
             patch('psutil.disk_partitions',side_effect=AssertionError('scan forbidden')), \
             patch.object(ModelRuntime,'ensure_ready',side_effect=AssertionError('load forbidden')), \
             patch.object(ModelSelectionPanel,'save_settings',side_effect=AssertionError('settings forbidden')):
            dialog=HardwareGuideDialog('')
            self.assertTrue(dialog.body.isReadOnly())
            for row in ROWS:
                dialog.vram.setCurrentIndex(dialog.vram.findData(row['vram']))
                for arch in ARCHITECTURES:
                    dialog.architecture.setCurrentIndex(dialog.architecture.findData(arch))
                    self.assertEqual(dialog.body.toPlainText(),guide_text(row['vram'],arch))
            dialog.close()

    def test_context_default_and_all_values_reach_both_server_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            model=Path(tmp)/'model.gguf';model.touch()
            for role in ('llm','vlm'):
                default=server_command({f'{role}_path':str(model)},'server',role=role)
                self.assertEqual(default[default.index('-c')+1],'8192')
                for value in CONTEXT_SIZES:
                    cmd=server_command({f'{role}_path':str(model),'context_size':value},'server',role=role)
                    self.assertEqual(cmd[cmd.index('-c')+1],str(value))
        for value in (True,0,8193,32769,4096.5,None):
            with self.assertRaises(ValueError):validate_context(value)

    def test_context_persistence_and_working_lock(self):
        with tempfile.TemporaryDirectory() as tmp,patch('path_utils.get_project_root',return_value=Path(tmp)), \
             patch('model_selection.get_project_root',return_value=Path(tmp)),patch.object(ModelSelectionPanel,'start_scan'):
            panel=ModelSelectionPanel()
            self.assertEqual(panel.values()['context_size'],8192)
            panel.context.setCurrentIndex(panel.context.findData(32768))
            restored=ModelSelectionPanel()
            self.assertEqual(restored.context.currentData(),32768)
            panel.set_working(True);self.assertFalse(panel.context.isEnabled())
            panel.set_working(False);self.assertTrue(panel.context.isEnabled())
            panel.close();restored.close()

    def test_context_change_restarts_owned_service_but_same_context_reuses(self):
        with tempfile.TemporaryDirectory() as tmp,patch('model_runtime.get_project_root',return_value=Path(tmp)), \
             patch('model_runtime.detect_engine_devices',return_value=[{'id':'CUDA0','name':'test'}]), \
             patch('model_runtime.port_in_use',return_value=False),patch('model_runtime.find_server',return_value='server'), \
             patch('model_runtime.server_command',return_value=['server','--port','8080']), \
             patch('model_runtime.subprocess.Popen') as popen,patch('model_runtime.LocalModelClient'),patch('model_runtime.check_cpu_ram'):
            popen.return_value.poll.return_value=None
            runtime=ModelRuntime();settings={'llm_path':'model.gguf','model_mode':'llm_only'}
            runtime.ensure_ready(settings);runtime.ensure_ready(settings)
            self.assertEqual(popen.call_count,1)
            runtime.ensure_ready({**settings,'context_size':16384})
            self.assertEqual(popen.call_count,2)
            runtime.stop()

if __name__=='__main__':unittest.main()
