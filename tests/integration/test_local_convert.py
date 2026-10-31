"""本機檔案轉 MP3：以真實 FFmpeg 驗證（不連線網路）。"""

from __future__ import annotations

import shutil
import subprocess
import threading

import pytest

from yt_media_tool.core import converter
from yt_media_tool.core.local_convert import (
    ConvertCancelledError, ConvertError, convert_to_mp3, is_media_file,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="需要 FFmpeg / FFprobe"),
]


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    root = tmp_path_factory.mktemp("local")
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", str(root / "我的影片.mp4")], check=True)
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "沒有聲音.mp4")], check=True)
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
                    "-c:a", "pcm_s16le", str(root / "長音訊.wav")], check=True)
    (root / "不是影片.mp4").write_bytes(b"not a video")
    return root


@pytest.fixture
def tools():
    return converter.find_ffmpeg()


def test_converts_audio_and_keeps_source(samples, tools, tmp_path):
    source = samples / "我的影片.mp4"
    before = source.read_bytes()
    progress = []
    result = convert_to_mp3(source, tmp_path, "192", tools, on_progress=progress.append)
    assert result.output == tmp_path / "我的影片.mp3"
    info = converter.probe_media(result.output, tools.ffprobe)
    assert info.has_audio and info.audio_codec == "mp3" and not info.has_video
    assert 150 < (info.audio_bitrate or 0) / 1000 < 230
    assert source.read_bytes() == before  # 來源檔不變
    assert progress and progress[-1] == 100.0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["我的影片.mp3"]  # 沒有殘留暫存檔


def test_existing_file_is_not_overwritten(samples, tools, tmp_path):
    (tmp_path / "我的影片.mp3").write_bytes(b"user file")
    result = convert_to_mp3(samples / "我的影片.mp4", tmp_path, "128", tools)
    assert result.output.name == "我的影片 (1).mp3"
    assert (tmp_path / "我的影片.mp3").read_bytes() == b"user file"


@pytest.mark.parametrize(("name", "message"), [("沒有聲音.mp4", "沒有聲音"), ("不是影片.mp4", "無法讀取")])
def test_invalid_sources_report_reason(samples, tools, tmp_path, name, message):
    with pytest.raises(ConvertError, match=message):
        convert_to_mp3(samples / name, tmp_path, "192", tools)
    assert list(tmp_path.iterdir()) == []


def test_cancel_removes_temp_file(samples, tools, tmp_path):
    cancel = threading.Event()

    def on_progress(pct):
        if pct > 0:
            cancel.set()

    with pytest.raises(ConvertCancelledError):
        convert_to_mp3(samples / "長音訊.wav", tmp_path, "320", tools, on_progress=on_progress, cancel=cancel)
    assert list(tmp_path.iterdir()) == []


def test_is_media_file():
    from pathlib import Path

    assert is_media_file(Path("a.MP4")) and is_media_file(Path("b.flac"))
    assert not is_media_file(Path("c.exe")) and not is_media_file(Path("d.txt"))
