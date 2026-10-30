"""日誌設定：寫入 AppData\\logs，採輪替檔案避免無限制成長。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from yt_media_tool.utils import paths

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO, directory: Path | None = None) -> Path:
    """設定根記錄器，回傳日誌檔路徑。重複呼叫不會重複加入 handler。"""
    global _configured
    log_path = (directory or paths.log_dir()) / "yt_media_tool.log"
    if _configured:
        return log_path

    root = logging.getLogger()
    root.setLevel(level)
    file_handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(file_handler)

    # 打包為視窗程式時 sys.stderr 可能是 None
    if sys.stderr is not None and not paths.is_frozen():
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(console)

    _configured = True
    return log_path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
