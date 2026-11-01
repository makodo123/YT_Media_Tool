"""將 yt-dlp、FFmpeg、磁碟空間與權限相關例外轉為使用者看得懂的繁體中文訊息。"""

from __future__ import annotations

import errno
import re

from yt_media_tool.core.converter import FFmpegNotFoundError, MediaProbeError
from yt_media_tool.core.cookies import CookieFileError


class DownloadCancelledError(Exception):
    """任務被使用者取消（或程式關閉時中斷）。"""

    def __init__(self, reason: str = "user") -> None:
        self.reason = reason
        super().__init__("下載已取消" if reason == "user" else "程式關閉，下載已中斷")


class InsufficientDiskSpaceError(OSError):
    def __init__(self, needed: int, free: int, directory: str) -> None:
        self.needed, self.free, self.directory = needed, free, directory
        super().__init__(errno.ENOSPC, "磁碟空間不足")


# Windows 錯誤碼
_WIN_DISK_FULL = {112, 39}  # ERROR_DISK_FULL, ERROR_HANDLE_DISK_FULL
_WIN_ACCESS = {5, 32, 33}  # ACCESS_DENIED, SHARING_VIOLATION, LOCK_VIOLATION
_WIN_PATH = {3, 206}  # PATH_NOT_FOUND, FILENAME_EXCED_RANGE

# 讀取瀏覽器 cookies 失敗：yt-dlp 會包著 FileNotFoundError 等底層例外，因此須在一般檔案錯誤之前判斷
_COOKIE_ERROR = re.compile(
    r"DPAPI|cookie database|cookies database|Failed to (decrypt|load) cookies|could not find .{0,40}cookies|"
    r"Unsupported browser|CookieLoadError", re.IGNORECASE)
_COOKIE_MESSAGE = (
    "無法讀取瀏覽器的登入資訊（cookies）。請確認 Firefox 已登入 YouTube 後完全關閉再試，"
    "或以瀏覽器擴充功能匯出 cookies.txt 後在「設定 → YouTube 登入資訊」指定。")

# (正規表示式, 說明)。依序比對 yt-dlp 的錯誤訊息。
_YTDLP_PATTERNS: list[tuple[str, str]] = [
    (r"DRM", "此內容受 DRM 數位版權保護，本工具不支援下載。"),
    (r"Private video", "這是私人影片，無法下載。"),
    (r"members[- ]only|Join this channel",
     "這是頻道會員專屬內容。若您是該頻道會員，可到「設定 → YouTube 登入資訊」使用該帳號的登入資訊後重試。"),
    (r"Sign in to confirm your age|age[- ]restricted|inappropriate for some users",
     "此影片有年齡限制，需要登入才能觀看。可到「設定 → YouTube 登入資訊」使用已登入 YouTube 的帳號後重試。"),
    (r"Sign in to confirm you.?re not a bot",
     "YouTube 要求登入以確認不是機器人。可到「設定 → YouTube 登入資訊」選擇已登入 YouTube 的 Firefox"
     "或 cookies.txt 後重試；若已設定，登入資訊可能已過期，請重新登入 YouTube 或重新匯出 cookies.txt。"
     "也可更換網路（例如關閉 VPN）後再試。"),
    (r"not available in your country|geo.?restrict|blocked it in your country",
     "此影片在您所在的地區無法觀看。"),
    (r"Premieres? in|This live event will begin", "影片尚未首播或直播尚未開始，無法下載。"),
    (r"playlist type is unviewable",
     "這是 YouTube 自動產生的「合輯」，無法用清單網址讀取。請改貼正在播放的歌曲網址（含 watch?v=…&list=RD…）。"),
    (r"is not a valid URL|Unsupported URL", "不支援的網址。"),
    (r"Video unavailable|This video has been removed|does not exist|"
     r"account associated with this video has been terminated",
     "影片不存在、已被移除或無法觀看。"),
    (r"Requested format is not available", "找不到符合條件的影片格式。"),
    (r"HTTP Error 429|Too Many Requests", "請求次數過多（HTTP 429），YouTube 暫時限制存取，請稍後再試。"),
    (r"HTTP Error 403", "YouTube 拒絕存取（HTTP 403），通常是下載連結過期，請按「重試」。"
     "若一直發生，可能是 YouTube 改版，請到「說明 → 檢查新版本」更新本程式。"),
    (r"HTTP Error 404", "找不到影片或檔案（HTTP 404），請確認網址是否正確後重試。"),
    (r"Unable to download webpage|Failed to resolve|getaddrinfo|Name or service not known|"
     r"timed out|Connection (reset|refused|aborted)|Network is unreachable|URLError|SSL",
     "網路連線失敗，請確認網路狀態後重試。"),
    (r"ffmpeg|ffprobe|Postprocessing|Conversion failed", "FFmpeg 處理失敗（影音合併或轉檔錯誤）。"),
]


def _oserror_message(exc: OSError) -> str | None:
    winerror = getattr(exc, "winerror", None)
    target = exc.filename or ""
    where = f"：{target}" if target else ""
    if isinstance(exc, InsufficientDiskSpaceError):
        return (f"磁碟空間不足：預估需要 {exc.needed / 1024 / 1024:.0f} MB，"
                f"目前僅剩 {exc.free / 1024 / 1024:.0f} MB（{exc.directory}）。請清出空間或更換下載資料夾。")
    if exc.errno == errno.ENOSPC or winerror in _WIN_DISK_FULL:
        return "磁碟空間不足，請清出空間或更換下載資料夾。"
    if isinstance(exc, PermissionError) or exc.errno in (errno.EACCES, errno.EPERM) or winerror in _WIN_ACCESS:
        return (f"沒有寫入權限或檔案正被其他程式使用{where}。"
                "請更換下載資料夾（避免 C:\\Program Files 等受保護位置），或關閉正在使用該檔案的程式。")
    if exc.errno == errno.ENAMETOOLONG or winerror == 206:
        return "檔案路徑過長，請改用較短的下載資料夾路徑。"
    if isinstance(exc, FileNotFoundError) or winerror in _WIN_PATH:
        return f"找不到指定的資料夾或檔案{where}。"
    return None


def explain_error(exc: BaseException) -> str:
    """回傳適合顯示給使用者的錯誤說明，並附上原始訊息以利排查。"""
    if isinstance(exc, DownloadCancelledError):
        return str(exc)
    if isinstance(exc, (FFmpegNotFoundError, CookieFileError)):
        return str(exc)
    if isinstance(exc, MediaProbeError):
        return f"輸出檔案檢查失敗：{exc}"

    raw = _clean(str(exc))
    if _COOKIE_ERROR.search(raw):
        return f"{_COOKIE_MESSAGE}\n詳細資訊：{raw}"

    # yt-dlp 會把底層例外包在 DownloadError.exc_info 中
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain and len(chain) < 10:
        chain.append(current)
        exc_info = getattr(current, "exc_info", None)
        nested = exc_info[1] if isinstance(exc_info, tuple) and len(exc_info) > 1 else None
        current = nested or current.__cause__ or current.__context__
    for item in chain:
        if isinstance(item, OSError) and not _is_network_oserror(item):
            message = _oserror_message(item)
            if message:
                return message

    for pattern, message in _YTDLP_PATTERNS:
        if re.search(pattern, raw, re.IGNORECASE):
            return f"{message}\n詳細資訊：{raw}" if raw else message
    return f"下載失敗：{raw}" if raw else f"下載失敗（{type(exc).__name__}）"


def _is_network_oserror(exc: OSError) -> bool:
    import socket

    return isinstance(exc, (ConnectionError, TimeoutError, socket.gaierror))


def _clean(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)  # 移除 ANSI 色碼
    text = re.sub(r"^ERROR:\s*", "", text.strip())
    return text[:1000]
