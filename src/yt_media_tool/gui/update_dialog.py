"""更新視窗：顯示「檢查中 → 下載中（進度條）→ 可安裝 → 安裝中」每一步與成功 / 失敗的結果。

視窗本身不做任何網路或檔案工作，只依主視窗提供的狀態顯示文字、進度與按鈕；
按鈕以 actionRequested 訊號通知主視窗（retry_check、download、cancel、install、page、copy）。
關閉視窗不會中斷下載，主視窗上方的提示會繼續顯示進度。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

# 狀態
CHECKING = "checking"
LATEST = "latest"
CHECK_FAILED = "check_failed"
PORTABLE = "portable"
AVAILABLE = "available"
DOWNLOADING = "downloading"
DOWNLOAD_FAILED = "download_failed"
READY = "ready"
INSTALLING = "installing"
UPDATED = "updated"
INSTALL_FAILED = "install_failed"

# 按鈕：（動作, 文字）；第一個為預設按鈕
_BUTTONS: dict[str, list[tuple[str, str]]] = {
    CHECKING: [("close", "關閉")],
    LATEST: [("close", "確定")],
    CHECK_FAILED: [("retry_check", "重試"), ("close", "關閉")],
    PORTABLE: [("page", "前往下載頁面"), ("close", "關閉")],
    AVAILABLE: [("download", "下載並安裝"), ("page", "前往下載頁面"), ("close", "稍後")],
    DOWNLOADING: [("close", "在背景繼續下載"), ("cancel", "取消下載")],
    DOWNLOAD_FAILED: [("download", "重試"), ("page", "前往下載頁面"), ("close", "關閉")],
    READY: [("install", "立即安裝並重新開啟"), ("close", "稍後")],
    INSTALLING: [],
    UPDATED: [("close", "確定"), ("page", "查看新版說明")],
    INSTALL_FAILED: [("page", "下載安裝程式手動更新"), ("copy", "複製詳細資訊"), ("close", "關閉")],
}

_TITLES = {
    CHECKING: "正在檢查新版本…",
    LATEST: "已是最新版本",
    CHECK_FAILED: "檢查新版本失敗",
    PORTABLE: "有新版本",
    AVAILABLE: "有新版本",
    DOWNLOADING: "正在下載新版本…",
    DOWNLOAD_FAILED: "下載更新失敗",
    READY: "新版本已下載完成",
    INSTALLING: "正在安裝更新…",
    UPDATED: "更新成功",
    INSTALL_FAILED: "更新沒有完成",
}

SUCCESS_STATES = {LATEST, READY, UPDATED}
FAILURE_STATES = {CHECK_FAILED, DOWNLOAD_FAILED, INSTALL_FAILED}


@dataclass
class UpdateView:
    state: str
    message: str = ""
    progress: float = 0.0  # 下載進度 0～100


class UpdateDialog(QDialog):
    actionRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("檢查新版本")
        self.setMinimumWidth(480)
        self.state = ""
        self.heading = QLabel()
        self.heading.setObjectName("dialogHeading")
        font = self.heading.font()
        font.setPointSizeF(font.pointSizeF() * 1.25)
        font.setBold(True)
        self.heading.setFont(font)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.bar = QProgressBar()
        self.bar.setTextVisible(True)
        self._buttons = QHBoxLayout()
        self._buttons.addStretch(1)
        self.button_widgets: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(self.heading)
        layout.addWidget(self.message)
        layout.addWidget(self.bar)
        layout.addSpacing(6)
        layout.addLayout(self._buttons)

    def show_view(self, view: UpdateView) -> None:
        if view.state != self.state:
            self.state = view.state
            self._rebuild_buttons()
        self.heading.setText(("✓ " if view.state in SUCCESS_STATES else "✕ " if view.state in FAILURE_STATES
                              else "") + _TITLES[view.state])
        color = "#4caf50" if view.state in SUCCESS_STATES else "#ef5350" if view.state in FAILURE_STATES else ""
        self.heading.setStyleSheet(f"color: {color};" if color else "")
        self.message.setText(view.message)
        if view.state in (CHECKING, INSTALLING):
            self.bar.setRange(0, 0)  # 不確定要多久：來回跑動的進度條
            self.bar.show()
        elif view.state == DOWNLOADING:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(view.progress))
            self.bar.setFormat("%p%")
            self.bar.show()
        else:
            self.bar.hide()

    def _rebuild_buttons(self) -> None:
        for button in self.button_widgets.values():
            self._buttons.removeWidget(button)
            button.deleteLater()
        self.button_widgets = {}
        for index, (action, text) in enumerate(_BUTTONS[self.state]):
            button = QPushButton(text)
            if index == 0:
                button.setDefault(True)
                button.setObjectName("primaryButton")
            button.clicked.connect(lambda _=False, a=action: self._clicked(a))
            self._buttons.addWidget(button)
            self.button_widgets[action] = button

    def _clicked(self, action: str) -> None:
        if action == "close":
            self.close()
        else:
            self.actionRequested.emit(action)
