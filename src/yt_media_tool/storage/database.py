"""SQLite 資料存取層。

- 所有 SQL 一律使用參數化查詢。
- 以 PRAGMA user_version 記錄 schema 版本，依序執行 MIGRATIONS 升級。
- 單一連線搭配鎖，可由多個工作執行緒安全存取。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from yt_media_tool.core.task_models import DownloadTask, TaskStatus, now_iso
from yt_media_tool.utils.paths import replace_path_prefix

log = logging.getLogger(__name__)

# (版本, SQL 陳述式清單)。新增 schema 變更時只能附加新版本，不可修改既有版本。
MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [
        """
        CREATE TABLE download_tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            url           TEXT    NOT NULL,
            media_format  TEXT    NOT NULL CHECK (media_format IN ('mp4', 'mp3')),
            quality       TEXT    NOT NULL,
            output_dir    TEXT    NOT NULL,
            status        TEXT    NOT NULL,
            title         TEXT    NOT NULL DEFAULT '',
            sort_order    INTEGER NOT NULL DEFAULT 0,
            error_message TEXT    NOT NULL DEFAULT '',
            output_path   TEXT    NOT NULL DEFAULT '',
            created_at    TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        )
        """,
        """
        CREATE TABLE download_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id       INTEGER,
            url           TEXT NOT NULL,
            title         TEXT NOT NULL DEFAULT '',
            media_format  TEXT NOT NULL,
            quality       TEXT NOT NULL,
            output_path   TEXT NOT NULL DEFAULT '',
            status        TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            finished_at   TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE application_settings (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    ]),
    (2, [
        "ALTER TABLE download_tasks ADD COLUMN actual_quality TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE download_tasks ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE download_tasks ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''",
        "CREATE INDEX idx_tasks_status_order ON download_tasks (status, sort_order)",
        "CREATE INDEX idx_history_finished ON download_history (finished_at)",
    ]),
    (3, [
        # 選歌視窗修改的檔名、只下載片段的開始 / 結束秒數
        "ALTER TABLE download_tasks ADD COLUMN file_name TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE download_tasks ADD COLUMN clip_start REAL",
        "ALTER TABLE download_tasks ADD COLUMN clip_end REAL",
        # 片段不算「已下載過」整部影片
        "ALTER TABLE download_history ADD COLUMN is_clip INTEGER NOT NULL DEFAULT 0",
    ]),
]
SCHEMA_VERSION = MIGRATIONS[-1][0]

_TASK_COLUMNS = (
    "url", "media_format", "quality", "output_dir", "status", "title", "sort_order",
    "error_message", "output_path", "actual_quality", "attempts", "created_at", "updated_at", "completed_at",
    "file_name", "clip_start", "clip_end",
)
_UPDATABLE_TASK_COLUMNS = frozenset(_TASK_COLUMNS) - {"created_at"}


class DatabaseError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if str(path) != ":memory:" else path
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        try:
            # isolation_level=None：交易由 transaction() 明確控制
            self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10, isolation_level=None)
        except sqlite3.Error as exc:
            raise DatabaseError(f"無法開啟資料庫 {path}：{exc}") from exc
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if isinstance(self.path, Path):
            self._conn.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    # ---- 基礎 ----
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def _query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @property
    def schema_version(self) -> int:
        return int(self._query("PRAGMA user_version")[0][0])

    def migrate(self, target: int = SCHEMA_VERSION) -> None:
        current = self.schema_version
        if current > SCHEMA_VERSION:
            raise DatabaseError(f"資料庫版本 {current} 比程式支援的版本 {SCHEMA_VERSION} 新，請更新程式")
        for version, statements in MIGRATIONS:
            if current < version <= target:
                log.info("資料庫 migration：%s -> %s", current, version)
                with self.transaction() as conn:
                    for statement in statements:
                        conn.execute(statement)
                    # PRAGMA 無法參數化，version 為程式內常數整數
                    conn.execute(f"PRAGMA user_version = {int(version)}")
                current = version

    # ---- download_tasks ----
    @staticmethod
    def _task_values(task: DownloadTask) -> dict[str, Any]:
        return {
            "url": task.url,
            "media_format": task.media_format.value,
            "quality": task.quality,
            "output_dir": task.output_dir,
            "status": task.status.value,
            "title": task.title,
            "sort_order": task.sort_order,
            "error_message": task.error_message,
            "output_path": task.output_path,
            "actual_quality": task.actual_quality,
            "attempts": task.attempts,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
            "file_name": task.file_name,
            "clip_start": task.clip_start,
            "clip_end": task.clip_end,
        }

    def next_sort_order(self) -> int:
        row = self._query("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM download_tasks")
        return int(row[0][0])

    def insert_task(self, task: DownloadTask) -> DownloadTask:
        values = self._task_values(task)
        columns = ", ".join(_TASK_COLUMNS)
        placeholders = ", ".join(f":{c}" for c in _TASK_COLUMNS)
        with self.transaction() as conn:
            # 欄位名稱來自程式內常數 _TASK_COLUMNS，值以具名參數綁定
            cur = conn.execute(f"INSERT INTO download_tasks ({columns}) VALUES ({placeholders})", values)  # noqa: S608
            task.id = int(cur.lastrowid)
        return task

    def save_task(self, task: DownloadTask) -> None:
        """將任務的可保存欄位寫回資料庫。"""
        if task.id is None:
            raise DatabaseError("任務尚未寫入資料庫")
        values = self._task_values(task)
        values.pop("created_at")
        self.update_task(task.id, **values)

    def update_task(self, task_id: int, **fields: Any) -> None:
        unknown = set(fields) - _UPDATABLE_TASK_COLUMNS
        if unknown:
            raise DatabaseError(f"不允許更新的欄位：{', '.join(sorted(unknown))}")
        if not fields:
            return
        fields.setdefault("updated_at", now_iso())
        # 欄位名稱來自白名單，值一律參數化
        assignments = ", ".join(f"{name} = :{name}" for name in fields)
        params = {name: (v.value if isinstance(v, TaskStatus) else v) for name, v in fields.items()}
        params["_id"] = task_id
        with self.transaction() as conn:
            conn.execute(f"UPDATE download_tasks SET {assignments} WHERE id = :_id", params)  # noqa: S608

    def delete_task(self, task_id: int) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM download_tasks WHERE id = ?", (task_id,))

    def delete_tasks_with_status(self, status: TaskStatus) -> int:
        with self.transaction() as conn:
            return conn.execute("DELETE FROM download_tasks WHERE status = ?", (status.value,)).rowcount

    def get_task(self, task_id: int) -> DownloadTask | None:
        rows = self._query("SELECT * FROM download_tasks WHERE id = ?", (task_id,))
        return self._row_to_task(rows[0]) if rows else None

    def load_tasks(self) -> list[DownloadTask]:
        rows = self._query("SELECT * FROM download_tasks ORDER BY sort_order, id")
        tasks = []
        for row in rows:
            try:
                tasks.append(self._row_to_task(row))
            except ValueError:
                log.warning("略過無法解析的任務資料 id=%s", row["id"])
        return tasks

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> DownloadTask:
        data = {key: row[key] for key in row.keys()}
        return DownloadTask(**data)

    # ---- download_history ----
    def add_history(self, task: DownloadTask) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                """INSERT INTO download_history
                   (task_id, url, title, media_format, quality, output_path, status, error_message, finished_at,
                    is_clip)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task.id, task.url, task.title, task.media_format.value, task.quality,
                 task.output_path, task.status.value, task.error_message, now_iso(), int(task.is_clip)),
            )
            return int(cur.lastrowid)

    def rename_output_path(self, old: str, new: str) -> int:
        """檔案改名後更新佇列與歷史紀錄中的檔案位置（路徑比對不分大小寫與斜線方向）。回傳更新筆數。"""
        def same(path: str) -> bool:
            return bool(path) and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(old))

        updated = 0
        with self.transaction() as conn:
            for table in ("download_tasks", "download_history"):
                # 資料表名稱來自程式內常數，值以參數綁定
                rows = conn.execute(f"SELECT id, output_path FROM {table} WHERE output_path != ''").fetchall()  # noqa: S608
                for row in rows:
                    if same(row["output_path"]):
                        conn.execute(f"UPDATE {table} SET output_path = ? WHERE id = ?", (new, row["id"]))  # noqa: S608
                        updated += 1
        return updated

    def rename_folder(self, old: str, new: str) -> int:
        """資料夾改名後更新佇列與歷史紀錄中位於該資料夾內的路徑。回傳更新筆數。"""
        updated = 0
        with self.transaction() as conn:
            for row in conn.execute("SELECT id, output_dir, output_path FROM download_tasks").fetchall():
                new_dir = replace_path_prefix(row["output_dir"], old, new)
                new_path = replace_path_prefix(row["output_path"], old, new)
                if new_dir or new_path:
                    conn.execute("UPDATE download_tasks SET output_dir = ?, output_path = ? WHERE id = ?",
                                 (new_dir or row["output_dir"], new_path or row["output_path"], row["id"]))
                    updated += 1
            for row in conn.execute("SELECT id, output_path FROM download_history").fetchall():
                new_path = replace_path_prefix(row["output_path"], old, new)
                if new_path:
                    conn.execute("UPDATE download_history SET output_path = ? WHERE id = ?", (new_path, row["id"]))
                    updated += 1
        return updated

    def completed_downloads(self) -> list[dict[str, Any]]:
        """所有下載完成的整部影片紀錄（新 → 舊，不含片段）：判斷「已下載過」用。"""
        rows = self._query("SELECT url, media_format, output_path FROM download_history "
                           "WHERE status = ? AND output_path != '' AND is_clip = 0 ORDER BY id DESC",
                           (TaskStatus.COMPLETED.value,))
        return [dict(row) for row in rows]

    def list_history(self, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM download_history ORDER BY id DESC LIMIT ?", (int(limit),))
        return [dict(row) for row in rows]

    def clear_history(self) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM download_history")

    # ---- application_settings ----
    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._query("SELECT value FROM application_settings WHERE key = ?", (key,))
        if not rows:
            return default
        try:
            return json.loads(rows[0]["value"])
        except json.JSONDecodeError:
            return default

    def set_setting(self, key: str, value: Any) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO application_settings (key, value, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                (key, json.dumps(value, ensure_ascii=False), now_iso()),
            )

    def all_settings(self) -> dict[str, Any]:
        result = {}
        for row in self._query("SELECT key, value FROM application_settings"):
            try:
                result[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                continue
        return result
