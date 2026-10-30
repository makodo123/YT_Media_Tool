"""下載佇列管理：排程、並行數控制、取消、重試、資料保存與程式重啟後的恢復。

此模組不依賴 Qt；GUI 透過 add_listener 註冊回呼，再以 Qt signal 轉送到主執行緒。
回呼可能在工作執行緒中被呼叫，且一律在釋放內部鎖之後才呼叫，避免死結。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from yt_media_tool.core.downloader import CancelToken, Downloader, ProgressUpdate
from yt_media_tool.core.errors import DownloadCancelledError, explain_error
from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus
from yt_media_tool.storage.database import Database
from yt_media_tool.storage.settings import MAX_CONCURRENT, MIN_CONCURRENT

log = logging.getLogger(__name__)

# 事件名稱
TASK_ADDED = "task_added"
TASK_UPDATED = "task_updated"  # 狀態或可保存欄位改變
TASK_PROGRESS = "task_progress"  # 僅進度 / 速度 / ETA 改變
TASK_REMOVED = "task_removed"  # payload 為 task id
TASK_FINISHED = "task_finished"  # 完成、失敗或取消
QUEUE_STATE = "queue_state"  # 暫停 / 並行數 / 重新排序等

Listener = Callable[[str, Any], None]


@dataclass
class TaskSpec:
    url: str
    media_format: MediaFormat
    quality: str
    output_dir: str
    title: str = ""


@dataclass
class QueueProgress:
    total: int
    finished: int
    completed: int
    failed: int
    cancelled: int
    active: int
    percent: float


class QueueManager:
    def __init__(
        self,
        db: Database,
        downloader: Downloader,
        max_concurrent: int = 1,
        keep_history: bool = True,
        paused: bool = False,
    ) -> None:
        self._db = db
        self._downloader = downloader
        self._lock = threading.RLock()
        self._tasks: dict[int, DownloadTask] = {}
        self._tokens: dict[int, CancelToken] = {}
        self._threads: dict[int, threading.Thread] = {}
        self._listeners: list[Listener] = []
        self._max_concurrent = self._clamp(max_concurrent)
        self.keep_history = keep_history
        self._paused = paused
        self._accepting = True
        self._closed = False

    # ---- 監聽 ----
    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def _emit(self, events: Iterable[tuple[str, Any]]) -> None:
        for event, payload in events:
            for listener in list(self._listeners):
                try:
                    listener(event, payload)
                except Exception:
                    log.exception("佇列事件處理失敗：%s", event)

    # ---- 查詢 ----
    @staticmethod
    def _clamp(value: int) -> int:
        return min(MAX_CONCURRENT, max(MIN_CONCURRENT, int(value)))

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def is_paused(self) -> bool:
        return self._paused

    def tasks(self) -> list[DownloadTask]:
        with self._lock:
            return [t.snapshot() for t in sorted(self._tasks.values(), key=lambda t: (t.sort_order, t.id or 0))]

    def get(self, task_id: int) -> DownloadTask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.snapshot() if task else None

    def running_count(self) -> int:
        with self._lock:
            return len(self._threads)

    def has_active_tasks(self) -> bool:
        with self._lock:
            return bool(self._threads)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status is TaskStatus.WAITING)

    def progress(self) -> QueueProgress:
        with self._lock:
            tasks = list(self._tasks.values())
        total = len(tasks)
        def count(status: TaskStatus) -> int:
            return sum(1 for t in tasks if t.status is status)

        completed, failed = count(TaskStatus.COMPLETED), count(TaskStatus.FAILED)
        cancelled = count(TaskStatus.CANCELLED)
        active = sum(1 for t in tasks if t.status.is_active)
        # 失敗與取消的任務視為「已結束」，計入整體進度
        percent = (sum(100.0 if t.status.is_finished else t.progress for t in tasks) / total) if total else 0.0
        return QueueProgress(total, completed + failed + cancelled, completed, failed, cancelled, active, percent)

    # ---- 恢復 ----
    def restore(self) -> list[DownloadTask]:
        """載入資料庫中的任務；上次中斷於下載中 / 轉檔中的任務改回等待。回傳未完成任務。"""
        restored = self._db.load_tasks()
        unfinished = []
        with self._lock:
            for task in restored:
                if task.status.is_active:
                    task.transition_to(TaskStatus.WAITING)
                    task.progress = 0.0
                    task.error_message = "上次程式關閉時中斷，已重新排入佇列"
                    self._db.save_task(task)
                self._tasks[task.id] = task  # type: ignore[index]
                if task.status is TaskStatus.WAITING:
                    unfinished.append(task.snapshot())
        self._emit([(TASK_ADDED, t.snapshot()) for t in self.tasks()])
        return unfinished

    # ---- 新增 ----
    def add_task(self, spec: TaskSpec) -> DownloadTask:
        return self.add_tasks([spec])[0]

    def add_tasks(self, specs: Iterable[TaskSpec]) -> list[DownloadTask]:
        if not self._accepting:
            raise RuntimeError("佇列已關閉，無法加入新任務")
        added = []
        with self._lock:
            order = self._db.next_sort_order()
            for spec in specs:
                task = DownloadTask(url=spec.url, media_format=spec.media_format, quality=spec.quality,
                                    output_dir=spec.output_dir, title=spec.title, sort_order=order)
                order += 1
                self._db.insert_task(task)
                self._tasks[task.id] = task  # type: ignore[index]
                added.append(task.snapshot())
        self._emit([(TASK_ADDED, t) for t in added])
        self._schedule()
        return added

    # ---- 控制 ----
    def set_max_concurrent(self, value: int) -> None:
        self._max_concurrent = self._clamp(value)
        self._emit([(QUEUE_STATE, None)])
        self._schedule()

    def pause(self) -> None:
        """暫停排程：不再啟動新任務，進行中的任務會繼續完成。"""
        self._paused = True
        self._emit([(QUEUE_STATE, None)])

    def resume(self) -> None:
        self._paused = False
        self._emit([(QUEUE_STATE, None)])
        self._schedule()

    def cancel(self, task_id: int) -> bool:
        events = []
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status.is_finished:
                return False
            if task_id in self._tokens:  # 執行中：通知工作執行緒終止，由其更新狀態
                self._tokens[task_id].cancel("user")
                task.cancel_requested = True
                task.stage = "取消中…"
                events.append((TASK_UPDATED, task.snapshot()))
            else:
                task.transition_to(TaskStatus.CANCELLED)
                task.error_message = "使用者已取消"
                self._db.save_task(task)
                self._add_history(task)
                events += [(TASK_UPDATED, task.snapshot()), (TASK_FINISHED, task.snapshot())]
        self._emit(events)
        return True

    def cancel_all(self) -> int:
        with self._lock:
            ids = [t.id for t in self._tasks.values() if not t.status.is_finished]
        return sum(1 for task_id in ids if self.cancel(task_id))  # type: ignore[arg-type]

    def retry(self, task_id: int) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            task.reset_for_retry()
            task.sort_order = self._db.next_sort_order()  # 重試的任務排到佇列最後
            self._db.save_task(task)
            snap = task.snapshot()
        self._emit([(TASK_UPDATED, snap), (QUEUE_STATE, None)])
        self._schedule()
        return True

    def retry_failed(self) -> int:
        with self._lock:
            ids = [t.id for t in sorted(self._tasks.values(), key=lambda t: t.sort_order)
                   if t.status is TaskStatus.FAILED]
        return sum(1 for task_id in ids if self.retry(task_id))  # type: ignore[arg-type]

    def remove(self, task_id: int) -> bool:
        """從佇列移除非執行中的任務（只刪除紀錄，不刪除任何檔案）。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task_id in self._threads:
                return False
            del self._tasks[task_id]
            self._db.delete_task(task_id)
        self._emit([(TASK_REMOVED, task_id)])
        return True

    def clear_completed(self) -> int:
        with self._lock:
            ids = [tid for tid, t in self._tasks.items() if t.status is TaskStatus.COMPLETED]
            for tid in ids:
                del self._tasks[tid]
            self._db.delete_tasks_with_status(TaskStatus.COMPLETED)
        self._emit([(TASK_REMOVED, tid) for tid in ids])
        return len(ids)

    def move(self, task_id: int, delta: int) -> bool:
        """調整等待中任務的順序（delta=-1 上移、+1 下移）。"""
        with self._lock:
            ordered = sorted(self._tasks.values(), key=lambda t: (t.sort_order, t.id or 0))
            index = next((i for i, t in enumerate(ordered) if t.id == task_id), None)
            if index is None or ordered[index].status is not TaskStatus.WAITING:
                return False
            target = index + delta
            if not 0 <= target < len(ordered):
                return False
            a, b = ordered[index], ordered[target]
            a.sort_order, b.sort_order = b.sort_order, a.sort_order
            if a.sort_order == b.sort_order:
                a.sort_order += delta
            self._db.update_task(a.id, sort_order=a.sort_order)  # type: ignore[arg-type]
            self._db.update_task(b.id, sort_order=b.sort_order)  # type: ignore[arg-type]
        self._emit([(QUEUE_STATE, None)])
        return True

    # ---- 排程與執行 ----
    def _next_waiting(self) -> DownloadTask | None:
        waiting = [t for t in self._tasks.values() if t.status is TaskStatus.WAITING and t.id not in self._threads]
        return min(waiting, key=lambda t: (t.sort_order, t.id or 0), default=None)

    def _schedule(self) -> None:
        events = []
        with self._lock:
            if self._paused or not self._accepting:
                return
            while len(self._threads) < self._max_concurrent:
                task = self._next_waiting()
                if task is None:
                    break
                task.transition_to(TaskStatus.DOWNLOADING)
                task.attempts += 1
                task.progress = 0.0
                task.error_message = ""
                task.stage = "準備中"
                self._db.save_task(task)
                token = CancelToken()
                thread = threading.Thread(target=self._worker, args=(task.id, token, task.snapshot()),
                                          name=f"download-{task.id}", daemon=True)
                self._tokens[task.id] = token  # type: ignore[index]
                self._threads[task.id] = thread  # type: ignore[index]
                events.append((TASK_UPDATED, task.snapshot()))
                thread.start()
        self._emit(events)

    def _on_progress(self, task_id: int, update: ProgressUpdate) -> None:
        events = []
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status.is_finished:
                return
            persist = False
            status_changed = update.status is not task.status and task.can_transition(update.status)
            if status_changed:
                task.transition_to(update.status)
                persist = True
            if update.progress is not None:
                task.progress = max(0.0, min(100.0, update.progress))
            task.speed, task.eta = update.speed, update.eta
            if update.stage and not task.cancel_requested:
                task.stage = update.stage
            if update.title is not None and update.title != task.title:
                task.title = update.title
                persist = True
            if update.actual_quality is not None and update.actual_quality != task.actual_quality:
                task.actual_quality = update.actual_quality
                persist = True
            if persist and not self._closed:
                self._db.save_task(task)
            events.append((TASK_UPDATED if persist else TASK_PROGRESS, task.snapshot()))
        self._emit(events)

    def _worker(self, task_id: int, token: CancelToken, snapshot: DownloadTask) -> None:
        status, fields = TaskStatus.FAILED, {"error_message": "未預期的錯誤"}
        try:
            result = self._downloader.download(snapshot, token, lambda u: self._on_progress(task_id, u))
            status, fields = TaskStatus.COMPLETED, {
                "output_path": str(result.output_path), "title": result.title,
                "actual_quality": result.actual_quality, "error_message": "",
            }
        except DownloadCancelledError as exc:
            if exc.reason == "shutdown":
                status, fields = TaskStatus.WAITING, {"error_message": "程式關閉時中斷，下次開啟時繼續"}
            else:
                status, fields = TaskStatus.CANCELLED, {"error_message": "使用者已取消"}
        except Exception as exc:
            log.exception("任務 %s 下載失敗", task_id)
            status, fields = TaskStatus.FAILED, {"error_message": explain_error(exc)}
        finally:
            self._finish(task_id, status, fields)
            self._schedule()

    def _finish(self, task_id: int, status: TaskStatus, fields: dict[str, Any]) -> None:
        events = []
        with self._lock:
            self._threads.pop(task_id, None)
            self._tokens.pop(task_id, None)
            task = self._tasks.get(task_id)
            if task is None:
                return
            for key, value in fields.items():
                setattr(task, key, value)
            if status is TaskStatus.WAITING:
                task.progress = 0.0
            task.transition_to(status)
            if not self._closed:
                try:
                    self._db.save_task(task)
                    if status.is_finished:
                        self._add_history(task)
                except Exception:
                    log.exception("無法保存任務 %s 的狀態", task_id)
            events.append((TASK_UPDATED, task.snapshot()))
            if status.is_finished:
                events.append((TASK_FINISHED, task.snapshot()))
        self._emit(events)

    def _add_history(self, task: DownloadTask) -> None:
        if self.keep_history:
            self._db.add_history(task)

    # ---- 關閉 ----
    def shutdown(self, timeout: float = 15.0) -> bool:
        """停止接受新任務並中斷所有執行中的任務；中斷的任務會保留為「等待」以便下次恢復。

        回傳是否所有工作執行緒都在時限內結束。
        """
        with self._lock:
            self._accepting = False
            for token in self._tokens.values():
                token.cancel("shutdown")
            threads = list(self._threads.items())
        deadline = time.monotonic() + timeout
        for _, thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        with self._lock:
            leftover = [tid for tid, th in self._threads.items() if th.is_alive()]
            for tid in leftover:
                # 工作執行緒仍在等待外部程序結束；先將資料庫狀態改回等待，下次啟動時恢復
                log.warning("任務 %s 未在時限內停止", tid)
                self._db.update_task(tid, status=TaskStatus.WAITING.value,
                                     error_message="程式關閉時中斷，下次開啟時繼續")
            self._closed = True
        return not leftover
