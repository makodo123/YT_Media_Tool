"""顯示來自外部的文字（影片標題、播放清單名稱、錯誤訊息）時，確保只當成純文字。

Qt 的訊息視窗與提示（tooltip）會自動判斷內容是不是 HTML：第一行出現像「<b>」「<img …>」的標籤時，
整段文字會被當成 HTML 排版。影片標題由上傳者決定，不可讓它變成畫面上的連結、圖片或格式。
"""

from __future__ import annotations

from PySide6.QtGui import Qt  # mightBeRichText 由 QtGui 提供


def plain(text: str) -> str:
    """回傳一定會以純文字顯示的字串：會被誤判為 HTML 時，把「<」換成全形「＜」。"""
    return text.replace("<", "＜") if text and Qt.mightBeRichText(text) else text
