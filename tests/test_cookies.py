from pathlib import Path

import pytest

from tests.fakes import FakeYDL
from tests.test_downloader import INFO, TOOLS, fake_probe, make_task
from yt_media_tool.core.converter import JsRuntimeInfo
from yt_media_tool.core.cookies import CookieConfig, CookieFileError, ydl_cookie_options
from yt_media_tool.core.downloader import TEMP_ROOT_NAME, CancelToken, Downloader
from yt_media_tool.core.errors import explain_error
from yt_media_tool.storage.settings import AppSettings, SettingsStore

COOKIE_TEXT = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret\n"


def test_no_cookies_by_default(tmp_path):
    assert ydl_cookie_options(CookieConfig(), tmp_path) == {}
    assert not CookieConfig().enabled


@pytest.mark.parametrize("browser", ["firefox", "chrome", "edge"])
def test_browser_cookies(tmp_path, browser):
    assert ydl_cookie_options(CookieConfig(browser), tmp_path) == {"cookiesfrombrowser": (browser,)}


def test_cookie_file_is_copied_not_used_directly(tmp_path):
    original = tmp_path / "my_cookies.txt"
    original.write_text(COOKIE_TEXT, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    opts = ydl_cookie_options(CookieConfig("file", str(original)), work)
    copy = Path(opts["cookiefile"])
    assert copy.parent == work and copy != original
    assert copy.read_text(encoding="utf-8") == COOKIE_TEXT


@pytest.mark.parametrize("path", ["", "Z:/does/not/exist/cookies.txt"])
def test_missing_cookie_file_has_clear_message(tmp_path, path):
    with pytest.raises(CookieFileError) as info:
        ydl_cookie_options(CookieConfig("file", path), tmp_path)
    assert "設定 → YouTube 登入資訊" in explain_error(info.value)


def test_downloader_uses_copy_and_removes_it(tmp_path):
    original = tmp_path / "cookies.txt"
    original.write_text(COOKIE_TEXT, encoding="utf-8")
    captured = []

    def factory(params):
        captured.append(params)
        # 模擬 yt-dlp 結束時寫回 cookies：只能寫到副本
        Path(params["cookiefile"]).write_text(COOKIE_TEXT + "# updated\n", encoding="utf-8")
        return FakeYDL(params, INFO)

    out = tmp_path / "out"
    d = Downloader(tools_provider=lambda: TOOLS, js_runtime_provider=JsRuntimeInfo, ydl_factory=factory,
                   probe=fake_probe, cookies_provider=lambda: CookieConfig("file", str(original)))
    d.download(make_task(out), CancelToken(), lambda u: None)
    used = {p["cookiefile"] for p in captured}
    assert len(used) == 1
    copy = Path(used.pop())
    assert copy.parent.parent.name == TEMP_ROOT_NAME  # 位於任務暫存資料夾
    assert not copy.exists()  # 任務結束後隨暫存資料夾刪除
    assert original.read_text(encoding="utf-8") == COOKIE_TEXT  # 原檔未被修改


def test_downloader_browser_cookies_in_all_requests(tmp_path):
    captured = []

    def factory(params):
        captured.append(params)
        return FakeYDL(params, INFO)

    d = Downloader(tools_provider=lambda: TOOLS, js_runtime_provider=JsRuntimeInfo, ydl_factory=factory,
                   probe=fake_probe, cookies_provider=lambda: CookieConfig("firefox"))
    d.download(make_task(tmp_path), CancelToken(), lambda u: None)
    assert len(captured) == 2  # 取得資訊 + 下載
    assert all(p["cookiesfrombrowser"] == ("firefox",) for p in captured)


def test_playlist_extraction_uses_cookies(tmp_path):
    original = tmp_path / "cookies.txt"
    original.write_text(COOKIE_TEXT, encoding="utf-8")
    captured = []

    def factory(params):
        captured.append(params)
        return FakeYDL(params, {"title": "清單", "entries": []})

    d = Downloader(tools_provider=lambda: TOOLS, js_runtime_provider=JsRuntimeInfo, ydl_factory=factory,
                   cookies_provider=lambda: CookieConfig("file", str(original)))
    d.extract_playlist("https://www.youtube.com/playlist?list=PLxxxxxxxxxx")
    copy = Path(captured[0]["cookiefile"])
    assert copy != original and not copy.exists()


def test_bot_check_message_points_to_cookie_setting():
    from yt_dlp.utils import DownloadError

    exc = DownloadError("ERROR: [youtube] aZHAWKSQXH4: Sign in to confirm you’re not a bot. "
                        "Use --cookies-from-browser or --cookies for the authentication.")
    message = explain_error(exc)
    assert "登入以確認不是機器人" in message and "設定 → YouTube 登入資訊" in message


@pytest.mark.parametrize("raw", [
    "ERROR: Failed to decrypt with DPAPI. See https://github.com/yt-dlp/yt-dlp/issues/10927",
    "ERROR: Could not copy Chrome cookie database. See https://github.com/yt-dlp/yt-dlp/issues/7271",
    "ERROR: could not find firefox cookies database in C:/Users/x/AppData/Roaming/Mozilla/Firefox/Profiles",
])
def test_browser_cookie_errors_explained(raw):
    message = explain_error(RuntimeError(raw))
    assert "無法讀取瀏覽器的登入資訊" in message and "Firefox" in message


def test_cookie_settings_persist_and_validate(db):
    store = SettingsStore(db)
    saved = store.save(AppSettings(cookies_source="file", cookies_file="D:/cookies.txt"))
    loaded = store.load()
    assert loaded.cookie_config() == CookieConfig("file", "D:/cookies.txt") == saved.cookie_config()
    db.set_setting("settings.cookies_source", "safari-on-windows")
    assert store.load().cookies_source == "none"


def test_real_ytdlp_browser_cookie_failure_is_explained(monkeypatch, tmp_path):
    """yt-dlp 找不到瀏覽器 cookies 時會包著 FileNotFoundError，仍須顯示 cookies 說明而非一般檔案錯誤。"""
    import yt_dlp

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(Exception) as info:
        with yt_dlp.YoutubeDL({"quiet": True, "cookiesfrombrowser": ("chrome",)}) as ydl:
            _ = ydl.cookiejar  # 觸發載入 cookies
    assert "無法讀取瀏覽器的登入資訊" in explain_error(info.value)
