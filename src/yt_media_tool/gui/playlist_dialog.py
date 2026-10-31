"""播放清單選擇對話框：列出清單中的影片，讓使用者勾選要下載的項目。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget,
)

from yt_media_tool.core.downloader import PlaylistEntry
from yt_media_tool.core.task_models import format_eta

UrlRole = Qt.ItemDataRole.UserRole + 1


@dataclass
class PlaylistGroup:
    """對話框中的一個播放清單。preselect_video_id 有值時只預先勾選該影片（從清單中某支影片的網址加入時）。"""

    title: str
    entries: list[PlaylistEntry]
    preselect_video_id: str | None = None
    truncated: bool = False


def _duration_text(seconds: float | None) -> str:
    return format_eta(seconds) if seconds else ""


class PlaylistPickerDialog(QDialog):
    def __init__(self, groups: list[PlaylistGroup], limit: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("選擇要下載的影片")
        self.resize(720, 560)

        hint = QLabel("勾選要下載的影片後按「加入」。從播放清單中某支影片的網址加入時，預設只勾選該影片；"
                      "要下載整個清單請按「全選」。")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        if any(g.truncated for g in groups):
            hint.setText(hint.text() + f"\n部分清單超過 {limit} 部，只列出前 {limit} 部。")

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋影片名稱")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        select_all = QPushButton("全選")
        select_all.setToolTip("勾選目前顯示的所有影片（有搜尋時只勾選符合的影片）")
        select_all.clicked.connect(lambda: self._set_visible_checked(True))
        select_none = QPushButton("全不選")
        select_none.setToolTip("取消勾選目前顯示的所有影片（有搜尋時只影響符合的影片）")
        select_none.clicked.connect(lambda: self._set_visible_checked(False))
        tools = QHBoxLayout()
        tools.addWidget(self.search, 1)
        tools.addWidget(select_all)
        tools.addWidget(select_none)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["影片名稱", "長度"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for group in groups:
            self._add_group(group)
        self.tree.expandAll()
        self.tree.itemChanged.connect(lambda *_: self._update_count())

        self.count_label = QLabel()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(self.count_label)
        bottom.addStretch(1)
        bottom.addWidget(self.buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(tools)
        layout.addWidget(self.tree, 1)
        layout.addLayout(bottom)
        self._update_count()

    def _add_group(self, group: PlaylistGroup) -> None:
        parent = QTreeWidgetItem(self.tree, [f"{group.title or '播放清單'}（{len(group.entries)} 部）", ""])
        parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
        for index, entry in enumerate(group.entries, 1):
            checked = group.preselect_video_id is None or entry.video_id == group.preselect_video_id
            item = QTreeWidgetItem(parent, [f"{index}. {entry.title or entry.url}", _duration_text(entry.duration)])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            item.setData(0, UrlRole, entry.url)
            item.setToolTip(0, f"{entry.title}\n{entry.url}" if entry.title else entry.url)
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _entry_items(self) -> list[QTreeWidgetItem]:
        items = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while (item := iterator.value()) is not None:
            if item.data(0, UrlRole):
                items.append(item)
            iterator += 1
        return items

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for item in self._entry_items():
            item.setHidden(bool(keyword) and keyword not in item.text(0).lower())

    def _set_visible_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        for item in self._entry_items():
            if not item.isHidden():
                item.setCheckState(0, state)
        self.tree.blockSignals(False)
        self.tree.viewport().update()
        self._update_count()

    def _update_count(self) -> None:
        total = len(self._entry_items())
        count = len(self.selected_urls())
        self.count_label.setText(f"已選 {count} / {total} 部")
        self.ok_button.setText(f"加入 {count} 部")
        self.ok_button.setEnabled(count > 0)

    def selected_urls(self) -> list[str]:
        """依清單順序回傳勾選的影片網址。"""
        return [item.data(0, UrlRole) for item in self._entry_items()
                if item.checkState(0) == Qt.CheckState.Checked]
