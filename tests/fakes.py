"""測試用的假下載器與假 yt-dlp，完全不連線網路。"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from yt_media_tool.core.downloader import (
    CancelToken, DownloadResult, PlaylistEntry, PlaylistInfo, ProgressUpdate,
)
from yt_media_tool.core.errors import DownloadCancelledError
from yt_media_tool.core.task_models import DownloadTask, TaskStatus


class FakeDownloader:
    """依網址決定行為：

    - 含 "fail"：拋出例外
    - 含 "block"：持續回報進度，直到被取消或 release(url) 後成功
    - 其他：立即成功，並在 output_dir 建立檔案
    """

    def __init__(self) -> None:
        self.started: list[str] = []
        self.release_events: dict[str, threading.Event] = {}
        self.fail_urls: set[str] = set()
        self.lock = threading.Lock()
        self.running = 0
        self.max_running = 0
        self.playlists: dict[str, PlaylistInfo] = {}

    def release(self, url: str) -> None:
        self.release_events.setdefault(url, threading.Event()).set()

    def download(self, task: DownloadTask, token: CancelToken, on_progress) -> DownloadResult:
        with self.lock:
            self.started.append(task.url)
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        try:
            on_progress(ProgressUpdate(TaskStatus.DOWNLOADING, progress=1.0, title=f"title-{task.url[-6:]}"))
            if "fail" in task.url or task.url in self.fail_urls:
                raise RuntimeError("ERROR: [youtube] abc: Private video")
            if "block" in task.url:
                event = self.release_events.setdefault(task.url, threading.Event())
                progress = 1.0
                while not event.is_set():
                    if token.cancelled:
                        raise DownloadCancelledError(token.reason)
                    progress = min(progress + 1, 90)
                    on_progress(ProgressUpdate(TaskStatus.DOWNLOADING, progress=progress, speed=1024.0, eta=5))
                    time.sleep(0.01)
            on_progress(ProgressUpdate(TaskStatus.PROCESSING, progress=95, stage="影音合併中"))
            out = Path(task.output_dir) / f"video-{task.id}.{task.media_format.value}"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"data")
            return DownloadResult(out, f"title-{task.url[-6:]}", "720p")
        finally:
            with self.lock:
                self.running -= 1

    def extract_playlist(self, url: str, limit: int = 500) -> PlaylistInfo:
        return self.playlists.get(url, PlaylistInfo("清單", [PlaylistEntry(
            f"https://www.youtube.com/watch?v=vid{i:08d}", f"影片 {i}") for i in range(3)]))


class FakeYDL:
    """模擬 yt_dlp.YoutubeDL 的最小介面，用於測試 Downloader 的檔案處理邏輯。"""

    def __init__(self, params: dict, info: dict, on_download=None) -> None:
        self.params = params
        self.info = info
        self.on_download = on_download  # callable(self)：在下載進行中插入自訂行為

    def __enter__(self) -> FakeYDL:
        return self

    def __exit__(self, *exc) -> None:
        return None

    @classmethod
    def factory(cls, info: dict, on_download=None):
        return lambda params: cls(params, info, on_download)

    def extract_info(self, url: str, download: bool = False) -> dict:
        return dict(self.info)

    def process_ie_result(self, info: dict, download: bool = True) -> dict:
        home = Path(self.params["paths"]["home"])
        ext = "mp3" if any(p["key"] == "FFmpegExtractAudio" for p in self.params["postprocessors"]) else "mp4"
        part = home / "media.f137.mp4.part"
        part.write_bytes(b"partial")
        for hook in self.params["progress_hooks"]:
            for done in (100, 500, 1000):
                hook({"status": "downloading", "downloaded_bytes": done, "total_bytes": 1000,
                      "speed": 2048.0, "eta": 3, "info_dict": {"format_id": "137"}})
        if self.on_download:
            self.on_download(self)
        for hook in self.params["postprocessor_hooks"]:
            hook({"status": "started", "postprocessor": "Merger" if ext == "mp4" else "ExtractAudio",
                  "info_dict": {}})
        part.unlink()
        final = home / f"media.{ext}"
        final.write_bytes(b"final media")
        for hook in self.params["postprocessor_hooks"]:
            hook({"status": "finished", "postprocessor": "Merger", "info_dict": {}})
        return {**info, "requested_downloads": [{"filepath": str(final)}]}
