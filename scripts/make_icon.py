"""產生 assets/app.ico 與 assets/app.png（以 Qt 繪製，不需額外套件）。

用法：python scripts/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPolygonF

ROOT = Path(__file__).resolve().parents[1]


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    path = QPainterPath()
    path.addRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 52 * s, 52 * s)
    p.fillPath(path, QColor("#1f2329"))
    p.setPen(QPen(QColor("#3d8bfd"), 10 * s))
    p.drawPath(path)
    # 播放三角形
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ff4d4d"))
    p.drawPolygon(QPolygonF([QPointF(92 * s, 56 * s), QPointF(92 * s, 140 * s), QPointF(164 * s, 98 * s)]))
    # 下載箭頭
    p.setBrush(QColor("#e6e9ee"))
    p.drawRect(QRectF(116 * s, 150 * s, 24 * s, 36 * s))
    p.drawPolygon(QPolygonF([QPointF(92 * s, 182 * s), QPointF(164 * s, 182 * s), QPointF(128 * s, 214 * s)]))
    p.end()
    return image


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 - QImage 繪製需要 Qt 應用程式物件
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    big = render(256)
    big.save(str(assets / "app.png"), "PNG")
    if not big.save(str(assets / "app.ico"), "ICO"):
        print("此 Qt 版本不支援寫入 ICO", file=sys.stderr)
        return 1
    print(f"已產生 {assets / 'app.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
