import sys
import os
import time
import queue
import traceback
import subprocess
import ctypes
import json
import io
import psutil
import torch
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QFileDialog, QFrame, QSizePolicy, QDialog, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QConicalGradient, QLinearGradient, QIcon, QPixmap, QPolygonF, QTextCursor

# 設置 Windows App User Model ID
try:
    myappid = 'pandirector.aidirectorstudio.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

NVML_AVAILABLE = False
try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except Exception:
    NVML_AVAILABLE = False

LOG_FILE = Path(__file__).resolve().parent.parent / "05_Output" / "logs" / "gui_error.log"
def excepthook(exc_type, exc_value, exc_tb):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== Midnight Neon GUI 異常日誌 ===\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    sys.__excepthook__(exc_type, exc_value, exc_tb)
sys.excepthook = excepthook

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "01_Project" / "user_config.json"

sys.path.insert(0, str(CODE_DIR))
sys.path.append(str(CODE_DIR / "bridge"))

from main import run_main_pipeline
from watch_folder import wait_for_file_ready, SUPPORTED_EXT
from auto_injector import check_resolve_running

# 讀取並持久化使用者偏好路徑
def load_saved_watch_dir():
    default_dir = str((PROJECT_ROOT / "02_Data").resolve())
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_path = data.get("watch_dir", "")
                if saved_path and os.path.exists(saved_path):
                    return saved_path
        except Exception:
            pass
    return default_dir

def save_watch_dir_to_config(path_str):
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception:
                pass
        config_data["watch_dir"] = path_str
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_gpu_telemetry_fallback():
    gpu_data = []
    try:
        cmd = "nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"
        out = subprocess.check_output(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW).decode()
        for line in out.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[0].isdigit():
                u_mb, t_mb, temp = float(parts[0]), float(parts[1]), int(parts[2])
                gpu_data.append((u_mb / 1024.0, t_mb / 1024.0, (u_mb / t_mb) * 100.0, temp))
    except Exception:
        pass
    return gpu_data

def create_app_icon():
    ico_path = PROJECT_ROOT / "01_Project" / "app_icon.ico"
    if ico_path.exists():
        return QIcon(str(ico_path))

    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(4, 4, 120, 120)
    bg_grad = QLinearGradient(0, 0, 128, 128)
    bg_grad.setColorAt(0.0, QColor("#121424"))
    bg_grad.setColorAt(1.0, QColor("#090A12"))
    painter.setPen(QPen(QColor("#7928CA"), 3))
    painter.setBrush(QBrush(bg_grad))
    painter.drawRoundedRect(rect, 24, 24)

    bolt = QPolygonF([
        QPointF(68, 18),
        QPointF(38, 66),
        QPointF(60, 66),
        QPointF(54, 110),
        QPointF(92, 54),
        QPointF(70, 54)
    ])
    bolt_grad = QLinearGradient(38, 18, 92, 110)
    bolt_grad.setColorAt(0.0, QColor("#00F5D4"))
    bolt_grad.setColorAt(0.6, QColor("#FF007F"))
    bolt_grad.setColorAt(1.0, QColor("#7928CA"))
    
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(bolt_grad))
    painter.drawPolygon(bolt)
    painter.end()

    return QIcon(pixmap)

def enable_windows_dark_titlebar(hwnd):
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        val = ctypes.c_int(1)
        set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
            val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

class EmittingStream(io.StringIO):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def write(self, text):
        if text and text.strip():
            self.callback(text.strip())

    def flush(self):
        pass

# ===== 1. 圓形進度環 =====
class RingMeter(QWidget):
    def __init__(self, title="CPU", unit="%", start_color="#00F5D4", end_color="#7928CA", size=115):
        super().__init__()
        self.title = title
        self.unit = unit
        self.start_color = QColor(start_color)
        self.end_color = QColor(end_color)
        self.percent = 0
        self.value_text = "0%"
        self.setFixedSize(size, size)

    def set_data(self, percent, value_text=""):
        self.percent = max(0, min(100, percent))
        self.value_text = value_text if value_text else f"{int(self.percent)}%"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        thickness = 8
        margin = thickness / 2.0 + 3
        rect = QRectF(margin, margin, w - margin*2, h - margin*2)

        bg_pen = QPen(QColor("#1A1D2E"), thickness)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self.percent > 0:
            grad = QConicalGradient(rect.center(), -90)
            grad.setColorAt(0.0, self.start_color)
            grad.setColorAt(0.5, self.end_color)
            grad.setColorAt(1.0, self.start_color)
            prog_pen = QPen(QBrush(grad), thickness)
            prog_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(prog_pen)
            span_angle = int(- (self.percent / 100.0) * 360 * 16)
            painter.drawArc(rect, 90 * 16, span_angle)

        painter.setPen(QColor("#8C9BAE"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(0, h * 0.18, w, 16), Qt.AlignmentFlag.AlignCenter, self.title)

        painter.setPen(QColor("#F0F6FC"))
        painter.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(0, h * 0.36, w, 22), Qt.AlignmentFlag.AlignCenter, f"{int(self.percent)}%")

        painter.setPen(QColor("#56D6C2"))
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(QRectF(0, h * 0.60, w, 16), Qt.AlignmentFlag.AlignCenter, self.value_text)
        painter.end()

# ===== 2. 方形水缸蓄水池 =====
class RamTankMeter(QWidget):
    def __init__(self, title="RAM TANK", width=130, height=115):
        super().__init__()
        self.title = title
        self.setFixedSize(width, height)
        self.percent = 0
        self.val_str = "0 / 0 GB"

    def set_data(self, percent, val_str):
        self.percent = max(0, min(100, percent))
        self.val_str = val_str
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        tank_rect = QRectF(6, 6, w - 12, h - 12)
        painter.setPen(QPen(QColor("#232742"), 2))
        painter.setBrush(QColor("#0A0B14"))
        painter.drawRoundedRect(tank_rect, 7, 7)

        painter.setPen(QPen(QColor("#3A4066"), 1, Qt.PenStyle.DashLine))
        y_75 = tank_rect.bottom() - (tank_rect.height() * 0.75)
        painter.drawLine(int(tank_rect.left() + 4), int(y_75), int(tank_rect.right() - 4), int(y_75))

        fill_h = (self.percent / 100.0) * (tank_rect.height() - 4)
        if fill_h > 0:
            water_rect = QRectF(tank_rect.left() + 2, tank_rect.bottom() - fill_h - 2, tank_rect.width() - 4, fill_h)
            grad = QLinearGradient(water_rect.bottomLeft(), water_rect.topLeft())
            if self.percent >= 85:
                grad.setColorAt(0.0, QColor("#E11D48"))
                grad.setColorAt(1.0, QColor("#FF007F"))
            elif self.percent >= 70:
                grad.setColorAt(0.0, QColor("#7928CA"))
                grad.setColorAt(1.0, QColor("#C084FC"))
            else:
                grad.setColorAt(0.0, QColor("#0077B6"))
                grad.setColorAt(1.0, QColor("#00F5D4"))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(water_rect, 5, 5)

        painter.setPen(QColor("#F0F6FC"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(6, 12, w - 12, 16), Qt.AlignmentFlag.AlignCenter, self.title)

        status_text = "CRITICAL" if self.percent >= 85 else ("WARNING" if self.percent >= 70 else f"{int(self.percent)}%")
        painter.setPen(QColor("#FFFFFF") if self.percent < 85 else QColor("#FFD166"))
        painter.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        painter.drawText(QRectF(6, 40, w - 12, 22), Qt.AlignmentFlag.AlignCenter, status_text)

        painter.setPen(QColor("#E2E8F0"))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(QRectF(6, 70, w - 12, 16), Qt.AlignmentFlag.AlignCenter, self.val_str)
        painter.end()

# ===== 3. 全色溫動態水銀溫度計 =====
class ThermoMeter(QWidget):
    def __init__(self, width=34, height=115):
        super().__init__()
        self.setFixedSize(width, height)
        self.temp_val = 30

    def set_temp(self, temp):
        if temp > 0:
            self.temp_val = max(10, min(105, temp))
        self.update()

    def get_color(self, t):
        if t <= 42:
            return QColor("#10B981")
        elif t <= 58:
            return QColor("#FBBF24")
        elif t <= 75:
            return QColor("#F97316")
        else:
            return QColor("#EF4444")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        tube_w = 7
        tube_x = (w - tube_w) / 2
        tube_h = h - 28
        tube_rect = QRectF(tube_x, 8, tube_w, tube_h)
        bulb_rect = QRectF((w - 16) / 2, h - 24, 16, 16)

        painter.setPen(QPen(QColor("#232742"), 1.5))
        painter.setBrush(QColor("#0A0B14"))
        painter.drawRoundedRect(tube_rect, 4, 4)
        painter.drawEllipse(bulb_rect)

        ratio = max(0.05, min(1.0, (self.temp_val - 25) / 70.0))
        fill_h = ratio * (tube_h - 4)
        col = self.get_color(self.temp_val)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(col)
        painter.drawEllipse(QRectF(bulb_rect.left() + 2, bulb_rect.top() + 2, bulb_rect.width() - 4, bulb_rect.height() - 4))
        if fill_h > 0:
            painter.drawRect(QRectF(tube_x + 1.5, tube_rect.bottom() - fill_h - 2, tube_w - 3, fill_h))

        painter.setPen(col)
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(0, h - 10, w, 11), Qt.AlignmentFlag.AlignCenter, f"{int(self.temp_val)}°C")
        painter.end()

# ===== 4. 本機硬碟磁貼小卡片 =====
class DiskTile(QFrame):
    def __init__(self, drive_letter="C:"):
        super().__init__()
        self.drive_letter = drive_letter
        self.setStyleSheet("""
            QFrame {
                background-color: #0E101A;
                border: 1px solid #1C2035;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        l = QVBoxLayout(self)
        l.setContentsMargins(6, 6, 6, 6)
        l.setSpacing(3)

        top_h = QHBoxLayout()
        self.lbl_name = QLabel(f"磁碟 ({drive_letter})")
        self.lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #E2E8F0;")
        top_h.addWidget(self.lbl_name)
        top_h.addStretch()
        l.addLayout(top_h)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("QProgressBar { background: #1A1D2E; border: none; border-radius: 3px; } QProgressBar::chunk { background: #00B4D8; border-radius: 3px; }")
        l.addWidget(self.bar)

        self.lbl_info = QLabel("讀取中...")
        self.lbl_info.setStyleSheet("font-family: 'Segoe UI'; font-size: 9px; color: #8C9BAE;")
        l.addWidget(self.lbl_info)

    def update_disk(self, total_gb, free_gb, percent):
        self.bar.setValue(int(percent))
        if percent >= 90:
            self.bar.setStyleSheet("QProgressBar { background: #1A1D2E; border: none; border-radius: 3px; } QProgressBar::chunk { background: #EF4444; border-radius: 3px; }")
        else:
            self.bar.setStyleSheet("QProgressBar { background: #1A1D2E; border: none; border-radius: 3px; } QProgressBar::chunk { background: #00B4D8; border-radius: 3px; }")
        self.lbl_info.setText(f"剩餘 {int(free_gb)} GB / 共 {int(total_gb)} GB")

# ===== 5. 更多... 彈窗 =====
class DiskDetailDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全機存儲磁碟陣列詳情")
        self.resize(520, 260)
        self.setStyleSheet("""
            QDialog { background-color: #0E101E; color: #F0F6FC; }
            QTableWidget { background-color: #121424; border: 1px solid #1F233D; color: #E2E8F0; gridline-color: #1F233D; border-radius: 8px; }
            QHeaderView::section { background-color: #1B1E36; color: #00F5D4; font-weight: bold; border: none; padding: 6px; }
        """)
        l = QVBoxLayout(self)
        table = QTableWidget()
        l.addWidget(table)

        partitions = [p for p in psutil.disk_partitions() if 'fixed' in p.opts or 'rw' in p.opts]
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["掛載槽位", "檔案系統", "總容量", "剩餘空間", "佔用率"])
        table.setRowCount(len(partitions))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for i, part in enumerate(partitions):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                tot = f"{usage.total / (1024**3):.1f} GB"
                free = f"{usage.free / (1024**3):.1f} GB"
                pct = f"{usage.percent}%"
                table.setItem(i, 0, QTableWidgetItem(part.device))
                table.setItem(i, 1, QTableWidgetItem(part.fstype))
                table.setItem(i, 2, QTableWidgetItem(tot))
                table.setItem(i, 3, QTableWidgetItem(free))
                table.setItem(i, 4, QTableWidgetItem(pct))
            except Exception:
                pass

MIDNIGHT_QSS = """
QMainWindow {
    background-color: #0B0C16;
}
QWidget {
    color: #F0F6FC;
    font-family: "Segoe UI", "Microsoft JhengHei UI", sans-serif;
}
QFrame.DashboardCard {
    background-color: #121424;
    border: 1px solid #1F233D;
    border-radius: 14px;
}
QFrame.HeaderCard {
    background-color: #0E101E;
    border-bottom: 1px solid #1C2035;
}
QLineEdit, QTextEdit {
    background-color: #090A12;
    border: 1px solid #232742;
    border-radius: 8px;
    padding: 10px 12px;
    color: #00F5D4;
    font-size: 12px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #7928CA;
    background-color: #0D0E1A;
}
QPushButton.PillBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF007F, stop:1 #7928CA);
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 9px 24px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton.PillBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF3399, stop:1 #9945FF);
}
QPushButton.SubPillBtn {
    background-color: #1C2038;
    color: #00F5D4;
    border: 1px solid #2D3359;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton.SubPillBtn:hover {
    background-color: #2D3359;
    color: #FFFFFF;
}
QPushButton.MoreBtn {
    background-color: transparent;
    color: #00F5D4;
    border: none;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 4px;
}
QPushButton.MoreBtn:hover {
    color: #FF007F;
    text-decoration: underline;
}
QLabel.PillBadge {
    background-color: #1B1E36;
    color: #A0ABC0;
    border: 1px solid #2A2F54;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 10px;
    font-weight: bold;
}
QTextEdit.TerminalLog {
    background-color: #08090F;
    border: 1px solid #1C2035;
    border-radius: 10px;
    color: #E2E8F0;
    font-family: "Consolas", monospace;
    font-size: 11px;
    padding: 10px;
}
"""

class TelemetryThread(QThread):
    telemetry_signal = pyqtSignal(float, int, float, str, float, str, int, float, str, int, list, bool)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        while self.running:
            try:
                cpu_pct = psutil.cpu_percent(interval=None)
                cpu_temp = int(36 + (cpu_pct * 0.45))
                
                mem = psutil.virtual_memory()
                ram_pct = mem.percent
                ram_val = f"{mem.used/(1024**3):.1f}/{mem.total/(1024**3):.1f}G"

                g0_pct, g0_val, g0_temp = 0.0, "0.0/16.0G", 0
                g1_pct, g1_val, g1_temp = 0.0, "0.0/12.0G", 0

                nvml_success = False
                if NVML_AVAILABLE:
                    try:
                        cnt = pynvml.nvmlDeviceGetCount()
                        if cnt >= 1:
                            h0 = pynvml.nvmlDeviceGetHandleByIndex(0)
                            info0 = pynvml.nvmlDeviceGetMemoryInfo(h0)
                            u0_gb = info0.used / (1024**3)
                            t0_gb = info0.total / (1024**3)
                            g0_pct = (info0.used / info0.total) * 100.0
                            g0_val = f"{u0_gb:.1f}/{t0_gb:.1f}G"
                            g0_temp = int(pynvml.nvmlDeviceGetTemperature(h0, pynvml.NVML_TEMPERATURE_GPU))
                        if cnt >= 2:
                            h1 = pynvml.nvmlDeviceGetHandleByIndex(1)
                            info1 = pynvml.nvmlDeviceGetMemoryInfo(h1)
                            u1_gb = info1.used / (1024**3)
                            t1_gb = info1.total / (1024**3)
                            g1_pct = (info1.used / info1.total) * 100.0
                            g1_val = f"{u1_gb:.1f}/{t1_gb:.1f}G"
                            g1_temp = int(pynvml.nvmlDeviceGetTemperature(h1, pynvml.NVML_TEMPERATURE_GPU))
                        nvml_success = True
                    except Exception:
                        nvml_success = False

                if not nvml_success or g0_val == "0.0/16.0G":
                    fb_data = get_gpu_telemetry_fallback()
                    if len(fb_data) >= 1:
                        u0_gb, t0_gb, g0_pct, g0_temp = fb_data[0]
                        g0_val = f"{u0_gb:.1f}/{t0_gb:.1f}G"
                    if len(fb_data) >= 2:
                        u1_gb, t1_gb, g1_pct, g1_temp = fb_data[1]
                        g1_val = f"{u1_gb:.1f}/{t1_gb:.1f}G"

                disks_data = []
                for d in ["C:\\", "D:\\", "E:\\"]:
                    try:
                        u = psutil.disk_usage(d)
                        disks_data.append((d[0], u.total/(1024**3), u.free/(1024**3), u.percent))
                    except Exception:
                        pass

                resolve_on, _ = check_resolve_running()
                self.telemetry_signal.emit(cpu_pct, cpu_temp, ram_pct, ram_val, g0_pct, g0_val, g0_temp, g1_pct, g1_val, g1_temp, disks_data, resolve_on)
            except Exception:
                pass
            time.sleep(1.5)

    def stop(self):
        self.running = False
        self.wait()

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    queue_signal = pyqtSignal(int)

    def __init__(self, watch_dir, prompt_text):
        super().__init__()
        self.watch_dir = Path(watch_dir)
        self.prompt_text = prompt_text
        self.is_watching = True
        self.task_queue = queue.Queue()
        self.processed = set()

    def run(self):
        for f in self.watch_dir.glob("*.*"):
            if f.suffix.lower() in SUPPORTED_EXT:
                self.processed.add(f.resolve())
        self.log_signal.emit("⚡ 哨兵監聽線上待命中，收件匣管線已鎖定。")

        while self.is_watching:
            try:
                files = [f for f in self.watch_dir.glob("*.*") if f.suffix.lower() in SUPPORTED_EXT]
                for f in files:
                    rf = f.resolve()
                    if rf not in self.processed:
                        self.processed.add(rf)
                        self.task_queue.put(rf)
                        self.queue_signal.emit(self.task_queue.qsize())
                        self.log_signal.emit(f"📥 捕獲全新素材: {f.name}")

                if not self.task_queue.empty():
                    target = self.task_queue.get()
                    self.queue_signal.emit(self.task_queue.qsize())
                    fname = target.name

                    self.log_signal.emit(f"▶ 啟動影音特徵提取與語義決策: {fname}")
                    wait_for_file_ready(target)

                    old_stdout = sys.stdout
                    stream_interceptor = EmittingStream(self.log_signal.emit)
                    sys.stdout = stream_interceptor

                    try:
                        ok = run_main_pipeline(str(target), context_prompt=self.prompt_text)
                    finally:
                        sys.stdout = old_stdout

                    if ok:
                        self.log_signal.emit(f"🎉 素材 [{fname}] 決策標記已成功注入 DaVinci Resolve！")
                    else:
                        self.log_signal.emit(f"❌ 素材 [{fname}] 處理中斷。")

                    self.task_queue.task_done()
                    self.queue_signal.emit(self.task_queue.qsize())

                time.sleep(1.5)
            except Exception as e:
                self.log_signal.emit(f"⚠️ 異常: {e}")
                time.sleep(2)

    def stop(self):
        self.is_watching = False
        self.wait()

class MidnightDashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Director Studio v1.0")
        self.resize(1200, 910)
        self.setMinimumSize(1060, 820)

        self.app_icon = create_app_icon()
        self.setWindowIcon(self.app_icon)

        # 優先從持久化配置讀取上次設定的路徑
        self.watch_dir = load_saved_watch_dir()
        self.worker = None

        self.init_ui()
        self.start_telemetry()

    def showEvent(self, event):
        super().showEvent(event)
        enable_windows_dark_titlebar(int(self.winId()))

    def make_card(self):
        card = QFrame()
        card.setProperty("class", "DashboardCard")
        return card

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 頂部導航
        header = QFrame()
        header.setProperty("class", "HeaderCard")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(28, 14, 28, 14)

        t_box = QHBoxLayout()
        logo = QLabel("🟣 AI DIRECTOR STUDIO")
        logo.setStyleSheet("font-size: 17px; font-weight: 900; color: #FFFFFF; letter-spacing: 1px;")
        ver = QLabel("v1.0 ARTIFACT")
        ver.setStyleSheet("background-color: #231938; color: #C084FC; border: 1px solid #7E22CE; border-radius: 6px; padding: 3px 8px; font-size: 10px; font-weight: bold;")
        t_box.addWidget(logo)
        t_box.addSpacing(10)
        t_box.addWidget(ver)
        h_layout.addLayout(t_box)

        h_layout.addStretch()

        self.badge_resolve = QLabel("RESOLVE: DETECTING")
        self.badge_resolve.setProperty("class", "PillBadge")
        self.badge_guard = QLabel("GUARD: IDLE")
        self.badge_guard.setProperty("class", "PillBadge")
        h_layout.addWidget(self.badge_resolve)
        h_layout.addSpacing(10)
        h_layout.addWidget(self.badge_guard)
        main_layout.addWidget(header)

        # 核心區域
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 16, 24, 12)
        body_layout.setSpacing(14)

        upper_box = QHBoxLayout()
        upper_box.setSpacing(16)

        # ======================================================================
        # ===== 左欄：硬體核心 =====
        # ======================================================================
        col_left = QVBoxLayout()
        col_left.setSpacing(14)

        # 1-1. SYSTEM CORE & MEMORY
        card_ram = self.make_card()
        ram_l = QVBoxLayout(card_ram)
        ram_l.setContentsMargins(18, 14, 18, 16)
        ram_l.setSpacing(0)

        lbl_ram_title = QLabel()
        lbl_ram_title.setText(
            "<div style='line-height: 100%; margin: 0px; padding: 0px;'>"
            "<span style='font-size: 13px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;'>SYSTEM CORE & MEMORY</span><br>"
            "<span style='font-size: 11px; color: #717B9E; line-height: 140%;'>中央處理器負載與實體記憶體水缸蓄量</span>"
            "</div>"
        )
        ram_l.addWidget(lbl_ram_title)
        ram_l.addSpacing(12)

        core_box = QHBoxLayout()
        core_box.addSpacing(25)
        self.ring_cpu = RingMeter(title="CPU LOAD", start_color="#00F5D4", end_color="#7928CA", size=115)
        self.thermo_cpu = ThermoMeter(width=34, height=115)
        self.tank_ram = RamTankMeter(title="RAM TANK", width=130, height=115)
        
        core_box.addWidget(self.ring_cpu)
        core_box.addSpacing(4)
        core_box.addWidget(self.thermo_cpu)
        core_box.addSpacing(18)
        core_box.addWidget(self.tank_ram)
        core_box.addStretch()
        ram_l.addLayout(core_box)
        col_left.addWidget(card_ram)

        # 1-2. LOCAL STORAGE POOL
        card_disk = self.make_card()
        disk_l = QVBoxLayout(card_disk)
        disk_l.setContentsMargins(18, 12, 18, 12)
        disk_l.setSpacing(0)

        lbl_disk_title = QLabel()
        lbl_disk_title.setText(
            "<div style='line-height: 100%; margin: 0px; padding: 0px;'>"
            "<span style='font-size: 13px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;'>LOCAL STORAGE POOL</span><br>"
            "<span style='font-size: 11px; color: #717B9E; line-height: 140%;'>本地高速存儲磁區 (SSD / NVMe / HDD) 空間監控</span>"
            "</div>"
        )
        disk_l.addWidget(lbl_disk_title)
        disk_l.addSpacing(10)

        self.disk_tiles_box = QHBoxLayout()
        self.disk_c = DiskTile("C:")
        self.disk_d = DiskTile("D:")
        self.disk_e = DiskTile("E:")
        self.disk_tiles_box.addWidget(self.disk_c)
        self.disk_tiles_box.addWidget(self.disk_d)
        self.disk_tiles_box.addWidget(self.disk_e)
        disk_l.addLayout(self.disk_tiles_box)

        more_row = QHBoxLayout()
        more_row.addStretch()
        btn_more = QPushButton("更多......")
        btn_more.setProperty("class", "MoreBtn")
        btn_more.clicked.connect(self.show_disk_details)
        more_row.addWidget(btn_more)
        disk_l.addLayout(more_row)
        col_left.addWidget(card_disk)

        # 1-3. GPU ACCELERATION
        card_gpus = self.make_card()
        gpu_l = QVBoxLayout(card_gpus)
        gpu_l.setContentsMargins(18, 14, 18, 16)
        gpu_l.setSpacing(0)

        lbl_gpu_title = QLabel()
        lbl_gpu_title.setText(
            "<div style='line-height: 100%; margin: 0px; padding: 0px;'>"
            "<span style='font-size: 13px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;'>GPU ACCELERATION</span><br>"
            "<span style='font-size: 11px; color: #717B9E; line-height: 140%;'>硬體加速核心顯存佔用與即時溫度監控</span>"
            "</div>"
        )
        gpu_l.addWidget(lbl_gpu_title)
        gpu_l.addSpacing(12)

        gpu_meter_box = QHBoxLayout()
        gpu_meter_box.addSpacing(25)
        self.ring_gpu0 = RingMeter(title="RTX 5060 Ti", start_color="#00F5D4", end_color="#0077B6", size=112)
        self.thermo_gpu0 = ThermoMeter(width=34, height=112)

        self.ring_gpu1 = RingMeter(title="RTX 3060", start_color="#C084FC", end_color="#FF007F", size=112)
        self.thermo_gpu1 = ThermoMeter(width=34, height=112)

        gpu_meter_box.addWidget(self.ring_gpu0)
        gpu_meter_box.addSpacing(4)
        gpu_meter_box.addWidget(self.thermo_gpu0)
        gpu_meter_box.addSpacing(18)
        gpu_meter_box.addWidget(self.ring_gpu1)
        gpu_meter_box.addSpacing(4)
        gpu_meter_box.addWidget(self.thermo_gpu1)
        gpu_meter_box.addStretch()
        gpu_l.addLayout(gpu_meter_box)
        col_left.addWidget(card_gpus)

        upper_box.addLayout(col_left, stretch=3)

        # ======================================================================
        # ===== 中欄：超大面積 Prompt 輸入 =====
        # ======================================================================
        col_mid = QVBoxLayout()
        card_prompt = self.make_card()
        cp_l = QVBoxLayout(card_prompt)
        cp_l.setContentsMargins(18, 14, 18, 16)
        cp_l.setSpacing(0)
        
        lbl_cp_title = QLabel()
        lbl_cp_title.setText(
            "<div style='line-height: 100%; margin: 0px; padding: 0px;'>"
            "<span style='font-size: 13px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;'>DOMAIN CONTEXT PROMPT</span><br>"
            "<span style='font-size: 11px; color: #717B9E; line-height: 140%;'>動態特徵提示詞注入，大幅降低專業術語同音錯字機率</span>"
            "</div>"
        )
        cp_l.addWidget(lbl_cp_title)
        cp_l.addSpacing(12)

        self.edit_prompt = QTextEdit()
        self.edit_prompt.setPlaceholderText("請在此輸入影音領域專有名詞、角色名字、電競術語或地名（支援多行換行輸入）...")
        self.edit_prompt.setText("日常生活旅遊 Vlog，包含特戰英豪遊戲術語（蓋克、拆包、大絕）、飯店電器開箱、日本地名與生活閒聊對話。")
        cp_l.addWidget(self.edit_prompt)
        col_mid.addWidget(card_prompt)

        upper_box.addLayout(col_mid, stretch=4)

        # ======================================================================
        # ===== 右欄：即時日誌終端 =====
        # ======================================================================
        col_right = QVBoxLayout()
        card_log = self.make_card()
        cl_l = QVBoxLayout(card_log)
        cl_l.setContentsMargins(18, 14, 18, 16)
        cl_l.setSpacing(0)

        log_head = QHBoxLayout()
        lbl_cl = QLabel("EVENT STREAM LOG")
        lbl_cl.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: bold; letter-spacing: 0.5px;")
        lbl_live = QLabel("● STREAMING")
        lbl_live.setStyleSheet("color: #00F5D4; font-size: 10px; font-weight: bold;")
        log_head.addWidget(lbl_cl)
        log_head.addStretch()
        log_head.addWidget(lbl_live)

        title_box_l = QWidget()
        tbl_l = QVBoxLayout(title_box_l)
        tbl_l.setContentsMargins(0, 0, 0, 0)
        tbl_l.setSpacing(0)
        tbl_l.addLayout(log_head)
        lbl_log_sub = QLabel("神經分析節點、檔案偵測與 DaVinci 注入事件串流")
        lbl_log_sub.setStyleSheet("color: #717B9E; font-size: 11px; line-height: 140%;")
        tbl_l.addWidget(lbl_log_sub)
        cl_l.addWidget(title_box_l)
        cl_l.addSpacing(12)

        self.txt_log = QTextEdit()
        self.txt_log.setProperty("class", "TerminalLog")
        self.txt_log.setReadOnly(True)
        cl_l.addWidget(self.txt_log)
        col_right.addWidget(card_log)

        upper_box.addLayout(col_right, stretch=3)
        body_layout.addLayout(upper_box, stretch=1)

        # ======================================================================
        # ===== 下方細長條 Pipeline (支援路徑修改自動儲存) =====
        # ======================================================================
        card_watch = self.make_card()
        cw_l = QHBoxLayout(card_watch)
        cw_l.setContentsMargins(20, 10, 20, 10)
        cw_l.setSpacing(14)

        title_box_w = QLabel()
        title_box_w.setText(
            "<div style='line-height: 125%; margin: 0px; padding: 0px;'>"
            "<span style='font-size: 13px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;'>WATCH FOLDER PIPELINE</span><br>"
            "<span style='font-size: 11px; font-weight: bold; color: #00F5D4;'>偵測這個路徑的資料夾更新 ➔</span>"
            "</div>"
        )
        cw_l.addWidget(title_box_w)

        self.edit_path = QLineEdit(self.watch_dir)
        self.edit_path.textChanged.connect(self.on_path_text_changed)
        btn_browse = QPushButton("探勘目錄")
        btn_browse.setProperty("class", "SubPillBtn")
        btn_browse.clicked.connect(self.browse_folder)
        cw_l.addWidget(self.edit_path, stretch=1)
        cw_l.addWidget(btn_browse)

        self.lbl_queue = QLabel("📦 佇列: 0 部")
        self.lbl_queue.setStyleSheet("color: #FBBF24; font-weight: bold; font-size: 12px; margin-left: 10px; margin-right: 10px;")
        cw_l.addWidget(self.lbl_queue)

        self.btn_toggle = QPushButton("⚡ START SENTINEL")
        self.btn_toggle.setProperty("class", "PillBtn")
        self.btn_toggle.clicked.connect(self.toggle_watching)
        cw_l.addWidget(self.btn_toggle)

        body_layout.addWidget(card_watch)
        main_layout.addWidget(body, stretch=1)

        # 底部署名
        footer = QFrame()
        footer.setStyleSheet("background-color: #090A12; border-top: 1px solid #161828; padding: 6px;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(28, 6, 28, 6)

        foot_left = QLabel("AI DIRECTOR STUDIO  |  NEURAL INGESTION & AUTO-MARKER")
        foot_left.setStyleSheet("color: #555E7A; font-size: 10px; font-weight: bold; letter-spacing: 0.8px;")
        foot_right = QLabel("Developed by Pan Bo-Han (潘柏翰)  |  指導老師：郭俞霈教授")
        foot_right.setStyleSheet("color: #8C9BAE; font-size: 11px; font-weight: bold;")
        f_layout.addWidget(foot_left)
        f_layout.addStretch()
        f_layout.addWidget(foot_right)
        main_layout.addWidget(footer)

        self.append_log("⚡ [系統核心] 完全體工作站已就緒。")

    def append_log(self, text):
        ts = datetime.now().strftime("%H:%M:%S")
        clean_text = text.strip()
        
        if "▶" in clean_text or "啟動" in clean_text:
            styled = f"<span style='color:#56D6C2; font-weight:bold;'>{clean_text}</span>"
        elif "🎉" in clean_text or "成功" in clean_text or "完成" in clean_text:
            styled = f"<span style='color:#74C69D; font-weight:bold;'>{clean_text}</span>"
        elif "❌" in clean_text or "失敗" in clean_text or "中斷" in clean_text:
            styled = f"<span style='color:#FF758F; font-weight:bold;'>{clean_text}</span>"
        elif "Cyan" in clean_text or "青色" in clean_text:
            styled = f"<span style='color:#00F5D4;'>{clean_text}</span>"
        elif "Pink" in clean_text or "粉紅" in clean_text or "精彩" in clean_text:
            styled = f"<span style='color:#FF007F; font-weight:bold;'>{clean_text}</span>"
        elif "Yellow" in clean_text or "黃色" in clean_text or "注意" in clean_text:
            styled = f"<span style='color:#FBBF24;'>{clean_text}</span>"
        elif "Green" in clean_text or "綠色" in clean_text or "推薦" in clean_text:
            styled = f"<span style='color:#52B788;'>{clean_text}</span>"
        elif "Blue" in clean_text or "藍色" in clean_text:
            styled = f"<span style='color:#00B4D8;'>{clean_text}</span>"
        elif "[" in clean_text and "]" in clean_text:
            styled = f"<span style='color:#C084FC;'>{clean_text}</span>"
        else:
            styled = f"<span style='color:#A0AEC0;'>{clean_text}</span>"

        html_line = f"<div style='margin-bottom: 2px;'><span style='color:#555E7A;'>[{ts}]</span> {styled}</div>"
        self.txt_log.append(html_line)
        self.txt_log.moveCursor(QTextCursor.MoveOperation.End)

    def on_path_text_changed(self, text):
        cleaned = text.strip()
        if os.path.exists(cleaned) and os.path.isdir(cleaned):
            self.watch_dir = cleaned
            save_watch_dir_to_config(cleaned)

    def browse_folder(self):
        f = QFileDialog.getExistingDirectory(self, "選擇素材收件匣資料夾", self.edit_path.text())
        if f:
            self.edit_path.setText(f)
            self.watch_dir = f
            save_watch_dir_to_config(f)
            self.append_log(f"📁 監聽目錄變更為: {f}")

    def show_disk_details(self):
        dlg = DiskDetailDialog(self)
        dlg.exec()

    def start_telemetry(self):
        self.telemetry = TelemetryThread()
        self.telemetry.telemetry_signal.connect(self.update_telemetry)
        self.telemetry.start()

    def update_telemetry(self, cpu_p, cpu_t, ram_p, ram_v, g0_p, g0_v, g0_t, g1_p, g1_v, g1_t, disks, resolve_on):
        self.ring_cpu.set_data(cpu_p)
        self.thermo_cpu.set_temp(cpu_t)
        self.tank_ram.set_data(ram_p, ram_v)
        
        self.ring_gpu0.set_data(g0_p, g0_v)
        self.thermo_gpu0.set_temp(g0_t)

        self.ring_gpu1.set_data(g1_p, g1_v)
        self.thermo_gpu1.set_temp(g1_t)

        for letter, tot, free, pct in disks:
            if letter == "C":
                self.disk_c.update_disk(tot, free, pct)
            elif letter == "D":
                self.disk_d.update_disk(tot, free, pct)
            elif letter == "E":
                self.disk_e.update_disk(tot, free, pct)

        if resolve_on:
            self.badge_resolve.setText("RESOLVE: READY")
            self.badge_resolve.setStyleSheet("background-color: #122822; color: #52B788; border: 1px solid #2D6A4F; border-radius: 10px; padding: 4px 12px; font-size: 10px; font-weight: bold;")
        else:
            self.badge_resolve.setText("RESOLVE: OFFLINE")
            self.badge_resolve.setStyleSheet("background-color: #2D1424; color: #F472B6; border: 1px solid #701A4B; border-radius: 10px; padding: 4px 12px; font-size: 10px; font-weight: bold;")

    def toggle_watching(self):
        if not self.worker or not self.worker.isRunning():
            self.worker = WorkerThread(self.edit_path.text(), self.edit_prompt.toPlainText())
            self.worker.log_signal.connect(self.append_log)
            self.worker.queue_signal.connect(self.on_queue)
            self.worker.start()

            self.btn_toggle.setText("⏹ STOP SENTINEL")
            self.btn_toggle.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E11D48, stop:1 #BE123C); color: #FFF; border: none; border-radius: 10px; padding: 9px 24px; font-weight: bold; font-size: 12px;")

            self.badge_guard.setText("GUARD: ACTIVE")
            self.badge_guard.setStyleSheet("background-color: #122822; color: #00F5D4; border: 1px solid #00F5D4; border-radius: 10px; padding: 4px 12px; font-size: 10px; font-weight: bold;")
        else:
            self.worker.stop()
            self.worker = None

            self.btn_toggle.setText("⚡ START SENTINEL")
            self.btn_toggle.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF007F, stop:1 #7928CA); color: #FFF; border: none; border-radius: 10px; padding: 9px 24px; font-weight: bold; font-size: 12px;")

            self.badge_guard.setText("GUARD: IDLE")
            self.badge_guard.setStyleSheet("background-color: #1B1E36; color: #A0ABC0; border: 1px solid #2A2F54; border-radius: 10px; padding: 4px 12px; font-size: 10px; font-weight: bold;")
            self.append_log("⚡ 哨兵監聽已離線。")

    def on_queue(self, q_count):
        self.lbl_queue.setText(f"📦 佇列: {q_count} 部")

    def closeEvent(self, event):
        if hasattr(self, 'telemetry') and self.telemetry.isRunning():
            self.telemetry.stop()
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app_icon = create_app_icon()
    app.setWindowIcon(app_icon)
    app.setStyleSheet(MIDNIGHT_QSS)
    window = MidnightDashboardWindow()
    window.show()
    sys.exit(app.exec())