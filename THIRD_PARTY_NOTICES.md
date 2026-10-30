# 第三方元件與授權說明

YT Media Tool V2.0 本身以 Apache License 2.0 授權（見專案根目錄 `LICENSE`）。
本程式使用或隨附下列第三方元件。各元件之著作權歸其原作者所有，並依各自授權條款散布。

| 元件 | 版本 | 用途 | 授權 | 來源 |
|---|---|---|---|---|
| Python | 3.12 | 執行環境（由 PyInstaller 隨附） | PSF License | https://www.python.org/ |
| PySide6 / Qt | 6.12.0 | 桌面 GUI | LGPL-3.0（動態連結，使用者可替換 `_internal` 中的 Qt 函式庫） | https://www.qt.io/qt-for-python ・ 原始碼：https://code.qt.io/ |
| yt-dlp | 2026.10.26 | 影片資訊取得與下載 | Unlicense | https://github.com/yt-dlp/yt-dlp |
| yt-dlp-ejs | 0.8.0 | yt-dlp 處理 YouTube 所需的 JavaScript 元件 | Unlicense（詳見套件內授權檔） | https://github.com/yt-dlp/ejs |
| Deno | 2.9.8 | yt-dlp 使用的 JavaScript 執行環境 | MIT | https://github.com/denoland/deno |
| FFmpeg / FFprobe | 9.0.2（BtbN win64-lgpl-shared） | 影音合併、MP3 轉檔、輸出檢查 | LGPL-2.1-or-later（不含 GPL 元件） | 見下方 |
| PyInstaller bootloader | 6.22.3 | EXE 啟動程式 | GPL-2.0 with bootloader exception | https://pyinstaller.org/ |

## FFmpeg

- 隨附版本、下載網址與 SHA256 記錄於 `packaging/ffmpeg_manifest.json`，發行版本中另存於
  `_internal/ffmpeg/VERSION.json`。
- 建置來源：BtbN/FFmpeg-Builds 的 `win64-lgpl-shared` 建置（FFmpeg n9.0.2-37-gae19868753，
  release `autobuild-2026-10-29-19-17`）。SHA256 已與 GitHub release asset digest 及建置者公布的
  `checksums.sha256` 交叉驗證。
- 授權：LGPL-2.1-or-later（LGPL 建置，未啟用 GPL 或 nonfree 元件）。授權全文隨附於 `_internal/ffmpeg/LICENSE*`；
  說明：https://www.ffmpeg.org/legal.html 。
- FFmpeg 以共用函式庫（`_internal/ffmpeg/*.dll`）形式散布，本程式以子程序方式呼叫 `ffmpeg.exe` / `ffprobe.exe`，
  使用者可自行以相容版本替換這些 DLL 或執行檔。
- 對應原始碼：https://github.com/FFmpeg/FFmpeg/tree/ae19868753 ；建置腳本與設定：https://github.com/BtbN/FFmpeg-Builds 。
- 注意：BtbN 的每日建置不保證長期保留。若日後該 release 被移除，需在 manifest 改用新的版本並重新驗證 SHA256。
- 也可使用 `scripts\build_exe.bat --no-ffmpeg` 建置不隨附 FFmpeg 的版本，由使用者自行安裝。

## 使用聲明

本工具僅供下載使用者擁有權利、已獲授權或平台明確允許下載的內容。本工具不實作、也不協助繞過 DRM
或其他存取限制。使用者須自行遵守著作權法及各平台服務條款。
