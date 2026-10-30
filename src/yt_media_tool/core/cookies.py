"""YouTube 登入資訊（cookies）設定。

YouTube 對部分網路會要求「登入以確認不是機器人」，yt-dlp 官方建議的解法是使用者提供
自己帳號的 cookies。本模組只負責把設定轉成 yt-dlp 參數：

- 瀏覽器：交由 yt-dlp 直接讀取（cookiesfrombrowser）。
- cookies.txt：先複製到任務專屬的暫存資料夾再交給 yt-dlp。yt-dlp 結束時會把 cookies
  寫回檔案，使用副本可避免修改使用者的原始檔，也避免多個任務同時寫入同一檔案而損壞；
  副本會隨暫存資料夾一併刪除。

本程式不會另外保存、記錄或傳送 cookies 內容。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COOKIE_SOURCES: dict[str, str] = {
    "none": "不使用",
    "firefox": "Firefox",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "file": "cookies.txt 檔案",
}
BROWSER_SOURCES = ("firefox", "chrome", "edge")


class CookieFileError(RuntimeError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"找不到 cookies 檔案：{path or '（未指定）'}\n"
                         "請到「設定 → YouTube 登入資訊」重新指定檔案，或改為「不使用」。")


@dataclass(frozen=True)
class CookieConfig:
    source: str = "none"
    file: str = ""

    @property
    def enabled(self) -> bool:
        return self.source in BROWSER_SOURCES or self.source == "file"

    def describe(self) -> str:
        if self.source == "file":
            return f"cookies.txt（{self.file}）"
        return COOKIE_SOURCES.get(self.source, "不使用")


def ydl_cookie_options(config: CookieConfig, work_dir: Path) -> dict[str, Any]:
    """回傳要加入 yt-dlp 參數的 cookies 設定；work_dir 必須是任務專屬、結束後會刪除的資料夾。"""
    if config.source in BROWSER_SOURCES:
        return {"cookiesfrombrowser": (config.source,)}
    if config.source == "file":
        source = Path(config.file) if config.file else None
        if source is None or not source.is_file():
            raise CookieFileError(config.file)
        copy = work_dir / "cookies.txt"
        shutil.copyfile(source, copy)
        return {"cookiefile": str(copy)}
    return {}
