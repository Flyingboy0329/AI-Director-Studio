import sys
import time
import queue
import traceback
from pathlib import Path
from datetime import datetime

import psutil
import torch
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QFileDialog, QFrame, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent
LOG_FILE = PROJECT_ROOT / "05_Output" / "logs" / "gui_error.log"

def excepthook(exc_type, exc_value, exc_tb):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n=== AI Director GUI error @ {datetime.now().isoformat()} ===\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    finally:
        sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = excepthook
sys.path.insert(0, str(CODE_DIR))
sys.path.append(str(CODE_DIR / "bridge"))

from main import run_main_pipeline
from watch_folder import wait_for_file_ready, SUPPORTED_EXT
from auto_injector import check_resolve_running

APP_QSS = """
* { font-family: "Segoe UI", "Microsoft JhengHei UI", sans-serif; font-size: 13px; }
QMainWindow, QWidget#Root { background: #101317; color: #E8EDF2; }
QFrame#TopBar { background: #171B21; border-bottom: 1px solid #2B323B; }
QLabel#Brand { color: #F3F6F9; font-size: 19px; font-weight: 800; letter-spacing: 1px; }
QLabel#BrandAccent { color: #56D6C2; font-size: 19px; font-weight: 800; }
QLabel#Version { color: #8C98A5; background: #222831; border: 1px solid #343D48; border-radius: 5px; padding: 4px 7px; font-size: 10px; font-weight: 700; }
QLabel#Eyebrow { color: #84919F; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }
QLabel#SectionTitle { color: #F1F4F7; font-size: 14px; font-weight: 700; }
QLabel#Muted { color: #8793A0; }
QFrame#Panel { background: #171B21; border: 1px solid #2A313A; border-radius: 10px; }
QFrame#MetricPanel { background: #14191E; border: 1px solid #28333A; border-radius: 9px; }
QLabel#MetricName { color: #84919F; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#MetricValue { color: #F3F6F9; font-family: "Consolas", monospace; font-size: 13px; font-weight: 700; }
QLabel#StatusPill { background: #20262D; color: #B5C0CA; border: 1px solid #343D46; border-radius: 6px; padding: 6px 9px; font-size: 10px; font-weight: 800; }
QLabel#StatusPill[status="online"] { background: #142B28; color: #69E0C8; border: 1px solid #28584F; }
QLabel#StatusPill[status="offline"] { background: #2B2024; color: #F09AA5; border: 1px solid #5C343D; }
QLineEdit { background: #0F1216; color: #E8EDF2; border: 1px solid #343D47; border-radius: 7px; padding: 10px 11px; selection-background-color: #287E76; }
QLineEdit:focus { border: 1px solid #56D6C2; }
QPushButton { background: #242B33; color: #DDE5EB; border: 1px solid #39434E; border-radius: 7px; padding: 9px 13px; font-weight: 650; }
QPushButton:hover { background: #2D3741; border-color: #52616F; }
QPushButton:disabled { color: #65717D; background: #1A1F25; border-color: #2A3038; }
QPushButton#PrimaryButton { background: #56D6C2; color: #0B1716; border: 1px solid #75E7D5; padding: 11px 18px; font-weight: 800; }
QPushButton#PrimaryButton:hover { background: #77E4D3; }
QPushButton#DangerButton { background: #B83F50; color: white; border: 1px solid #D75A6A; padding: 11px 18px; font-weight: 800; }
QPushButton#DangerButton:hover { background: #CF4A5D; }
QProgressBar { background: #0D1014; border: 1px solid #303943; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #56D6C2; border-radius: 3px; }
QTextEdit#LogView { background: #0D1014; color: #B7C5CF; border: 1px solid #2A323B; border-radius: 8px; padding: 8px; selection-background-color: #285E59; font-family: "Consolas", "Microsoft JhengHei UI", monospace; font-size: 11px; }
QFrame#Footer { background: #0D1014; border-top: 1px solid #252C34; }
"""

class TelemetryThread(QThread):
    telemetry_signal = pyqtSignal(str, str, str, bool)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        while self.running:
            try:
                mem = psutil.virtual_memory()
                ram = f"{mem.used / 1024**3:.1f} / {mem.total / 1024**3:.1f} GB · {mem.percent}%"
                g0, g1 = "Not detected", "Not detected"
                if torch.cuda.is_available():
                    count = torch.cuda.device_count()
                    if count >= 1:
                        used = torch.cuda.memory_allocated(0) / 1024**3
                        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                        name = torch.cuda.get_device_name(0).replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
                        g0 = f"{name} · {used:.1f}/{total:.1f} GB"
                    if count >= 2:
                        used = torch.cuda.memory_allocated(1) / 1024**3
                        total = torch.cuda.get_device_properties(1).total_memory / 1024**3
                        name = torch.cuda.get_device_name(1).replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
                        g1 = f"{name} · {used:.1f}/{total:.1f} GB"
                resolve_on, _ = check_resolve_running()
                self.telemetry_signal.emit(ram, g0, g1, resolve_on)
            except Exception:
                pass
            for _ in range(20):
                if not self.running:
                    break
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait(2500)


class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    status_signal = pyqtSignal(str, str)
    queue_signal = pyqtSignal(int)
    done_signal = pyqtSignal()

    def __init__(self, watch_dir, prompt_text):
        super().__init__()
        self.watch_dir = Path(watch_dir)
        self.prompt_text = prompt_text
        self.watching = True
        self.task_queue = queue.Queue()
        self.processed = set()

    def run(self):
        try:
            self.watch_dir.mkdir(parents=True, exist_ok=True)
            for f in self.watch_dir.glob("*"):
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXT:
                    self.processed.add(f.resolve())
            self.log_signal.emit("監聽已啟動：新素材將自動加入處理佇列。")
            self.status_signal.emit("監聽中 · 等待新素材", "#56D6C2")

            while self.watching:
                try:
                    for f in self.watch_dir.glob("*"):
                        if f.is_file() and f.suffix.lower() in SUPPORTED_EXT:
                            rf = f.resolve()
                            if rf not in self.processed:
                                self.processed.add(rf)
                                self.task_queue.put(rf)
                                self.queue_signal.emit(self.task_queue.qsize())
                                self.log_signal.emit(f"已加入佇列 · {f.name}")

                    if not self.task_queue.empty():
                        target = self.task_queue.get()
                        self.queue_signal.emit(self.task_queue.qsize())
                        self.log_signal.emit(f"開始分析 · {target.name}")
                        self.status_signal.emit(f"正在分析 · {target.name}", "#E6C779")
                        self.progress_signal.emit(10, "等待檔案寫入完成")
                        wait_for_file_ready(target)
                        if not self.watching:
                            self.task_queue.task_done()
                            break
                        self.progress_signal.emit(45, "執行語音與視覺分析")
                        ok = run_main_pipeline(str(target), context_prompt=self.prompt_text)
                        if ok:
                            self.progress_signal.emit(100, "分析與標記注入完成")
                            self.log_signal.emit(f"完成 · {target.name}")
                        else:
                            self.progress_signal.emit(0, "處理失敗")
                            self.log_signal.emit(f"失敗 · {target.name} · 請檢查管線日誌")
                        self.task_queue.task_done()
                        self.queue_signal.emit(self.task_queue.qsize())
                        time.sleep(0.8)
                        self.progress_signal.emit(0, "等待下一份素材")
                        self.status_signal.emit("監聽中 · 等待新素材", "#56D6C2")
                    time.sleep(0.8)
                except Exception as exc:
                    self.log_signal.emit(f"工作階段錯誤 · {exc}")
                    time.sleep(1.5)
        except Exception as exc:
            self.log_signal.emit(f"監聽器無法啟動 · {exc}")
        finally:
            self.done_signal.emit()

    def stop(self):
        self.watching = False
        self.wait(5000)


class AIDirectorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Director Studio")
        self.resize(1060, 820)
        self.setMinimumSize(900, 720)
        self.watch_dir = str((PROJECT_ROOT / "02_Data").resolve())
        self.worker = None
        self._build_ui()
        self._start_telemetry()
        self._log("AI Director Studio 已就緒。")

    def panel(self, name="Panel"):
        frame = QFrame()
        frame.setObjectName(name)
        return frame

    def metric(self, title, value):
        frame = self.panel("MetricPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        name = QLabel(title)
        name.setObjectName("MetricName")
        val = QLabel(value)
        val.setObjectName("MetricValue")
        val.setWordWrap(True)
        layout.addWidget(name)
        layout.addWidget(val)
        return frame, val

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = self.panel("TopBar")
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 16, 24, 16)
        brand = QLabel("AI DIRECTOR")
        brand.setObjectName("Brand")
        accent = QLabel("STUDIO")
        accent.setObjectName("BrandAccent")
        version = QLabel("LOCAL WORKFLOW  /  v1.1")
        version.setObjectName("Version")
        h.addWidget(brand)
        h.addSpacing(6)
        h.addWidget(accent)
        h.addSpacing(12)
        h.addWidget(version)
        h.addStretch()
        self.badge_resolve = QLabel("RESOLVE · CHECKING")
        self.badge_resolve.setObjectName("StatusPill")
        self.badge_resolve.setProperty("status", "offline")
        self.badge_guard = QLabel("WATCHER · IDLE")
        self.badge_guard.setObjectName("StatusPill")
        self.badge_guard.setProperty("status", "offline")
        h.addWidget(self.badge_resolve)
        h.addSpacing(8)
        h.addWidget(self.badge_guard)
        outer.addWidget(header)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 19, 24, 15)
        body.setSpacing(13)

        intro = QVBoxLayout()
        eyebrow = QLabel("MEDIA INTELLIGENCE  /  LOCAL INFERENCE")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("素材分析工作站")
        title.setStyleSheet("font-size: 25px; font-weight: 800; color: #F3F6F9;")
        subtitle = QLabel("監聽資料夾、分析影音特徵，並將決策標記送入 DaVinci Resolve。")
        subtitle.setObjectName("Muted")
        intro.addWidget(eyebrow)
        intro.addWidget(title)
        intro.addWidget(subtitle)
        body.addLayout(intro)

        telemetry = self.panel()
        tl = QVBoxLayout(telemetry)
        tl.setContentsMargins(15, 13, 15, 14)
        top = QHBoxLayout()
        section = QLabel("系統狀態")
        section.setObjectName("SectionTitle")
        live = QLabel("● LIVE TELEMETRY")
        live.setStyleSheet("color: #56D6C2; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        top.addWidget(section)
        top.addStretch()
        top.addWidget(live)
        tl.addLayout(top)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.lbl_ram = self.metric("SYSTEM MEMORY", "讀取中…")
        self.lbl_gpu0 = self.metric("GPU 0", "讀取中…")
        self.lbl_gpu1 = self.metric("GPU 1", "讀取中…")
        grid.addWidget(self.lbl_ram[0], 0, 0)
        grid.addWidget(self.lbl_gpu0[0], 0, 1)
        grid.addWidget(self.lbl_gpu1[0], 0, 2)
        tl.addLayout(grid)
        body.addWidget(telemetry)

        config = QHBoxLayout()
        config.setSpacing(13)

        context = self.panel()
        cp = QVBoxLayout(context)
        cp.setContentsMargins(15, 14, 15, 15)
        title_row = QHBoxLayout()
        ct = QLabel("分析情境")
        ct.setObjectName("SectionTitle")
        tag = QLabel("CONTEXT")
        tag.setObjectName("Eyebrow")
        title_row.addWidget(ct)
        title_row.addStretch()
        title_row.addWidget(tag)
        cp.addLayout(title_row)
        cp.addWidget(QLabel("提供素材背景、專有名詞與分析重點。"))
        self.edit_prompt = QLineEdit("日常生活旅遊 Vlog，包含遊戲術語、飯店電器開箱、日本地名與生活閒聊。")
        cp.addWidget(self.edit_prompt)
        config.addWidget(context, 1)

        folder = self.panel()
        fp = QVBoxLayout(folder)
        fp.setContentsMargins(15, 14, 15, 15)
        title_row2 = QHBoxLayout()
        ft = QLabel("素材收件匣")
        ft.setObjectName("SectionTitle")
        tag2 = QLabel("WATCH FOLDER")
        tag2.setObjectName("Eyebrow")
        title_row2.addWidget(ft)
        title_row2.addStretch()
        title_row2.addWidget(tag2)
        fp.addLayout(title_row2)
        fp.addWidget(QLabel("新影片放入此資料夾後，自動排入分析佇列。"))
        path_row = QHBoxLayout()
        self.edit_path = QLineEdit(self.watch_dir)
        self.edit_path.setMinimumWidth(80)
        self.edit_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        browse = QPushButton("選擇資料夾")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.edit_path, 1)
        path_row.addWidget(browse)
        fp.addLayout(path_row)
        config.addWidget(folder, 1)
        body.addLayout(config)

        control = self.panel()
        cl = QVBoxLayout(control)
        cl.setContentsMargins(15, 14, 15, 15)
        cl.setSpacing(10)
        ctl_head = QHBoxLayout()
        ctl_titles = QVBoxLayout()
        ct = QLabel("自動分析任務")
        ct.setObjectName("SectionTitle")
        sub = QLabel("啟動後持續監聽資料夾，每次處理一份素材。")
        sub.setObjectName("Muted")
        ctl_titles.addWidget(ct)
        ctl_titles.addWidget(sub)
        ctl_head.addLayout(ctl_titles)
        ctl_head.addStretch()
        self.lbl_task_info = QLabel("待命中 · 尚未開始監聽")
        self.lbl_task_info.setStyleSheet("color: #A9B4BE; font-weight: 700;")
        ctl_head.addWidget(self.lbl_task_info)
        cl.addLayout(ctl_head)
        self.prog = QProgressBar()
        self.prog.setValue(0)
        self.prog.setTextVisible(False)
        cl.addWidget(self.prog)
        statusrow = QHBoxLayout()
        self.lbl_prog = QLabel("準備就緒")
        self.lbl_prog.setObjectName("Muted")
        self.lbl_queue = QLabel("佇列  0")
        self.lbl_queue.setStyleSheet("color: #E6C779; font-weight: 700;")
        self.lbl_pct = QLabel("0%")
        self.lbl_pct.setStyleSheet("color: #56D6C2; font-family: Consolas; font-weight: 800;")
        statusrow.addWidget(self.lbl_prog)
        statusrow.addStretch()
        statusrow.addWidget(self.lbl_queue)
        statusrow.addSpacing(18)
        statusrow.addWidget(self.lbl_pct)
        cl.addLayout(statusrow)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_toggle = QPushButton("啟動自動監聽")
        self.btn_toggle.setObjectName("PrimaryButton")
        self.btn_toggle.setMinimumWidth(185)
        self.btn_toggle.clicked.connect(self._toggle)
        buttons.addWidget(self.btn_toggle)
        cl.addLayout(buttons)
        body.addWidget(control)

        logs = self.panel()
        ll = QVBoxLayout(logs)
        ll.setContentsMargins(13, 11, 13, 12)
        head = QHBoxLayout()
        logtitle = QLabel("執行紀錄")
        logtitle.setObjectName("SectionTitle")
        logtag = QLabel("LIVE EVENT LOG")
        logtag.setObjectName("Eyebrow")
        head.addWidget(logtitle)
        head.addStretch()
        head.addWidget(logtag)
        ll.addLayout(head)
        self.txt_log = QTextEdit()
        self.txt_log.setObjectName("LogView")
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(105)
        ll.addWidget(self.txt_log, 1)
        body.addWidget(logs, 1)
        outer.addWidget(content, 1)

        footer = self.panel("Footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 9, 24, 9)
        left = QLabel("AI DIRECTOR STUDIO  ·  HUMAN-IN-THE-LOOP EDITING")
        left.setStyleSheet("color: #7D8995; font-size: 10px; font-weight: 700; letter-spacing: 0.7px;")
        right = QLabel("Developed by Pan Bo-Han")
        right.setStyleSheet("color: #65717D; font-size: 10px;")
        fl.addWidget(left)
        fl.addStretch()
        fl.addWidget(right)
        outer.addWidget(footer)

    def _log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f'<span style="color:#667582">{ts}</span>  {message}')
        self.txt_log.moveCursor(QTextCursor.MoveOperation.End)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇素材收件匣", self.edit_path.text())
        if folder:
            self.edit_path.setText(folder)
            self._log(f"監聽目錄已設定：{folder}")

    def _start_telemetry(self):
        self.telemetry = TelemetryThread()
        self.telemetry.telemetry_signal.connect(self._update_telemetry)
        self.telemetry.start()

    def _update_telemetry(self, ram, gpu0, gpu1, resolve_on):
        self.lbl_ram[1].setText(ram)
        self.lbl_gpu0[1].setText(gpu0)
        self.lbl_gpu1[1].setText(gpu1)
        self.badge_resolve.setText("RESOLVE · ONLINE" if resolve_on else "RESOLVE · OFFLINE")
        self.badge_resolve.setProperty("status", "online" if resolve_on else "offline")
        self.badge_resolve.style().unpolish(self.badge_resolve)
        self.badge_resolve.style().polish(self.badge_resolve)

    def _toggle(self):
        if self.worker and self.worker.isRunning():
            self._stop_worker()
            return
        folder = Path(self.edit_path.text().strip())
        if not folder.exists() or not folder.is_dir():
            self._log("無法啟動：請先選擇有效的素材資料夾。")
            return
        self.worker = WorkerThread(str(folder), self.edit_prompt.text().strip())
        self.worker.log_signal.connect(self._log)
        self.worker.progress_signal.connect(self._progress)
        self.worker.status_signal.connect(self._task_status)
        self.worker.queue_signal.connect(self._queue)
        self.worker.done_signal.connect(self._worker_done)
        self.worker.start()
        self.btn_toggle.setText("停止自動監聽")
        self.btn_toggle.setObjectName("DangerButton")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        self.badge_guard.setText("WATCHER · ACTIVE")
        self.badge_guard.setProperty("status", "online")
        self.badge_guard.style().unpolish(self.badge_guard)
        self.badge_guard.style().polish(self.badge_guard)

    def _stop_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        self.worker = None
        self.btn_toggle.setText("啟動自動監聽")
        self.btn_toggle.setObjectName("PrimaryButton")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        self.badge_guard.setText("WATCHER · IDLE")
        self.badge_guard.setProperty("status", "offline")
        self.badge_guard.style().unpolish(self.badge_guard)
        self.badge_guard.style().polish(self.badge_guard)
        self.lbl_task_info.setText("待命中 · 監聽已停止")
        self._progress(0, "待命中")

    def _worker_done(self):
        if self.worker and not self.worker.isRunning():
            self.worker = None
        self.btn_toggle.setText("啟動自動監聽")
        self.btn_toggle.setObjectName("PrimaryButton")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        self.badge_guard.setText("WATCHER · IDLE")
        self.badge_guard.setProperty("status", "offline")
        self.badge_guard.style().unpolish(self.badge_guard)
        self.badge_guard.style().polish(self.badge_guard)

    def _progress(self, value, text):
        self.prog.setValue(value)
        self.lbl_pct.setText(f"{value}%")
        self.lbl_prog.setText(text)

    def _task_status(self, text, color):
        self.lbl_task_info.setText(text)
        self.lbl_task_info.setStyleSheet(f"color: {color}; font-weight: 700;")

    def _queue(self, count):
        self.lbl_queue.setText(f"佇列  {count}")

    def closeEvent(self, event):
        if hasattr(self, "telemetry") and self.telemetry.isRunning():
            self.telemetry.stop()
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    app.setFont(QFont("Segoe UI", 10))
    window = AIDirectorWindow()
    window.show()
    sys.exit(app.exec())
