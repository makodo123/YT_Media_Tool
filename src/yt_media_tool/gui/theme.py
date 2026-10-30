"""深色主題（Fusion 樣式 + 調色盤 + 少量樣式表）。"""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#3d8bfd"
STATUS_COLORS = {
    "waiting": "#b0b6c0",
    "downloading": "#5aa9ff",
    "processing": "#f0b85a",
    "completed": "#5fd38d",
    "failed": "#ff6b6b",
    "cancelled": "#8a8f98",
}

STYLESHEET = f"""
QWidget {{ font-size: 10pt; }}
QGroupBox {{ border: 1px solid #3a3f47; border-radius: 6px; margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #cfd6e0; }}
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QTextEdit {{
    background: #1e2127; border: 1px solid #3a3f47; border-radius: 4px; padding: 3px; }}
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QPushButton {{ background: #2f343c; border: 1px solid #454b55; border-radius: 4px; padding: 5px 12px; }}
QPushButton:hover {{ background: #3a404a; }}
QPushButton:pressed {{ background: #262a30; }}
QPushButton:disabled {{ color: #6b717b; background: #262a30; }}
QPushButton#primaryButton {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: bold; }}
QPushButton#primaryButton:hover {{ background: #5a9dff; }}
QPushButton#dangerButton:hover {{ background: #6b2b2b; }}
QTableView {{ background: #1b1d22; alternate-background-color: #20232a; gridline-color: #2c3038;
    border: 1px solid #3a3f47; selection-background-color: #2d4a73; }}
QHeaderView::section {{ background: #272b32; color: #d5dbe3; border: none; border-right: 1px solid #353a42;
    padding: 4px; }}
QProgressBar {{ border: 1px solid #3a3f47; border-radius: 4px; background: #1e2127; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QStatusBar {{ background: #1b1d22; }}
QLabel#hintLabel {{ color: #9aa3ae; }}
QLabel#warningLabel {{ color: #f0b85a; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    base, window, text = QColor("#1e2127"), QColor("#24272e"), QColor("#e6e9ee")
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#20232a"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2f343c"))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, QColor("#2f343c"))
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff6b6b"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#7d848f"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#6b717b"))
    app.setPalette(palette)
    if sys.platform.startswith("win"):
        app.setFont(QFont("Microsoft JhengHei UI", 10))
    app.setStyleSheet(STYLESHEET)
