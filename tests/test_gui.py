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

    assert window.windowTitle() == "YT Media Tool V2.0"
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
    assert group_b.child(0).text(1) == "03:20"


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
    result = dialog.result_settings()
    assert result.max_concurrent == 3 and result.default_format == "mp3"
    assert result.default_mp3_quality == "320" and result.keep_history is False
    assert result.embed_metadata is False
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
