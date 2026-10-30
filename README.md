# YT Media Tool V2.0

Windows 11 桌面 YouTube 影音下載工具（繁體中文介面、深色主題）。
以 **PySide6** 建置 GUI、**yt-dlp** 取得與下載影片、**FFmpeg / FFprobe** 合併影音、轉換 MP3 並檢查輸出檔，
**SQLite** 保存佇列、歷史紀錄與設定，**PyInstaller** 打包為 one-folder EXE。

> **使用聲明**：本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。
> 本工具不實作、也不協助繞過 DRM 或其他存取限制；遇到 DRM 保護的內容會直接顯示「不支援」。

---

## 功能

| 類別 | 內容 |
|---|---|
| 網址輸入 | 單一或多行貼上（換行、空白、逗號分隔皆可）、自動去除重複（同一影片 ID 的 watch / youtu.be / Shorts 視為重複）、辨識一般影片 / Shorts / 播放清單 / 播放清單中的影片、不支援的網址逐一列出原因 |
| 播放清單 | 需勾選「展開播放清單」才會展開；展開在背景讀取，加入前一定會顯示影片數量並請使用者確認（單次上限 500 部） |
| 格式 | MP4 720p / 1080p / 最高可用解析度；MP3 128 / 192 / 320 kbps |
| 實際品質揭露 | 原始素材沒有目標解析度時，顯示實際取得的解析度與可用解析度清單；MP3 顯示原始音源位元率，目標位元率高於原始音源時明確標示「實際音質不會提升」 |
| 佇列 | 編號、影片名稱、格式、品質、進度、速度、剩餘時間、狀態、操作（取消 / 重試 / 開啟位置）；單筆取消、全部取消、重試失敗任務、清除已完成、右鍵上移 / 下移 / 移除、暫停 / 開始佇列 |
| 並行 | 預設同時 1 筆，可設定 1–3 筆 |
| 進度 | 單筆進度、整體佇列進度、即時速度、ETA、總下載速度、合併 / 轉檔 / 檢查 / 移動等階段、選取任務可看詳細錯誤訊息 |
| 恢復 | 重新開啟程式時恢復未完成任務，並詢問是否立即繼續 |
| 設定 | 預設儲存資料夾、同時下載數量、預設格式、預設 MP3 品質、預設 MP4 解析度、完成後開啟資料夾、保留歷史紀錄、自訂 FFmpeg 資料夾 |
| 安全 | 每個任務專屬暫存資料夾、同名檔案自動編號不覆蓋、取消只刪除自己的暫存檔、輸出檔經 FFprobe 驗證後才標記完成、不組合 shell 指令、參數化 SQL |

## 系統需求

- Windows 10 / 11 64 位元
- 執行 EXE：不需另外安裝 Python。完整版隨附 FFmpeg 與 Deno；精簡版（`--no-ffmpeg`）需自行安裝 FFmpeg。
- 開發 / 建置：Python **3.12**（64 位元）、PowerShell 5.1 以上、可連線 PyPI 與 FFmpeg 下載來源

---

## Windows 安裝與啟動（原始碼）

```bat
git clone <repository-url> YT_Media_Tool
cd YT_Media_Tool
scripts\setup_windows.bat
scripts\run_dev.bat
```

`setup_windows.bat` 會以 `py -3.12` 建立 `.venv` 並安裝 `requirements-dev.txt`（全部固定版本）。
若尚未安裝 Python 3.12：`winget install -e --id Python.Python.3.12`。

開發時若系統沒有 FFmpeg，可擇一：
- 執行 `powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1`（放到 `vendor\ffmpeg\bin`，程式會自動找到）
- `winget install --id Gyan.FFmpeg -e`
- 在程式「工具 → 設定 → FFmpeg 資料夾」指定含 `ffmpeg.exe`、`ffprobe.exe` 的資料夾

## 打包 EXE

```bat
scripts\build_exe.bat
```

步驟：執行 pytest → 依 `packaging\ffmpeg_manifest.json` 下載並**驗證 SHA256** 的 FFmpeg → PyInstaller one-folder 建置
→ `scripts\verify_dist.py` 檢查發行結構 → 以 `--smoke-test` 實際啟動 EXE → 產生 zip 與 `.sha256`。

選項：

| 參數 | 說明 |
|---|---|
| `--no-ffmpeg` | 不隨附 FFmpeg（程式會偵測缺少並顯示安裝指引） |
| `--no-deno` | 不隨附 Deno |
| `--skip-tests` | 略過 pytest |

產出：

```
dist/
├── YT_Media_Tool/
│   ├── YT_Media_Tool.exe
│   ├── README.md / THIRD_PARTY_NOTICES.md / RELEASE_NOTES.md
│   └── _internal/
│       ├── ffmpeg/   ffmpeg.exe、ffprobe.exe、LICENSE、VERSION.json（版本 / 來源 / SHA256）
│       ├── deno/     deno.exe、LICENSE
│       └── …         Python、Qt、yt-dlp 等
├── YT_Media_Tool-2.0.0-win64.zip
└── YT_Media_Tool-2.0.0-win64.zip.sha256
```

也可手動執行：`.venv\Scripts\python -m PyInstaller --noconfirm --clean packaging\yt_media_tool.spec`
（環境變數 `YTMT_BUNDLE_FFMPEG=0` / `YTMT_BUNDLE_DENO=0` 可停用隨附）。

### FFmpeg 部署方式（可重現）

- 版本、下載網址、SHA256 與授權資訊集中在 `packaging/ffmpeg_manifest.json`。
- `scripts/fetch_ffmpeg.ps1` 下載後比對 SHA256，不符即中止；manifest 未填 SHA256 時預設拒絕建置
  （`-AllowUnpinned` 會顯示計算出的雜湊，請與官方公布值比對後寫回 manifest 並提交）。
- 離線建置：`scripts\fetch_ffmpeg.ps1 -ZipPath D:\ffmpeg-7.1.1-essentials_build.zip`
- 預設來源為 gyan.dev essentials build（GPLv3），授權與原始碼取得方式見 `THIRD_PARTY_NOTICES.md`；
  如需 LGPL 版本，改用 BtbN 的 `win64-lgpl` 版本化 release 並更新 manifest。

### FFmpeg 尋找順序

程式**不假設**使用者已設定 PATH，依序尋找：
1. 設定中指定的 FFmpeg 資料夾
2. 環境變數 `YTMT_FFMPEG_DIR`
3. 隨附資料夾 `_internal\ffmpeg`（開發時為 `vendor\ffmpeg\bin`）
4. EXE 同層的 `ffmpeg` 資料夾
5. 系統 PATH

找不到時，主視窗頂端顯示警示，「工具 → 檢查相依元件」列出搜尋過的位置與安裝指引，且不允許加入任務。

## 資料存放位置

| 項目 | 位置 |
|---|---|
| 資料庫（佇列、歷史、設定） | `%LOCALAPPDATA%\YT_Media_Tool\yt_media_tool.sqlite3` |
| 日誌（2 MB × 5 輪替） | `%LOCALAPPDATA%\YT_Media_Tool\logs\yt_media_tool.log` |
| 預設下載資料夾 | 使用者「下載」資料夾\YT_Media_Tool（透過 Known Folder API 取得，支援重新導向） |
| 下載中暫存檔 | `<下載資料夾>\.ytmt_tmp\task_<編號>_<亂數>\`（隱藏；完成、失敗或取消時刪除） |

不會寫入 EXE 所在的安裝目錄。測試或可攜用途可用環境變數 `YTMT_DATA_DIR` 指定其他位置。

---

## 專案架構

```
YT_Media_Tool/
├── main.py                         啟動檔（開發與 PyInstaller 共用）
├── requirements.txt / requirements-dev.txt / pyproject.toml
├── src/yt_media_tool/
│   ├── app.py                      進入點：日誌、單一執行個體鎖、主視窗、--smoke-test
│   ├── app_context.py              組合資料庫、設定、下載引擎與佇列
│   ├── core/
│   │   ├── task_models.py          任務資料模型與狀態機
│   │   ├── url_parser.py           網址分類、正規化、去重與錯誤原因
│   │   ├── downloader.py           yt-dlp 下載引擎（暫存隔離、取消、驗證、不覆蓋移動）
│   │   ├── converter.py            FFmpeg / FFprobe / Deno 偵測、媒體檢查、格式選擇
│   │   ├── queue_manager.py        佇列排程、並行、取消、重試、保存與恢復（不依賴 Qt）
│   │   └── errors.py               錯誤訊息轉換（yt-dlp、FFmpeg、磁碟、權限）
│   ├── storage/
│   │   ├── database.py             SQLite（參數化 SQL、user_version migration）
│   │   └── settings.py             設定模型與驗證
│   ├── gui/
│   │   ├── main_window.py          主視窗
│   │   ├── queue_table.py          佇列表格模型、進度條與操作按鈕 delegate
│   │   ├── settings_dialog.py      設定
│   │   ├── history_dialog.py       下載歷史
│   │   ├── qt_bridge.py            工作執行緒事件 → Qt signal（主執行緒）
│   │   ├── workers.py              背景工作（播放清單展開）
│   │   └── theme.py                深色主題
│   └── utils/
│       ├── paths.py                AppData、隨附檔位置、安全檔名、檔名保留
│       ├── system_open.py          開啟資料夾 / 在檔案總管中選取檔案
│       ├── win_job.py              Windows Job Object：程式結束時終止 ffmpeg 等子程序
│       └── logging_utils.py        日誌
├── tests/                          pytest（單元、GUI、離線整合）
├── scripts/                        setup_windows.bat、run_dev.bat、build_exe.bat、fetch_ffmpeg.ps1、verify_dist.py、make_icon.py
├── packaging/                      yt_media_tool.spec、ffmpeg_manifest.json、version_info.txt
├── assets/                         app.ico、app.png
└── docs/                           WINDOWS_INTEGRATION_TESTS.md、RELEASE_NOTES.md
```

### 執行緒模型

- GUI 主執行緒只處理介面；每個下載任務在獨立的工作執行緒中執行 yt-dlp。
- yt-dlp 的 progress hooks / postprocessor hooks 回報進度 → `QueueManager` 更新狀態（每 0.2 秒節流）
  → `QueueEventBridge` 以 Qt signal 排入主執行緒更新表格。
- 播放清單展開在 `QThreadPool` 背景執行。

### 下載流程與檔案安全

1. 取得影片資訊（不下載）並描述實際可取得的品質；檢查磁碟空間與寫入權限。
2. 在任務專屬暫存資料夾中下載與後處理（yt-dlp 的輸出目錄就是暫存資料夾，**不會接觸下載資料夾中的任何既有檔案**）。
3. 以 FFprobe 驗證成品（MP4 需有影像串流、MP3 需有音訊串流）。
4. 以「不覆蓋」方式移到下載資料夾（同名時自動加上 ` (1)`、` (2)`…）。
5. 全部完成才標記「完成」；任何一步失敗或取消，只刪除該任務自己的暫存資料夾。

---

## 測試

```bat
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check src tests main.py
```

- 測試完全不連線 YouTube。`tests/integration/` 以本機 HTTP 伺服器提供測試影片，實際執行 yt-dlp 與 FFmpeg
  （需要 FFmpeg；找不到時自動略過）。
- Windows 實機整合測試清單：[`docs/WINDOWS_INTEGRATION_TESTS.md`](docs/WINDOWS_INTEGRATION_TESTS.md)

## 已知限制

- 取消發生在 FFmpeg 合併 / 轉檔進行中時，會等該 FFmpeg 步驟結束（通常數秒）後才停止並清除暫存檔；狀態會顯示「取消中…」。
- 關閉程式時，Windows Job Object 會確保 ffmpeg.exe / deno.exe 子程序一併結束，不會殘留鎖住檔案。
- 程式關閉時中斷的任務會從頭重新下載（不續傳），以確保暫存檔一定被清除。
- 不支援需要登入的內容（私人、會員專屬、年齡限制）與 DRM 內容；也不支援頻道網址。
- YouTube 端變動可能使 yt-dlp 失效，需更新 `requirements.txt` 中的 yt-dlp 版本後重新打包。
