"""歌名自動整理：常見的 YouTube 標題寫法。"""

import pytest

from yt_media_tool.core.title_cleanup import clean_channel, clean_title


@pytest.mark.parametrize(("title", "channel", "expected"), [
    ("周杰倫 Jay Chou【晴天 Sunny Day】Official MV", "周杰倫 Jay Chou", "周杰倫 - 晴天"),
    ("告白氣球 (Official Music Video) [HD]", "周杰倫 Jay Chou", "周杰倫 - 告白氣球"),
    ("稻香 - 周杰倫 (Lyrics/動態歌詞) 4K", "周杰倫 Jay Chou", "周杰倫 - 稻香"),
    ("【官方MV】五月天 Mayday - 倔強", "相信音樂BinMusic", "五月天 - 倔強"),
    ("五月天 Mayday【倔強】Official Music Video", "相信音樂BinMusic", "五月天 - 倔強"),
    ("鄧紫棋 G.E.M.【光年之外 LIGHT YEARS AWAY】MV", "G.E.M. 鄧紫棋", "鄧紫棋 - 光年之外"),
    ("Ed Sheeran - Shape of You (Official Music Video)", "Ed Sheeran", "Ed Sheeran - Shape of You"),
    ("Adele - Hello (Official Video)", "AdeleVEVO", "Adele - Hello"),
    ("Hello (Lyrics)", "Adele - Topic", "Adele - Hello"),
    ("林俊傑 JJ Lin《修煉愛情 Practice Love》官方 MV", "林俊傑 JJ Lin", "林俊傑 - 修煉愛情"),
    ("Taylor Swift | Anti-Hero (Official Music Video)", "Taylor Swift", "Taylor Swift - Anti-Hero"),
    ("小幸運 - 田馥甄 Hebe Tien", "華研國際", "小幸運 - 田馥甄"),  # 判斷不出哪邊是演出者時依慣例
    ("我的日常 vlog", "某某頻道", "某某 - 我的日常 vlog"),
    ("Bohemian Rhapsody (Live Aid 1985)", "Queen Official", "Queen - Bohemian Rhapsody (Live Aid 1985)"),
    ("告白氣球 Remix", "周杰倫 Jay Chou", "周杰倫 - 告白氣球 Remix"),  # 版本字不是翻譯
    ("周杰倫【晴天 Live】", "某頻道", "周杰倫 - 晴天 Live"),
    ("Coldplay - Yellow [Acoustic]", "Coldplay", "Coldplay - Yellow (Acoustic)"),
])
def test_clean_title_examples(title, channel, expected):
    result = clean_title({"title": title, "channel": channel})
    assert result is not None and result.display == expected


def test_youtube_music_metadata_wins():
    info = {"title": "周杰倫 Jay Chou【晴天】Official MV", "track": "晴天", "artists": ["周杰倫"]}
    result = clean_title(info)
    assert (result.artist, result.track, result.display) == ("周杰倫", "晴天", "周杰倫 - 晴天")


@pytest.mark.parametrize("title", ["", "【Official MV】", "(Lyrics) [4K]"])
def test_nothing_left_returns_none(title):
    assert clean_title({"title": title, "channel": "某頻道"}) is None


@pytest.mark.parametrize(("channel", "expected"), [
    ("周杰倫 - Topic", "周杰倫"), ("AdeleVEVO", "Adele"), ("五月天 官方頻道", "五月天"),
    ("周杰倫 Jay Chou", "周杰倫"), ("Queen Official", "Queen"),
])
def test_clean_channel(channel, expected):
    assert clean_channel(channel) == expected
