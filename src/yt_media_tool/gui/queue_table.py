"""下載佇列表格：資料模型、進度條與操作按鈕 delegate。"""

from __future__ import annotations

import re

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QPersistentModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QHeaderView, QStyle, QStyledItemDelegate, QStyleOptionButton,
    QStyleOptionProgressBar, QStyleOptionViewItem, QTableView,
)

from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus, format_eta, format_speed
from yt_media_tool.gui.theme import STATUS_COLORS

COLUMNS = ["編號", "影片名稱", "格式", "品質", "進度", "速度", "剩餘時間", "狀態", "操作"]
COL_ID, COL_TITLE, COL_FORMAT, COL_QUALITY, COL_PROGRESS, COL_SPEED, COL_ETA, COL_STATUS, COL_ACTIONS = range(9)

ACTION_CANCEL = "cancel"
ACTION_RETRY = "retry"
ACTION_OPEN = "open"
ACTION_LABELS = {ACTION_CANCEL: "取消", ACTION_RETRY: "重試", ACTION_OPEN: "開啟位置"}

TaskRole = Qt.ItemDataRole.UserRole + 1


def actions_for(task: DownloadTask) -> list[str]:
    if task.status is TaskStatus.COMPLETED:
        return [ACTION_OPEN]
    if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
        return [ACTION_RETRY, ACTION_OPEN]
    return [ACTION_CANCEL, ACTION_OPEN]


def status_text(task: DownloadTask) -> str:
    if task.cancel_requested and not task.status.is_finished:
        return "取消中…"
    if task.status.is_active and task.stage:
        return task.stage  # 例如「取得影片資訊中」「影音合併中」「MP3 轉檔中」
    return task.status.label


def quality_text(task: DownloadTask) -> str:
    """品質欄文字：實際品質與目標相同時只顯示一次；低於目標時顯示「目標 → 實際 ⚠」
    （MP3 的實際值為原始音源位元率，例如「192 kbps → 124 kbps ⚠」）；
    影片還有更高解析度時附上「（最高 1080p）」。

    完整說明（編碼、可用解析度、原始音源位元率）見儲存格提示。
    """
    actual = task.actual_quality
    if not actual:
        return task.quality_text
    if task.media_format is MediaFormat.MP3:
        source = re.search(r"原始音源約 (\d+) kbps", actual)
        if source and "高於原始音源" in actual:
            return f"{task.quality_text} → {source.group(1)} kbps ⚠"
        return task.quality_text
    match = re.match(r"(\d+)p", actual)
    if not match:
        return f"{task.quality_text} → {actual.split('（')[0].strip()}"
    height = int(match.group(1))
    if task.quality == "best":
        return f"{task.quality_text} → {height}p"
    if height != int(task.quality):
        return f"{task.quality_text} → {height}p" + (" ⚠" if height < int(task.quality) else "")
    highest = re.search(r"最高 (\d+)p", actual)
    if highest and int(highest.group(1)) > height:
        return f"{task.quality_text}（最高 {highest.group(1)}p）"
    return task.quality_text


class QueueTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tasks: list[DownloadTask] = []
        self._rows: dict[int, int] = {}

    # ---- Qt 介面 ----
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        col = index.column()
        if role == TaskRole:
            return task
        if role == Qt.ItemDataRole.DisplayRole:
            return {
                COL_ID: str(task.id),
                COL_TITLE: task.display_title,
                COL_FORMAT: task.media_format.label,
                COL_QUALITY: quality_text(task),
                COL_PROGRESS: f"{task.progress:.1f}%",
                COL_SPEED: format_speed(task.speed) if task.status.is_active else "",
                COL_ETA: format_eta(task.eta) if task.status.is_active else "",
                COL_STATUS: status_text(task),
                COL_ACTIONS: "",
            }.get(col)
        if role == Qt.ItemDataRole.ToolTipRole:
            if col == COL_TITLE:
                return f"{task.display_title}\n{task.url}"
            if col == COL_QUALITY and task.actual_quality:
                return f"目標：{task.quality_text}\n實際：{task.actual_quality}"
            if col == COL_STATUS and task.error_message:
                return task.error_message
        if role == Qt.ItemDataRole.ForegroundRole and col == COL_STATUS:
            return QColor(STATUS_COLORS.get(task.status.value, "#e6e9ee"))
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (COL_ID, COL_FORMAT, COL_SPEED, COL_ETA):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    # ---- 資料操作 ----
    def _reindex(self) -> None:
        self._rows = {t.id: i for i, t in enumerate(self._tasks)}  # type: ignore[misc]

    def set_tasks(self, tasks: list[DownloadTask]) -> None:
        self.beginResetModel()
        self._tasks = sorted(tasks, key=lambda t: (t.sort_order, t.id or 0))
        self._reindex()
        self.endResetModel()

    def upsert(self, task: DownloadTask) -> None:
        row = self._rows.get(task.id)  # type: ignore[arg-type]
        if row is None:
            pos = len(self._tasks)
            for i, existing in enumerate(self._tasks):
                if (existing.sort_order, existing.id or 0) > (task.sort_order, task.id or 0):
                    pos = i
                    break
            self.beginInsertRows(QModelIndex(), pos, pos)
            self._tasks.insert(pos, task)
            self._reindex()
            self.endInsertRows()
            return
        old = self._tasks[row]
        self._tasks[row] = task
        if old.sort_order != task.sort_order:
            self.set_tasks(self._tasks)
        else:
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLUMNS) - 1))

    def remove(self, task_id: int) -> None:
        row = self._rows.get(task_id)
        if row is None:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._tasks[row]
        self._reindex()
        self.endRemoveRows()

    def task_at(self, row: int) -> DownloadTask | None:
        return self._tasks[row] if 0 <= row < len(self._tasks) else None

    def row_of(self, task_id: int) -> int | None:
        return self._rows.get(task_id)

    def tasks(self) -> list[DownloadTask]:
        return list(self._tasks)


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        task: DownloadTask | None = index.data(TaskRole)
        if task is None:
            return super().paint(painter, option, index)
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(4, 5, -4, -5)
        bar.minimum, bar.maximum = 0, 1000
        bar.progress = int(task.progress * 10)
        bar.text = f"{task.progress:.1f}%"
        bar.textVisible = True
        bar.state = option.state | QStyle.StateFlag.State_Enabled
        bar.palette = option.palette
        if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            bar.palette.setColor(bar.palette.ColorRole.Highlight, QColor("#6b4040"))
        elif task.status is TaskStatus.COMPLETED:
            bar.palette.setColor(bar.palette.ColorRole.Highlight, QColor("#2f8a57"))
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter, option.widget)


class ActionDelegate(QStyledItemDelegate):
    """在儲存格內繪製操作按鈕，點擊時發出 actionTriggered(task_id, action)。"""

    actionTriggered = Signal(int, str)
    BUTTON_SPACING = 4

    def _button_rects(self, option: QStyleOptionViewItem, task: DownloadTask) -> list[tuple[str, QRect]]:
        metrics = option.fontMetrics
        option_rect = option.rect
        x = option_rect.x() + 4
        rects = []
        for action in actions_for(task):
            width = metrics.horizontalAdvance(ACTION_LABELS[action]) + 16
            rects.append((action, QRect(x, option_rect.y() + 3, width, option_rect.height() - 6)))
            x += width + self.BUTTON_SPACING
        return rects

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        task: DownloadTask | None = index.data(TaskRole)
        if task is None:
            return
        style = option.widget.style() if option.widget else QApplication.style()
        for action, rect in self._button_rects(option, task):
            btn = QStyleOptionButton()
            btn.rect = rect
            btn.text = ACTION_LABELS[action]
            btn.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Raised
            btn.palette = option.palette
            style.drawControl(QStyle.ControlElement.CE_PushButton, btn, painter, option.widget)

    def editorEvent(self, event: QEvent, model, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
            task: DownloadTask | None = index.data(TaskRole)
            if task is not None and event.button() == Qt.MouseButton.LeftButton:
                for action, rect in self._button_rects(option, task):
                    if rect.contains(event.position().toPoint()):
                        self.actionTriggered.emit(task.id, action)
                        return True
        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        size = super().sizeHint(option, index)
        size.setWidth(170)
        return size


class QueueTableView(QTableView):
    actionTriggered = Signal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.queue_model = QueueTableModel(self)
        self.setModel(self.queue_model)
        self._progress_delegate = ProgressDelegate(self)
        self._action_delegate = ActionDelegate(self)
        self._action_delegate.actionTriggered.connect(self.actionTriggered)
        self.setItemDelegateForColumn(COL_PROGRESS, self._progress_delegate)
        self.setItemDelegateForColumn(COL_ACTIONS, self._action_delegate)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setHighlightSections(False)
        for col, width in {COL_ID: 50, COL_FORMAT: 55, COL_QUALITY: 150, COL_PROGRESS: 120, COL_SPEED: 90,
                           COL_ETA: 75, COL_STATUS: 150, COL_ACTIONS: 150}.items():
            self.setColumnWidth(col, width)

    def selected_task_ids(self) -> list[int]:
        rows = sorted({index.row() for index in self.selectionModel().selectedRows()})
        return [t.id for r in rows if (t := self.queue_model.task_at(r)) is not None]  # type: ignore[misc]

    def current_task(self) -> DownloadTask | None:
        index = self.currentIndex()
        return self.queue_model.task_at(index.row()) if index.isValid() else None
