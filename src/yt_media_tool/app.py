"""應用程式進入點：初始化日誌、單一執行個體鎖、資料庫與主視窗。"""

from __future__ import annotations

import logging
import sys

from yt_media_tool import APP_DISPLAY_NAME, APP_ID, __version__
from yt_media_tool.utils import paths
from yt_media_tool.utils.logging_utils import setup_logging
from yt_media_tool.utils.win_job import create_app_mutex, kill_children_on_exit

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--version" in argv:
        print(f"{APP_DISPLAY_NAME} {__version__}")
        return 0
    # --smoke-test：建立主視窗、檢查相依元件後自動結束（供打包後驗證用，不會開始任何下載）
    smoke_test = "--smoke-test" in argv
    argv = [a for a in argv if a != "--smoke-test"]
    log_path = setup_logging()
    kill_children_on_exit()
    create_app_mutex()
    log.info("%s %s 啟動（frozen=%s），資料目錄：%s", APP_DISPLAY_NAME, __version__, paths.is_frozen(),
             paths.app_data_dir())

    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from yt_media_tool.app_context import create_context
    from yt_media_tool.gui.i18n import install_qt_translations
    from yt_media_tool.gui.main_window import MainWindow
    from yt_media_tool.gui.theme import apply_dark_theme
    from yt_media_tool.storage.database import DatabaseError

    app = QApplication(argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(__version__)
    icon_path = paths.bundle_dir() / "assets" / "app.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    apply_dark_theme(app)
    install_qt_translations(app)

    # 避免兩個執行個體同時操作同一個佇列資料庫
    lock = QLockFile(str(paths.app_data_dir() / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.warning(None, APP_DISPLAY_NAME, "YT Media Tool 已在執行中。")
        return 1

    try:
        ctx = create_context(start_paused=True)
    except DatabaseError as exc:
        log.exception("資料庫初始化失敗")
        QMessageBox.critical(None, APP_DISPLAY_NAME, f"無法開啟資料庫：\n{exc}\n\n日誌：{log_path}")
        return 2

    window = MainWindow(ctx)
    window.show()
    if smoke_test:
        report = window.dependency_report()
        log.info("smoke test 相依元件：\n%s", report)
        print(report)
        QTimer.singleShot(1500, window.close)
    else:
        window.restore_queue(ask=True)
    code = app.exec()
    lock.unlock()
    log.info("程式結束，代碼 %s", code)
    return code
