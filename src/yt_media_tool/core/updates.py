"""檢查 GitHub 上是否有新的正式版本。

只向 GitHub API 讀取最新正式版的版本號（不含測試版），不傳送任何個人資料。
下載頁面使用固定網址，不採用 API 回傳的連結。
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from typing import Any

from yt_media_tool import __version__

REPO = "makodo123/YT_Media_Tool"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
MAX_RESPONSE_BYTES = 1024 * 1024

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    """解析「v2.4.0」或「2.4.0」；含測試版後綴（例如 -beta.1）或格式不符時回傳 None。"""
    match = _VERSION.match((text or "").strip())
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def is_newer(latest: str, current: str = __version__) -> bool:
    latest_v, current_v = parse_version(latest), parse_version(current)
    return bool(latest_v and current_v and latest_v > current_v)


def fetch_latest_version(timeout: float = 10.0,
                         opener: Callable[..., Any] = urllib.request.urlopen) -> str | None:
    """回傳最新正式版的版本號（例如「2.4.0」）；網路錯誤由呼叫端處理，回應格式不符時回傳 None。"""
    request = urllib.request.Request(LATEST_RELEASE_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"YT-Media-Tool/{__version__}",
    })
    with opener(request, timeout=timeout) as response:
        data = json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8"))
    tag = data.get("tag_name") if isinstance(data, dict) else None
    version = parse_version(tag if isinstance(tag, str) else None)
    return ".".join(map(str, version)) if version else None
