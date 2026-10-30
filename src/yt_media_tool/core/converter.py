"""FFmpeg / FFprobe 與 JavaScript 執行環境的偵測、媒體檢查及 yt-dlp 後處理設定。

尋找順序（不假設使用者已設定 PATH）：
1. 使用者在設定中指定的資料夾
2. 環境變數 YTMT_FFMPEG_DIR
3. 隨附於程式的資料夾（打包後：_internal/ffmpeg；開發時：vendor/ffmpeg/bin）
4. EXE 同層的 ffmpeg 資料夾
5. 系統 PATH

所有外部程式皆以參數清單呼叫，不經由 shell。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from yt_media_tool.core.task_models import MediaFormat
from yt_media_tool.utils import paths

log = logging.getLogger(__name__)

_EXE = ".exe" if sys.platform.startswith("win") else ""
# Windows 視窗程式呼叫主控台程式時不要跳出黑色視窗
_CREATIONFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)

FFMPEG_INSTALL_GUIDE = (
    "找不到 FFmpeg / FFprobe，無法合併影音或轉換 MP3。\n\n"
    "解決方式（擇一）：\n"
    "1. 使用隨附 FFmpeg 的完整發行版本。\n"
    "2. 自行下載 Windows 版 FFmpeg（例如 https://www.gyan.dev/ffmpeg/builds/ 或 "
    "https://github.com/BtbN/FFmpeg-Builds/releases ），解壓縮後在「設定 → FFmpeg 資料夾」"
    "指定含有 ffmpeg.exe 與 ffprobe.exe 的 bin 資料夾。\n"
    "3. 使用 winget 安裝：winget install --id Gyan.FFmpeg -e，安裝後重新啟動本程式。"
)

JS_RUNTIME_GUIDE = (
    "未偵測到 JavaScript 執行環境（Deno）。yt-dlp 需要它來取得完整的 YouTube 格式清單，"
    "缺少時部分影片可能只剩低畫質或無法下載。\n"
    "請使用隨附 Deno 的發行版本，或執行：winget install --id DenoLand.Deno -e"
)


class FFmpegNotFoundError(RuntimeError):
    def __init__(self, missing: list[str] | None = None) -> None:
        self.missing = missing or ["ffmpeg", "ffprobe"]
        super().__init__(FFMPEG_INSTALL_GUIDE)


@dataclass
class ToolInfo:
    ffmpeg: Path | None = None
    ffprobe: Path | None = None
    ffmpeg_version: str = ""
    source: str = ""
    searched: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.ffmpeg is not None and self.ffprobe is not None

    @property
    def missing(self) -> list[str]:
        return [name for name, p in (("ffmpeg", self.ffmpeg), ("ffprobe", self.ffprobe)) if p is None]

    @property
    def location(self) -> str | None:
        """傳給 yt-dlp 的 ffmpeg_location（資料夾）。"""
        return str(self.ffmpeg.parent) if self.ffmpeg else None

    def require(self) -> ToolInfo:
        if not self.available:
            raise FFmpegNotFoundError(self.missing)
        return self


def candidate_ffmpeg_dirs(custom_dir: str | os.PathLike | None = None) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    if custom_dir:
        candidates.append(("設定指定", Path(custom_dir)))
    env_dir = os.environ.get("YTMT_FFMPEG_DIR")
    if env_dir:
        candidates.append(("環境變數 YTMT_FFMPEG_DIR", Path(env_dir)))
    bundle = paths.bundle_dir()
    candidates += [
        ("隨附", bundle / "ffmpeg"),
        ("隨附", bundle / "ffmpeg" / "bin"),
        ("隨附", bundle / "vendor" / "ffmpeg" / "bin"),
        ("程式資料夾", paths.executable_dir() / "ffmpeg"),
    ]
    return candidates


def _version_of(ffmpeg: Path) -> str:
    try:
        out = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-version"], capture_output=True, text=True,
            timeout=10, creationflags=_CREATIONFLAGS, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    first = (out.stdout or "").splitlines()[:1]
    match = re.search(r"ffmpeg version (\S+)", first[0]) if first else None
    return match.group(1) if match else ""


def find_ffmpeg(custom_dir: str | os.PathLike | None = None, use_path: bool = True) -> ToolInfo:
    """偵測 FFmpeg 與 FFprobe；兩者需在同一資料夾（yt-dlp 的 ffmpeg_location 以資料夾指定）。"""
    info = ToolInfo()
    for source, directory in candidate_ffmpeg_dirs(custom_dir):
        info.searched.append(str(directory))
        ffmpeg, ffprobe = directory / f"ffmpeg{_EXE}", directory / f"ffprobe{_EXE}"
        if ffmpeg.is_file() and ffprobe.is_file():
            info.ffmpeg, info.ffprobe, info.source = ffmpeg, ffprobe, source
            break
    if not info.available and use_path:
        info.searched.append("PATH")
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if ffmpeg and ffprobe and Path(ffmpeg).parent == Path(ffprobe).parent:
            info.ffmpeg, info.ffprobe, info.source = Path(ffmpeg), Path(ffprobe), "系統 PATH"
    if info.ffmpeg:
        info.ffmpeg_version = _version_of(info.ffmpeg)
    return info


@dataclass
class JsRuntimeInfo:
    name: str | None = None
    path: Path | None = None
    source: str = ""

    @property
    def available(self) -> bool:
        return self.name is not None

    def ydl_option(self) -> dict:
        if not self.available:
            return {}
        return {"js_runtimes": {self.name: {"path": str(self.path)} if self.path else {}}}


def find_js_runtime() -> JsRuntimeInfo:
    """yt-dlp 自 2025.11 起需要 JS 執行環境處理 YouTube；優先使用隨附的 Deno。"""
    bundle = paths.bundle_dir()
    for directory in (bundle / "deno", paths.executable_dir() / "deno"):
        exe = directory / f"deno{_EXE}"
        if exe.is_file():
            return JsRuntimeInfo("deno", exe, "隨附")
    try:  # 開發環境：pip 安裝的 deno 套件
        import deno  # type: ignore[import-not-found]

        exe = Path(deno.find_deno_bin())
        if exe.is_file():
            return JsRuntimeInfo("deno", exe, "deno 套件")
    except Exception:  # 套件不存在或損壞時改用 PATH
        log.debug("deno 套件不可用", exc_info=True)
    for name in ("deno", "node", "bun"):
        found = shutil.which(name)
        if found:
            return JsRuntimeInfo(name, Path(found), "系統 PATH")
    return JsRuntimeInfo()


# ---- 媒體檢查 ----
@dataclass
class MediaInfo:
    duration: float | None
    has_video: bool
    has_audio: bool
    width: int | None = None
    height: int | None = None
    video_codec: str = ""
    audio_codec: str = ""
    audio_bitrate: int | None = None  # bps
    format_name: str = ""

    def describe(self) -> str:
        parts = []
        if self.has_video and self.height:
            parts.append(f"{self.height}p {self.video_codec}".strip())
        if self.has_audio:
            br = f" {round(self.audio_bitrate / 1000)} kbps" if self.audio_bitrate else ""
            parts.append(f"{self.audio_codec}{br}".strip())
        return "，".join(parts)


class MediaProbeError(RuntimeError):
    pass


def probe_media(path: Path, ffprobe: Path) -> MediaInfo:
    cmd = [str(ffprobe), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, creationflags=_CREATIONFLAGS,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MediaProbeError(f"無法執行 FFprobe：{exc}") from exc
    if proc.returncode != 0:
        raise MediaProbeError(f"FFprobe 無法讀取檔案：{(proc.stderr or '').strip()[:300]}")
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaProbeError("FFprobe 輸出格式錯誤") from exc
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def _num(value, cast):
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None

    return MediaInfo(
        duration=_num(fmt.get("duration"), float),
        has_video=video is not None,
        has_audio=audio is not None,
        width=_num(video.get("width"), int) if video else None,
        height=_num(video.get("height"), int) if video else None,
        video_codec=(video or {}).get("codec_name", ""),
        audio_codec=(audio or {}).get("codec_name", ""),
        audio_bitrate=_num((audio or {}).get("bit_rate"), int) or (
            _num(fmt.get("bit_rate"), int) if audio and not video else None),
        format_name=fmt.get("format_name", ""),
    )


def verify_output(path: Path, media_format: MediaFormat, ffprobe: Path) -> MediaInfo:
    """確認輸出檔確實存在且包含預期的串流，才可將任務標記為完成。"""
    if not path.is_file() or path.stat().st_size == 0:
        raise MediaProbeError(f"輸出檔案不存在或大小為 0：{path}")
    info = probe_media(path, ffprobe)
    if media_format is MediaFormat.MP3:
        if not info.has_audio:
            raise MediaProbeError("輸出的 MP3 檔案中沒有音訊串流")
    elif not info.has_video:
        raise MediaProbeError("輸出的 MP4 檔案中沒有影像串流")
    return info


# ---- yt-dlp 格式與後處理設定 ----
def format_selector(media_format: MediaFormat, quality: str) -> str:
    """回傳 yt-dlp 的格式選擇字串。

    MP4 優先挑選 H.264 + AAC，以確保 Windows 內建播放器可直接播放；
    沒有符合解析度上限的格式時退回較低者，最後才使用任何可用格式。
    """
    if media_format is MediaFormat.MP3:
        return "bestaudio/best"
    if quality == "best":
        return "bv*+ba[ext=m4a]/bv*+ba/b"
    h = int(quality)
    return (
        f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/"
        f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
        f"bv*[height<={h}]+ba/"
        f"b[height<={h}]/"
        "bv*+ba/b"
    )


def postprocessors(media_format: MediaFormat, quality: str) -> list[dict]:
    if media_format is MediaFormat.MP3:
        return [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}]
    # 若下載到的是單一非 MP4 檔案，轉封裝為 MP4（不重新編碼）
    return [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
