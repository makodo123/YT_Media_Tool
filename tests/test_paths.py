import threading

import pytest

from yt_media_tool.utils import paths
from yt_media_tool.utils.paths import FileNameReserver, sanitize_filename


@pytest.mark.parametrize("raw,expected", [
    ('a<b>c:d"e/f\\g|h?i*j', "a_b_c_d_e_f_g_h_i_j"),
    ("  多個   空白  ", "多個 空白"),
    ("結尾的點...", "結尾的點"),
    ("CON", "_CON"),
    ("com1.backup", "_com1.backup"),
    ("", "untitled"),
    ("...", "untitled"),
    ("tab\there\x00", "tab_here_"),
])
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_limits_length():
    assert len(sanitize_filename("字" * 500)) == paths.MAX_STEM_LENGTH


def test_existing_file_is_never_overwritten(tmp_path):
    (tmp_path / "影片.mp4").write_bytes(b"user file")
    (tmp_path / "影片 (1).mp4").write_bytes(b"user file 2")
    reserver = FileNameReserver()
    path = reserver.reserve(tmp_path, "影片", "mp4")
    assert path.name == "影片 (2).mp4"
    assert (tmp_path / "影片.mp4").read_bytes() == b"user file"


def test_reservations_are_unique_across_threads(tmp_path):
    reserver = FileNameReserver()
    results = []
    lock = threading.Lock()

    def worker():
        p = reserver.reserve(tmp_path, "same", ".mp3")
        with lock:
            results.append(p)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({p.name for p in results}) == 20


def test_release_allows_reuse(tmp_path):
    reserver = FileNameReserver()
    first = reserver.reserve(tmp_path, "x", "mp4")
    assert reserver.is_reserved(first)
    assert reserver.reserve(tmp_path, "x", "mp4").name == "x (1).mp4"
    reserver.release(first)
    assert reserver.reserve(tmp_path, "x", "mp4").name == "x.mp4"


def test_app_data_dir_uses_override(isolated_app_data):
    assert paths.app_data_dir() == isolated_app_data
    assert paths.database_path().parent == isolated_app_data
    assert paths.log_dir().parent == isolated_app_data


def test_app_data_dir_on_windows_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("YTMT_DATA_DIR")
    monkeypatch.setattr(paths, "is_windows", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert paths.app_data_dir() == tmp_path / "Local" / "YT_Media_Tool"


def test_data_dir_is_not_inside_bundle(monkeypatch, tmp_path):
    """打包後資料不得寫入 EXE 所在目錄。"""
    monkeypatch.delenv("YTMT_DATA_DIR")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert paths.bundle_dir() not in paths.app_data_dir().parents


def test_job_object_is_noop_off_windows(monkeypatch):
    from yt_media_tool.utils import win_job

    monkeypatch.setattr(win_job.sys, "platform", "linux")
    assert win_job.kill_children_on_exit() is False


def test_app_mutex_is_noop_off_windows(monkeypatch):
    from yt_media_tool.utils import win_job

    monkeypatch.setattr(win_job.sys, "platform", "linux")
    assert win_job.create_app_mutex() is False
