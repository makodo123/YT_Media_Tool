"""檢查 PyInstaller 產出的 one-folder 發行資料夾結構。

用法：python scripts/verify_dist.py [dist/YT_Media_Tool] [--expect-ffmpeg] [--expect-deno]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mb(size: int) -> str:
    return f"{size / 1024 / 1024:7.1f} MB"


def size_report(dist: Path, top: int = 20) -> str:
    """列出發行資料夾總大小、_internal 各子項目大小與最大的檔案，供縮小體積時參考。"""
    files = [p for p in dist.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    internal = dist / "_internal"
    groups: dict[str, int] = {}
    for p in files:
        rel = p.relative_to(internal) if internal in p.parents else p.relative_to(dist)
        key = rel.parts[0] if internal in p.parents and len(rel.parts) > 1 else str(rel)
        if internal in p.parents and len(rel.parts) > 2 and rel.parts[0] == "PySide6":
            key = "/".join(rel.parts[:3]) if rel.parts[1] == "plugins" else "/".join(rel.parts[:2])
        groups[key] = groups.get(key, 0) + p.stat().st_size
    lines = [f"總計 {_mb(total)}（{len(files)} 個檔案）", "", "各項目："]
    for key, size in sorted(groups.items(), key=lambda kv: -kv[1])[:top]:
        lines.append(f"{_mb(size)}  {key}")
    lines += ["", "最大的檔案："]
    for p in sorted(files, key=lambda f: -f.stat().st_size)[:top]:
        lines.append(f"{_mb(p.stat().st_size)}  {p.relative_to(dist).as_posix()}")
    return "\n".join(lines)


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
        ("Qt 繁體中文翻譯", any(internal.rglob("qtbase_zh_TW.qm"))),
        ("未包含其他語言的 Qt 翻譯", not any(p.name != "qtbase_zh_TW.qm" and p.name != "qt_zh_TW.qm"
                                    for p in internal.rglob("*.qm"))),
        ("未包含 opengl32sw.dll", not any(internal.rglob("opengl32sw.dll"))),
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

    if dist.is_dir():
        report = size_report(dist)
        print(report)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            message = report.replace("%", "%25").replace("\n", "%0A")
            print(f"::notice title=發行資料夾大小::{message}")

    ok = True
    for name, passed in checks:
        print(f"[{'OK' if passed else 'FAIL'}] {name}")
        ok &= passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
