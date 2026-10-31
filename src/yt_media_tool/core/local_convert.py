"""本機影音檔轉 MP3（使用隨附的 FFmpeg）。

與下載相同的檔案安全原則：
- 來源檔只讀取，絕不修改或刪除。
- FFmpeg 先寫到輸出資料夾中的隱藏暫存檔，經 FFprobe 確認有音訊後，才以「不覆蓋」方式改成正式檔名；
  同名檔案已存在時自動加上「 (1)」「 (2)」…。
- 取消或失敗時只刪除自己的暫存檔。
- 以參數清單呼叫 FFmpeg，不經過 shell。
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from yt_media_tool.core import converter
from yt_media_tool.core.converter import MediaProbeError, ToolInfo
from yt_media_tool.core.downloader import move_no_overwrite
from yt_media_tool.utils.paths import FileNameReserver

log = logging.getLogger(__name__)

# 檔案選擇對話框與拖放接受的副檔名（實際能否轉換以 FFprobe 判斷是否有音訊為準）
MEDIA_SUFFIXES = (
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".flv", ".m4v", ".ts", ".3gp",
    ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma", ".mp3",
)
BITRATES = ("128", "192", "320")

_TIME = re.compile(r"^out_time_(?:us|ms)=(\d+)$")


class ConvertCancelledError(Exception):
    pass


class ConvertError(Exception):
    """轉檔失敗；訊息為顯示給使用者的中文說明。"""


@dataclass
class ConvertResult:
    source: Path
    output: Path
    source_kbps: float | None  # 原始音訊位元率（可得時）


def is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_SUFFIXES


def convert_to_mp3(source: Path, output_dir: Path, bitrate: str, tools: ToolInfo,
                   on_progress: Callable[[float], None] | None = None,
                   cancel: threading.Event | None = None,
                   reserver: FileNameReserver | None = None) -> ConvertResult:
    """把 source 的第一條音軌轉成 MP3，存到 output_dir（檔名同來源，副檔名 .mp3）。"""
    if bitrate not in BITRATES:
        raise ValueError(f"不支援的位元率：{bitrate}")
    tools = tools.require()
    source = Path(source)
    if not source.is_file():
        raise ConvertError(f"找不到檔案：{source}")
    try:
        info = converter.probe_media(source, tools.ffprobe)  # type: ignore[arg-type]
    except MediaProbeError as exc:
        raise ConvertError(f"無法讀取這個檔案（可能不是影音檔或已損毀）：{exc}") from exc
    if not info.has_audio:
        raise ConvertError("這個檔案沒有聲音，無法轉成 MP3。")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    temp = output_dir / f".ytmt_convert_{uuid.uuid4().hex[:8]}.mp3"
    cmd = [
        str(tools.ffmpeg), "-hide_banner", "-nostdin", "-loglevel", "error", "-n",
        "-i", str(source),
        "-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-b:a", f"{bitrate}k",
        "-map_metadata", "0", "-id3v2_version", "3",
        "-progress", "pipe:1", "-nostats",
        str(temp),
    ]
    reserver = reserver or FileNameReserver()
    final: Path | None = None
    try:
        _run_ffmpeg(cmd, info.duration, on_progress, cancel)
        try:
            converter.verify_output(temp, converter.MediaFormat.MP3, tools.ffprobe)  # type: ignore[arg-type]
        except MediaProbeError as exc:
            raise ConvertError(f"轉出的檔案檢查失敗：{exc}") from exc
        while True:
            final = reserver.reserve(output_dir, source.stem, "mp3")
            try:
                if move_no_overwrite(temp, final):
                    break
            finally:
                reserver.release(final)
        if on_progress:
            on_progress(100.0)
        return ConvertResult(source, final, info.audio_bitrate / 1000 if info.audio_bitrate else None)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                log.warning("無法刪除轉檔暫存檔 %s", temp, exc_info=True)


def _run_ffmpeg(cmd: list[str], duration: float | None, on_progress: Callable[[float], None] | None,
                cancel: threading.Event | None) -> None:
    proc = subprocess.Popen(  # 參數清單，不經過 shell
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=converter._CREATIONFLAGS,
    )
    stderr_lines: list[str] = []
    reader = threading.Thread(target=lambda: stderr_lines.extend(proc.stderr), daemon=True)  # type: ignore[arg-type]
    reader.start()
    watcher_stop = threading.Event()

    def watch_cancel() -> None:
        while not watcher_stop.wait(0.2):
            if cancel is not None and cancel.is_set():
                proc.kill()
                return

    watcher = threading.Thread(target=watch_cancel, daemon=True)
    watcher.start()
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            match = _TIME.match(line.strip())
            if match and duration and on_progress:
                seconds = int(match.group(1)) / 1_000_000
                on_progress(min(99.0, seconds / duration * 100))
        proc.wait()
    finally:
        watcher_stop.set()
        reader.join(timeout=5)
    if cancel is not None and cancel.is_set():
        raise ConvertCancelledError()
    if proc.returncode != 0:
        detail = "".join(stderr_lines).strip()[-500:]
        raise ConvertError(f"FFmpeg 轉檔失敗：{detail or f'結束代碼 {proc.returncode}'}")
