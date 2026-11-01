"""已下載過的影片判斷（已下載過提醒、播放清單同步）。"""

from yt_media_tool.core.download_index import DownloadedIndex, video_key
from yt_media_tool.core.task_models import MediaFormat


def test_video_key_treats_url_variants_as_same_video():
    keys = {video_key(u) for u in ("https://youtu.be/aaaaaaaaaaa?t=30", "https://www.youtube.com/watch?v=aaaaaaaaaaa",
                                   "https://www.youtube.com/watch?v=aaaaaaaaaaa&list=PLabcdefghij123456",
                                   "https://m.youtube.com/watch?v=aaaaaaaaaaa")}
    assert keys == {"aaaaaaaaaaa"}
    assert video_key("http://127.0.0.1/x.mp4") == "http://127.0.0.1/x.mp4"


def test_index_uses_newest_existing_file_per_format(tmp_path):
    old, new, video = tmp_path / "old.mp3", tmp_path / "new.mp3", tmp_path / "v.mp4"
    for p in (old, video):
        p.write_bytes(b"x")
    rows = [  # 新 → 舊；最新那筆的檔案已被刪除
        {"url": "https://youtu.be/aaaaaaaaaaa", "media_format": "mp3", "output_path": str(new)},
        {"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "media_format": "mp3", "output_path": str(old)},
        {"url": "https://youtu.be/aaaaaaaaaaa", "media_format": "mp4", "output_path": str(video)},
        {"url": "https://youtu.be/bbbbbbbbbbb", "media_format": "mp3", "output_path": ""},
    ]
    index = DownloadedIndex(rows)
    assert index.find("https://www.youtube.com/watch?v=aaaaaaaaaaa&t=1", MediaFormat.MP3) == old
    assert index.find("https://youtu.be/aaaaaaaaaaa", MediaFormat.MP4) == video
    assert index.find("https://youtu.be/bbbbbbbbbbb", MediaFormat.MP3) is None
    assert len(index) == 2
