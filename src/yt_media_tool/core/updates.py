"""檢查、下載並安裝 GitHub 上的新正式版本。

- 只向 GitHub API 讀取最新正式版的版本號與檔案檢查碼（不含測試版），不傳送任何個人資料。
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
DOWNLOAD_BASE = f"https://github.com/{REPO}/releases/download"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_SETUP_BYTES = 1024 * 1024 * 1024  # 安裝程式大小上限（防止異常回應塞滿磁碟）
CHUNK = 256 * 1024

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
Opener = Callable[..., Any]


class UpdateError(Exception):
    """下載或驗證更新失敗；訊息為顯示給使用者的中文說明。"""


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


def fetch_latest_release(timeout: float = 10.0, opener: Opener = urllib.request.urlopen) -> LatestRelease | None:
    """讀取最新正式版；網路錯誤由呼叫端處理，回應格式不符時回傳 None。"""
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


def launch_installer(setup: Path) -> None:
    """以靜默模式執行安裝程式：等本程式結束後安裝，完成後重新開啟程式。呼叫後應立即關閉程式。"""
    if not sys.platform.startswith("win"):
        raise UpdateError("自動安裝只支援 Windows。")
    win_job.allow_children_to_outlive()  # 否則安裝程式會在本程式結束時被一併終止
    win_job.release_app_mutex()  # 否則安裝程式會認為程式仍在執行而停止
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(  # 參數清單，不經過 shell
        [str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/WAITPID={os.getpid()}", "/RESTARTAPP=1"],
        creationflags=flags, close_fds=True,
    )
    log.info("已啟動更新安裝程式 %s", setup)
