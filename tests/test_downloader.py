"""Downloader 的檔案安全行為測試（以假 yt-dlp 取代網路）。"""

from collections import namedtuple
from pathlib import Path

import pytest

from tests.fakes import FakeYDL
from yt_media_tool.core import downloader as downloader_mod
from yt_media_tool.core.converter import FFmpegNotFoundError, JsRuntimeInfo, MediaInfo, ToolInfo
from yt_media_tool.core.downloader import (
    TEMP_ROOT_NAME, CancelToken, Downloader, describe_selection, move_no_overwrite,
)
from yt_media_tool.core.errors import DownloadCancelledError, InsufficientDiskSpaceError, MediaProbeError
from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus

TOOLS = ToolInfo(ffmpeg=Path("/fake/ffmpeg"), ffprobe=Path("/fake/ffprobe"), source="test")
INFO = {
    "id": "dQw4w9WgXcQ", "title": "測試: 影片/標題?", "duration": 10,
    "formats": [{"format_id": "22", "height": 720, "vcodec": "avc1"}, {"format_id": "18", "height": 360,
                                                                      "vcodec": "avc1"}],
    "requested_formats": [{"format_id": "137", "height": 720, "filesize": 1000},
                          {"format_id": "140", "abr": 129.5, "filesize": 500}],
}


def fake_probe(path, fmt, ffprobe):
    assert Path(path).is_file()
    return MediaInfo(duration=10, has_video=fmt is MediaFormat.MP4, has_audio=True, height=720,
                     video_codec="h264", audio_codec="aac")


def make_downloader(info=INFO, on_download=None, probe=fake_probe, tools=TOOLS):
    return Downloader(tools_provider=lambda: tools, js_runtime_provider=lambda: JsRuntimeInfo(),
                      ydl_factory=FakeYDL.factory(info, on_download), probe=probe)


def make_task(out: Path, fmt=MediaFormat.MP4, quality="1080", task_id=7):
    return DownloadTask(url="https://youtu.be/dQw4w9WgXcQ", media_format=fmt, quality=quality,
                        output_dir=str(out), id=task_id)


def test_successful_download_reports_stages_and_cleans_temp(tmp_path):
    updates = []
    result = make_downloader().download(make_task(tmp_path), CancelToken(), updates.append)
    assert result.output_path == tmp_path / "測試_ 影片_標題_.mp4"
    assert result.output_path.read_bytes() == b"final media"
    assert not (tmp_path / TEMP_ROOT_NAME).exists()
    stages = [u.stage for u in updates]
    assert "影音合併中" in stages and "檢查輸出檔案中" in stages
    assert any(u.status is TaskStatus.PROCESSING for u in updates)
    assert updates[1].title == "測試: 影片/標題?"
    # 目標 1080p 但原始素材只有 720p：必須明確標示實際品質
    assert result.actual_quality.startswith("720p")
    assert "原始素材無 1080p" in result.actual_quality
    progress = [u.progress for u in updates if u.status is TaskStatus.DOWNLOADING and u.progress]
    assert progress == sorted(progress)


def test_mp3_reports_source_bitrate(tmp_path):
    result = make_downloader().download(make_task(tmp_path, MediaFormat.MP3, "320"), CancelToken(), lambda u: None)
    assert result.output_path.suffix == ".mp3"
    assert "原始音源約 130 kbps" in result.actual_quality
    assert "實際音質不會提升" in result.actual_quality


def test_same_name_files_are_not_overwritten(tmp_path):
    existing = tmp_path / "測試_ 影片_標題_.mp4"
    existing.write_bytes(b"user's own file")
    # 與 yt-dlp 中繼檔名相同的使用者檔案也不得被讀取或刪除
    (tmp_path / "media.mp4").write_bytes(b"user media")
    result = make_downloader().download(make_task(tmp_path), CancelToken(), lambda u: None)
    assert result.output_path.name == "測試_ 影片_標題_ (1).mp4"
    assert existing.read_bytes() == b"user's own file"
    assert (tmp_path / "media.mp4").read_bytes() == b"user media"


def test_cancel_during_download_removes_only_own_temp(tmp_path):
    other_temp = tmp_path / TEMP_ROOT_NAME / "task_99_deadbeef"
    other_temp.mkdir(parents=True)
    (other_temp / "media.mp4.part").write_bytes(b"other task")
    user_file = tmp_path / "keep.mp4"
    user_file.write_bytes(b"keep")
    token = CancelToken()
    seen_temp = []

    def cancel_midway(ydl):
        seen_temp.append(Path(ydl.params["paths"]["home"]))
        token.cancel("user")
        for hook in ydl.params["progress_hooks"]:
            hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 10})

    with pytest.raises(DownloadCancelledError) as info:
        make_downloader(on_download=cancel_midway).download(make_task(tmp_path), token, lambda u: None)
    assert info.value.reason == "user"
    assert not seen_temp[0].exists()  # 本任務暫存資料夾已刪除
    assert (other_temp / "media.mp4.part").read_bytes() == b"other task"  # 其他任務不受影響
    assert user_file.read_bytes() == b"keep"
    assert sorted(p.name for p in tmp_path.iterdir()) == [TEMP_ROOT_NAME, "keep.mp4"]


def test_cancel_during_postprocessing(tmp_path):
    token = CancelToken()

    def cancel_before_pp(ydl):
        token.cancel("shutdown")

    with pytest.raises(DownloadCancelledError) as info:
        make_downloader(on_download=cancel_before_pp).download(make_task(tmp_path), token, lambda u: None)
    assert info.value.reason == "shutdown"
    assert list(tmp_path.iterdir()) == []


def test_cancel_before_start_does_nothing(tmp_path):
    token = CancelToken()
    token.cancel()
    with pytest.raises(DownloadCancelledError):
        make_downloader().download(make_task(tmp_path), token, lambda u: None)
    assert list(tmp_path.iterdir()) == []


def test_missing_ffmpeg_fails_before_network(tmp_path):
    def explode(params):
        raise AssertionError("不應呼叫 yt-dlp")

    d = Downloader(tools_provider=lambda: ToolInfo(), js_runtime_provider=lambda: JsRuntimeInfo(),
                   ydl_factory=explode)
    with pytest.raises(FFmpegNotFoundError) as info:
        d.download(make_task(tmp_path), CancelToken(), lambda u: None)
    assert "FFmpeg" in str(info.value) and "winget" in str(info.value)


def test_insufficient_disk_space(tmp_path, monkeypatch):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(downloader_mod.shutil, "disk_usage", lambda p: usage(10, 9, 1))
    with pytest.raises(InsufficientDiskSpaceError):
        make_downloader().download(make_task(tmp_path), CancelToken(), lambda u: None)
    assert not (tmp_path / TEMP_ROOT_NAME).exists()


def test_failed_verification_leaves_no_output(tmp_path):
    def bad_probe(path, fmt, ffprobe):
        raise MediaProbeError("沒有影像串流")

    with pytest.raises(MediaProbeError):
        make_downloader(probe=bad_probe).download(make_task(tmp_path), CancelToken(), lambda u: None)
    assert list(tmp_path.iterdir()) == []


def test_playlist_url_task_is_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="播放清單"):
        make_downloader(info={"_type": "playlist", "entries": []}).download(
            make_task(tmp_path), CancelToken(), lambda u: None)


def test_ydl_options_are_safe(tmp_path):
    captured = []

    def factory(params):
        captured.append(params)
        return FakeYDL(params, INFO)

    d = Downloader(tools_provider=lambda: TOOLS, js_runtime_provider=lambda: JsRuntimeInfo("deno", Path("/d")),
                   ydl_factory=factory, probe=fake_probe)
    d.download(make_task(tmp_path), CancelToken(), lambda u: None)
    dl_opts = captured[-1]
    assert dl_opts["noplaylist"] is True
    assert dl_opts["overwrites"] is False
    assert dl_opts["ffmpeg_location"] == str(TOOLS.ffmpeg.parent)
    assert dl_opts["js_runtimes"] == {"deno": {"path": str(Path("/d"))}}
    assert Path(dl_opts["paths"]["home"]).parent.name == TEMP_ROOT_NAME
    assert dl_opts["merge_output_format"] == "mp4"


def test_move_no_overwrite(tmp_path):
    src = tmp_path / "a"
    src.write_text("new")
    dst = tmp_path / "b"
    dst.write_text("old")
    assert move_no_overwrite(src, dst) is False
    assert dst.read_text() == "old" and src.exists()
    dst.unlink()
    assert move_no_overwrite(src, dst) is True
    assert dst.read_text() == "new" and not src.exists()


def test_describe_selection_lists_available_resolutions():
    text = describe_selection(INFO, MediaFormat.MP4, "1080")
    assert text.startswith("720p") and "360p、720p" in text
    assert describe_selection(INFO, MediaFormat.MP4, "720") == "720p"
    assert "未知" in describe_selection({"requested_formats": [{}]}, MediaFormat.MP3, "128")
    assert "不會提升" not in describe_selection(INFO, MediaFormat.MP3, "128")


def test_extract_playlist_builds_watch_urls():
    info = {"title": "我的清單", "entries": [{"id": "aaaaaaaaaaa", "url": "aaaaaaaaaaa", "title": "A"},
                                           {"id": "bbbbbbbbbbb", "url": "https://www.youtube.com/watch?v=bbbbbbbbbbb"},
                                           None]}
    d = make_downloader(info=info)
    result = d.extract_playlist("https://www.youtube.com/playlist?list=PLxxxxxxxxxx", limit=1)
    assert result.title == "我的清單"
    assert [e.url for e in result.entries] == ["https://www.youtube.com/watch?v=aaaaaaaaaaa"]
    assert result.truncated
