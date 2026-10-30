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


def test_playlist_requires_opt_in(window, dialogs):
    window.expand_playlist.setChecked(False)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    assert rows(window) == 0
    assert "展開播放清單" in dialogs.text()


def test_playlist_expansion_asks_before_adding(window, qtbot, monkeypatch):
    window.expand_playlist.setChecked(True)
    asked = []
    monkeypatch.setattr(window, "confirm_playlist", lambda count, summary: asked.append(count) or False)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: asked == [3], timeout=5000)
    qtbot.waitUntil(lambda: not window._busy_expanding)
    assert rows(window) == 0

    monkeypatch.setattr(window, "confirm_playlist", lambda count, summary: True)
    window.url_input.setPlainText(PLAYLIST)
    window.add_from_input()
    qtbot.waitUntil(lambda: rows(window) == 3, timeout=5000)


def test_video_in_playlist_without_expand_adds_single_video(window):
    window.expand_playlist.setChecked(False)
    window.url_input.setPlainText("https://www.youtube.com/watch?v=aaaaaaaaaaa&list=PLabcdefghij123456")
    window.add_from_input()
    assert rows(window) == 1
    assert window.ctx.queue.tasks()[0].url == "https://www.youtube.com/watch?v=aaaaaaaaaaa"


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
    assert "下載中" in model.data(model.index(0, COL_STATUS))
    fake.release(BLOCK)
    qtbot.waitUntil(lambda: model.task_at(0).status is TaskStatus.COMPLETED, timeout=5000)
    assert model.task_at(0).progress == 100
    assert "720p" in model.data(model.index(0, COL_QUALITY))
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
    result = dialog.result_settings()
    assert result.max_concurrent == 3 and result.default_format == "mp3"
    assert result.default_mp3_quality == "320" and result.keep_history is False
    window.ctx.apply_settings(result)
    assert window.ctx.queue.max_concurrent == 3
    assert window.ctx.queue.keep_history is False
