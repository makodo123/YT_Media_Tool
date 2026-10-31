"""在檔案總管中開啟資料夾、選取檔案，或以預設播放器開啟下載的媒體檔。

不經由 shell 執行：Windows 使用 Shell API（SHOpenFolderAndSelectItems），
其他平台使用參數清單呼叫 xdg-open / open。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# 只開啟本程式產生的媒體檔，避免把可執行檔等交給系統執行
MEDIA_SUFFIXES = {".mp3", ".mp4"}


def _windows_select_file(path: Path) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        ole32 = ctypes.windll.ole32  # type: ignore[attr-defined]
        shell32.ILCreateFromPathW.restype = ctypes.c_void_p
        shell32.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell32.ILFree.argtypes = [ctypes.c_void_p]
        shell32.SHOpenFolderAndSelectItems.argtypes = [
            ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD,
        ]
        ole32.CoInitialize(None)
        pidl = shell32.ILCreateFromPathW(str(path))
        if not pidl:
            return False
        try:
            return shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0) == 0
        finally:
            shell32.ILFree(pidl)
    except Exception:
        log.exception("SHOpenFolderAndSelectItems 失敗")
        return False


def _open_with_default_app(path: Path) -> bool:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])  # noqa: S607
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S607
        return True
    except OSError:
        log.exception("無法開啟 %s", path)
        return False


def open_folder(folder: Path) -> bool:
    folder = Path(folder)
    return folder.is_dir() and _open_with_default_app(folder)


def open_media(path: Path) -> bool:
    """以系統預設播放器開啟下載的 MP3 / MP4；其他類型的檔案一律不開啟。"""
    path = Path(path)
    return path.suffix.lower() in MEDIA_SUFFIXES and path.is_file() and _open_with_default_app(path)


def reveal_file(path: Path) -> bool:
    """開啟檔案所在位置；檔案不存在時改開啟其所在資料夾。"""
    path = Path(path)
    if path.is_file() and sys.platform.startswith("win") and _windows_select_file(path):
        return True
    return open_folder(path.parent if path.suffix or path.is_file() else path)
