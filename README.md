# YT Media Tool

[![Windows CI](https://github.com/makodo123/YT_Media_Tool/actions/workflows/windows-ci.yml/badge.svg)](https://github.com/makodo123/YT_Media_Tool/actions/workflows/windows-ci.yml)

Windows 10 / 11 桌面 YouTube 影音下載工具，採繁體中文介面與深色主題。

- 介面：**PySide6**
- 下載：**yt-dlp**
- 影音合併、MP3 轉檔與輸出檢查：**FFmpeg / FFprobe**
- 佇列、歷史紀錄與設定：**SQLite**
- 打包：**PyInstaller**（one-folder EXE）

> **使用聲明**：本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。
> 本工具不實作、也不協助繞過 DRM 或其他存取限制；遇到受 DRM 保護的內容時會直接顯示「不支援」。

---

## 下載即用（一般使用者）

到 [Releases](https://github.com/makodo123/YT_Media_Tool/releases/latest) 下載最新版本，以下兩種擇一：

**安裝版（建議）**

1. 下載 `YT_Media_Tool-<版本>-win64-setup.exe` 並執行
2. 依畫面指示安裝：預設只為目前使用者安裝，不需要系統管理員權限；也可以選擇為所有使用者安裝到 Program Files
3. 從開始功能表或桌面捷徑開啟「YT Media Tool」

- 升級：直接執行新版安裝程式即可覆蓋安裝，設定與佇列會保留。
- 解除安裝：「設定 → 應用程式 → 已安裝的應用程式 → YT Media Tool」。會詢問是否一併刪除設定與紀錄；
  已下載的影片與音樂一律不會被刪除。

**免安裝版**

1. 下載 `YT_Media_Tool-<版本>-win64.zip`
2. 解壓縮到任意資料夾（例如 `D:\Apps\YT_Media_Tool`）
3. 執行 `YT_Media_Tool\YT_Media_Tool.exe`

兩種版本都不需要另外安裝 Python 或 FFmpeg（已隨附）。首次執行若出現 SmartScreen 警告（程式未經數位簽章），
請按「其他資訊」→「仍要執行」。

以下「Windows 安裝與啟動（原始碼）」之後的段落僅供開發者參考。

## 功能

| 類別 | 內容 |
|---|---|
| 網址輸入 | 可貼上或從瀏覽器拖曳單一或多行網址（以換行、空白或逗號分隔）；在瀏覽器複製 YouTube 網址後切回程式會自動帶入輸入框（可在設定關閉）；自動去除重複（同一影片 ID 的 watch / youtu.be / Shorts 網址視為重複）；可辨識一般影片、Shorts、播放清單及播放清單中的影片；不支援的網址會逐一列出原因 |
| 播放清單 | 含播放清單的網址（`playlist?list=…` 或 `watch?v=…&list=…`）會在背景讀取清單，列出每部影片的名稱與長度，讓您勾選要下載哪些（可搜尋、全選 / 全不選；單次上限 500 部）。播放清單網址預設全部勾選；從清單中某支影片的網址加入時，預設只勾選該影片。播放清單的影片存到以清單名稱命名的子資料夾，並產生依原順序排列的清單檔「清單名稱.m3u8」（音樂播放器可直接開啟；皆可在設定關閉） |
| 本機檔案轉 MP3 | 「工具 → 本機檔案轉 MP3」或把電腦裡的影音檔拖曳到主視窗，即可用隨附的 FFmpeg 轉成 MP3（128 / 192 / 320 kbps）；原檔不會被修改，同名 MP3 已存在時自動加編號 |
| 字幕 | 主視窗勾選「下載字幕」後，MP4 一併下載字幕並存成與影片同名的 .srt（繁體中文 → 中文 → 簡體中文 → 英文；沒有時使用 YouTube 自動產生的字幕）；字幕下載失敗不影響影片 |
| 歌名自動整理 | 檔名與歌曲資訊自動整理成「演出者 - 歌名」（MP3 一律整理；MP4 只在標題中找得到演出者時整理，vlog 等影片維持原標題）（例如「周杰倫 Jay Chou【晴天】Official MV」→「周杰倫 - 晴天」）；優先使用 YouTube 提供的歌曲資訊，整理不出合理結果時保留原標題；佇列仍顯示原標題（可在設定關閉） |
| 歌曲資訊 | MP3 / MP4 自動寫入標題、演出者（頻道名稱）並以影片縮圖作為封面，音樂播放器與手機會顯示歌名和封面（可在設定關閉） |
| 格式 | MP4 720p / 1080p / 最高可用解析度；MP3 128 / 192 / 320 kbps |
| 實際品質揭露 | 原始影片沒有目標解析度時，品質欄顯示「1080p → 720p ⚠」；影片有更高解析度時顯示「720p（最高 1080p）」，滑鼠停留可看可用解析度清單；MP3 的原始音源位元率低於目標時，品質欄顯示「192 kbps → 124 kbps ⚠」，滑鼠停留會說明「實際音質不會提升」 |
| 佇列 | 欄位：編號、影片名稱、格式、品質、進度、速度、剩餘時間、狀態、操作（取消 / 重試 / 開啟位置）。支援單筆取消、全部取消、重試失敗任務、清除已完成、右鍵上移 / 下移，以及暫停 / 開始佇列；雙擊已完成的任務以預設播放器開啟 |
| 速度上限 | 可在設定限制所有下載合計的速度（例如 5 MB/s），避免佔滿網路 |
| 新版本提醒與自動更新 | 啟動時向 GitHub 查詢最新正式版（只讀取版本號與檢查碼，不傳送個人資料）；安裝版會在背景下載新版安裝程式並核對檢查碼，完成後按「立即安裝並重新開啟」即自動更新；免安裝版提示到下載頁面。可略過該版本或在設定關閉；也可從「說明 → 檢查新版本」手動檢查 |
| 完成通知 | 佇列全部完成時，若程式不在前景，工作列圖示閃爍並顯示系統通知（可在設定關閉） |
| 歷史紀錄 | 可搜尋；雙擊在檔案總管中顯示檔案；右鍵複製網址或以相同格式重新下載 |
| 批次操作 | 以 Ctrl / Shift 多選（Ctrl+A 全選）後，可按「移除所選」或 Delete 鍵移除，也可用右鍵批次取消、重試或移除；移除只刪除佇列紀錄，不會刪除已下載的檔案 |
| 並行 | 預設同時下載 1 筆，可設定為 1–3 筆 |
| 進度 | 單筆進度、整體佇列進度（不計入失敗與取消的任務）、即時速度、剩餘時間、總下載速度；顯示合併、轉檔、檢查、移動等階段；選取任務可查看詳細錯誤訊息 |
| 恢復 | 重新開啟程式時恢復未完成的任務，並詢問是否立即繼續 |
| 設定 | 預設儲存資料夾（會記住上次使用的資料夾）、同時下載數量、速度上限、自動帶入剪貼簿網址、預設格式、預設 MP3 品質、預設 MP4 解析度、完成後開啟資料夾、完成通知、保留歷史紀錄、寫入歌名與封面、播放清單子資料夾、播放清單檔（.m3u8）、啟動時檢查新版本、自訂 FFmpeg 資料夾、YouTube 登入資訊（cookies，選用） |
| 安全 | 每個任務使用專屬暫存資料夾；同名檔案自動編號、不覆蓋；取消時只刪除自己的暫存檔；輸出檔經 FFprobe 驗證後才標記完成；不組合 shell 指令；SQL 全部參數化 |

## 系統需求

- Windows 10 / 11（64 位元）
- 執行 EXE：不需另外安裝 Python。完整版隨附 FFmpeg 與 Deno；精簡版（以 `--no-ffmpeg` 建置）需自行安裝 FFmpeg。
- 開發與建置：Python **3.12**（64 位元）、PowerShell 5.1 以上，且需能連線至 PyPI 與 FFmpeg 下載來源。

---

## Windows 安裝與啟動（原始碼）

### 步驟 1：安裝必要工具（只需做一次）

開啟「命令提示字元」或「PowerShell」，執行：

```bat
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
```

安裝完成後，請**關閉並重新開啟**命令提示字元，讓新安裝的程式生效。

### 步驟 2：下載原始碼

以下兩種方法擇一：

- **方法 A：使用 Git**（之後可用 `git pull` 取得更新）

  ```bat
  cd %USERPROFILE%\Documents
  git clone https://github.com/makodo123/YT_Media_Tool.git
  cd YT_Media_Tool
  ```

- **方法 B：不使用 Git**
  1. 開啟 https://github.com/makodo123/YT_Media_Tool
  2. 按綠色「Code」按鈕 →「Download ZIP」
  3. 解壓縮後，在命令提示字元中用 `cd` 切換到解壓出來的 `YT_Media_Tool-main` 資料夾

### 步驟 3：建立執行環境（只需做一次）

```bat
scripts\setup_windows.bat
```

此步驟會建立 `.venv` 虛擬環境，並安裝 `requirements-dev.txt` 中的套件（全部固定版本）。需要網路連線，約需數分鐘。

### 步驟 4：啟動程式

```bat
scripts\run_dev.bat
```

### 若程式提示找不到 FFmpeg

以下方法擇一：

- 執行 `powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1`：會依 `packaging\ffmpeg_manifest.json` 下載並驗證 FFmpeg，
  放到 `vendor\ffmpeg\bin`，程式會自動找到。
- 執行 `winget install -e --id Gyan.FFmpeg`，安裝後重新啟動程式。
- 在程式的「工具 → 設定 → FFmpeg 資料夾」，指定含有 `ffmpeg.exe` 與 `ffprobe.exe` 的資料夾。

## 打包 EXE

```bat
scripts\build_exe.bat
```

執行步驟：

1. 執行 pytest
2. 依 `packaging\ffmpeg_manifest.json` 下載 FFmpeg 並**驗證 SHA256**
3. 以 PyInstaller 建置 one-folder 版本
4. 以 `scripts\verify_dist.py` 檢查發行資料夾，並用其中的 FFmpeg 實際轉出 MP3、轉封裝 MP4
5. 以 `--smoke-test` 實際啟動 EXE
6. 產生 zip 與 `.sha256`

`build_exe.bat` 參數：

| 參數 | 說明 |
|---|---|
| `--no-ffmpeg` | 不隨附 FFmpeg（程式會偵測到缺少並顯示安裝指引） |
| `--no-deno` | 不隨附 Deno |
| `--skip-tests` | 略過 pytest |

產出：

```
dist/
├── YT_Media_Tool/
│   ├── YT_Media_Tool.exe
│   ├── README.md / THIRD_PARTY_NOTICES.md / RELEASE_NOTES.md / LICENSE.txt
│   └── _internal/
│       ├── ffmpeg/   ffmpeg.exe、ffprobe.exe、FFmpeg 的 DLL、LICENSE、VERSION.json（版本 / 來源 / SHA256）
│       ├── deno/     deno.exe、LICENSE
│       └── …         Python、Qt、yt-dlp 等
├── YT_Media_Tool-<版本>-win64.zip
├── YT_Media_Tool-<版本>-win64.zip.sha256
├── YT_Media_Tool-<版本>-win64-setup.exe          （執行 build_installer.bat 後）
└── YT_Media_Tool-<版本>-win64-setup.exe.sha256
```

也可以手動執行：`.venv\Scripts\python -m PyInstaller --noconfirm --clean packaging\yt_media_tool.spec`
（設定環境變數 `YTMT_BUNDLE_FFMPEG=0` 或 `YTMT_BUNDLE_DENO=0` 可停用對應元件的隨附）。

### 建立安裝程式

先完成上面的打包，再執行：

```bat
winget install -e --id JRSoftware.InnoSetup
scripts\build_installer.bat
```

會以 `packaging\installer.iss`（Inno Setup 6.5 以上）產生 `dist\YT_Media_Tool-<版本>-win64-setup.exe` 與 `.sha256`。

- 預設只為目前使用者安裝（`%LOCALAPPDATA%\Programs\YT Media Tool`），可改為所有使用者（Program Files）。
- 建立開始功能表捷徑，桌面捷徑可選；安裝精靈為繁體中文，並顯示使用聲明。
- 升級時先清除舊版 `_internal` 再安裝；程式執行中時會提示關閉（透過程式建立的 mutex 偵測）。
- 解除安裝時詢問是否刪除 `%LOCALAPPDATA%\YT_Media_Tool`（設定、佇列、歷史、日誌）；靜默解除安裝時預設保留。
- CI 會以 `scripts\verify_installer.py` 實際靜默安裝、啟動、用隨附 FFmpeg 轉檔，再解除安裝，
  並確認捷徑與「應用程式」清單登錄都有建立與移除。

### 發布新版本到 GitHub Releases

1. 更新 `src/yt_media_tool/__init__.py`、`scripts/build_exe.bat` 與 `pyproject.toml` 中的版本號，推送到 `main`
   （EXE 與安裝程式的版本資訊會自動取用 `__init__.py` 的版本號；測試會檢查三者一致）。
2. 等待該次推送的 Windows CI 全部通過。
3. 以下列任一方式觸發 `.github/workflows/release.yml`，它會在 Windows 上自動測試、打包（隨附 FFmpeg 與 Deno）、
   建立並測試安裝程式，再建立 Release（附上 zip、安裝程式與兩者的 `.sha256`）：
   - **GitHub 網頁**：Actions → Release → Run workflow，輸入標籤（例如 `v2.0.1`）
   - **推送標籤**：

     ```bat
     git tag v2.0.1
     git push origin v2.0.1
     ```

標籤格式為 `vX.Y.Z`，或加上後綴的 `vX.Y.Z-beta.N`；含 `-` 的標籤會發布為「預先發行版本」。
若因標籤輸入錯誤而失敗，請從 Release workflow 頁面重新執行，不要對失敗的那次按「Re-run」（會沿用錯誤的輸入）。

### FFmpeg 部署方式（可重現）

- 版本、下載網址、SHA256 與授權資訊集中在 `packaging/ffmpeg_manifest.json`。
- 目前使用 BtbN 的 **LGPL 共用函式庫（win64-lgpl-shared）** 建置：ffmpeg.exe 與 ffprobe.exe 共用同一組 DLL，
  比靜態建置小約 40–55 MB，且不含 GPL 元件。下載、合併與 MP3 轉檔所需的功能（libmp3lame、stream copy）皆已具備。
- `scripts/fetch_ffmpeg.ps1` 下載後會比對 SHA256，不符即中止；manifest 未填 SHA256 時預設拒絕建置。
  若本機 `vendor\ffmpeg` 的版本與 manifest 不同，會自動重新下載。
- `.github/workflows/ffmpeg-verify.yml` 會將 manifest 中的 SHA256 與 GitHub release digest、建置者公布的
  `checksums.sha256` 交叉比對。
- BtbN 的每日建置不保證長期保留。若來源被移除，可用 `.github/workflows/ffmpeg-candidates.yml` 比較新的候選版本，
  更新 manifest 後重新驗證。
- 離線建置：`scripts\fetch_ffmpeg.ps1 -ZipPath D:\ffmpeg-n9.0.2-37-gae19868753-win64-lgpl-shared-9.0.zip`
- 授權與原始碼取得方式請見 `THIRD_PARTY_NOTICES.md`。

### FFmpeg 尋找順序

程式**不假設**使用者已設定 PATH，會依下列順序尋找：

1. 設定中指定的 FFmpeg 資料夾
2. 環境變數 `YTMT_FFMPEG_DIR`
3. 隨附資料夾 `_internal\ffmpeg`（開發時為 `vendor\ffmpeg\bin`）
4. EXE 同層的 `ffmpeg` 資料夾
5. 系統 PATH

若都找不到，主視窗頂端會顯示警示，且無法加入任務；可在「工具 → 檢查相依元件」查看搜尋過的位置與安裝指引。

## YouTube 要求「登入以確認不是機器人」時

在部分網路環境（例如 VPN、公司網路、部分 ISP）或短時間內大量下載時，YouTube 可能要求登入驗證，任務會失敗並顯示此訊息。
這時可到「工具 → 設定 → YouTube 登入資訊」選擇來源：

| 來源 | 說明 |
|---|---|
| Firefox | 先在 Firefox 登入 YouTube；程式會直接讀取，最穩定 |
| cookies.txt 檔案 | 用瀏覽器擴充功能（例如「Get cookies.txt LOCALLY」）在無痕視窗登入 YouTube 後匯出，再於設定中指定；程式只使用副本，不會修改原檔。**使用 Chrome / Edge 請用這個方式** |

不提供直接讀取 Chrome / Edge：新版 Chrome / Edge 的加密方式讓程式無法讀取其 cookies。

注意事項：

- 此功能會使用您 YouTube 帳號的登入狀態。yt-dlp 官方提醒帳號可能因此受到 YouTube 限制，建議使用次要帳號。
- 本程式不會另外保存、記錄或傳送 cookies 內容；cookies.txt 的副本放在任務暫存資料夾中，任務結束即刪除。
- 登入後只能取得該帳號原本就有權觀看的內容，不會繞過 DRM 或其他存取限制。
- 也可以先嘗試關閉 VPN 或更換網路。

## 資料存放位置

| 項目 | 位置 |
|---|---|
| 資料庫（佇列、歷史、設定） | `%LOCALAPPDATA%\YT_Media_Tool\yt_media_tool.sqlite3` |
| 日誌（每檔 2 MB，保留 5 份） | `%LOCALAPPDATA%\YT_Media_Tool\logs\yt_media_tool.log` |
| 預設下載資料夾 | `<使用者的「下載」資料夾>\YT_Media_Tool`（透過 Known Folder API 取得，支援資料夾重新導向） |
| 下載中的暫存檔 | `<下載資料夾>\.ytmt_tmp\task_<編號>_<亂數>\`（隱藏；完成、失敗或取消時刪除） |

程式不會寫入 EXE 所在的安裝目錄。若用於測試或可攜環境，可用環境變數 `YTMT_DATA_DIR` 指定其他位置。

---

## 專案架構

```
YT_Media_Tool/
├── main.py                         啟動檔（開發與 PyInstaller 共用）
├── requirements.txt / requirements-dev.txt / pyproject.toml
├── handoff.md                      開發交接文件（目前狀態、關鍵決定、注意事項）
├── src/yt_media_tool/
│   ├── app.py                      進入點：日誌、單一執行個體鎖、Qt 中文翻譯、主視窗、--smoke-test
│   ├── app_context.py              組合資料庫、設定、下載引擎與佇列
│   ├── core/
│   │   ├── task_models.py          任務資料模型與狀態機
│   │   ├── url_parser.py           網址分類、正規化、去重與錯誤原因
│   │   ├── downloader.py           yt-dlp 下載引擎（暫存隔離、取消、驗證、不覆蓋移動）
│   │   ├── converter.py            FFmpeg / FFprobe / Deno 偵測、媒體檢查、格式選擇
│   │   ├── cookies.py              YouTube 登入資訊（cookies）設定
│   │   ├── queue_manager.py        佇列排程、並行、取消、重試、保存與恢復（不依賴 Qt）
│   │   └── errors.py               錯誤訊息轉換（yt-dlp、FFmpeg、cookies、磁碟、權限）
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
│   │   ├── i18n.py                 載入 Qt 繁體中文翻譯
│   │   └── theme.py                深色主題
│   └── utils/
│       ├── paths.py                AppData、隨附檔位置、安全檔名、檔名保留
│       ├── system_open.py          開啟資料夾 / 在檔案總管中選取檔案
│       ├── win_job.py              Windows Job Object：程式結束時終止 ffmpeg 等子程序
│       └── logging_utils.py        日誌
├── tests/                          pytest（單元、GUI、離線整合）
├── scripts/                        setup_windows.bat、run_dev.bat、build_exe.bat、build_installer.bat / .py、
│                                   fetch_ffmpeg.ps1、verify_dist.py、verify_installer.py、make_release_zip.py、
│                                   ci_run.ps1、junit_annotations.py、make_icon.py
├── packaging/                      yt_media_tool.spec、version_info.txt（範本）、ffmpeg_manifest.json、
│                                   installer.iss、installer_notice.txt、ChineseTraditional.isl
├── .github/workflows/              windows-ci.yml、release.yml、ffmpeg-verify.yml、ffmpeg-candidates.yml
├── assets/                         app.ico、app.png
└── docs/                           WINDOWS_INTEGRATION_TESTS.md、RELEASE_NOTES.md
```

### 執行緒模型

- GUI 主執行緒只處理介面；每個下載任務在獨立的工作執行緒中執行 yt-dlp。
- yt-dlp 的 progress hooks / postprocessor hooks 回報進度 → `QueueManager` 更新狀態（每 0.2 秒節流）
  → `QueueEventBridge` 以 Qt signal 排入主執行緒更新表格。
- 播放清單在 `QThreadPool` 中於背景展開。

### 下載流程與檔案安全

1. 取得影片資訊（不下載），判斷實際可取得的品質，並檢查磁碟空間與寫入權限。
2. 在任務專屬的暫存資料夾中下載與後處理（yt-dlp 的輸出目錄就是暫存資料夾，**不會接觸下載資料夾中的任何既有檔案**）。
3. 以 FFprobe 驗證成品（MP4 需有影像串流，MP3 需有音訊串流）。
4. 以「不覆蓋」方式移到下載資料夾（同名時自動加上 ` (1)`、` (2)`…）。
5. 全部完成才標記為「已完成」；任何一步失敗或取消，都只刪除該任務自己的暫存資料夾。

關閉程式時，Windows Job Object 會讓 ffmpeg.exe / deno.exe 等子程序一併結束，不會殘留並鎖住檔案。

---

## 測試

```bat
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check src tests main.py scripts
```

- 測試完全不連線 YouTube。`tests/integration/` 以本機 HTTP 伺服器提供測試影片，實際執行 yt-dlp 與 FFmpeg
  （需要 FFmpeg；找不到時會自動略過）。
- GitHub Actions（`.github/workflows/windows-ci.yml`）會在 `windows-latest` 上執行 ruff 與完整 pytest（含 FFmpeg 整合測試），
  再以與 Release 相同的流程打包（隨附 FFmpeg 與 Deno）、用發行資料夾中的 FFmpeg 實際轉檔並啟動 EXE，
  接著建立安裝程式並實際安裝 / 啟動 / 解除安裝；產出的 zip 與安裝程式可在該次執行的 Artifacts 下載。
- Windows 實機整合測試清單：[`docs/WINDOWS_INTEGRATION_TESTS.md`](docs/WINDOWS_INTEGRATION_TESTS.md)

## 授權

本專案以 [Apache License 2.0](LICENSE) 授權。隨附的第三方元件（FFmpeg、Qt、Deno 等）依其各自的授權散布，詳見 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

## 已知限制

- 若在 FFmpeg 合併或轉檔期間取消，會等該步驟結束（通常數秒）後才停止並清除暫存檔；期間狀態會顯示「取消中…」。
- 關閉程式時被中斷的任務，下次會從頭重新下載（不續傳），以確保暫存檔都會被清除。
- 不支援受 DRM 保護的內容與頻道網址。需要登入的內容（年齡限制、會員專屬等）只有在設定 cookies，且該帳號本身有權觀看時才能下載。
- YouTube 改版可能導致 yt-dlp 暫時無法使用，屆時需更新 `requirements.txt` 中的 yt-dlp 版本，並重新打包發布。
