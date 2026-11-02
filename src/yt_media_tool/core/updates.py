"""檢查、下載並安裝 GitHub 上的新正式版本。

- 只向 GitHub API 讀取最新正式版的版本號與檔案檢查碼（不含測試版），不傳送任何個人資料。
- GitHub API 未登入時每個網路每小時只能查詢 60 次；額度用完（或 API 無法連線）時，
  改從 Releases 網頁的「最新版」轉址得知版本號，此時只以 Release 附的 .sha256 檔驗證。
- 下載網址由固定的儲存庫與版本號組成，不採用 API 回傳的連結。
- 下載的安裝程式須同時符合 GitHub 計算的檢查碼（API 的 digest）與 Release 附的 .sha256 檔，才會被使用。
- 只有「安裝版」能自動安裝；免安裝版（zip）請使用者自行下載。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_media_tool import __version__
from yt_media_tool.utils import paths, win_job

log = logging.getLogger(__name__)

REPO = "makodo123/YT_Media_Tool"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
HELP_PAGE = f"https://github.com/{REPO}#readme"  # 使用說明（README）
DOWNLOAD_BASE = f"https://github.com/{REPO}/releases/download"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_SETUP_BYTES = 1024 * 1024 * 1024  # 安裝程式大小上限（防止異常回應塞滿磁碟）
CHUNK = 256 * 1024

_TAG_URL = re.compile(rf"^https://github\.com/{re.escape(REPO)}/releases/tag/(v?\d+\.\d+\.\d+)/?$")
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
Opener = Callable[..., Any]


class UpdateError(Exception):
    """下載或驗證更新失敗；訊息為顯示給使用者的中文說明。"""


class UpdateCheckError(UpdateError):
    """查詢最新版本失敗。"""


RATE_LIMIT_MESSAGE = ("GitHub 暫時限制查詢次數（同一個網路每小時約 60 次），而且備用的查詢方式也無法連線。\n"
                      "請稍後（約一小時）再試；程式下次開啟時也會自動再檢查。")
OFFLINE_MESSAGE = "無法連線到 GitHub 檢查新版本，請確認網路連線後再試。"


class UpdateCancelledError(UpdateError):
    def __init__(self) -> None:
        super().__init__("已取消下載更新")


@dataclass(frozen=True)
class LatestRelease:
    version: str  # 例如「2.6.0」
    setup_name: str  # 例如「YT_Media_Tool-2.6.0-win64-setup.exe」
    setup_digest: str | None  # GitHub 計算的 SHA256（小寫十六進位）；舊版 API 可能沒有

    @property
    def tag(self) -> str:
        return f"v{self.version}"

    @property
    def setup_url(self) -> str:
        return f"{DOWNLOAD_BASE}/{self.tag}/{self.setup_name}"

    @property
    def sha256_url(self) -> str:
        return f"{self.setup_url}.sha256"


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    """解析「v2.4.0」或「2.4.0」；含測試版後綴（例如 -beta.1）或格式不符時回傳 None。"""
    match = _VERSION.match((text or "").strip())
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def is_newer(latest: str, current: str = __version__) -> bool:
    latest_v, current_v = parse_version(latest), parse_version(current)
    return bool(latest_v and current_v and latest_v > current_v)


def _request(url: str, accept: str = "*/*") -> urllib.request.Request:
    if not url.startswith(("https://api.github.com/", "https://github.com/")):
        raise ValueError(f"不允許的網址：{url}")
    # 已限制為 GitHub 的 https 網址（S310）
    return urllib.request.Request(url, headers={"Accept": accept,  # noqa: S310
                                                "User-Agent": f"YT-Media-Tool/{__version__}"})


def _rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 429)


def fetch_latest_release(timeout: float = 10.0, opener: Opener = urllib.request.urlopen) -> LatestRelease | None:
    """讀取最新正式版；回應格式不符時回傳 None。

    先查 GitHub API（含檔案檢查碼）；API 額度用完或無法連線時改用 Releases 網頁（只有版本號）。
    兩種方式都失敗時拋出 UpdateCheckError（訊息可直接顯示給使用者）。
    """
    try:
        return _fetch_from_api(timeout, opener)
    except (OSError, ValueError) as exc:  # HTTPError / URLError 皆為 OSError；ValueError：回應不是 JSON
        api_error = exc
        log.info("GitHub API 無法使用（%s），改從 Releases 網頁判斷最新版", exc)
    try:
        return _fetch_from_page(timeout, opener)
    except OSError as exc:
        log.warning("Releases 網頁也無法讀取：%s", exc)
        message = RATE_LIMIT_MESSAGE if _rate_limited(api_error) else OFFLINE_MESSAGE
        raise UpdateCheckError(message) from exc


def _fetch_from_page(timeout: float, opener: Opener) -> LatestRelease | None:
    """Releases 的「最新版」網址會轉到 …/releases/tag/vX.Y.Z（不受 API 每小時次數限制）。"""
    with opener(_request(RELEASES_PAGE, "text/html"), timeout=timeout) as response:
        final_url = response.geturl()
    match = _TAG_URL.match(final_url or "")
    version = parse_version(match.group(1) if match else None)
    if not version:
        return None
    text = ".".join(map(str, version))
    return LatestRelease(text, f"YT_Media_Tool-{text}-win64-setup.exe", None)


def _fetch_from_api(timeout: float, opener: Opener) -> LatestRelease | None:
    with opener(_request(LATEST_RELEASE_API, "application/vnd.github+json"), timeout=timeout) as response:
        data = json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8"))
    tag = data.get("tag_name") if isinstance(data, dict) else None
    version = parse_version(tag if isinstance(tag, str) else None)
    if not version:
        return None
    text = ".".join(map(str, version))
    setup_name = f"YT_Media_Tool-{text}-win64-setup.exe"
    digest = None
    for asset in data.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") == setup_name:
            value = str(asset.get("digest") or "")
            if value.startswith("sha256:") and _SHA256.match(value[7:]):
                digest = value[7:].lower()
    return LatestRelease(text, setup_name, digest)


def fetch_latest_version(timeout: float = 10.0, opener: Opener = urllib.request.urlopen) -> str | None:
    release = fetch_latest_release(timeout, opener)
    return release.version if release else None


def is_installed_build() -> bool:
    """是否為安裝版（安裝程式會在程式資料夾放 unins000.exe）；免安裝版與開發環境無法自動安裝。"""
    return paths.is_frozen() and (paths.executable_dir() / "unins000.exe").is_file()


def updates_dir() -> Path:
    return paths.app_data_dir() / "updates"


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(release: LatestRelease, dest_dir: Path | None = None,
                    on_progress: Callable[[float], None] | None = None,
                    cancel: threading.Event | None = None,
                    opener: Opener = urllib.request.urlopen, timeout: float = 30.0) -> Path:
    """下載安裝程式並驗證檢查碼，回傳安裝程式路徑。已下載且驗證過的檔案會直接沿用。"""
    dest_dir = Path(dest_dir or updates_dir())
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / release.setup_name

    try:
        with opener(_request(release.sha256_url), timeout=timeout) as response:
            published = response.read(4096).decode("utf-8", "replace").split()
    except OSError as exc:
        raise UpdateError(f"無法下載更新的檢查碼，請稍後再試（{exc}）") from exc
    expected = published[0].lower() if published and _SHA256.match(published[0]) else ""
    if not expected:
        raise UpdateError("更新的檢查碼格式不正確，已停止更新。")
    if release.setup_digest and release.setup_digest != expected:
        raise UpdateError("GitHub 上的檔案檢查碼與發布的檢查碼不一致，已停止更新。")

    # 清除舊的下載（其他版本或未完成的檔案）
    for old in dest_dir.iterdir():
        if old != target and old.is_file():
            old.unlink(missing_ok=True)
    if target.is_file() and _sha256_of(target) == expected:
        if on_progress:
            on_progress(100.0)
        return target
    target.unlink(missing_ok=True)

    part = dest_dir / f"{release.setup_name}.part"
    digest = hashlib.sha256()
    received = 0
    try:
        with opener(_request(release.setup_url), timeout=timeout) as response, part.open("wb") as fh:
            total = int(response.headers.get("Content-Length") or 0) if getattr(response, "headers", None) else 0
            while chunk := response.read(CHUNK):
                if cancel is not None and cancel.is_set():
                    raise UpdateCancelledError()
                received += len(chunk)
                if received > MAX_SETUP_BYTES:
                    raise UpdateError("下載的檔案大小異常，已停止更新。")
                digest.update(chunk)
                fh.write(chunk)
                if on_progress and total:
                    on_progress(min(99.0, received / total * 100))
        if digest.hexdigest() != expected:
            raise UpdateError("下載的安裝程式檢查碼不符（檔案可能不完整），請重試。")
        os.replace(part, target)
    except OSError as exc:
        raise UpdateError(f"下載更新失敗，請確認網路連線後重試（{exc}）") from exc
    finally:
        part.unlink(missing_ok=True)
    if on_progress:
        on_progress(100.0)
    return target


CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def install_log_path() -> Path:
    """自動更新時安裝程式的記錄檔（失敗時可請使用者提供）。"""
    return updates_dir() / "install.log"


_LOG_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\s+")


def _log_lines(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()[-256 * 1024:]
    except OSError:
        return []
    for encoding in ("utf-8", "cp950", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return [_LOG_PREFIX.sub("", line).strip() for line in text.splitlines()]


def summarize_install_log(path: Path | None = None) -> tuple[str, str]:
    """把安裝記錄檔整理成（給使用者看的原因, 最後幾行記錄供回報問題）。使用者不需要自己開記錄檔。"""
    path = path or install_log_path()
    lines = _log_lines(path)
    details = "\n".join(line for line in lines[-30:] if line)
    if not lines:
        return ("安裝程式沒有執行（找不到安裝記錄）。可能被防毒軟體或 Windows 安全性功能擋下，"
                "或下載的安裝程式已被刪除。", "")
    if any("Installation process succeeded" in line for line in lines):
        return "安裝程式回報已安裝完成，但程式版本沒有改變（可能安裝到了其他資料夾）。", details
    for i, line in enumerate(lines):
        if line.startswith("Message box") or line.startswith("Exception message:"):
            reason = next((nxt for nxt in lines[i + 1:i + 4] if nxt and not nxt.startswith("Defaulting")), "")
            if reason:
                return f"安裝程式顯示：{reason}", details
    if any("SetupAborted" in line or "aborted" in line.lower() or "cancel" in line.lower() for line in lines):
        return "安裝被取消或中斷了。", details
    return "安裝沒有完成（可能被中斷，或舊版程式沒有在時間內關閉）。", details


def launch_installer(setup: Path) -> Path:
    """以靜默模式執行安裝程式：等本程式結束後安裝，完成後重新開啟程式。呼叫後應立即關閉程式。

    回傳安裝記錄檔路徑。安裝程式必須在本程式結束後繼續執行，因此：
    1. 取消本程式 Job Object 的「結束時終止子程序」並允許脫離 Job；
    2. 以 CREATE_BREAKAWAY_FROM_JOB 啟動，讓安裝程式完全不在本程式的 Job 內（不被允許時改為一般啟動）；
    3. 釋放程式 mutex，避免安裝程式認為程式仍在執行而停止。
    """
    if not sys.platform.startswith("win"):
        raise UpdateError("自動安裝只支援 Windows。")
    log_file = install_log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.unlink(missing_ok=True)
    win_job.allow_children_to_outlive()
    win_job.release_app_mutex()
    args = [str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log_file}",
            f"/WAITPID={os.getpid()}", "/RESTARTAPP=1"]
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        # 參數清單，不經過 shell
        subprocess.Popen(args, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, close_fds=True)
    except OSError:
        # 本程式本身位於不允許脫離的外層 Job 時會被拒絕；此時已取消終止設定，一般啟動即可
        log.warning("無法以 CREATE_BREAKAWAY_FROM_JOB 啟動安裝程式，改為一般啟動", exc_info=True)
        subprocess.Popen(args, creationflags=flags, close_fds=True)
    log.info("已啟動更新安裝程式 %s（記錄檔 %s）", setup, log_file)
    return log_file
