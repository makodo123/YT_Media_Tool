# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder 建置設定。

產出：
    dist/YT_Media_Tool/YT_Media_Tool.exe
    dist/YT_Media_Tool/_internal/            （Python、Qt、yt-dlp 等）
    dist/YT_Media_Tool/_internal/ffmpeg/     （ffmpeg.exe、ffprobe.exe、授權與版本資訊）
    dist/YT_Media_Tool/_internal/deno/       （deno.exe 與授權）

環境變數：
    YTMT_BUNDLE_FFMPEG=0  不隨附 FFmpeg（程式啟動時會偵測並顯示安裝指引）
    YTMT_BUNDLE_DENO=0    不隨附 Deno

用法（於專案根目錄）：pyinstaller --noconfirm --clean packaging/yt_media_tool.spec
"""

import json
import os
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ROOT = Path(SPECPATH).resolve().parent
EXE_SUFFIX = ".exe" if sys.platform.startswith("win") else ""
BUNDLE_FFMPEG = os.environ.get("YTMT_BUNDLE_FFMPEG", "1") != "0"
BUNDLE_DENO = os.environ.get("YTMT_BUNDLE_DENO", "1") != "0"

datas = [
    (str(ROOT / "assets" / "app.ico"), "assets"),
    (str(ROOT / "assets" / "app.png"), "assets"),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
]
# yt-dlp 處理 YouTube 所需的 JavaScript 元件
datas += collect_data_files("yt_dlp_ejs")
datas += copy_metadata("yt-dlp")

# ---- FFmpeg / FFprobe 與其 DLL ----
# 不交給 PyInstaller 處理：若以 datas 加入，PyInstaller 會分析 DLL 相依並在 _internal 最上層
# 另外放一份 avcodec 等 DLL（約 140 MB 重複）。改為在 COLLECT 完成後原樣複製到 _internal/ffmpeg。
FFMPEG_FILES = []
if BUNDLE_FFMPEG:
    ffmpeg_root = ROOT / "vendor" / "ffmpeg"
    for name in ("ffmpeg", "ffprobe"):
        exe = ffmpeg_root / "bin" / f"{name}{EXE_SUFFIX}"
        if not exe.is_file():
            raise SystemExit(
                f"找不到 {exe}。\n請先執行 scripts\\fetch_ffmpeg.ps1 下載並驗證 FFmpeg，"
                "或設定 YTMT_BUNDLE_FFMPEG=0 建置不隨附 FFmpeg 的版本。")
    manifest = ffmpeg_root / "VERSION.json"
    if not manifest.is_file():
        raise SystemExit(f"找不到 {manifest}（由 fetch_ffmpeg.ps1 產生，記錄版本、來源與 SHA256）")
    # bin 中的執行檔與共用函式庫 DLL（靜態建置則沒有 DLL），以及版本、授權資訊
    FFMPEG_FILES = sorted(p for p in (ffmpeg_root / "bin").iterdir() if p.is_file())
    FFMPEG_FILES += [manifest] + sorted(ffmpeg_root.glob("LICENSE*")) + sorted(ffmpeg_root.glob("README*"))
    print("隨附 FFmpeg：", json.loads(manifest.read_text(encoding="utf-8-sig")).get("version"))

# ---- Deno（由 requirements.txt 固定版本的 deno 套件提供）----
if BUNDLE_DENO:
    import deno

    deno_exe = Path(deno.find_deno_bin())
    if not deno_exe.is_file():
        raise SystemExit("找不到 deno 執行檔，請確認已安裝 requirements.txt 中的 deno 套件，或設定 YTMT_BUNDLE_DENO=0")
    datas.append((str(deno_exe), "deno"))
    from importlib.metadata import distribution

    dist = distribution("deno")
    for f in dist.files or []:
        if f.name.upper().startswith("LICENSE"):
            datas.append((str(f.locate()), "deno"))
    print("隨附 Deno：", dist.version)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["yt_dlp_ejs"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest", "pytestqt", "PySide6.QtWebEngineCore", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia"],
    noarchive=False,
    optimize=0,
)
# ---- 移除用不到的 Qt 檔案（依 CI 大小報告）----
# opengl32sw.dll：軟體 OpenGL 繪圖（約 20 MB），本程式只使用標準 Widgets，不需要
# Qt 翻譯檔：只保留繁體中文（標準對話框按鈕使用），其餘語言約 6.5 MB
KEEP_QT_TRANSLATIONS = {"qtbase_zh_TW.qm", "qt_zh_TW.qm"}
EXCLUDED_FILES = {"opengl32sw.dll"}


def _keep(entry):
    dest = entry[0].replace("\\", "/")
    name = dest.rsplit("/", 1)[-1]
    if "/translations/" in f"/{dest}" and name.endswith(".qm"):
        return name in KEEP_QT_TRANSLATIONS
    return name.lower() not in EXCLUDED_FILES


a.datas = [entry for entry in a.datas if _keep(entry)]
a.binaries = [entry for entry in a.binaries if _keep(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YT_Media_Tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 壓縮容易被防毒軟體誤判，且影響啟動速度
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "assets" / "app.ico"),
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform.startswith("win") else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="YT_Media_Tool",
)

# COLLECT 完成後原樣複製 FFmpeg（見上方說明）
if FFMPEG_FILES:
    ffmpeg_target = Path(coll.name) / "_internal" / "ffmpeg"
    ffmpeg_target.mkdir(parents=True, exist_ok=True)
    for source in FFMPEG_FILES:
        shutil.copy2(source, ffmpeg_target / source.name)
    print(f"已複製 {len(FFMPEG_FILES)} 個 FFmpeg 檔案到 {ffmpeg_target}")
