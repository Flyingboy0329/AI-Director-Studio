import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_gui import MidnightDashboardWindow


class LogCategoryTests(unittest.TestCase):
    def test_categories_and_errors_keep_requested_colors(self):
        for message,color in (("[Faster-Whisper] 選型完成：small",'#00F5D4'),
                              ("✅ [Faster-Whisper] 轉錄完成",'#00F5D4'),
                              ("[顯存預算] CUDA0",'#C084FC'),
                              ("[分層規劃] 分配",'#FB923C'),
                              ("[Faster-Whisper] failed：錯誤",'#FF758F'),
                              ("[分層規劃] ⚠ 警告",'#FBBF24')):
            with self.subTest(message=message):
                window=SimpleNamespace(txt_log=Mock())
                MidnightDashboardWindow.append_log(window,message)
                self.assertIn(color,window.txt_log.append.call_args.args[0])


if __name__=='__main__':unittest.main()
