"""已下載過的影片：依歷史紀錄判斷某部影片（同格式）是否已經下載、檔案是否還在。

用於「已下載過提醒」與播放清單同步（再次加入同一個播放清單時，只預先勾選還沒下載的歌）。
檔案已被使用者刪除或移走時不算已下載；只下載片段的紀錄不算下載過整部影片。
"""

from __future__ import annotations

from pathlib import Path

from yt_media_tool.core.task_models import MediaFormat
from yt_media_tool.core.url_parser import parse_urls


def video_key(url: str) -> str:
    """同一部影片的不同網址寫法（youtu.be、Shorts、帶時間參數）視為相同。"""
    parsed = parse_urls(url).valid
    return parsed[0].video_id or url if parsed else url


class DownloadedIndex:
    def __init__(self, rows: list[dict]) -> None:
        """rows：Database.completed_downloads() 的結果（新 → 舊）。同一部影片取最新且檔案仍存在的那一筆。"""
        self._files: dict[tuple[str, str], Path] = {}
        for row in rows:
            key = (video_key(str(row.get("url") or "")), str(row.get("media_format") or ""))
            if key in self._files:
                continue
            path = Path(str(row.get("output_path") or ""))
            try:
                if row.get("output_path") and path.is_file():
                    self._files[key] = path
            except OSError:  # 例如網路磁碟已中斷
                continue

    def find(self, url: str, media_format: MediaFormat) -> Path | None:
        return self._files.get((video_key(url), MediaFormat(media_format).value))

    def __len__(self) -> int:
        return len(self._files)
