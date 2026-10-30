"""主視窗：網址輸入、格式選擇、下載佇列、整體進度與錯誤詳細資訊。"""

from __future__ import annotations

import dataclasses
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from yt_media_tool import APP_DISPLAY_NAME, __version__
from yt_media_tool.app_context import AppContext
from yt_media_tool.core import converter
from yt_media_tool.core.downloader import PlaylistInfo
from yt_media_tool.core.errors import explain_error
from yt_media_tool.core.queue_manager import (
    QUEUE_STATE, TASK_ADDED, TASK_FINISHED, TASK_PROGRESS, TASK_REMOVED, TASK_UPDATED, TaskSpec,
)
from yt_media_tool.core.task_models import (
    DownloadTask, MediaFormat, TaskStatus, format_speed, quality_options,
)
from yt_media_tool.core.url_parser import ParsedUrl, UrlKind, parse_urls
from yt_media_tool.gui.history_dialog import HistoryDialog
from yt_media_tool.gui.qt_bridge import QueueEventBridge
from yt_media_tool.gui.queue_table import ACTION_CANCEL, ACTION_OPEN, ACTION_RETRY, QueueTableView
from yt_media_tool.gui.settings_dialog import SettingsDialog
from yt_media_tool.gui.workers import BackgroundJob
from yt_media_tool.storage.settings import AppSettings
from yt_media_tool.utils import system_open

log = logging.getLogger(__name__)

MAX_PLAYLIST_ITEMS = 500
DISCLAIMER = (
    "本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。\n"
    "請遵守著作權法及 YouTube 服務條款；本工具不支援、也不會嘗試繞過 DRM 或其他存取限制。"
)


def _local_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._closing = False
        self._busy_expanding = False
        self._last_completed_dir: str | None = None
        self._jobs: set[BackgroundJob] = set()
        self._expand_context: tuple = ()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1180, 760)

        self.bridge = QueueEventBridge(self)
        self.bridge.event.connect(self._on_queue_event)
        ctx.queue.add_listener(self.bridge)

        self._build_menu()
        self._build_ui()
        self._apply_settings_to_ui()
        self._restore_geometry()
        self._refresh_dependency_banner()

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
        history_action = QAction("下載歷史紀錄…", self)
        history_action.triggered.connect(lambda: HistoryDialog(self.ctx.db, self).exec())
        tools_menu.addAction(history_action)
        check_action = QAction("檢查相依元件（FFmpeg / Deno）", self)
        check_action.triggered.connect(self.show_dependency_report)
        tools_menu.addAction(check_action)

        help_menu = self.menuBar().addMenu("說明(&H)")
        notice = QAction("使用聲明", self)
        notice.triggered.connect(lambda: QMessageBox.information(self, "使用聲明", DISCLAIMER))
        help_menu.addAction(notice)
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

        # ---- 網址輸入 ----
        url_group = QGroupBox("網址")
        url_layout = QVBoxLayout(url_group)
        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText(
            "貼上 YouTube 影片、Shorts 或播放清單網址；可一次貼上多行，重複網址會自動去除。")
        self.url_input.setFixedHeight(90)
        url_layout.addWidget(self.url_input)
        row = QHBoxLayout()
        paste_button = QPushButton("從剪貼簿貼上")
        paste_button.clicked.connect(self._paste_clipboard)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self.url_input.clear)
        self.expand_playlist = QCheckBox("影片網址含播放清單時，下載整個清單")
        self.expand_playlist.setToolTip(
            "例如 watch?v=…&list=… 這類網址：勾選時下載整個播放清單，未勾選時只下載這一支影片。\n"
            "播放清單網址（playlist?list=…）一律讀取整個清單。加入前都會顯示影片數量並請您確認。")
        self.detection_label = QLabel()
        self.detection_label.setObjectName("hintLabel")
        row.addWidget(paste_button)
        row.addWidget(clear_button)
        row.addSpacing(12)
        row.addWidget(self.expand_playlist)
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

    def selected_format(self) -> MediaFormat:
        return MediaFormat.MP3 if self.mp3_radio.isChecked() else MediaFormat.MP4

    def _refresh_quality_combo(self) -> None:
        fmt = self.selected_format()
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

    def _show_about(self) -> None:
        QMessageBox.about(self, "關於", f"<b>{APP_DISPLAY_NAME}</b><br>版本 {__version__}<br><br>"
                          + DISCLAIMER.replace("\n", "<br>"))

    # ================= 網址處理 =================
    def _paste_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text()
        if text:
            current = self.url_input.toPlainText().rstrip()
            self.url_input.setPlainText(f"{current}\n{text}".strip() if current else text.strip())

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
            if item.kind is UrlKind.PLAYLIST:
                playlists.append(item)  # 加入前會顯示影片數量並確認
            elif item.kind is UrlKind.VIDEO_IN_PLAYLIST and self.expand_playlist.isChecked():
                playlists.append(item)
            else:
                singles.append(item.video_url)  # type: ignore[arg-type]

        fmt, quality = self.selected_format(), self.quality_combo.currentData()
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
                    results.append((item, downloader.extract_playlist(item.playlist_url, MAX_PLAYLIST_ITEMS)))
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
        entries: list[str] = []
        summary: list[str] = []
        for item, outcome in results:
            if isinstance(outcome, Exception):
                notes.append(f"• 無法讀取播放清單 {item.original}\n   {explain_error(outcome)}")
                if item.kind is UrlKind.VIDEO_IN_PLAYLIST:
                    singles.append(item.video_url)
                continue
            title = outcome.title or item.playlist_id
            extra = f"（僅取前 {MAX_PLAYLIST_ITEMS} 部）" if outcome.truncated else ""
            summary.append(f"• {title}：{len(outcome.entries)} 部影片{extra}")
            entries.extend(e.url for e in outcome.entries)
        if entries:
            answer = self.confirm_playlist(len(entries), summary)
            if answer:
                singles.extend(entries)
            else:
                notes.append("已取消加入播放清單中的影片。")
        self._finish_add(singles, fmt, quality, output_dir, notes)

    def confirm_playlist(self, count: int, summary: list[str]) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("加入播放清單")
        box.setText(f"播放清單共有 {count} 部影片，確定要全部加入下載佇列嗎？")
        box.setInformativeText("\n".join(summary))
        add = box.addButton(f"加入 {count} 部", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is add

    def _finish_add(self, urls: list[str], fmt: MediaFormat, quality: str, output_dir: str,
                    notes: list[str]) -> list[DownloadTask]:
        # 去除重複（播放清單展開後可能與單一網址重複）並略過佇列中尚未完成的相同任務
        existing = {(t.url, t.media_format, t.quality, t.output_dir) for t in self.ctx.queue.tasks()
                    if not t.status.is_finished}
        seen: set[str] = set()
        specs: list[TaskSpec] = []
        skipped = 0
        for url in urls:
            parsed = parse_urls(url).valid
            key = parsed[0].dedupe_key if parsed else url
            if key in seen:
                continue
            seen.add(key)
            if (url, fmt, quality, output_dir) in existing:
                skipped += 1
                continue
            specs.append(TaskSpec(url=url, media_format=fmt, quality=quality, output_dir=output_dir))
        if skipped:
            notes.append(f"已略過 {skipped} 個已在佇列中的相同任務。")
        added = self.ctx.queue.add_tasks(specs) if specs else []
        if added:
            self.url_input.clear()
            self.statusBar().showMessage(f"已加入 {len(added)} 筆任務", 5000)
            if self.ctx.queue.is_paused and not self.ctx.queue.has_active_tasks():
                self.statusBar().showMessage(
                    f"已加入 {len(added)} 筆任務（佇列目前暫停中，按「開始佇列」開始下載）", 8000)
        if notes:
            QMessageBox.information(self, "加入佇列", "\n\n".join(notes))
        return added

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

    def _reveal(self, task: DownloadTask) -> None:
        if task.output_path and Path(task.output_path).is_file():
            system_open.reveal_file(Path(task.output_path))
        else:
            self._open_folder(task.output_dir)

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
            self.statusBar().showMessage(f"完成：{task.display_title}", 5000)
        elif task.status is TaskStatus.FAILED:
            self.statusBar().showMessage(f"失敗：{task.display_title}（選取任務可檢視詳細錯誤）", 8000)
        queue = self.ctx.queue
        if (self.ctx.settings.open_folder_on_complete and self._last_completed_dir and not self._closing
                and not queue.has_active_tasks() and (queue.pending_count() == 0 or queue.is_paused)):
            system_open.open_folder(Path(self._last_completed_dir))
            self._last_completed_dir = None

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
        if self.ctx.queue.has_active_tasks():
            answer = QMessageBox.question(
                self, "結束程式",
                "仍有下載進行中。確定要結束嗎？\n進行中的任務會被中斷並清除暫存檔，下次開啟時會重新排入佇列。")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closing = True
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
