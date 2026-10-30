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
| FFmpeg / FFprobe | 7.1.1（essentials build） | 影音合併、MP3 轉檔、輸出檢查 | GPL-3.0-or-later（本建置含 GPL 元件） | 見下方 |
| PyInstaller bootloader | 6.22.3 | EXE 啟動程式 | GPL-2.0 with bootloader exception | https://pyinstaller.org/ |

## FFmpeg

- 隨附版本、下載網址與 SHA256 記錄於 `packaging/ffmpeg_manifest.json`，發行版本中另存於
  `_internal/ffmpeg/VERSION.json`。
- 預設建置來源：gyan.dev essentials build（GitHub 鏡像 `GyanD/codexffmpeg` 的版本化 release）。
- FFmpeg 為獨立執行檔，本程式以子程序方式呼叫，未與其連結。
- 授權：https://www.ffmpeg.org/legal.html ；GPL 授權全文隨附於 `_internal/ffmpeg/LICENSE*`。
- 對應原始碼：https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz ，建置設定見 https://www.gyan.dev/ffmpeg/builds/ 。
  依 GPL 要求，散布者應能在散布後三年內依請求提供對應原始碼。
- 若需避免 GPL 元件，可在 `packaging/ffmpeg_manifest.json` 改用 LGPL 建置
  （例如 BtbN/FFmpeg-Builds 的 `win64-lgpl` 版本化 release），並更新 sha256 與本文件。
- 也可使用 `scripts\build_exe.bat --no-ffmpeg` 建置不隨附 FFmpeg 的版本，由使用者自行安裝。

## 使用聲明

本工具僅供下載使用者擁有權利、已獲授權或平台明確允許下載的內容。本工具不實作、也不協助繞過 DRM
或其他存取限制。使用者須自行遵守著作權法及各平台服務條款。
