"""設定對話框。"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from yt_media_tool.core import converter
from yt_media_tool.core.cookies import COOKIE_SOURCES
from yt_media_tool.core.task_models import MP3_QUALITIES, MP4_QUALITIES, MediaFormat
from yt_media_tool.core import ai_clients
from yt_media_tool.core.downloader import ChannelInfo
from yt_media_tool.core.errors import explain_error
from yt_media_tool.core.url_parser import UrlParseError, parse_channel_url
from yt_media_tool.gui.workers import BackgroundJob
from yt_media_tool.gui.safe_text import plain
from yt_media_tool.mcp_server import launch_command

from yt_media_tool.storage.settings import (
    MAX_AUTO_CHANNELS, MAX_CONCURRENT, MAX_RATE_LIMIT_MBPS, MIN_CONCURRENT, AppSettings,
)

MAX_AUTO_DOWNLOADS = 10  # 與 MainWindow 相同：AI 助理每批最多自動加入佇列的影片數

# AI 助理設定檔的狀態 → （顯示文字, 按鈕文字；None 表示不顯示按鈕）
AI_CLIENT_TEXT = {
    ai_clients.ConfigState.NOT_FOUND: ("未偵測到（沒有安裝，或安裝後還沒開啟過）", None),
    ai_clients.ConfigState.NOT_CONFIGURED: ("已偵測到，尚未加入", "加入"),
    ai_clients.ConfigState.CONFIGURED: ("✔ 已加入", None),
    ai_clients.ConfigState.OUTDATED: ("已加入，但程式位置不同（例如改裝到別的資料夾）", "更新"),
    ai_clients.ConfigState.INVALID: ("設定檔格式有誤，無法自動加入", None),
}


def _folder_row(parent: QWidget, line_edit: QLineEdit, title: str) -> QWidget:
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(line_edit, 1)
    button = QPushButton("瀏覽…", row)

    def browse() -> None:
        start = line_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(parent, title, start)
        if chosen:
            line_edit.setText(chosen)

    button.clicked.connect(browse)
    layout.addWidget(button)
    return row


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None,
                 channel_resolver: Callable[[str], ChannelInfo] | None = None) -> None:
        super().__init__(parent)
        self._channel_resolver = channel_resolver  # 頻道網址 → 頻道 ID 與名稱（需連網，在背景執行）
        self._channel_job: BackgroundJob | None = None
        self.setWindowTitle("設定")
        self.setMinimumWidth(560)
        self._original = settings

        self.download_dir = QLineEdit(settings.download_dir)
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(MIN_CONCURRENT, MAX_CONCURRENT)
        self.max_concurrent.setValue(settings.max_concurrent)
        self.max_concurrent.setToolTip("同時下載太多影片較容易被 YouTube 要求驗證，一般建議 1–2。")
        self.rate_limit = QDoubleSpinBox()
        self.rate_limit.setRange(0.0, MAX_RATE_LIMIT_MBPS)
        self.rate_limit.setDecimals(1)
        self.rate_limit.setSingleStep(0.5)
        self.rate_limit.setSuffix(" MB/s")
        self.rate_limit.setSpecialValueText("不限制")
        self.rate_limit.setValue(settings.rate_limit_mbps)
        self.auto_paste = QCheckBox("切回程式時自動帶入剪貼簿中的 YouTube 網址")
        self.auto_paste.setToolTip("在瀏覽器複製網址後切回本程式，網址會自動放進輸入框（不會自動開始下載）。")
        self.auto_paste.setChecked(settings.auto_paste_clipboard)
        self.rate_limit.setToolTip("所有下載合計的速度上限，避免下載時佔滿網路、影響看影片或開會。\n"
                                   "0 表示不限制。變更後對下一個開始的任務生效。")
        self.default_format = QComboBox()
        self.default_format.addItem("MP4 影片", MediaFormat.MP4.value)
        self.default_format.addItem("MP3 音訊", MediaFormat.MP3.value)
        self.default_format.setCurrentIndex(self.default_format.findData(settings.default_format))
        self.mp4_quality = QComboBox()
        for key, label in MP4_QUALITIES.items():
            self.mp4_quality.addItem(label, key)
        self.mp4_quality.setCurrentIndex(self.mp4_quality.findData(settings.default_mp4_quality))
        self.mp3_quality = QComboBox()
        for key, label in MP3_QUALITIES.items():
            self.mp3_quality.addItem(label, key)
        self.mp3_quality.setCurrentIndex(self.mp3_quality.findData(settings.default_mp3_quality))
        self.open_folder = QCheckBox("全部下載完成後開啟資料夾")
        self.open_folder.setChecked(settings.open_folder_on_complete)
        self.notify = QCheckBox("全部下載完成時通知（工作列閃爍並顯示系統通知）")
        self.notify.setToolTip("程式不在前景時才會通知，切到其他視窗做事也會知道下載完成。")
        self.notify.setChecked(settings.notify_on_complete)
        self.keep_history = QCheckBox("保留下載歷史紀錄")
        self.keep_history.setChecked(settings.keep_history)
        self.embed_metadata = QCheckBox("寫入歌名、演出者與封面（以影片縮圖作為封面）")
        self.embed_metadata.setToolTip("在 MP3 / MP4 檔案中寫入標題、演出者（頻道名稱）等資訊並嵌入封面，\n"
                                       "音樂播放器與手機會顯示歌名和封面。")
        self.embed_metadata.setChecked(settings.embed_metadata)
        self.clean_titles = QCheckBox("自動整理歌名（例如「周杰倫 - 晴天」，去掉「Official MV」等字樣）")
        self.clean_titles.setToolTip("檔名與歌曲資訊改用整理後的「演出者 - 歌名」；\n"
                                     "佇列與歷史紀錄仍顯示 YouTube 原標題。MP3 一律整理；\n"
                                     "MP4 只在標題中找得到演出者時整理（vlog、教學等影片維持原標題）。\n"
                                     "優先使用 YouTube 提供的歌曲資訊；整理不出合理結果時保留原標題。\n"
                                     "只影響之後的下載。")
        self.clean_titles.setChecked(settings.clean_titles)
        self.playlist_subfolder = QCheckBox("播放清單存到以清單名稱命名的子資料夾")
        self.playlist_subfolder.setToolTip("例如「下載資料夾\\我的最愛歌單\\」；只下載貼上的那一支影片時不另建資料夾。")
        self.playlist_subfolder.setChecked(settings.playlist_subfolder)
        self.playlist_m3u = QCheckBox("下載播放清單時產生播放順序檔（.m3u8），音樂播放器可依清單原本的順序播放")
        self.playlist_m3u.setToolTip("從播放清單下載 2 部以上時，在存放的資料夾產生「清單名稱.m3u8」，\n"
                                     "用音樂播放器（例如 VLC、foobar2000、手機音樂 App）開啟即依原清單順序播放。")
        self.playlist_m3u.setChecked(settings.playlist_m3u)
        self.check_updates = QCheckBox("啟動時檢查是否有新版本")
        self.check_updates.setToolTip("只連線 GitHub 讀取最新版本號，不會傳送任何個人資料。\n"
                                      "也可以從「說明 → 檢查新版本」手動檢查。")
        self.check_updates.setChecked(settings.check_updates)
        self.auto_download_updates = QCheckBox("有新版本時自動在背景下載（安裝前會先詢問；只適用安裝版）")
        self.auto_download_updates.setToolTip("下載的安裝程式會核對檢查碼，通過後才能安裝；\n"
                                              "按「立即安裝並重新開啟」才會關閉程式並更新。免安裝版請到下載頁面手動更新。")
        self.auto_download_updates.setChecked(settings.auto_download_updates)
        self.ffmpeg_dir = QLineEdit(settings.ffmpeg_dir)
        self.ffmpeg_dir.setPlaceholderText("留白＝自動偵測（隨附版本或系統 PATH）")
        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("hintLabel")
        self.ffmpeg_status.setWordWrap(True)
        check_button = QPushButton("檢查")
        check_button.clicked.connect(self._check_ffmpeg)

        download_group = QGroupBox("下載")
        form = QFormLayout(download_group)
        folder_row = _folder_row(self, self.download_dir, "選擇下載資料夾")
        folder_row.setToolTip("與主視窗的「儲存至」相同；在主視窗換資料夾並加入任務後，這裡也會跟著更新。")
        form.addRow("下載資料夾：", folder_row)
        form.addRow("同時下載數量：", self.max_concurrent)
        form.addRow("速度上限：", self.rate_limit)
        form.addRow("預設格式：", self.default_format)
        form.addRow("預設 MP4 解析度：", self.mp4_quality)
        form.addRow("預設 MP3 品質：", self.mp3_quality)

        files_group = QGroupBox("其他功能")
        files_layout = QVBoxLayout(files_group)
        for box in (self.embed_metadata, self.clean_titles, self.playlist_subfolder, self.playlist_m3u,
                    self.auto_paste, self.notify, self.open_folder, self.keep_history, self.check_updates,
                    self.auto_download_updates):
            files_layout.addWidget(box)

        ffmpeg_group = QGroupBox("FFmpeg（通常不需更改）")
        ffmpeg_form = QFormLayout(ffmpeg_group)
        ffmpeg_row = _folder_row(self, self.ffmpeg_dir, "選擇含 ffmpeg.exe 的資料夾")
        ffmpeg_row.layout().addWidget(check_button)
        ffmpeg_form.addRow("FFmpeg 資料夾：", ffmpeg_row)
        ffmpeg_form.addRow("", self.ffmpeg_status)

        # ---- YouTube 登入資訊（cookies）----
        self.cookies_source = QComboBox()
        for key, label in COOKIE_SOURCES.items():
            self.cookies_source.addItem(label, key)
        self.cookies_source.setCurrentIndex(max(0, self.cookies_source.findData(settings.cookies_source)))
        self.cookies_file = QLineEdit(settings.cookies_file)
        self.cookies_file.setPlaceholderText("由瀏覽器擴充功能匯出的 Netscape 格式 cookies.txt")
        self.cookies_file_row = QWidget(self)
        file_layout = QHBoxLayout(self.cookies_file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(self.cookies_file, 1)
        browse_cookies = QPushButton("瀏覽…")
        browse_cookies.clicked.connect(self._browse_cookies)
        file_layout.addWidget(browse_cookies)
        # 檔案欄一直可用；選擇或輸入檔案時自動把來源切換為「cookies.txt 檔案」
        self.cookies_file.textEdited.connect(self._on_cookie_file_edited)
        cookies_note = QLabel(
            "一般不需要設定。只有在 YouTube 要求「登入以確認不是機器人」，或影片需要登入才能觀看"
            "（例如年齡限制、會員專屬）時才使用；程式會以您的 YouTube 帳號登入狀態下載。"
            "yt-dlp 官方提醒帳號可能因此被 YouTube 限制，建議使用次要帳號。\n"
            "• Firefox：先在 Firefox 登入 YouTube，程式會直接讀取，最穩定。\n"
            "• cookies.txt：用瀏覽器擴充功能匯出後在此指定（Chrome / Edge 請用這個方式，"
            "因為新版的加密讓程式無法直接讀取）；程式只使用副本，不會修改原檔。\n"
            "本程式不會另外保存、記錄或傳送 cookies 內容。")
        cookies_note.setObjectName("hintLabel")
        cookies_note.setWordWrap(True)
        cookies_group = QGroupBox("YouTube 登入資訊（選用）")
        cookies_form = QFormLayout(cookies_group)
        cookies_form.addRow("來源：", self.cookies_source)
        cookies_form.addRow("cookies.txt：", self.cookies_file_row)
        cookies_form.addRow(cookies_note)

        # ---- AI 助理（MCP）----
        self.mcp_enabled = QCheckBox("允許 AI 助理（MCP）查詢紀錄與帶入網址")
        self.mcp_enabled.setChecked(settings.mcp_enabled)
        mcp_note = QLabel(
            "開啟後，Claude、Codex 等支援 MCP 的 AI 助理可以：查詢下載歷史紀錄、查看佇列，"
            "以及把 YouTube 網址放進主視窗的輸入框。\n"
            "AI 助理不能開始下載、刪除紀錄或更改設定：帶入的網址一定要由您按「加入佇列」才會下載。\n"
            "偵測到 Claude Desktop 或 Codex 時，可按「加入」自動寫入它們的設定（只新增這一項，原檔會先備份）；"
            "Claude Code 請複製指令到命令提示字元執行一次；其他 AI 助理請在其 MCP 設定中填入啟動指令。")
        mcp_note.setObjectName("hintLabel")
        mcp_note.setWordWrap(True)
        self._mcp_launch = launch_command()
        self.mcp_command = QLineEdit(" ".join(f'"{part}"' if " " in part else part for part in self._mcp_launch))
        self.mcp_command.setReadOnly(True)
        self.claude_code_command = QLineEdit(ai_clients.claude_code_command(self._mcp_launch))
        self.claude_code_command.setReadOnly(True)
        self.claude_desktop_status, self.claude_desktop_button, claude_desktop_row = self._client_row()
        self.claude_desktop_button.clicked.connect(lambda: self._add_ai_client(ai_clients.add_to_claude_desktop))
        self.codex_status, self.codex_button, codex_row = self._client_row()
        self.codex_button.clicked.connect(lambda: self._add_ai_client(ai_clients.add_to_codex))
        mcp_group = QGroupBox("AI 助理（MCP，選用）")
        mcp_form = QFormLayout(mcp_group)
        mcp_form.addRow(self.mcp_enabled)
        mcp_form.addRow("Claude Desktop：", claude_desktop_row)
        mcp_form.addRow("Codex：", codex_row)
        mcp_form.addRow("Claude Code：", self._copy_row(self.claude_code_command))
        mcp_form.addRow("其他 AI 助理：", self._copy_row(self.mcp_command))
        mcp_form.addRow(mcp_note)
        self._refresh_ai_clients()

        # 自動下載頻道（白名單）：AI 助理帶入的影片屬於這些頻道時直接加入佇列
        self.auto_channels = QListWidget()
        self.auto_channels.setMaximumHeight(110)
        self.auto_channels.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for channel in settings.mcp_auto_channels:
            self._add_channel_item(channel["id"], channel["name"])
        self.add_channel_button = QPushButton("加入頻道…")
        self.add_channel_button.clicked.connect(self._ask_channel)
        self.add_channel_button.setEnabled(channel_resolver is not None)
        remove_channel = QPushButton("移除")
        remove_channel.clicked.connect(self._remove_channels)
        channel_buttons = QVBoxLayout()
        channel_buttons.addWidget(self.add_channel_button)
        channel_buttons.addWidget(remove_channel)
        channel_buttons.addStretch(1)
        channel_row = QWidget(self)
        channel_layout = QHBoxLayout(channel_row)
        channel_layout.setContentsMargins(0, 0, 0, 0)
        channel_layout.addWidget(self.auto_channels, 1)
        channel_layout.addLayout(channel_buttons)
        channel_note = QLabel(
            "AI 助理帶入的影片若屬於這些頻道，會直接加入佇列開始下載，不再需要您確認（每次最多 "
            f"{MAX_AUTO_DOWNLOADS} 部；播放清單仍會放進輸入框讓您勾選）。其他頻道的影片一律放進輸入框等您確認。\n"
            "請只加入您有權利下載的頻道，例如您自己的頻道。清單是空的時候不會自動下載。")
        channel_note.setObjectName("hintLabel")
        channel_note.setWordWrap(True)
        mcp_form.addRow("自動下載頻道：", channel_row)
        mcp_form.addRow(channel_note)

        note = QLabel("影片沒有所選的畫質或音質時，會下載可取得的最高品質，並在佇列的「品質」欄標示 ⚠。")
        note.setObjectName("hintLabel")
        note.setWordWrap(True)
        form.addRow(note)  # 放在「下載」群組內，說明上面的畫質與音質設定

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("儲存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        # 內容放在捲動區域：小螢幕或高縮放比例時也不會被截斷，儲存 / 取消按鈕固定在底部
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        for group in (download_group, files_group, ffmpeg_group, cookies_group, mcp_group):
            content_layout.addWidget(group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)
        self._check_ffmpeg()
        self._fit_to_screen(content)

    def _fit_to_screen(self, content: QWidget) -> None:
        """依內容決定高度，但不超過螢幕可用高度的 90%。"""
        content.setMinimumWidth(self.minimumWidth() - 40)
        wanted = content.sizeHint().height() + 70
        screen = self.screen() or QApplication.primaryScreen()
        limit = int(screen.availableGeometry().height() * 0.9) if screen else wanted
        self.resize(max(self.minimumWidth(), content.sizeHint().width() + 40), min(wanted, limit))

    def _use_cookie_file_source(self) -> None:
        self.cookies_source.setCurrentIndex(self.cookies_source.findData("file"))

    def _on_cookie_file_edited(self, text: str) -> None:
        if text.strip():
            self._use_cookie_file_source()

    def _browse_cookies(self) -> None:
        start = self.cookies_file.text() or str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(self, "選擇 cookies.txt", start, "Cookies 檔案 (*.txt);;所有檔案 (*)")
        if chosen:
            self.cookies_file.setText(chosen)
            self._use_cookie_file_source()

    def _check_ffmpeg(self) -> None:
        info = converter.find_ffmpeg(self.ffmpeg_dir.text().strip() or None)
        if info.available:
            self.ffmpeg_status.setText(f"✔ 已找到 FFmpeg {info.ffmpeg_version}（{info.source}）：{info.ffmpeg.parent}")
        else:
            self.ffmpeg_status.setText("✘ 找不到 FFmpeg / FFprobe。" + ("指定的資料夾中缺少 " + "、".join(
                f"{m}.exe" for m in info.missing) if self.ffmpeg_dir.text().strip() else ""))

    def _accept(self) -> None:
        folder = self.download_dir.text().strip()
        if not folder:
            QMessageBox.warning(self, "設定", "請指定下載資料夾。")
            return
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "設定", f"無法建立下載資料夾：\n{folder}\n\n{exc}")
            return
        ffmpeg_dir = self.ffmpeg_dir.text().strip()
        if ffmpeg_dir and not converter.find_ffmpeg(ffmpeg_dir, use_path=False).available:
            QMessageBox.warning(self, "設定", "指定的 FFmpeg 資料夾中找不到 ffmpeg 與 ffprobe 執行檔。")
            return
        if self.cookies_source.currentData() == "file" and not Path(self.cookies_file.text().strip()).is_file():
            QMessageBox.warning(self, "設定", "請指定存在的 cookies.txt 檔案，或將登入資訊來源改為「不使用」。")
            return
        self.accept()

    # ---- 自動下載頻道 ----
    def _add_channel_item(self, channel_id: str, name: str) -> None:
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, {"id": channel_id, "name": name})
        item.setToolTip(plain(f"{name}\nhttps://www.youtube.com/channel/{channel_id}"))
        self.auto_channels.addItem(item)

    def channels(self) -> list[dict[str, str]]:
        return [self.auto_channels.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.auto_channels.count())]

    def _ask_channel(self) -> None:
        text, ok = QInputDialog.getText(self, "加入自動下載頻道",
                                        "貼上頻道網址（到頻道首頁複製，例如 https://www.youtube.com/@帳號）：")
        if ok and text.strip():
            self.add_channel(text)

    def add_channel(self, text: str) -> None:
        try:
            url = parse_channel_url(text)
        except UrlParseError as exc:
            QMessageBox.warning(self, "自動下載頻道", str(exc))
            return
        if self._channel_resolver is None or self._channel_job is not None:
            return
        resolver = self._channel_resolver
        job = BackgroundJob(lambda: resolver(url))
        job.signals.succeeded.connect(self._on_channel_resolved)
        job.signals.failed.connect(self._on_channel_failed)
        self._channel_job = job
        self.add_channel_button.setEnabled(False)
        self.add_channel_button.setText("讀取中…")
        QThreadPool.globalInstance().start(job)

    def _channel_done(self) -> None:
        self._channel_job = None
        self.add_channel_button.setEnabled(True)
        self.add_channel_button.setText("加入頻道…")

    def _on_channel_failed(self, exc: Exception) -> None:
        self._channel_done()
        QMessageBox.warning(self, "自動下載頻道", plain(f"讀不到這個頻道：{explain_error(exc)}"))

    def _on_channel_resolved(self, channel: ChannelInfo) -> None:
        self._channel_done()
        if any(c["id"] == channel.channel_id for c in self.channels()):
            QMessageBox.information(self, "自動下載頻道", plain(f"「{channel.name}」已經在清單中。"))
            return
        if len(self.channels()) >= MAX_AUTO_CHANNELS:
            QMessageBox.warning(self, "自動下載頻道", f"最多 {MAX_AUTO_CHANNELS} 個頻道。")
            return
        answer = QMessageBox.question(
            self, "自動下載頻道",
            plain(f"加入「{channel.name}」後，AI 助理帶入這個頻道的影片會直接開始下載，不再需要您確認。\n\n"
                  "請確認您有權利下載這個頻道的內容。確定要加入嗎？"))
        if answer == QMessageBox.StandardButton.Yes:
            self._add_channel_item(channel.channel_id, channel.name)

    def _remove_channels(self) -> None:
        for item in self.auto_channels.selectedItems():
            self.auto_channels.takeItem(self.auto_channels.row(item))

    def _copy_mcp_command(self) -> None:
        self._copy_text(self.mcp_command)

    @staticmethod
    def _copy_text(edit: QLineEdit) -> None:
        QApplication.clipboard().setText(edit.text())
        edit.selectAll()

    def _copy_row(self, edit: QLineEdit) -> QWidget:
        button = QPushButton("複製")
        button.clicked.connect(lambda: self._copy_text(edit))
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return row

    def _client_row(self) -> tuple[QLabel, QPushButton, QWidget]:
        status = QLabel()
        status.setWordWrap(True)
        button = QPushButton("加入")
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(status, 1)
        layout.addWidget(button)
        return status, button, row

    def _refresh_ai_clients(self) -> None:
        launch = self._mcp_launch
        for config, label, button in (
            (ai_clients.claude_desktop_status(launch), self.claude_desktop_status, self.claude_desktop_button),
            (ai_clients.codex_status(launch), self.codex_status, self.codex_button),
        ):
            text, action = AI_CLIENT_TEXT[config.state]
            if config.state is ai_clients.ConfigState.INVALID:
                text += f"：{config.detail}"
            label.setText(text)
            label.setToolTip(plain(str(config.path)) if config.path else "")
            button.setVisible(action is not None)
            button.setText(action or "")

    def _add_ai_client(self, add) -> None:
        try:
            config = add(self._mcp_launch)
        except ai_clients.ConfigError as exc:
            QMessageBox.warning(self, "AI 助理",
                                f"無法自動加入：{exc}\n\n可以改為手動設定（詳見「說明 → 使用說明」）。")
            self._refresh_ai_clients()
            return
        self.mcp_enabled.setChecked(True)  # 加入 AI 助理就是要使用這個功能
        self._refresh_ai_clients()
        how_to_quit = ("（在右下角系統匣的 Claude 圖示按右鍵 →「結束」，只關閉視窗不夠）"
                       if config.name == "Claude Desktop" else "")
        QMessageBox.information(
            self, "AI 助理",
            f"已加入 {config.name}。\n\n"
            "1. 按「儲存」保存設定（已同時勾選「允許 AI 助理」）。\n"
            f"2. 完全結束 {config.name} 後重新開啟{how_to_quit}。\n\n"
            "原本的設定檔已備份在同一個資料夾（檔名結尾為「.ytmt-backup-日期」）。")

    def result_settings(self) -> AppSettings:
        return dataclasses.replace(
            self._original,
            download_dir=self.download_dir.text().strip(),
            max_concurrent=self.max_concurrent.value(),
            default_format=self.default_format.currentData(),
            default_mp4_quality=self.mp4_quality.currentData(),
            default_mp3_quality=self.mp3_quality.currentData(),
            open_folder_on_complete=self.open_folder.isChecked(),
            notify_on_complete=self.notify.isChecked(),
            rate_limit_mbps=self.rate_limit.value(),
            auto_paste_clipboard=self.auto_paste.isChecked(),
            check_updates=self.check_updates.isChecked(),
            auto_download_updates=self.auto_download_updates.isChecked(),
            keep_history=self.keep_history.isChecked(),
            embed_metadata=self.embed_metadata.isChecked(),
            clean_titles=self.clean_titles.isChecked(),
            playlist_subfolder=self.playlist_subfolder.isChecked(),
            playlist_m3u=self.playlist_m3u.isChecked(),
            ffmpeg_dir=self.ffmpeg_dir.text().strip(),
            cookies_source=self.cookies_source.currentData(),
            cookies_file=self.cookies_file.text().strip(),
            mcp_enabled=self.mcp_enabled.isChecked(),
            mcp_auto_channels=self.channels(),
        ).validated()
