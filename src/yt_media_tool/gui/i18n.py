"""載入 Qt 內建的繁體中文翻譯，讓標準對話框按鈕（是 / 否 / 確定 / 取消）顯示中文。"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication

from yt_media_tool.utils import paths

log = logging.getLogger(__name__)

QT_TRANSLATION = "qtbase_zh_TW"


def translation_dirs() -> list[Path]:
    dirs = [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))]
    bundle = paths.bundle_dir()
    # PyInstaller 打包後的位置；QLibraryInfo 在打包環境中不一定指向正確位置
    dirs += [bundle / "PySide6" / "translations", bundle / "PySide6" / "Qt" / "translations"]
    return dirs


def install_qt_translations(app: QApplication) -> bool:
    for directory in translation_dirs():
        translator = QTranslator(app)  # 以 app 為 parent，生命週期與應用程式相同
        if translator.load(QT_TRANSLATION, str(directory)):
            app.installTranslator(translator)
            log.info("已載入 Qt 繁體中文翻譯：%s", directory)
            return True
    log.warning("找不到 Qt 繁體中文翻譯（%s），標準按鈕將顯示英文", QT_TRANSLATION)
    return False
