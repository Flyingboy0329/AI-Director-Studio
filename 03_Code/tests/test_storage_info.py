import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage_inventory import storage_inventory, storage_text
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette
from app_gui import MidnightDashboardWindow, InfoTextDialog, MIDNIGHT_QSS
from model_selection import ModelSelectionPanel


class StorageInfoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_inventory_includes_removable_deduplicates_and_skips_unreadable(self):
        partitions=[NS(mountpoint=mount,device=mount,fstype=fs,opts=opts) for mount,fs,opts in
                    [("C:/","NTFS","fixed"),("U:/","exFAT","removable"),("U:/","exFAT","rw"),
                     ("Z:/","NTFS","rw"),("D:/","","cdrom")]]
        def usage(mount):
            if mount=="Z:/":raise PermissionError()
            return NS(total=100*1024**3,free=40*1024**3,percent=60)
        with patch('storage_inventory.psutil.disk_partitions',return_value=partitions),patch('storage_inventory.psutil.disk_usage',side_effect=usage):
            disks=storage_inventory()
        self.assertEqual([d['mount'] for d in disks],["C:/","U:/"])
        self.assertIn("exFAT",storage_text(disks))
        self.assertIn("未偵測",storage_text([]))

    def test_shared_information_window_is_dark_readonly_and_nonmodal(self):
        dialog=InfoTextDialog("test","original")
        dialog.show();self.app.processEvents()
        self.assertTrue(dialog.body.isReadOnly())
        self.assertFalse(dialog.isModal())
        self.assertEqual(dialog.body.palette().color(QPalette.ColorRole.Base).name(),"#090a12")
        self.assertEqual(dialog.body.palette().color(QPalette.ColorRole.Text).name(),"#e2e8f0")
        dialog.set_text("new content")
        self.assertEqual(dialog.body.toPlainText(),"new content")
        dialog.close()

    def test_three_fixed_cards_leave_missing_slots_empty_and_details_show_all(self):
        with patch.object(MidnightDashboardWindow,'start_telemetry'),patch.object(ModelSelectionPanel,'start_scan'):
            window=MidnightDashboardWindow()
            for count in (0,1,6,2,0):
                disks=[(f"{chr(67+i)}:/",100,40,60) for i in range(count)]
                window.update_storage({"disks":disks})
                self.assertEqual(len(window.disk_tiles),3)
                for index,tile in enumerate(window.disk_tiles):
                    self.assertEqual(bool(tile.lbl_name.text()),index<count)
                    self.assertEqual(tile.bar.isHidden(),index>=count)
                window.show_disk_details()
                self.assertTrue(window.disk_dialog.body.isReadOnly())
                if count:self.assertIn(f"{count} 個",window.disk_dialog.body.toPlainText())
            window.update_storage({"disks":[("E:/",100,40,60),("F:/",100,40,60)]})
            self.assertEqual([tile.lbl_name.text() for tile in window.disk_tiles],["","","E:/"])
            self.assertIn("F:/",window.disk_dialog.body.toPlainText())
            window.show_sampling_help()
            self.assertIsInstance(window.sampling_dialog,InfoTextDialog)
            self.assertIn("8192",window.sampling_dialog.body.toPlainText())
            window.close()

if __name__=='__main__':unittest.main()
