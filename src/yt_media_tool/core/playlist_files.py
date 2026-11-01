"""播放清單檔（.m3u8）：從播放清單加入的影片下載完成後，在存放資料夾產生依原順序排列的清單檔。

- 每次從播放清單加入 2 部以上影片時記錄一個「批次」（資料夾、清單名稱、格式、影片順序），
  存在資料庫的 application_settings，程式重開後仍會繼續更新。
- 每完成一部就重寫清單檔，只列出已下載且檔案仍存在的影片（失敗的影片重試成功後也會補上）。
- 清單檔使用 UTF-8（.m3u8）與相對路徑，整個資料夾搬到別處或複製到手機仍可使用。
- 第一次建立時若同名檔案已存在，改用「清單名稱 (1).m3u8」，不覆蓋使用者的檔案；之後只更新本程式建立的那個檔案。
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from yt_media_tool.core.task_models import DownloadTask, TaskStatus
from yt_media_tool.storage.database import Database
from yt_media_tool.utils.paths import sanitize_filename

log = logging.getLogger(__name__)

SETTING_KEY = "playlist_files.batches"
MAX_BATCHES = 50  # 只保留最近的批次，避免設定無限增長


def _same_folder(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


class PlaylistFileStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def _load(self) -> list[dict[str, Any]]:
        batches = self._db.get_setting(SETTING_KEY, [])
        return [b for b in batches if isinstance(b, dict)] if isinstance(batches, list) else []

    def _save(self, batches: list[dict[str, Any]]) -> None:
        self._db.set_setting(SETTING_KEY, batches[-MAX_BATCHES:])

    def add_batch(self, folder: str, title: str, media_format: str, urls: list[str]) -> bool:
        """記錄一個播放清單批次；少於 2 部影片時不需要清單檔。"""
        urls = list(dict.fromkeys(urls))
        if len(urls) < 2:
            return False
        batches = self._load()
        batches.append({"id": uuid.uuid4().hex, "folder": folder, "title": title or "播放清單",
                        "format": media_format, "urls": urls, "files": {}, "m3u": ""})
        self._save(batches)
        return True

    def on_task_completed(self, task: DownloadTask) -> list[Path]:
        """任務完成時更新相關的清單檔，回傳寫入的清單檔路徑。"""
        if task.status is not TaskStatus.COMPLETED or not task.output_path:
            return []
        batches = self._load()
        written = []
        for batch in batches:
            if (batch.get("format") == task.media_format.value and task.url in batch.get("urls", [])
                    and _same_folder(batch.get("folder", ""), task.output_dir)):
                batch.setdefault("files", {})[task.url] = Path(task.output_path).name
                path = self._write(batch)
                if path is not None:
                    written.append(path)
        if written:
            self._save(batches)
        return written

    def rename_file(self, folder: str, old_name: str, new_name: str) -> None:
        """批次整理改名後更新記錄的檔名，之後重寫清單檔時才不會漏掉這首。"""
        batches = self._load()
        changed = False
        for batch in batches:
            if _same_folder(batch.get("folder", ""), folder):
                files = batch.get("files", {})
                for url, name in files.items():
                    if name == old_name:
                        files[url], changed = new_name, True
        if changed:
            self._save(batches)

    def _write(self, batch: dict[str, Any]) -> Path | None:
        folder = Path(batch["folder"])
        files = batch.get("files", {})
        entries = [files[url] for url in batch["urls"] if url in files and (folder / files[url]).is_file()]
        if not entries:
            return None
        if batch.get("m3u"):
            target = folder / batch["m3u"]
        else:
            target = _unused_name(folder, sanitize_filename(batch["title"]) or "播放清單")
            batch["m3u"] = target.name
        lines = ["#EXTM3U"]
        for name in entries:
            lines += [f"#EXTINF:-1,{Path(name).stem}", name]
        temp = folder / f".ytmt_m3u_{uuid.uuid4().hex[:8]}.tmp"
        try:
            temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.replace(temp, target)  # 只會取代本程式先前建立的清單檔
        except OSError:
            log.warning("無法寫入播放清單檔 %s", target, exc_info=True)
            temp.unlink(missing_ok=True)
            return None
        return target


def _unused_name(folder: Path, stem: str) -> Path:
    counter = 0
    while True:
        candidate = folder / (f"{stem} ({counter}).m3u8" if counter else f"{stem}.m3u8")
        if not candidate.exists():
            return candidate
        counter += 1
