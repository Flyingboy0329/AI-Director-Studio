import os,sys,unittest
from pathlib import Path
from unittest.mock import patch,Mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication,QMessageBox
import app_gui

class StartupPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_decline_does_not_relaunch(self):
        with patch.object(app_gui.sys,'platform','win32'),patch.object(app_gui.ctypes,'windll',create=True) as dll,patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):
            dll.shell32.IsUserAnAdmin.return_value=False
            self.assertFalse(app_gui.offer_temperature_elevation())
            dll.shell32.ShellExecuteW.assert_not_called()

    def test_accepted_relaunch_and_cancel(self):
        with patch.object(app_gui.sys,'platform','win32'),patch.object(app_gui.ctypes,'windll',create=True) as dll,patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(QMessageBox,'information') as info:
            dll.shell32.IsUserAnAdmin.return_value=False
            dll.shell32.ShellExecuteW.return_value=33
            self.assertTrue(app_gui.offer_temperature_elevation())
            self.assertEqual(dll.shell32.ShellExecuteW.call_args.args[1],'runas')
            dll.shell32.ShellExecuteW.return_value=5
            self.assertFalse(app_gui.offer_temperature_elevation())
            info.assert_called_once()

    def test_admin_skips_prompt(self):
        with patch.object(app_gui.sys,'platform','win32'),patch.object(app_gui.ctypes,'windll',create=True) as dll,patch.object(QMessageBox,'question') as question:
            dll.shell32.IsUserAnAdmin.return_value=True
            self.assertFalse(app_gui.offer_temperature_elevation())
            question.assert_not_called()

if __name__=='__main__':unittest.main()
