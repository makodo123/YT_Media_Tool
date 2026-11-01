"""舊檔案批次整理歌名：預覽、改名、字幕與播放清單同步、不覆蓋、復原。"""

import pytest

from yt_media_tool.core import batch_rename
from yt_media_tool.core.batch_rename import RenamePlan, proposed_stem

MESSY = "周深 ZHOU SHEN × MAYDAY 五月天 [ 如煙 Like Smoke ] 5525+2版 Official Stage Video"
CLEAN = "周深 × 五月天 - 如煙 (5525+2版)"


@pytest.fixture
def music(tmp_path):
    folder = tmp_path / "音樂"
    (folder / "合輯").mkdir(parents=True)
    (folder / f"{MESSY}.mp4").write_bytes(b"video")
    (folder / f"{MESSY}.srt").write_text("subtitle", encoding="utf-8")
    (folder / f"{MESSY}.zh-TW.srt").write_text("subtitle tw", encoding="utf-8")
    (folder / "合輯" / "MAYDAY五月天 [ 笑忘歌 The Song of Laughter ] Official Live Video (1).mp3").write_bytes(b"a")
    (folder / "周杰倫 - 晴天.mp3").write_bytes(b"already clean")
    (folder / "說明.txt").write_text("x", encoding="utf-8")
    (folder / ".ytmt_tmp").mkdir()
    (folder / ".ytmt_tmp" / "Some Song (Official Video).mp3").write_bytes(b"temp")
    return folder


def test_proposed_stem():
    assert proposed_stem(MESSY) == CLEAN
    assert proposed_stem("告白氣球 (Official Music Video) [HD] (2)") == "告白氣球 (2)"  # 保留重複編號
    assert proposed_stem("周杰倫 - 晴天") is None  # 已經整理好
    assert proposed_stem("我的日常 vlog") is None
    # Windows 檔名不能有「|」，yt-dlp 存成全形「｜」
    assert proposed_stem("白敬亭 BAI JINGTING × MAYDAY五月天 [  任性 Willful  ] 5525版 Official Stage Video "
                         "｜ Theme Song of ＂The First Frost＂") == "白敬亭 × 五月天 - 任性 (5525版)"


def test_scan_previews_only_media_and_skips_temp(music):
    plans = batch_rename.scan(music)
    assert sorted((p.path.name, p.new_name) for p in plans) == sorted([
        (f"{MESSY}.mp4", f"{CLEAN}.mp4"),
        ("MAYDAY五月天 [ 笑忘歌 The Song of Laughter ] Official Live Video (1).mp3", "五月天 - 笑忘歌 (1).mp3"),
    ])
    assert len(batch_rename.scan(music, recursive=False)) == 1  # 不含子資料夾


def test_apply_renames_with_subtitles_and_playlist(music):
    (music / "清單.m3u8").write_text(f"#EXTM3U\n#EXTINF:-1,{MESSY}\n{MESSY}.mp4\n#EXTINF:-1,其他\n其他.mp3\n",
                                     encoding="utf-8")
    plans = batch_rename.scan(music, recursive=False)
    results, errors = batch_rename.apply(plans)
    assert errors == [] and len(results) == 1
    assert (music / f"{CLEAN}.mp4").read_bytes() == b"video"
    assert (music / f"{CLEAN}.srt").read_text(encoding="utf-8") == "subtitle"
    assert (music / f"{CLEAN}.zh-TW.srt").is_file()
    assert not list(music.glob(f"{MESSY}*"))
    assert (music / "清單.m3u8").read_text(encoding="utf-8") == (
        f"#EXTM3U\n#EXTINF:-1,{CLEAN}\n{CLEAN}.mp4\n#EXTINF:-1,其他\n其他.mp3\n")

    assert batch_rename.undo(results) == []
    assert (music / f"{MESSY}.mp4").read_bytes() == b"video"
    assert (music / f"{MESSY}.zh-TW.srt").is_file() and not (music / f"{CLEAN}.srt").exists()
    assert f"{MESSY}.mp4" in (music / "清單.m3u8").read_text(encoding="utf-8")


def test_apply_never_overwrites(music):
    (music / f"{CLEAN}.mp4").write_bytes(b"user file")
    results, errors = batch_rename.apply(batch_rename.scan(music, recursive=False))
    assert errors == [] and results[0].new.name == f"{CLEAN} (1).mp4"
    assert (music / f"{CLEAN}.mp4").read_bytes() == b"user file"
    assert (music / f"{CLEAN} (1).srt").is_file()  # 字幕跟著新檔名


def test_user_edited_name_and_missing_file(music):
    plan = RenamePlan(music / f"{MESSY}.mp4", "我自己取的名字 / 有斜線")
    gone = RenamePlan(music / "不存在.mp4", "x")
    results, errors = batch_rename.apply([plan, gone])
    assert results[0].new.name == "我自己取的名字 _ 有斜線.mp4"  # 不合法字元被替換
    assert errors == [(music / "不存在.mp4", "檔案已不存在（可能已被移動或刪除）")]


def test_undo_skips_when_original_name_reused(music):
    results, _ = batch_rename.apply(batch_rename.scan(music, recursive=False))
    (music / f"{MESSY}.mp4").write_bytes(b"new file with old name")
    errors = batch_rename.undo(results)
    assert errors and "已被使用" in errors[0][1]
    assert (music / f"{MESSY}.mp4").read_bytes() == b"new file with old name"
    assert (music / f"{CLEAN}.mp4").read_bytes() == b"video"
