# YT Media Tool V2.0 交接文件

> 更新時間：2026-10-30｜儲存庫：https://github.com/makodo123/YT_Media_Tool （分支 `main`）
> 使用者以**繁體中文**溝通，請全程使用繁體中文回覆。

---

## 1. 任務目標

從零建立 Windows 11 桌面程式 **YT Media Tool V2.0**（繁體中文、深色主題）：

- YouTube 單一 / 多網址批次下載；MP4（720p / 1080p / 最高）與 MP3（128 / 192 / 320 kbps）
- 下載佇列：即時進度、速度、ETA、單筆 / 全部取消、失敗重試、清除已完成、重開程式恢復未完成任務、並行 1–3 筆
- FFmpeg 合併與轉檔，SQLite 保存佇列 / 歷史 / 設定，PyInstaller one-folder EXE
- 技術：Python 3.12、PySide6、yt-dlp（Python API）、FFmpeg / FFprobe、SQLite、PyInstaller、pytest
- 限制：只下載有權利或獲授權的內容；**不得實作 DRM 或存取限制規避**；不得把使用者輸入拼成 shell 指令；
  資料寫在 `%LOCALAPPDATA%\YT_Media_Tool`，不可寫入程式目錄；同名檔案不可覆蓋。
- 原始需求規格的完整內容在第一次對話中，README.md 的「功能」表已涵蓋全部要求。

**目前階段**：功能完成、beta 測試中。使用者已實機測過 beta.2 / beta.3 下載成功（含 cookies）。
「縮小發行檔」已於 beta.4 完成；使用者回報的「無法批次刪除佇列」與「總進度條包含失敗任務」已於 **beta.5** 修正並發布，使用者已實測 beta.5 無誤，**正式版 `v2.0.0` 已發布**（https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.0.0 ，標示為 Latest）。

---

## 2. 目前完成的內容

### 發行狀態

| 版本 | commit | 狀態 |
|---|---|---|
| v2.0.0-beta.1 | 3a381b7 | 已發布（舊，建議使用者刪除） |
| v2.0.0-beta.2 | 66f0cf5 | 已發布（新增 cookies） |
| v2.0.0-beta.3 | 99fcf7d | 已發布，**使用者實測下載正常** |
| v2.0.0-beta.4 | 90af50e | 已發布（程式碼同 b122bf8）；縮小發行檔、FFmpeg 改 LGPL |
| v2.0.0-beta.5 | eb5d61d | 已發布；zip 144.1 MB，sha256 `033f37d6…ea87e7` 已核對；**使用者實測無誤** |
| **v2.0.0** | ab7e980 | **正式版已發布（Latest）**；程式碼同 eb5d61d（僅更新文件）；zip 144.1 MB，sha256 `15cdf062…c026ef` 已核對 |

beta.4 相對 beta.3：發行資料夾 412.4 MB → **333.4 MB**；FFmpeg 改 BtbN LGPL shared；確認對話框按鈕改中文。
beta.5 相對 beta.4：佇列可批次移除（「移除所選」按鈕、多選右鍵選單、Delete 鍵）；總進度不計入失敗與取消的任務。

### 專案結構（主要檔案）

```
main.py                         啟動檔（開發與 PyInstaller 共用）
requirements.txt / -dev.txt     全部固定版本（已確認皆有 win_amd64 / py3.12 wheel）
pyproject.toml                  套件資訊、pytest、ruff 設定（Apache-2.0）
src/yt_media_tool/
  app.py                        進入點：日誌、Job Object、單一執行個體鎖、Qt 中文翻譯、--smoke-test / --version
  app_context.py                組合 DB / 設定 / Downloader / QueueManager
  core/task_models.py           任務模型與狀態機（等待/下載中/轉檔中/完成/失敗/取消）
  core/url_parser.py            網址分類、正規化、去重、錯誤原因
  core/downloader.py            yt-dlp 下載引擎（見第 3 節的檔案安全設計）
  core/converter.py             FFmpeg / FFprobe / Deno 偵測、ffprobe 驗證、格式選擇字串
  core/cookies.py               YouTube cookies 設定 → yt-dlp 參數（cookies.txt 只用副本）
  core/queue_manager.py         佇列排程、取消、重試、保存與恢復（不依賴 Qt）
  core/errors.py                例外 → 中文說明（yt-dlp、FFmpeg、磁碟、權限、cookies）
  storage/database.py           SQLite（參數化 SQL、PRAGMA user_version migration，目前 v2）
  storage/settings.py           AppSettings（含 cookies_source / cookies_file）
  gui/main_window.py            主視窗
  gui/queue_table.py            表格 model、進度條與操作按鈕 delegate
  gui/settings_dialog.py        設定（含「YouTube 登入資訊（選用）」）
  gui/history_dialog.py / qt_bridge.py / workers.py / theme.py / i18n.py
  utils/paths.py                AppData、隨附檔位置、安全檔名、FileNameReserver
  utils/system_open.py / logging_utils.py / win_job.py
tests/                          180 個測試（單元、GUI、本機 HTTP 整合測試；不連線 YouTube）
scripts/
  setup_windows.bat / run_dev.bat / build_exe.bat   Windows 開發與打包
  fetch_ffmpeg.ps1              依 manifest 下載並驗證 FFmpeg 到 vendor/ffmpeg
  verify_dist.py                發行資料夾檢查 + 大小報告 + 用隨附 FFmpeg 實際轉 MP3 / MP4
  make_release_zip.py           壓縮 zip 並產生 .sha256
  ci_run.ps1                    CI 執行包裝：失敗時把最後 80 行輸出轉成 GitHub 註解
  junit_annotations.py          pytest 失敗 → GitHub 註解
  make_icon.py                  產生 assets/app.ico
packaging/
  yt_media_tool.spec            PyInstaller one-folder
  ffmpeg_manifest.json          FFmpeg 版本 / 網址 / SHA256（唯一來源）
  version_info.txt              EXE 版本資源
.github/workflows/
  windows-ci.yml                push main：Windows 測試 + 完整打包（與 Release 同流程）
  release.yml                   手動 Run workflow / 推 tag / 推 release/v* 分支 → 建立 GitHub Release
  ffmpeg-verify.yml             manifest 變更時交叉驗證 FFmpeg SHA256
  ffmpeg-candidates.yml         比較 FFmpeg 候選建置的大小與 MP3 支援（只在修改此檔時執行）
docs/WINDOWS_INTEGRATION_TESTS.md   Windows 實機測試清單（A–H 段）
docs/RELEASE_NOTES.md               Release 頁面說明（release.yml 會讀取）
THIRD_PARTY_NOTICES.md              第三方授權
```

### 本次對話後段的主要修改（依時間）

- 新增 Windows CI、Release workflow、FFmpeg 驗證流程；修正多個只在 Windows 才出現的問題
- cookies 功能（`core/cookies.py`、設定對話框、錯誤訊息）
- 修正：Windows 暫存資料夾「等待刪除」競爭（`downloader._make_task_dir` 重試）、「全部取消」競爭（先取消等待中再中斷執行中）
- 縮小：移除 `opengl32sw.dll` 與非中文 Qt 翻譯；FFmpeg 改 BtbN lgpl-shared；修正 FFmpeg DLL 重複打包
- 載入 Qt 繁中翻譯（`gui/i18n.py`），標準按鈕顯示「是 / 否 / 確定 / 取消」
- 批次移除：`main_window.remove_selected()`、`build_context_menu()` / `_build_batch_menu()`（多選右鍵選單），
  只移除佇列紀錄、不刪檔案、略過進行中任務，2 筆以上先確認
- 總進度（`queue_manager.progress().percent`）只計算完成 / 下載中 / 等待中；失敗與取消不計入（使用者要求）

---

## 3. 關鍵決定與原因

| 決定 | 原因 |
|---|---|
| **yt-dlp 的 `paths.home` 設為任務專屬暫存資料夾**，成品經 ffprobe 驗證後才用 `move_no_overwrite` 移到下載資料夾 | 早期實測發現：yt-dlp 把下載資料夾中**使用者既有的同名中繼檔**當成「已下載」，轉 MP3 後**刪除了使用者的檔案**。現在 yt-dlp 完全不接觸下載資料夾。 |
| 暫存在 `<下載資料夾>\.ytmt_tmp\task_<id>_<亂數>\`，取消 / 失敗只刪自己的資料夾 | 同磁碟區移動為原子操作；不會誤刪其他任務或使用者檔案。 |
| 執行緒（非多程序）＋ `CancelToken`；Windows Job Object（`utils/win_job.py`） | yt-dlp hook 可即時中斷下載；程式結束時 Job Object 一併終止 ffmpeg / deno 子程序。代價：FFmpeg 轉檔中取消要等該步驟結束。 |
| 隨附 **Deno**（pip 套件 `deno==2.9.8`）＋ `yt-dlp-ejs` | yt-dlp 2025.11 起 YouTube 需要 JS 執行環境，缺少時格式不完整。Deno 93.5 MB 無法省。 |
| **cookies 功能**（設定 → YouTube 登入資訊，預設不使用） | 使用者實測遇到「Sign in to confirm you're not a bot」，yt-dlp 官方解法即提供使用者自己帳號的 cookies，屬正當驗證、非規避；經使用者同意後加入。cookies.txt 只用暫存副本（yt-dlp 會寫回檔案、並行會互相覆寫）。 |
| Chrome / Edge 建議改用 **cookies.txt**（擴充功能「Get cookies.txt LOCALLY」，無痕視窗匯出） | Chrome 127+ 的 app-bound encryption 讓 yt-dlp 在 Windows 上通常讀不到 cookies。 |
| **FFmpeg 改用 BtbN win64-lgpl-shared 9.0.2**（使用者選 A） | CI 實測比較：需要的大小 gyan essentials 200.9 MB → lgpl-shared 約 144–167 MB，且改為 LGPL、不含 GPL 元件；MP3（libmp3lame）與 stream copy 皆具備。代價：BtbN 每日建置不保證長期保留。 |
| FFmpeg **不交給 PyInstaller**，在 spec 的 COLLECT 之後原樣複製到 `_internal/ffmpeg` | 以 datas 加入時 PyInstaller 分析 DLL 相依，在 `_internal` 最上層多放一份（+142 MB）。 |
| FFmpeg SHA256 一律**交叉驗證**後才寫入 manifest | 下載檔、GitHub release asset digest、建置者公布的 checksums 三者一致才採用。 |
| Release 改用 **workflow_dispatch（使用者按 Run workflow）** | 本雲端環境推送 git tag 被代理 403 擋下；建立公開 Release 依規則需由使用者觸發。 |
| 發布為**預先發行版本**（tag 含 `-beta.N`） | 自動化測試無法連 YouTube；正式版 `v2.0.0` 待使用者完整實測後再發。 |
| Windows CI 的打包工作與 Release 完全相同（只差不發布） | 讓每次 push 都驗證完整發行路徑，不必請使用者反覆按 Run workflow 試錯。 |
| one-folder（`_internal`）而非 one-file | 原始規格要求；啟動快、防毒誤判少。 |
| Apache-2.0 授權 | 使用者建立 repo 時選擇。 |

---

## 4. 下一步

1. ~~發布 beta.4、beta.5~~（已完成：https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.0.0-beta.5 ）
2. ~~請使用者實測 beta.5~~（已完成，無問題）：
   - 換 FFmpeg（beta.4 起）後的 MP4（含 1080p 合併）與 MP3（128/192/320）是否正常；確認對話框按鈕是否為中文
   - 批次移除（多選 → 「移除所選」/ 右鍵 / Delete）與總進度條（有失敗任務時不再虛高）
3. ~~發布正式版 `v2.0.0`~~（已完成）。之後的修正請以 `v2.0.1` 等版本號發布（需同步更新 `__init__.py` 與 `build_exe.bat` 的版本號）。
4. 可選：
   - 使用者可自行刪除舊的 beta.1（Releases 頁刪 Release，再到 Tags 頁刪 tag；本環境無權限刪除）。
   - 安裝程式（Inno Setup：Program Files、開始功能表、解除安裝）——先前提過，使用者尚未決定。
   - `actions/upload-artifact@v5` 仍有 Node.js 20 淘汰警告，可評估升級。
   - 小問題（未修）：Release 在測試之前就失敗時（例如標籤格式錯誤），「將失敗測試轉為註解」步驟也會因找不到
     `test-results.xml` 而顯示失敗；可讓 `scripts/junit_annotations.py` 在檔案不存在時直接結束，或在 workflow 加上
     `hashFiles('test-results.xml') != ''` 條件。只影響顯示，不影響發布。
   - 依 `docs/WINDOWS_INTEGRATION_TESTS.md` 完整跑實機清單。

---

## 5. 不要碰的地方與已知的雷

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

### 打包
- FFmpeg 檔案在 spec 的 **COLLECT 之後**手動複製，不要改回 `datas`（會重複打包約 140 MB）。`verify_dist.py` 會檢查。
- `packaging/ffmpeg_manifest.json` 的 `sha256` 只能填**交叉驗證過**的值；`fetch_ffmpeg.ps1` 在 sha256 為空時預設拒絕建置。
- **BtbN 的 autobuild release 可能被刪除**：若 fetch 404，用 `ffmpeg-candidates.yml`（修改該檔觸發）比較新版本，更新 manifest（url、checksum_url、sha256）後由 `ffmpeg-verify.yml` 驗證。
- spec 的 `_keep()` 會刪除非 `qtbase_zh_TW.qm` / `qt_zh_TW.qm` 的 Qt 翻譯與 `opengl32sw.dll`；若改用 Qt OpenGL / 其他語系需調整。
- 版本號在兩處：`src/yt_media_tool/__init__.py` 的 `__version__` 與 `scripts/build_exe.bat` 的 `VERSION`；`release.yml` 會檢查兩者與 tag 一致（tag 可為 `vX.Y.Z` 或 `vX.Y.Z-後綴`）。

### 本雲端環境的限制
- 使用者按 Run workflow 時曾把 tag 打成 `v2.0.0beta.5`（少了 `-`），會在「決定版本標籤」被擋下；請提醒格式 `vX.Y.Z` 或 `vX.Y.Z-beta.N`，
  且要從 workflow 頁面重新 Run，**不要 Re-run 失敗的那次**（會沿用錯誤的輸入）。
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

## 6. 常用指令（Linux 雲端環境）

```bash
# 開發環境（新環境需重建）
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# GUI 測試需要：apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 fonts-noto-cjk

# 最新 CI 狀態
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/runs?per_page=5"
# 某個 job 的註解（失敗原因、大小報告）
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/check-runs/<job_id>/annotations"
# Release 與附件 digest
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases"
```
