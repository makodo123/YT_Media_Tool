import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_dist", ROOT / "scripts" / "verify_dist.py")
verify_dist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_dist)
SUFFIX = ".exe" if sys.platform.startswith("win") else ""


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="需要 FFmpeg")
def test_ffmpeg_functional_checks_pass_with_working_ffmpeg():
    directory = Path(shutil.which("ffmpeg")).parent
    if not (directory / f"ffprobe{SUFFIX}").exists():
        pytest.skip("ffmpeg 與 ffprobe 不在同一資料夾")
    checks = verify_dist.ffmpeg_functional_checks(directory, SUFFIX)
    assert checks and all(ok for _, ok in checks), checks


def test_ffmpeg_functional_checks_fail_when_missing(tmp_path):
    # 空資料夾：模擬缺少執行檔或 DLL，檢查必須失敗而不是拋出例外
    checks = verify_dist.ffmpeg_functional_checks(tmp_path, SUFFIX)
    assert checks and not all(ok for _, ok in checks)


def test_size_report_lists_largest_files(tmp_path):
    dist = tmp_path / "YT_Media_Tool"
    (dist / "_internal" / "ffmpeg").mkdir(parents=True)
    (dist / "_internal" / "ffmpeg" / "avcodec.dll").write_bytes(b"0" * 2048)
    (dist / "YT_Media_Tool.exe").write_bytes(b"0" * 1024)
    report = verify_dist.size_report(dist)
    assert "總計" in report and "ffmpeg" in report and "_internal/ffmpeg/avcodec.dll" in report


def test_duplicated_ffmpeg_dll_detected(tmp_path, monkeypatch, capsys):
    dist = tmp_path / "YT_Media_Tool"
    internal = dist / "_internal"
    (internal / "ffmpeg").mkdir(parents=True)
    monkeypatch.setattr(verify_dist, "ffmpeg_functional_checks", lambda d, s: [])

    verify_dist.main([str(dist), "--expect-ffmpeg"])
    assert "[OK] FFmpeg DLL 未重複打包" in capsys.readouterr().out

    (internal / "avcodec-63.dll").write_bytes(b"0")
    verify_dist.main([str(dist), "--expect-ffmpeg"])
    assert "[FAIL] FFmpeg DLL 未重複打包（重複：avcodec-63.dll）" in capsys.readouterr().out
