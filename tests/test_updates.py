"""新版本檢查（不連線網路，以假的 opener 模擬 GitHub API）。"""

import io
import json

import pytest

from yt_media_tool.core import updates


@pytest.mark.parametrize(("text", "expected"), [
    ("v2.4.0", (2, 4, 0)), ("2.10.1", (2, 10, 1)), (" v3.0.0 ", (3, 0, 0)),
    ("v2.4.0-beta.1", None), ("latest", None), ("", None), (None, None),
])
def test_parse_version(text, expected):
    assert updates.parse_version(text) == expected


def test_is_newer_compares_numbers_not_strings():
    assert updates.is_newer("2.10.0", "2.9.9")
    assert not updates.is_newer("2.3.0", "2.3.0")
    assert not updates.is_newer("2.2.9", "2.3.0")
    assert not updates.is_newer("garbage", "2.3.0")


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


def test_fetch_latest_version_reads_tag_name():
    seen = {}

    def opener(request, timeout):
        seen["url"], seen["timeout"] = request.full_url, timeout
        seen["agent"] = request.get_header("User-agent")
        return _Response(json.dumps({"tag_name": "v9.8.7", "html_url": "https://evil.example"}).encode())

    assert updates.fetch_latest_version(timeout=5, opener=opener) == "9.8.7"
    assert seen["url"] == updates.LATEST_RELEASE_API and seen["timeout"] == 5
    assert seen["agent"].startswith("YT-Media-Tool/")


@pytest.mark.parametrize("payload", [{"tag_name": "nightly"}, {"message": "Not Found"}, ["x"]])
def test_fetch_latest_version_ignores_unexpected_payload(payload):
    assert updates.fetch_latest_version(opener=lambda request, timeout: _Response(json.dumps(payload).encode())) is None


# ---- 下載與驗證（假的 opener，不連線網路） ----
import hashlib  # noqa: E402
import threading  # noqa: E402

SETUP_BYTES = b"MZ fake installer " * 50_000
SETUP_SHA = hashlib.sha256(SETUP_BYTES).hexdigest()


class _Streaming(_Response):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


def make_opener(files: dict[str, bytes], log: list | None = None):
    def opener(request, timeout):
        if log is not None:
            log.append(request.full_url)
        if request.full_url not in files:
            raise OSError("404 Not Found")
        return _Streaming(files[request.full_url])
    return opener


def release(digest=SETUP_SHA):
    return updates.LatestRelease("9.9.9", "YT_Media_Tool-9.9.9-win64-setup.exe", digest)


def server(setup=SETUP_BYTES, sha=SETUP_SHA):
    r = release()
    return {r.setup_url: setup, r.sha256_url: f"{sha}  {r.setup_name}\n".encode()}


def test_fetch_latest_release_reads_digest_and_builds_fixed_urls():
    payload = {"tag_name": "v9.9.9", "html_url": "https://evil.example",
               "assets": [{"name": "YT_Media_Tool-9.9.9-win64-setup.exe", "digest": f"sha256:{SETUP_SHA}",
                           "browser_download_url": "https://evil.example/setup.exe"}]}
    r = updates.fetch_latest_release(opener=lambda request, timeout: _Response(json.dumps(payload).encode()))
    assert (r.version, r.setup_digest) == ("9.9.9", SETUP_SHA)
    assert r.setup_url == ("https://github.com/makodo123/YT_Media_Tool/releases/download/v9.9.9/"
                           "YT_Media_Tool-9.9.9-win64-setup.exe")  # 不採用 API 回傳的連結


def test_download_update_verifies_and_reuses(tmp_path):
    progress, calls = [], []
    (tmp_path / "YT_Media_Tool-9.9.8-win64-setup.exe").write_bytes(b"old")
    path = updates.download_update(release(), tmp_path, progress.append, opener=make_opener(server(), calls))
    assert path.read_bytes() == SETUP_BYTES and progress[-1] == 100.0
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]  # 舊版與暫存檔已清除
    calls.clear()
    assert updates.download_update(release(), tmp_path, opener=make_opener(server(), calls)) == path
    assert calls == [release().sha256_url]  # 已下載且檢查碼正確：不重新下載


@pytest.mark.parametrize(("files", "rel", "message"), [
    (server(sha="0" * 64), release(), "不一致"),  # .sha256 與 GitHub digest 不同
    (server(setup=SETUP_BYTES[:-10]), release(digest=None), "檢查碼不符"),  # 下載不完整
    (server(sha="not-a-hash"), release(), "格式不正確"),
])
def test_download_update_rejects_bad_files(tmp_path, files, rel, message):
    with pytest.raises(updates.UpdateError, match=message):
        updates.download_update(rel, tmp_path, opener=make_opener(files))
    assert not any(p.suffix in (".exe", ".part") for p in tmp_path.iterdir())


def test_download_update_can_be_cancelled(tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(updates.UpdateCancelledError):
        updates.download_update(release(), tmp_path, cancel=cancel, opener=make_opener(server()))
    assert list(tmp_path.iterdir()) == []


def test_only_github_https_urls_are_requested():
    with pytest.raises(ValueError):
        updates._request("http://github.com/x")
    with pytest.raises(ValueError):
        updates._request("https://evil.example/x")


def test_is_installed_build(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.paths, "is_frozen", lambda: True)
    monkeypatch.setattr(updates.paths, "executable_dir", lambda: tmp_path)
    assert not updates.is_installed_build()  # 免安裝版
    (tmp_path / "unins000.exe").write_bytes(b"x")
    assert updates.is_installed_build()
    monkeypatch.setattr(updates.paths, "is_frozen", lambda: False)
    assert not updates.is_installed_build()  # 開發環境


def test_launch_installer_breaks_away_from_job_and_logs(tmp_path, monkeypatch):
    import os
    import subprocess

    calls, order = [], []
    monkeypatch.setattr(updates.sys, "platform", "win32")
    monkeypatch.setattr(updates, "updates_dir", lambda: tmp_path)
    monkeypatch.setattr(updates.win_job, "allow_children_to_outlive", lambda: order.append("outlive") or True)
    monkeypatch.setattr(updates.win_job, "release_app_mutex", lambda: order.append("mutex"))

    def popen(args, creationflags=0, close_fds=True):
        calls.append((args, creationflags))
        if creationflags & updates.CREATE_BREAKAWAY_FROM_JOB:
            raise PermissionError("外層 Job 不允許脫離")  # 模擬被拒絕：改為一般啟動
        return object()

    monkeypatch.setattr(subprocess, "Popen", popen)
    log_file = updates.launch_installer(tmp_path / "setup.exe")
    assert order == ["outlive", "mutex"]  # 啟動前先取消子程序終止並釋放 mutex
    assert log_file == tmp_path / "install.log"
    (first_args, first_flags), (second_args, second_flags) = calls
    assert first_flags & updates.CREATE_BREAKAWAY_FROM_JOB and not second_flags & updates.CREATE_BREAKAWAY_FROM_JOB
    assert first_args == second_args
    assert first_args[0] == str(tmp_path / "setup.exe")
    assert {"/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RESTARTAPP=1", f"/WAITPID={os.getpid()}",
            f"/LOG={tmp_path / 'install.log'}"} <= set(first_args)


# ---- GitHub API 額度用完時改用 Releases 網頁 ----

class _PageResponse(_Response):
    def __init__(self, url):
        super().__init__(b"<html></html>")
        self._url = url

    def geturl(self):
        return self._url


def _api_then_page(api_error, page_url=None, calls=None):
    import urllib.error

    def opener(request, timeout):
        if calls is not None:
            calls.append(request.full_url)
        if request.full_url == updates.LATEST_RELEASE_API:
            raise api_error
        assert request.full_url == updates.RELEASES_PAGE
        if page_url is None:
            raise urllib.error.URLError("offline")
        return _PageResponse(page_url)
    return opener


def _rate_limit():
    import urllib.error

    return urllib.error.HTTPError(updates.LATEST_RELEASE_API, 403, "rate limit exceeded", {}, None)


def test_rate_limited_api_falls_back_to_releases_page():
    calls = []
    opener = _api_then_page(_rate_limit(), "https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.9.0", calls)
    release = updates.fetch_latest_release(opener=opener)
    assert release == updates.LatestRelease("2.9.0", "YT_Media_Tool-2.9.0-win64-setup.exe", None)
    assert calls == [updates.LATEST_RELEASE_API, updates.RELEASES_PAGE]
    assert release.setup_url == ("https://github.com/makodo123/YT_Media_Tool/releases/download/v2.9.0/"
                                 "YT_Media_Tool-2.9.0-win64-setup.exe")


def test_page_fallback_still_verifies_sha256(tmp_path):
    rel = release(digest=None)  # 網頁方式沒有 API 的檢查碼，只靠 .sha256 檔
    with pytest.raises(updates.UpdateError, match="檢查碼不符"):
        updates.download_update(rel, tmp_path, opener=make_opener(server(setup=b"tampered")))
    assert updates.download_update(rel, tmp_path, opener=make_opener(server())).read_bytes() == SETUP_BYTES


@pytest.mark.parametrize("url", [
    "https://github.com/makodo123/YT_Media_Tool/releases",  # 還沒有任何正式版
    "https://github.com/someone/else/releases/tag/v9.9.9",
    "https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.9.0-beta.1",
])
def test_page_fallback_ignores_unexpected_redirects(url):
    assert updates.fetch_latest_release(opener=_api_then_page(_rate_limit(), url)) is None


def test_both_failing_reports_friendly_message():
    import urllib.error

    with pytest.raises(updates.UpdateCheckError, match="GitHub 暫時限制查詢次數"):
        updates.fetch_latest_release(opener=_api_then_page(_rate_limit()))
    with pytest.raises(updates.UpdateCheckError, match="無法連線到 GitHub"):
        updates.fetch_latest_release(opener=_api_then_page(urllib.error.URLError("offline")))
