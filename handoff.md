# YT Media Tool 交接文件

> 更新時間：2026-10-31｜儲存庫：https://github.com/makodo123/YT_Media_Tool （分支 `main`，最新 commit 見 `git log`）
> 使用者以**繁體中文**溝通，請全程使用繁體中文回覆，說明技術選項時用淺白比喻（使用者偏好見附錄 A）。

本文件分五大項：**1. 任務目標**、**2. 已完成的內容與修改的檔案**、**3. 關鍵決定與原因**、
**4. 還沒做的下一步**、**5. 不要碰的地方與已知的雷**；附錄為使用者偏好與常用指令。

---

## 1. 這個任務的目標

從零建立並持續維護 Windows 桌面程式 **YT Media Tool**（繁體中文介面、深色主題），並以 GitHub Releases 發布。

- YouTube 單一 / 多網址批次下載；MP4（720p / 1080p / 最高可用解析度）與 MP3（128 / 192 / 320 kbps）
- 下載佇列：即時進度、速度、剩餘時間、單筆 / 全部取消、失敗重試、清除已完成、重開程式恢復未完成任務、並行 1–3 筆
- FFmpeg 合併與轉檔，SQLite 保存佇列 / 歷史 / 設定，PyInstaller one-folder EXE ＋ Inno Setup 安裝程式
- 技術：Python 3.12、PySide6、yt-dlp（Python API）、FFmpeg / FFprobe、SQLite、PyInstaller、Inno Setup、pytest
- **限制（原始規格，不可違反）**：只下載有權利或獲授權的內容；**不得實作 DRM 或存取限制規避**；
  不得把使用者輸入拼成 shell 指令；資料寫在 `%LOCALAPPDATA%\YT_Media_Tool`，不可寫入程式目錄；同名檔案不可覆蓋。
- 原始需求規格的完整內容在第一次對話中；README.md 的「功能」表涵蓋全部功能（含後續新增）。

最近兩輪的工作方式：使用者要求「**以使用者角度檢查文字與功能（及是否可新增功能）**」→ 修正並發測試版 →
使用者實機測試回報 → 修正 → 使用者確認後發正式版。

---

## 2. 目前已經完成什麼、改了哪些檔

### 2.1 目前狀態

- **最新正式版 `v2.3.0`**（標示為 Latest）：2026-10-31 發布，4 個附件與 `.sha256` 已核對；**使用者實測下載無誤**。
  https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.3.0
- v2.3.0 的程式碼與使用者實測無誤的 `v2.3.0-beta.1` 相同（之後只改 handoff.md）。
- **沒有進行中的工作**。
- 使用者實測紀錄：v2.1.0（下載、cookies、MP4 / MP3、批次移除、總進度、安裝 / 升級 / 解除安裝）、v2.1.2、
  v2.2.0-beta.2、v2.2.0、v2.3.0-beta.1、v2.3.0 皆回報無誤。
- 測試：221 個通過＋1 個僅 Windows 執行（單元、GUI、以本機 HTTP 伺服器搭配真實 yt-dlp / FFmpeg 的整合測試；不連線 YouTube）。

### 2.2 發行紀錄（新 → 舊）

| 版本 | commit | 狀態 |
|---|---|---|
| **v2.3.0** | 3450eb4 | **正式版（Latest）**；程式碼同 v2.3.0-beta.1；setup.exe 106.1 MB（`6e2446e3…4595c6d`）、zip 144.1 MB（`49f6f0cd…167a5f`），sha256 已核對；**使用者實測無誤** |
| v2.3.0-beta.1 | d4c4219 | 預先發行；歌名與封面、播放清單子資料夾、拖曳、雙擊播放、完成通知、歷史紀錄改善；setup `399c68c5…b12cf4`、zip `1108f731…aad377b`；**使用者實測無誤** |
| v2.2.0 | 8325ae0 | 正式版；程式碼同 v2.2.0-beta.2；setup `aaf7346d…14adc9`、zip `e6eb4a32…3bc794`；**使用者實測無誤** |
| v2.2.0-beta.2 | 95b1fcb | 預先發行；MP3 品質欄「192 kbps → 124 kbps ⚠」；setup `95ee448c…9deeef`、zip `d762703b…914035`；**使用者實測無誤** |
| v2.2.0-beta.1 | 8893df6 | 預先發行；播放清單選擇對話框；setup `4ebe23db…2753e6`、zip `0dbaca59…41c711`；使用者回報 MP3 降級顯示 → beta.2 |
| v2.1.3-beta.1 | e133883 | 預先發行；使用者角度的文字與操作修正；使用者回報播放清單問題 → 由 v2.2.0 取代（未發 v2.1.3 正式版） |
| v2.1.2 | 230496f | 正式版；品質欄標示最高解析度、移除 Chrome / Edge；setup `a6d6e99e…9bd21f`、zip `53c8481c…dadc14`；**使用者實測無誤** |
| v2.1.1 | 1e6b4b0 | 正式版；品質欄修正；setup `dd66c142…ff5f72`、zip `f3f529b5…9687a`；變更已由 v2.1.2 實測涵蓋 |
| v2.1.0 | f77af01 | 正式版；新增安裝程式；setup `462e36e0…31fe97`、zip `d7e4c9a5…58454c`；**使用者實測無誤** |
| v2.1.0-beta.1 | 68afd24 | 預先發行；新增安裝程式；使用者實測無誤 |
| v2.0.0 | ab7e980 | 正式版；程式碼同 eb5d61d（僅更新文件）；zip 144.1 MB |
| v2.0.0-beta.1～5 | 3a381b7 / 66f0cf5 / 99fcf7d / 90af50e / eb5d61d | 預先發行；beta.2 新增 cookies、beta.4 縮小發行檔與 FFmpeg 改 LGPL、beta.5 批次移除與總進度修正 |

所有 Release 都有 4 個附件：`YT_Media_Tool-<版本>-win64-setup.exe`、`…-win64.zip` 與兩者的 `.sha256`。
**使用者決定保留所有 beta 版本，不刪除**。

### 2.3 各版改了什麼、改了哪些檔（新 → 舊）

**v2.3.0**（使用者第二次「使用者角度檢查」後選定的 4 項新功能＋歷史紀錄改善）

| 功能 | 修改的檔案與重點 |
|---|---|
| 歌名、演出者與封面 | `core/converter.py`：`postprocessors(..., embed_metadata)` 加入 `FFmpegThumbnailsConvertor`（jpg、before_dl）、`FFmpegMetadata`、`EmbedThumbnail`；`core/downloader.py`：`metadata_provider`、`writethumbnail`、`POSTPROCESSOR_STAGES` 新增「寫入歌曲資訊中」「嵌入封面中」、`SILENT_POSTPROCESSORS`；`app_context.py` 接上設定；`storage/settings.py` 新增 `embed_metadata`（預設開）；`gui/settings_dialog.py` 勾選框 |
| 播放清單子資料夾 | `gui/playlist_dialog.py`：`selected_by_group()`；`gui/main_window.py`：`choose_playlist_entries()` 改回傳 `list[list[str]]`、`_playlist_folder()`、`_finish_add(folders=...)`；`storage/settings.py` 新增 `playlist_subfolder`（預設開） |
| 拖曳網址 | `gui/main_window.py`：`setAcceptDrops`、`dragEnterEvent` / `dropEvent` / `_dropped_text()` / `_append_urls()`；輸入框 `setAcceptDrops(False)` |
| 雙擊播放 | `utils/system_open.py`：`open_media()`（只開 .mp3 / .mp4）、`_open_with_default_app()`；`gui/main_window.py`：`play()`、表格 `doubleClicked`、右鍵「播放（雙擊）」 |
| 全部完成通知 | `gui/main_window.py`：`_batch_counts`、`_idle_timer`（800 ms）→ `_check_queue_idle()` → `notify_queue_finished()` → `_show_notification()`（`QSystemTrayIcon`）＋ `QApplication.alert`；`storage/settings.py` 新增 `notify_on_complete`（預設開） |
| 歷史紀錄改善 | `gui/history_dialog.py` 重寫：只顯示檔名（完整路徑在提示）、搜尋、狀態顏色、雙擊 `reveal()`、右鍵複製網址 / `redownload()`；`gui/main_window.py`：`open_history()`、`redownload()`（`_finish_add(clear_input=False)`） |
| 文字 | `core/queue_manager.py`：取消訊息「使用者已取消」→「已取消下載」 |
| 測試與文件 | `tests/test_gui.py`、`tests/integration/test_local_pipeline.py`（`test_embed_title_artist_and_cover`：真實 yt-dlp＋FFmpeg 驗證 MP3 / MP4 的 title、artist 與 mjpeg 封面）、`tests/test_converter_and_errors.py`、`tests/test_queue_manager.py`；README、`docs/RELEASE_NOTES.md`、`docs/WINDOWS_INTEGRATION_TESTS.md`（C12–C17、E6a） |

**v2.2.0**（beta.1 → beta.2）

- 播放清單選擇對話框：新檔 `gui/playlist_dialog.py`（`PlaylistPickerDialog`、`PlaylistGroup`）：列出名稱與長度、搜尋、
  全選 / 全不選（只影響目前顯示的項目）、勾選清單本身＝整個清單；`playlist?list=` 預設全勾，`watch?v=…&list=…` 只預勾該影片
  （不在清單中時插在最前面）；讀取失敗時退回只加入該影片。
- `gui/main_window.py`：移除「展開播放清單」勾選框，含播放清單的網址一律開啟選擇對話框。
- `core/downloader.py`：`PlaylistEntry` 新增 `video_id`、`duration`。
- `gui/theme.py`：勾選框（`QCheckBox::indicator`、`QTreeView::indicator`）加上明顯外框，勾選時填滿藍色。
- beta.2：`gui/queue_table.py` 的 `quality_text()`：MP3 原始音源低於目標時顯示「192 kbps → 124 kbps ⚠」。
- 測試：`tests/test_gui.py`、`tests/fakes.py`、`tests/test_downloader.py`；文件：README、RELEASE_NOTES、WINDOWS_INTEGRATION_TESTS（C7、C8、C4）。

**v2.1.3**（只發 beta.1，由 v2.2.0 取代）

- `core/task_models.py`：狀態名稱「等待中 / 已完成 / 已取消」。
- `gui/queue_table.py`：狀態欄直接顯示階段（「MP3 轉檔中」，不再是「轉檔中（MP3 轉檔中）」）。
- `gui/main_window.py`：整體狀態加上「等待」筆數；詳細資訊把失敗原因放最前面；儲存設定時只套用有變更的項目
  （`_apply_settings_to_ui(previous)`）；記住上次使用的下載資料夾（`_ensure_output_dir` 寫回 `settings.download_dir`）。
- `core/errors.py`：年齡限制 / 會員專屬訊息改為提示可設定登入資訊；機器人驗證訊息改為「Firefox 或 cookies.txt」。
- `gui/settings_dialog.py`：cookies 說明改寫、統一用「您」；`gui/history_dialog.py`：提示文字修正。

**v2.1.2 以前**（摘要）

- v2.1.2：品質欄「720p（最高 1080p）」（`describe_selection` / `describe_result`）；cookies 來源移除 Chrome / Edge。
- v2.1.1：品質欄只在不同時顯示「目標 → 實際 ⚠」；`release.yml` 自動去除 tag 前後空白。
- v2.1.0：Inno Setup 安裝程式（`packaging/installer.iss`、`scripts/build_installer.*`、`scripts/verify_installer.py`）；
  具名 mutex `YTMediaTool_AppMutex`；EXE 版本資源由 `__init__.py` 自動產生；`tests/test_release_config.py`。
- v2.0.0 系列：Windows CI / Release workflow / FFmpeg 驗證流程；cookies 功能；Qt 繁中翻譯；批次移除；
  總進度不計失敗與取消；發行檔縮小（移除 `opengl32sw.dll` 與非中文翻譯、FFmpeg 改 BtbN LGPL shared）；
  修正 Windows「等待刪除」與「全部取消」競爭。

### 2.4 專案結構（主要檔案）

```
main.py                         啟動檔（開發與 PyInstaller 共用）
requirements.txt / -dev.txt     全部固定版本（已確認皆有 win_amd64 / py3.12 wheel）
pyproject.toml                  套件資訊、版本號、pytest、ruff 設定（Apache-2.0）
src/yt_media_tool/
  __init__.py                   __version__（版本號唯一來源；EXE / 安裝程式自動取用）
  app.py                        進入點：日誌、Job Object、具名 mutex、單一執行個體鎖、Qt 中文翻譯、--smoke-test / --version
  app_context.py                組合 DB / 設定 / Downloader（cookies、metadata provider）/ QueueManager
  core/task_models.py           任務模型與狀態機（等待中 / 下載中 / 轉檔中 / 已完成 / 失敗 / 已取消）
  core/url_parser.py            網址分類、正規化、去重、錯誤原因
  core/downloader.py            yt-dlp 下載引擎（暫存隔離、取消、驗證、不覆蓋移動、播放清單讀取）
  core/converter.py             FFmpeg / FFprobe / Deno 偵測、ffprobe 驗證、格式選擇、後處理（含歌名與封面）
  core/cookies.py               YouTube cookies 設定 → yt-dlp 參數（cookies.txt 只用副本）
  core/queue_manager.py         佇列排程、取消、重試、保存與恢復（不依賴 Qt）
  core/errors.py                例外 → 中文說明（yt-dlp、FFmpeg、cookies、磁碟、權限）
  storage/database.py           SQLite（參數化 SQL、PRAGMA user_version migration，目前 v2）
  storage/settings.py           AppSettings（cookies、embed_metadata、playlist_subfolder、notify_on_complete 等）
  gui/main_window.py            主視窗（加入佇列、播放清單、拖曳、雙擊播放、批次操作、完成通知）
  gui/playlist_dialog.py        播放清單選擇對話框（勾選要下載的影片，可依清單分組取得）
  gui/history_dialog.py         下載歷史（搜尋、在檔案總管中顯示、重新下載）
  gui/queue_table.py            表格 model、品質 / 狀態文字、進度條與操作按鈕 delegate
  gui/settings_dialog.py        設定（含「YouTube 登入資訊（選用）」）
  gui/qt_bridge.py / workers.py / theme.py / i18n.py
  utils/paths.py                AppData、隨附檔位置、安全檔名、FileNameReserver
  utils/win_job.py              Job Object（結束時終止子程序）、具名 mutex（供安裝程式偵測）
  utils/system_open.py          開啟資料夾、在檔案總管中選取檔案、以預設播放器開啟 MP3 / MP4
  utils/logging_utils.py
tests/                          單元、GUI（pytest-qt）、integration/（本機 HTTP＋真實 yt-dlp / FFmpeg）、fakes.py
scripts/
  setup_windows.bat / run_dev.bat / build_exe.bat   Windows 開發與打包
  build_installer.py / .bat     以 Inno Setup 建立 setup.exe 與 .sha256
  verify_installer.py           CI 中實際靜默安裝、啟動、轉檔、解除安裝並檢查捷徑與登錄
  fetch_ffmpeg.ps1              依 manifest 下載並驗證 FFmpeg 到 vendor/ffmpeg
  verify_dist.py                發行資料夾檢查 + 大小報告 + 用隨附 FFmpeg 實際轉 MP3 / MP4
  make_release_zip.py           壓縮 zip 並產生 .sha256
  ci_run.ps1                    CI 執行包裝：失敗時把最後 80 行輸出轉成 GitHub 註解
  junit_annotations.py          pytest 失敗 → GitHub 註解（找不到結果檔時略過）
  make_icon.py                  產生 assets/app.ico
packaging/
  yt_media_tool.spec            PyInstaller one-folder（FFmpeg 於 COLLECT 後複製；版本資源由範本產生）
  version_info.txt              EXE 版本資源範本（$VERSION$ / $VERSION_TUPLE$）
  ffmpeg_manifest.json          FFmpeg 版本 / 網址 / SHA256（唯一來源）
  installer.iss                 Inno Setup 6.5+ 安裝程式腳本
  installer_notice.txt          安裝精靈顯示的使用聲明
  ChineseTraditional.isl        繁中語系備援副本（Inno Setup 內建版本優先）
.github/workflows/
  windows-ci.yml                push main：Windows 測試 + 完整打包 + 建立並實測安裝程式（與 Release 同流程）
  release.yml                   Run workflow / 推 tag / 推 release/v* 分支 → 測試、打包、安裝程式 → 建立 Release
  ffmpeg-verify.yml             manifest 變更時交叉驗證 FFmpeg SHA256
  ffmpeg-candidates.yml         比較 FFmpeg 候選建置的大小與 MP3 支援（只在修改此檔時執行）
docs/WINDOWS_INTEGRATION_TESTS.md   Windows 實機測試清單（A–I 段；C12–C17、E6a 為 v2.3.0 新功能）
docs/RELEASE_NOTES.md               Release 頁面說明（release.yml 會讀取）
THIRD_PARTY_NOTICES.md              第三方授權
```

---

## 3. 剛剛做的關鍵決定，以及為什麼這樣決定

### 3.1 最近兩輪（v2.1.3～v2.3.0）的決定

| 決定 | 原因 |
|---|---|
| **移除「展開播放清單」勾選框**，含播放清單的網址一律開啟「選擇要下載的影片」對話框（v2.2.0） | 使用者回報「不勾選就無法加入」（最可能是貼了 `watch?v=…&list=…`，未勾選只加入單支），並要求能選歌。用一個選擇視窗同時解決兩件事，介面上不再有容易誤會的勾選框。 |
| `watch?v=…&list=…` **只預勾貼上的那一支**；`playlist?list=` 預設全勾 | 從網址列複製時多半只想要正在播的那首；想要整個清單按「全選」即可。 |
| MP3 降級顯示「**192 kbps → 124 kbps ⚠**」（v2.2.0-beta.2） | 使用者要求與 MP4 的「1080p → 720p ⚠」一致；原本只有「192 kbps ⚠」看不出實際音質。 |
| 狀態「**已取消 / 已完成 / 等待中**」（v2.1.3） | 「取消」狀態就在「取消」按鈕旁邊，看起來像按鈕。 |
| **記住上次使用的下載資料夾**、儲存設定時只套用有變更的項目 | 原本重開程式或存設定後，主視窗的資料夾 / 格式 / 品質會被重設回預設值。 |
| 年齡限制 / 會員專屬錯誤訊息改為「可設定登入資訊後重試」 | 原本寫「無法下載」，與 README「帳號有權觀看即可下載」矛盾；以使用者自己帳號登入屬正當驗證，非規避。 |
| v2.1.3 **不發正式版**，直接由 v2.2.0 取代 | beta.1 實測就回報播放清單問題，修正屬新功能，依規則升 minor 版本。 |
| **歌名與封面用 yt-dlp 內建後處理**（Metadata / EmbedThumbnail＋縮圖轉 JPEG），不另加 mutagen 等套件 | 與 yt-dlp 官方 `--embed-metadata --embed-thumbnail --convert-thumbnails jpg` 一致，只需隨附的 FFmpeg（FFmpeg 內建 mjpeg 編碼器與 WebP 解碼器，LGPL 版本也有；使用者以 v2.3.0-beta.1 實機確認封面正常）；縮圖在任務暫存資料夾處理，不影響檔案安全設計。JPEG 播放器相容性最好、檔案較小。 |
| 縮圖轉檔 `when: before_dl`，且列在 `SILENT_POSTPROCESSORS` | 與 yt-dlp CLI 相同時機；它在下載前執行，若觸發狀態變更會讓任務先變「轉檔中」再回「下載中」、進度跳動。 |
| 播放清單子資料夾：**只下載貼上的那一支時不建資料夾** | 使用者只是從清單裡抓一首歌，不該多出一個只有一首歌的資料夾。 |
| 完成通知用 **800 ms 單次計時器延後判斷**是否全部結束 | 佇列事件以非同步送到主執行緒；測試中發現連續完成的任務會讓「佇列已空」被判斷兩次，拆成兩則「1 部完成」。延後判斷可合併成一則。 |
| 通知**只在視窗不在前景時**跳出（工作列閃爍＋系統匣通知，15 秒後收起圖示） | 使用者正看著程式時不打擾，只更新狀態列；系統匣圖示不常駐。 |
| 雙擊播放用 `open_media()` **只開 .mp3 / .mp4** | 交給系統預設程式開啟的只限本程式產生的媒體檔，避免意外執行其他類型的檔案。 |
| 輸入框 `setAcceptDrops(False)`，拖放交給主視窗**另起一行附加** | QPlainTextEdit 預設會把拖入的文字插在滑鼠位置，可能插進既有網址中間。 |
| 歷史紀錄「重新下載」**不清除輸入框** | 使用者可能正在輸入其他網址。 |
| 三個新功能都**預設開啟並可在設定關閉**（`embed_metadata`、`playlist_subfolder`、`notify_on_complete`） | 大多數使用者想要；若某環境出問題（例如封面嵌入失敗），可自行關閉而不必等新版。 |
| 使用者**未選**的小改進不做：記住上次格式與品質、加入前提醒已下載過、同時下載上限提高到 5 | 使用者在 2026-10-31 的選項中沒有勾選。 |

### 3.2 架構、檔案安全與發布的決定（長期有效）

| 決定 | 原因 |
|---|---|
| **yt-dlp 的 `paths.home` 設為任務專屬暫存資料夾**，成品經 ffprobe 驗證後才用 `move_no_overwrite` 移到下載資料夾 | 早期實測發現：yt-dlp 把下載資料夾中**使用者既有的同名中繼檔**當成「已下載」，轉 MP3 後**刪除了使用者的檔案**。現在 yt-dlp 完全不接觸下載資料夾。 |
| 暫存在 `<下載資料夾>\.ytmt_tmp\task_<id>_<亂數>\`，取消 / 失敗只刪自己的資料夾 | 同磁碟區移動為原子操作；不會誤刪其他任務或使用者檔案。 |
| 執行緒（非多程序）＋ `CancelToken`；Windows Job Object（`utils/win_job.py`） | yt-dlp hook 可即時中斷下載；程式結束時 Job Object 一併終止 ffmpeg / deno 子程序。代價：FFmpeg 轉檔中取消要等該步驟結束。 |
| 隨附 **Deno**（pip 套件 `deno==2.9.8`）＋ `yt-dlp-ejs` | yt-dlp 2025.11 起 YouTube 需要 JS 執行環境，缺少時格式不完整。Deno 93.5 MB 無法省。 |
| **cookies 功能**（設定 → YouTube 登入資訊，預設不使用） | 使用者實測遇到「Sign in to confirm you're not a bot」，yt-dlp 官方解法即提供使用者自己帳號的 cookies，屬正當驗證、非規避；經使用者同意後加入。cookies.txt 只用暫存副本（yt-dlp 會寫回檔案、並行會互相覆寫）。 |
| cookies 來源**移除 Chrome / Edge**（只剩不使用 / Firefox / cookies.txt） | Chrome 127+ 的 app-bound encryption 讓 yt-dlp 在 Windows 上讀不到 cookies，使用者回報「選了也沒用」。舊設定的 chrome / edge 載入時自動改回「不使用」。cookies.txt 方式使用者實測成功。 |
| **FFmpeg 用 BtbN win64-lgpl-shared 9.0.2**（使用者選擇） | CI 實測比較：gyan essentials 200.9 MB → lgpl-shared 約 144–167 MB，且為 LGPL、不含 GPL 元件；MP3（libmp3lame）與 stream copy 皆具備。代價：BtbN 每日建置不保證長期保留。 |
| FFmpeg **不交給 PyInstaller**，在 spec 的 COLLECT 之後原樣複製到 `_internal/ffmpeg` | 以 datas 加入時 PyInstaller 分析 DLL 相依，在 `_internal` 最上層多放一份（+142 MB）。 |
| FFmpeg SHA256 一律**交叉驗證**後才寫入 manifest | 下載檔、GitHub release asset digest、建置者公布的 checksums 三者一致才採用。 |
| **安裝程式用 Inno Setup**，預設「只為目前使用者」安裝（可改所有使用者） | 不需系統管理員權限即可安裝與升級；資料本來就在 `%LOCALAPPDATA%`，與安裝位置無關。 |
| 安裝程式以 **AppMutex** 偵測執行中的程式；升級前清除舊 `_internal` | 避免覆蓋執行中的檔案；避免舊版已移除的 DLL 殘留。 |
| 解除安裝時**詢問**是否刪除 `%LOCALAPPDATA%\YT_Media_Tool`，靜默模式預設保留；下載資料夾永不碰 | 使用者資料由使用者決定；影片檔絕不能因解除安裝而遺失。 |
| 版本號以 `__init__.py` 為唯一來源，EXE 版本資源與安裝程式自動取用 | 原本 `version_info.txt` 寫死 2.0.0，升版時會不一致；改為範本並加測試檢查。 |
| Release 用 **workflow_dispatch（使用者按 Run workflow）** | 本雲端環境推送 git tag 被代理 403 擋下；建立公開 Release 需由使用者觸發。 |
| 新功能先發**預先發行版本**（tag 含 `-beta.N`），使用者實測後再發正式版；新功能升 minor、修正升 patch | 自動化測試無法連 YouTube；需使用者實機確認下載與安裝流程。 |
| Windows CI 的打包工作與 Release 完全相同（只差不發布） | 讓每次 push 都驗證完整發行路徑（含安裝程式），不必請使用者反覆按 Run workflow 試錯。 |
| one-folder（`_internal`）而非 one-file | 原始規格要求；啟動快、防毒誤判少。 |
| Apache-2.0 授權 | 使用者建立 repo 時選擇。 |

---

## 4. 還沒做的下一步

**目前沒有待辦的必要工作。** v2.3.0 已發布為 Latest；使用者有新需求或回報問題時，依下方流程以新版本號修正並發布。

之後可能的方向（**皆需使用者決定，未經同意不要做**）：

- 使用者 2026-10-31 未選的小改進：記住上次在主視窗選的格式與品質、加入前提醒「歷史紀錄中已下載過」、同時下載上限從 3 提高到 5。
- **多線程下載**（使用者詢問過，尚未決定）：
  - 已支援「同時下載多個影片」1–3 筆（原始規格上限 3）。
  - 選項 A：設定新增「單一影片分段同時下載數」（yt-dlp `concurrent_fragment_downloads`，建議 1–8、預設 4）；
    只對分段格式（直播錄影、HLS、部分 DASH）有加速效果，一般 YouTube 影片無差別。
  - 選項 B：同時下載數量上限從 3 提高（例如 5），需註明可能觸發 YouTube 機器人驗證。
  - 不建議外接 aria2c 多連線（需多附程式，且易被 YouTube 限速或要求驗證）。
- 依 `docs/WINDOWS_INTEGRATION_TESTS.md` 完整跑一次實機清單。
- `actions/upload-artifact@v5` 的 Node.js 20 淘汰警告可評估升級。

### 發布新版本的流程

1. 修改程式並補測試；本機跑完整測試數次與 ruff（見第 5 節「流程習慣」）。
2. 同步更新版本號：`src/yt_media_tool/__init__.py`、`scripts/build_exe.bat` 的 `VERSION`、`pyproject.toml`
   （`tests/test_release_config.py` 會檢查三者一致；EXE 與安裝程式版本自動取 `__init__.py`）。修正升 patch、新功能升 minor。
3. 更新 `docs/RELEASE_NOTES.md`（Release 頁面內容來源）、README 與 `docs/WINDOWS_INTEGRATION_TESTS.md`。
4. 推送到 `main`（本環境的工作分支也一併推送），等該 commit 的 Windows CI 兩個工作（測試；打包 EXE 與安裝程式）都 success。
5. 請使用者開 https://github.com/makodo123/YT_Media_Tool/actions/workflows/release.yml → Run workflow，
   tag 填 `vX.Y.Z-beta.1`；使用者實測無誤後再以 `vX.Y.Z` 發布正式版（程式碼不必再改）。
6. 用 API 確認 Release 的 4 個附件與 `.sha256` 內容（附錄 B），並更新本文件。

---

## 5. 有哪些地方不要碰、有什麼雷

### 檔案安全（最重要）
- **不要**把 yt-dlp 的 `paths.home` 或 `outtmpl` 改回下載資料夾，也不要開 `overwrites`——會重現「刪除使用者檔案」的嚴重問題（`tests/test_downloader.py::test_same_name_files_are_not_overwritten` 守著）。
- 取消 / 失敗只能刪 `temp_dir`（任務自己的暫存資料夾），不可刪 `.ytmt_tmp` 底下其他東西或下載資料夾內任何檔案。
- 縮圖（`writethumbnail`）也必須留在暫存資料夾；`_run_download` 只挑副檔名為 .mp3 / .mp4 的成品，縮圖會隨暫存資料夾刪除。
- `system_open.open_media()` 的副檔名白名單（.mp3 / .mp4）不要放寬。

### 近期新增功能的雷
- `MainWindow.choose_playlist_entries()` 回傳 **`list[list[str]]`（依清單分組）或 `None`（取消）**；測試以 monkeypatch 取代它，改回傳格式要一起改測試。
- 完成通知依賴 `_idle_timer` 延後判斷；**不要改成在 `_on_task_finished` 當下判斷**（會拆成多則通知，`test_notify_once_when_whole_queue_finishes` 守著）。
- 深色主題下 Fusion 的勾選框未勾選時與背景同色，**看不到**；`gui/theme.py` 的 `::indicator` 樣式不要刪。新增有勾選框的元件（例如 QListView）也要套用。
- `converter.probe_media()` 判斷影像串流時會略過 `attached_pic`（封面）；改這段會讓有封面的 MP3 被誤判為有影像、或 MP4 驗證錯誤。
- 狀態欄文字直接顯示 `task.stage`（例如「準備中」「取得影片資訊中」），測試中的 FakeDownloader 只會停在「準備中」。
- `PlaylistEntry` 的 `video_id` 用來判斷預先勾選；`extract_playlist()` 要持續填入。

### Windows 專屬的雷（CI 上踩過）
- **從 pwsh 呼叫 Windows PowerShell 5.1**：繼承的 `PSModulePath` 會讓 `Get-FileHash`、`Expand-Archive`、`Compress-Archive` 失效。腳本中一律用 .NET（`fetch_ffmpeg.ps1`）或 Python（`make_release_zip.py`）；`ci_run.ps1` 會清除 `PSModulePath`。
- **PowerShell 5.1 `Set-Content -Encoding UTF8` 會加 BOM**：讀 JSON 用 `utf-8-sig`；寫 JSON 用 `[IO.File]::WriteAllText(..., UTF8Encoding($false))`。
- `.ps1` 要 **UTF-8 with BOM + CRLF**；`.bat` 要 **CRLF**（中文訊息前有 `chcp 65001`）。用 Python 編輯這些檔時記得保留格式（改版本號時用 bytes 取代）。
- PowerShell 的 `$args` 是自動變數，不可自訂使用。
- **測試不可執行假的 .exe**：有桌面的 Windows 會跳「不支援的 16 位元應用程式」對話框卡住 pytest（`test_converter_and_errors.py` 用 `fake_version` fixture 替換 `_version_of`）。
- 路徑比對不要寫死 `/`：`str(Path("/d"))` 在 Windows 是 `\d`。
- Windows 剛刪除的資料夾可能處於「等待刪除」，在其中建立子資料夾會暫時 PermissionError（`_make_task_dir` 已重試）。

### 安裝程式
- `installer.iss` 的 `AppId` GUID **不可更改**（改了會變成另一個程式，無法升級舊安裝）。
- `AppMutex` 與 `win_job.APP_MUTEX_NAME`、`AppDataFolder` 與 `APP_ID` 必須一致（測試會檢查）。
- `.iss`、`installer_notice.txt`、`.isl` 必須是 UTF-8 with BOM + CRLF（測試會檢查），否則中文會亂碼。
- 解除安裝程式會先複製自己到暫存資料夾再執行，原程序立即結束；`verify_installer.py` 以輪詢等待完成。
- 解除安裝的資料刪除提示只刪 `%LOCALAPPDATA%\YT_Media_Tool`，**絕不可**擴大到下載資料夾。
- 本環境（Linux）無法執行 Inno Setup；`.iss` 的修改只能靠 Windows CI 驗證。

### 打包
- FFmpeg 檔案在 spec 的 **COLLECT 之後**手動複製，不要改回 `datas`（會重複打包約 140 MB）。`verify_dist.py` 會檢查。
- `packaging/ffmpeg_manifest.json` 的 `sha256` 只能填**交叉驗證過**的值；`fetch_ffmpeg.ps1` 在 sha256 為空時預設拒絕建置。
- **BtbN 的 autobuild release 可能被刪除**：若 fetch 404，用 `ffmpeg-candidates.yml`（修改該檔觸發）比較新版本，更新 manifest（url、checksum_url、sha256）後由 `ffmpeg-verify.yml` 驗證。
- **CI 的整合測試用 choco 安裝的 FFmpeg，不是隨附的 BtbN 版本**；隨附版本只由 `verify_dist.py` 驗證 MP3 / MP4 轉檔。換 FFmpeg 版本後，歌名與封面嵌入需請使用者實機確認（或擴充 `verify_dist.py`）。
- spec 的 `_keep()` 會刪除非 `qtbase_zh_TW.qm` / `qt_zh_TW.qm` 的 Qt 翻譯與 `opengl32sw.dll`；若改用 Qt OpenGL / 其他語系需調整。
- 版本號在三處：`__init__.py`、`build_exe.bat` 的 `VERSION`、`pyproject.toml`（測試檢查一致）；
  `release.yml` 另檢查 tag 與版本一致（tag 可為 `vX.Y.Z` 或 `vX.Y.Z-後綴`）。
- `version_info.txt` 是範本，不要填入實際版本號。

### 本雲端環境的限制
- tag 格式常出錯：曾打成 `v2.0.0beta.5`（少 `-`）、「 v2.1.1」（前面有空白，`release.yml` 現已 `Trim()`）。請提醒格式 `vX.Y.Z` 或 `vX.Y.Z-beta.N`，
  且要從 workflow 頁面重新 Run，**不要 Re-run 失敗的那次**（會沿用錯誤的輸入與舊 commit）。使用者回報時常貼上舊的 run 連結：先用 API 確認是否真的有新 run。
- 使用者回覆「沒問題」有時只是「好的」，有時是「實測無誤」：**先用 API 查是否真的有新的 Release run**，再依情況回覆。
- **不能推送 git tag**（代理 403）；**不能建立 / 刪除 GitHub Release**（屬公開動作，需使用者觸發；推 `release/v*` 分支也被拒）。發布一律請使用者按 Run workflow。
- 連不到 YouTube（代理擋）；`gh` CLI 的 token 無效。GitHub 公開 API（未驗證）可讀 runs / jobs / annotations / releases，**讀不到完整日誌**——所以失敗原因要靠 `ci_run.ps1` / `junit_annotations.py` 轉成註解。
- `windows-ci.yml` 設有 `cancel-in-progress`：CI 跑到一半時再 push 會取消正在跑的那一輪；只改 `.md` / `docs/**` 不會觸發 CI。
- 本 session 指定的工作分支為 `ccr-8a1768df-b3zofa`；慣例是同時推送到該分支與 `main`（`main` 才會觸發 CI）。
- 新環境需重建 `.venv` 並安裝 GUI 測試用系統套件（附錄 B），否則 pytest 會因 `libEGL.so.1` 缺失而無法啟動。

### 流程習慣
- push 前跑完整測試數次再 commit（曾因指令串接錯誤在測試失敗時推送）：
  ```bash
  QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
  .venv/bin/ruff check src tests main.py scripts
  ```
- 介面改動後用 offscreen 截圖自行檢查（例如建立 `MainWindow` / 對話框後 `widget.grab().save(...)`）。
- 不要叫使用者發布，直到該 commit 的 Windows CI 兩個工作都 success。

---

## 附錄 A：使用者偏好與背景

- 全程使用繁體中文回覆；說明技術選項時用淺白比喻（使用者曾問「A 是什麼意思？」）。
- 等待 CI 或發布時，使用者通常回覆「等 CI 通過再通知我」「發布完成再通知我」：請在背景監看（Bash 背景輪詢 API），完成後主動回報。
- 使用者實測後會回覆「下載測試後再回報」/「下載測試後沒問題」/「沒問題」；回報問題時會附截圖。
- 新功能由使用者挑選：提出選項（說明好處與代價）後請使用者複選，只做使用者選的項目。
- 公開發布（Run workflow）由使用者親自按；本環境無法推 tag 或建立 Release。
- 使用者為 **Claude Pro 方案**，已確認「Usage credits（額外用量）」為**關閉**，不會產生額外費用；儲存庫為公開，GitHub Actions 不收費。
- 所有 beta 版本保留，不刪除。
- 每次發布後要更新 handoff.md，且須包含本文件的五大項。

## 附錄 B：常用指令（Linux 雲端環境）

```bash
# 開發環境（新環境需重建）
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# GUI 測試需要：
apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 fonts-noto-cjk

# 最新 CI 狀態；某個 run 的工作與步驟
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/runs?per_page=5"
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/runs/<run_id>/jobs"
# 某個 job 的註解（失敗原因、大小報告）
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/check-runs/<job_id>/annotations"
# Release 與附件 digest；最新正式版；.sha256 內容
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases"
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases/latest"
curl -sSL "https://github.com/makodo123/YT_Media_Tool/releases/download/<tag>/YT_Media_Tool-<版本>-win64.zip.sha256"
```
