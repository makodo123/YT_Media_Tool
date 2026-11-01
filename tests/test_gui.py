"""GUI 測試（pytest-qt，offscreen 平台）。使用 FakeDownloader，不連線網路。"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox

from tests.fakes import FakeDownloader
from yt_media_tool.app_context import create_context
from yt_media_tool.core.converter import ToolInfo
from yt_media_tool.core.queue_manager import TaskSpec
from yt_media_tool.core.task_models import MediaFormat, TaskStatus
from yt_media_tool.gui.main_window import MainWindow
from yt_media_tool.gui.queue_table import COL_QUALITY, COL_STATUS, COLUMNS
from yt_media_tool.gui.settings_dialog import SettingsDialog
from yt_media_tool.storage.database import Database

BLOCK = "https://www.youtube.com/watch?v=block000001"
PLAYLIST = "https://www.youtube.com/playlist?list=PLabcdefghij123456"


class Dialogs:
    """攔截 QMessageBox，記錄訊息並回傳預設答案。"""

    def __init__(self, monkeypatch, answer=QMessageBox.StandardButton.Yes):
        self.messages: list[tuple[str, str]] = []
        self.answer = answer
        for name in ("information", "warning", "critical"):
            monkeypatch.setattr(QMessageBox, name, self._record(name))
        monkeypatch.setattr(QMessageBox, "question", self._question)

    def _record(self, kind):
        def fn(parent, title, text, *args, **kwargs):
            self.messages.append((kind, f"{title}\n{text}"))
            return QMessageBox.StandardButton.Ok
        return fn

    def _question(self, parent, title, text, *args, **kwargs):
        self.messages.append(("question", f"{title}\n{text}"))
        return self.answer

    def text(self) -> str:
        return "\n".join(m for _, m in self.messages)


@pytest.fixture
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


@pytest.fixture
def fake():
    return FakeDownloader()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "gui.sqlite3"


@pytest.fixture
def window(qtbot, tmp_path, db_path, fake, dialogs):
    ctx = create_context(db_path=db_path, downloader=fake, start_paused=True)
    ctx.tools = ToolInfo(ffmpeg=Path("/fake/ffmpeg"), ffprobe=Path("/fake/ffprobe"), source="test")
    ctx.settings.download_dir = str(tmp_path / "downloads")
    ctx.settings.auto_paste_clipboard = False  # 避免剪貼簿內容影響其他測試；剪貼簿測試中再開啟
    win = MainWindow(ctx)
    qtbot.addWidget(win)
    win.show()
    yield win
    if not win._closing:
        fake.release(BLOCK)
        win.close()


def rows(win):
    return win.table.queue_model.rowCount()


def test_window_title_columns_and_theme(window):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from yt_media_tool.gui.theme import apply_dark_theme

    from yt_media_tool import __version__

    assert window.windowTitle() == f"YT Media Tool v{__version__}"  # 標題版本號與實際版本一致
    model = window.table.queue_model
    assert [model.headerData(i, Qt.Orientation.Horizontal) for i in range(len(COLUMNS))] == \
        ["編號", "影片名稱", "格式", "品質", "進度", "速度", "剩餘時間", "狀態", "操作"]
    apply_dark_theme(QApplication.instance())
    assert QApplication.instance().palette().window().color().lightness() < 80


def test_quality_options_follow_format(window):
    window.mp4_radio.setChecked(True)
    assert [window.quality_combo.itemText(i) for i in range(window.quality_combo.count())] == \
        ["720p", "1080p", "最高可用解析度"]
    window.mp3_radio.setChecked(True)
    assert [window.quality_combo.itemData(i) for i in range(window.quality_combo.count())] == ["128", "192", "320"]


def test_add_urls_dedupes_and_reports_invalid(window, dialogs, qtbot):
    window.url_input.setPlainText("\n".join([
        "https://youtu.be/aaaaaaaaaaa",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "https://www.youtube.com/shorts/bbbbbbbbbbb",
        "https://example.com/video",
    ]))
    window.add_from_input()
    assert rows(window) == 2
    assert "不支援的網站" in dialogs.text()
    assert "重複" in dialogs.text()
    assert window.url_input.toPlainText() == ""
    tasks = window.ctx.queue.tasks()
    assert tasks[1].url == "https://www.youtube.com/shorts/bbbbbbbbbbb"


def test_all_invalid_shows_warning_and_adds_nothing(window, dialogs):
    window.url_input.setPlainText("https://www.youtube.com/@channel\nnot-a-url")
    window.add_from_input()
    assert rows(window) == 0
    assert "頻道" in dialogs.text()


def test_playlist_url_opens_picker_with_all_checked(window, qtbot, monkeypatch):
    shown = []

    def choose(groups, *_):
        shown.append(groups)
        return [[e.url for e in groups[0].entries[:2]]]  # 使用者只勾選前兩部

    monkeypatch.setattr(window, "choose_playlist_entries", choose)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 2, timeout=5000)
    assert len(shown[0]) == 1 and shown[0][0].preselect_video_id is None
    assert len(shown[0][0].entries) == 3
    # 存到以清單名稱命名的子資料夾
    folder = str(Path(window.folder_edit.text()) / "清單")
    assert {t.output_dir for t in window.ctx.queue.tasks()} == {folder}


def test_playlist_subfolder_can_be_disabled(window, qtbot, monkeypatch):
    window.ctx.settings.playlist_subfolder = False
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: [[groups[0].entries[0].url]])
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 1, timeout=5000)
    assert window.ctx.queue.tasks()[0].output_dir == str(Path(window.folder_edit.text()))


def test_playlist_picker_cancel_adds_nothing(window, qtbot, monkeypatch, dialogs):
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: None)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: not window._busy_expanding, timeout=5000)
    assert rows(window) == 0
    assert "已取消加入播放清單中的影片" in dialogs.text()


def test_video_in_playlist_preselects_pasted_video(window, qtbot, monkeypatch):
    shown = []

    def choose(groups, *_):
        shown.append(groups)
        return [[e.url for e in groups[0].entries if e.video_id == groups[0].preselect_video_id]]

    monkeypatch.setattr(window, "choose_playlist_entries", choose)
    window.url_input.setPlainText("https://www.youtube.com/watch?v=vid00000001&list=PLabcdefghij123456")
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 1, timeout=5000)
    assert shown[0][0].preselect_video_id == "vid00000001"
    task = window.ctx.queue.tasks()[0]
    assert task.url == "https://www.youtube.com/watch?v=vid00000001"
    assert task.output_dir == str(Path(window.folder_edit.text()))  # 只下載貼上的影片：不另建子資料夾


def test_video_in_playlist_whole_list_goes_to_subfolder(window, qtbot, monkeypatch):
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: [[e.url for e in groups[0].entries]])
    window.url_input.setPlainText("https://www.youtube.com/watch?v=vid00000001&list=PLabcdefghij123456")
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 3, timeout=5000)
    assert {t.output_dir for t in window.ctx.queue.tasks()} == {str(Path(window.folder_edit.text()) / "清單")}


def test_pasted_video_missing_from_playlist_is_listed_first(window, qtbot, monkeypatch):
    shown = []
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: shown.append(groups) or [[]])
    window.url_input.setPlainText("https://www.youtube.com/watch?v=aaaaaaaaaaa&list=PLabcdefghij123456")
    window.add_from_input()
    qtbot.waitUntil(lambda: bool(shown), timeout=5000)
    first = shown[0][0].entries[0]
    assert (first.video_id, first.url) == ("aaaaaaaaaaa", "https://www.youtube.com/watch?v=aaaaaaaaaaa")


def test_playlist_read_failure_falls_back_to_single_video(window, qtbot, monkeypatch, fake, dialogs):
    def broken(url, limit=500):
        raise RuntimeError("boom")

    monkeypatch.setattr(fake, "extract_playlist", broken)
    window.url_input.setPlainText("https://www.youtube.com/watch?v=aaaaaaaaaaa&list=PLabcdefghij123456")
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 1, timeout=5000)
    assert "無法讀取播放清單" in dialogs.text()


def test_playlist_picker_dialog(qtbot):
    from PySide6.QtCore import Qt

    from yt_media_tool.core.downloader import PlaylistEntry
    from yt_media_tool.gui.playlist_dialog import PlaylistGroup, PlaylistPickerDialog

    def entries(prefix):
        return [PlaylistEntry(f"https://www.youtube.com/watch?v={prefix}{i:010d}", f"{prefix} 歌曲 {i}",
                              f"{prefix}{i:010d}", 200.0) for i in range(3)]

    dialog = PlaylistPickerDialog([PlaylistGroup("清單 A", entries("a")),
                                   PlaylistGroup("清單 B", entries("b"), preselect_video_id="b0000000001")], 500)
    qtbot.addWidget(dialog)
    assert dialog.selected_urls() == [e.url for e in entries("a")] + ["https://www.youtube.com/watch?v=b0000000001"]
    assert dialog.selected_by_group() == [[e.url for e in entries("a")], ["https://www.youtube.com/watch?v=b0000000001"]]
    assert dialog.ok_button.text() == "加入 4 部" and dialog.count_label.text() == "已選 4 / 6 部"

    dialog.search.setText("歌曲 2")  # 搜尋後「全不選」只影響符合的影片
    dialog._set_visible_checked(False)
    assert dialog.selected_urls() == ["https://www.youtube.com/watch?v=a0000000000",
                                      "https://www.youtube.com/watch?v=a0000000001",
                                      "https://www.youtube.com/watch?v=b0000000001"]
    dialog.search.clear()
    dialog._set_visible_checked(False)
    assert dialog.selected_urls() == [] and not dialog.ok_button.isEnabled()

    group_b = dialog.tree.topLevelItem(1)  # 勾選清單本身＝整個清單
    group_b.setCheckState(0, Qt.CheckState.Checked)
    assert len(dialog.selected_urls()) == 3 and dialog.ok_button.text() == "加入 3 部"
    assert group_b.child(0).text(2) == "03:20"


def test_missing_ffmpeg_blocks_adding_with_guide(window, dialogs, monkeypatch):
    window.ctx.tools = ToolInfo()
    monkeypatch.setattr(window.ctx, "refresh_tools", lambda: ToolInfo())
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window.add_from_input()
    assert rows(window) == 0
    assert "找不到 FFmpeg" in dialogs.text()


def test_progress_updates_reach_table_without_blocking(window, qtbot, fake):
    window.ctx.queue.resume()
    window.url_input.setPlainText(BLOCK)
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: model.task_at(0) and model.task_at(0).status is TaskStatus.DOWNLOADING, timeout=5000)
    qtbot.waitUntil(lambda: model.task_at(0).progress > 5, timeout=5000)
    assert model.data(model.index(0, COL_STATUS)) in ("準備中", "下載中")  # 狀態欄顯示目前階段
    fake.release(BLOCK)
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.COMPLETED, timeout=5000)
    assert model.task_at(0).progress == 100
    assert model.data(model.index(0, COL_QUALITY)) == "1080p → 720p ⚠"
    assert "完成 1" in window.overall_label.text()


def test_row_actions_cancel_and_retry(window, qtbot, fake):
    window.ctx.queue.resume()
    window.url_input.setPlainText(BLOCK)
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.DOWNLOADING, timeout=5000)
    task_id = model.task_at(0).id
    window._on_row_action(task_id, "cancel")
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.CANCELLED, timeout=5000)
    fake.release(BLOCK)
    window._on_row_action(task_id, "retry")
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.COMPLETED, timeout=5000)


def test_cancel_all_and_clear_completed_buttons(window, qtbot, fake):
    queue = window.ctx.queue
    queue.add_tasks([TaskSpec("https://youtu.be/aaaaaaaaaaa", MediaFormat.MP4, "720", window.folder_edit.text())])
    queue.resume()
    qtbot.waitUntil(lambda: queue.progress().completed == 1, timeout=5000)
    queue.pause()
    queue.add_tasks([TaskSpec(BLOCK, MediaFormat.MP3, "192", window.folder_edit.text())])
    window.cancel_all()
    qtbot.waitUntil(lambda: queue.progress().cancelled == 1, timeout=5000)
    window.clear_button.click()
    qtbot.waitUntil(lambda: rows(window) == 1)


def test_close_while_downloading_cleans_up_and_requeues(window, qtbot, fake, db_path, dialogs):
    queue = window.ctx.queue
    queue.resume()
    window.url_input.setPlainText(BLOCK)
    window.add_from_input()
    qtbot.waitUntil(lambda: fake.running == 1, timeout=5000)
    task_id = queue.tasks()[0].id

    dialogs.answer = QMessageBox.StandardButton.No
    window.close()
    assert window.isVisible()  # 使用者選擇不結束
    assert fake.running == 1

    dialogs.answer = QMessageBox.StandardButton.Yes
    window.close()
    assert not window.isVisible()
    assert fake.running == 0  # 工作執行緒已停止
    assert not queue.has_active_tasks()
    reopened = Database(db_path)
    try:
        assert reopened.get_task(task_id).status is TaskStatus.WAITING  # 下次開啟時恢復
    finally:
        reopened.close()


def test_restore_queue_on_restart(qtbot, tmp_path, db_path, dialogs):
    db = Database(db_path)
    from yt_media_tool.core.task_models import DownloadTask

    db.insert_task(DownloadTask(url="https://youtu.be/aaaaaaaaaaa", media_format=MediaFormat.MP3, quality="320",
                                output_dir=str(tmp_path), status=TaskStatus.DOWNLOADING))
    db.close()
    fake = FakeDownloader()
    ctx = create_context(db_path=db_path, downloader=fake, start_paused=True)
    win = MainWindow(ctx)
    qtbot.addWidget(win)
    dialogs.answer = QMessageBox.StandardButton.No
    assert win.restore_queue(ask=True) == 1
    assert ctx.queue.is_paused
    assert win.table.queue_model.rowCount() == 1
    assert win.pause_button.text() == "開始佇列"
    win.pause_button.click()
    qtbot.waitUntil(lambda: ctx.queue.progress().completed == 1, timeout=5000)
    win.close()


def test_settings_dialog_returns_validated_settings(qtbot, window):
    dialog = SettingsDialog(window.ctx.settings, window)
    qtbot.addWidget(dialog)
    dialog.max_concurrent.setValue(3)
    dialog.default_format.setCurrentIndex(dialog.default_format.findData("mp3"))
    dialog.mp3_quality.setCurrentIndex(dialog.mp3_quality.findData("320"))
    dialog.keep_history.setChecked(False)
    dialog.embed_metadata.setChecked(False)
    assert dialog.clean_titles.isChecked()  # 預設開啟
    dialog.clean_titles.setChecked(False)
    result = dialog.result_settings()
    assert result.max_concurrent == 3 and result.default_format == "mp3"
    assert result.default_mp3_quality == "320" and result.keep_history is False
    assert result.embed_metadata is False
    assert result.clean_titles is False and result.download_preferences().clean_titles is False
    window.ctx.apply_settings(result)
    assert window.ctx.queue.max_concurrent == 3
    assert window.ctx.queue.keep_history is False


def test_settings_dialog_cookie_options(qtbot, window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    window.ctx.settings.cookies_source = "firefox"
    dialog = SettingsDialog(window.ctx.settings, window)
    qtbot.addWidget(dialog)
    assert dialog.cookies_source.currentData() == "firefox"
    assert [dialog.cookies_source.itemText(i) for i in range(dialog.cookies_source.count())] == \
        ["不使用", "Firefox", "cookies.txt 檔案"]
    # 即使來源是瀏覽器，檔案欄與「瀏覽…」也必須可用
    assert dialog.cookies_file_row.isEnabled()

    # 以「瀏覽…」選擇檔案後，來源自動切換為 cookies.txt 檔案
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(cookie_file), ""))
    dialog._browse_cookies()
    assert dialog.cookies_source.currentData() == "file"
    assert dialog.cookies_file.text() == str(cookie_file)

    result = dialog.result_settings()
    assert result.cookies_source == "file" and result.cookies_file == str(cookie_file)
    window.ctx.apply_settings(result)
    assert "cookies.txt" in window.dependency_report()


def test_typing_cookie_path_switches_source(qtbot, window):
    dialog = SettingsDialog(window.ctx.settings, window)
    qtbot.addWidget(dialog)
    dialog.cookies_source.setCurrentIndex(dialog.cookies_source.findData("firefox"))
    qtbot.keyClicks(dialog.cookies_file, "D:/cookies.txt")
    assert dialog.cookies_source.currentData() == "file"


def test_qt_standard_buttons_are_translated(qtbot):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    from yt_media_tool.gui.i18n import install_qt_translations

    app = QApplication.instance()
    assert install_qt_translations(app)
    # QMessageBox 的「是 / 否」按鈕文字來自 QPlatformTheme 翻譯
    assert QCoreApplication.translate("QPlatformTheme", "&Yes") != "&Yes"


def _add_waiting(window, count):
    urls = [f"https://www.youtube.com/watch?v=batch{i:06d}" for i in range(count)]
    window.ctx.queue.add_tasks([TaskSpec(u, MediaFormat.MP4, "720", window.folder_edit.text()) for u in urls])
    return urls


def test_remove_selected_batch(window, dialogs, qtbot):
    _add_waiting(window, 3)  # 佇列暫停中，三筆皆為等待
    assert rows(window) == 3
    assert not window.remove_button.isEnabled()
    window.table.selectAll()
    assert window.remove_button.isEnabled() and window.remove_button.text() == "移除所選（3）"

    dialogs.answer = QMessageBox.StandardButton.No
    assert window.remove_selected() == 0
    assert rows(window) == 3

    dialogs.answer = QMessageBox.StandardButton.Yes
    assert window.remove_selected() == 3
    assert rows(window) == 0
    assert "不會刪除已下載的檔案" in dialogs.text()


def test_remove_selected_skips_running(window, dialogs, qtbot, fake):
    queue = window.ctx.queue
    queue.add_tasks([TaskSpec(BLOCK, MediaFormat.MP4, "720", window.folder_edit.text())])
    _add_waiting(window, 2)
    queue.resume()  # 同時下載數為 1：BLOCK 執行中，其餘兩筆維持等待
    qtbot.waitUntil(lambda: fake.running == 1, timeout=5000)
    window.table.selectAll()
    assert window.remove_button.text() == "移除所選（2）"
    assert window.remove_selected() == 2
    assert [t.url for t in queue.tasks()] == [BLOCK]
    assert "1 筆進行中未移除" in window.statusBar().currentMessage()
    assert "另有 1 筆進行中的任務不會移除" in dialogs.text()


def test_batch_context_menu_applies_to_selection(window, dialogs, qtbot):
    _add_waiting(window, 3)
    window.table.selectAll()
    task = window.table.queue_model.task_at(0)
    labels = [a.text() for a in window.build_context_menu(task).actions() if a.text()]
    assert "取消所選（3 筆）" in labels
    assert "從佇列移除所選（3 筆，不刪除檔案）" in labels

    # 取消所選後，可對所選任務重試
    next(a for a in window.build_context_menu(task).actions() if a.text() == "取消所選（3 筆）").trigger()
    assert all(t.status is TaskStatus.CANCELLED for t in window.ctx.queue.tasks())
    window.table.selectAll()
    labels = [a.text() for a in window.build_context_menu(task).actions() if a.text()]
    assert "重試所選（3 筆）" in labels


def test_single_selection_context_menu_unchanged(window, qtbot):
    _add_waiting(window, 2)
    window.table.selectRow(0)
    labels = [a.text() for a in window.build_context_menu(window.table.queue_model.task_at(0)).actions() if a.text()]
    assert "取消" in labels and "從佇列移除（不刪除檔案）" in labels


@pytest.mark.parametrize("fmt,quality,actual,expected", [
    (MediaFormat.MP4, "720", "", "720p"),
    (MediaFormat.MP4, "720", "720p", "720p"),
    (MediaFormat.MP4, "720", "720p h264/aac", "720p"),
    (MediaFormat.MP4, "1080", "1080p vp9/opus", "1080p"),
    (MediaFormat.MP4, "1080", "720p h264/aac（原始素材無 1080p，可用解析度：360p、720p）", "1080p → 720p ⚠"),
    (MediaFormat.MP4, "720", "720p h264/aac（最高 1080p，可用解析度：360p、720p、1080p）", "720p（最高 1080p）"),
    (MediaFormat.MP4, "720", "720p（最高 1080p，可用解析度：360p、720p、1080p）", "720p（最高 1080p）"),
    (MediaFormat.MP4, "best", "2160p vp9/opus", "最高可用解析度 → 2160p"),
    (MediaFormat.MP4, "1080", "解析度未知", "1080p → 解析度未知"),
    (MediaFormat.MP3, "192", "MP3 192 kbps（原始音源約 130 kbps，輸出位元率高於原始音源，實際音質不會提升）",
     "192 kbps → 130 kbps ⚠"),
    (MediaFormat.MP3, "128", "MP3 128 kbps（原始音源約 130 kbps）", "128 kbps"),
    (MediaFormat.MP3, "320", "MP3 320 kbps（原始音源位元率未知）", "320 kbps"),
])
def test_quality_text_shows_target_once_unless_different(fmt, quality, actual, expected):
    from yt_media_tool.core.task_models import DownloadTask
    from yt_media_tool.gui.queue_table import quality_text

    task = DownloadTask(url="https://youtu.be/aaaaaaaaaaa", media_format=fmt, quality=quality,
                        output_dir="/tmp", actual_quality=actual)
    assert quality_text(task) == expected


@pytest.mark.parametrize(("status", "stage", "expected"), [
    (TaskStatus.PROCESSING, "MP3 轉檔中", "MP3 轉檔中"),
    (TaskStatus.PROCESSING, "", "轉檔中"),
    (TaskStatus.DOWNLOADING, "取得影片資訊中", "取得影片資訊中"),
    (TaskStatus.DOWNLOADING, "下載中", "下載中"),
    (TaskStatus.WAITING, "", "等待中"),
    (TaskStatus.CANCELLED, "", "已取消"),
])
def test_status_text_does_not_repeat_stage(status, stage, expected):
    from yt_media_tool.core.task_models import DownloadTask
    from yt_media_tool.gui.queue_table import status_text

    task = DownloadTask(url="https://youtu.be/aaaaaaaaaaa", media_format=MediaFormat.MP4, quality="1080",
                        output_dir="/tmp", status=status, stage=stage)
    assert status_text(task) == expected


def test_overall_label_counts_waiting_tasks(window):
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa\nhttps://youtu.be/bbbbbbbbbbb")
    window.add_from_input()
    assert "共 2 筆：進行中 0、等待 2、" in window.overall_label.text()


def test_failed_reason_shown_first_in_details(window, qtbot):
    task = window.ctx.queue.add_tasks([TaskSpec(url="https://youtu.be/aaaaaaaaaaa", media_format=MediaFormat.MP4,
                                                quality="1080", output_dir=window.folder_edit.text())])[0]
    task.status, task.error_message = TaskStatus.FAILED, "這是私人影片，無法下載。"
    window.table.queue_model.upsert(task)
    window.table.selectRow(0)
    window._update_details()
    lines = window.details.toPlainText().splitlines()
    assert lines[2:4] == ["失敗原因：", "這是私人影片，無法下載。"]


def test_saving_settings_keeps_current_choices(window, monkeypatch, tmp_path):
    import dataclasses

    import yt_media_tool.gui.main_window as main_window

    window.mp3_radio.setChecked(True)
    window.quality_combo.setCurrentIndex(window.quality_combo.findData("320"))
    window.folder_edit.setText(str(tmp_path / "chosen"))

    class FakeDialog:
        def __init__(self, settings, parent):
            self.settings = settings

        def exec(self):
            return True

        def result_settings(self):
            return dataclasses.replace(self.settings, max_concurrent=3)

    monkeypatch.setattr(main_window, "SettingsDialog", FakeDialog)
    window.open_settings()
    assert window.selected_format() is MediaFormat.MP3
    assert window.quality_combo.currentData() == "320"
    assert window.folder_edit.text() == str(tmp_path / "chosen")
    assert window.ctx.settings.max_concurrent == 3


def test_download_folder_is_remembered(window, tmp_path, db_path):
    from yt_media_tool.storage.settings import SettingsStore

    chosen = tmp_path / "my videos"
    window.folder_edit.setText(str(chosen))
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window.add_from_input()
    assert window.ctx.settings.download_dir == str(chosen)
    assert SettingsStore(window.ctx.db).load().download_dir == str(chosen)


def _history_task(tmp_path, n, status, title="", output="", error="", fmt=MediaFormat.MP3, quality="320"):
    from yt_media_tool.core.task_models import DownloadTask

    return DownloadTask(url=f"https://www.youtube.com/watch?v=hist0000{n:03d}", media_format=fmt, quality=quality,
                        output_dir=str(tmp_path), id=n, title=title, status=status, output_path=output,
                        error_message=error)


def test_history_dialog_shows_file_name_search_and_actions(window, qtbot, tmp_path, monkeypatch, dialogs):
    from yt_media_tool.gui.history_dialog import HistoryDialog
    from yt_media_tool.utils import system_open

    song = tmp_path / "晴天.mp3"
    song.write_bytes(b"x")
    db = window.ctx.db
    db.add_history(_history_task(tmp_path, 1, TaskStatus.COMPLETED, "晴天", str(song)))
    db.add_history(_history_task(tmp_path, 2, TaskStatus.FAILED, "私人影片",
                                 error="這是私人影片，無法下載。\n詳細資訊：x", fmt=MediaFormat.MP4, quality="1080"))
    db.add_history(_history_task(tmp_path, 3, TaskStatus.COMPLETED, "已刪除", str(tmp_path / "gone.mp3")))
    dialog = HistoryDialog(db, window, on_redownload=window.redownload)
    qtbot.addWidget(dialog)

    rows = {dialog.table.item(r, 1).text(): r for r in range(dialog.table.rowCount())}
    assert dialog.table.item(rows["晴天"], 5).text() == "晴天.mp3"  # 只顯示檔名，完整路徑在提示
    assert dialog.table.item(rows["晴天"], 5).toolTip() == str(song)
    assert dialog.table.item(rows["私人影片"], 5).text() == "這是私人影片，無法下載。"

    dialog.search.setText("晴天")
    assert dialog.visible_rows() == [rows["晴天"]]
    dialog.search.clear()

    revealed = []
    monkeypatch.setattr(system_open, "reveal_file", lambda path: revealed.append(path) or True)
    assert dialog.reveal(rows["晴天"]) and revealed == [song]
    assert not dialog.reveal(rows["已刪除"])
    assert "檔案已不存在" in dialogs.text()

    labels = [a.text() for a in dialog.build_context_menu(rows["私人影片"]).actions()]
    assert labels == ["複製網址", "重新下載（以相同格式加入佇列）"]
    window.url_input.setPlainText("https://youtu.be/keepthis01")
    dialog.redownload(rows["私人影片"])
    task = window.ctx.queue.tasks()[0]
    assert (task.url, task.media_format, task.quality, task.title) == (
        "https://www.youtube.com/watch?v=hist0000002", MediaFormat.MP4, "1080", "私人影片")
    assert window.url_input.toPlainText() == "https://youtu.be/keepthis01"  # 不清除使用者正在輸入的網址


def test_drop_urls_appends_to_input(window):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    mime = QMimeData()
    mime.setUrls([QUrl("https://www.youtube.com/watch?v=bbbbbbbbbbb"), QUrl("file:///C:/x.txt")])
    enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
    window.dragEnterEvent(enter)
    assert enter.isAccepted()
    drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier)
    window.dropEvent(drop)
    assert window.url_input.toPlainText() == "https://youtu.be/aaaaaaaaaaa\nhttps://www.youtube.com/watch?v=bbbbbbbbbbb"
    assert "已加入 1 個網址" in window.statusBar().currentMessage()

    text_only = QMimeData()
    text_only.setText("沒有網址")
    enter = QDragEnterEvent(QPoint(1, 1), Qt.DropAction.CopyAction, text_only, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
    enter.ignore()
    window.dragEnterEvent(enter)
    window.dropEvent(QDropEvent(QPointF(1, 1), Qt.DropAction.CopyAction, text_only, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier))
    assert "沒有可辨識的 YouTube 網址" in window.statusBar().currentMessage()


def test_double_click_completed_task_plays_file(window, qtbot, fake, monkeypatch):
    from yt_media_tool.utils import system_open

    played = []
    monkeypatch.setattr(system_open, "_open_with_default_app", lambda path: played.append(path) or True)
    window.ctx.queue.resume()
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.COMPLETED, timeout=5000)
    task = model.task_at(0)
    window.table.doubleClicked.emit(model.index(0, 1))
    assert played == [Path(task.output_path)]
    assert "播放（雙擊）" in [a.text() for a in window.build_context_menu(task).actions()]

    Path(task.output_path).unlink()
    assert not window.play(task)
    assert "檔案已不存在" in window.statusBar().currentMessage()


def test_open_media_only_opens_mp3_and_mp4(tmp_path, monkeypatch):
    from yt_media_tool.utils import system_open

    opened = []
    monkeypatch.setattr(system_open, "_open_with_default_app", lambda path: opened.append(path.name) or True)
    for name in ("a.mp3", "b.MP4", "c.exe", "d.bat"):
        (tmp_path / name).write_bytes(b"x")
        system_open.open_media(tmp_path / name)
    assert not system_open.open_media(tmp_path / "missing.mp3")
    assert opened == ["a.mp3", "b.MP4"]


def test_notify_once_when_whole_queue_finishes(window, qtbot, fake, monkeypatch):
    shown = []
    monkeypatch.setattr(window, "isActiveWindow", lambda: False)
    monkeypatch.setattr(window, "_show_notification", lambda title, message: shown.append((title, message)))
    window.ctx.queue.resume()
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa\nhttps://youtu.be/bbbbbbbbbbb")
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: all(model.task_at(i).status is TaskStatus.COMPLETED for i in range(2)), timeout=5000)
    qtbot.waitUntil(lambda: bool(shown), timeout=3000)
    qtbot.wait(1000)  # 確認不會再發出第二次通知
    assert shown == [("下載完成", "2 部下載完成")]
    assert "佇列已全部完成" in window.statusBar().currentMessage()


def test_no_notification_when_disabled_or_window_active(window, monkeypatch):
    shown = []
    monkeypatch.setattr(window, "_show_notification", lambda title, message: shown.append(message))
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    window.notify_queue_finished(1, 1)
    assert shown == []  # 使用者正在看視窗時只更新狀態列
    assert "1 部下載完成，1 部失敗" in window.statusBar().currentMessage()


def test_playlist_tasks_show_titles_before_download(window, qtbot, monkeypatch):
    seen_destination = []

    def choose(groups, output_dir):
        seen_destination.append(output_dir)
        return [[e.url for e in groups[0].entries]]

    monkeypatch.setattr(window, "choose_playlist_entries", choose)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 3, timeout=5000)
    assert [t.title for t in window.ctx.queue.tasks()] == ["影片 0", "影片 1", "影片 2"]  # 不必等開始下載
    assert seen_destination == [str(Path(window.folder_edit.text()))]


def test_reveal_waiting_task_opens_nearest_existing_folder(window, tmp_path, monkeypatch):
    from yt_media_tool.core.task_models import DownloadTask
    from yt_media_tool.utils import system_open

    opened = []
    monkeypatch.setattr(system_open, "open_folder", lambda folder: opened.append(folder) or True)
    task = DownloadTask(url="https://youtu.be/aaaaaaaaaaa", media_format=MediaFormat.MP3, quality="192",
                        output_dir=str(tmp_path / "清單" / "尚未建立"))
    window._reveal(task)
    assert opened == [tmp_path]  # 子資料夾還沒建立：開啟最近的上層資料夾，不顯示錯誤


def test_playlist_dialog_shows_destination(window, qtbot):
    from PySide6.QtWidgets import QLabel

    from yt_media_tool.core.downloader import PlaylistEntry
    from yt_media_tool.gui.playlist_dialog import PlaylistGroup, PlaylistPickerDialog

    dialog = PlaylistPickerDialog([PlaylistGroup("清單", [PlaylistEntry("https://youtu.be/aaaaaaaaaaa", "歌")])], 500,
                                  window, destination="儲存位置：D:\\音樂\\（清單名稱）")
    qtbot.addWidget(dialog)
    assert any("儲存位置：D:\\音樂" in label.text() for label in dialog.findChildren(QLabel))


def test_settings_dialog_fits_screen(qtbot, window):
    dialog = SettingsDialog(window.ctx.settings, window)
    qtbot.addWidget(dialog)
    available = dialog.screen().availableGeometry().height()
    assert dialog.height() <= available


def test_subtitles_checkbox_only_for_mp4_and_saved(window):
    window.mp4_radio.setChecked(True)
    assert not window.subtitles_check.isHidden()
    window.subtitles_check.setChecked(True)
    assert window.ctx.settings.download_subtitles is True
    from yt_media_tool.storage.settings import SettingsStore

    assert SettingsStore(window.ctx.db).load().download_subtitles is True
    window.mp3_radio.setChecked(True)
    assert window.subtitles_check.isHidden()


def test_settings_dialog_rate_limit(qtbot, window):
    dialog = SettingsDialog(window.ctx.settings, window)
    qtbot.addWidget(dialog)
    assert dialog.rate_limit.text() == "不限制"
    dialog.rate_limit.setValue(2.5)
    assert dialog.result_settings().rate_limit_mbps == 2.5



def test_auto_paste_clipboard_urls(window):
    from PySide6.QtGui import QGuiApplication

    window.ctx.settings.auto_paste_clipboard = True
    window._last_clipboard = None
    clipboard = QGuiApplication.clipboard()
    clipboard.setText("看這個 https://youtu.be/aaaaaaaaaaa 和 https://example.com/x")
    window._last_clipboard = None  # 模擬在其他程式中複製
    assert window.auto_paste_clipboard() == 1
    assert window.url_input.toPlainText() == "https://youtu.be/aaaaaaaaaaa"
    assert "已從剪貼簿帶入 1 個網址" in window.statusBar().currentMessage()
    assert window.auto_paste_clipboard() == 0  # 同一份剪貼簿內容只帶入一次

    window.url_input.clear()
    window._last_clipboard = None
    clipboard.setText("https://www.youtube.com/watch?v=aaaaaaaaaaa")  # 與輸入框中重複 → 不帶入
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window._last_clipboard = None
    assert window.auto_paste_clipboard() == 0

    window.ctx.settings.auto_paste_clipboard = False
    clipboard.setText("https://youtu.be/bbbbbbbbbbb")
    window._last_clipboard = None
    assert window.auto_paste_clipboard() == 0


def test_auto_paste_skips_urls_already_in_queue(window):
    from PySide6.QtGui import QGuiApplication

    window.url_input.setPlainText("https://youtu.be/ccccccccccc")
    window.add_from_input()
    window.ctx.settings.auto_paste_clipboard = True
    QGuiApplication.clipboard().setText("https://youtu.be/ccccccccccc")
    window._last_clipboard = None
    assert window.auto_paste_clipboard() == 0


def test_copy_inside_app_is_not_auto_pasted(window, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    active = Qt.ApplicationState.ApplicationActive
    monkeypatch.setattr(QGuiApplication, "applicationState", staticmethod(lambda: active))
    window.ctx.settings.auto_paste_clipboard = True
    QGuiApplication.clipboard().setText("https://youtu.be/ddddddddddd")  # 在程式中「複製網址」
    window._on_clipboard_changed()
    assert window.auto_paste_clipboard() == 0


def _release(version="99.0.0"):
    from yt_media_tool.core import updates

    return updates.LatestRelease(version, f"YT_Media_Tool-{version}-win64-setup.exe", None)


def test_update_banner_portable_build_links_to_download_page(window, dialogs, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    from yt_media_tool.core import updates

    monkeypatch.setattr(updates, "is_installed_build", lambda: False)
    monkeypatch.setattr(updates, "download_update", lambda *a, **k: pytest.fail("免安裝版不可自動下載"))
    assert window.update_banner.isHidden()
    window._on_update_checked(_release())
    text = window.update_banner.text()
    assert not window.update_banner.isHidden() and "99.0.0" in text and "免安裝版" in text
    assert dialogs.messages == []  # 自動檢查不跳對話框

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    window._on_update_link("download")
    assert opened == [updates.RELEASES_PAGE]  # 固定網址，不使用 API 回傳的連結

    window._on_update_link("skip")
    assert window.update_banner.isHidden()
    assert window.ctx.settings.skipped_update_version == "99.0.0"
    window._on_update_checked(_release())
    assert window.update_banner.isHidden()  # 已略過的版本不再自動提醒
    window._on_update_checked(_release("99.0.1"))
    assert not window.update_banner.isHidden()  # 更新的版本仍會提醒


def test_installed_build_downloads_then_installs(window, qtbot, dialogs, monkeypatch, tmp_path):
    from yt_media_tool.core import updates

    setup = tmp_path / "YT_Media_Tool-99.0.0-win64-setup.exe"
    setup.write_bytes(b"MZ")
    launched = []

    def fake_download(release, on_progress=None, cancel=None, **kwargs):
        on_progress(50.0)
        return setup

    monkeypatch.setattr(updates, "is_installed_build", lambda: True)
    monkeypatch.setattr(updates, "download_update", fake_download)
    monkeypatch.setattr(updates, "launch_installer", lambda path: launched.append(path))
    window._on_update_checked(_release())
    qtbot.waitUntil(lambda: "已下載完成並通過檢查" in window.update_banner.text(), timeout=5000)
    assert "立即安裝並重新開啟" in window.update_banner.text()

    dialogs.answer = QMessageBox.StandardButton.No
    window._on_update_link("install")
    assert launched == [] and not window._closing  # 使用者取消：不安裝

    dialogs.answer = QMessageBox.StandardButton.Yes
    window._on_update_link("install")
    assert launched == [setup] and window._closing  # 啟動安裝程式並關閉程式
    assert window.ctx.settings.pending_update_version == "99.0.0"  # 下次啟動時確認是否更新成功
    assert "安裝完成後會自動重新開啟" in dialogs.text()


def test_update_download_failure_shows_retry(window, qtbot, monkeypatch):
    from yt_media_tool.core import updates

    attempts = []

    def failing(release, **kwargs):
        attempts.append(1)
        raise updates.UpdateError("檢查碼不符")

    monkeypatch.setattr(updates, "is_installed_build", lambda: True)
    monkeypatch.setattr(updates, "download_update", failing)
    window._on_update_checked(_release())
    qtbot.waitUntil(lambda: "自動下載失敗" in window.update_banner.text(), timeout=5000)
    assert "檢查碼不符" in window.update_banner.text() and 'href="update"' in window.update_banner.text()
    window._on_update_link("update")
    qtbot.waitUntil(lambda: len(attempts) == 2, timeout=5000)


def test_auto_download_can_be_disabled(window, monkeypatch):
    from yt_media_tool.core import updates

    window.ctx.settings.auto_download_updates = False
    monkeypatch.setattr(updates, "is_installed_build", lambda: True)
    monkeypatch.setattr(updates, "download_update", lambda *a, **k: pytest.fail("不應自動下載"))
    window._on_update_checked(_release())
    assert "下載並安裝" in window.update_banner.text()


def test_manual_update_check_reports_result(window, dialogs):
    window._update_manual = True
    window._on_update_checked(_release("0.0.1"))
    assert "目前已是最新的正式版" in dialogs.text() and "測試版" in dialogs.text()
    window._update_manual = True
    window._on_update_failed(OSError("offline"))
    assert "無法連線到 GitHub" in dialogs.text()
    window._update_manual = False
    window._on_update_failed(OSError("offline"))
    assert dialogs.text().count("無法連線到 GitHub") == 1  # 自動檢查失敗時不打擾


def test_check_for_updates_runs_in_background(window, qtbot, monkeypatch):
    from yt_media_tool.core import updates

    monkeypatch.setattr(updates, "is_installed_build", lambda: False)
    monkeypatch.setattr(updates, "fetch_latest_release", lambda: _release("99.1.0"))
    window.check_for_updates()
    qtbot.waitUntil(lambda: not window.update_banner.isHidden(), timeout=3000)
    assert window._update_job is None


needs_ffmpeg = pytest.mark.skipif(not (__import__("shutil").which("ffmpeg") and __import__("shutil").which("ffprobe")),
                                  reason="需要 FFmpeg / FFprobe")


@pytest.fixture
def local_media(tmp_path):
    import shutil
    import subprocess

    src = tmp_path / "來源"
    src.mkdir()
    subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:a", "aac", str(src / "錄音.m4a")], check=True)
    (src / "說明.txt").write_text("x", encoding="utf-8")
    return src


@needs_ffmpeg
def test_convert_dialog_converts_files(qtbot, window, local_media, tmp_path):
    from yt_media_tool.core import converter
    from yt_media_tool.gui.convert_dialog import COL_STATUS, ConvertDialog

    dialog = ConvertDialog(converter.find_ffmpeg(), "128", window)
    qtbot.addWidget(dialog)
    assert dialog.add_files([local_media / "錄音.m4a", local_media / "說明.txt", local_media / "錄音.m4a"]) == 1
    assert "說明.txt" in dialog.summary.text()  # 不支援的檔案會被略過並提示

    out = tmp_path / "輸出"
    dialog.other_folder.setChecked(True)
    dialog.folder_edit.setText(str(out))
    dialog.start_button.click()
    qtbot.waitUntil(lambda: dialog.table.item(0, COL_STATUS).text().startswith("完成"), timeout=20000)
    qtbot.waitUntil(lambda: not dialog.is_running(), timeout=5000)
    assert (out / "錄音.mp3").is_file()
    assert sorted(p.name for p in local_media.iterdir()) == ["說明.txt", "錄音.m4a"]  # 來源資料夾不變
    assert "完成 1 個" in dialog.summary.text()
    dialog.start_button.click()
    assert "都已轉好" in dialog.summary.text()  # 已轉好的不重複轉


def test_convert_dialog_requires_output_folder(qtbot, window, tmp_path, dialogs):
    from yt_media_tool.core.converter import ToolInfo
    from yt_media_tool.gui.convert_dialog import ConvertDialog

    media = tmp_path / "a.mp4"
    media.write_bytes(b"x")
    dialog = ConvertDialog(ToolInfo(ffmpeg=Path("/fake/ffmpeg"), ffprobe=Path("/fake/ffprobe"), source="test"),
                           "192", window, files=[media])
    qtbot.addWidget(dialog)
    dialog.other_folder.setChecked(True)
    dialog.start_button.click()
    assert "請選擇要存放 MP3 的資料夾" in dialogs.text()
    assert not dialog.is_running()


def test_dropping_local_media_opens_converter(window, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    media = tmp_path / "影片.mp4"
    media.write_bytes(b"x")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(media)), QUrl.fromLocalFile(str(tmp_path / "x.exe"))])
    window.dropEvent(QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier))
    dialog = window._convert_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.files() == [media]
    assert window.url_input.toPlainText() == ""  # 本機檔案不放進網址輸入框
    dialog.close()


def test_playlist_download_writes_m3u8_in_order(window, qtbot, monkeypatch):
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: [[e.url for e in groups[0].entries]])
    window.ctx.queue.resume()
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: rows(window) == 3 and all(model.task_at(i).status is TaskStatus.COMPLETED
                                                     for i in range(3)), timeout=10000)
    folder = Path(window.folder_edit.text()) / "清單"
    m3u = folder / "清單.m3u8"
    qtbot.waitUntil(m3u.is_file, timeout=3000)
    names = [line for line in m3u.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    assert names == [Path(t.output_path).name for t in window.ctx.queue.tasks()]


def test_playlist_m3u_can_be_disabled(window, qtbot, monkeypatch):
    window.ctx.settings.playlist_m3u = False
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: [[e.url for e in groups[0].entries]])
    window.ctx.queue.resume()
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: rows(window) == 3 and all(model.task_at(i).status is TaskStatus.COMPLETED
                                                     for i in range(3)), timeout=10000)
    assert not list((Path(window.folder_edit.text()) / "清單").glob("*.m3u8"))


def test_youtube_mix_is_read_from_watch_page(window, qtbot, fake, monkeypatch):
    requested = []
    original = fake.extract_playlist

    def record(url, limit=500):
        requested.append(url)
        return original(url, limit)

    monkeypatch.setattr(fake, "extract_playlist", record)
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: [[groups[0].entries[0].url]])
    window.url_input.setPlainText("https://www.youtube.com/watch?v=uzVdsZbYibQ&list=RDuzVdsZbYibQ&start_radio=1")
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 1, timeout=5000)
    assert requested == ["https://www.youtube.com/watch?v=uzVdsZbYibQ&list=RDuzVdsZbYibQ"]


def test_rename_dialog_renames_and_syncs_queue_history(window, qtbot, dialogs, monkeypatch):
    from PySide6.QtCore import Qt

    from yt_media_tool.gui.rename_dialog import COL_NEW, COL_OLD
    from yt_media_tool.utils import system_open

    messy = "周深 ZHOU SHEN × MAYDAY 五月天 [ 如煙 Like Smoke ] 5525+2版 Official Stage Video"
    clean = "周深 × 五月天 - 如煙 (5525+2版)"
    window.ctx.queue.resume()
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.COMPLETED, timeout=5000)
    task = model.task_at(0)
    folder = Path(task.output_path).parent
    # 模擬之前下載、檔名很長的檔案（佇列與歷史都指向它）
    messy_path = folder / f"{messy}.mp4"
    Path(task.output_path).rename(messy_path)
    window.ctx.queue.rename_output_path(task.output_path, str(messy_path))
    (folder / "其他 [ 笑忘歌 Song ] Official Live Video.mp3").write_bytes(b"x")

    dialog = window.open_rename_dialog()
    qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 2
    rows = {dialog.table.item(r, COL_OLD).text(): r for r in range(2)}
    assert dialog.table.item(rows[f"{messy}.mp4"], COL_NEW).text() == clean
    other = rows["其他 [ 笑忘歌 Song ] Official Live Video.mp3"]
    dialog.table.item(other, COL_OLD).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.apply_button.text() == "改名（1 個）"

    assert dialog.apply() == 1
    new_path = folder / f"{clean}.mp4"
    assert new_path.is_file() and (folder / "其他 [ 笑忘歌 Song ] Official Live Video.mp3").is_file()
    assert model.task_at(0).output_path == str(new_path)  # 佇列跟著更新
    history = window.ctx.db.list_history()
    assert history[0]["output_path"] == str(new_path)  # 歷史紀錄跟著更新
    played = []
    monkeypatch.setattr(system_open, "_open_with_default_app", lambda path: played.append(path) or True)
    assert window.play(model.task_at(0)) and played == [new_path]  # 雙擊播放仍找得到檔案

    assert dialog.undo() == 1
    assert messy_path.is_file() and model.task_at(0).output_path == str(messy_path)
    assert window.ctx.db.list_history()[0]["output_path"] == str(messy_path)


def test_rename_dialog_user_edited_name(window, qtbot, dialogs, tmp_path):
    from yt_media_tool.gui.rename_dialog import COL_NEW, RenameDialog

    folder = tmp_path / "舊檔案"
    folder.mkdir()
    (folder / "告白氣球 (Official Music Video) [HD].mp3").write_bytes(b"x")
    dialog = RenameDialog(str(folder), window)
    qtbot.addWidget(dialog)
    assert dialog.scan() == 1
    dialog.table.item(0, COL_NEW).setText("周杰倫 - 告白氣球")  # 使用者自己補上演出者
    dialog.apply()
    assert sorted(p.name for p in folder.iterdir()) == ["周杰倫 - 告白氣球.mp3"]
    assert "已改名 1 個項目" in dialog.summary.text()
    assert dialog.scan() == 0 and "掃描了 1 個 MP3 / MP4，檔名都已經整理好了" in dialog.summary.text()


def test_playlist_store_follows_renamed_files(db, tmp_path):
    from yt_media_tool.core.playlist_files import PlaylistFileStore
    from yt_media_tool.core.task_models import DownloadTask

    music = tmp_path / "清單"
    music.mkdir()
    urls = ["https://www.youtube.com/watch?v=aaaaaaaaaaa", "https://www.youtube.com/watch?v=bbbbbbbbbbb"]
    store = PlaylistFileStore(db)
    store.add_batch(str(music), "清單", "mp3", urls)
    (music / "舊.mp3").write_bytes(b"x")
    store.on_task_completed(DownloadTask(url=urls[0], media_format=MediaFormat.MP3, quality="192",
                                         output_dir=str(music), status=TaskStatus.COMPLETED,
                                         output_path=str(music / "舊.mp3")))
    (music / "舊.mp3").rename(music / "新.mp3")
    store.rename_file(str(music), "舊.mp3", "新.mp3")
    (music / "二.mp3").write_bytes(b"x")
    store.on_task_completed(DownloadTask(url=urls[1], media_format=MediaFormat.MP3, quality="192",
                                         output_dir=str(music), status=TaskStatus.COMPLETED,
                                         output_path=str(music / "二.mp3")))
    text = (music / "清單.m3u8").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    assert lines == ["新.mp3", "二.mp3"]  # 改名後的檔案沒有從清單中消失


def test_rename_mix_folder_syncs_queue_history_and_download_folder(window, qtbot, dialogs, monkeypatch):
    from yt_media_tool.utils import system_open

    mix = "Mix - 周深 ZHOU SHEN × MAYDAY 五月天 [ 如煙 Like Smoke ] 5525+2版 Official Stage Video"
    window.ctx.queue.resume()
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window.add_from_input()
    model = window.table.queue_model
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.COMPLETED, timeout=5000)
    task = model.task_at(0)
    base = Path(task.output_path).parent
    # 重現使用者的情況：歌曲在舊版建立的「Mix - …」資料夾裡，「儲存至」也是這個資料夾
    old_dir = base / mix
    old_dir.mkdir()
    song = old_dir / "周深 × 五月天 - 如煙 (5525+2版).mp4"
    Path(task.output_path).rename(song)
    window.ctx.queue.rename_output_path(task.output_path, str(song))
    window.folder_edit.setText(str(old_dir))

    dialog = window.open_rename_dialog()
    qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 1 and dialog.table.item(0, 0).text().startswith("📁 Mix - ")
    assert "掃描了 1 個 MP3 / MP4：可以整理 1 個合輯資料夾；另有 1 個已經整理好" in dialog.summary.text()
    assert dialog.apply() == 1

    new_dir = base / "合輯 - 周深 × 五月天 - 如煙 (5525+2版)"
    new_song = new_dir / song.name
    assert new_song.is_file() and not old_dir.exists()
    assert dialog.folder_edit.text() == str(new_dir)  # 對話框跟著換到新名稱
    assert window.folder_edit.text() == str(new_dir)  # 主視窗「儲存至」也跟著更新
    assert model.task_at(0).output_path == str(new_song)
    assert window.ctx.db.list_history()[0]["output_path"] == str(new_song)
    played = []
    monkeypatch.setattr(system_open, "_open_with_default_app", lambda path: played.append(path) or True)
    assert window.play(model.task_at(0)) and played == [new_song]

    assert dialog.undo() == 1
    assert song.is_file() and model.task_at(0).output_path == str(song)
    assert window.folder_edit.text() == str(old_dir)
    assert window.ctx.db.list_history()[0]["output_path"] == str(song)


def test_mix_playlist_folder_name_is_cleaned_on_download(window, qtbot, fake, monkeypatch):
    from yt_media_tool.core.downloader import PlaylistEntry, PlaylistInfo

    url = "https://www.youtube.com/watch?v=uzVdsZbYibQ&list=RDuzVdsZbYibQ"
    fake.playlists[url] = PlaylistInfo(
        "Mix - 周深 ZHOU SHEN × MAYDAY 五月天 [ 如煙 Like Smoke ] 5525+2版 Official Stage Video",
        [PlaylistEntry(f"https://www.youtube.com/watch?v=vid{i:08d}", f"歌 {i}", f"vid{i:08d}") for i in range(2)])
    monkeypatch.setattr(window, "choose_playlist_entries", lambda groups, *_: [[e.url for e in groups[0].entries]])
    window.url_input.setPlainText(url)
    window.add_from_input()
    # 貼上的那首不在讀到的清單中，會排在最前面：共 3 首
    qtbot.waitUntil(lambda: rows(window) == 3, timeout=5000)
    assert {Path(t.output_dir).name for t in window.ctx.queue.tasks()} == {"合輯 - 周深 × 五月天 - 如煙 (5525+2版)"}


def test_failed_auto_update_is_reported_on_next_start(qtbot, tmp_path, db_path, fake, dialogs, monkeypatch):
    import dataclasses

    from yt_media_tool import __version__
    from yt_media_tool.core import updates
    from yt_media_tool.utils import system_open

    ctx = create_context(db_path=db_path, downloader=fake, start_paused=True)
    ctx.apply_settings(dataclasses.replace(ctx.settings, pending_update_version="99.0.0"))
    win = MainWindow(ctx)  # 模擬安裝沒有完成：重新開啟後版本仍是舊的
    qtbot.addWidget(win)
    text = win.update_banner.text()
    assert not win.update_banner.isHidden() and "99.0.0" in text and "沒有完成" in text and __version__ in text
    assert ctx.settings.pending_update_version == ""  # 只提示一次
    revealed = []
    monkeypatch.setattr(system_open, "reveal_file", lambda path: revealed.append(path) or True)
    win._on_update_link("openlog")
    assert revealed == [updates.install_log_path()]
    win.close()


def test_successful_auto_update_shows_status(qtbot, db_path, fake, dialogs):
    import dataclasses

    from yt_media_tool import __version__

    ctx = create_context(db_path=db_path, downloader=fake, start_paused=True)
    ctx.apply_settings(dataclasses.replace(ctx.settings, pending_update_version=__version__))
    win = MainWindow(ctx)
    qtbot.addWidget(win)
    assert win.update_banner.isHidden() and "已更新到" in win.statusBar().currentMessage()
    assert ctx.settings.pending_update_version == ""
    win.close()


# ---- v2.8.0：只下載片段、已下載過提醒、播放清單同步、選歌時修改檔名 ----

VIDEO = "https://www.youtube.com/watch?v=aaaaaaaaaaa"


def _history(window, url, fmt, path, is_clip=False):
    from yt_media_tool.core.task_models import DownloadTask

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    done = DownloadTask(url=url, media_format=fmt, quality="192" if fmt is MediaFormat.MP3 else "720",
                        output_dir=str(path.parent), status=TaskStatus.COMPLETED, output_path=str(path))
    if is_clip:
        done.clip_start = 10.0
    window.ctx.db.add_history(done)


def test_clip_adds_one_task_with_range_and_resets(window, dialogs):
    window.url_input.setPlainText(VIDEO)
    window.clip_check.setChecked(True)
    assert window.clip_start_edit.isEnabled()
    window.clip_start_edit.setText("1:20")
    window.clip_end_edit.setText("4:35")
    window.add_from_input()
    task = window.ctx.queue.tasks()[0]
    assert (task.clip_start, task.clip_end) == (80.0, 275.0)
    model = window.table.queue_model
    assert model.data(model.index(0, COL_QUALITY)).endswith("｜片段 1:20～4:35")
    assert not window.clip_check.isChecked() and window.clip_start_edit.text() == ""
    # 同一部影片的完整版不算重複
    window.url_input.setPlainText(VIDEO)
    window.add_from_input()
    assert rows(window) == 2 and window.ctx.queue.tasks()[1].clip_start is None


def test_clip_with_only_end_starts_from_beginning(window):
    window.url_input.setPlainText("https://youtu.be/aaaaaaaaaaa")
    window.clip_check.setChecked(True)
    window.clip_end_edit.setText("90")
    window.add_from_input()
    task = window.ctx.queue.tasks()[0]
    assert (task.clip_start, task.clip_end) == (None, 90.0)
    assert task.clip_text == "片段 0:00～1:30"


@pytest.mark.parametrize("start,end,urls,message", [
    ("", "", VIDEO, "請輸入片段的開始或結束時間"),
    ("1:61", "", VIDEO, "時間格式不正確"),
    ("2:00", "1:00", VIDEO, "結束時間必須晚於開始時間"),
    ("0:10", "", f"{VIDEO}\nhttps://youtu.be/bbbbbbbbbbb", "一次只能用於一部影片"),
    ("0:10", "", PLAYLIST, "一次只能用於一部影片"),
])
def test_invalid_clip_is_rejected(window, dialogs, start, end, urls, message):
    window.url_input.setPlainText(urls)
    window.clip_check.setChecked(True)
    window.clip_start_edit.setText(start)
    window.clip_end_edit.setText(end)
    window.add_from_input()
    assert rows(window) == 0 and message in dialogs.text()
    assert window.clip_check.isChecked()  # 讓使用者修正，不清除


def test_clip_of_video_in_playlist_does_not_open_picker(window, monkeypatch):
    monkeypatch.setattr(window, "choose_playlist_entries", lambda *a: pytest.fail("片段不展開播放清單"))
    window.url_input.setPlainText("https://www.youtube.com/watch?v=vid00000001&list=PLabcdefghij123456")
    window.clip_check.setChecked(True)
    window.clip_start_edit.setText("30")
    window.add_from_input()
    task = window.ctx.queue.tasks()[0]
    assert task.url == "https://www.youtube.com/watch?v=vid00000001" and task.clip_start == 30.0


@pytest.mark.parametrize("answer,expected_rows", [("skip", 1), ("again", 2), (None, 0)])
def test_already_downloaded_asks_before_adding(window, tmp_path, monkeypatch, dialogs, answer, expected_rows):
    _history(window, "https://youtu.be/aaaaaaaaaaa", MediaFormat.MP3, tmp_path / "music" / "歌手 - 歌.mp3")
    asked = []
    monkeypatch.setattr(window, "ask_already_downloaded", lambda files, fmt: asked.append(files) or answer)
    window.mp3_radio.setChecked(True)
    window.url_input.setPlainText(f"{VIDEO}&t=30s\nhttps://youtu.be/bbbbbbbbbbb")
    window.add_from_input()
    assert [p.name for p in asked[0]] == ["歌手 - 歌.mp3"]
    assert rows(window) == expected_rows
    assert (window.url_input.toPlainText() == "") is (answer is not None)  # 取消時保留輸入的網址
    if answer == "skip":
        assert "已略過 1 部已經下載過的影片" in dialogs.text()


def test_already_downloaded_ignores_other_format_deleted_files_and_clips(window, tmp_path, monkeypatch):
    monkeypatch.setattr(window, "ask_already_downloaded", lambda *a: pytest.fail("不應詢問"))
    _history(window, VIDEO, MediaFormat.MP4, tmp_path / "v" / "影片.mp4")  # 格式不同
    _history(window, VIDEO, MediaFormat.MP3, tmp_path / "v" / "片段.mp3", is_clip=True)  # 只下載過片段
    gone = tmp_path / "v" / "已刪除.mp3"
    _history(window, VIDEO, MediaFormat.MP3, gone)
    gone.unlink()  # 檔案已被使用者刪除
    window.mp3_radio.setChecked(True)
    window.url_input.setPlainText(VIDEO)
    window.add_from_input()
    assert rows(window) == 1


def test_redownload_from_history_does_not_ask(window, tmp_path, monkeypatch):
    _history(window, VIDEO, MediaFormat.MP3, tmp_path / "m" / "歌.mp3")
    monkeypatch.setattr(window, "ask_already_downloaded", lambda *a: pytest.fail("重新下載不應詢問"))
    assert len(window.redownload(VIDEO, MediaFormat.MP3, "192")) == 1


def test_playlist_sync_marks_downloaded_and_skips_question(window, qtbot, tmp_path, monkeypatch):
    folder = Path(window.folder_edit.text()) / "清單"
    _history(window, "https://www.youtube.com/watch?v=vid00000001", MediaFormat.MP3, folder / "影片 1.mp3")
    window.mp3_radio.setChecked(True)
    shown = []

    def choose(groups, *_):
        shown.append(groups)
        return [[e.url for e in groups[0].entries]]  # 使用者仍勾選全部（包含已下載的）

    monkeypatch.setattr(window, "choose_playlist_entries", choose)
    monkeypatch.setattr(window, "ask_already_downloaded", lambda *a: pytest.fail("選歌視窗已確認，不再詢問"))
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 3, timeout=5000)
    group = shown[0][0]
    assert group.downloaded == {"https://www.youtube.com/watch?v=vid00000001": str(folder / "影片 1.mp3")}
    assert group.names["https://www.youtube.com/watch?v=vid00000000"] == "影片 0"


def test_playlist_sync_keeps_downloaded_songs_in_m3u(window, qtbot, tmp_path, monkeypatch):
    folder = Path(window.folder_edit.text()) / "清單"
    _history(window, "https://www.youtube.com/watch?v=vid00000001", MediaFormat.MP3, folder / "舊的歌.mp3")
    window.mp3_radio.setChecked(True)
    monkeypatch.setattr(window, "choose_playlist_entries",
                        lambda groups, *_: [[e.url for e in groups[0].entries if e.url not in groups[0].downloaded]])
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 2, timeout=5000)
    window.ctx.queue.resume()
    qtbot.waitUntil(lambda: all(t.status is TaskStatus.COMPLETED for t in window.ctx.queue.tasks()), timeout=5000)
    m3u = folder / "清單.m3u8"

    def names():
        lines = m3u.read_text(encoding="utf-8").splitlines() if m3u.is_file() else []
        return [line for line in lines if not line.startswith("#")]

    qtbot.waitUntil(lambda: len(names()) == 3, timeout=5000)
    assert names()[1] == "舊的歌.mp3"  # 依播放清單順序，已下載的歌也在清單中


def test_custom_names_from_picker_become_task_file_names(window, qtbot, monkeypatch):
    def choose(groups, *_):
        window._custom_names = {groups[0].entries[0].url: "五月天 - 倔強"}
        return [[e.url for e in groups[0].entries[:2]]]

    monkeypatch.setattr(window, "choose_playlist_entries", choose)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 2, timeout=5000)
    tasks = window.ctx.queue.tasks()
    assert [t.file_name for t in tasks] == ["五月天 - 倔強", ""]
    window.table.selectRow(0)
    window._update_details()
    assert "指定檔名：五月天 - 倔強" in window.details.toPlainText()


def test_planned_name_follows_title_cleanup_setting(window):
    from yt_media_tool.core.downloader import PlaylistEntry

    entry = PlaylistEntry(VIDEO, "周杰倫 Jay Chou【晴天 Sunny Day】Official MV", "aaaaaaaaaaa", None, "周杰倫")
    vlog = PlaylistEntry(VIDEO, "我的日常 vlog", "aaaaaaaaaaa", None, "某某頻道")
    window.ctx.settings.clean_titles = True
    assert window.planned_name(entry, MediaFormat.MP3) == "周杰倫 - 晴天"
    assert window.planned_name(vlog, MediaFormat.MP3) == "某某 - 我的日常 vlog"  # 頻道名稱去掉「頻道」等字
    assert window.planned_name(vlog, MediaFormat.MP4) == "我的日常 vlog"  # MP4 不用頻道名稱補
    window.ctx.settings.clean_titles = False
    assert window.planned_name(entry, MediaFormat.MP3) == "周杰倫 Jay Chou【晴天 Sunny Day】Official MV"


def test_picker_names_downloaded_and_select_new(qtbot):
    from PySide6.QtCore import Qt

    from yt_media_tool.core.downloader import PlaylistEntry
    from yt_media_tool.gui.playlist_dialog import COL_NAME, COL_STATUS, PlaylistGroup, PlaylistPickerDialog

    urls = [f"https://www.youtube.com/watch?v=v{i:010d}" for i in range(3)]
    entries = [PlaylistEntry(u, f"歌曲 {i} Official MV", u[-11:], 200.0) for i, u in enumerate(urls)]
    group = PlaylistGroup("清單", entries, names={u: f"歌手 - 歌曲 {i}" for i, u in enumerate(urls)},
                          downloaded={urls[1]: "D:\\音樂\\歌手 - 歌曲 1.mp3"})
    dialog = PlaylistPickerDialog([group], 500)
    qtbot.addWidget(dialog)
    item = dialog.tree.topLevelItem(0).child
    assert dialog.selected_urls() == [urls[0], urls[2]]  # 已下載的預設不勾選
    assert item(1).text(COL_STATUS) == "✓ 已下載" and item(0).text(COL_NAME) == "歌手 - 歌曲 0"
    assert dialog.select_new.isVisibleTo(dialog)

    dialog._set_visible_checked(True)
    assert len(dialog.selected_urls()) == 3
    dialog._select_not_downloaded()
    assert dialog.selected_urls() == [urls[0], urls[2]]

    # 修改檔名：只回傳勾選且真的改過的
    item(0).setText(COL_NAME, "五月天 - 倔強")
    item(2).setText(COL_NAME, "  歌手 - 歌曲 2 ")
    item(1).setText(COL_NAME, "沒勾選的")
    assert dialog.custom_names() == {urls[0]: "五月天 - 倔強"}
    item(0).setCheckState(0, Qt.CheckState.Unchecked)
    assert dialog.custom_names() == {}

    dialog.search.setText("倔強")  # 也能搜尋預計檔名
    assert not item(0).isHidden() and item(1).isHidden()


def test_picker_hides_select_new_without_downloaded(qtbot):
    from yt_media_tool.core.downloader import PlaylistEntry
    from yt_media_tool.gui.playlist_dialog import PlaylistGroup, PlaylistPickerDialog

    dialog = PlaylistPickerDialog([PlaylistGroup("清單", [PlaylistEntry(VIDEO, "歌")])], 500)
    qtbot.addWidget(dialog)
    assert not dialog.select_new.isVisibleTo(dialog)
