"""YouTube 網址解析：分類（影片 / Shorts / 播放清單）、正規化、去除重複與錯誤原因說明。

此模組只做離線的字串解析，不連線網路。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import parse_qs, urlsplit


class UrlKind(str, Enum):
    VIDEO = "video"
    SHORTS = "shorts"
    PLAYLIST = "playlist"
    VIDEO_IN_PLAYLIST = "video_in_playlist"  # 播放清單中的單一影片（watch?v=...&list=...）

    @property
    def label(self) -> str:
        return {
            UrlKind.VIDEO: "影片",
            UrlKind.SHORTS: "Shorts",
            UrlKind.PLAYLIST: "播放清單",
            UrlKind.VIDEO_IN_PLAYLIST: "播放清單中的影片",
        }[self]


@dataclass(frozen=True)
class ParsedUrl:
    original: str
    kind: UrlKind
    video_id: str | None = None
    playlist_id: str | None = None

    @property
    def video_url(self) -> str | None:
        if not self.video_id:
            return None
        if self.kind is UrlKind.SHORTS:
            return f"https://www.youtube.com/shorts/{self.video_id}"
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def playlist_url(self) -> str | None:
        return f"https://www.youtube.com/playlist?list={self.playlist_id}" if self.playlist_id else None

    @property
    def normalized(self) -> str:
        """正規化後的網址（播放清單網址回傳清單，其餘回傳單一影片網址）。"""
        if self.kind is UrlKind.PLAYLIST:
            return self.playlist_url  # type: ignore[return-value]
        return self.video_url  # type: ignore[return-value]

    @property
    def dedupe_key(self) -> str:
        if self.kind is UrlKind.PLAYLIST:
            return f"list:{self.playlist_id}"
        if self.kind is UrlKind.VIDEO_IN_PLAYLIST:
            return f"video:{self.video_id}|list:{self.playlist_id}"
        return f"video:{self.video_id}"  # 一般影片與 Shorts 同一 ID 視為重複


@dataclass(frozen=True)
class InvalidUrl:
    original: str
    reason: str


@dataclass
class ParseResult:
    valid: list[ParsedUrl] = field(default_factory=list)
    invalid: list[InvalidUrl] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)

    @property
    def has_playlists(self) -> bool:
        return any(p.kind in (UrlKind.PLAYLIST, UrlKind.VIDEO_IN_PLAYLIST) for p in self.valid)


class UrlParseError(ValueError):
    pass


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID = re.compile(r"^[A-Za-z0-9_-]{10,64}$")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
_CHANNEL_PREFIXES = ("/channel/", "/c/", "/user/", "/@")
MAX_URL_LENGTH = 2048


def _check_video_id(value: str | None) -> str:
    if not value:
        raise UrlParseError("網址缺少影片 ID")
    if not _VIDEO_ID.match(value):
        raise UrlParseError(f"影片 ID 格式不正確：{value}")
    return value


def _check_playlist_id(value: str) -> str:
    if not _PLAYLIST_ID.match(value):
        raise UrlParseError(f"播放清單 ID 格式不正確：{value}")
    return value


def parse_url(raw: str) -> ParsedUrl:
    """解析單一網址；不支援時拋出 UrlParseError，訊息即為顯示給使用者的原因。"""
    text = (raw or "").strip()
    if not text:
        raise UrlParseError("網址為空白")
    if len(text) > MAX_URL_LENGTH:
        raise UrlParseError("網址長度過長")
    if any(ch.isspace() for ch in text):
        raise UrlParseError("網址中含有空白字元")
    if "://" not in text:
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", text, re.IGNORECASE):
            text = "https://" + text
        else:
            raise UrlParseError("不是有效的網址")

    parts = urlsplit(text)
    if parts.scheme.lower() not in ("http", "https"):
        raise UrlParseError(f"不支援的通訊協定：{parts.scheme}（僅支援 http / https）")
    host = (parts.hostname or "").lower()
    if not host:
        raise UrlParseError("不是有效的網址")
    query = parse_qs(parts.query)
    path = parts.path or "/"

    if host in _SHORT_HOSTS:
        video_id = _check_video_id(path.strip("/").split("/")[0] or None)
        list_id = query.get("list", [None])[0]
        if list_id:
            return ParsedUrl(raw.strip(), UrlKind.VIDEO_IN_PLAYLIST, video_id, _check_playlist_id(list_id))
        return ParsedUrl(raw.strip(), UrlKind.VIDEO, video_id)

    if host not in _YOUTUBE_HOSTS:
        raise UrlParseError(f"不支援的網站：{host}（僅支援 YouTube 網址）")

    list_id = query.get("list", [None])[0]
    if path.startswith("/shorts/"):
        video_id = _check_video_id(path[len("/shorts/"):].strip("/").split("/")[0] or None)
        return ParsedUrl(raw.strip(), UrlKind.SHORTS, video_id)
    if path in ("/watch", "/watch/"):
        video_id = _check_video_id(query.get("v", [None])[0])
        if list_id:
            return ParsedUrl(raw.strip(), UrlKind.VIDEO_IN_PLAYLIST, video_id, _check_playlist_id(list_id))
        return ParsedUrl(raw.strip(), UrlKind.VIDEO, video_id)
    if path.startswith(("/embed/", "/live/", "/v/")):
        segment = path.strip("/").split("/")
        video_id = _check_video_id(segment[1] if len(segment) > 1 else None)
        return ParsedUrl(raw.strip(), UrlKind.VIDEO, video_id)
    if path in ("/playlist", "/playlist/"):
        if not list_id:
            raise UrlParseError("播放清單網址缺少 list 參數")
        return ParsedUrl(raw.strip(), UrlKind.PLAYLIST, None, _check_playlist_id(list_id))
    if path.startswith(_CHANNEL_PREFIXES):
        raise UrlParseError("不支援頻道網址，請貼上影片、Shorts 或播放清單網址")
    if path.startswith("/results"):
        raise UrlParseError("不支援搜尋結果網址")
    raise UrlParseError("無法辨識的 YouTube 網址（需為影片、Shorts 或播放清單）")


def split_input(text: str) -> list[str]:
    """將使用者輸入（可能多行、以空白或逗號分隔）拆成候選網址。"""
    tokens = re.split(r"[\s,，、]+", text or "")
    return [t for t in (tok.strip().strip("<>\"'") for tok in tokens) if t]


def parse_urls(text: str) -> ParseResult:
    """解析多行網址並去除重複（依影片 / 清單 ID 判斷，順序保留第一次出現者）。"""
    result = ParseResult()
    seen: set[str] = set()
    for candidate in split_input(text):
        try:
            parsed = parse_url(candidate)
        except UrlParseError as exc:
            result.invalid.append(InvalidUrl(candidate, str(exc)))
            continue
        if parsed.dedupe_key in seen:
            result.duplicates.append(candidate)
            continue
        seen.add(parsed.dedupe_key)
        result.valid.append(parsed)
    return result
