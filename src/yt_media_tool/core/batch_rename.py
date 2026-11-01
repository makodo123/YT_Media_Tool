"""舊檔案批次整理歌名：把資料夾中已下載的 MP3 / MP4 依「歌名自動整理」規則改名。

安全原則：
- 只處理 .mp3 / .mp4；略過隱藏檔與本程式的暫存資料夾（.ytmt_*）。
- 先產生預覽（RenamePlan），使用者確認後才改名；同名檔案已存在時改用「 (1)」「 (2)」…，絕不覆蓋。
- 同名的字幕檔（影片.srt、影片.zh-TW.srt）一併改名，播放器才會繼續自動載入。
- 同資料夾中的播放清單檔（.m3u8）裡的檔名一併更新。
- 可用 undo() 復原上一次改名。
只改檔名，不修改檔案內容（MP3 內的歌名資訊不變）。
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from yt_media_tool.core.downloader import move_no_overwrite
from yt_media_tool.core.title_cleanup import clean_title
from yt_media_tool.utils.paths import sanitize_filename

log = logging.getLogger(__name__)

MEDIA_SUFFIXES = (".mp3", ".mp4")
_DUPLICATE_SUFFIX = re.compile(r"^(.*?)\s*\((\d+)\)$")  # 「歌名 (1)」：保留編號


@dataclass
class RenamePlan:
    path: Path
    new_stem: str

    @property
    def new_name(self) -> str:
        return self.new_stem + self.path.suffix


@dataclass
class RenameResult:
    old: Path
    new: Path
    extras: list[tuple[Path, Path]] = field(default_factory=list)  # 一併改名的字幕檔（舊, 新）


def proposed_stem(stem: str) -> str | None:
    """依歌名整理規則建議的新檔名主體；不需要改時回傳 None。"""
    match = _DUPLICATE_SUFFIX.match(stem)
    base, number = (match.group(1), match.group(2)) if match else (stem, None)
    cleaned = clean_title({"title": base, "channel": ""})
    if cleaned is None:
        return None
    new = sanitize_filename(cleaned.display)
    if number:
        new = f"{new} ({number})"
    return new if new and new != stem else None


def _skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(part.startswith(".") for part in parts)


def scan(folder: Path, recursive: bool = True) -> list[RenamePlan]:
    folder = Path(folder)
    candidates = folder.rglob("*") if recursive else folder.iterdir()
    plans = []
    for path in sorted(candidates):
        if path.suffix.lower() not in MEDIA_SUFFIXES or not path.is_file() or _skip(path, folder):
            continue
        stem = proposed_stem(path.stem)
        if stem:
            plans.append(RenamePlan(path, stem))
    return plans


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _move_to_unused(src: Path, stem: str, suffix: str) -> Path | None:
    """改名為 stem+suffix；已存在時加上「 (1)」「 (2)」…。回傳新路徑；新舊相同（只差大小寫）時回傳 None。"""
    for counter in range(10000):
        target = src.with_name(f"{stem} ({counter}){suffix}" if counter else f"{stem}{suffix}")
        if _same(target, src):
            return None
        if not target.exists() and move_no_overwrite(src, target):
            return target
    raise FileExistsError(f"找不到可用的檔名：{stem}{suffix}")


def _subtitles_of(media: Path) -> list[Path]:
    prefix = media.stem + "."
    return sorted(p for p in media.parent.iterdir()
                  if p.is_file() and p.suffix.lower() == ".srt" and p.name.startswith(prefix)
                  and "." not in p.name[len(prefix):-len(".srt")])  # 影片.srt 或 影片.<語言>.srt


def _update_playlists(folder: Path, renamed: dict[str, str]) -> None:
    """把資料夾內 .m3u8 中的舊檔名換成新檔名（只換完整的檔名行與 #EXTINF 標題）。"""
    if not renamed:
        return
    titles = {Path(old).stem: Path(new).stem for old, new in renamed.items()}
    for playlist in folder.glob("*.m3u8"):
        try:
            lines = playlist.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        changed = False
        for i, line in enumerate(lines):
            if line in renamed:
                lines[i], changed = renamed[line], True
            elif line.startswith("#EXTINF:") and "," in line:
                head, title = line.split(",", 1)
                if title in titles:
                    lines[i], changed = f"{head},{titles[title]}", True
        if changed:
            temp = folder / f".ytmt_m3u_{uuid.uuid4().hex[:8]}.tmp"
            try:
                temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
                os.replace(temp, playlist)
            except OSError:
                log.warning("無法更新播放清單檔 %s", playlist, exc_info=True)
                temp.unlink(missing_ok=True)


def apply(plans: Iterable[RenamePlan]) -> tuple[list[RenameResult], list[tuple[Path, str]]]:
    """依預覽改名；回傳（成功的改名, 失敗的檔案與原因）。"""
    results: list[RenameResult] = []
    errors: list[tuple[Path, str]] = []
    by_folder: dict[Path, dict[str, str]] = {}
    for plan in plans:
        src = plan.path
        stem = sanitize_filename(plan.new_stem)
        if not stem:
            errors.append((src, "新檔名不可空白"))
            continue
        if not src.is_file():
            errors.append((src, "檔案已不存在（可能已被移動或刪除）"))
            continue
        subtitles = _subtitles_of(src)
        try:
            target = _move_to_unused(src, stem, src.suffix)
        except OSError as exc:
            errors.append((src, f"無法改名：{exc.strerror or exc}"))
            continue
        if target is None:
            continue
        result = RenameResult(src, target)
        for sub in subtitles:
            rest = sub.name[len(src.stem):]  # 「.srt」或「.zh-TW.srt」
            new_sub = sub.with_name(target.stem + rest)
            try:
                if not new_sub.exists() and move_no_overwrite(sub, new_sub):
                    result.extras.append((sub, new_sub))
            except OSError:
                log.warning("無法改名字幕 %s", sub, exc_info=True)
        results.append(result)
        by_folder.setdefault(src.parent, {})[src.name] = target.name
    for folder, renamed in by_folder.items():
        _update_playlists(folder, renamed)
    return results, errors


def undo(results: list[RenameResult]) -> list[tuple[Path, str]]:
    """復原 apply() 的改名；原檔名已被其他檔案使用時略過並回報。"""
    errors: list[tuple[Path, str]] = []
    by_folder: dict[Path, dict[str, str]] = {}
    for result in reversed(results):
        if not result.new.is_file():
            errors.append((result.new, "檔案已不存在，無法復原"))
            continue
        try:
            if result.old.exists() or not move_no_overwrite(result.new, result.old):
                errors.append((result.new, f"原檔名「{result.old.name}」已被使用，無法復原"))
                continue
        except OSError as exc:
            errors.append((result.new, f"無法復原：{exc.strerror or exc}"))
            continue
        for old_sub, new_sub in result.extras:
            try:
                if new_sub.is_file() and not old_sub.exists():
                    move_no_overwrite(new_sub, old_sub)
            except OSError:
                log.warning("無法復原字幕 %s", new_sub, exc_info=True)
        by_folder.setdefault(result.old.parent, {})[result.new.name] = result.old.name
    for folder, renamed in by_folder.items():
        _update_playlists(folder, renamed)
    return errors
