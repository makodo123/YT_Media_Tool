"""下載任務的資料模型與狀態機。"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum


class TaskStatus(str, Enum):
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"  # FFmpeg 合併 / 轉檔中
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]

    @property
    def is_active(self) -> bool:
        return self in (TaskStatus.DOWNLOADING, TaskStatus.PROCESSING)

    @property
    def is_finished(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


STATUS_LABELS = {
    TaskStatus.WAITING: "等待",
    TaskStatus.DOWNLOADING: "下載中",
    TaskStatus.PROCESSING: "轉檔中",
    TaskStatus.COMPLETED: "完成",
    TaskStatus.FAILED: "失敗",
    TaskStatus.CANCELLED: "取消",
}

# 合法的狀態轉換
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.WAITING: frozenset({TaskStatus.DOWNLOADING, TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.DOWNLOADING: frozenset({
        TaskStatus.PROCESSING, TaskStatus.COMPLETED, TaskStatus.FAILED,
        TaskStatus.CANCELLED, TaskStatus.WAITING,  # WAITING：程式關閉時中斷，下次恢復
    }),
    TaskStatus.PROCESSING: frozenset({
        TaskStatus.DOWNLOADING,  # 例如影片與音訊分別下載後再合併
        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.WAITING,
    }),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.WAITING}),  # 重試
    TaskStatus.CANCELLED: frozenset({TaskStatus.WAITING}),  # 重試
}


class InvalidTransitionError(ValueError):
    pass


class MediaFormat(str, Enum):
    MP4 = "mp4"
    MP3 = "mp3"

    @property
    def label(self) -> str:
        return self.value.upper()


# 品質選項（目標輸出設定）
MP4_QUALITIES: dict[str, str] = {"720": "720p", "1080": "1080p", "best": "最高可用解析度"}
MP3_QUALITIES: dict[str, str] = {"128": "128 kbps", "192": "192 kbps", "320": "320 kbps"}


def quality_options(media_format: MediaFormat) -> dict[str, str]:
    return MP4_QUALITIES if media_format is MediaFormat.MP4 else MP3_QUALITIES


def quality_label(media_format: MediaFormat, quality: str) -> str:
    return quality_options(media_format).get(quality, quality)


def validate_quality(media_format: MediaFormat, quality: str) -> str:
    if quality not in quality_options(media_format):
        raise ValueError(f"{media_format.label} 不支援品質設定：{quality}")
    return quality


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class DownloadTask:
    url: str
    media_format: MediaFormat
    quality: str
    output_dir: str
    id: int | None = None
    title: str = ""
    status: TaskStatus = TaskStatus.WAITING
    sort_order: int = 0
    error_message: str = ""
    output_path: str = ""
    actual_quality: str = ""  # 實際取得的格式說明（例如原始素材僅有 720p）
    attempts: int = 0
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    completed_at: str = ""
    # 以下為執行期資訊，不寫入資料庫
    progress: float = 0.0  # 0~100
    speed: float | None = None  # bytes/s
    eta: int | None = None  # 秒
    stage: str = ""  # 例如「影音合併中」「MP3 轉檔中」
    cancel_requested: bool = False

    def __post_init__(self) -> None:
        self.media_format = MediaFormat(self.media_format)
        self.status = TaskStatus(self.status)
        validate_quality(self.media_format, self.quality)

    @property
    def display_title(self) -> str:
        return self.title or self.url

    @property
    def quality_text(self) -> str:
        return quality_label(self.media_format, self.quality)

    def can_transition(self, new_status: TaskStatus) -> bool:
        return new_status == self.status or new_status in ALLOWED_TRANSITIONS[self.status]

    def transition_to(self, new_status: TaskStatus) -> None:
        new_status = TaskStatus(new_status)
        if not self.can_transition(new_status):
            raise InvalidTransitionError(f"任務 {self.id} 無法由「{self.status.label}」變更為「{new_status.label}」")
        self.status = new_status
        self.updated_at = now_iso()
        if new_status is TaskStatus.COMPLETED:
            self.progress = 100.0
            self.completed_at = self.updated_at
        if new_status.is_finished or new_status is TaskStatus.WAITING:
            self.speed = None
            self.eta = None
            self.stage = ""
            self.cancel_requested = False

    def reset_for_retry(self) -> None:
        self.transition_to(TaskStatus.WAITING)
        self.error_message = ""
        self.output_path = ""
        self.actual_quality = ""
        self.progress = 0.0
        self.completed_at = ""

    def snapshot(self) -> DownloadTask:
        return dataclasses.replace(self)


def format_speed(speed: float | None) -> str:
    if not speed or speed <= 0:
        return ""
    if speed >= 1024 * 1024:
        return f"{speed / 1024 / 1024:.2f} MB/s"
    return f"{speed / 1024:.1f} KB/s"


def format_eta(seconds: int | float | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
