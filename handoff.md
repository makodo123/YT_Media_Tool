# YT Media Tool 交接文件

> 更新時間：2026-10-30｜儲存庫：https://github.com/makodo123/YT_Media_Tool （分支 `main`，最新 commit 見 `git log`）
> 使用者以**繁體中文**溝通，請全程使用繁體中文回覆。

---

## 1. 任務目標

從零建立 Windows 桌面程式 **YT Media Tool V2.0**（繁體中文、深色主題）：

- YouTube 單一 / 多網址批次下載；MP4（720p / 1080p / 最高）與 MP3（128 / 192 / 320 kbps）
- 下載佇列：即時進度、速度、ETA、單筆 / 全部取消、失敗重試、清除已完成、重開程式恢復未完成任務、並行 1–3 筆
- FFmpeg 合併與轉檔，SQLite 保存佇列 / 歷史 / 設定，PyInstaller one-folder EXE
- 技術：Python 3.12、PySide6、yt-dlp（Python API）、FFmpeg / FFprobe、SQLite、PyInstaller、pytest
- 限制：只下載有權利或獲授權的內容；**不得實作 DRM 或存取限制規避**；不得把使用者輸入拼成 shell 指令；
  資料寫在 `%LOCALAPPDATA%\YT_Media_Tool`，不可寫入程式目錄；同名檔案不可覆蓋。
- 原始需求規格的完整內容在第一次對話中；README.md 的「功能」表已涵蓋全部要求。

### 目前階段：v2.2.0（播放清單選擇）已推送到 `main`，CI 通過（81d6ee1，run 41157586352），等使用者發布 `v2.2.0-beta.1`

- 使用者要求「以使用者角度檢查文字與功能」並同意全部修正（版本號 2.1.3），已合併到 `main`。
  `v2.1.3-beta.1` 已發布：https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.1.3-beta.1
- 使用者實測 v2.1.3-beta.1 回報：(1) 播放清單「不勾選就無法加入」（程式碼中 `playlist?list=` 不需勾選；最可能是貼了
  `watch?v=…&list=…`，未勾選時只加入單支影片）；(2) 想選擇播放清單中要下載的歌曲。
  → 改為 **v2.2.0**：移除勾選框，任何含播放清單的網址都開啟「選擇要下載的影片」對話框（`gui/playlist_dialog.py`）。
  v2.1.3 不另發正式版，直接以 v2.2.0 取代。

- **最新正式版 `v2.1.2`**（標示為 Latest），提供安裝版（`-setup.exe`）與免安裝版（zip）：
  https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.1.2
- 使用者已在 Windows 實機測試 v2.1.0 並確認無誤：下載、cookies、MP4 / MP3、批次移除、總進度、安裝 / 升級 / 解除安裝。
- 使用者已實測 **v2.1.2 下載無誤**（2026-10-30）；v2.1.2 包含 v2.1.1 的品質欄修正，故 v2.1.1 的變更一併視為已驗證。
- 之後若有新需求或問題回報，以新版本號修正並發布（流程見第 4 節）。

---

## 2. 目前完成的內容

### 發行狀態

| 版本 | commit | 狀態 |
|---|---|---|
| v2.0.0-beta.1 | 3a381b7 | 已發布（舊版） |
| v2.0.0-beta.2 | 66f0cf5 | 已發布（新增 cookies） |
| v2.0.0-beta.3 | 99fcf7d | 已發布；使用者實測下載正常 |
| v2.0.0-beta.4 | 90af50e | 已發布（程式碼同 b122bf8）；縮小發行檔、FFmpeg 改 LGPL |
| v2.0.0-beta.5 | eb5d61d | 已發布；批次移除、總進度修正；使用者實測無誤 |
| v2.0.0 | ab7e980 | 正式版；程式碼同 eb5d61d（僅更新文件）；zip 144.1 MB |
| v2.1.0-beta.1 | 68afd24 | 已發布（預先發行）；新增安裝程式；使用者實測無誤 |
| v2.1.0 | f77af01 | 正式版，使用者實測無誤；程式碼同 68afd24；setup.exe 106.1 MB（`462e36e0…31fe97`）、zip 144.1 MB（`d7e4c9a5…58454c`），sha256 已核對 |
| v2.1.1 | 1e6b4b0 | 正式版；品質欄修正；setup.exe 106.1 MB（`dd66c142…ff5f72`）、zip 144.1 MB（`f3f529b5…9687a`），sha256 已核對；變更已由 v2.1.2 實測涵蓋 |
| **v2.1.2** | 230496f | **正式版（Latest）**；品質欄標示最高解析度、移除 Chrome / Edge；setup.exe 106.1 MB（`a6d6e99e…9bd21f`）、zip 144.1 MB（`53c8481c…dadc14`），sha256 已核對；**使用者實測下載無誤** |
| v2.1.3-beta.1 | e133883 | 已發布（預先發行）；使用者角度的文字與操作修正；setup.exe 106.1 MB（`4c1caf4f…68e566`）、zip 144.1 MB（`6ec04c07…6e9fda`），sha256 已核對；使用者實測回報播放清單問題 → 由 v2.2.0 取代 |

各版重點：

- beta.4：發行資料夾 412.4 MB → **333.4 MB**；FFmpeg 改 BtbN LGPL shared；確認對話框按鈕改中文。
- beta.5：佇列可批次移除（「移除所選」按鈕、多選右鍵選單、Delete 鍵）；總進度不計入失敗與取消的任務。
- v2.1.0：新增 Inno Setup 安裝程式；EXE 版本資訊改為自動取用程式版本號。
- v2.1.1：品質欄不再顯示「720p → 720p」：實際與目標相同只顯示一次；低於目標「1080p → 720p ⚠」；
  最高可用解析度「最高可用解析度 → 2160p」；MP3 高於原始音源「320 kbps ⚠」（`gui/queue_table.py` 的 `quality_text()`，
  以數字比較解析度；完整說明在儲存格提示）。發布流程同時改為自動去除 tag 前後空白。
- v2.2.0（未發布）：播放清單選擇對話框——列出名稱與長度、可搜尋、全選 / 全不選（只影響目前顯示的項目）、
  勾選清單本身＝整個清單；`playlist?list=` 預設全勾，`watch?v=…&list=…` 只預勾該影片（不在清單中時插在最前面）；
  讀取失敗時退回只加入該影片。`PlaylistEntry` 新增 `video_id`、`duration`。深色主題的勾選框加上明顯外框
  （原本 Fusion 未勾選的框與背景同色，看不到）。包含 v2.1.3 的所有修正。
- v2.1.3（只發 beta.1）：使用者角度檢查後的修正——
  狀態名稱改為「等待中 / 已完成 / 已取消」（「取消」狀態易與「取消」按鈕混淆）；狀態欄直接顯示階段
  （「MP3 轉檔中」，不再顯示「轉檔中（MP3 轉檔中）」）；整體狀態加上「等待」筆數；詳細資訊把失敗原因放最前面；
  儲存設定時只套用有變更的項目（原本會把主視窗目前選的格式 / 品質 / 資料夾重設）；記住上次使用的下載資料夾
  （加入佇列時寫回 `settings.download_dir`）；年齡限制 / 會員專屬錯誤訊息改為提示可設定登入資訊（原本寫「無法下載」，
  與 README 已知限制矛盾）；機器人驗證訊息改為「Firefox 或 cookies.txt」；cookies 說明文字改用「您」並改寫；
  播放清單網址不必勾選即直接讀取（仍會先確認數量），勾選框改為「影片網址含播放清單時，下載整個清單」，
  只影響 `watch?v=…&list=…` 網址。
- v2.1.2：影片有更高解析度時品質欄顯示「720p（最高 1080p）」（`describe_selection` 附「最高 Np，可用解析度：…」，
  `describe_result` 保留附註；使用者原本以為選 720p 應顯示「1080p → 720p」，但那會與 ⚠ 降級警告混淆，故改用此格式）；
  cookies 來源移除 Chrome / Edge。

**使用者決定保留所有 beta 版本，不刪除**（正式版為 Latest，一般使用者不會下載到 beta）。

### 專案結構（主要檔案）

```
main.py                         啟動檔（開發與 PyInstaller 共用）
requirements.txt / -dev.txt     全部固定版本（已確認皆有 win_amd64 / py3.12 wheel）
pyproject.toml                  套件資訊、版本號、pytest、ruff 設定（Apache-2.0）
src/yt_media_tool/
  __init__.py                   __version__（版本號唯一來源；EXE / 安裝程式自動取用）
  app.py                        進入點：日誌、Job Object、具名 mutex、單一執行個體鎖、Qt 中文翻譯、--smoke-test / --version
  app_context.py                組合 DB / 設定 / Downloader / QueueManager
  core/task_models.py           任務模型與狀態機（等待 / 下載中 / 轉檔中 / 完成 / 失敗 / 取消）
  core/url_parser.py            網址分類、正規化、去重、錯誤原因
  core/downloader.py            yt-dlp 下載引擎（見第 3 節的檔案安全設計）
  core/converter.py             FFmpeg / FFprobe / Deno 偵測、ffprobe 驗證、格式選擇字串
  core/cookies.py               YouTube cookies 設定 → yt-dlp 參數（cookies.txt 只用副本）
  core/queue_manager.py         佇列排程、取消、重試、保存與恢復（不依賴 Qt）
  core/errors.py                例外 → 中文說明（yt-dlp、FFmpeg、cookies、磁碟、權限）
  storage/database.py           SQLite（參數化 SQL、PRAGMA user_version migration，目前 v2）
  storage/settings.py           AppSettings（含 cookies_source / cookies_file）
  gui/main_window.py            主視窗（含批次移除、多選右鍵選單）
  gui/playlist_dialog.py        播放清單選擇對話框（勾選要下載的影片）
  gui/queue_table.py            表格 model、進度條與操作按鈕 delegate
  gui/settings_dialog.py        設定（含「YouTube 登入資訊（選用）」）
  gui/history_dialog.py / qt_bridge.py / workers.py / theme.py / i18n.py
  utils/paths.py                AppData、隨附檔位置、安全檔名、FileNameReserver
  utils/win_job.py              Job Object（結束時終止子程序）、具名 mutex（供安裝程式偵測）
  utils/system_open.py / logging_utils.py
tests/                          211 個測試 + 1 個僅 Windows 執行（單元、GUI、本機 HTTP 整合；不連線 YouTube）
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
docs/WINDOWS_INTEGRATION_TESTS.md   Windows 實機測試清單（A–I 段；I 為安裝程式）
docs/RELEASE_NOTES.md               Release 頁面說明（release.yml 會讀取）
THIRD_PARTY_NOTICES.md              第三方授權
```

### 主要修改紀錄（依時間）

- 新增 Windows CI、Release workflow、FFmpeg 驗證流程；修正多個只在 Windows 才出現的問題
- cookies 功能（`core/cookies.py`、設定對話框、錯誤訊息）
- 修正：Windows 暫存資料夾「等待刪除」競爭（`downloader._make_task_dir` 重試）、「全部取消」競爭（先取消等待中再中斷執行中）
- 縮小：移除 `opengl32sw.dll` 與非中文 Qt 翻譯；FFmpeg 改 BtbN lgpl-shared；修正 FFmpeg DLL 重複打包
- 載入 Qt 繁中翻譯（`gui/i18n.py`），標準按鈕顯示「是 / 否 / 確定 / 取消」
- 批次移除：`main_window.remove_selected()`、`build_context_menu()` / `_build_batch_menu()`；
  只移除佇列紀錄、不刪檔案、略過進行中任務，2 筆以上先確認
- 總進度（`queue_manager.progress().percent`）只計算完成 / 下載中 / 等待中；失敗與取消不計入（使用者要求）
- 發布 v2.0.0 後：`docs/RELEASE_NOTES.md` 補齊功能說明；README 全文校稿（語句、統一「您」「發布」、過時內容）
- **安裝程式（v2.1.0）**：`installer.iss`、`build_installer`、`verify_installer`；具名 mutex `YTMediaTool_AppMutex`；
  EXE 版本資源改由 `__init__.py` 自動產生；`tests/test_release_config.py` 檢查版本與名稱一致；
  `junit_annotations.py` 找不到結果檔時不再回報失敗

---

## 3. 關鍵決定與原因

| 決定 | 原因 |
|---|---|
| **yt-dlp 的 `paths.home` 設為任務專屬暫存資料夾**，成品經 ffprobe 驗證後才用 `move_no_overwrite` 移到下載資料夾 | 早期實測發現：yt-dlp 把下載資料夾中**使用者既有的同名中繼檔**當成「已下載」，轉 MP3 後**刪除了使用者的檔案**。現在 yt-dlp 完全不接觸下載資料夾。 |
| 暫存在 `<下載資料夾>\.ytmt_tmp\task_<id>_<亂數>\`，取消 / 失敗只刪自己的資料夾 | 同磁碟區移動為原子操作；不會誤刪其他任務或使用者檔案。 |
| 執行緒（非多程序）＋ `CancelToken`；Windows Job Object（`utils/win_job.py`） | yt-dlp hook 可即時中斷下載；程式結束時 Job Object 一併終止 ffmpeg / deno 子程序。代價：FFmpeg 轉檔中取消要等該步驟結束。 |
| 隨附 **Deno**（pip 套件 `deno==2.9.8`）＋ `yt-dlp-ejs` | yt-dlp 2025.11 起 YouTube 需要 JS 執行環境，缺少時格式不完整。Deno 93.5 MB 無法省。 |
| **cookies 功能**（設定 → YouTube 登入資訊，預設不使用） | 使用者實測遇到「Sign in to confirm you're not a bot」，yt-dlp 官方解法即提供使用者自己帳號的 cookies，屬正當驗證、非規避；經使用者同意後加入。cookies.txt 只用暫存副本（yt-dlp 會寫回檔案、並行會互相覆寫）。 |
| cookies 來源**移除 Chrome / Edge**（v2.1.1 之後；只剩不使用 / Firefox / cookies.txt），Chrome / Edge 改用 **cookies.txt**（擴充功能「Get cookies.txt LOCALLY」，無痕視窗匯出） | Chrome 127+ 的 app-bound encryption 讓 yt-dlp 在 Windows 上讀不到 cookies，使用者回報「選了也沒用」。舊設定的 chrome / edge 載入時自動改回「不使用」（`SettingsStore.load` 驗證）。cookies.txt 方式使用者實測成功。 |
| **FFmpeg 改用 BtbN win64-lgpl-shared 9.0.2**（使用者選擇） | CI 實測比較：需要的大小 gyan essentials 200.9 MB → lgpl-shared 約 144–167 MB，且改為 LGPL、不含 GPL 元件；MP3（libmp3lame）與 stream copy 皆具備。代價：BtbN 每日建置不保證長期保留。 |
| FFmpeg **不交給 PyInstaller**，在 spec 的 COLLECT 之後原樣複製到 `_internal/ffmpeg` | 以 datas 加入時 PyInstaller 分析 DLL 相依，在 `_internal` 最上層多放一份（+142 MB）。 |
| FFmpeg SHA256 一律**交叉驗證**後才寫入 manifest | 下載檔、GitHub release asset digest、建置者公布的 checksums 三者一致才採用。 |
| **安裝程式用 Inno Setup**，預設「只為目前使用者」安裝（可改所有使用者） | 不需系統管理員權限即可安裝與升級；資料本來就在 `%LOCALAPPDATA%`，與安裝位置無關。 |
| 安裝程式以 **AppMutex** 偵測執行中的程式；升級前清除舊 `_internal` | 避免覆蓋執行中的檔案；避免舊版已移除的 DLL 殘留。 |
| 解除安裝時**詢問**是否刪除 `%LOCALAPPDATA%\YT_Media_Tool`，靜默模式預設保留；下載資料夾永不碰 | 使用者資料由使用者決定；影片檔絕不能因解除安裝而遺失。 |
| 版本號以 `__init__.py` 為唯一來源，EXE 版本資源與安裝程式自動取用 | 原本 `version_info.txt` 寫死 2.0.0，升版時會不一致；改為範本並加測試檢查。 |
| Release 改用 **workflow_dispatch（使用者按 Run workflow）** | 本雲端環境推送 git tag 被代理 403 擋下；建立公開 Release 依規則需由使用者觸發。 |
| 新功能先發**預先發行版本**（tag 含 `-beta.N`），使用者實測後再發正式版 | 自動化測試無法連 YouTube；需使用者實機確認下載與安裝流程。 |
| Windows CI 的打包工作與 Release 完全相同（只差不發布） | 讓每次 push 都驗證完整發行路徑（含安裝程式），不必請使用者反覆按 Run workflow 試錯。 |
| one-folder（`_internal`）而非 one-file | 原始規格要求；啟動快、防毒誤判少。 |
| Apache-2.0 授權 | 使用者建立 repo 時選擇。 |

---

## 4. 下一步

- **待辦**：v2.2.0 CI 通過 → 使用者發布 `v2.2.0-beta.1` → 確認附件 → 使用者實測 → 發布正式版 `v2.2.0`。

以下為之後可能的方向（皆需使用者決定）：

- **多線程下載**（使用者詢問過，尚未決定）：
  - 已支援「同時下載多個影片」1–3 筆（原始規格上限 3）。
  - 選項 A：設定新增「單一影片分段同時下載數」（yt-dlp `concurrent_fragment_downloads`，建議 1–8、預設 4）；
    只對分段格式（直播錄影、HLS、部分 DASH）有加速效果，一般 YouTube 影片無差別。已用比喻向使用者說明，使用者尚未決定。
  - 選項 B：把同時下載數量上限從 3 提高（例如 5），需註明可能觸發 YouTube 機器人驗證。
  - 不建議外接 aria2c 多連線（需多附程式，且易被 YouTube 限速或要求驗證）。
  - 若要做，以 `v2.2.0` 發布（新功能）。
- 依 `docs/WINDOWS_INTEGRATION_TESTS.md` 完整跑一次實機清單。
- `actions/upload-artifact@v5` 的 Node.js 20 淘汰警告可評估升級。

### 發布新版本的流程（例如 v2.1.1 修正或 v2.2.0 新功能）

1. 修改程式並補測試；本機跑完整測試數次與 ruff（見第 6 節「流程習慣」）。
2. 同步更新版本號：`src/yt_media_tool/__init__.py`、`scripts/build_exe.bat` 的 `VERSION`、`pyproject.toml`
   （`tests/test_release_config.py` 會檢查三者一致；EXE 與安裝程式版本自動取 `__init__.py`）。
3. 視需要更新 `docs/RELEASE_NOTES.md`（Release 頁面內容來源）、README 與 `docs/WINDOWS_INTEGRATION_TESTS.md`。
4. 推送到 `main`，等該 commit 的 Windows CI 兩個工作（測試；打包 EXE 與安裝程式）都 success。
5. 請使用者到 Actions → Release → Run workflow，tag 填 `v2.2.0-beta.1`（測試版）；使用者實測無誤後再以 `v2.2.0` 發布正式版。
6. 用 API 確認 Release 的 4 個附件（zip、setup.exe 與兩個 `.sha256`）及雜湊內容（見第 7 節），並更新本文件。

---

## 5. 使用者偏好與背景

- 全程使用繁體中文回覆；說明技術選項時用淺白比喻（使用者曾問「A 是什麼意思？」）。
- 等待 CI 或發布時，使用者通常回覆「等 CI 通過再通知我」「發布完成再通知我」：請在背景監看，完成後主動回報結果。
- 使用者實測後會回覆「下載測試後再回報」/「下載測試後沒問題」。
- 公開發布（Run workflow）由使用者親自按；本環境無法推 tag 或建立 Release。
- 使用者為 **Claude Pro 方案**，已確認「Usage credits（額外用量）」為**關閉**，不會產生額外費用；
  儲存庫為公開，GitHub Actions 不收費。
- 所有 beta 版本保留，不刪除。

---

## 6. 不要碰的地方與已知的雷

### 檔案安全（最重要）
- **不要**把 yt-dlp 的 `paths.home` 或 `outtmpl` 改回下載資料夾，也不要開 `overwrites`——會重現「刪除使用者檔案」的嚴重問題（`tests/test_downloader.py::test_same_name_files_are_not_overwritten` 守著）。
- 取消 / 失敗只能刪 `temp_dir`（任務自己的暫存資料夾），不可刪 `.ytmt_tmp` 底下其他東西或下載資料夾內任何檔案。

### Windows 專屬的雷（CI 上踩過）
- **從 pwsh 呼叫 Windows PowerShell 5.1**：繼承的 `PSModulePath` 會讓 `Get-FileHash`、`Expand-Archive`、`Compress-Archive` 失效。腳本中一律用 .NET（`fetch_ffmpeg.ps1`）或 Python（`make_release_zip.py`）；`ci_run.ps1` 會清除 `PSModulePath`。
- **PowerShell 5.1 `Set-Content -Encoding UTF8` 會加 BOM**：讀 JSON 用 `utf-8-sig`；寫 JSON 用 `[IO.File]::WriteAllText(..., UTF8Encoding($false))`。
- `.ps1` 要 **UTF-8 with BOM + CRLF**；`.bat` 要 **CRLF**（中文訊息前有 `chcp 65001`）。用 Python 編輯這些檔時記得保留格式。
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
- spec 的 `_keep()` 會刪除非 `qtbase_zh_TW.qm` / `qt_zh_TW.qm` 的 Qt 翻譯與 `opengl32sw.dll`；若改用 Qt OpenGL / 其他語系需調整。
- 版本號在三處：`__init__.py`、`build_exe.bat` 的 `VERSION`、`pyproject.toml`（測試檢查一致）；
  `release.yml` 另檢查 tag 與版本一致（tag 可為 `vX.Y.Z` 或 `vX.Y.Z-後綴`）。
- `version_info.txt` 是範本，不要填入實際版本號。

### 本雲端環境的限制
- 使用者按 Run workflow 時曾把 tag 打成 `v2.0.0beta.5`（少了 `-`），會在「決定版本標籤」被擋下；請提醒格式 `vX.Y.Z` 或 `vX.Y.Z-beta.N`，
  且要從 workflow 頁面重新 Run，**不要 Re-run 失敗的那次**（會沿用錯誤的輸入與舊 commit）。
  v2.1.1 第一次 Run 時 tag 前多了空白（「 v2.1.1」）而失敗；`release.yml` 現在會先 `Trim()`，錯誤訊息也以「」標示 tag。
  使用者回報時常貼上舊的失敗 run 連結：先用 API 確認是否真的有新 run。
- **不能推送 git tag**（代理 403）；**不能建立 / 刪除 GitHub Release**（屬公開動作，需使用者觸發；推 `release/v*` 分支也被拒）。發布一律請使用者按 Run workflow。
- 連不到 YouTube（代理擋）；`gh` CLI 的 token 無效。GitHub 公開 API（未驗證）可讀 runs / jobs / annotations / releases，**讀不到完整日誌**——所以失敗原因要靠 `ci_run.ps1` / `junit_annotations.py` 轉成註解。
- `windows-ci.yml` 設有 `cancel-in-progress`：CI 跑到一半時再 push 會取消正在跑的那一輪；只改 `.md` / `docs/**` 不會觸發 CI。

### 流程習慣
- push 前跑完整測試數次再 commit（曾因指令串接錯誤在測試失敗時推送）：
  ```bash
  QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
  .venv/bin/ruff check src tests main.py scripts
  ```
- 不要叫使用者發布，直到該 commit 的 Windows CI 兩個工作都 success。

---

## 7. 常用指令（Linux 雲端環境）

```bash
# 開發環境（新環境需重建）
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# GUI 測試需要：apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 fonts-noto-cjk

# 最新 CI 狀態
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/runs?per_page=5"
# 某個 job 的註解（失敗原因、大小報告）
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/check-runs/<job_id>/annotations"
# Release 與附件 digest；最新正式版
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases"
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases/latest"
```
