"""整理舊檔案的歌名：掃描資料夾、預覽「目前檔名 → 整理後檔名」，勾選確認後改名，可復原。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from yt_media_tool.core import batch_rename
from yt_media_tool.core.batch_rename import RenamePlan, RenameResult
from yt_media_tool.gui.theme import STATUS_COLORS

COL_OLD, COL_NEW, COL_FOLDER = range(3)
PathRole = Qt.ItemDataRole.UserRole + 1
# 改名後通知主視窗更新佇列、歷史與播放清單紀錄：[(舊路徑, 新路徑), ...]
RenamedCallback = Callable[[list[tuple[Path, Path]]], None]


class RenameDialog(QDialog):
    def __init__(self, start_folder: str, parent: QWidget | None = None,
                 on_renamed: RenamedCallback | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("整理舊檔案的歌名")
        self.resize(980, 560)
        self._on_renamed = on_renamed
        self._root = Path(start_folder)
        self._last: list[RenameResult] = []

        hint = QLabel("把之前下載、檔名很長的 MP3 / MP4 改成「演出者 - 歌名」；YouTube 合輯資料夾（「Mix - …」）"
                      "改成「合輯 - 演出者 - 歌名」。\n"
                      "步驟：選資料夾 → 按「掃描」預覽 → 勾選要改的項目（「整理後名稱」可點兩下修改）→ 按「改名」。\n"
                      "只改檔名、不改檔案內容；不會覆蓋同名檔案；同名的字幕檔與播放清單檔會一起改。")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)

        self.folder_edit = QLineEdit(start_folder)
        browse = QPushButton("瀏覽…")
        browse.clicked.connect(self._browse)
        self.recursive = QCheckBox("包含子資料夾")
        self.recursive.setChecked(True)
        self.scan_button = QPushButton("掃描")
        self.scan_button.clicked.connect(self.scan)
        top = QHBoxLayout()
        top.addWidget(QLabel("資料夾："))
        top.addWidget(self.folder_edit, 1)
        top.addWidget(browse)
        top.addWidget(self.recursive)
        top.addWidget(self.scan_button)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["目前名稱", "整理後名稱（點兩下可修改）", "所在資料夾"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                   | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_OLD, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NEW, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_FOLDER, 140)
        self.table.itemChanged.connect(lambda *_: self._update_buttons())

        select_all = QPushButton("全選")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("全不選")
        select_none.clicked.connect(lambda: self._set_all(False))
        self.summary = QLabel()
        self.summary.setObjectName("hintLabel")
        self.summary.setWordWrap(True)
        self.undo_button = QPushButton("復原上次改名")
        self.undo_button.clicked.connect(self.undo)
        self.apply_button = QPushButton("改名")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.apply)
        close_button = QPushButton("關閉")
        close_button.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addWidget(select_all)
        bottom.addWidget(select_none)
        bottom.addWidget(self.summary, 1)
        bottom.addWidget(self.undo_button)
        bottom.addWidget(self.apply_button)
        bottom.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addLayout(bottom)
        self._update_buttons()

    # ---- 掃描與預覽 ----
    def _browse(self) -> None:
        start = self.folder_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "選擇要整理的資料夾", start)
        if chosen:
            self.folder_edit.setText(chosen)
            self.scan()

    def scan(self) -> int:
        folder = Path(self.folder_edit.text().strip())
        if not folder.is_dir():
            QMessageBox.warning(self, "整理舊檔案的歌名", f"資料夾不存在：\n{folder}")
            return 0
        self._root = folder
        recursive = self.recursive.isChecked()
        plans = batch_rename.scan(folder, recursive)
        media_count = len(batch_rename.media_files(folder, recursive))
        self.table.blockSignals(True)
        self.table.setRowCount(len(plans))
        for row, plan in enumerate(plans):
            old = QTableWidgetItem(("📁 " if plan.is_dir else "") + plan.path.name)
            old.setFlags((old.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
            old.setCheckState(Qt.CheckState.Checked)
            old.setData(PathRole, str(plan.path))
            old.setData(Qt.ItemDataRole.UserRole + 2, plan.is_dir)
            old.setToolTip(str(plan.path) + ("\n（合輯資料夾：裡面的檔案位置會一併更新）" if plan.is_dir else ""))
            new = QTableWidgetItem(plan.new_stem)
            new.setToolTip("資料夾名稱" if plan.is_dir else f"副檔名維持 {plan.path.suffix}")
            if plan.path == folder:
                where_text = "（所選的資料夾本身）"
            else:
                relative = plan.path.parent.relative_to(folder)
                where_text = "（此資料夾）" if str(relative) == "." else str(relative)
            where = QTableWidgetItem(where_text)
            where.setFlags(where.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for col, item in ((COL_OLD, old), (COL_NEW, new), (COL_FOLDER, where)):
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        file_count = sum(1 for p in plans if not p.is_dir)
        folder_count = len(plans) - file_count
        scope = "（含子資料夾）" if recursive else ""
        if media_count == 0 and not plans:
            text = f"這個資料夾{scope}裡沒有 MP3 / MP4 檔案。"
        elif not plans:
            text = f"掃描了 {media_count} 個 MP3 / MP4，檔名都已經整理好了（或無法判斷歌名），不需要改名。"
        else:
            parts = [f"{file_count} 個檔案"] if file_count else []
            parts += [f"{folder_count} 個合輯資料夾"] if folder_count else []
            tidy = media_count - file_count
            text = (f"掃描了 {media_count} 個 MP3 / MP4：可以整理 {'、'.join(parts)}"
                    + (f"；另有 {tidy} 個已經整理好。" if tidy else "。"))
        self.summary.setText(text)
        self.summary.setStyleSheet("")
        self._update_buttons()
        return len(plans)

    def checked_plans(self) -> list[RenamePlan]:
        plans = []
        for row in range(self.table.rowCount()):
            old, new = self.table.item(row, COL_OLD), self.table.item(row, COL_NEW)
            if old.checkState() == Qt.CheckState.Checked and new.text().strip():
                plans.append(RenamePlan(Path(old.data(PathRole)), new.text().strip(),
                                        is_dir=bool(old.data(Qt.ItemDataRole.UserRole + 2))))
        return plans

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            self.table.item(row, COL_OLD).setCheckState(state)

    def _update_buttons(self) -> None:
        count = len(self.checked_plans())
        self.apply_button.setText(f"改名（{count} 個）")
        self.apply_button.setEnabled(count > 0)
        self.undo_button.setEnabled(bool(self._last))

    # ---- 改名與復原 ----
    def apply(self) -> int:
        plans = self.checked_plans()
        if not plans:
            return 0
        question = (f"確定要將 {len(plans)} 個檔案改名嗎？\n"
                    "（同名檔案不會被覆蓋；之後可按「復原上次改名」還原）")
        if QMessageBox.question(self, "整理舊檔案的歌名", question) != QMessageBox.StandardButton.Yes:
            return 0
        results, errors = batch_rename.apply(plans)
        self._last = results
        self._notify([(r.old, r.new) for r in results])  # 先檔案、後資料夾（與實際改名順序相同）
        self._follow_root(results, forward=True)
        self.scan()
        message = f"已改名 {len(results)} 個項目。"
        if errors:
            message += f"另有 {len(errors)} 個無法改名：" + "；".join(f"{p.name}（{why}）" for p, why in errors[:3])
        self.summary.setText(message)
        self._color_summary(bool(errors))
        self._update_buttons()
        return len(results)

    def undo(self) -> int:
        if not self._last:
            return 0
        results, self._last = self._last, []
        errors = batch_rename.undo(results)
        failed = {p for p, _ in errors}
        # 復原時資料夾先還原，裡面檔案的路徑才對得上：依相反順序通知
        restored = [(r.new, r.old) for r in reversed(results) if r.new not in failed]
        self._notify(restored)
        self._follow_root([r for r in results if r.new not in failed], forward=False)
        self.scan()
        message = f"已復原 {len(restored)} 個項目。"
        if errors:
            message += f"另有 {len(errors)} 個無法復原：" + "；".join(f"{p.name}（{why}）" for p, why in errors[:3])
        self.summary.setText(message)
        self._color_summary(bool(errors))
        self._update_buttons()
        return len(restored)

    def _follow_root(self, results: list[RenameResult], forward: bool) -> None:
        """所選的資料夾本身被改名（或復原）時，更新資料夾欄位，重新掃描才找得到。"""
        current = Path(self.folder_edit.text().strip())
        for result in results:
            if not result.is_dir:
                continue
            before, after = (result.old, result.new) if forward else (result.new, result.old)
            if current == before:
                self.folder_edit.setText(str(after))
                current = after

    def _notify(self, pairs: list[tuple[Path, Path]]) -> None:
        if pairs and self._on_renamed is not None:
            self._on_renamed(pairs)

    def _color_summary(self, has_errors: bool) -> None:
        color = STATUS_COLORS["failed"] if has_errors else STATUS_COLORS["completed"]
        self.summary.setStyleSheet(f"color: {QColor(color).name()};")
