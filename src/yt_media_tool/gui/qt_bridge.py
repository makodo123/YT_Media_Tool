"""把 QueueManager 的回呼（可能來自工作執行緒）轉為 Qt signal，交由主執行緒處理。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal


class QueueEventBridge(QObject):
    # 跨執行緒發出的 signal 會以 QueuedConnection 傳遞到接收者所在的主執行緒
    event = Signal(str, object)

    def __call__(self, event: str, payload: Any) -> None:
        self.event.emit(event, payload)
