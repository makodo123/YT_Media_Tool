"""播放清單選擇對話框：列出清單中的影片，讓使用者勾選要下載的項目。

- 「預計檔名」欄顯示整理後的名稱，點兩下可修改；修改過的名稱下載時一定採用。
- 「已下載」欄標示歷史紀錄中已下載過（檔案還在）的影片；這些影片預設不勾選，
  再次加入同一個播放清單時就只會下載新加入的歌（播放清單同步）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget,
)

from yt_media_tool.core.downloader import PlaylistEntry
from yt_media_tool.core.task_models import format_eta

UrlRole = Qt.ItemDataRole.UserRole + 1
AutoNameRole = Qt.ItemDataRole.UserRole + 2  # 自動產生的檔名（判斷使用者是否修改過）
DownloadedRole = Qt.ItemDataRole.UserRole + 3
COL_TITLE, COL_NAME, COL_DURATION, COL_STATUS = range(4)


@dataclass
class PlaylistGroup:
    """對話框中的一個播放清單。preselect_video_id 有值時只預先勾選該影片（從清單中某支影片的網址加入時）。

    names：網址 → 預計檔名（不含副檔名）；downloaded：網址 → 已下載的檔案位置。
    """

    title: str
    entries: list[PlaylistEntry]
    preselect_video_id: str | None = None
    truncated: bool = False
    names: dict[str, str] = field(default_factory=dict)
    downloaded: dict[str, str] = field(default_factory=dict)


def _duration_text(seconds: float | None) -> str:
    return format_eta(seconds) if seconds else ""


class PlaylistPickerDialog(QDialog):
    def __init__(self, groups: list[PlaylistGroup], limit: int, parent: QWidget | None = None,
                 destination: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("選擇要下載的影片")
        self.resize(940, 580)

        lines = ["勾選要下載的影片後按「加入」；「預計檔名」可點兩下修改。從播放清單中某支影片的網址加入時，"
                 "預設只勾選該影片；要下載整個清單請按「全選」。"]
        downloaded = sum(len(g.downloaded) for g in groups)
        if downloaded:
            lines.append(f"其中 {downloaded} 部之前已經下載過（檔案還在），預設不勾選，只下載還沒有的歌。")
        if destination:
            lines.append(destination)
        if any(g.truncated for g in groups):
            lines.append(f"部分清單超過 {limit} 部，只列出前 {limit} 部。")
        hint = QLabel("\n".join(lines))
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)

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
        self.select_new = QPushButton("只選未下載的")
        self.select_new.setToolTip("勾選目前顯示的影片中還沒下載過的，已下載過的取消勾選")
        self.select_new.clicked.connect(self._select_not_downloaded)
        self.select_new.setVisible(downloaded > 0)
        tools = QHBoxLayout()
        tools.addWidget(self.search, 1)
        tools.addWidget(select_all)
        tools.addWidget(select_none)
        tools.addWidget(self.select_new)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["影片名稱", "預計檔名（點兩下可修改）", "長度", "已下載"])
        self.tree.headerItem().setToolTip(
            COL_NAME, "下載後的檔名（不含副檔名）。\n沒有修改時，若 YouTube 提供歌曲資訊（影片中的音樂），"
                      "下載時會以歌曲資訊為準；修改過的名稱一定採用。\n用「演出者 - 歌名」的寫法時，"
                      "音樂播放器也會顯示這個演出者與歌名。")
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # 只允許編輯「預計檔名」欄
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        for group in groups:
            self._add_group(group)
        self.tree.expandAll()
        self.tree.itemChanged.connect(lambda *_: self._update_count())
        self.tree.itemDoubleClicked.connect(self._edit_name)

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
        parent = QTreeWidgetItem(self.tree, [f"{group.title or '播放清單'}（{len(group.entries)} 部）", "", "", ""])
        parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
        for index, entry in enumerate(group.entries, 1):
            downloaded = group.downloaded.get(entry.url, "")
            if group.preselect_video_id is not None:
                checked = entry.video_id == group.preselect_video_id
            else:
                checked = not downloaded  # 播放清單同步：已下載過的預設不勾選
            name = group.names.get(entry.url, "")
            item = QTreeWidgetItem(parent, [f"{index}. {entry.title or entry.url}", name,
                                            _duration_text(entry.duration), "✓ 已下載" if downloaded else ""])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            item.setCheckState(COL_TITLE, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            item.setData(COL_TITLE, UrlRole, entry.url)
            item.setData(COL_TITLE, AutoNameRole, name)
            item.setData(COL_TITLE, DownloadedRole, bool(downloaded))
            item.setToolTip(COL_TITLE, f"{entry.title}\n{entry.url}" if entry.title else entry.url)
            item.setToolTip(COL_NAME, "點兩下可修改檔名")
            if downloaded:
                item.setToolTip(COL_STATUS, f"已下載：{downloaded}")
            item.setTextAlignment(COL_DURATION, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _edit_name(self, item: QTreeWidgetItem, column: int) -> None:
        if item.data(COL_TITLE, UrlRole):
            self.tree.editItem(item, COL_NAME)

    def _entry_items(self) -> list[QTreeWidgetItem]:
        items = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while (item := iterator.value()) is not None:
            if item.data(COL_TITLE, UrlRole):
                items.append(item)
            iterator += 1
        return items

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for item in self._entry_items():
            haystack = f"{item.text(COL_TITLE)}\n{item.text(COL_NAME)}".lower()
            item.setHidden(bool(keyword) and keyword not in haystack)

    def _set_checked(self, decide) -> None:
        self.tree.blockSignals(True)
        for item in self._entry_items():
            if not item.isHidden():
                state = Qt.CheckState.Checked if decide(item) else Qt.CheckState.Unchecked
                item.setCheckState(COL_TITLE, state)
        self.tree.blockSignals(False)
        self.tree.viewport().update()
        self._update_count()

    def _set_visible_checked(self, checked: bool) -> None:
        self._set_checked(lambda item: checked)

    def _select_not_downloaded(self) -> None:
        self._set_checked(lambda item: not item.data(COL_TITLE, DownloadedRole))

    def _update_count(self) -> None:
        total = len(self._entry_items())
        count = len(self.selected_urls())
        self.count_label.setText(f"已選 {count} / {total} 部")
        self.ok_button.setText(f"加入 {count} 部")
        self.ok_button.setEnabled(count > 0)

    def selected_by_group(self) -> list[list[str]]:
        """依清單分組回傳勾選的影片網址（順序與傳入的清單相同）。"""
        result = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            result.append([group.child(j).data(COL_TITLE, UrlRole) for j in range(group.childCount())
                           if group.child(j).checkState(COL_TITLE) == Qt.CheckState.Checked])
        return result

    def selected_urls(self) -> list[str]:
        """依清單順序回傳勾選的影片網址。"""
        return [item.data(COL_TITLE, UrlRole) for item in self._entry_items()
                if item.checkState(COL_TITLE) == Qt.CheckState.Checked]

    def custom_names(self) -> dict[str, str]:
        """使用者修改過的檔名：網址 → 新檔名（只含勾選的影片；改回原樣或清空的不算）。"""
        names = {}
        for item in self._entry_items():
            text = item.text(COL_NAME).strip()
            if (item.checkState(COL_TITLE) == Qt.CheckState.Checked and text
                    and text != (item.data(COL_TITLE, AutoNameRole) or "")):
                names[item.data(COL_TITLE, UrlRole)] = text
        return names
