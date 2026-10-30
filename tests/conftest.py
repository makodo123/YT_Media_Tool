from __future__ import annotations

import os
import time

import pytest

from tests.fakes import FakeDownloader
from yt_media_tool.core.queue_manager import QueueManager, TaskSpec
from yt_media_tool.core.task_models import MediaFormat
from yt_media_tool.storage.database import Database


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    """所有測試的 AppData 都導向暫存資料夾，不寫入真實使用者目錄。"""
    data_dir = tmp_path / "appdata"
    monkeypatch.setenv("YTMT_DATA_DIR", str(data_dir))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return data_dir


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    yield database
    try:
        database.close()
    except Exception:
        pass


@pytest.fixture
def fake_downloader():
    return FakeDownloader()


@pytest.fixture
def queue_factory(db, fake_downloader):
    created: list[QueueManager] = []

    def make(max_concurrent: int = 1, paused: bool = False, keep_history: bool = True) -> QueueManager:
        q = QueueManager(db, fake_downloader, max_concurrent=max_concurrent, paused=paused,
                         keep_history=keep_history)
        created.append(q)
        return q

    yield make
    for q in created:
        q.shutdown(timeout=5)


@pytest.fixture
def spec_factory(tmp_path):
    def make(url: str, fmt: MediaFormat = MediaFormat.MP4, quality: str = "1080") -> TaskSpec:
        return TaskSpec(url=url, media_format=fmt, quality=quality, output_dir=str(tmp_path / "out"))

    return make


def wait_until(predicate, timeout: float = 5.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()
