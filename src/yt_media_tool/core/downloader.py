"""下載引擎：以 yt-dlp Python API 執行單一任務（於工作執行緒中呼叫）。

安全設計：
- 每個任務使用專屬的暫存資料夾（<下載資料夾>/.ytmt_tmp/task_<id>_<亂數>），
  所有 .part、分段及合併前的檔案都在其中；取消或失敗時只刪除該資料夾，
  不會動到其他任務或使用者原有檔案。
- yt-dlp 的輸出目錄（home）就是該暫存資料夾，yt-dlp 完全不接觸下載資料夾中的既有檔案。
- 成品先以 FFprobe 驗證，再以「不覆蓋」方式移到下載資料夾；同名時自動編號
  （FileNameReserver 同時避免並行任務搶到相同檔名）。
- 只有在下載、FFmpeg 後處理、驗證與移動全部完成後才回傳成功。
- 所有參數以 dict 傳給 yt-dlp API，不組合任何 shell 指令。
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadCancelled as _YtdlpDownloadCancelled

from yt_media_tool.core import converter
from yt_media_tool.core.converter import JsRuntimeInfo, MediaInfo, ToolInfo
from yt_media_tool.core.cookies import CookieConfig, ydl_cookie_options
from yt_media_tool.core.errors import DownloadCancelledError, InsufficientDiskSpaceError
from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus
from yt_media_tool.core.title_cleanup import clean_title
from yt_media_tool.utils.paths import FileNameReserver, sanitize_filename

log = logging.getLogger(__name__)

TEMP_ROOT_NAME = ".ytmt_tmp"
MIN_FREE_BYTES = 200 * 1024 * 1024  # 無法預估檔案大小時，至少需保留的空間
DOWNLOAD_PROGRESS_SHARE = 95.0  # 下載階段佔整體進度的比例，其餘為後處理

POSTPROCESSOR_STAGES = {
    "Merger": "影音合併中",
    "ExtractAudio": "MP3 轉檔中",
    "VideoRemuxer": "轉換封裝格式中",
    "VideoConvertor": "影片轉檔中",
    "FixupM4a": "修正音訊容器中",
    "FixupM3u8": "修正串流容器中",
    "FixupStretched": "修正影像比例中",
    "FixupDuplicateMoov": "修正影片結構中",
    "FixupTimestamp": "修正時間戳記中",
    "MoveFiles": "移動檔案中",
    "Metadata": "寫入歌曲資訊中",
    "EmbedThumbnail": "嵌入封面中",
}
# 不改變任務狀態的後處理（下載前就會執行，例如轉換縮圖格式）
SILENT_POSTPROCESSORS = {"MoveFiles", "ThumbnailsConvertor", "SubtitlesConvertor"}


class CancelToken:
    """執行緒安全的取消旗標；reason 為 "user"（使用者取消）或 "shutdown"（程式關閉）。"""

    def __init__(self) -> None:
        self._event = threading.Event()
        self.reason = "user"

    def cancel(self, reason: str = "user") -> None:
        if not self._event.is_set():
            self.reason = reason
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise DownloadCancelledError(self.reason)


class _HookCancelled(_YtdlpDownloadCancelled):
    """在 yt-dlp hook 中拋出，yt-dlp 會將其視為取消並向上傳遞。"""

    msg = "Download cancelled by user"


@dataclass
class ProgressUpdate:
    status: TaskStatus
    progress: float | None = None
    speed: float | None = None
    eta: int | None = None
    stage: str = ""
    title: str | None = None
    actual_quality: str | None = None


ProgressCallback = Callable[[ProgressUpdate], None]


@dataclass
class DownloadResult:
    output_path: Path
    title: str
    actual_quality: str
    media_info: MediaInfo | None = None


@dataclass(frozen=True)
class DownloadPreferences:
    """每個任務開始時讀取一次的下載偏好設定。"""

    embed_metadata: bool = False  # 寫入歌名、演出者並嵌入封面
    rate_limit: int | None = None  # 每個任務的速度上限（bytes/s）；None 表示不限制
    subtitles: bool = False  # MP4 一併下載字幕（.srt）
    clean_titles: bool = False  # MP3 自動整理歌名（檔名「演出者 - 歌名」，並寫入歌曲資訊）


@dataclass(frozen=True)
class SubtitleChoice:
    lang: str
    automatic: bool  # True：YouTube 自動產生的字幕
    label: str


# 字幕語言優先順序：繁體中文 → 中文 → 簡體中文 → 英文
SUBTITLE_PREFERENCES: list[tuple[str, str]] = [
    ("zh-Hant", "繁體中文"), ("zh-TW", "繁體中文"), ("zh-HK", "繁體中文"), ("zh", "中文"),
    ("zh-Hans", "簡體中文"), ("zh-CN", "簡體中文"), ("en", "英文"), ("en-US", "英文"), ("en-GB", "英文"),
]


def choose_subtitle(info: dict) -> SubtitleChoice | None:
    """選一種字幕：優先使用上傳者提供的字幕（依語言優先順序，其次任何語言），
    沒有時才使用 YouTube 自動產生的字幕（依語言優先順序）。"""
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if v and k != "live_chat"}
    automatic = {k: v for k, v in (info.get("automatic_captions") or {}).items() if v}
    for lang, label in SUBTITLE_PREFERENCES:
        if lang in manual:
            return SubtitleChoice(lang, False, label)
    if manual:
        lang = next(iter(manual))
        return SubtitleChoice(lang, False, lang)
    for lang, label in SUBTITLE_PREFERENCES:
        if lang in automatic:
            return SubtitleChoice(lang, True, f"{label}（自動產生）")
    return None


@dataclass
class PlaylistEntry:
    url: str
    title: str
    video_id: str = ""
    duration: float | None = None  # 秒；播放清單未提供時為 None


@dataclass
class PlaylistInfo:
    title: str
    entries: list[PlaylistEntry] = field(default_factory=list)
    truncated: bool = False


class _YdlLogger:
    """把 yt-dlp 的輸出導向 logging，避免在無主控台的 EXE 中寫入 None stdout。"""

    def __init__(self, task_id: int | None) -> None:
        self._prefix = f"[task {task_id}] " if task_id is not None else ""
        self.warnings: list[str] = []

    def debug(self, msg: str) -> None:
        if not msg.startswith("[debug] "):
            log.debug("%s%s", self._prefix, msg)

    def info(self, msg: str) -> None:
        log.info("%s%s", self._prefix, msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)
        log.warning("%s%s", self._prefix, msg)

    def error(self, msg: str) -> None:
        log.error("%s%s", self._prefix, msg)


class _ProgressAggregator:
    """整合影片、音訊分開下載的多段進度為單一百分比（各分段依序下載）。"""

    def __init__(self, expected_sizes: list[int | None]) -> None:
        self.expected = list(expected_sizes) or [None]
        self.parts: dict[str, tuple[float, float | None]] = {}
        self.order: list[str] = []

    def update(self, key: str, downloaded: float, total: float | None) -> float:
        if key not in self.parts:
            self.order.append(key)
        self.parts[key] = (downloaded, total)
        index = self.order.index(key)
        n = max(len(self.expected), len(self.order))
        sizes = [self.expected[i] if i < len(self.expected) else None for i in range(n)]
        for i, k in enumerate(self.order):
            if self.parts[k][1]:
                sizes[i] = self.parts[k][1]
        if all(sizes):
            done = sum(sizes[i] for i in range(index))  # 先前的分段已完成
            done += min(downloaded, sizes[index])
            pct = done / sum(sizes) * 100
        else:
            fraction = min(downloaded / total, 1.0) if total else 0.0
            pct = (index + fraction) / n * 100
        return max(0.0, min(100.0, pct))


def _escape_outtmpl(text: str) -> str:
    return text.replace("%", "%%")


def _remove_tree(path: Path, attempts: int = 5) -> None:
    """刪除暫存資料夾；Windows 上檔案可能短暫被鎖定，因此重試數次。"""
    for i in range(attempts):
        if not path.exists():
            return
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if i == attempts - 1:
                log.warning("無法完全刪除暫存資料夾 %s", path, exc_info=True)
            time.sleep(0.3 * (i + 1))


class Downloader:
    def __init__(
        self,
        tools_provider: Callable[[], ToolInfo],
        js_runtime_provider: Callable[[], JsRuntimeInfo] | None = None,
        reserver: FileNameReserver | None = None,
        ydl_factory: Callable[[dict[str, Any]], Any] = yt_dlp.YoutubeDL,
        extra_options: dict[str, Any] | None = None,
        probe: Callable[[Path, MediaFormat, Path], MediaInfo] = converter.verify_output,
        cookies_provider: Callable[[], CookieConfig] | None = None,
        preferences_provider: Callable[[], DownloadPreferences] | None = None,
    ) -> None:
        self._tools_provider = tools_provider
        self._js_runtime_provider = js_runtime_provider or converter.find_js_runtime
        self.reserver = reserver or FileNameReserver()
        self._ydl_factory = ydl_factory
        self._extra_options = dict(extra_options or {})
        self._probe = probe
        self._cookies_provider = cookies_provider or CookieConfig
        self._preferences_provider = preferences_provider or DownloadPreferences

    # ---- 共用設定 ----
    def _base_options(self, logger: _YdlLogger, tools: ToolInfo | None,
                      cookie_options: dict[str, Any] | None = None) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": False,
            "noprogress": True,
            "logger": logger,
            "noplaylist": True,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "continuedl": True,
            "overwrites": False,
            "windowsfilenames": True,
            "consoletitle": False,
        }
        if tools and tools.location:
            opts["ffmpeg_location"] = tools.location
        opts.update(self._js_runtime_provider().ydl_option())
        opts.update(cookie_options or {})
        opts.update(self._extra_options)
        return opts

    # ---- 播放清單展開 ----
    def extract_playlist(self, url: str, limit: int = 500) -> PlaylistInfo:
        logger = _YdlLogger(None)
        # cookies.txt 副本放在用完即刪的暫存資料夾
        with tempfile.TemporaryDirectory(prefix="ytmt_playlist_") as work_dir:
            cookie_options = ydl_cookie_options(self._cookies_provider(), Path(work_dir))
            opts = self._base_options(logger, None, cookie_options)
            opts.update({"noplaylist": False, "extract_flat": "in_playlist", "playlistend": limit + 1})
            with self._ydl_factory(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        entries_raw = list(info.get("entries") or []) if info else []
        entries: list[PlaylistEntry] = []
        for entry in entries_raw:
            if not entry:
                continue
            video_id = entry.get("id")
            entry_url = entry.get("url") or entry.get("webpage_url")
            if video_id and (not entry_url or not str(entry_url).startswith("http")):
                entry_url = f"https://www.youtube.com/watch?v={video_id}"
            if entry_url:
                duration = entry.get("duration")
                entries.append(PlaylistEntry(str(entry_url), entry.get("title") or "", str(video_id or ""),
                                             float(duration) if isinstance(duration, (int, float)) else None))
        truncated = len(entries) > limit
        return PlaylistInfo(title=(info or {}).get("title") or "", entries=entries[:limit], truncated=truncated)

    # ---- 單一任務下載 ----
    def download(self, task: DownloadTask, token: CancelToken, on_progress: ProgressCallback) -> DownloadResult:
        tools = self._tools_provider().require()
        token.raise_if_cancelled()

        output_dir = Path(task.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._check_writable(output_dir)

        temp_root = output_dir / TEMP_ROOT_NAME
        temp_dir = temp_root / f"task_{task.id}_{uuid.uuid4().hex[:8]}"
        reserved: Path | None = None
        logger = _YdlLogger(task.id)
        success = False
        try:
            _make_task_dir(temp_dir)
            _hide_on_windows(temp_root)
            on_progress(ProgressUpdate(TaskStatus.DOWNLOADING, progress=0.0, stage="取得影片資訊中"))
            # cookies.txt 副本放在本任務暫存資料夾，任務結束時隨資料夾刪除
            cookie_options = ydl_cookie_options(self._cookies_provider(), temp_dir)
            prefs = self._preferences_provider()

            info_opts = self._base_options(logger, tools, cookie_options)
            info_opts["format"] = converter.format_selector(task.media_format, task.quality)
            if task.media_format is MediaFormat.MP4:
                info_opts["merge_output_format"] = "mp4"
            with self._ydl_factory(info_opts) as ydl:
                info = ydl.extract_info(task.url, download=False)
            token.raise_if_cancelled()
            if not info:
                raise RuntimeError("無法取得影片資訊")
            if info.get("_type") == "playlist":
                raise RuntimeError("此任務為播放清單，請重新貼上播放清單網址加入佇列")

            title = str(info.get("title") or info.get("id") or "untitled")
            file_stem = title
            if prefs.clean_titles and task.media_format is MediaFormat.MP3:
                cleaned = clean_title(info)
                if cleaned is not None:
                    # 歌曲資訊（FFmpegMetadata 優先使用 track / artist）與檔名都用整理後的名稱；佇列仍顯示原標題
                    info["track"] = cleaned.track
                    if cleaned.artist:
                        info["artist"] = cleaned.artist
                        info["artists"] = [cleaned.artist]
                    file_stem = cleaned.display
            actual = describe_selection(info, task.media_format, task.quality)
            on_progress(ProgressUpdate(TaskStatus.DOWNLOADING, progress=0.0, stage="下載中",
                                       title=title, actual_quality=actual))
            self._check_disk_space(info, task, output_dir)

            produced, source_kbps = self._run_download(task, info, tools, logger, token, on_progress, temp_dir,
                                                       cookie_options, prefs)
            token.raise_if_cancelled()
            if task.media_format is MediaFormat.MP3 and source_kbps and "未知" in actual:
                actual = describe_mp3(task.quality, source_kbps)

            # 先在暫存資料夾中驗證，確認無誤才移到下載資料夾
            on_progress(ProgressUpdate(TaskStatus.PROCESSING, progress=98.0, stage="檢查輸出檔案中"))
            media_info = self._probe(produced, task.media_format, tools.ffprobe)  # type: ignore[arg-type]
            token.raise_if_cancelled()

            subtitle: tuple[Path, SubtitleChoice] | None = None
            subtitle_note = ""
            if prefs.subtitles and task.media_format is MediaFormat.MP4:
                on_progress(ProgressUpdate(TaskStatus.PROCESSING, progress=98.5, stage="下載字幕中"))
                subtitle, subtitle_note = self._download_subtitle(info, tools, logger, temp_dir, cookie_options)
                token.raise_if_cancelled()

            on_progress(ProgressUpdate(TaskStatus.PROCESSING, progress=99.0, stage="移動檔案中"))
            ext = "mp4" if task.media_format is MediaFormat.MP4 else "mp3"
            stem = sanitize_filename(file_stem)
            while True:
                reserved = self.reserver.reserve(output_dir, stem, ext)
                if move_no_overwrite(produced, reserved):
                    break
                # 保留後到移動前被其他程式建立了同名檔案：改用下一個編號
                self.reserver.release(reserved)
                reserved = None
            final_path = reserved
            if subtitle is not None:
                subtitle_note = _move_subtitle(subtitle[0], final_path, subtitle[1])
            actual = describe_result(media_info, task.media_format, task.quality, actual) + subtitle_note
            success = True
            return DownloadResult(final_path, title, actual, media_info)
        except _YtdlpDownloadCancelled as exc:
            raise DownloadCancelledError(token.reason) from exc
        except yt_dlp.utils.DownloadError as exc:
            if token.cancelled:
                raise DownloadCancelledError(token.reason) from exc
            raise
        finally:
            _remove_tree(temp_dir)
            try:
                temp_root.rmdir()  # 只有在沒有其他任務使用時（空資料夾）才會成功
            except OSError:
                pass
            if reserved is not None:
                self.reserver.release(reserved)
            if not success:
                log.info("任務 %s 未成功，已清除暫存資料夾 %s", task.id, temp_dir)

    def _run_download(self, task, info, tools, logger, token, on_progress, temp_dir: Path,
                      cookie_options: dict[str, Any] | None = None,
                      prefs: DownloadPreferences | None = None) -> tuple[Path, float | None]:
        """在暫存資料夾內完成下載與 FFmpeg 後處理，回傳（暫存資料夾中的成品路徑, 原始音訊 kbps）。

        yt-dlp 的 home 路徑設為任務專屬暫存資料夾，因此 yt-dlp 不會讀取、覆蓋或刪除
        下載資料夾中的任何既有檔案（例如誤把同名的既有檔案當成「已下載」再刪除）。
        """
        requested = info.get("requested_formats") or [info]
        aggregator = _ProgressAggregator([f.get("filesize") or f.get("filesize_approx") for f in requested])
        last_emit = [0.0]
        source_audio: dict[str, float | None] = {"kbps": None}

        def progress_hook(d: dict) -> None:
            if token.cancelled:
                raise _HookCancelled()
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                key = str((d.get("info_dict") or {}).get("format_id") or d.get("filename") or "0")
                pct = aggregator.update(key, float(d.get("downloaded_bytes") or 0), total)
                now = time.monotonic()
                if now - last_emit[0] >= 0.2:
                    last_emit[0] = now
                    eta = d.get("eta")
                    on_progress(ProgressUpdate(
                        TaskStatus.DOWNLOADING, progress=pct * DOWNLOAD_PROGRESS_SHARE / 100,
                        speed=d.get("speed"), eta=int(eta) if eta is not None else None, stage="下載中"))
            elif status == "error":
                log.warning("任務 %s 下載分段發生錯誤", task.id)

        def postprocessor_hook(d: dict) -> None:
            if token.cancelled:
                raise _HookCancelled()
            name = d.get("postprocessor") or ""
            if name == "ExtractAudio" and d.get("status") == "started" and source_audio["kbps"] is None:
                source_audio["kbps"] = self._source_audio_kbps(d.get("info_dict") or {}, tools)
            if d.get("status") == "started" and name not in SILENT_POSTPROCESSORS:
                stage = POSTPROCESSOR_STAGES.get(name, f"後處理中（{name}）")
                on_progress(ProgressUpdate(TaskStatus.PROCESSING, progress=DOWNLOAD_PROGRESS_SHARE,
                                           speed=None, eta=None, stage=stage))

        prefs = prefs or DownloadPreferences()
        embed_metadata = prefs.embed_metadata
        opts = self._base_options(logger, tools, cookie_options)
        if prefs.rate_limit:
            opts["ratelimit"] = prefs.rate_limit
        opts.update({
            "format": converter.format_selector(task.media_format, task.quality),
            # 縮圖也寫在暫存資料夾（media.jpg），嵌入後由 yt-dlp 刪除，殘留的會隨暫存資料夾清除
            "writethumbnail": embed_metadata,
            # 固定的 ASCII 暫存檔名：避免標題中的特殊字元與過長路徑問題
            "outtmpl": {"default": "media.%(ext)s"},
            "paths": {"home": str(temp_dir)},
            "postprocessors": converter.postprocessors(task.media_format, task.quality, embed_metadata),
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
        })
        if task.media_format is MediaFormat.MP4:
            opts["merge_output_format"] = "mp4"

        with self._ydl_factory(opts) as ydl:
            result = ydl.process_ie_result(info, download=True)
        token.raise_if_cancelled()

        ext = ".mp4" if task.media_format is MediaFormat.MP4 else ".mp3"
        candidates = [Path(item.get("filepath") or "") for item in (result or {}).get("requested_downloads") or []]
        candidates.append(temp_dir / f"media{ext}")
        temp_resolved = temp_dir.resolve()
        for path in candidates:
            if path.suffix.lower() == ext and path.is_file() and path.resolve().parent == temp_resolved:
                return path, source_audio["kbps"]
        raise RuntimeError("下載程序結束但找不到輸出檔案")

    def _download_subtitle(self, info: dict, tools: ToolInfo, logger, temp_dir: Path,
                           cookie_options: dict[str, Any] | None) -> tuple[tuple[Path, SubtitleChoice] | None, str]:
        """另外下載一種字幕並轉成 SRT（在暫存資料夾中）。字幕是附加項目：失敗只回傳附註，不影響影片。"""
        choice = choose_subtitle(info)
        if choice is None:
            return None, "；此影片沒有可用字幕"
        opts = self._base_options(logger, tools, cookie_options)
        opts.update({
            "skip_download": True,
            "writesubtitles": not choice.automatic,
            "writeautomaticsub": choice.automatic,
            "subtitleslangs": [choice.lang],
            "subtitlesformat": "srt/vtt/best",
            "outtmpl": {"default": "media.%(ext)s"},
            "paths": {"home": str(temp_dir)},
            "postprocessors": [{"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"}],
        })
        try:
            with self._ydl_factory(opts) as ydl:
                ydl.process_ie_result(dict(info), download=True)
        except Exception:  # 字幕失敗不可讓整個任務失敗
            log.warning("字幕下載失敗（%s）", choice.lang, exc_info=True)
            return None, "；字幕下載失敗（影片不受影響）"
        produced = temp_dir / f"media.{choice.lang}.srt"
        if not produced.is_file():
            return None, "；字幕下載失敗（影片不受影響）"
        return (produced, choice), ""

    @staticmethod
    def _source_audio_kbps(info: dict, tools: ToolInfo) -> float | None:
        """MP3 轉檔前以 FFprobe 量測原始音訊位元率（yt-dlp 未提供 abr 時使用）。"""
        abr = info.get("abr")
        if abr:
            return float(abr)
        source = info.get("filepath")
        if not source or tools.ffprobe is None:
            return None
        try:
            bitrate = converter.probe_media(Path(source), tools.ffprobe).audio_bitrate
        except converter.MediaProbeError:
            return None
        return bitrate / 1000 if bitrate else None

    @staticmethod
    def _check_writable(directory: Path) -> None:
        probe = directory / f".ytmt_write_test_{uuid.uuid4().hex[:8]}"
        try:
            with open(probe, "wb") as fh:
                fh.write(b"0")
        finally:
            _safe_unlink(probe)

    @staticmethod
    def _check_disk_space(info: dict, task: DownloadTask, directory: Path) -> None:
        requested = info.get("requested_formats") or [info]
        sizes = [f.get("filesize") or f.get("filesize_approx") for f in requested]
        free = shutil.disk_usage(directory).free
        if all(sizes):
            size = sum(sizes)  # type: ignore[arg-type]
            if task.media_format is MediaFormat.MP3:
                duration = float(info.get("duration") or 0)
                needed = size + int(duration * int(task.quality) * 1000 / 8)
            else:
                needed = size * 2  # 合併時暫存檔與成品會同時存在
            needed = int(needed * 1.05) + 20 * 1024 * 1024
        else:
            needed = MIN_FREE_BYTES
        if free < needed:
            raise InsufficientDiskSpaceError(needed, free, str(directory))


def describe_selection(info: dict, media_format: MediaFormat, quality: str) -> str:
    """依 yt-dlp 選定的格式說明實際可取得的品質，原始素材不足時明確標示；
    素材有更高解析度時附上最高解析度，讓使用者知道還有更高畫質可選。"""
    formats = info.get("formats") or []
    requested = info.get("requested_formats") or [info]
    if media_format is MediaFormat.MP4:
        heights = sorted({int(f["height"]) for f in formats
                          if f.get("height") and f.get("vcodec") not in (None, "none")})
        chosen = next((f.get("height") for f in requested if f.get("height")), None) or info.get("height")
        if not chosen:
            return "解析度未知"
        text = f"{int(chosen)}p"
        available = "、".join(f"{h}p" for h in heights) if heights else "未知"
        if quality != "best" and int(chosen) < int(quality):
            text += f"（原始素材無 {quality}p，可用解析度：{available}）"
        elif heights and heights[-1] > int(chosen):
            text += f"（最高 {heights[-1]}p，可用解析度：{available}）"
        return text
    abr = next((f.get("abr") for f in requested if f.get("abr")), None) or info.get("abr")
    return describe_mp3(quality, abr)


def describe_mp3(quality: str, source_kbps: float | None) -> str:
    if not source_kbps:
        return f"MP3 {quality} kbps（原始音源位元率未知）"
    abr = round(float(source_kbps))
    text = f"MP3 {quality} kbps（原始音源約 {abr} kbps"
    if int(quality) > abr:
        text += "，輸出位元率高於原始音源，實際音質不會提升"
    return text + "）"


def describe_result(media: MediaInfo, media_format: MediaFormat, quality: str, selection: str) -> str:
    """以 FFprobe 實測結果更新品質說明，保留選擇格式時的附註（原始素材不足、最高解析度）。"""
    if media_format is MediaFormat.MP4 and media.height:
        codecs = "/".join(c for c in (media.video_codec, media.audio_codec) if c)
        text = f"{media.height}p" + (f" {codecs}" if codecs else "")
        if "（" in selection:
            text += selection[selection.index("（"):]
        elif quality != "best" and media.height < int(quality):
            text += f"（原始素材無 {quality}p）"
        return text
    return selection


def _make_task_dir(path: Path, attempts: int = 15) -> None:
    """建立任務暫存資料夾。

    Windows 上剛被其他任務刪除的 .ytmt_tmp 若仍被防毒軟體或索引服務開啟，會暫時處於「等待刪除」狀態，
    此時在其中建立資料夾會得到「存取被拒」；稍候重試即可。
    """
    for attempt in range(attempts):
        try:
            path.mkdir(parents=True, exist_ok=False)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2)


def _move_subtitle(source: Path, video: Path, choice: SubtitleChoice) -> str:
    """把字幕移到影片旁（同檔名 .srt，播放器會自動載入）；同名檔已存在時改用「檔名.語言.srt」，仍存在則不儲存。"""
    for target in (video.with_suffix(".srt"), video.with_name(f"{video.stem}.{choice.lang}.srt")):
        if move_no_overwrite(source, target):
            return f"；字幕：{choice.label}"
    return "；字幕檔名已被使用，未儲存字幕"


def move_no_overwrite(src: Path, dst: Path) -> bool:
    """將 src 移到 dst；dst 已存在時不覆蓋並回傳 False。src 與 dst 位於同一磁碟區。"""
    if os.name == "nt":
        try:
            os.rename(src, dst)  # Windows 上目的檔存在時會拋出 FileExistsError
        except FileExistsError:
            return False
        return True
    try:
        os.link(src, dst)  # POSIX：link 在目的檔存在時失敗，不會覆蓋
    except FileExistsError:
        return False
    except OSError:
        # 不支援硬連結的檔案系統（例如 exFAT）
        if dst.exists():
            return False
        os.rename(src, dst)
        return True
    src.unlink()
    return True


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        log.warning("無法刪除檔案 %s", path, exc_info=True)


def _hide_on_windows(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)  # type: ignore[attr-defined]
    except Exception:  # 隱藏屬性僅為美觀，失敗不影響功能
        log.debug("無法設定隱藏屬性 %s", path, exc_info=True)
