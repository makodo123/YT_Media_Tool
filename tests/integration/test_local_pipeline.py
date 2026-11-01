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
from yt_media_tool.core.downloader import TEMP_ROOT_NAME, CancelToken, DownloadPreferences, Downloader
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

    # 影片縮圖（YouTube 多為 WebP；本機 FFmpeg 不一定有 WebP 編碼器，改用 PNG 一樣需經過轉檔）
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=red:size=320x180", "-frames:v", "1",
                    str(root / "thumb.png")], check=True)

    (root / "sub.vtt").write_text("WEBVTT\n\n00:00:00.500 --> 00:00:02.000\n測試字幕\n", encoding="utf-8")

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
    details = [(t.status.value, t.error_message) for t in queue.tasks()]
    assert statuses == [TaskStatus.COMPLETED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.COMPLETED], details
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["sample (1).mp4", "sample.mp3", "sample.mp4"]
    assert "404" in queue.tasks()[2].error_message
    queue.shutdown(5)


def _probe_json(path):
    import json

    ffprobe = str(converter.find_ffmpeg().ffprobe)
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize(("fmt", "quality"), [(MediaFormat.MP3, "192"), (MediaFormat.MP4, "720")])
def test_embed_title_artist_and_cover(media_server, tmp_path, fmt, quality):
    """寫入歌名、演出者並以縮圖作為封面；暫存的縮圖不得殘留在下載資料夾。"""
    import yt_dlp

    base = media_server["fast"]

    class WithThumbnail(yt_dlp.YoutubeDL):
        def extract_info(self, url, *args, **kwargs):
            info = super().extract_info(url, *args, **kwargs)
            info.update({"title": "晴天", "uploader": "周杰倫",
                         "thumbnails": [{"url": f"{base}/thumb.png", "id": "0"}]})
            return info

    tools = converter.find_ffmpeg()
    downloader = Downloader(tools_provider=lambda: tools, js_runtime_provider=converter.JsRuntimeInfo,
                            extra_options={"proxy": ""}, ydl_factory=WithThumbnail,
                            preferences_provider=lambda: DownloadPreferences(embed_metadata=True))
    stages = []
    result = downloader.download(task(f"{base}/sample.mp4", tmp_path, fmt, quality), CancelToken(),
                                 lambda u: stages.append(u.stage))
    data = _probe_json(result.output_path)
    tags = {k.lower(): v for k, v in data["format"].get("tags", {}).items()}
    assert tags.get("title") == "晴天" and tags.get("artist") == "周杰倫"
    covers = [s for s in data["streams"] if s.get("disposition", {}).get("attached_pic")]
    assert covers and covers[0]["codec_name"] == "mjpeg"
    assert result.media_info.has_audio and result.media_info.has_video is (fmt is MediaFormat.MP4)
    assert "嵌入封面中" in stages
    assert sorted(p.name for p in tmp_path.iterdir()) == [result.output_path.name]


def _downloader_with_info(base, extra: dict, prefs):
    import yt_dlp

    class Injected(yt_dlp.YoutubeDL):
        def extract_info(self, url, *args, **kwargs):
            info = super().extract_info(url, *args, **kwargs)
            info.update(extra)
            return info

    tools = converter.find_ffmpeg()
    return Downloader(tools_provider=lambda: tools, js_runtime_provider=converter.JsRuntimeInfo,
                      extra_options={"proxy": ""}, ydl_factory=Injected, preferences_provider=lambda: prefs)


def test_subtitle_saved_next_to_video_as_srt(media_server, tmp_path):
    base = media_server["fast"]
    subs = {"title": "有字幕的影片", "subtitles": {"en": [{"url": f"{base}/sub.vtt", "ext": "vtt"}],
                                                   "zh-TW": [{"url": f"{base}/sub.vtt", "ext": "vtt"}]}}
    downloader = _downloader_with_info(base, subs, DownloadPreferences(subtitles=True))
    (tmp_path / "有字幕的影片.srt").write_text("使用者既有的字幕", encoding="utf-8")  # 同名檔不可被覆蓋
    stages = []
    result = downloader.download(task(f"{base}/sample.mp4", tmp_path), CancelToken(), lambda u: stages.append(u.stage))
    assert result.output_path.name == "有字幕的影片.mp4"
    assert (tmp_path / "有字幕的影片.srt").read_text(encoding="utf-8") == "使用者既有的字幕"
    srt = (tmp_path / "有字幕的影片.zh-TW.srt").read_text(encoding="utf-8")
    assert "00:00:00,500 --> 00:00:02,000" in srt and "測試字幕" in srt  # 已轉成 SRT，且選了繁體中文
    assert result.actual_quality.endswith("；字幕：繁體中文")
    assert "下載字幕中" in stages
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["有字幕的影片.mp4", "有字幕的影片.srt", "有字幕的影片.zh-TW.srt"]


def test_subtitle_failure_does_not_fail_video(media_server, tmp_path):
    base = media_server["fast"]
    extra = {"title": "字幕壞掉", "subtitles": {"zh-TW": [{"url": f"{base}/missing.vtt", "ext": "vtt"}]}}
    result = _downloader_with_info(base, extra, DownloadPreferences(subtitles=True)).download(
        task(f"{base}/sample.mp4", tmp_path), CancelToken(), lambda u: None)
    assert result.output_path.is_file() and result.actual_quality.endswith("；字幕下載失敗（影片不受影響）")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["字幕壞掉.mp4"]


def test_no_subtitles_available_is_noted(media_server, tmp_path):
    base = media_server["fast"]
    result = _downloader_with_info(base, {"title": "沒字幕"}, DownloadPreferences(subtitles=True)).download(
        task(f"{base}/sample.mp4", tmp_path), CancelToken(), lambda u: None)
    assert result.actual_quality.endswith("；此影片沒有可用字幕")


def test_clean_title_used_for_mp3_filename_and_tags(media_server, tmp_path):
    base = media_server["fast"]
    extra = {"title": "周杰倫 Jay Chou【晴天 Sunny Day】Official MV", "uploader": "周杰倫 Jay Chou",
             "channel": "周杰倫 Jay Chou"}
    prefs = DownloadPreferences(embed_metadata=True, clean_titles=True)
    result = _downloader_with_info(base, extra, prefs).download(
        task(f"{base}/sample.mp4", tmp_path, MediaFormat.MP3, "192"), CancelToken(), lambda u: None)
    assert result.output_path.name == "周杰倫 - 晴天.mp3"
    assert result.title == "周杰倫 Jay Chou【晴天 Sunny Day】Official MV"  # 佇列仍顯示原標題
    tags = {k.lower(): v for k, v in _probe_json(result.output_path)["format"].get("tags", {}).items()}
    assert tags.get("title") == "晴天" and tags.get("artist") == "周杰倫"

    # 關閉時維持原標題
    off = _downloader_with_info(base, extra, DownloadPreferences(clean_titles=False)).download(
        task(f"{base}/sample.mp4", tmp_path, MediaFormat.MP3, "192", task_id=2), CancelToken(), lambda u: None)
    assert off.output_path.name.startswith("周杰倫 Jay Chou【晴天 Sunny Day】Official MV")
    # MP4：標題中找得到演出者時整理；只能用頻道名稱時（vlog 等）維持原標題
    mp4 = _downloader_with_info(base, extra, prefs).download(
        task(f"{base}/sample.mp4", tmp_path, MediaFormat.MP4, "720", task_id=3), CancelToken(), lambda u: None)
    assert mp4.output_path.name == "周杰倫 - 晴天.mp4"
    vlog = {"title": "我的日常 vlog", "uploader": "某某頻道", "channel": "某某頻道"}
    kept = _downloader_with_info(base, vlog, prefs).download(
        task(f"{base}/sample.mp4", tmp_path, MediaFormat.MP4, "720", task_id=4), CancelToken(), lambda u: None)
    assert kept.output_path.name == "我的日常 vlog.mp4"
