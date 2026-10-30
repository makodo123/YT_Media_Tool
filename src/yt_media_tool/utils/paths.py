"""路徑相關工具：AppData 位置、隨附執行檔位置、安全檔名與同名檔案處理。

資料庫、設定與日誌一律寫入使用者 AppData（Windows）或 XDG 資料目錄（其他平台），
絕不寫入 EXE 所在的安裝目錄。
"""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path

from yt_media_tool import APP_ID

# Windows 不允許的檔名字元與保留名稱
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_STEM_LENGTH = 150


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_frozen() -> bool:
    """是否為 PyInstaller 打包後的執行環境。"""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """隨附資源所在目錄（打包後為 _internal，開發時為專案根目錄）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # src/yt_media_tool/utils/paths.py -> 專案根目錄
    return Path(__file__).resolve().parents[3]


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_dir()


def app_data_dir() -> Path:
    """應用程式資料目錄；可用環境變數 YTMT_DATA_DIR 覆寫（測試用）。"""
    override = os.environ.get("YTMT_DATA_DIR")
    if override:
        base = Path(override)
    elif is_windows():
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(root) / APP_ID if root else Path.home() / "AppData" / "Local" / APP_ID
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def database_path() -> Path:
    return app_data_dir() / "yt_media_tool.sqlite3"


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _windows_downloads_folder() -> Path | None:
    """透過 SHGetKnownFolderPath 取得使用者實際的「下載」資料夾（可能被重新導向）。"""
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        raw = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}").bytes_le
        guid = GUID.from_buffer_copy(raw)
        out = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        ole32 = ctypes.windll.ole32  # type: ignore[attr-defined]
        if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value) if out.value else None
        finally:
            ole32.CoTaskMemFree(out)
    except Exception:  # noqa: BLE001 - 任何失敗都回退至預設路徑
        return None


def default_download_dir() -> Path:
    downloads = _windows_downloads_folder() if is_windows() else None
    if downloads is None:
        downloads = Path.home() / "Downloads"
    return downloads / APP_ID


def sanitize_filename(name: str, max_length: int = MAX_STEM_LENGTH) -> str:
    """將影片標題轉為 Windows 合法的檔名主體（不含副檔名）。"""
    cleaned = _INVALID_CHARS.sub("_", name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")
    if not cleaned:
        cleaned = "untitled"
    if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


class FileNameReserver:
    """跨執行緒的檔名保留機制，確保多個同時進行的任務不會取得相同的輸出路徑。

    與磁碟上既有檔案或其他任務已保留的路徑同名時，會自動加上「 (1)」「 (2)」…，
    從不覆蓋使用者原有檔案。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reserved: set[str] = set()

    @staticmethod
    def _key(path: Path) -> str:
        # Windows 檔名不分大小寫
        return os.path.normcase(os.path.abspath(path))

    def reserve(self, directory: Path, stem: str, extension: str) -> Path:
        ext = extension if extension.startswith(".") else f".{extension}"
        with self._lock:
            counter = 0
            while True:
                suffix = f" ({counter})" if counter else ""
                candidate = directory / f"{stem}{suffix}{ext}"
                key = self._key(candidate)
                if key not in self._reserved and not candidate.exists():
                    self._reserved.add(key)
                    return candidate
                counter += 1
                if counter > 9999:
                    raise FileExistsError(f"無法為 {stem}{ext} 找到可用的檔名")

    def release(self, path: Path) -> None:
        with self._lock:
            self._reserved.discard(self._key(path))

    def is_reserved(self, path: Path) -> bool:
        with self._lock:
            return self._key(path) in self._reserved


def unique_output_path(directory: Path, stem: str, extension: str) -> Path:
    """不保留的單次查詢版本：回傳目前不存在的檔案路徑。"""
    return FileNameReserver().reserve(directory, stem, extension)
