"""播放清單檔（.m3u8）的產生與更新。"""

from pathlib import Path

import pytest

from yt_media_tool.core.playlist_files import PlaylistFileStore
from yt_media_tool.core.task_models import DownloadTask, MediaFormat, TaskStatus

URLS = [f"https://www.youtube.com/watch?v=song{i:07d}" for i in range(3)]


def done(folder: Path, i: int, name: str, fmt=MediaFormat.MP3) -> DownloadTask:
    out = folder / name
    out.write_bytes(b"x")
    return DownloadTask(url=URLS[i], media_format=fmt, quality="192" if fmt is MediaFormat.MP3 else "1080",
                        output_dir=str(folder), status=TaskStatus.COMPLETED, output_path=str(out))


@pytest.fixture
def music(tmp_path):
    folder = tmp_path / "音樂"  # db fixture 的資料庫檔也在 tmp_path，另用子資料夾
    folder.mkdir()
    return folder


def read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_m3u_follows_playlist_order_and_updates(db, music):
    store = PlaylistFileStore(db)
    assert store.add_batch(str(music), "我的最愛", "mp3", URLS)
    # 第 3 首先下載完成
    [m3u] = store.on_task_completed(done(music, 2, "稻香.mp3"))
    assert m3u == music / "我的最愛.m3u8"
    assert read(m3u) == ["#EXTM3U", "#EXTINF:-1,稻香", "稻香.mp3"]
    store.on_task_completed(done(music, 0, "晴天.mp3"))
    assert read(m3u) == ["#EXTM3U", "#EXTINF:-1,晴天", "晴天.mp3", "#EXTINF:-1,稻香", "稻香.mp3"]  # 依清單順序
    assert sorted(p.name for p in music.iterdir()) == ["我的最愛.m3u8", "晴天.mp3", "稻香.mp3"]  # 沒有暫存檔


def test_survives_restart_and_skips_deleted_files(db, music):
    PlaylistFileStore(db).add_batch(str(music), "清單", "mp3", URLS)
    store = PlaylistFileStore(db)  # 模擬重新開啟程式
    store.on_task_completed(done(music, 0, "一.mp3"))
    (music / "一.mp3").unlink()
    [m3u] = store.on_task_completed(done(music, 1, "二.mp3"))
    assert read(m3u) == ["#EXTM3U", "#EXTINF:-1,二", "二.mp3"]


def test_does_not_overwrite_user_file(db, music):
    (music / "清單.m3u8").write_text("使用者自己的清單", encoding="utf-8")
    store = PlaylistFileStore(db)
    store.add_batch(str(music), "清單", "mp3", URLS)
    [m3u] = store.on_task_completed(done(music, 0, "一.mp3"))
    assert m3u.name == "清單 (1).m3u8"
    assert (music / "清單.m3u8").read_text(encoding="utf-8") == "使用者自己的清單"
    [again] = store.on_task_completed(done(music, 1, "二.mp3"))
    assert again == m3u  # 之後更新同一個（本程式建立的）檔案


def test_ignores_single_song_other_format_and_other_folder(db, music):
    store = PlaylistFileStore(db)
    assert not store.add_batch(str(music), "只有一首", "mp3", URLS[:1])
    store.add_batch(str(music), "清單", "mp3", URLS)
    assert store.on_task_completed(done(music, 0, "影片.mp4", MediaFormat.MP4)) == []
    other = music / "其他"
    other.mkdir()
    assert store.on_task_completed(done(other, 0, "一.mp3")) == []
    assert not list(music.glob("*.m3u8"))


def test_same_playlist_again_reuses_m3u_and_keeps_known_songs(db, music):
    store = PlaylistFileStore(db)
    store.add_batch(str(music), "我的最愛", "mp3", URLS[:2])
    store.on_task_completed(done(music, 0, "晴天.mp3"))
    store.on_task_completed(done(music, 1, "稻香.mp3"))
    # 清單新增了第 3 首；再次加入時只下載新歌，已下載的兩首以 known_files 帶入
    assert store.add_batch(str(music), "我的最愛", "mp3", URLS, known_files={URLS[0]: "晴天.mp3", URLS[1]: "稻香.mp3"})
    [m3u] = store.on_task_completed(done(music, 2, "七里香.mp3"))
    assert m3u == music / "我的最愛.m3u8"  # 沿用同一個清單檔，不產生「我的最愛 (1).m3u8」
    assert [line for line in read(m3u) if not line.startswith("#")] == ["晴天.mp3", "稻香.mp3", "七里香.mp3"]
    assert len(db.get_setting("playlist_files.batches")) == 1


def test_known_files_for_new_batch(db, music):
    (music / "晴天.mp3").write_bytes(b"x")
    store = PlaylistFileStore(db)
    store.add_batch(str(music), "清單", "mp3", URLS[:2], known_files={URLS[0]: "晴天.mp3"})
    [m3u] = store.on_task_completed(done(music, 1, "稻香.mp3"))
    assert [line for line in read(m3u) if not line.startswith("#")] == ["晴天.mp3", "稻香.mp3"]
