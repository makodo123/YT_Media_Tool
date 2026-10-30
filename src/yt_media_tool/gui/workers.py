"""在背景執行緒進行的 GUI 輔助工作（例如展開播放清單），避免阻塞主執行緒。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

log = logging.getLogger(__name__)


class _Signals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class BackgroundJob(QRunnable):
    """在 QThreadPool 中執行 fn()，完成後以 signal 將結果送回主執行緒。"""

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _Signals()
        self.setAutoDelete(False)  # 由呼叫端保留參照，避免 signal 物件在結果送達前被回收

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            log.exception("背景工作失敗")
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(result)
