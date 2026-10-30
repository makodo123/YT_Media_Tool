import errno
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

from yt_media_tool.core import converter
from yt_media_tool.core.converter import FFmpegNotFoundError, find_ffmpeg, format_selector, postprocessors
from yt_media_tool.core.errors import DownloadCancelledError, InsufficientDiskSpaceError, explain_error
from yt_media_tool.core.task_models import MediaFormat

EXE = ".exe" if os.name == "nt" else ""


def make_fake_tools(directory: Path, names=("ffmpeg", "ffprobe")) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        exe = directory / f"{name}{EXE}"
        exe.write_text("#!/bin/sh\necho 'ffmpeg version 7.1-test Copyright'\n")
        exe.chmod(0o755)


def test_custom_dir_takes_priority(tmp_path):
    make_fake_tools(tmp_path / "custom")
    info = find_ffmpeg(tmp_path / "custom")
    assert info.available and info.source == "設定指定"
    assert info.location == str(tmp_path / "custom")


def test_bundled_dir_found_without_path(tmp_path, monkeypatch):
    make_fake_tools(tmp_path / "bundle" / "ffmpeg")
    monkeypatch.setattr(converter.paths, "bundle_dir", lambda: tmp_path / "bundle")
    monkeypatch.setattr(converter.paths, "executable_dir", lambda: tmp_path / "bundle")
    monkeypatch.setenv("PATH", "")
    info = find_ffmpeg()
    assert info.available and info.source == "隨附"


def test_missing_ffmpeg_detected_with_guide(tmp_path, monkeypatch):
    monkeypatch.setattr(converter.paths, "bundle_dir", lambda: tmp_path / "empty")
    monkeypatch.setattr(converter.paths, "executable_dir", lambda: tmp_path / "empty")
    monkeypatch.delenv("YTMT_FFMPEG_DIR", raising=False)
    monkeypatch.setenv("PATH", "")
    info = find_ffmpeg()
    assert not info.available
    assert info.missing == ["ffmpeg", "ffprobe"]
    with pytest.raises(FFmpegNotFoundError) as exc:
        info.require()
    assert "安裝" in str(exc.value) or "下載" in str(exc.value)
    assert "FFmpeg" in explain_error(exc.value)


def test_only_ffprobe_missing_is_reported(tmp_path, monkeypatch):
    make_fake_tools(tmp_path / "half", names=("ffmpeg",))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(converter.paths, "bundle_dir", lambda: tmp_path / "empty")
    monkeypatch.setattr(converter.paths, "executable_dir", lambda: tmp_path / "empty")
    info = find_ffmpeg(tmp_path / "half")
    assert not info.available


def test_format_selectors():
    assert format_selector(MediaFormat.MP3, "320") == "bestaudio/best"
    sel = format_selector(MediaFormat.MP4, "720")
    assert "height<=720" in sel and "avc1" in sel and sel.endswith("/bv*+ba/b")
    assert "height" not in format_selector(MediaFormat.MP4, "best")
    assert postprocessors(MediaFormat.MP3, "192") == [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    assert postprocessors(MediaFormat.MP4, "best")[0]["key"] == "FFmpegVideoRemuxer"


def test_js_runtime_option():
    info = converter.JsRuntimeInfo("deno", Path("/x/deno"))
    assert info.ydl_option() == {"js_runtimes": {"deno": {"path": str(Path("/x/deno"))}}}
    assert converter.JsRuntimeInfo().ydl_option() == {}


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="需要 FFmpeg")
def test_probe_and_verify_real_media(tmp_path):
    media = tmp_path / "tone.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "sine=duration=1",
                    "-b:a", "128k", str(media)], check=True)
    ffprobe = Path(shutil.which("ffprobe"))
    info = converter.verify_output(media, MediaFormat.MP3, ffprobe)
    assert info.has_audio and not info.has_video
    with pytest.raises(converter.MediaProbeError):
        converter.verify_output(media, MediaFormat.MP4, ffprobe)
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    with pytest.raises(converter.MediaProbeError):
        converter.verify_output(broken, MediaFormat.MP4, ffprobe)


# ---- 錯誤訊息 ----
def winerror(code: int) -> OSError:
    exc = OSError(f"winerror {code}")
    exc.winerror = code
    return exc


@pytest.mark.parametrize("exc,expected", [
    (OSError(errno.ENOSPC, "No space left on device"), "磁碟空間不足"),
    (winerror(112), "磁碟空間不足"),
    (PermissionError(errno.EACCES, "denied", "C:/Program Files/x.mp4"), "沒有寫入權限"),
    (winerror(5), "沒有寫入權限"),
    (winerror(206), "路徑過長"),
    (InsufficientDiskSpaceError(500 * 1024 * 1024, 10 * 1024 * 1024, "D:/"), "預估需要 500 MB"),
    (DownloadError("ERROR: [youtube] x: Private video. Sign in if you've been granted access"), "私人影片"),
    (DownloadError("ERROR: [youtube] x: This video is DRM protected"), "DRM"),
    (DownloadError("ERROR: Sign in to confirm your age"), "年齡限制"),
    (DownloadError("ERROR: unable to download video data: HTTP Error 403: Forbidden"), "HTTP 403"),
    (DownloadError("ERROR: HTTP Error 429: Too Many Requests"), "請求次數過多"),
    (DownloadError("ERROR: [youtube] x: Video unavailable"), "無法觀看"),
    (DownloadError("ERROR: Unable to download webpage: <urlopen error [Errno -2] Name or service not known>"),
     "網路連線失敗"),
    (DownloadError("ERROR: Postprocessing: Conversion failed!"), "FFmpeg 處理失敗"),
    (DownloadCancelledError("user"), "已取消"),
    (RuntimeError("something odd"), "下載失敗：something odd"),
])
def test_explain_error(exc, expected):
    assert expected in explain_error(exc)


def test_explain_error_unwraps_ytdlp_exc_info():
    inner = OSError(errno.ENOSPC, "No space left on device")
    wrapped = DownloadError("ERROR: unable to write data", exc_info=(type(inner), inner, None))
    assert "磁碟空間不足" in explain_error(wrapped)
