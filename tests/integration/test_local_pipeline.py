"""使用真實 yt-dlp 與 FFmpeg 的整合測試。

媒體檔由本機 HTTP 伺服器提供（yt-dlp generic extractor），不連線 YouTube 或其他外部網站。
"""

from __future__ import annotations

import functools
import http.server
import shutil
import subprocess
import threading
import time

import pytest

from yt_media_tool.core import converter
from yt_media_tool.core.downloader import TEMP_ROOT_NAME, CancelToken, Downloader
from yt_media_tool.core.errors import DownloadCancelledError
from yt_media_tool.core.queue_manager import QueueManager, TaskSpec
from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="需要 FFmpeg / FFprobe"),
]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    delay = 0.0

    def log_message(self, *args):  # 不輸出存取紀錄
        pass

    def copyfile(self, source, outputfile):
        try:
            while chunk := source.read(16 * 1024):
                outputfile.write(chunk)
                if self.delay:
                    time.sleep(self.delay)
        except (BrokenPipeError, ConnectionResetError):
            pass


@pytest.fixture(scope="module")
def media_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("srv")
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", str(root / "sample.mp4")], check=True)
    # 較大的檔案供取消測試使用
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=20:size=1280x720:rate=30",
                    "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "4M", "-pix_fmt", "yuv420p",
                    str(root / "large.mp4")], check=True)

    slow = type("SlowHandler", (_QuietHandler,), {"delay": 0.02})
    servers = []
    for handler in (_QuietHandler, slow):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(root)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
    fast, slow_server = (f"http://127.0.0.1:{s.server_address[1]}" for s in servers)
    yield {"fast": fast, "slow": slow_server}
    for server in servers:
        server.shutdown()


@pytest.fixture
def real_downloader():
    tools = converter.find_ffmpeg()
    # proxy="" 讓 yt-dlp 直接連線本機伺服器，不經過環境中的代理伺服器
    return Downloader(tools_provider=lambda: tools, js_runtime_provider=converter.JsRuntimeInfo,
                      extra_options={"proxy": ""})


def task(url, out, fmt=MediaFormat.MP4, quality="720", task_id=1):
    return DownloadTask(url=url, media_format=fmt, quality=quality, output_dir=str(out), id=task_id)


def test_mp4_download_with_real_ytdlp(media_server, real_downloader, tmp_path):
    (tmp_path / "sample.mp4").write_bytes(b"user's existing file")
    (tmp_path / "media.mp4").write_bytes(b"user's other file")
    updates = []
    result = real_downloader.download(task(f"{media_server['fast']}/sample.mp4", tmp_path), CancelToken(),
                                      updates.append)
    assert result.output_path.name == "sample (1).mp4"
    assert (tmp_path / "sample.mp4").read_bytes() == b"user's existing file"
    assert (tmp_path / "media.mp4").read_bytes() == b"user's other file"
    assert result.media_info.has_video and result.media_info.has_audio
    assert result.actual_quality.startswith("360p") and "原始素材無 720p" in result.actual_quality
    assert not (tmp_path / TEMP_ROOT_NAME).exists()
    assert any(u.status is TaskStatus.PROCESSING for u in updates)


def test_mp3_conversion_with_real_ffmpeg(media_server, real_downloader, tmp_path):
    result = real_downloader.download(task(f"{media_server['fast']}/sample.mp4", tmp_path, MediaFormat.MP3, "192"),
                                      CancelToken(), lambda u: None)
    assert result.output_path.suffix == ".mp3"
    info = converter.probe_media(result.output_path, converter.find_ffmpeg().ffprobe)
    assert info.has_audio and info.audio_codec == "mp3" and not info.has_video
    assert "原始音源約" in result.actual_quality
    assert sorted(p.name for p in tmp_path.iterdir()) == ["sample.mp3"]


def test_real_cancellation_cleans_temp(media_server, real_downloader, tmp_path):
    token = CancelToken()
    started = threading.Event()

    def on_progress(update):
        if update.progress and update.progress > 1:
            started.set()

    def cancel_later():
        started.wait(20)
        token.cancel("user")

    threading.Thread(target=cancel_later, daemon=True).start()
    with pytest.raises(DownloadCancelledError):
        real_downloader.download(task(f"{media_server['slow']}/large.mp4", tmp_path), token, on_progress)
    assert started.is_set()
    assert list(tmp_path.iterdir()) == []


def test_unreachable_url_fails_with_message(real_downloader, tmp_path):
    from yt_media_tool.core.errors import explain_error

    with pytest.raises(Exception) as info:
        real_downloader.download(task("http://127.0.0.1:9/nothing.mp4", tmp_path), CancelToken(), lambda u: None)
    assert "網路" in explain_error(info.value) or "下載失敗" in explain_error(info.value)
    assert not (tmp_path / TEMP_ROOT_NAME).exists()


def test_queue_with_real_engine(media_server, real_downloader, db, tmp_path):
    tmp_path = tmp_path / "out"
    queue = QueueManager(db, real_downloader, max_concurrent=2)
    base = media_server["fast"]
    queue.add_tasks([
        TaskSpec(f"{base}/sample.mp4", MediaFormat.MP4, "best", str(tmp_path)),
        TaskSpec(f"{base}/sample.mp4", MediaFormat.MP3, "128", str(tmp_path)),
        TaskSpec(f"{base}/missing.mp4", MediaFormat.MP4, "720", str(tmp_path)),
        TaskSpec(f"{base}/sample.mp4", MediaFormat.MP4, "1080", str(tmp_path)),
    ])
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and (queue.has_active_tasks() or queue.pending_count()):
        time.sleep(0.1)
    statuses = [t.status for t in queue.tasks()]
    assert statuses == [TaskStatus.COMPLETED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.COMPLETED]
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["sample (1).mp4", "sample.mp3", "sample.mp4"]
    assert "404" in queue.tasks()[2].error_message
    queue.shutdown(5)
