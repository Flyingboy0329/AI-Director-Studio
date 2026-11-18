"""Local model selection, private preferences and background runtime startup."""
import json
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QSizePolicy, QCheckBox,
)

from path_utils import get_project_root, get_settings_file, load_local_settings, resolve_project_path
from model_runtime import ModelRuntime, find_server
from whisper_resources import RAM_GIB
from context_settings import CONTEXT_SIZES, DEFAULT_CONTEXT, validate_context


class ScrollSafeComboBox(QComboBox):
    """Let the surrounding scroll area handle wheel input, even when focused."""
    def wheelEvent(self, event):
        event.ignore()


class RuntimeLoadThread(QThread):
    status = pyqtSignal(str)
    ready = pyqtSignal(bool, str)

    def __init__(self, runtime, settings, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.settings = dict(settings)

    def run(self):
        try:
            self.runtime.ensure_ready(self.settings, self.status.emit)
            self.runtime.ensure_audio_ready(self.settings, self.status.emit)
            self.ready.emit(True, "模型就緒" if self.settings.get("llm_path") else "技術分析模式（未選 LLM）")
        except Exception as exc:
            self.ready.emit(False, str(exc))


def scan_gguf(directory):
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise ValueError("模型資料夾不存在")
    # Names only suggest roles; keep every main model available in both selectors.
    files = sorted((p.resolve() for p in root.rglob("*")
                    if p.is_file() and p.suffix.lower() == ".gguf"),
                   key=lambda p: str(p).casefold())
    projectors = [p for p in files if "mmproj" in p.name.lower()]
    models = [p for p in files if p not in projectors]
    return models, projectors


class RuntimeUnloadThread(QThread):
    stopped = pyqtSignal(bool, str)

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel

    def run(self):
        try:
            external = bool(self.panel.runtime.external_services)
            self.panel.shutdown_runtime()
            self.stopped.emit(True, "本程式啟動的引擎已退出；外部服務保留，無法代為卸載。" if external else "模型已卸載，本程式啟動的 llama-server 已退出。")
        except Exception as exc:
            self.stopped.emit(False, str(exc))


class RuntimeRecoveryThread(QThread):
    status = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, runtime, parent):
        super().__init__(parent);self.runtime=runtime

    def run(self):
        try:
            self.runtime.recover(self.status.emit)
            self.done.emit(True,"背景模型紀錄檢查完成")
        except Exception as exc:
            self.done.emit(False,str(exc))


class ModelScanThread(QThread):
    completed = pyqtSignal(object, object, str)

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.directory = directory

    def run(self):
        try:
            models, projectors = scan_gguf(self.directory)
            self.completed.emit(models, projectors, "")
        except Exception as exc:
            self.completed.emit([], [], str(exc))


class SingleLineHint(QLabel):
    """Keep the footer on one line without forcing the center column wider."""
    def __init__(self, text):
        super().__init__()
        self.full_text = text
        self.setToolTip(text)
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.fontMetrics().height() + 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(
            self.full_text, Qt.TextElideMode.ElideRight, self.contentsRect().width()))


class ModelSelectionPanel(QFrame):
    help_requested = pyqtSignal()
    unload_requested = pyqtSignal()
    runtime_ready = pyqtSignal(bool, str)
    runtime_log = pyqtSignal(str)
    runtime_stopped = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "DashboardCard")
        self.settings_path = get_settings_file("model_settings.json")
        self.settings = self.load_settings()
        self.scan_thread = None
        self.loading = True
        self.runtime = ModelRuntime()
        self.runtime_loader = None
        self.runtime_unloader = None
        self.runtime_recovery = None
        self.unload_failed = False
        self.working = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(5)
        title = QLabel("LOCAL MODEL SELECTION")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #E2E8F0;")
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch()
        self.help_button = QPushButton("說明…")
        self.help_button.setProperty("class", "MoreBtn")
        self.help_button.clicked.connect(lambda: self.help_requested.emit())
        title_row.addWidget(self.help_button)
        layout.addLayout(title_row)
        row = QHBoxLayout()
        self.directory = QLineEdit(self.settings.get(
            "model_dir", str(get_project_root() / "04_Models")))
        self.directory.setPlaceholderText("包含 GGUF 的資料夾（含子資料夾）")
        self.directory.setToolTip(self.directory.text())
        self.directory.setMinimumHeight(38)
        self.browse = QPushButton("選資料夾")
        self.browse.setProperty("class", "SubPillBtn")
        self.refresh = QPushButton("掃描")
        self.refresh.setProperty("class", "SubPillBtn")
        row.addWidget(self.directory, 1)
        row.addWidget(self.browse)
        row.addWidget(self.refresh)
        layout.addLayout(row)
        self.mode = ScrollSafeComboBox()
        self.mode.addItem("VLM ＋ LLM · 分工處理", "separate")
        self.mode.addItem("只用 LLM · 不使用獨立 VLM", "llm_only")
        self.mode.setCurrentIndex(max(0, self.mode.findData(self.settings.get("model_mode", "separate"))))
        self.mode.setToolTip("只用 LLM：有匹配 mmproj 且主模型支援視覺時，可兼做畫面理解；不選 mmproj 則僅做文字決策。")
        layout.addWidget(self.mode)
        self.selectors = {}
        for key, label in (("vlm_path", "VLM · 畫面理解"),
                           ("mmproj_path", "mmproj · VLM 配套投影"),
                           ("llm_path", "LLM · 導演決策／單模型模式主檔"),
                           ("llm_mmproj_path", "mmproj · LLM 配套投影（選用）")):
            layout.addWidget(QLabel(label))
            combo = ScrollSafeComboBox()
            combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            combo.setMinimumContentsLength(10)
            combo.setStyleSheet("QComboBox { background: #090A12; color: #00F5D4; "
                                "border: 1px solid #232742; border-radius: 6px; padding: 7px; }"
                                "QComboBox QAbstractItemView { background: #121424; color: #E2E8F0; }")
            combo.currentIndexChanged.connect(self.save_settings)
            layout.addWidget(combo)
            self.selectors[key] = combo
        self.mode.setStyleSheet(self.selectors["vlm_path"].styleSheet())
        self.mode.currentIndexChanged.connect(self.update_mode)
        self.update_mode()
        layout.addWidget(QLabel("Faster-Whisper · 語音轉錄"))
        self.whisper = ScrollSafeComboBox()
        self.whisper.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.whisper.setMinimumContentsLength(10)
        self.whisper.view().setMinimumWidth(400)
        self.whisper.addItem("自動 · 依 RAM 選 small／base／tiny（CPU INT8）", "")
        for name, description in (
                ("tiny", "最快、資源最省；適合粗略預覽"),
                ("base", "輕量快速；適合清楚的簡單對話"),
                ("small", "速度與辨識品質折衷；日常素材起點"),
                ("medium", "較重視辨識品質；需要更多資源"),
                ("large-v3", "品質優先；較慢、資源需求高"),
                ("turbo", "大型模型的速度折衷；效果依素材而異")):
            load = "低" if name in ("tiny", "base") else "中" if name == "small" else "高"
            self.whisper.addItem(f"{name} · RAM 規劃約 {RAM_GIB[name]:g}GiB｜CPU 負擔{load} · {description}", name)
        self.whisper.setStyleSheet(self.selectors["vlm_path"].styleSheet())
        # Also allow an existing CTranslate2 model directory (not a GGUF).
        local = self.settings.get("whisper_model", "")
        index = self.whisper.findData(local)
        if index < 0:
            self.whisper.addItem(local, local)
            index = self.whisper.count() - 1
        self.whisper.setCurrentIndex(index)
        self.whisper.setToolTip("內建模型存於04_Models/Whisper；完整則離線使用，缺少時先找快取再首次下載／續傳。卸除不刪權重。本機模型須為完整CTranslate2目錄，不能使用GGUF。")
        self.whisper.currentIndexChanged.connect(self.on_whisper_selected)
        audio_row = QHBoxLayout()
        audio_row.addWidget(self.whisper, 1)
        audio_browse = QPushButton("本機模型")
        self.audio_browse = audio_browse
        audio_browse.setProperty("class", "SubPillBtn")
        audio_browse.clicked.connect(self.choose_whisper)
        audio_row.addWidget(audio_browse)
        layout.addLayout(audio_row)
        context_row = QHBoxLayout()
        context_row.addWidget(QLabel("Context"))
        self.context = ScrollSafeComboBox()
        for size in CONTEXT_SIZES:
            self.context.addItem(f"{size//1024}K" + ("（預設）" if size == DEFAULT_CONTEXT else ""), size)
        try:
            context = validate_context(self.settings.get("context_size", DEFAULT_CONTEXT))
        except ValueError:
            context = DEFAULT_CONTEXT
        self.context.setCurrentIndex(self.context.findData(context))
        self.context.setStyleSheet(self.selectors["vlm_path"].styleSheet())
        self.context.setToolTip("每個模型服務的 token 容量；重新載入後生效。較大 Context 增加記憶體需求，不能超過模型原生支援。外部服務需自行設定。")
        self.context.currentIndexChanged.connect(self.save_settings)
        context_row.addWidget(self.context, 1)
        layout.addLayout(context_row)
        runtime_row = QHBoxLayout()
        self.engine_button = QPushButton("選引擎")
        self.engine_button.setProperty("class", "SubPillBtn")
        self.engine_button.setToolTip("指定 llama-server.exe；預設自動尋找專案 tools 下的引擎。")
        self.engine_button.clicked.connect(self.choose_engine)
        self.load_button = QPushButton("載入模型")
        self.load_button.setProperty("class", "SubPillBtn")
        self.load_button.clicked.connect(self.toggle_runtime)
        self.runtime_status = QLabel("MODEL: 未載入")
        self.runtime_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        runtime_row.addWidget(self.engine_button)
        runtime_row.addWidget(self.load_button)
        runtime_row.addWidget(self.runtime_status, 1)
        layout.addLayout(runtime_row)
        self.disable_mmap = QCheckBox("停用 mmap（模型檔案映射）")
        self.disable_mmap.setChecked(self.settings.get("load_mode", "none") == "none")
        self.disable_mmap.setToolTip("關閉模型檔案的記憶體映射；CPU 權重、暫存與系統快取仍可能使用 RAM，統一記憶體也不會變成獨立顯存。")
        self.disable_mmap.toggled.connect(self.save_settings)
        layout.addWidget(self.disable_mmap)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size: 11px; color: #A0ABC0;")
        layout.addWidget(self.status)
        self.whisper_actual = QLabel("Whisper：等待選型，尚未載入")
        self.whisper_actual.setWordWrap(True)
        self.whisper_actual.setStyleSheet("font-size: 11px; color: #00F5D4;")
        self.whisper_actual_model = ""
        self.whisper_loaded = False
        layout.addWidget(self.whisper_actual)
        for combo in [self.mode, self.whisper, self.context, *self.selectors.values()]:
            combo.setMinimumHeight(32)
        for button in (self.browse, self.refresh, audio_browse, self.engine_button, self.load_button):
            button.setMinimumHeight(32)
        self.status.setMinimumHeight(18)
        self.setMinimumHeight(self.sizeHint().height())
        self.browse.clicked.connect(self.choose_directory)
        self.refresh.clicked.connect(self.start_scan)
        self.directory.returnPressed.connect(self.start_scan)
        self.loading = False
        self.start_scan()

    def load_settings(self):
        data = load_local_settings("model_settings.json")
        if data.get("model_dir"):
            data["model_dir"] = str(resolve_project_path(data["model_dir"]))
        for key in ("vlm_path", "llm_path", "mmproj_path", "llm_mmproj_path", "server_path"):
            if data.get(key):
                data[key] = str(resolve_project_path(data[key]))
        return data

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "選擇模型資料夾", self.directory.text())
        if directory:
            self.directory.setText(directory)
            self.start_scan()

    def start_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            return
        if self.selectors["vlm_path"].count():
            self.settings.update(self.values())
        self.refresh.setEnabled(False)
        self.browse.setEnabled(False)
        self.directory.setEnabled(False)
        self.status.setText("正在掃描 GGUF（含子資料夾）…")
        self.scan_thread = ModelScanThread(self.directory.text().strip(), self)
        self.scan_thread.completed.connect(self.finish_scan)
        self.scan_thread.start()

    def finish_scan(self, models, projectors, error):
        self.loading = True
        root = Path(self.directory.text().strip()).resolve()
        for key, combo in self.selectors.items():
            combo.clear()
            combo.addItem("未選擇", "")
            for path in projectors if key in ("mmproj_path", "llm_mmproj_path") else models:
                combo.addItem(str(path.relative_to(root)), str(path))
                combo.setItemData(combo.count() - 1, str(path), 3)  # ToolTipRole
            saved = self.settings.get(key, "")
            index = combo.findData(saved)
            if saved and index < 0:
                combo.addItem(f"未在此資料夾找到：{Path(saved).name}", saved)
                index = combo.count() - 1
            combo.setCurrentIndex(max(0, index))
        self.loading = False
        self.refresh.setEnabled(True)
        self.browse.setEnabled(True)
        self.directory.setEnabled(True)
        self.directory.setToolTip(str(root))
        self.status.setText(error or f"找到 {len(models)} 個主模型、{len(projectors)} 個 mmproj。")
        if not error:
            self.save_settings()

    def values(self):
        return {"model_dir": self.directory.text().strip(),
                "model_mode": self.mode.currentData(),
                "server_path": self.settings.get("server_path", ""),
                "llm_url": self.settings.get("llm_url", "http://127.0.0.1:8080"),
                "vlm_url": self.settings.get("vlm_url", "http://127.0.0.1:8081"),
                "whisper_model": self.whisper.currentData() or "",
                "whisper_prompt": self.settings.get("whisper_prompt", ""),
                "load_mode": "none" if self.disable_mmap.isChecked() else "auto",
                "context_size": self.context.currentData(),
                **{key: combo.currentData() or "" for key, combo in self.selectors.items()}}

    def update_mode(self, *_):
        separate = self.mode.currentData() == "separate"
        for key in ("vlm_path", "mmproj_path"):
            self.selectors[key].setEnabled(separate)
        # Keep VLM preferences when switching modes; model_mode determines usage.
        if not self.loading:
            self.save_settings()

    def update_whisper_status(self, message):
        if message.startswith("[Faster-Whisper] LOADING："):
            self.whisper_actual.setText("Whisper：載入中…")
            return
        for prefix, state in (("[Faster-Whisper] 選型完成：", "已選型，載入中"),
                              ("[Faster-Whisper] READY：", "READY")):
            if message.startswith(prefix):
                self.whisper_actual_model = message[len(prefix):].split(" | ", 1)[0].strip()
                self.whisper_loaded = state == "READY"
                self.whisper_actual.setText(f"Whisper：{self.whisper_actual_model}｜{state}")
                self.whisper_actual.setToolTip(message)
                return
        if message.startswith("[Faster-Whisper] 稽核完成"):
            self.whisper_actual.setText(f"Whisper：{self.whisper_actual_model}｜本次轉錄完成" + ("・已釋放" if self.whisper_loaded is False else "・READY（模型保留）"))
        elif message.startswith("[Faster-Whisper] UNLOADED："):
            self.whisper_loaded = False
            self.whisper_actual.setText(f"Whisper：{self.whisper_actual_model}｜未載入（本次已釋放）")
        elif message.startswith("[Faster-Whisper] 釋放失敗："):
            self.whisper_loaded = None
        elif message.startswith(("[Faster-Whisper] failed：", "[Faster-Whisper] cancelled：")):
            self.whisper_actual.setText(f"Whisper：{self.whisper_actual_model or '未載入'}｜本次未完成")
            self.whisper_actual.setToolTip(message)

    def choose_engine(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇 llama-server 引擎", find_server(self.settings.get("server_path", "")), "llama-server (llama-server llama-server.exe);;All files (*)")
        if path:
            self.settings["server_path"] = path
            self.save_settings()
            self.runtime_status.setText("MODEL: 引擎已選")
            self.runtime_status.setToolTip(path)

    def announce_whisper(self):
        choice = self.whisper.currentData() or "自動（依 RAM 選 small／base／tiny；CPU INT8）"
        state = "已載入（變更選擇須卸除後重載）" if self.runtime.has_audio_model() else "未載入"
        self.runtime_log.emit(f"[Faster-Whisper] 選擇：{choice}；狀態：{state}。按載入模型時部署並回報大小／裝置／READY；停止監看保留，由卸除模型釋放。")

    def on_whisper_selected(self, *_):
        self.save_settings()
        if not self.runtime.has_audio_model():
            self.whisper_loaded = False
            self.whisper_actual.setText("Whisper：已選擇，尚未載入")
        else:
            self.whisper_actual.setToolTip("選擇已變更；目前模型保留，卸除並重新載入後套用。")
        self.announce_whisper()

    def refresh_runtime_button(self):
        owned = bool(self.runtime.processes) or self.runtime.has_audio_model()
        external = bool(self.runtime.external_services)
        self.load_button.setText("卸除模型" if owned else "中斷外部連線" if external else "載入模型")
        self.load_button.setStyleSheet("background: #E11D48; color: white; border: none; border-radius: 8px; padding: 7px 14px; font-weight: bold;" if owned or external else "")

    def recover_runtime(self):
        self.load_button.setEnabled(False)
        self.runtime_recovery=RuntimeRecoveryThread(self.runtime,self)
        self.runtime_recovery.status.connect(self.runtime_log.emit)
        self.runtime_recovery.done.connect(self.on_recovered)
        self.runtime_recovery.start()

    def on_recovered(self, ok, message):
        self.refresh_runtime_button()
        self.load_button.setEnabled(True)
        if self.runtime.processes:
            self.runtime_status.setText("MODEL: 背景引擎已偵測")
        self.runtime_log.emit(f"[模型恢復] {message}")

    def set_working(self, working):
        self.working = working
        self.mode.setEnabled(not working)
        self.directory.setEnabled(not working)
        self.browse.setEnabled(not working)
        self.refresh.setEnabled(not working)
        self.engine_button.setEnabled(not working)
        self.load_button.setEnabled(not working or bool(self.runtime.processes or self.runtime.external_services or self.runtime.has_audio_model()))
        self.whisper.setEnabled(not working)
        self.context.setEnabled(not working)
        self.audio_browse.setEnabled(not working)
        self.disable_mmap.setEnabled(not working)
        for combo in self.selectors.values():
            combo.setEnabled(not working)
        if not working:
            self.update_mode()

    def load_runtime(self):
        if self.runtime_recovery and self.runtime_recovery.isRunning():
            self.runtime_ready.emit(False,"正在恢復背景模型紀錄，請完成後再開始。")
            return
        if self.runtime_unloader and self.runtime_unloader.isRunning():
            return
        if self.runtime_loader and self.runtime_loader.isRunning():
            return
        if self.scan_thread and self.scan_thread.isRunning():
            self.runtime_ready.emit(False, "模型目錄仍在掃描，請完成後再試。")
            return
        self.set_working(True)
        self.load_button.setEnabled(False)
        self.runtime_log.emit("=" * 48)
        self.runtime_log.emit("[模型部署] 開始載入本次模型配置")
        self.announce_whisper()
        self.runtime_status.setText("MODEL: 載入中…")
        self.runtime.cancel.clear()
        self.runtime_loader = RuntimeLoadThread(self.runtime, self.values(), self)
        self.runtime_loader.status.connect(self.runtime_log.emit)
        self.runtime_loader.ready.connect(self.on_runtime_ready)
        self.runtime_loader.start()

    def toggle_runtime(self):
        if self.unload_failed or self.runtime.processes or self.runtime.external_services or self.runtime.has_audio_model():
            if self.receivers(self.unload_requested):self.unload_requested.emit()
            else:self.unload_runtime()
        else:
            self.load_runtime()

    def unload_runtime(self):
        if self.runtime_unloader and self.runtime_unloader.isRunning():
            return
        self.set_working(True)
        self.load_button.setEnabled(False)
        self.load_button.setText("卸除中…")
        self.runtime_status.setText("MODEL: 卸載中…")
        self.runtime_unloader = RuntimeUnloadThread(self)
        self.runtime_unloader.stopped.connect(self.on_runtime_stopped)
        self.runtime_unloader.start()

    def on_runtime_stopped(self, ok, message):
        self.unload_failed = not ok
        self.runtime_status.setText("MODEL: 未載入" if ok else "MODEL: 卸載失敗")
        self.runtime_status.setToolTip(message)
        if ok:
            self.runtime.external_services.clear()
        self.set_working(False)
        self.refresh_runtime_button()
        if not ok:self.load_button.setText("重試卸除")
        self.runtime_log.emit(f"{'✅' if ok else '❌'} [模型引擎] {message}")
        self.runtime_stopped.emit(ok, message)

    def on_runtime_ready(self, ok, message):
        has_model = bool(self.runtime_loader and self.runtime_loader.settings.get("llm_path"))
        self.runtime_status.setText(("MODEL: READY" if has_model else "MODEL: 技術模式") if ok else "MODEL: 載入失敗")
        self.runtime_status.setToolTip(message)
        self.set_working(False)
        self.refresh_runtime_button()
        self.runtime_log.emit(f"{'✅' if ok else '❌'} [模型引擎] {message}")
        self.runtime_ready.emit(ok, message)

    def shutdown_runtime(self):
        self.runtime.cancel.set()
        if self.runtime_loader and self.runtime_loader.isRunning():
            self.runtime_loader.wait()
        self.runtime.stop(self.runtime_log.emit)

    def save_settings(self, *_):
        if self.loading:
            return
        self.settings.update(self.values())
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.status.setText(f"設定儲存失敗：{exc}")

    def choose_whisper(self):
        directory = QFileDialog.getExistingDirectory(self, "選擇 Faster-Whisper CTranslate2 模型目錄")
        if not directory:
            return
        if not (Path(directory) / "model.bin").is_file() or not (Path(directory) / "config.json").is_file():
            self.status.setText("此目錄缺少 model.bin 或 config.json；Whisper 不接受 GGUF。")
            return
        index = self.whisper.findData(directory)
        if index < 0:
            self.whisper.addItem(directory, directory)
            index = self.whisper.count() - 1
        self.whisper.setCurrentIndex(index)

    def wait_for_scan(self):
        if self.scan_thread:
            self.scan_thread.wait()
