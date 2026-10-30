"""組合應用程式各元件（資料庫、設定、下載引擎、佇列），供 GUI 與測試共用。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from yt_media_tool.core import converter
from yt_media_tool.core.converter import JsRuntimeInfo, ToolInfo
from yt_media_tool.core.downloader import Downloader
from yt_media_tool.core.queue_manager import QueueManager
from yt_media_tool.storage.database import Database
from yt_media_tool.storage.settings import AppSettings, SettingsStore
from yt_media_tool.utils import paths

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    db: Database
    settings_store: SettingsStore
    settings: AppSettings
    downloader: Downloader
    queue: QueueManager
    tools: ToolInfo
    js_runtime: JsRuntimeInfo

    def refresh_tools(self) -> ToolInfo:
        self.tools = converter.find_ffmpeg(self.settings.ffmpeg_dir or None)
        log.info("FFmpeg：%s", f"{self.tools.ffmpeg}（{self.tools.source}）" if self.tools.available else "未找到")
        return self.tools

    def current_tools(self) -> ToolInfo:
        # 先前找不到時重新偵測一次，讓使用者安裝 FFmpeg 後不必重新啟動
        return self.tools if self.tools.available else self.refresh_tools()

    def apply_settings(self, new_settings: AppSettings) -> AppSettings:
        old_ffmpeg = self.settings.ffmpeg_dir
        self.settings = self.settings_store.save(new_settings)
        self.queue.set_max_concurrent(self.settings.max_concurrent)
        self.queue.keep_history = self.settings.keep_history
        if self.settings.ffmpeg_dir != old_ffmpeg:
            self.refresh_tools()
        return self.settings

    def close(self, timeout: float = 15.0) -> bool:
        finished = self.queue.shutdown(timeout)
        self.db.close()
        return finished


def create_context(db_path: Path | str | None = None, downloader: Downloader | None = None,
                   start_paused: bool = True) -> AppContext:
    db = Database(db_path or paths.database_path())
    store = SettingsStore(db)
    settings = store.load()
    tools = converter.find_ffmpeg(settings.ffmpeg_dir or None)
    js_runtime = converter.find_js_runtime()
    ctx_holder: dict[str, AppContext] = {}
    if downloader is None:
        downloader = Downloader(tools_provider=lambda: ctx_holder["ctx"].current_tools(),
                                js_runtime_provider=lambda: ctx_holder["ctx"].js_runtime,
                                cookies_provider=lambda: ctx_holder["ctx"].settings.cookie_config())
    queue = QueueManager(db, downloader, max_concurrent=settings.max_concurrent,
                         keep_history=settings.keep_history, paused=start_paused)
    ctx = AppContext(db, store, settings, downloader, queue, tools, js_runtime)
    ctx_holder["ctx"] = ctx
    return ctx
