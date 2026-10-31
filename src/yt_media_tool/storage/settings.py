"""應用程式設定：以 application_settings 資料表保存，載入時驗證並套用預設值。"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from yt_media_tool.core.cookies import COOKIE_SOURCES, CookieConfig
from yt_media_tool.core.task_models import MP3_QUALITIES, MP4_QUALITIES, MediaFormat
from yt_media_tool.storage.database import Database
from yt_media_tool.utils import paths

MIN_CONCURRENT = 1
MAX_CONCURRENT = 3


@dataclass
class AppSettings:
    download_dir: str = field(default_factory=lambda: str(paths.default_download_dir()))
    max_concurrent: int = 1
    default_format: str = MediaFormat.MP4.value
    default_mp3_quality: str = "192"
    default_mp4_quality: str = "1080"
    open_folder_on_complete: bool = False
    keep_history: bool = True
    ffmpeg_dir: str = ""  # 自訂 FFmpeg 位置（空白表示自動偵測）
    playlist_confirm_threshold: int = 1  # 播放清單展開時一律提示確認
    cookies_source: str = "none"  # YouTube 登入資訊來源：none / firefox / file
    cookies_file: str = ""  # cookies_source 為 file 時的 cookies.txt 路徑
    embed_metadata: bool = True  # 寫入標題、演出者並以影片縮圖作為封面
    playlist_subfolder: bool = True  # 播放清單的影片存到以清單名稱命名的子資料夾
    notify_on_complete: bool = True  # 佇列全部完成時通知（工作列閃爍、系統通知）

    def validated(self) -> AppSettings:
        defaults = AppSettings()
        s = dataclasses.replace(self)
        try:
            s.max_concurrent = min(MAX_CONCURRENT, max(MIN_CONCURRENT, int(s.max_concurrent)))
        except (TypeError, ValueError):
            s.max_concurrent = defaults.max_concurrent
        if s.default_format not in (MediaFormat.MP4.value, MediaFormat.MP3.value):
            s.default_format = defaults.default_format
        if s.default_mp3_quality not in MP3_QUALITIES:
            s.default_mp3_quality = defaults.default_mp3_quality
        if s.default_mp4_quality not in MP4_QUALITIES:
            s.default_mp4_quality = defaults.default_mp4_quality
        if not isinstance(s.download_dir, str) or not s.download_dir.strip():
            s.download_dir = defaults.download_dir
        s.open_folder_on_complete = bool(s.open_folder_on_complete)
        s.keep_history = bool(s.keep_history)
        s.embed_metadata = bool(s.embed_metadata)
        s.playlist_subfolder = bool(s.playlist_subfolder)
        s.notify_on_complete = bool(s.notify_on_complete)
        s.ffmpeg_dir = s.ffmpeg_dir if isinstance(s.ffmpeg_dir, str) else ""
        if s.cookies_source not in COOKIE_SOURCES:
            s.cookies_source = defaults.cookies_source
        s.cookies_file = s.cookies_file if isinstance(s.cookies_file, str) else ""
        return s

    def cookie_config(self) -> CookieConfig:
        return CookieConfig(self.cookies_source, self.cookies_file)

    def default_quality_for(self, media_format: MediaFormat) -> str:
        return self.default_mp4_quality if media_format is MediaFormat.MP4 else self.default_mp3_quality


class SettingsStore:
    PREFIX = "settings."

    def __init__(self, db: Database) -> None:
        self._db = db

    def load(self) -> AppSettings:
        stored = self._db.all_settings()
        kwargs = {}
        for f in dataclasses.fields(AppSettings):
            key = self.PREFIX + f.name
            if key in stored:
                kwargs[f.name] = stored[key]
        return AppSettings(**kwargs).validated()

    def save(self, settings: AppSettings) -> AppSettings:
        settings = settings.validated()
        for f in dataclasses.fields(AppSettings):
            self._db.set_setting(self.PREFIX + f.name, getattr(settings, f.name))
        return settings
