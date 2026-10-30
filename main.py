"""YT Media Tool V2.0 啟動檔（開發環境與 PyInstaller 共用）。"""

import multiprocessing
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from yt_media_tool.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
