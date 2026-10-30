"""檢查 PyInstaller 產出的 one-folder 發行資料夾結構。

用法：python scripts/verify_dist.py [dist/YT_Media_Tool] [--expect-ffmpeg] [--expect-deno]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    dist = Path(args[0]) if args else ROOT / "dist" / "YT_Media_Tool"
    suffix = ".exe" if sys.platform.startswith("win") else ""
    internal = dist / "_internal"
    checks: list[tuple[str, bool]] = [
        (f"主程式 YT_Media_Tool{suffix}", (dist / f"YT_Media_Tool{suffix}").is_file()),
        ("_internal 資料夾", internal.is_dir()),
        ("圖示 assets/app.ico", (internal / "assets" / "app.ico").is_file()),
        ("第三方授權說明", (internal / "THIRD_PARTY_NOTICES.md").is_file()),
        ("yt-dlp-ejs JavaScript 元件", (internal / "yt_dlp_ejs").is_dir()),
        ("未包含 SQLite 資料庫", not list(dist.rglob("*.sqlite3"))),
        ("未包含日誌檔", not list(dist.rglob("*.log"))),
    ]
    if "--expect-ffmpeg" in argv:
        checks += [
            ("隨附 ffmpeg", (internal / "ffmpeg" / f"ffmpeg{suffix}").is_file()),
            ("隨附 ffprobe", (internal / "ffmpeg" / f"ffprobe{suffix}").is_file()),
            ("FFmpeg 版本與來源資訊", (internal / "ffmpeg" / "VERSION.json").is_file()),
        ]
        version_file = internal / "ffmpeg" / "VERSION.json"
        if version_file.is_file():
            info = json.loads(version_file.read_text(encoding="utf-8-sig"))
            checks.append(("FFmpeg SHA256 已記錄", bool(info.get("sha256"))))
    if "--expect-deno" in argv:
        checks.append(("隨附 deno", (internal / "deno" / f"deno{suffix}").is_file()))

    ok = True
    for name, passed in checks:
        print(f"[{'OK' if passed else 'FAIL'}] {name}")
        ok &= passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
