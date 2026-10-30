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
