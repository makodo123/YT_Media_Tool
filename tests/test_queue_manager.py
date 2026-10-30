from yt_media_tool.core.queue_manager import TASK_FINISHED, QueueManager
from yt_media_tool.core.task_models import MediaFormat, TaskStatus

from tests.conftest import wait_until

URL_A = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
URL_B = "https://www.youtube.com/watch?v=bbbbbbbbbbb"
URL_C = "https://www.youtube.com/watch?v=ccccccccccc"
BLOCK_1 = "https://www.youtube.com/watch?v=block000001"
BLOCK_2 = "https://www.youtube.com/watch?v=block000002"
FAIL = "https://www.youtube.com/watch?v=fail0000001"


def statuses(queue):
    return [t.status for t in queue.tasks()]


def idle(queue):
    return lambda: not queue.has_active_tasks() and queue.pending_count() == 0


def test_tasks_run_in_queue_order(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory(paused=True)
    queue.add_tasks([spec_factory(u) for u in (URL_C, URL_A, URL_B)])
    queue.resume()
    assert wait_until(idle(queue))
    assert fake_downloader.started == [URL_C, URL_A, URL_B]
    assert statuses(queue) == [TaskStatus.COMPLETED] * 3


def test_move_changes_execution_order(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory(paused=True)
    a, b, c = queue.add_tasks([spec_factory(u) for u in (URL_A, URL_B, URL_C)])
    assert queue.move(c.id, -1)
    assert queue.move(c.id, -1)
    assert not queue.move(c.id, -1)  # 已在最前面
    assert [t.id for t in queue.tasks()] == [c.id, a.id, b.id]
    queue.resume()
    assert wait_until(idle(queue))
    assert fake_downloader.started == [URL_C, URL_A, URL_B]


def test_default_concurrency_is_one(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory()
    queue.add_tasks([spec_factory(BLOCK_1), spec_factory(BLOCK_2)])
    assert wait_until(lambda: fake_downloader.running == 1)
    assert queue.running_count() == 1
    assert statuses(queue) == [TaskStatus.DOWNLOADING, TaskStatus.WAITING]
    fake_downloader.release(BLOCK_1)
    fake_downloader.release(BLOCK_2)
    assert wait_until(idle(queue))
    assert fake_downloader.max_running == 1


def test_concurrency_can_be_raised_to_three_but_not_more(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory(max_concurrent=10)
    assert queue.max_concurrent == 3
    urls = [f"https://www.youtube.com/watch?v=block{i:06d}" for i in range(5)]
    queue.add_tasks([spec_factory(u) for u in urls])
    assert wait_until(lambda: fake_downloader.running == 3)
    for u in urls:
        fake_downloader.release(u)
    assert wait_until(idle(queue))
    assert fake_downloader.max_running == 3


def test_cancel_waiting_task(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory()
    running, waiting = queue.add_tasks([spec_factory(BLOCK_1), spec_factory(URL_A)])
    assert wait_until(lambda: queue.get(running.id).status is TaskStatus.DOWNLOADING)
    assert queue.cancel(waiting.id)
    assert queue.get(waiting.id).status is TaskStatus.CANCELLED
    assert queue.get(running.id).status is TaskStatus.DOWNLOADING  # 其他任務不受影響
    fake_downloader.release(BLOCK_1)
    assert wait_until(idle(queue))
    assert URL_A not in fake_downloader.started
    assert queue.get(running.id).status is TaskStatus.COMPLETED


def test_cancel_running_task_stops_it_and_queue_continues(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory()
    running, nxt = queue.add_tasks([spec_factory(BLOCK_1), spec_factory(URL_A)])
    assert wait_until(lambda: fake_downloader.running == 1)
    assert queue.cancel(running.id)
    assert wait_until(lambda: queue.get(running.id).status is TaskStatus.CANCELLED)
    assert wait_until(lambda: queue.get(nxt.id).status is TaskStatus.COMPLETED)
    assert queue.get(running.id).error_message == "使用者已取消"


def test_cancel_finished_task_is_noop(queue_factory, spec_factory):
    queue = queue_factory()
    task = queue.add_task(spec_factory(URL_A))
    assert wait_until(idle(queue))
    assert not queue.cancel(task.id)
    assert queue.get(task.id).status is TaskStatus.COMPLETED


def test_cancel_all(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory(max_concurrent=2)
    queue.add_tasks([spec_factory(u) for u in (BLOCK_1, BLOCK_2, URL_A, URL_B)])
    assert wait_until(lambda: fake_downloader.running == 2)
    assert queue.cancel_all() == 4
    assert wait_until(lambda: all(s is TaskStatus.CANCELLED for s in statuses(queue)))
    assert not queue.has_active_tasks()
    assert URL_A not in fake_downloader.started


def test_failure_does_not_stop_queue_and_has_message(queue_factory, spec_factory):
    queue = queue_factory()
    failed, ok = queue.add_tasks([spec_factory(FAIL), spec_factory(URL_A)])
    assert wait_until(idle(queue))
    assert queue.get(failed.id).status is TaskStatus.FAILED
    assert "私人影片" in queue.get(failed.id).error_message
    assert queue.get(ok.id).status is TaskStatus.COMPLETED


def test_retry_failed_task(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory()
    failed, ok = queue.add_tasks([spec_factory(FAIL), spec_factory(URL_A)])
    assert wait_until(idle(queue))
    fake_downloader.started.clear()
    # 讓重試成功：把網址從失敗名單移除（FakeDownloader 依網址判斷）
    queue._tasks[failed.id].url = URL_B
    assert queue.retry(failed.id)
    assert wait_until(lambda: queue.get(failed.id).status is TaskStatus.COMPLETED)
    task = queue.get(failed.id)
    assert task.attempts == 2
    assert task.error_message == ""
    assert not queue.retry(ok.id)  # 已完成任務不可重試


def test_retry_moves_task_to_end(queue_factory, spec_factory):
    queue = queue_factory()
    failed = queue.add_task(spec_factory(FAIL))
    assert wait_until(idle(queue))
    queue.pause()
    later = queue.add_task(spec_factory(URL_A))
    queue.retry(failed.id)
    assert [t.id for t in queue.tasks()] == [later.id, failed.id]


def test_retry_failed_batch_and_cancelled(queue_factory, spec_factory):
    queue = queue_factory(paused=True)
    a, b = queue.add_tasks([spec_factory(URL_A), spec_factory(URL_B)])
    queue.cancel(a.id)
    queue.cancel(b.id)
    assert queue.retry(a.id)
    assert queue.get(a.id).status is TaskStatus.WAITING
    assert queue.retry_failed() == 0


def test_clear_completed_keeps_files_and_other_tasks(queue_factory, spec_factory, db, tmp_path):
    queue = queue_factory()
    done, failed = queue.add_tasks([spec_factory(URL_A), spec_factory(FAIL)])
    assert wait_until(idle(queue))
    output = queue.get(done.id).output_path
    assert queue.clear_completed() == 1
    assert queue.get(done.id) is None
    assert queue.get(failed.id) is not None
    assert db.get_task(done.id) is None
    from pathlib import Path

    assert Path(output).is_file()  # 清除紀錄不刪除檔案


def test_state_is_persisted_and_restored(db, fake_downloader, spec_factory):
    queue = QueueManager(db, fake_downloader)
    done, running, waiting = queue.add_tasks([spec_factory(URL_A), spec_factory(BLOCK_1), spec_factory(URL_B)])
    assert wait_until(lambda: queue.get(running.id).status is TaskStatus.DOWNLOADING)
    # 模擬程式異常結束：資料庫中留下「下載中」狀態
    assert db.get_task(running.id).status is TaskStatus.DOWNLOADING

    restored_queue = QueueManager(db, fake_downloader, paused=True)
    unfinished = restored_queue.restore()
    assert {t.id for t in unfinished} == {running.id, waiting.id}
    assert restored_queue.get(running.id).status is TaskStatus.WAITING
    assert restored_queue.get(done.id).status is TaskStatus.COMPLETED
    assert db.get_task(running.id).status is TaskStatus.WAITING
    fake_downloader.release(BLOCK_1)
    queue.shutdown(5)


def test_shutdown_interrupts_and_requeues_tasks(db, fake_downloader, spec_factory):
    queue = QueueManager(db, fake_downloader, max_concurrent=2)
    a, b, c = queue.add_tasks([spec_factory(BLOCK_1), spec_factory(BLOCK_2), spec_factory(URL_A)])
    assert wait_until(lambda: fake_downloader.running == 2)
    assert queue.shutdown(timeout=5)
    assert fake_downloader.running == 0
    assert not queue.has_active_tasks()
    for task in (a, b):
        assert db.get_task(task.id).status is TaskStatus.WAITING
    assert db.get_task(c.id).status is TaskStatus.WAITING
    assert URL_A not in fake_downloader.started
    try:
        queue.add_task(spec_factory(URL_B))
    except RuntimeError:
        pass
    else:
        raise AssertionError("關閉後不應接受新任務")


def test_history_written_only_when_enabled(queue_factory, spec_factory, db):
    queue = queue_factory(keep_history=False)
    queue.add_task(spec_factory(URL_A))
    assert wait_until(idle(queue))
    assert db.list_history() == []
    queue.keep_history = True
    queue.add_task(spec_factory(URL_B, MediaFormat.MP3, "320"))
    assert wait_until(idle(queue))
    history = db.list_history()
    assert len(history) == 1 and history[0]["media_format"] == "mp3"


def test_events_emitted_and_listener_errors_isolated(queue_factory, spec_factory):
    queue = queue_factory()
    seen = []
    queue.add_listener(lambda e, p: (_ for _ in ()).throw(RuntimeError("listener bug")))
    queue.add_listener(lambda e, p: seen.append(e))
    queue.add_task(spec_factory(URL_A))
    assert wait_until(idle(queue))
    assert TASK_FINISHED in seen
    assert queue.progress().completed == 1


def test_overall_progress(queue_factory, spec_factory):
    queue = queue_factory()
    queue.add_tasks([spec_factory(URL_A), spec_factory(FAIL)])
    assert wait_until(idle(queue))
    progress = queue.progress()
    assert progress.total == 2 and progress.completed == 1 and progress.failed == 1
    assert progress.percent == 100.0


def test_remove_only_non_running(queue_factory, spec_factory, fake_downloader):
    queue = queue_factory()
    running, waiting = queue.add_tasks([spec_factory(BLOCK_1), spec_factory(URL_A)])
    assert wait_until(lambda: fake_downloader.running == 1)
    assert not queue.remove(running.id)
    assert queue.remove(waiting.id)
    fake_downloader.release(BLOCK_1)
