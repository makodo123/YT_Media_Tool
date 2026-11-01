"""主視窗：網址輸入、格式選擇、下載佇列、整體進度與錯誤詳細資訊。"""

from __future__ import annotations

import dataclasses
import html
import logging
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction, QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent, QGuiApplication, QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSplitter,
    QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget,
)

from yt_media_tool import APP_DISPLAY_NAME, APP_NAME, __version__
from yt_media_tool.app_context import AppContext
from yt_media_tool.core import converter, updates
from yt_media_tool.core.download_index import DownloadedIndex
from yt_media_tool.core.downloader import PlaylistEntry, PlaylistInfo
from yt_media_tool.core.local_convert import is_media_file
from yt_media_tool.core.playlist_files import PlaylistFileStore, same_folder
from yt_media_tool.core.title_cleanup import clean_playlist_title, clean_title
from yt_media_tool.core.errors import explain_error
from yt_media_tool.core.queue_manager import (
    QUEUE_STATE, TASK_ADDED, TASK_FINISHED, TASK_PROGRESS, TASK_REMOVED, TASK_UPDATED, TaskSpec,
)
from yt_media_tool.core.task_models import (
    DownloadTask, MediaFormat, TaskStatus, format_speed, parse_clock, quality_options,
)
from yt_media_tool.core.url_parser import ParsedUrl, UrlKind, parse_urls
from yt_media_tool.gui.convert_dialog import ConvertDialog
from yt_media_tool.gui.history_dialog import HistoryDialog
from yt_media_tool.gui.rename_dialog import RenameDialog
from yt_media_tool.gui.playlist_dialog import PlaylistGroup, PlaylistPickerDialog
from yt_media_tool.gui.qt_bridge import QueueEventBridge
from yt_media_tool.gui.queue_table import ACTION_CANCEL, ACTION_OPEN, ACTION_RETRY, QueueTableView
from yt_media_tool.gui import update_dialog
from yt_media_tool.gui.settings_dialog import SettingsDialog
from yt_media_tool.gui.update_dialog import UpdateDialog, UpdateView
from yt_media_tool.gui.workers import BackgroundJob
from yt_media_tool.storage.settings import AppSettings
from yt_media_tool.utils.paths import replace_path_prefix, sanitize_filename
from yt_media_tool.utils import system_open

log = logging.getLogger(__name__)

MAX_PLAYLIST_ITEMS = 500
PASTED_VIDEO_TITLE = "（您貼上的影片）"  # 貼上的影片不在讀到的播放清單中時，選擇對話框顯示的名稱
DISCLAIMER = (
    "本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。\n"
    "請遵守著作權法及 YouTube 服務條款；本工具不支援、也不會嘗試繞過 DRM 或其他存取限制。"
)


def _local_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso


class _UpdateSignals(QObject):
    """背景下載更新 → 主執行緒。"""

    progress = Signal(float)
    finished = Signal(object)  # Path（成功）或 UpdateError


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._closing = False
        self._busy_expanding = False
        self._last_completed_dir: str | None = None
        self._batch_counts = {"completed": 0, "failed": 0}  # 自上次佇列全部結束以來的完成 / 失敗筆數
        self._tray: QSystemTrayIcon | None = None
        self._update_job: BackgroundJob | None = None
        self._convert_dialog: ConvertDialog | None = None
        self._playlist_files = PlaylistFileStore(ctx.db)
        self._update_manual = False
        self._available_update: updates.LatestRelease | None = None
        self._update_thread: threading.Thread | None = None
        self._update_cancel: threading.Event | None = None
        self._update_path: Path | None = None
        self._update_error = ""
        self._update_progress = 0.0
        self._update_check_error = ""
        self._update_dialog: UpdateDialog | None = None
        self._install_view: UpdateView | None = None  # 安裝中 / 上次更新的結果
        self._install_details = ""
        self._closing_for_update = False
        self._update_signals = _UpdateSignals(self)
        self._update_signals.progress.connect(self._on_update_progress)
        self._update_signals.finished.connect(self._on_update_downloaded)
        self._jobs: set[BackgroundJob] = set()
        self._expand_context: tuple = ()
        self._custom_names: dict[str, str] = {}  # 選歌視窗中修改過的檔名（網址 → 檔名）
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1180, 760)
        self.setAcceptDrops(True)  # 可把瀏覽器的網址拖曳到視窗任何位置

        self.bridge = QueueEventBridge(self)
        self.bridge.event.connect(self._on_queue_event)
        ctx.queue.add_listener(self.bridge)

        self._build_menu()
        self._build_ui()
        self._apply_settings_to_ui()
        self._restore_geometry()
        self._refresh_dependency_banner()
        self.check_previous_update()  # 需在建立橫幅之後

        self._idle_timer = QTimer(self, singleShot=True, interval=800)
        self._idle_timer.timeout.connect(self._check_queue_idle)
        # 切回程式時自動帶入剪貼簿中的 YouTube 網址；程式自己複製的內容不帶入
        self._last_clipboard: str | None = None
        QGuiApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)
        app = QGuiApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_application_state_changed)
        self._parse_timer = QTimer(self, singleShot=True, interval=250)
        self._parse_timer.timeout.connect(self._update_detection_summary)
        self.url_input.textChanged.connect(self._parse_timer.start)

    # ================= 介面建置 =================
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("檔案(&F)")
        open_dir = QAction("開啟下載資料夾", self)
        open_dir.triggered.connect(lambda: self._open_folder(self.folder_edit.text()))
        file_menu.addAction(open_dir)
        file_menu.addSeparator()
        quit_action = QAction("結束(&X)", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        tools_menu = self.menuBar().addMenu("工具(&T)")
        settings_action = QAction("設定…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)
        rename_action = QAction("整理舊檔案的歌名…", self)
        rename_action.triggered.connect(lambda: self.open_rename_dialog())
        tools_menu.addAction(rename_action)
        convert_action = QAction("本機檔案轉 MP3…", self)
        convert_action.triggered.connect(lambda: self.open_converter())
        tools_menu.addAction(convert_action)
        history_action = QAction("下載歷史紀錄…", self)
        history_action.triggered.connect(self.open_history)
        tools_menu.addAction(history_action)
        check_action = QAction("檢查相依元件（FFmpeg / Deno）", self)
        check_action.triggered.connect(self.show_dependency_report)
        tools_menu.addAction(check_action)

        help_menu = self.menuBar().addMenu("說明(&H)")
        notice = QAction("使用聲明", self)
        notice.triggered.connect(lambda: QMessageBox.information(self, "使用聲明", DISCLAIMER))
        help_menu.addAction(notice)
        check_update = QAction("檢查新版本…", self)
        check_update.triggered.connect(lambda: self.check_for_updates(manual=True))
        help_menu.addAction(check_update)
        about = QAction("關於", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)

        # 相依元件警示
        self.dependency_banner = QLabel()
        self.dependency_banner.setObjectName("warningLabel")
        self.dependency_banner.setWordWrap(True)
        self.dependency_banner.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.dependency_banner)

        # 新版本提醒
        self.update_banner = QLabel()
        self.update_banner.setObjectName("infoLabel")
        self.update_banner.setWordWrap(True)
        self.update_banner.setTextFormat(Qt.TextFormat.RichText)
        self.update_banner.linkActivated.connect(self._on_update_link)
        self.update_banner.hide()
        root.addWidget(self.update_banner)

        # ---- 網址輸入 ----
        url_group = QGroupBox("網址")
        url_layout = QVBoxLayout(url_group)
        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText(
            "貼上或從瀏覽器拖曳 YouTube 影片、Shorts 或播放清單網址；可一次貼上多行，重複網址會自動去除。\n"
            "含有播放清單的網址會列出清單中的影片，讓您勾選要下載哪些。")
        self.url_input.setFixedHeight(90)
        # 拖曳交給主視窗處理：一律另起一行附加，避免插入到既有網址中間
        self.url_input.setAcceptDrops(False)
        url_layout.addWidget(self.url_input)
        row = QHBoxLayout()
        paste_button = QPushButton("從剪貼簿貼上")
        paste_button.clicked.connect(self._paste_clipboard)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self.url_input.clear)
        self.detection_label = QLabel()
        self.detection_label.setObjectName("hintLabel")
        self.clip_check = QCheckBox("只下載片段：")
        self.clip_check.setToolTip(
            "只下載影片中的一段（例如從演唱會或節目中截出一首歌），一次用於一部影片。\n"
            "時間格式：1:30、1:02:30 或秒數；開始留白表示從頭，結束留白表示到結尾。\n"
            "檔名會加上「（片段 開始-結束）」；MP4 的開頭可能提早 1～2 秒（從最近的關鍵畫面開始）。\n"
            "加入佇列後會自動取消勾選。")
        self.clip_start_edit = QLineEdit()
        self.clip_start_edit.setPlaceholderText("開始 0:00")
        self.clip_end_edit = QLineEdit()
        self.clip_end_edit.setPlaceholderText("結束（結尾）")
        for edit in (self.clip_start_edit, self.clip_end_edit):
            edit.setFixedWidth(96)
            edit.setEnabled(False)
            edit.returnPressed.connect(self.add_from_input)
        self.clip_check.toggled.connect(self._on_clip_toggled)
        row.addWidget(paste_button)
        row.addWidget(clear_button)
        row.addSpacing(16)
        row.addWidget(self.clip_check)
        row.addWidget(self.clip_start_edit)
        row.addWidget(QLabel("～"))
        row.addWidget(self.clip_end_edit)
        row.addStretch(1)
        row.addWidget(self.detection_label)
        url_layout.addLayout(row)
        root.addWidget(url_group)

        # ---- 格式與儲存位置 ----
        fmt_group = QGroupBox("下載格式與儲存位置")
        fmt_layout = QHBoxLayout(fmt_group)
        self.mp4_radio = QRadioButton("MP4 影片")
        self.mp3_radio = QRadioButton("MP3 音訊")
        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.mp4_radio)
        self.format_group.addButton(self.mp3_radio)
        self.mp4_radio.toggled.connect(self._refresh_quality_combo)
        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(150)
        self.subtitles_check = QCheckBox("下載字幕")
        self.subtitles_check.setToolTip("MP4 一併下載字幕，存成與影片同名的 .srt 檔（播放器會自動載入）。\n"
                                        "優先順序：繁體中文 → 中文 → 簡體中文 → 英文；\n"
                                        "影片沒有提供字幕時，使用 YouTube 自動產生的字幕。\n"
                                        "對尚未開始下載的任務也會生效。")
        self.subtitles_check.toggled.connect(self._on_subtitles_toggled)
        self.folder_edit = QLineEdit()
        browse = QPushButton("瀏覽…")
        browse.clicked.connect(self._browse_folder)
        self.add_button = QPushButton("加入佇列")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setShortcut(QKeySequence("Ctrl+Return"))
        self.add_button.clicked.connect(self.add_from_input)
        fmt_layout.addWidget(self.mp4_radio)
        fmt_layout.addWidget(self.mp3_radio)
        fmt_layout.addWidget(QLabel("品質："))
        fmt_layout.addWidget(self.quality_combo)
        fmt_layout.addWidget(self.subtitles_check)
        fmt_layout.addSpacing(16)
        fmt_layout.addWidget(QLabel("儲存至："))
        fmt_layout.addWidget(self.folder_edit, 1)
        fmt_layout.addWidget(browse)
        fmt_layout.addSpacing(8)
        fmt_layout.addWidget(self.add_button)
        root.addWidget(fmt_group)

        # ---- 佇列 ----
        self.table = QueueTableView()
        self.table.actionTriggered.connect(self._on_row_action)
        self.table.doubleClicked.connect(lambda index: self.play(self.table.queue_model.task_at(index.row())))
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().currentRowChanged.connect(lambda *_: self._update_details())
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_queue_controls())
        delete = QAction(self.table)
        delete.setShortcut(QKeySequence.StandardKey.Delete)
        delete.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        delete.triggered.connect(self.remove_selected)
        self.table.addAction(delete)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("選取任務以檢視詳細資訊與錯誤訊息")
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # ---- 佇列控制 ----
        controls = QHBoxLayout()
        self.pause_button = QPushButton()
        self.pause_button.clicked.connect(self._toggle_pause)
        self.cancel_all_button = QPushButton("全部取消")
        self.cancel_all_button.setObjectName("dangerButton")
        self.cancel_all_button.clicked.connect(self.cancel_all)
        self.retry_button = QPushButton("重試失敗任務")
        self.retry_button.clicked.connect(self._retry_failed)
        self.clear_button = QPushButton("清除已完成")
        self.clear_button.clicked.connect(self._clear_completed)
        self.remove_button = QPushButton("移除所選")
        self.remove_button.setToolTip("按住 Ctrl / Shift 可多選，Ctrl+A 全選；快捷鍵 Delete。\n"
                                      "只從佇列移除紀錄，不會刪除已下載的檔案；進行中的任務需先取消。")
        self.remove_button.clicked.connect(self.remove_selected)
        self.overall_label = QLabel()
        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 1000)
        self.overall_bar.setFixedWidth(260)
        self.overall_bar.setFormat("整體 %p%")
        self.overall_bar.setToolTip("完成、下載中與等待中任務的整體進度（不含失敗與取消的任務）")
        for w in (self.pause_button, self.cancel_all_button, self.retry_button, self.clear_button,
                  self.remove_button):
            controls.addWidget(w)
        controls.addStretch(1)
        controls.addWidget(self.overall_label)
        controls.addWidget(self.overall_bar)
        root.addLayout(controls)

        self.setCentralWidget(central)
        self.speed_label = QLabel()
        self.statusBar().addPermanentWidget(self.speed_label)
        self._update_queue_controls()

    # ================= 設定 =================
    def _apply_settings_to_ui(self, previous: AppSettings | None = None) -> None:
        """套用設定到主視窗；有 previous 時只更新有變更的項目，保留使用者在主視窗目前的選擇。"""
        s = self.ctx.settings
        format_changed = previous is None or s.default_format != previous.default_format
        if format_changed:
            (self.mp3_radio if s.default_format == MediaFormat.MP3.value else self.mp4_radio).setChecked(True)
        fmt = self.selected_format()
        if format_changed or s.default_quality_for(fmt) != previous.default_quality_for(fmt):  # type: ignore[union-attr]
            self._refresh_quality_combo()
        if previous is None or s.download_dir != previous.download_dir:
            self.folder_edit.setText(s.download_dir)
        self.subtitles_check.blockSignals(True)
        self.subtitles_check.setChecked(s.download_subtitles)
        self.subtitles_check.blockSignals(False)

    def selected_format(self) -> MediaFormat:
        return MediaFormat.MP3 if self.mp3_radio.isChecked() else MediaFormat.MP4

    def _on_subtitles_toggled(self, checked: bool) -> None:
        if checked != self.ctx.settings.download_subtitles:
            self.ctx.apply_settings(dataclasses.replace(self.ctx.settings, download_subtitles=checked))

    def _refresh_quality_combo(self) -> None:
        fmt = self.selected_format()
        self.subtitles_check.setVisible(fmt is MediaFormat.MP4)
        self.quality_combo.clear()
        for key, label in quality_options(fmt).items():
            self.quality_combo.addItem(label, key)
        default = self.ctx.settings.default_quality_for(fmt)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(default)))
        tip = ("目標解析度；原始影片沒有該解析度時會取得最接近的較低解析度，並在佇列中標示實際結果。"
               if fmt is MediaFormat.MP4 else
               "目標 MP3 位元率；若原始音源位元率較低，提高輸出位元率不會提升實際音質，佇列中會標示原始音源位元率。")
        self.quality_combo.setToolTip(tip)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.ctx.settings, self)
        if dialog.exec():
            previous = self.ctx.settings
            self.ctx.apply_settings(dialog.result_settings())
            self._apply_settings_to_ui(previous)
            self._refresh_dependency_banner()
            self.statusBar().showMessage("設定已儲存", 4000)

    def _browse_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "選擇下載資料夾", self.folder_edit.text() or str(Path.home()))
        if chosen:
            self.folder_edit.setText(chosen)

    # ================= 相依元件 =================
    def _refresh_dependency_banner(self) -> None:
        messages = []
        if not self.ctx.tools.available:
            messages.append("⚠ 找不到 FFmpeg / FFprobe：無法合併影音或轉換 MP3。"
                            "請至「工具 → 檢查相依元件」查看安裝方式。")
        if not self.ctx.js_runtime.available:
            messages.append("⚠ 未偵測到 Deno（JavaScript 執行環境）：部分 YouTube 格式可能無法取得。")
        self.dependency_banner.setText("\n".join(messages))
        self.dependency_banner.setVisible(bool(messages))
        if self.ctx.tools.available:
            self.statusBar().showMessage(f"FFmpeg {self.ctx.tools.ffmpeg_version}（{self.ctx.tools.source}）", 5000)

    def dependency_report(self) -> str:
        tools = self.ctx.refresh_tools()
        js = self.ctx.js_runtime
        lines = []
        if tools.available:
            lines.append(f"✔ FFmpeg {tools.ffmpeg_version}（{tools.source}）\n   {tools.ffmpeg}\n   {tools.ffprobe}")
        else:
            lines.append("✘ " + converter.FFMPEG_INSTALL_GUIDE + "\n\n已搜尋：\n   " + "\n   ".join(tools.searched))
        if js.available:
            lines.append(f"✔ JavaScript 執行環境：{js.name}（{js.source}）\n   {js.path or ''}")
        else:
            lines.append("✘ " + converter.JS_RUNTIME_GUIDE)
        lines.append(f"YouTube 登入資訊（cookies）：{self.ctx.settings.cookie_config().describe()}")
        try:
            import yt_dlp.version

            lines.append(f"yt-dlp 版本：{yt_dlp.version.__version__}")
        except Exception:
            log.debug("無法取得 yt-dlp 版本", exc_info=True)
        return "\n\n".join(lines)

    def show_dependency_report(self) -> None:
        report = self.dependency_report()
        self._refresh_dependency_banner()
        QMessageBox.information(self, "相依元件檢查", report)

    # ================= 新版本提醒與自動更新 =================
    def check_for_updates(self, manual: bool = False) -> None:
        """在背景向 GitHub 查詢最新正式版；manual 為使用者從選單手動檢查（開啟更新視窗顯示每一步與結果）。"""
        if manual:
            self._update_manual = True
            self._update_check_error = ""
            self._install_view = None
            self.open_update_dialog()
        if self._update_job is not None:
            return
        self._update_manual = manual
        job = BackgroundJob(updates.fetch_latest_release)
        job.signals.succeeded.connect(self._on_update_checked)
        job.signals.failed.connect(self._on_update_failed)
        self._update_job = job
        QThreadPool.globalInstance().start(job)
        self._refresh_update_dialog()

    def _on_update_checked(self, release: updates.LatestRelease | None) -> None:
        self._update_job = None
        manual = self._update_manual
        if self._closing:
            return
        if release is not None and updates.is_newer(release.version) and (
                manual or release.version != self.ctx.settings.skipped_update_version):
            if self._available_update is None or self._available_update.version != release.version:
                self._available_update, self._update_path, self._update_error = release, None, ""
            if updates.is_installed_build() and (manual or self.ctx.settings.auto_download_updates):
                self.start_update_download()
            self.show_update_banner()
        self._refresh_update_dialog()

    def _on_update_failed(self, exc: Exception) -> None:
        self._update_job = None
        message = str(exc) if isinstance(exc, updates.UpdateCheckError) else updates.OFFLINE_MESSAGE
        self._update_check_error = message
        if not self._closing:
            self._refresh_update_dialog()

    # ---- 更新視窗 ----
    def open_update_dialog(self) -> UpdateDialog:
        if self._update_dialog is None:
            self._update_dialog = UpdateDialog(self)
            self._update_dialog.actionRequested.connect(self._on_update_action)
        dialog = self._update_dialog
        dialog.show_view(self.update_view())
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _refresh_update_dialog(self) -> None:
        if self._update_dialog is not None and self._update_dialog.isVisible():
            self._update_dialog.show_view(self.update_view())

    def update_view(self) -> UpdateView:
        """更新視窗目前要顯示的狀態與說明。"""
        if self._install_view is not None:
            return self._install_view
        if self._update_job is not None:
            return UpdateView(update_dialog.CHECKING, "正在向 GitHub 查詢最新版本，請稍候…")
        if self._update_check_error:
            return UpdateView(update_dialog.CHECK_FAILED, self._update_check_error)
        release = self._available_update
        if release is None or not updates.is_newer(release.version):
            return UpdateView(update_dialog.LATEST,
                              f"目前已是最新的正式版（{__version__}）。\n\n"
                              "測試版（版本名稱含 beta）只放在 GitHub 的 Releases 頁面供試用，不會自動提醒；"
                              "正式版發布後才會通知所有使用者更新。")
        head = f"有新版本 {release.version}（目前為 {__version__}）。"
        if not updates.is_installed_build():
            return UpdateView(update_dialog.PORTABLE,
                              f"{head}\n\n免安裝版請到下載頁面下載新的 zip，解壓縮後取代舊的資料夾"
                              "（設定與紀錄存在別處，不會遺失）。")
        if self._update_path is not None:
            return UpdateView(update_dialog.READY,
                              f"新版本 {release.version} 已下載完成，並通過檢查碼驗證。\n\n"
                              "按「立即安裝並重新開啟」後，程式會先關閉，接著出現安裝進度視窗，"
                              "安裝完成後自動重新開啟新版。設定、佇列與歷史紀錄都會保留。")
        if self.update_downloading():
            return UpdateView(update_dialog.DOWNLOADING,
                              f"{head}\n\n正在下載安裝程式… 可以先關閉這個視窗，下載會在背景繼續，"
                              "完成後視窗上方會出現「立即安裝並重新開啟」。", self._update_progress)
        if self._update_error:
            return UpdateView(update_dialog.DOWNLOAD_FAILED,
                              f"{self._update_error}\n\n可以按「重試」，或到下載頁面手動下載安裝程式。")
        return UpdateView(update_dialog.AVAILABLE,
                          f"{head}YouTube 改版時舊版可能無法下載，建議更新。\n\n"
                          "按「下載並安裝」會先下載並驗證安裝程式，完成後再由您決定何時安裝。")

    def _on_update_action(self, action: str) -> None:
        if action == "retry_check":
            self.check_for_updates(manual=True)
        elif action == "download":
            self.start_update_download()
            self.show_update_banner()
            self._refresh_update_dialog()
        elif action == "cancel":
            if self._update_cancel is not None:
                self._update_cancel.set()
        elif action == "install":
            self.install_update()
        elif action == "page":
            QDesktopServices.openUrl(QUrl(updates.RELEASES_PAGE))
        elif action == "copy":
            text = f"{self._install_view.message if self._install_view else ''}\n\n{self._install_details}".strip()
            QGuiApplication.clipboard().setText(text)
            self._last_clipboard = text  # 不要被當成貼上的網址
            button = self._update_dialog.button_widgets.get("copy") if self._update_dialog else None
            if button is not None:
                button.setText("已複製 ✓")

    def update_downloading(self) -> bool:
        return self._update_thread is not None and self._update_thread.is_alive()

    def start_update_download(self) -> bool:
        """在背景下載並驗證新版安裝程式；完成後顯示「立即安裝並重新開啟」。"""
        release = self._available_update
        if release is None or self.update_downloading() or self._update_path is not None:
            return False
        self._update_cancel = threading.Event()
        self._update_error, self._update_progress = "", 0.0
        signals, cancel = self._update_signals, self._update_cancel

        def work() -> None:
            try:
                path = updates.download_update(release, on_progress=signals.progress.emit, cancel=cancel)
            except updates.UpdateCancelledError as exc:
                signals.finished.emit(exc)
            except updates.UpdateError as exc:
                signals.finished.emit(exc)
            except Exception as exc:  # 意外錯誤也只顯示給使用者，不影響程式
                log.exception("下載更新失敗")
                signals.finished.emit(updates.UpdateError(f"下載更新失敗：{exc}"))
            else:
                signals.finished.emit(path)

        self._update_thread = threading.Thread(target=work, daemon=True)
        self._update_thread.start()
        return True

    def _on_update_progress(self, pct: float) -> None:
        self._update_progress = pct
        self.show_update_banner()
        self._refresh_update_dialog()

    def _on_update_downloaded(self, result: object) -> None:
        self._update_thread = None
        if isinstance(result, Path):
            self._update_path = result
        elif not isinstance(result, updates.UpdateCancelledError):
            self._update_error = str(result)
        if not self._closing:
            self.show_update_banner()
            self._refresh_update_dialog()

    def show_update_banner(self) -> None:
        release = self._available_update
        if release is None:
            return
        version = release.version
        head = f"有新版本 <b>{version}</b>（目前為 {__version__}）。"
        skip = '<a href="skip">略過這個版本</a>'
        page = '<a href="download">前往下載頁面</a>'
        if self._update_path is not None:
            text = (f"新版本 <b>{version}</b> 已下載完成並通過檢查。　"
                    f'<a href="install">立即安裝並重新開啟</a>　{skip}')
        elif self.update_downloading():
            text = f'{head}正在背景下載… {self._update_progress:.0f}%　<a href="progress">顯示進度</a>'
        elif self._update_error:
            text = (f"{head}自動下載失敗：{html.escape(self._update_error)}　"
                    f'<a href="update">重試</a>　{page}　{skip}')
        elif updates.is_installed_build():
            text = f'{head}YouTube 改版時舊版可能無法下載，建議更新。　<a href="update">下載並安裝</a>　{page}　{skip}'
        else:
            text = f"{head}免安裝版請下載新的 zip，解壓縮後取代舊的資料夾。　{page}　{skip}"
        self.update_banner.setText(text)
        self.update_banner.show()

    def check_previous_update(self) -> None:
        """上次啟動了自動更新：開啟程式後直接顯示更新成功或失敗（含原因），使用者不需要自己看記錄檔。"""
        pending = self.ctx.settings.pending_update_version
        if not pending:
            return
        self.ctx.apply_settings(dataclasses.replace(self.ctx.settings, pending_update_version=""))
        if not updates.is_newer(pending):
            self._install_view = UpdateView(update_dialog.UPDATED,
                                            f"已成功更新到 {APP_NAME} {__version__}。\n\n"
                                            "設定、下載佇列與歷史紀錄都已保留。")
            self.statusBar().showMessage(f"已更新到 {APP_DISPLAY_NAME}", 10000)
        else:
            reason, self._install_details = updates.summarize_install_log()
            log.warning("自動更新到 %s 沒有完成（目前 %s）：%s", pending, __version__, reason)
            self._install_view = UpdateView(
                update_dialog.INSTALL_FAILED,
                f"上次要更新到 {pending}，但沒有完成（目前仍是 {__version__}）。\n\n原因：{reason}\n\n"
                "請按「下載安裝程式手動更新」，下載後執行即可（設定與紀錄不會遺失）。"
                "若問題持續，可按「複製詳細資訊」貼給開發者。")
            self.update_banner.setText(
                f"上次自動更新到 <b>{pending}</b> 沒有完成（目前仍是 {__version__}）。　"
                '<a href="details">查看原因</a>　<a href="download">前往下載頁面</a>')
            self.update_banner.show()
        QTimer.singleShot(300, self.open_update_dialog)  # 主視窗顯示後再開啟

    def _on_update_link(self, link: str) -> None:
        if link == "details":
            self.open_update_dialog()
        elif link == "download":
            QDesktopServices.openUrl(QUrl(updates.RELEASES_PAGE))
        elif link == "update":
            self.start_update_download()
            self.show_update_banner()
            self.open_update_dialog()
        elif link == "progress":
            self.open_update_dialog()
        elif link == "install":
            self.install_update()
        elif link == "skip" and self._available_update is not None:
            if self._update_cancel is not None:
                self._update_cancel.set()
            self.ctx.apply_settings(dataclasses.replace(self.ctx.settings,
                                                        skipped_update_version=self._available_update.version))
            self.update_banner.hide()

    def install_update(self) -> bool:
        """關閉程式並執行已驗證的新版安裝程式（安裝完成後由安裝程式重新開啟本程式）。"""
        setup, release = self._update_path, self._available_update
        if setup is None or release is None or not setup.is_file():
            return False
        if self._convert_dialog is not None and self._convert_dialog.is_running():
            QMessageBox.information(self, "安裝更新", "本機檔案轉 MP3 仍在進行中，請等轉檔完成或取消後再安裝更新。")
            return False
        message = f"程式將關閉並安裝 {APP_NAME} {release.version}，安裝完成後會自動重新開啟。"
        if self.ctx.queue.has_active_tasks():
            message += "\n\n目前進行中的下載會中斷，重新開啟後會排回佇列繼續下載。"
        if QMessageBox.question(self, "安裝更新", message) != QMessageBox.StandardButton.Yes:
            return False
        # 記下正在更新的版本：下次啟動時比對版本，顯示更新成功或失敗
        self.ctx.apply_settings(dataclasses.replace(self.ctx.settings, pending_update_version=release.version))
        self._install_view = UpdateView(update_dialog.INSTALLING,
                                        f"正在啟動 {release.version} 的安裝程式…\n\n"
                                        "程式會自動關閉，接著出現安裝進度視窗；"
                                        "安裝完成後會自動重新開啟新版，並告訴您是否更新成功。")
        self.open_update_dialog()
        QApplication.processEvents()
        try:
            updates.launch_installer(setup)
        except (OSError, updates.UpdateError) as exc:
            self.ctx.apply_settings(dataclasses.replace(self.ctx.settings, pending_update_version=""))
            self._install_details = ""
            self._install_view = UpdateView(update_dialog.INSTALL_FAILED,
                                            f"無法啟動安裝程式：{exc}\n\n"
                                            "請按「下載安裝程式手動更新」，下載後執行即可。")
            self._refresh_update_dialog()
            return False
        self._closing_for_update = True
        self.close()
        return True

    def _show_about(self) -> None:
        QMessageBox.about(self, "關於", f"<b>{APP_NAME}</b><br>版本 {__version__}<br><br>"
                          + DISCLAIMER.replace("\n", "<br>"))

    # ================= 網址處理 =================
    def _append_urls(self, text: str) -> None:
        current = self.url_input.toPlainText().rstrip()
        self.url_input.setPlainText(f"{current}\n{text}".strip() if current else text.strip())

    def _on_clipboard_changed(self) -> None:
        if QGuiApplication.applicationState() == Qt.ApplicationState.ApplicationActive:
            # 在本程式中複製的（例如右鍵「複製網址」）：記為已處理，切回程式時不再帶入
            self._last_clipboard = QGuiApplication.clipboard().text()

    def _on_application_state_changed(self, state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            self.auto_paste_clipboard()

    def auto_paste_clipboard(self) -> int:
        """把剪貼簿中新的 YouTube 網址附加到輸入框（不自動加入佇列）。回傳帶入的網址數。"""
        if not self.ctx.settings.auto_paste_clipboard or self._closing:
            return 0
        text = QGuiApplication.clipboard().text()
        if not text or text == self._last_clipboard or len(text) > 100_000:
            return 0
        self._last_clipboard = text
        present = {p.dedupe_key for p in parse_urls(self.url_input.toPlainText()).valid}
        queued = {t.url for t in self.ctx.queue.tasks()}
        new = [p.original for p in parse_urls(text).valid
               if p.dedupe_key not in present and (p.video_url or p.playlist_url) not in queued]
        if not new:
            return 0
        self._append_urls("\n".join(new))
        self.statusBar().showMessage(f"已從剪貼簿帶入 {len(new)} 個網址，按「加入佇列」開始下載（可在設定關閉）", 8000)
        return len(new)

    def _paste_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text()
        if text:
            self._append_urls(text)

    @staticmethod
    def _dropped_text(mime) -> str:
        if mime.hasUrls():
            return "\n".join(u.toString() for u in mime.urls() if u.scheme() in ("http", "https"))
        return mime.text() if mime.hasText() else ""

    @staticmethod
    def _dropped_media_files(mime) -> list[Path]:
        if not mime.hasUrls():
            return []
        return [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile() and is_media_file(Path(u.toLocalFile()))]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._dropped_text(event.mimeData()).strip() or self._dropped_media_files(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        files = self._dropped_media_files(event.mimeData())
        if files:
            # 拖進來的是電腦裡的影音檔：開啟「本機檔案轉 MP3」
            event.acceptProposedAction()
            self.open_converter(files)
            return
        text = self._dropped_text(event.mimeData()).strip()
        if not text:
            return
        event.acceptProposedAction()
        self._append_urls(text)
        self.url_input.setFocus()
        count = len(parse_urls(text).valid)
        message = (f"已加入 {count} 個網址到輸入框，按「加入佇列」開始下載" if count
                   else "拖曳的內容中沒有可辨識的 YouTube 網址")
        self.statusBar().showMessage(message, 6000)

    def _update_detection_summary(self) -> None:
        result = parse_urls(self.url_input.toPlainText())
        if not result.valid and not result.invalid:
            self.detection_label.clear()
            return
        counts: dict[str, int] = {}
        for item in result.valid:
            counts[item.kind.label] = counts.get(item.kind.label, 0) + 1
        parts = [f"{label} {n}" for label, n in counts.items()]
        if result.invalid:
            parts.append(f"不支援 {len(result.invalid)}")
        if result.duplicates:
            parts.append(f"重複 {len(result.duplicates)}")
        self.detection_label.setText("偵測到：" + "、".join(parts))

    def _on_clip_toggled(self, checked: bool) -> None:
        for edit in (self.clip_start_edit, self.clip_end_edit):
            edit.setEnabled(checked)
        if checked:
            self.clip_start_edit.setFocus()

    def _reset_clip(self) -> None:
        self.clip_check.setChecked(False)
        self.clip_start_edit.clear()
        self.clip_end_edit.clear()

    def clip_range(self) -> tuple[float | None, float | None] | None:
        """「只下載片段」的時間範圍；未勾選時回傳 None。格式錯誤時 ValueError（訊息可直接顯示）。"""
        if not self.clip_check.isChecked():
            return None
        start = parse_clock(self.clip_start_edit.text())
        end = parse_clock(self.clip_end_edit.text())
        if start is None and end is None:
            raise ValueError("請輸入片段的開始或結束時間（例如 1:30），或取消勾選「只下載片段」。")
        if start is not None and end is not None and end <= start:
            raise ValueError("片段的結束時間必須晚於開始時間。")
        if start == 0:
            start = None
        return start, end

    def _ensure_output_dir(self) -> str | None:
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "下載資料夾", "請先選擇下載資料夾。")
            return None
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "下載資料夾", f"無法使用此資料夾：\n{folder}\n\n{explain_error(exc)}")
            return None
        folder = str(Path(folder))
        if folder != self.ctx.settings.download_dir:
            # 記住使用者選的資料夾，下次開啟程式時沿用
            self.ctx.apply_settings(dataclasses.replace(self.ctx.settings, download_dir=folder))
        return folder

    def add_from_input(self) -> None:
        if self._busy_expanding:
            return
        result = parse_urls(self.url_input.toPlainText())
        notes: list[str] = []
        if result.invalid:
            notes.append("以下網址不支援：\n"
                         + "\n".join(f"• {i.original}\n   原因：{i.reason}" for i in result.invalid))
        if result.duplicates:
            notes.append(f"已略過 {len(result.duplicates)} 個重複網址。")
        if not result.valid:
            QMessageBox.warning(self, "無法加入", "\n\n".join(notes) or "請先輸入 YouTube 網址。")
            return
        try:
            clip = self.clip_range()
        except ValueError as exc:
            QMessageBox.warning(self, "只下載片段", str(exc))
            return
        if clip is not None and (len(result.valid) != 1 or result.valid[0].kind is UrlKind.PLAYLIST):
            QMessageBox.warning(self, "只下載片段",
                                "「只下載片段」一次只能用於一部影片（不能用於整個播放清單）。\n"
                                "請只貼上一個影片網址，或取消勾選「只下載片段」。")
            return
        if not self.ctx.current_tools().available:
            self._refresh_dependency_banner()
            QMessageBox.warning(self, "缺少 FFmpeg", converter.FFMPEG_INSTALL_GUIDE)
            return
        output_dir = self._ensure_output_dir()
        if output_dir is None:
            return

        singles: list[str] = []
        playlists: list[ParsedUrl] = []
        for item in result.valid:
            if item.kind in (UrlKind.PLAYLIST, UrlKind.VIDEO_IN_PLAYLIST):
                playlists.append(item)  # 讀取清單後讓使用者勾選要下載的影片
            else:
                singles.append(item.video_url)  # type: ignore[arg-type]

        fmt, quality = self.selected_format(), self.quality_combo.currentData()
        if clip is not None:
            # 片段：只下載貼上的那一部影片（網址含播放清單時也不展開清單）
            if self._finish_add([result.valid[0].video_url], fmt, quality, output_dir, notes,  # type: ignore[list-item]
                                clip=clip):
                self._reset_clip()
            return
        if playlists:
            self._expand_playlists(playlists, singles, fmt, quality, output_dir, notes)
        else:
            self._finish_add(singles, fmt, quality, output_dir, notes)

    def _expand_playlists(self, playlists: list[ParsedUrl], singles: list[str], fmt: MediaFormat,
                          quality: str, output_dir: str, notes: list[str]) -> None:
        downloader = self.ctx.downloader

        def work() -> list[tuple[ParsedUrl, PlaylistInfo | Exception]]:
            results: list[tuple[ParsedUrl, PlaylistInfo | Exception]] = []
            for item in playlists:
                try:
                    results.append((item, downloader.extract_playlist(item.playlist_source_url, MAX_PLAYLIST_ITEMS)))
                except Exception as exc:  # noqa: BLE001
                    results.append((item, exc))
            return results

        self._set_expanding(True)
        self._expand_context = (singles, fmt, quality, output_dir, notes)
        job = BackgroundJob(work)
        # 連接到 QObject 的方法（而非 lambda），確保結果在主執行緒處理；並保留 job 參照直到完成
        job.signals.succeeded.connect(self._on_playlists_expanded)
        job.signals.failed.connect(self._on_playlists_failed)
        self._jobs.add(job)
        QThreadPool.globalInstance().start(job)

    def _on_playlists_failed(self, exc: Exception) -> None:
        self._jobs.clear()
        self._set_expanding(False)
        QMessageBox.warning(self, "播放清單", explain_error(exc))

    def _set_expanding(self, busy: bool) -> None:
        self._busy_expanding = busy
        self.add_button.setEnabled(not busy)
        self.add_button.setText("讀取播放清單中…" if busy else "加入佇列")
        if busy:
            self.statusBar().showMessage("正在讀取播放清單內容…")
        else:
            self.statusBar().clearMessage()

    def _on_playlists_expanded(self, results) -> None:
        self._jobs.clear()
        self._set_expanding(False)
        singles, fmt, quality, output_dir, notes = self._expand_context
        if self._closing:
            return
        groups: list[PlaylistGroup] = []
        for item, outcome in results:
            if isinstance(outcome, Exception):
                notes.append(f"• 無法讀取播放清單 {item.original}\n   {explain_error(outcome)}")
                if item.kind is UrlKind.VIDEO_IN_PLAYLIST:
                    singles.append(item.video_url)
                continue
            title = outcome.title or item.playlist_id or ""
            entries = list(outcome.entries)
            preselect = item.video_id if item.kind is UrlKind.VIDEO_IN_PLAYLIST else None
            if preselect and not any(e.video_id == preselect for e in entries):
                # 貼上的影片不在讀到的清單中（例如超過上限）：放在最前面，避免使用者想要的影片消失
                entries.insert(0, PlaylistEntry(item.video_url or "", PASTED_VIDEO_TITLE, preselect))
            if not entries:
                notes.append(f"• 播放清單「{title}」中沒有可下載的影片。")
                continue
            groups.append(PlaylistGroup(title, entries, preselect, outcome.truncated))
        index = self.downloaded_index() if groups else None
        for group in groups:
            group.names = {e.url: self.planned_name(e, fmt) for e in group.entries if e.title != PASTED_VIDEO_TITLE}
            for entry in group.entries:
                found = index.find(entry.url, fmt) if index is not None else None
                if found is not None:
                    group.downloaded[entry.url] = str(found)
        folders: dict[str, str] = {}
        titles = {e.url: e.title for g in groups for e in g.entries if e.title and e.title != PASTED_VIDEO_TITLE}
        picked: set[str] = set()
        if groups:
            self._custom_names = {}
            chosen = self.choose_playlist_entries(groups, output_dir)
            if chosen is None:
                notes.append("已取消加入播放清單中的影片。")
            else:
                for group, urls in zip(groups, chosen, strict=True):
                    folder = self._playlist_folder(output_dir, group, urls)
                    for url in urls:
                        singles.append(url)
                        picked.add(url)
                        if folder:
                            folders.setdefault(url, folder)
                    if self.ctx.settings.playlist_m3u:
                        self._add_playlist_batch(group, urls, folder or output_dir, fmt)
        self._finish_add(singles, fmt, quality, output_dir, notes, folders=folders, titles=titles,
                         names=self._custom_names, confirmed=picked)

    def downloaded_index(self) -> DownloadedIndex:
        try:
            return DownloadedIndex(self.ctx.db.completed_downloads())
        except Exception:  # 判斷「已下載過」只是輔助功能，失敗時當作都沒下載過
            log.warning("無法讀取下載紀錄", exc_info=True)
            return DownloadedIndex([])

    def planned_name(self, entry: PlaylistEntry, fmt: MediaFormat) -> str:
        """選歌視窗顯示的預計檔名（與下載時的歌名整理規則相同；下載時有 YouTube 歌曲資訊會以其為準）。"""
        if not entry.title:
            return ""
        if self.ctx.settings.clean_titles:
            cleaned = clean_title({"title": entry.title, "channel": entry.channel},
                                  channel_fallback=fmt is MediaFormat.MP3)
            if cleaned is not None:
                return sanitize_filename(cleaned.display)
        return sanitize_filename(entry.title)

    def _add_playlist_batch(self, group: PlaylistGroup, urls: list[str], folder: str, fmt: MediaFormat) -> None:
        """記錄播放清單檔（.m3u8）批次；同一個資料夾中已下載過的歌也列入，清單才會完整（播放清單同步）。"""
        chosen = set(urls)
        known = {}
        for url, path in group.downloaded.items():
            if url not in chosen and same_folder(str(Path(path).parent), folder):
                known[url] = Path(path).name
        ordered = [e.url for e in group.entries if e.url in chosen or e.url in known]
        try:
            self._playlist_files.add_batch(folder, group.title, fmt.value, ordered, known_files=known)
        except Exception:
            log.warning("無法記錄播放清單檔", exc_info=True)

    def _playlist_folder(self, output_dir: str, group: PlaylistGroup, urls: list[str]) -> str | None:
        """播放清單的影片存到以清單名稱命名的子資料夾；只下載貼上的那一支影片時不另建資料夾。"""
        if not self.ctx.settings.playlist_subfolder or not urls:
            return None
        if group.preselect_video_id and len(urls) == 1:
            entry = next((e for e in group.entries if e.url == urls[0]), None)
            if entry is not None and entry.video_id == group.preselect_video_id:
                return None
        # YouTube 合輯的標題是「Mix - <第一首的完整標題>」：整理成「合輯 - 演出者 - 歌名」當資料夾名稱
        return str(Path(output_dir) / sanitize_filename(clean_playlist_title(group.title) or "播放清單"))

    def choose_playlist_entries(self, groups: list[PlaylistGroup], output_dir: str = "") -> list[list[str]] | None:
        """顯示播放清單選擇對話框；依清單回傳勾選的影片網址，取消時回傳 None。"""
        folder = output_dir or self.folder_edit.text()
        if self.ctx.settings.playlist_subfolder:
            destination = f"儲存位置：{Path(folder) / '（清單名稱）'}（只下載貼上的那一支時存在 {folder}）"
        else:
            destination = f"儲存位置：{folder}"
        dialog = PlaylistPickerDialog(groups, MAX_PLAYLIST_ITEMS, self, destination=destination)
        if not dialog.exec():
            return None
        self._custom_names = dialog.custom_names()
        return dialog.selected_by_group()

    def open_converter(self, files: list[Path] | None = None) -> ConvertDialog:
        """開啟「本機檔案轉 MP3」（非強制回應視窗，轉檔時仍可操作主視窗）。"""
        if self._convert_dialog is None or not self._convert_dialog.isVisible():
            self._convert_dialog = ConvertDialog(self.ctx.current_tools(), self.ctx.settings.default_mp3_quality, self)
        dialog = self._convert_dialog
        if files and not dialog.is_running():
            dialog.add_files(files)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def open_rename_dialog(self) -> RenameDialog:
        """整理舊檔案的歌名（預設掃描目前的下載資料夾）。"""
        dialog = RenameDialog(self.folder_edit.text(), self, on_renamed=self.on_files_renamed)
        dialog.show()
        dialog.scan()
        return dialog

    def on_files_renamed(self, pairs: list[tuple[Path, Path]]) -> None:
        """檔案改名後同步佇列、歷史紀錄與播放清單紀錄中的檔名。"""
        for old, new in pairs:
            if new.is_dir():
                self._on_folder_renamed(old, new)
                continue
            self.ctx.queue.rename_output_path(str(old), str(new))
            try:
                self._playlist_files.rename_file(str(old.parent), old.name, new.name)
            except Exception:  # 播放清單紀錄只是附加資訊
                log.warning("無法更新播放清單紀錄", exc_info=True)
        self._update_details()

    def _on_folder_renamed(self, old: Path, new: Path) -> None:
        self.ctx.queue.rename_folder(str(old), str(new))
        try:
            self._playlist_files.rename_folder(str(old), str(new))
        except Exception:
            log.warning("無法更新播放清單紀錄", exc_info=True)
        moved = replace_path_prefix(self.folder_edit.text(), str(old), str(new))
        if moved:  # 「儲存至」就是（或位於）被改名的資料夾
            self.folder_edit.setText(moved)
        saved = replace_path_prefix(self.ctx.settings.download_dir, str(old), str(new))
        if saved:
            self.ctx.apply_settings(dataclasses.replace(self.ctx.settings, download_dir=saved))

    def open_history(self) -> None:
        HistoryDialog(self.ctx.db, self, on_redownload=self.redownload).exec()

    def redownload(self, url: str, fmt: MediaFormat, quality: str, title: str = "") -> list[DownloadTask]:
        """從歷史紀錄重新下載：以相同格式與品質加入佇列，存到目前的下載資料夾。"""
        if not self.ctx.current_tools().available:
            self._refresh_dependency_banner()
            QMessageBox.warning(self, "缺少 FFmpeg", converter.FFMPEG_INSTALL_GUIDE)
            return []
        output_dir = self._ensure_output_dir()
        if output_dir is None:
            return []
        return self._finish_add([url], fmt, quality, output_dir, [], clear_input=False,
                                titles={url: title} if title else None, check_downloaded=False)

    def _finish_add(self, urls: list[str], fmt: MediaFormat, quality: str, output_dir: str,
                    notes: list[str], clear_input: bool = True, folders: dict[str, str] | None = None,
                    titles: dict[str, str] | None = None, names: dict[str, str] | None = None,
                    clip: tuple[float | None, float | None] | None = None, check_downloaded: bool = True,
                    confirmed: set[str] | None = None) -> list[DownloadTask]:
        """加入佇列；folders 可為個別網址指定儲存資料夾（例如播放清單子資料夾），
        titles 為已知的影片名稱（下載開始前就能在佇列中顯示，開始下載後以實際名稱更新），
        names 為使用者修改過的檔名，clip 為只下載片段的（開始, 結束）秒數。
        check_downloaded：已下載過（檔案還在）的影片先詢問；confirmed 中的網址（已在選歌視窗確認）不再詢問。"""
        clip_start, clip_end = clip or (None, None)
        # 去除重複（播放清單展開後可能與單一網址重複）並略過佇列中尚未完成的相同任務
        existing = {(t.url, t.media_format, t.quality, t.output_dir, t.clip_start, t.clip_end)
                    for t in self.ctx.queue.tasks() if not t.status.is_finished}
        seen: set[str] = set()
        specs: list[TaskSpec] = []
        skipped = 0
        for url in urls:
            parsed = parse_urls(url).valid
            key = parsed[0].dedupe_key if parsed else url
            if key in seen:
                continue
            seen.add(key)
            target = (folders or {}).get(url, output_dir)
            if (url, fmt, quality, target, clip_start, clip_end) in existing:
                skipped += 1
                continue
            specs.append(TaskSpec(url=url, media_format=fmt, quality=quality, output_dir=target,
                                  title=(titles or {}).get(url, ""), file_name=(names or {}).get(url, ""),
                                  clip_start=clip_start, clip_end=clip_end))
        if skipped:
            notes.append(f"已略過 {skipped} 個已在佇列中的相同任務。")
        if check_downloaded and clip is None and specs:
            unchecked = [s for s in specs if s.url not in (confirmed or set())]
            if unchecked:
                decided = self._confirm_already_downloaded(unchecked, fmt)
                if decided is None:
                    return []
                specs = [s for s in specs if s not in decided]
                if decided:
                    notes.append(f"已略過 {len(decided)} 部已經下載過的影片。")
        added = self.ctx.queue.add_tasks(specs) if specs else []
        if added:
            if clear_input:
                self.url_input.clear()
            self.statusBar().showMessage(f"已加入 {len(added)} 筆任務", 5000)
            if self.ctx.queue.is_paused and not self.ctx.queue.has_active_tasks():
                self.statusBar().showMessage(
                    f"已加入 {len(added)} 筆任務（佇列目前暫停中，按「開始佇列」開始下載）", 8000)
        if notes:
            QMessageBox.information(self, "加入佇列", "\n\n".join(notes))
        return added

    def _confirm_already_downloaded(self, specs: list[TaskSpec], fmt: MediaFormat) -> list[TaskSpec] | None:
        """已下載過（同格式、檔案還在）的影片先詢問。回傳要略過的任務；按「取消」時回傳 None。"""
        index = self.downloaded_index()
        found = [(s, index.find(s.url, fmt)) for s in specs]
        found = [(s, path) for s, path in found if path is not None]
        if not found:
            return []
        answer = self.ask_already_downloaded([path for _, path in found], fmt)
        if answer == "skip":
            return [s for s, _ in found]
        return [] if answer == "again" else None

    def ask_already_downloaded(self, files: list[Path], fmt: MediaFormat) -> str | None:
        """詢問已下載過的影片要怎麼處理：回傳 "skip"（略過）、"again"（仍要下載）或 None（取消加入）。"""
        listed = "\n".join(f"• {path.name}" for path in files[:5])
        more = f"\n…等共 {len(files)} 部" if len(files) > 5 else ""
        box = QMessageBox(QMessageBox.Icon.Question, "已經下載過",
                          f"以下 {len(files)} 部影片之前已經下載成 {fmt.label}，檔案還在：\n\n{listed}{more}\n\n"
                          "要略過這些影片，還是再下載一次？（再下載一次不會覆蓋原檔，新檔名會加上編號）", parent=self)
        skip = box.addButton("略過已下載的", QMessageBox.ButtonRole.AcceptRole)
        again = box.addButton("仍要下載", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip)
        box.exec()
        clicked = box.clickedButton()
        return "skip" if clicked is skip else "again" if clicked is again else None

    # ================= 佇列操作 =================
    def _on_row_action(self, task_id: int, action: str) -> None:
        if action == ACTION_CANCEL:
            self.ctx.queue.cancel(task_id)
        elif action == ACTION_RETRY:
            self.ctx.queue.retry(task_id)
        elif action == ACTION_OPEN:
            task = self.ctx.queue.get(task_id)
            if task:
                self._reveal(task)

    def play(self, task: DownloadTask | None) -> bool:
        """雙擊已完成的任務：以預設播放器開啟檔案。"""
        if task is None or task.status is not TaskStatus.COMPLETED or not task.output_path:
            return False
        if not Path(task.output_path).is_file():
            self.statusBar().showMessage(f"檔案已不存在（可能已被移動或刪除）：{task.output_path}", 8000)
            return False
        return system_open.open_media(Path(task.output_path))

    def _reveal(self, task: DownloadTask) -> None:
        if task.output_path and Path(task.output_path).is_file():
            system_open.reveal_file(Path(task.output_path))
            return
        # 尚未開始下載的任務，資料夾（例如播放清單子資料夾）可能還沒建立：改開最近的上層資料夾
        folder = Path(task.output_dir)
        while not folder.is_dir() and folder.parent != folder:
            folder = folder.parent
        self._open_folder(str(folder if folder.is_dir() else task.output_dir))

    def _open_folder(self, folder: str) -> None:
        if not system_open.open_folder(Path(folder)):
            QMessageBox.warning(self, "開啟資料夾", f"資料夾不存在或無法開啟：\n{folder}")

    def cancel_all(self) -> None:
        if not any(not t.status.is_finished for t in self.ctx.queue.tasks()):
            return
        if QMessageBox.question(self, "全部取消", "確定要取消所有等待中與下載中的任務嗎？") \
                == QMessageBox.StandardButton.Yes:
            count = self.ctx.queue.cancel_all()
            self.statusBar().showMessage(f"已取消 {count} 筆任務", 5000)

    def _retry_failed(self) -> None:
        count = self.ctx.queue.retry_failed()
        self.statusBar().showMessage(f"已重新排入 {count} 筆失敗任務" if count else "沒有失敗的任務", 5000)

    def _clear_completed(self) -> None:
        count = self.ctx.queue.clear_completed()
        self.statusBar().showMessage(f"已清除 {count} 筆已完成任務（檔案不受影響）", 5000)

    def _selected_tasks(self) -> list[DownloadTask]:
        return [t for tid in self.table.selected_task_ids() if (t := self.ctx.queue.get(tid)) is not None]

    def remove_selected(self) -> int:
        """從佇列移除所有選取的任務（不刪除檔案）；進行中的任務略過。回傳移除筆數。"""
        selected = self._selected_tasks()
        removable = [t for t in selected if not t.status.is_active]
        skipped = len(selected) - len(removable)
        if not removable:
            if skipped:
                self.statusBar().showMessage("選取的任務都在進行中，請先取消再移除", 6000)
            return 0
        if len(removable) > 1:
            note = f"\n（另有 {skipped} 筆進行中的任務不會移除）" if skipped else ""
            answer = QMessageBox.question(
                self, "移除任務", f"確定要從佇列移除 {len(removable)} 筆任務嗎？\n不會刪除已下載的檔案。{note}")
            if answer != QMessageBox.StandardButton.Yes:
                return 0
        removed = sum(1 for t in removable if self.ctx.queue.remove(t.id))  # type: ignore[arg-type]
        message = f"已從佇列移除 {removed} 筆任務（檔案不受影響）"
        if skipped:
            message += f"；{skipped} 筆進行中未移除"
        self.statusBar().showMessage(message, 6000)
        return removed

    def _cancel_tasks(self, tasks: list[DownloadTask]) -> None:
        count = sum(1 for t in tasks if self.ctx.queue.cancel(t.id))  # type: ignore[arg-type]
        self.statusBar().showMessage(f"已取消 {count} 筆任務", 5000)

    def _retry_tasks(self, tasks: list[DownloadTask]) -> None:
        count = sum(1 for t in tasks if self.ctx.queue.retry(t.id))  # type: ignore[arg-type]
        self.statusBar().showMessage(f"已重新排入 {count} 筆任務", 5000)

    def _toggle_pause(self) -> None:
        if self.ctx.queue.is_paused:
            self.ctx.queue.resume()
        else:
            self.ctx.queue.pause()

    def _show_context_menu(self, pos) -> None:
        task = self.table.queue_model.task_at(self.table.indexAt(pos).row())
        if task is None:
            return
        menu = self.build_context_menu(task)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def build_context_menu(self, task: DownloadTask) -> QMenu:
        selected = self._selected_tasks()
        if len(selected) > 1 and task.id in {t.id for t in selected}:
            return self._build_batch_menu(selected)
        menu = QMenu(self)
        queue = self.ctx.queue
        if not task.status.is_finished:
            menu.addAction("取消", lambda: queue.cancel(task.id))
        if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            menu.addAction("重試", lambda: queue.retry(task.id))
        if task.status is TaskStatus.COMPLETED:
            menu.addAction("播放（雙擊）", lambda: self.play(task))
        menu.addAction("開啟檔案位置", lambda: self._reveal(task))
        menu.addAction("複製網址", lambda: QGuiApplication.clipboard().setText(task.url))
        if task.status is TaskStatus.WAITING:
            menu.addSeparator()
            menu.addAction("上移", lambda: queue.move(task.id, -1))
            menu.addAction("下移", lambda: queue.move(task.id, 1))
        if not task.status.is_active:
            menu.addSeparator()
            menu.addAction("從佇列移除（不刪除檔案）", lambda: queue.remove(task.id))
        menu.addSeparator()
        menu.addAction("全選（Ctrl+A）", self.table.selectAll)
        return menu

    def _build_batch_menu(self, selected: list[DownloadTask]) -> QMenu:
        """多選時的右鍵選單：動作套用到所有選取的任務。"""
        menu = QMenu(self)
        cancellable = [t for t in selected if not t.status.is_finished]
        retryable = [t for t in selected if t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED)]
        removable = [t for t in selected if not t.status.is_active]
        if cancellable:
            menu.addAction(f"取消所選（{len(cancellable)} 筆）", lambda: self._cancel_tasks(cancellable))
        if retryable:
            menu.addAction(f"重試所選（{len(retryable)} 筆）", lambda: self._retry_tasks(retryable))
        if removable:
            menu.addSeparator()
            menu.addAction(f"從佇列移除所選（{len(removable)} 筆，不刪除檔案）", self.remove_selected)
        menu.addSeparator()
        menu.addAction("全選（Ctrl+A）", self.table.selectAll)
        return menu

    # ================= 佇列事件（主執行緒） =================
    def _on_queue_event(self, event: str, payload) -> None:
        model = self.table.queue_model
        if event in (TASK_ADDED, TASK_UPDATED, TASK_PROGRESS):
            model.upsert(payload)
        elif event == TASK_REMOVED:
            model.remove(payload)
        elif event == QUEUE_STATE:
            model.set_tasks(self.ctx.queue.tasks())
        elif event == TASK_FINISHED:
            self._on_task_finished(payload)
        current = self.table.current_task()
        if current is not None and (not isinstance(payload, DownloadTask) or payload.id == current.id):
            self._update_details()
        self._update_queue_controls()

    def _on_task_finished(self, task: DownloadTask) -> None:
        if task.status is TaskStatus.COMPLETED:
            self._last_completed_dir = task.output_dir
            self._batch_counts["completed"] += 1
            try:
                self._playlist_files.on_task_completed(task)  # 更新播放清單檔（.m3u8）
            except Exception:  # 清單檔只是附加功能，不可影響佇列
                log.warning("更新播放清單檔失敗", exc_info=True)
            self.statusBar().showMessage(f"完成：{task.display_title}", 5000)
        elif task.status is TaskStatus.FAILED:
            self._batch_counts["failed"] += 1
            self.statusBar().showMessage(f"失敗：{task.display_title}（選取任務可檢視詳細錯誤）", 8000)
        # 佇列事件以非同步方式送達：稍候再判斷是否全部結束，避免連續完成的任務被拆成多次通知
        self._idle_timer.start()
        queue = self.ctx.queue
        if (self.ctx.settings.open_folder_on_complete and self._last_completed_dir and not self._closing
                and not queue.has_active_tasks() and (queue.pending_count() == 0 or queue.is_paused)):
            system_open.open_folder(Path(self._last_completed_dir))
            self._last_completed_dir = None

    def _check_queue_idle(self) -> None:
        queue = self.ctx.queue
        if self._closing or queue.has_active_tasks() or queue.pending_count():
            return
        completed, failed = self._batch_counts["completed"], self._batch_counts["failed"]
        self._batch_counts = {"completed": 0, "failed": 0}
        if self.ctx.settings.notify_on_complete and (completed or failed):
            self.notify_queue_finished(completed, failed)

    def notify_queue_finished(self, completed: int, failed: int) -> None:
        """佇列全部下載完成：工作列圖示閃爍，並在視窗不在前景時顯示系統通知。"""
        message = f"{completed} 部下載完成" + (f"，{failed} 部失敗" if failed else "")
        self.statusBar().showMessage(f"佇列已全部完成：{message}", 10000)
        if self.isActiveWindow():
            return
        QApplication.alert(self)  # Windows：工作列圖示閃爍直到使用者切回視窗
        self._show_notification("下載完成" if not failed else "下載結束", message)

    def _show_notification(self, title: str, message: str) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self._tray is None:
            self._tray = QSystemTrayIcon(self.windowIcon(), self)
            self._tray.setToolTip(APP_DISPLAY_NAME)
            self._tray.messageClicked.connect(self._bring_to_front)
            self._tray.activated.connect(lambda *_: self._bring_to_front())
        self._tray.show()
        self._tray.showMessage(f"{APP_DISPLAY_NAME}：{title}", message, QSystemTrayIcon.MessageIcon.Information, 8000)
        # 通知顯示後收起系統匣圖示，不常駐
        QTimer.singleShot(15000, self._tray.hide)

    def _bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _update_queue_controls(self) -> None:
        queue = self.ctx.queue
        self.pause_button.setText("開始佇列" if queue.is_paused else "暫停佇列")
        self.pause_button.setToolTip("暫停後不會啟動新的任務，進行中的任務會繼續完成。")
        progress = queue.progress()
        self.overall_bar.setValue(int(progress.percent * 10))
        state = "（已暫停）" if queue.is_paused else ""
        waiting = progress.total - progress.finished - progress.active
        self.overall_label.setText(
            f"共 {progress.total} 筆：進行中 {progress.active}、等待 {waiting}、完成 {progress.completed}、"
            f"失敗 {progress.failed}、取消 {progress.cancelled}{state}")
        tasks = self.table.queue_model.tasks()
        total_speed = sum(t.speed or 0 for t in tasks if t.status.is_active)
        self.speed_label.setText(f"總下載速度：{format_speed(total_speed)}" if total_speed else "")
        self.retry_button.setEnabled(progress.failed > 0)
        self.clear_button.setEnabled(progress.completed > 0)
        selected = self.table.selected_task_ids()
        removable = sum(1 for tid in selected if (t := queue.get(tid)) is not None and not t.status.is_active)
        self.remove_button.setEnabled(removable > 0)
        self.remove_button.setText(f"移除所選（{removable}）" if removable > 1 else "移除所選")
        self.cancel_all_button.setEnabled(progress.total - progress.finished > 0)

    def _update_details(self) -> None:
        task = self.table.current_task()
        if task is None:
            self.details.clear()
            return
        lines = [f"影片名稱：{task.display_title}"]
        failed = task.status is TaskStatus.FAILED and task.error_message
        if failed:
            lines += ["", "失敗原因：", task.error_message, ""]
        lines += [
            f"網址：{task.url}",
            f"格式 / 目標品質：{task.media_format.label} {task.quality_text}",
        ]
        if task.is_clip:
            lines.append(f"只下載片段：{task.clip_text.removeprefix('片段 ')}")
        if task.file_name:
            lines.append(f"指定檔名：{task.file_name}")
        if task.actual_quality:
            lines.append(f"實際取得：{task.actual_quality}")
        lines.append(f"狀態：{task.status.label}" + (f"（{task.stage}）" if task.stage else ""))
        lines.append(f"儲存位置：{task.output_path or task.output_dir}")
        lines.append(f"建立時間：{_local_time(task.created_at)}　嘗試次數：{task.attempts}")
        if task.completed_at:
            lines.append(f"完成時間：{_local_time(task.completed_at)}")
        if task.error_message and not failed:
            lines += ["", "訊息：", task.error_message]
        self.details.setPlainText("\n".join(lines))

    # ================= 啟動與關閉 =================
    def restore_queue(self, ask: bool = True) -> int:
        """載入上次未完成的任務；有未完成任務時詢問是否繼續下載。"""
        unfinished = self.ctx.queue.restore()
        if unfinished and ask:
            answer = QMessageBox.question(
                self, "恢復未完成的佇列",
                f"上次有 {len(unfinished)} 筆未完成的下載任務，是否立即繼續下載？\n"
                "選擇「否」會保留在佇列中，之後可按「開始佇列」繼續。")
            if answer == QMessageBox.StandardButton.Yes:
                self.ctx.queue.resume()
        elif not unfinished:
            self.ctx.queue.resume()
        self._update_queue_controls()
        return len(unfinished)

    def _restore_geometry(self) -> None:
        geometry = self.ctx.db.get_setting("ui.geometry")
        if isinstance(geometry, str):
            self.restoreGeometry(QByteArray.fromHex(geometry.encode()))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return
        if self._convert_dialog is not None and self._convert_dialog.is_running():
            if not self._convert_dialog.close():  # 會詢問是否取消轉檔
                event.ignore()
                return
        if self.ctx.queue.has_active_tasks() and not self._closing_for_update:  # 安裝更新時已先確認過
            answer = QMessageBox.question(
                self, "結束程式",
                "仍有下載進行中。確定要結束嗎？\n進行中的任務會被中斷並清除暫存檔，下次開啟時會重新排入佇列。")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closing = True
        if self._update_cancel is not None:
            self._update_cancel.set()  # 停止背景下載更新（下次啟動會重新下載或沿用已驗證的檔案）
        try:
            self.ctx.db.set_setting("ui.geometry", bytes(self.saveGeometry().toHex()).decode())
        except Exception:
            log.exception("無法保存視窗位置")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage("正在停止下載並清理暫存檔…")
        QApplication.processEvents()
        try:
            finished = self.ctx.close(timeout=15.0)
            if not finished:
                log.warning("部分工作執行緒未在時限內結束；其狀態已改為等待，下次啟動時恢復")
        finally:
            QApplication.restoreOverrideCursor()
            try:
                self.bridge.event.disconnect(self._on_queue_event)
            except (RuntimeError, TypeError):
                pass
        event.accept()
