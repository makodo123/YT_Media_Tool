"""設定對話框。"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from yt_media_tool.core import converter
from yt_media_tool.core.task_models import MP3_QUALITIES, MP4_QUALITIES, MediaFormat
from yt_media_tool.storage.settings import MAX_CONCURRENT, MIN_CONCURRENT, AppSettings


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
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setMinimumWidth(560)
        self._original = settings

        self.download_dir = QLineEdit(settings.download_dir)
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(MIN_CONCURRENT, MAX_CONCURRENT)
        self.max_concurrent.setValue(settings.max_concurrent)
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
        self.open_folder = QCheckBox("下載完成後開啟資料夾")
        self.open_folder.setChecked(settings.open_folder_on_complete)
        self.keep_history = QCheckBox("保留下載歷史紀錄")
        self.keep_history.setChecked(settings.keep_history)
        self.ffmpeg_dir = QLineEdit(settings.ffmpeg_dir)
        self.ffmpeg_dir.setPlaceholderText("留白＝自動偵測（隨附版本或系統 PATH）")
        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("hintLabel")
        self.ffmpeg_status.setWordWrap(True)
        check_button = QPushButton("檢查 FFmpeg")
        check_button.clicked.connect(self._check_ffmpeg)

        form = QFormLayout()
        form.addRow("預設儲存資料夾：", _folder_row(self, self.download_dir, "選擇下載資料夾"))
        form.addRow("同時下載數量：", self.max_concurrent)
        form.addRow("預設下載格式：", self.default_format)
        form.addRow("預設 MP4 解析度：", self.mp4_quality)
        form.addRow("預設 MP3 品質：", self.mp3_quality)
        form.addRow("", self.open_folder)
        form.addRow("", self.keep_history)
        form.addRow("FFmpeg 資料夾：", _folder_row(self, self.ffmpeg_dir, "選擇含 ffmpeg.exe 的資料夾"))
        form.addRow("", check_button)
        form.addRow("", self.ffmpeg_status)

        note = QLabel("畫質與音質為目標輸出設定；原始素材不支援時，會在佇列中顯示實際取得的格式。")
        note.setObjectName("hintLabel")
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("儲存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self._check_ffmpeg()

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
        self.accept()

    def result_settings(self) -> AppSettings:
        return dataclasses.replace(
            self._original,
            download_dir=self.download_dir.text().strip(),
            max_concurrent=self.max_concurrent.value(),
            default_format=self.default_format.currentData(),
            default_mp4_quality=self.mp4_quality.currentData(),
            default_mp3_quality=self.mp3_quality.currentData(),
            open_folder_on_complete=self.open_folder.isChecked(),
            keep_history=self.keep_history.isChecked(),
            ffmpeg_dir=self.ffmpeg_dir.text().strip(),
        ).validated()
