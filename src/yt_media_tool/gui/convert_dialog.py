"""本機檔案轉 MP3 對話框：加入（或拖曳）影音檔，依序以背景執行緒轉檔。"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from yt_media_tool.core.converter import ToolInfo
from yt_media_tool.core.local_convert import (
    BITRATES, MEDIA_SUFFIXES, ConvertCancelledError, ConvertError, convert_to_mp3, is_media_file,
)
from yt_media_tool.gui.theme import STATUS_COLORS
from yt_media_tool.utils import system_open
from yt_media_tool.utils.paths import FileNameReserver

COL_FILE, COL_STATUS = range(2)
PathRole = Qt.ItemDataRole.UserRole + 1


class _Signals(QObject):
    progress = Signal(int, float)
    done = Signal(int, bool, str, str)  # 列、成功、狀態文字、輸出路徑
    finished = Signal()


class ConvertDialog(QDialog):
    def __init__(self, tools: ToolInfo, default_bitrate: str = "192", parent: QWidget | None = None,
                 files: list[Path] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("本機檔案轉 MP3")
        self.resize(760, 480)
        self.setAcceptDrops(True)
        self._tools = tools
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._reserver = FileNameReserver()
        self.signals = _Signals()
        self.signals.progress.connect(self._on_progress)
        self.signals.done.connect(self._on_done)
        self.signals.finished.connect(self._on_finished)

        hint = QLabel("把電腦裡的影片或音訊檔轉成 MP3（例如手機錄的影片）。"
                      "可按「加入檔案」或直接把檔案拖曳到這個視窗。\n"
                      "原檔不會被修改；同名的 MP3 已存在時會自動加上編號，不會覆蓋。")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["檔案", "狀態"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        # 狀態欄放得下「完成：檔名（附註）」與失敗原因；完整內容在提示
        self.table.horizontalHeader().setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_FILE, 260)
        self.table.cellDoubleClicked.connect(self._reveal_row)

        self.add_button = QPushButton("加入檔案…")
        self.add_button.clicked.connect(self._browse_files)
        self.remove_button = QPushButton("移除所選")
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self._clear)
        list_buttons = QHBoxLayout()
        for button in (self.add_button, self.remove_button, self.clear_button):
            list_buttons.addWidget(button)
        list_buttons.addStretch(1)

        self.bitrate = QComboBox()
        for value in BITRATES:
            self.bitrate.addItem(f"{value} kbps", value)
        self.bitrate.setCurrentIndex(max(0, self.bitrate.findData(default_bitrate)))
        self.same_folder = QRadioButton("與原檔相同的資料夾")
        self.other_folder = QRadioButton("指定資料夾：")
        self.same_folder.setChecked(True)
        folder_group = QButtonGroup(self)
        folder_group.addButton(self.same_folder)
        folder_group.addButton(self.other_folder)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("選擇要存放 MP3 的資料夾")
        self.folder_edit.textEdited.connect(lambda: self.other_folder.setChecked(True))
        browse = QPushButton("瀏覽…")
        browse.clicked.connect(self._browse_folder)
        options = QHBoxLayout()
        options.addWidget(QLabel("音質："))
        options.addWidget(self.bitrate)
        options.addSpacing(16)
        options.addWidget(QLabel("存到："))
        options.addWidget(self.same_folder)
        options.addWidget(self.other_folder)
        options.addWidget(self.folder_edit, 1)
        options.addWidget(browse)

        self.summary = QLabel()
        self.summary.setObjectName("hintLabel")
        self.start_button = QPushButton("開始轉檔")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start_or_cancel)
        close_button = QPushButton("關閉")
        close_button.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addWidget(self.summary, 1)
        bottom.addWidget(self.start_button)
        bottom.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.table, 1)
        layout.addLayout(list_buttons)
        layout.addLayout(options)
        layout.addLayout(bottom)
        if files:
            self.add_files(files)
        self._update_buttons()

    # ---- 檔案清單 ----
    def files(self) -> list[Path]:
        return [Path(self.table.item(r, COL_FILE).data(PathRole)) for r in range(self.table.rowCount())]

    def add_files(self, paths: list[Path]) -> int:
        """加入影音檔（略過重複與不支援的檔案），回傳加入的數量。"""
        existing = {str(p) for p in self.files()}
        skipped, added = [], 0
        for path in paths:
            path = Path(path)
            if not path.is_file() or not is_media_file(path):
                skipped.append(path.name)
                continue
            if str(path) in existing:
                continue
            existing.add(str(path))
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(path.name)
            item.setData(PathRole, str(path))
            item.setToolTip(str(path))
            self.table.setItem(row, COL_FILE, item)
            self.table.setItem(row, COL_STATUS, QTableWidgetItem("等待中"))
            added += 1
        if skipped:
            self.summary.setText(f"已略過不支援的檔案：{'、'.join(skipped[:5])}" + ("…" if len(skipped) > 5 else ""))
        self._update_buttons()
        return added

    def _browse_files(self) -> None:
        patterns = " ".join(f"*{s}" for s in MEDIA_SUFFIXES)
        chosen, _ = QFileDialog.getOpenFileNames(self, "選擇影音檔", str(Path.home()),
                                                 f"影音檔 ({patterns});;所有檔案 (*)")
        self.add_files([Path(p) for p in chosen])

    def _browse_folder(self) -> None:
        start = self.folder_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "選擇存放 MP3 的資料夾", start)
        if chosen:
            self.folder_edit.setText(chosen)
            self.other_folder.setChecked(True)

    def _remove_selected(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self._update_buttons()

    def _clear(self) -> None:
        self.table.setRowCount(0)
        self.summary.clear()
        self._update_buttons()

    def _reveal_row(self, row: int, _col: int = 0) -> None:
        output = self.table.item(row, COL_STATUS).data(PathRole)
        if output and Path(output).is_file():
            system_open.reveal_file(Path(output))

    # ---- 拖放 ----
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if paths and not self.is_running():
            event.acceptProposedAction()
            self.add_files(paths)

    # ---- 轉檔 ----
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _update_buttons(self) -> None:
        running = self.is_running()
        has_files = self.table.rowCount() > 0
        self.start_button.setText("取消" if running else "開始轉檔")
        self.start_button.setEnabled(running or has_files)
        for widget in (self.add_button, self.remove_button, self.clear_button, self.bitrate,
                       self.same_folder, self.other_folder, self.folder_edit):
            widget.setEnabled(not running)

    def output_dir_for(self, source: Path) -> Path | None:
        if self.same_folder.isChecked():
            return source.parent
        folder = self.folder_edit.text().strip()
        return Path(folder) if folder else None

    def _start_or_cancel(self) -> None:
        if self.is_running():
            self._cancel.set()
            self.start_button.setEnabled(False)
            self.summary.setText("正在取消…")
            return
        if not self._tools.available:
            QMessageBox.warning(self, "本機檔案轉 MP3", "找不到 FFmpeg，無法轉檔。請到「工具 → 檢查相依元件」查看。")
            return
        if self.other_folder.isChecked() and not self.folder_edit.text().strip():
            QMessageBox.warning(self, "本機檔案轉 MP3", "請選擇要存放 MP3 的資料夾。")
            return
        jobs = []
        for row, source in enumerate(self.files()):
            status = self.table.item(row, COL_STATUS)
            if status.data(PathRole):  # 已轉好的不重複轉
                continue
            status.setText("等待中")
            status.setForeground(QColor(STATUS_COLORS["waiting"]))
            jobs.append((row, source, self.output_dir_for(source)))
        if not jobs:
            self.summary.setText("清單中的檔案都已轉好了。")
            return
        self._cancel.clear()
        self._thread = threading.Thread(target=self._work, args=(jobs, self.bitrate.currentData()), daemon=True)
        self._thread.start()
        self.summary.setText(f"轉檔中…（共 {len(jobs)} 個檔案）")
        self._update_buttons()

    def _work(self, jobs: list[tuple[int, Path, Path]], bitrate: str) -> None:
        for row, source, output_dir in jobs:
            if self._cancel.is_set():
                self.signals.done.emit(row, False, "已取消", "")
                continue
            try:
                result = convert_to_mp3(source, output_dir, bitrate, self._tools,
                                        on_progress=lambda pct, r=row: self.signals.progress.emit(r, pct),
                                        cancel=self._cancel, reserver=self._reserver)
            except ConvertCancelledError:
                self.signals.done.emit(row, False, "已取消", "")
            except ConvertError as exc:
                self.signals.done.emit(row, False, f"失敗：{exc}", "")
            except OSError as exc:
                self.signals.done.emit(row, False, f"失敗：無法寫入（{exc.strerror or exc}）", "")
            else:
                note = ""
                if result.source_kbps and result.source_kbps < int(bitrate) * 0.9:
                    note = f"（原始約 {result.source_kbps:.0f} kbps，音質不會提升）"
                self.signals.done.emit(row, True, f"完成：{result.output.name}{note}", str(result.output))
        self.signals.finished.emit()

    def _on_progress(self, row: int, pct: float) -> None:
        item = self.table.item(row, COL_STATUS)
        if item is not None:
            item.setText(f"轉檔中 {pct:.0f}%")
            item.setForeground(QColor(STATUS_COLORS["processing"]))

    def _on_done(self, row: int, ok: bool, text: str, output: str) -> None:
        item = self.table.item(row, COL_STATUS)
        if item is None:
            return
        item.setText(text)
        item.setToolTip(text + ("\n雙擊可在檔案總管中顯示" if ok else ""))
        item.setData(PathRole, output or None)
        status = "completed" if ok else ("cancelled" if text == "已取消" else "failed")
        item.setForeground(QColor(STATUS_COLORS[status]))

    def _on_finished(self) -> None:
        self._thread = None
        texts = [self.table.item(r, COL_STATUS).text() for r in range(self.table.rowCount())]
        done = sum(t.startswith("完成") for t in texts)
        failed = sum(t.startswith("失敗") for t in texts)
        failed_note = f"、失敗 {failed} 個（滑鼠停在狀態上可看原因）" if failed else ""
        self.summary.setText(f"轉檔結束：完成 {done} 個{failed_note}。雙擊已完成的項目可在檔案總管中顯示。")
        self._update_buttons()

    def wait_finished(self, timeout: float = 30.0) -> None:
        """測試用：等待背景轉檔結束。"""
        if self._thread is not None:
            self._thread.join(timeout)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_running():
            answer = QMessageBox.question(self, "本機檔案轉 MP3", "仍在轉檔中，確定要取消並關閉嗎？")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._cancel.set()
            self.wait_finished(15.0)
        event.accept()
