"""下載歷史紀錄對話框。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from yt_media_tool.core.task_models import STATUS_LABELS, MediaFormat, TaskStatus, quality_label
from yt_media_tool.storage.database import Database


def _local_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso


class HistoryDialog(QDialog):
    HEADERS = ("時間", "影片名稱", "格式", "品質", "狀態", "檔案 / 錯誤")

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("下載歷史紀錄")
        self.resize(900, 480)
        self.table = QTableWidget(0, len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(5, 280)

        clear_button = QPushButton("清除歷史紀錄")
        clear_button.setObjectName("dangerButton")
        clear_button.clicked.connect(self._clear)
        close_button = QPushButton("關閉")
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        rows = self._db.list_history()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            try:
                fmt = MediaFormat(row["media_format"])
                quality = quality_label(fmt, row["quality"])
                fmt_text = fmt.label
            except ValueError:
                fmt_text, quality = row["media_format"], row["quality"]
            try:
                status = STATUS_LABELS[TaskStatus(row["status"])]
            except ValueError:
                status = row["status"]
            detail = row["output_path"] or row["error_message"]
            values = [_local_time(row["finished_at"]), row["title"] or row["url"], fmt_text, quality, status, detail]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value) if c != 1 else f"{row['title']}\n{row['url']}")
                self.table.setItem(r, c, item)

    def _clear(self) -> None:
        if QMessageBox.question(self, "清除歷史紀錄", "確定要清除所有下載歷史紀錄嗎？（不會刪除已下載的檔案）") \
                == QMessageBox.StandardButton.Yes:
            self._db.clear_history()
            self.reload()
