import pytest

from yt_media_tool.core.url_parser import UrlKind, UrlParseError, parse_url, parse_urls, split_input

VID = "dQw4w9WgXcQ"
LIST = "PLabcdefghij123456"


@pytest.mark.parametrize("url,kind", [
    (f"https://www.youtube.com/watch?v={VID}", UrlKind.VIDEO),
    (f"https://youtube.com/watch?v={VID}&t=42s", UrlKind.VIDEO),
    (f"https://m.youtube.com/watch?v={VID}", UrlKind.VIDEO),
    (f"https://music.youtube.com/watch?v={VID}", UrlKind.VIDEO),
    (f"https://youtu.be/{VID}", UrlKind.VIDEO),
    (f"https://youtu.be/{VID}?si=xyz", UrlKind.VIDEO),
    (f"https://www.youtube.com/embed/{VID}", UrlKind.VIDEO),
    (f"https://www.youtube.com/live/{VID}", UrlKind.VIDEO),
    (f"https://www.youtube.com/shorts/{VID}", UrlKind.SHORTS),
    (f"https://youtube.com/shorts/{VID}?feature=share", UrlKind.SHORTS),
    (f"https://www.youtube.com/playlist?list={LIST}", UrlKind.PLAYLIST),
    (f"https://www.youtube.com/watch?v={VID}&list={LIST}&index=2", UrlKind.VIDEO_IN_PLAYLIST),
    (f"https://youtu.be/{VID}?list={LIST}", UrlKind.VIDEO_IN_PLAYLIST),
    (f"youtube.com/watch?v={VID}", UrlKind.VIDEO),  # 缺少通訊協定
    (f"youtu.be/{VID}", UrlKind.VIDEO),
])
def test_recognizes_url_kinds(url, kind):
    parsed = parse_url(url)
    assert parsed.kind is kind


def test_normalized_urls():
    assert parse_url(f"https://youtu.be/{VID}?t=3").normalized == f"https://www.youtube.com/watch?v={VID}"
    assert parse_url(f"https://youtube.com/shorts/{VID}").normalized == f"https://www.youtube.com/shorts/{VID}"
    assert parse_url(f"https://www.youtube.com/playlist?list={LIST}").normalized == \
        f"https://www.youtube.com/playlist?list={LIST}"
    mixed = parse_url(f"https://www.youtube.com/watch?v={VID}&list={LIST}")
    assert mixed.video_url == f"https://www.youtube.com/watch?v={VID}"
    assert mixed.playlist_url == f"https://www.youtube.com/playlist?list={LIST}"


@pytest.mark.parametrize("url,reason_part", [
    ("", "空白"),
    ("hello world", "空白字元"),
    ("not a url", "空白字元"),
    ("justtext", "不是有效的網址"),
    ("ftp://youtube.com/watch?v=dQw4w9WgXcQ", "通訊協定"),
    ("https://vimeo.com/123456", "不支援的網站"),
    ("https://evil-youtube.com/watch?v=dQw4w9WgXcQ", "不支援的網站"),
    ("https://www.youtube.com/watch", "缺少影片 ID"),
    ("https://www.youtube.com/watch?v=short", "格式不正確"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ;rm", "格式不正確"),
    ("https://www.youtube.com/playlist", "缺少 list"),
    ("https://www.youtube.com/@SomeChannel", "頻道"),
    ("https://www.youtube.com/channel/UC1234567890", "頻道"),
    ("https://www.youtube.com/results?search_query=x", "搜尋"),
    ("https://www.youtube.com/feed/trending", "無法辨識"),
    ("https://youtu.be/", "缺少影片 ID"),
    ("https://www.youtube.com/watch?v=" + "a" * 3000, "過長"),
])
def test_invalid_urls_have_reasons(url, reason_part):
    with pytest.raises(UrlParseError) as info:
        parse_url(url)
    assert reason_part in str(info.value)


def test_split_input_handles_multiline_and_separators():
    text = f" https://youtu.be/{VID} \n\n<https://youtu.be/aaaaaaaaaaa>,https://youtu.be/bbbbbbbbbbb，x\r\n"
    assert split_input(text) == [
        f"https://youtu.be/{VID}", "https://youtu.be/aaaaaaaaaaa", "https://youtu.be/bbbbbbbbbbb", "x",
    ]


def test_parse_urls_removes_duplicates_and_reports_invalid():
    text = "\n".join([
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtu.be/{VID}",  # 相同影片 ID → 重複
        f"https://www.youtube.com/shorts/{VID}",  # Shorts 與一般網址同 ID → 重複
        f"https://www.youtube.com/watch?v={VID}&t=10",  # 同 ID → 重複
        "https://youtu.be/aaaaaaaaaaa",
        f"https://www.youtube.com/playlist?list={LIST}",
        f"https://www.youtube.com/playlist?list={LIST}",
        "https://example.com/video",
    ])
    result = parse_urls(text)
    assert [p.normalized for p in result.valid] == [
        f"https://www.youtube.com/watch?v={VID}",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        f"https://www.youtube.com/playlist?list={LIST}",
    ]
    assert len(result.duplicates) == 4
    assert len(result.invalid) == 1
    assert "不支援的網站" in result.invalid[0].reason
    assert result.has_playlists


def test_video_in_playlist_is_distinct_from_plain_video():
    result = parse_urls(f"https://youtu.be/{VID}\nhttps://www.youtube.com/watch?v={VID}&list={LIST}")
    assert len(result.valid) == 2


@pytest.mark.parametrize(("url", "expected"), [
    # YouTube 自動產生的「合輯」沒有清單頁面：用播放頁面網址讀取
    ("https://www.youtube.com/watch?v=uzVdsZbYibQ&list=RDuzVdsZbYibQ&start_radio=1",
     "https://www.youtube.com/watch?v=uzVdsZbYibQ&list=RDuzVdsZbYibQ"),
    ("https://www.youtube.com/playlist?list=RDuzVdsZbYibQ",
     "https://www.youtube.com/watch?v=uzVdsZbYibQ&list=RDuzVdsZbYibQ"),
    # 一般播放清單維持清單頁面
    ("https://www.youtube.com/watch?v=uzVdsZbYibQ&list=PLabcdefghij123456",
     "https://www.youtube.com/playlist?list=PLabcdefghij123456"),
    ("https://www.youtube.com/playlist?list=PLabcdefghij123456", "https://www.youtube.com/playlist?list=PLabcdefghij123456"),
])
def test_playlist_source_url_handles_youtube_mixes(url, expected):
    assert parse_url(url).playlist_source_url == expected


@pytest.mark.parametrize("list_id", ["WL", "LL", "RDMM"])
def test_short_special_list_ids_are_accepted(list_id):
    """「稍後觀看」「喜歡的影片」「我的合輯」的清單 ID 只有 2～4 碼，不可因此拒絕整個網址。"""
    parsed = parse_url(f"https://www.youtube.com/watch?v={VID}&list={list_id}")
    assert parsed.kind is UrlKind.VIDEO_IN_PLAYLIST and parsed.playlist_id == list_id
    assert parsed.video_url == f"https://www.youtube.com/watch?v={VID}"


def test_video_with_unrecognized_list_param_is_still_a_video():
    for url in (f"https://www.youtube.com/watch?v={VID}&list=bad!id", f"https://youtu.be/{VID}?list=x"):
        parsed = parse_url(url)
        assert parsed.kind is UrlKind.VIDEO and parsed.video_id == VID and parsed.playlist_id is None
    with pytest.raises(UrlParseError):  # 純清單網址的 ID 仍須合法
        parse_url("https://www.youtube.com/playlist?list=bad!id")


@pytest.mark.parametrize("text", [
    f"看這個 https://youtu.be/{VID} 很讚",
    f"推薦這首https://youtu.be/{VID}很好聽",
    f"(https://www.youtube.com/watch?v={VID})",
    f"https://www.youtube.com/watch?v={VID}。",
    f"https://www.youtube.com/watch?v={VID}.",
    f"youtube.com/watch?v={VID}。謝謝",
    f"1. https://youtu.be/{VID}",
    f"周杰倫 - 晴天\nhttps://youtu.be/{VID}",
])
def test_urls_are_found_inside_pasted_text(text):
    """網址常連同前後文字、編號或標點一起貼上：只取網址，其餘文字不當成「不支援的網址」。"""
    result = parse_urls(text)
    assert [p.video_id for p in result.valid] == [VID]
    assert result.invalid == []


def test_plain_text_is_ignored_but_url_like_text_is_reported():
    result = parse_urls(f"只有文字 hello https://vimeo.com/1 example.com/x https://youtu.be/{VID}https://youtu.be/aaaaaaaaaaa")
    assert result.ignored == ["只有文字", "hello"]
    assert [i.original for i in result.invalid] == ["https://vimeo.com/1", "example.com/x"]
    assert [p.video_id for p in result.valid] == [VID, "aaaaaaaaaaa"]  # 兩個網址黏在一起也能分開
