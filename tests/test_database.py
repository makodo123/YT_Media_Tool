import sqlite3

import pytest

from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus
from yt_media_tool.storage.database import MIGRATIONS, SCHEMA_VERSION, Database, DatabaseError
from yt_media_tool.storage.settings import AppSettings, SettingsStore


def make_task(url="https://youtu.be/dQw4w9WgXcQ", **kw):
    return DownloadTask(url=url, media_format=kw.pop("fmt", MediaFormat.MP4), quality=kw.pop("quality", "720"),
                        output_dir=kw.pop("output_dir", "C:/Downloads"), **kw)


def test_creates_all_tables_with_schema_version(db):
    tables = {r[0] for r in db._query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"download_tasks", "download_history", "application_settings"} <= tables
    assert db.schema_version == SCHEMA_VERSION


def test_task_round_trip(db):
    task = db.insert_task(make_task(title="測試影片", sort_order=3))
    task.status = TaskStatus.FAILED
    task.error_message = "網路錯誤"
    task.actual_quality = "480p"
    db.save_task(task)
    loaded = db.get_task(task.id)
    assert loaded.url == task.url
    assert loaded.media_format is MediaFormat.MP4
    assert loaded.status is TaskStatus.FAILED
    assert loaded.error_message == "網路錯誤"
    assert loaded.actual_quality == "480p"
    assert loaded.created_at == task.created_at


def test_sql_injection_strings_are_stored_literally(db):
    evil = "https://youtu.be/dQw4w9WgXcQ'); DROP TABLE download_tasks; --"
    task = db.insert_task(make_task(url=evil, title="'; DELETE FROM download_history; --"))
    db.set_setting("x'; DROP TABLE application_settings; --", "v")
    assert db.get_task(task.id).url == evil
    assert len(db.load_tasks()) == 1
    assert db.get_setting("x'; DROP TABLE application_settings; --") == "v"


def test_update_task_rejects_unknown_columns(db):
    task = db.insert_task(make_task())
    with pytest.raises(DatabaseError):
        db.update_task(task.id, **{"status = 'x' --": "1"})


def test_load_tasks_ordered_by_sort_order(db):
    for order in (3, 1, 2):
        db.insert_task(make_task(title=str(order), sort_order=order))
    assert [t.title for t in db.load_tasks()] == ["1", "2", "3"]
    assert db.next_sort_order() == 4


def test_history_and_clear(db):
    task = db.insert_task(make_task(title="a"))
    task.status = TaskStatus.COMPLETED
    task.output_path = "C:/Downloads/a.mp4"
    db.add_history(task)
    history = db.list_history()
    assert history[0]["title"] == "a" and history[0]["status"] == "completed"
    db.clear_history()
    assert db.list_history() == []


def test_migration_from_v1_preserves_data(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    for statement in MIGRATIONS[0][1]:
        conn.execute(statement)
    conn.execute(
        "INSERT INTO download_tasks (url, media_format, quality, output_dir, status, title, sort_order, "
        "error_message, output_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("https://youtu.be/dQw4w9WgXcQ", "mp3", "192", "D:/music", "waiting", "舊任務", 1, "", "",
         "2025-01-01T00:00:00+00:00", "2025-01-01T00:00:00+00:00"))
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    database = Database(path)
    try:
        assert database.schema_version == SCHEMA_VERSION
        task = database.load_tasks()[0]
        assert task.title == "舊任務" and task.media_format is MediaFormat.MP3 and task.attempts == 0
        assert task.actual_quality == ""
    finally:
        database.close()


def test_newer_schema_is_rejected(tmp_path):
    path = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()
    with pytest.raises(DatabaseError):
        Database(path)


def test_settings_round_trip_and_validation(db):
    store = SettingsStore(db)
    defaults = store.load()
    assert defaults.max_concurrent == 1
    saved = store.save(AppSettings(download_dir="D:/影片", max_concurrent=3, default_format="mp3",
                                   default_mp3_quality="320", default_mp4_quality="720",
                                   open_folder_on_complete=True, keep_history=False))
    loaded = store.load()
    assert loaded == saved
    assert loaded.download_dir == "D:/影片" and loaded.max_concurrent == 3

    # 不合法的值會被修正為合法範圍或預設值
    db.set_setting("settings.max_concurrent", 99)
    db.set_setting("settings.default_mp3_quality", "999")
    db.set_setting("settings.default_format", "avi")
    loaded = store.load()
    assert loaded.max_concurrent == 3
    assert loaded.default_mp3_quality == "192"
    assert loaded.default_format == "mp4"


def test_clip_and_file_name_round_trip(db):
    task = DownloadTask(url="https://youtu.be/dQw4w9WgXcQ", media_format=MediaFormat.MP3, quality="192",
                        output_dir="D:/music", file_name="五月天 - 倔強", clip_start=80.0, clip_end=None)
    db.insert_task(task)
    loaded = db.load_tasks()[0]
    assert (loaded.file_name, loaded.clip_start, loaded.clip_end) == ("五月天 - 倔強", 80.0, None)


def test_completed_downloads_excludes_clips_and_failures(db):
    def finished(url, status, is_clip=False, path="D:/m/a.mp3"):
        t = DownloadTask(url=url, media_format=MediaFormat.MP3, quality="192", output_dir="D:/m", status=status,
                         output_path=path, clip_start=5.0 if is_clip else None)
        db.add_history(t)

    finished("https://youtu.be/aaaaaaaaaaa", TaskStatus.COMPLETED)
    finished("https://youtu.be/bbbbbbbbbbb", TaskStatus.COMPLETED, is_clip=True)
    finished("https://youtu.be/ccccccccccc", TaskStatus.FAILED, path="")
    finished("https://youtu.be/ddddddddddd", TaskStatus.COMPLETED, path="D:/m/new.mp3")
    assert [r["url"][-11:] for r in db.completed_downloads()] == ["ddddddddddd", "aaaaaaaaaaa"]  # 新 → 舊


def test_migrates_v2_database_to_add_clip_columns(tmp_path):
    path = tmp_path / "v2.sqlite3"
    conn = sqlite3.connect(path)
    for _, statements in MIGRATIONS[:2]:
        for statement in statements:
            conn.execute(statement)
    conn.execute(
        "INSERT INTO download_history (url, title, media_format, quality, output_path, status, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("https://youtu.be/dQw4w9WgXcQ", "舊歌", "mp3", "192", "D:/m/舊歌.mp3", "completed", "2026-01-01"))
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()
    database = Database(path)
    try:
        assert database.schema_version == SCHEMA_VERSION == 3
        assert [r["output_path"] for r in database.completed_downloads()] == ["D:/m/舊歌.mp3"]  # 舊紀錄不是片段
    finally:
        database.close()
