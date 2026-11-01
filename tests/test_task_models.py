import pytest

from yt_media_tool.core.task_models import (
    DownloadTask, InvalidTransitionError, MediaFormat, TaskStatus, format_eta, format_speed,
)


def make_task(**kw):
    return DownloadTask(url="https://youtu.be/dQw4w9WgXcQ", media_format=kw.pop("fmt", MediaFormat.MP4),
                        quality=kw.pop("quality", "1080"), output_dir="/tmp", id=1, **kw)


def test_happy_path_transitions():
    task = make_task()
    for status in (TaskStatus.DOWNLOADING, TaskStatus.PROCESSING, TaskStatus.COMPLETED):
        task.transition_to(status)
    assert task.status is TaskStatus.COMPLETED
    assert task.progress == 100.0
    assert task.completed_at


@pytest.mark.parametrize("start,target", [
    (TaskStatus.WAITING, TaskStatus.COMPLETED),
    (TaskStatus.WAITING, TaskStatus.PROCESSING),
    (TaskStatus.COMPLETED, TaskStatus.WAITING),
    (TaskStatus.COMPLETED, TaskStatus.FAILED),
    (TaskStatus.FAILED, TaskStatus.COMPLETED),
    (TaskStatus.CANCELLED, TaskStatus.DOWNLOADING),
])
def test_invalid_transitions_raise(start, target):
    task = make_task(status=start)
    with pytest.raises(InvalidTransitionError):
        task.transition_to(target)


def test_retry_resets_runtime_fields():
    task = make_task(status=TaskStatus.FAILED, error_message="boom", progress=40.0, actual_quality="720p")
    task.reset_for_retry()
    assert task.status is TaskStatus.WAITING
    assert task.error_message == "" and task.progress == 0 and task.actual_quality == ""


def test_finished_clears_speed_and_eta():
    task = make_task()
    task.transition_to(TaskStatus.DOWNLOADING)
    task.speed, task.eta, task.stage = 1000.0, 30, "下載中"
    task.transition_to(TaskStatus.CANCELLED)
    assert task.speed is None and task.eta is None and task.stage == ""


def test_invalid_quality_rejected():
    with pytest.raises(ValueError):
        make_task(fmt=MediaFormat.MP3, quality="1080")
    with pytest.raises(ValueError):
        make_task(fmt=MediaFormat.MP4, quality="320")


def test_status_labels_are_traditional_chinese():
    assert [s.label for s in TaskStatus] == ["等待中", "下載中", "轉檔中", "已完成", "失敗", "已取消"]


def test_format_helpers():
    assert format_speed(None) == ""
    assert format_speed(512 * 1024) == "512.0 KB/s"
    assert format_speed(3 * 1024 * 1024) == "3.00 MB/s"
    assert format_eta(None) == ""
    assert format_eta(75) == "01:15"
    assert format_eta(3725) == "1:02:05"


@pytest.mark.parametrize("text,seconds", [
    ("90", 90.0), ("1:30", 90.0), ("01:30", 90.0), ("1:02:30", 3750.0), ("1:30.5", 90.5), ("1：30", 90.0),
    (" 0:59 ", 59.0), ("", None), ("  ", None),
])
def test_parse_clock(text, seconds):
    from yt_media_tool.core.task_models import parse_clock

    assert parse_clock(text) == seconds


@pytest.mark.parametrize("text", ["1:60", "1:60:00", "abc", "1:2:3:4", "-5", "1:"])
def test_parse_clock_rejects_bad_input(text):
    from yt_media_tool.core.task_models import parse_clock

    with pytest.raises(ValueError, match="時間格式不正確"):
        parse_clock(text)


def test_clip_text_and_format_clock():
    from yt_media_tool.core.task_models import clip_text, format_clock

    assert [format_clock(s) for s in (0, 65.97, 2.5, 3725.5, 59.96)] == ["0:00", "1:06", "0:02.5", "1:02:05.5", "1:00"]
    assert clip_text(80, 275) == "片段 1:20～4:35"
    assert clip_text(None, 30) == "片段 0:00～0:30"
    assert clip_text(60, None) == "片段 1:00～結尾"
    assert clip_text(None, None) == ""
    task = make_task(clip_start=80.0)
    assert task.is_clip and task.clip_text == "片段 1:20～結尾"
    assert not make_task().is_clip
