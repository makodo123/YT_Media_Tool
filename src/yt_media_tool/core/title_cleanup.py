"""歌名自動整理：把 YouTube 影片標題整理成「演出者 - 歌名」。

順序：
1. YouTube 提供的歌曲資訊（「影片中的音樂」：track / artist）最準確，有就直接使用。
2. 否則整理標題：去掉「Official MV」「動態歌詞」「4K」等雜訊，拆出演出者與歌名；
   中文名稱後面附的英文翻譯（例如「晴天 Sunny Day」）只保留中文。
3. 標題中沒有演出者時用頻道名稱（去掉「- Topic」「官方頻道」等字）。
整理不出合理結果時回傳 None，呼叫端保留原標題（寧可不整理，也不整理錯）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CJK = r"㐀-䶿一-鿿豈-﫿぀-ヿ가-힯"

# 括號內含這些字時，整個括號視為雜訊移除
_NOISE_WORDS = (
    r"official|music\s*video|m/?v|lyrics?|lyric\s*video|audio|visuali[sz]er|video|hd|hq|4k|8k|1080p|720p|"
    r"官方|動態歌詞|歌詞|字幕|高音質|高畫質|完整版|中字|中文字幕|首播|音源|純享版"
)
_BRACKETS = r"[\(\[（【「『〔《<]([^\(\)\[\]（）【】「」『』〔〕《》<>]*)[\)\]）】」』〕》>]"
_NOISE_BRACKET = re.compile(_BRACKETS)
_NOISE_IN_BRACKET = re.compile(rf"(?i)(^|[^a-z])({_NOISE_WORDS})([^a-z]|$)")
# 不在括號內、位於開頭或結尾的雜訊
_TRAILING_NOISE = re.compile(
    r"(?i)[\s\-–—|｜]*(official\s+(music\s+)?video|official\s+mv|official\s+audio|official\s+lyric\s+video|"
    r"lyric\s+video|music\s+video|官方\s*mv|官方完整版\s*mv|官方版|\bmv\b|\bm/v\b|\b4k\b|\bhd\b)[\s\-–—|｜]*$")
_LEADING_NOISE = re.compile(r"(?i)^\s*(官方\s*mv|official\s+mv|\bmv\b)[\s\-–—|｜:：]*")
_SEPARATORS = re.compile(r"\s+[-–—]\s+|\s*[|｜]\s*")
# 中文名稱後附加的英文 / 拼音翻譯，例如「周杰倫 Jay Chou」「晴天 Sunny Day」（翻譯以大寫字母開頭）
_CJK_WITH_LATIN = re.compile(rf"^([{_CJK}][{_CJK}\s·・&、]*?)\s+([A-Z][A-Za-z0-9 .'&!?,-]*)$")
_LATIN_WITH_CJK = re.compile(rf"^([A-Z][A-Za-z0-9 .'&!?,-]*?)\s+([{_CJK}][{_CJK}\s·・&、]*)$")
# 這些字代表不同版本，不是翻譯，不可去掉
_VERSION_WORDS = re.compile(r"(?i)\b(remix|live|acoustic|cover|ver|version|instrumental|inst|demo|edit|mix|feat|ft|"
                            r"remaster(ed)?|unplugged|piano|orchestra)\b")
# 這些括號內的文字是歌名（例如「周杰倫【晴天】」）；( ) [ ] 內不是雜訊的文字則接在歌名後面
_TITLE_BRACKETS = "【《「『〔<"
_CHANNEL_NOISE = re.compile(
    r"(?i)\s*(-\s*topic|vevo|official\s+youtube\s+channel|official\s+channel|official|官方頻道|官方|頻道|channel)\s*$")


@dataclass(frozen=True)
class CleanTitle:
    artist: str
    track: str

    @property
    def display(self) -> str:
        return f"{self.artist} - {self.track}" if self.artist else self.track


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -–—|｜:：,，")


def _drop_translation(text: str) -> str:
    """「晴天 Sunny Day」→「晴天」；「Jay Chou 周杰倫」→「周杰倫」；其他維持原樣。"""
    text = _squash(text)
    match = _CJK_WITH_LATIN.match(text)
    if match and not _VERSION_WORDS.search(match.group(2)):
        return _squash(match.group(1))
    match = _LATIN_WITH_CJK.match(text)
    if match and not _VERSION_WORDS.search(match.group(1)):
        return _squash(match.group(2))
    return text


def clean_channel(name: str) -> str:
    previous = None
    name = _squash(name or "")
    while previous != name:
        previous, name = name, _squash(_CHANNEL_NOISE.sub("", name))
    return _drop_translation(name)


def _strip_noise(title: str) -> tuple[str, list[str]]:
    """移除雜訊括號與前後雜訊字；回傳（剩下的文字, 保留下來的括號內容）。"""
    kept: list[str] = []

    def replace(match: re.Match) -> str:
        inner = match.group(1).strip()
        if not inner or _NOISE_IN_BRACKET.search(inner):
            return " "
        if match.group(0)[0] not in _TITLE_BRACKETS:
            return f" ({inner}) "  # 例如「(Live Aid 1985)」：保留在原位置
        kept.append(inner)
        return f" \x00{len(kept) - 1}\x00 "

    text = _NOISE_BRACKET.sub(replace, title)
    previous = None
    while previous != text:
        previous = text
        text = _TRAILING_NOISE.sub("", _LEADING_NOISE.sub("", text))
    return _squash(text), kept


def clean_title(info: dict) -> CleanTitle | None:
    track = str(info.get("track") or "").strip()
    artists = info.get("artists") or ([info["artist"]] if info.get("artist") else [])
    if track and artists:
        return CleanTitle(_squash(", ".join(str(a) for a in artists[:3])), _squash(track))

    title = str(info.get("title") or "")
    channel = clean_channel(str(info.get("channel") or info.get("uploader") or ""))
    text, kept = _strip_noise(title)
    if not text and not kept:
        return None

    artist, song = "", ""
    placeholders = re.findall(r"\x00(\d+)\x00", text)
    outside = _squash(re.sub(r"\x00\d+\x00", " ", text))
    if placeholders and outside and not _SEPARATORS.search(outside):
        # 「周杰倫 Jay Chou【晴天 Sunny Day】」：括號外是演出者、括號內是歌名
        artist, song = outside, kept[int(placeholders[0])]
    else:
        text = _squash(re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], text))
        parts = [p for p in (_squash(x) for x in _SEPARATORS.split(text)) if p]
        if len(parts) >= 2:
            left, right = parts[0], " ".join(parts[1:])
            # 頻道名稱出現在哪一邊，那邊就是演出者；判斷不出時依慣例「演出者 - 歌名」
            if channel and channel in _drop_translation(right) and channel not in _drop_translation(left):
                artist, song = right, left
            else:
                artist, song = left, right
        elif parts:
            song = parts[0]
            artist = channel
    artist, song = _drop_translation(artist), _drop_translation(song)
    if not song or len(song) > 120:
        return None
    if artist and artist == song:
        artist = ""
    return CleanTitle(artist, song)
