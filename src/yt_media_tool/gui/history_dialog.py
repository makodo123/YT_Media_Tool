"""下載歷史紀錄對話框。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from yt_media_tool.core.task_models import STATUS_LABELS, MediaFormat, TaskStatus, quality_label
from yt_media_tool.gui.theme import STATUS_COLORS
from yt_media_tool.storage.database import Database
from yt_media_tool.utils import system_open

# 重新下載：(網址, 格式, 品質)
RedownloadCallback = Callable[[str, MediaFormat, str], None]


def _local_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso


class HistoryDialog(QDialog):
    HEADERS = ("時間", "影片名稱", "格式", "品質", "狀態", "檔案 / 錯誤")

    def __init__(self, db: Database, parent: QWidget | None = None,
                 on_redownload: RedownloadCallback | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._on_redownload = on_redownload
        self._rows: list[dict[str, Any]] = []
        self.setWindowTitle("下載歷史紀錄")
        self.resize(980, 520)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋影片名稱、網址或檔名")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        hint = QLabel("雙擊已完成的項目可在檔案總管中顯示檔案；按右鍵可複製網址或重新下載。")
        hint.setObjectName("hintLabel")

        self.table = QTableWidget(0, len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, width in {0: 150, 2: 55, 3: 110, 4: 70, 5: 260}.items():
            self.table.setColumnWidth(col, width)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(lambda row, _col: self.reveal(row))

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
        layout.addWidget(self.search)
        layout.addWidget(hint)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        self._rows = self._db.list_history()
        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
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
            output = row["output_path"]
            error = (row["error_message"] or "").splitlines()
            detail = Path(output).name if output else (error[0] if error else "")
            values = [_local_time(row["finished_at"]), row["title"] or row["url"], fmt_text, quality, status, detail]
            tips = ["", "\n".join(filter(None, (row["title"], row["url"]))), "", "", "",
                    output or row["error_message"]]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(tips[c] or str(value))
                if c == 4:
                    item.setForeground(QColor(STATUS_COLORS.get(row["status"], "#e6e9ee")))
                self.table.setItem(r, c, item)
        self._apply_filter(self.search.text())

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for r, row in enumerate(self._rows):
            haystack = " ".join(str(row.get(k) or "") for k in ("title", "url", "output_path")).lower()
            self.table.setRowHidden(r, bool(keyword) and keyword not in haystack)

    def visible_rows(self) -> list[int]:
        return [r for r in range(self.table.rowCount()) if not self.table.isRowHidden(r)]

    # ---- 動作 ----
    def reveal(self, row: int) -> bool:
        """在檔案總管中顯示該筆的檔案；檔案已不存在時提示。"""
        output = self._rows[row]["output_path"] if 0 <= row < len(self._rows) else ""
        if not output:
            return False
        if not Path(output).is_file():
            QMessageBox.information(self, "下載歷史紀錄", f"檔案已不存在（可能已被移動或刪除）：\n{output}")
            return False
        return system_open.reveal_file(Path(output))

    def redownload(self, row: int) -> None:
        data = self._rows[row]
        try:
            fmt = MediaFormat(data["media_format"])
        except ValueError:
            return
        if self._on_redownload is not None:
            self._on_redownload(data["url"], fmt, data["quality"])

    def build_context_menu(self, row: int) -> QMenu:
        data = self._rows[row]
        menu = QMenu(self)
        if data["output_path"]:
            menu.addAction("在檔案總管中顯示", lambda: self.reveal(row))
        menu.addAction("複製網址", lambda: QGuiApplication.clipboard().setText(data["url"]))
        if self._on_redownload is not None:
            menu.addAction("重新下載（以相同格式加入佇列）", lambda: self.redownload(row))
        return menu

    def _show_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if index.isValid():
            self.build_context_menu(index.row()).exec(self.table.viewport().mapToGlobal(pos))

    def _clear(self) -> None:
        if QMessageBox.question(self, "清除歷史紀錄", "確定要清除所有下載歷史紀錄嗎？（不會刪除已下載的檔案）") \
                == QMessageBox.StandardButton.Yes:
            self._db.clear_history()
            self.reload()
