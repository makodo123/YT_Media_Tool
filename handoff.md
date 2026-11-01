# YT Media Tool 交接文件

> 更新時間：2026-11-01（v2.8.1-beta.2 開發完成：更新視窗；等待 Windows CI）｜儲存庫：https://github.com/makodo123/YT_Media_Tool （分支 `main`，最新 commit 見 `git log`）
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

使用者詢問「還能做什麼實用小工具」後，選了「本機檔案轉 MP3」與「產生播放清單檔」（v2.5.0），之後又選了「歌名自動整理」與「自動下載並安裝更新」（v2.6.0），再選了「整理舊檔案的歌名」（v2.7.0）。
v2.7.1 是修正版：第一次實機自動更新（v2.6.0 → v2.7.0）失敗，找出原因並修正。
之後第三次「實用小工具」建議中，使用者選了「播放清單同步」「已下載過提醒」「只下載片段」「選歌時先看整理後歌名」（v2.8.0）。

最近幾輪的工作方式：使用者要求「**以使用者角度檢查文字與功能（及是否可新增功能）**」→ 修正並發測試版 →
使用者實機測試回報 → 修正 → 使用者確認後發正式版。

---

## 2. 目前已經完成什麼、改了哪些檔

### 2.1 目前狀態

- **`v2.8.1-beta.1` 已發布（預先發行，61d1cca）**：GitHub API 額度用完時改用 Releases 網頁判斷最新版。
- **開發中 `v2.8.1-beta.2`（版本號仍為 2.8.1）**：使用者要求「按檢查更新要跳出視窗、有進度條，下載與安裝的成功或失敗都要顯示，不要讓使用者看 log」→ 新增更新視窗；等 Windows CI 通過後請使用者 Run `v2.8.1-beta.2`。
- **最新正式版 `v2.8.0`**（標示為 Latest）：2026-11-01 發布（a213573），4 個附件與 `.sha256` 已核對（安裝程式的 GitHub digest 與 `.sha256` 一致）。
  https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.8.0
- v2.8.0 的程式碼與使用者實測無誤的 `v2.8.0-beta.1`（b342233）相同，之後只改 handoff.md。
- v2.7.1（自動更新修正）的程式碼與 `v2.7.1-beta.1`（86fa6ac）相同；兩者皆實測無誤。
- **第一次實機自動更新（v2.6.0 → v2.7.0）失敗**：使用者回報「點選立即安裝並重新開啟後沒開啟且版本還是卡在 2.6.0」。
  原因與修正見 2.3 的 v2.7.1；Windows CI 新增的「程式內自動更新」端到端測試通過；`v2.7.1-beta.1` 與 `v2.7.1` 使用者手動安裝實測無誤。
  已安裝 v2.6.0 / v2.7.0 的使用者**必須手動安裝 v2.7.1 一次**（錯誤在舊版自己的程式碼裡，舊版無法自行更新成功）。
- v2.7.0 開發中使用者回報與修正：beta.1 → 安裝說明「%LOCALAPPDATA%」不白話、選「Mix - …」資料夾「沒反應」（實為檔案已整理好、資料夾名稱亂）→ beta.2 修正；beta.2 實測無誤。
- v2.6.0 開發中使用者回報與修正：beta.1 → YouTube「合輯」（`list=RD…`）讀不到「This playlist type is unviewable」（beta.2 修正）；
  beta.2 → MP4 沒有整理歌名、「[ 歌名 ] 5525版 Official Stage Video | 說明」與「周深《歌名》_ 描述」整理不對（beta.3 修正）；beta.3 實測無誤。
- **從 v2.6.0 起才有自動更新，但 v2.6.0 / v2.7.0 的自動更新會失敗**；v2.7.1 之後的下一個正式版才是第一次能實際驗證成功的自動更新（C27）。
- 使用者實測紀錄：v2.1.0（下載、cookies、MP4 / MP3、批次移除、總進度、安裝 / 升級 / 解除安裝）、v2.1.2、
  v2.2.0-beta.2、v2.2.0、v2.3.0-beta.1、v2.3.0、v2.4.0-beta.1、v2.4.0、v2.5.0-beta.2、v2.5.0、v2.6.0-beta.3、v2.6.0、v2.7.0-beta.2、v2.7.1-beta.1、v2.7.1、v2.8.0-beta.1 皆回報無誤。
- 測試：414 個通過＋1 個僅 Windows 執行（單元、GUI、以本機 HTTP 伺服器搭配真實 yt-dlp / FFmpeg 的整合測試；不連線 YouTube）。

### 2.2 發行紀錄（新 → 舊）

| 版本 | commit | 狀態 |
|---|---|---|
| v2.8.1-beta.2（開發中） | — | 更新視窗（檢查 / 下載進度 / 安裝 / 結果）、重新開啟後顯示更新成功或失敗原因；等 Windows CI 通過後請使用者 Run `v2.8.1-beta.2` |
| v2.8.1-beta.1 | 61d1cca | 預先發行；新版本檢查在 API 額度用完時改用 Releases 網頁；setup.exe 106.2 MB（`75558eee…e5926888`）、zip 144.2 MB（`2f31eb7b…09054216`），sha256 已核對；**等待使用者實測** |
| **v2.8.0** | a213573 | **正式版（Latest）**；程式碼同 v2.8.0-beta.1；setup.exe 106.2 MB（`b6dd5785…be405bcd`）、zip 144.2 MB（`8edc8280…fa84d1b`），sha256 已核對 |
| v2.8.0-beta.1 | b342233 | 預先發行；播放清單同步、已下載過提醒、只下載片段、選歌時的預計檔名；setup.exe 106.2 MB（`5edf5946…f354ffde`）、zip 144.2 MB（`e61115b3…ff818abb`），sha256 已核對；**使用者實測無誤** |
| v2.7.1 | 4f08730 | 正式版；程式碼同 v2.7.1-beta.1；setup.exe 106.2 MB（`375108b7…77e014fb`）、zip 144.2 MB（`47abe6f5…6bdbee75`），sha256 已核對；**使用者實測無誤** |
| v2.7.1-beta.1 | 86fa6ac | 預先發行；自動更新修正（Job Object 延伸旗標、安裝紀錄、失敗提示）；setup.exe 106.2 MB（`cd431120…62c8d0`）、zip 144.2 MB（`17746ef7…f842d8e`），sha256 已核對；Windows CI 程式內自動更新端到端測試通過；**使用者手動安裝實測無誤** |
| v2.7.0 | ce659f2 | 正式版（自動更新有錯，見 v2.7.1）；程式碼同 v2.7.0-beta.2；setup.exe 106.2 MB（`092d10a3…cec8f7e5`）、zip 144.2 MB（`19dd347d…6225140`），sha256 已核對 |
| v2.7.0-beta.2 | d7de925 | 預先發行；合輯資料夾整理、掃描摘要、安裝說明白話；setup.exe 106.2 MB（`1d14c24b…5ea7df0`）、zip 144.2 MB（`8fd0323a…02966ba`），sha256 已核對；**使用者實測無誤** |
| v2.7.0-beta.1 | 88a1fd5 | 預先發行；整理舊檔案的歌名；setup.exe 106.1 MB（`ecc6812c…ade9521`）、zip 144.2 MB（`e9f43a2e…1ac0a1d`），sha256 已核對；使用者回報合輯資料夾與說明文字 → beta.2 |
| v2.6.0 | 28cd087 | 正式版；程式碼同 v2.6.0-beta.3；setup.exe 106.1 MB（`49daabd5…bd6d6c`）、zip 144.2 MB（`d66c0857…66edb2fd`），sha256 已核對；**使用者實測無誤** |
| v2.6.0-beta.3 | 9fa5196 | 預先發行；MP4 也整理歌名（找得到演出者時）、「[ 歌名 ] 5525版」等寫法；setup.exe 106.2 MB（`14259764…df54019`）、zip 144.1 MB（`0c2c8141…eea46c0`），sha256 已核對；**使用者實測無誤** |
| v2.6.0-beta.2 | 5e71822 | 預先發行；合輯網址修正、歌名整理支援「歌手 [ 歌名 ]」與合唱；setup.exe 106.1 MB（`fe645706…5bf46c`）、zip 144.2 MB（`2a31a330…bd9b1d`），sha256 已核對；使用者回報 MP4 未整理 → beta.3 |
| v2.6.0-beta.1 | d67afc0 | 預先發行；歌名自動整理、自動下載並安裝更新；setup.exe 106.1 MB（`3ddc1a30…b63759`）、zip 144.2 MB（`7d9b6966…c925e59`），sha256 已核對；使用者回報合輯網址讀不到 → beta.2 |
| v2.5.0 | dba2aa7 | 正式版；程式碼同 v2.5.0-beta.2；setup.exe 106.1 MB（`cd2314ba…a4edc67`）、zip 144.1 MB（`665fd29c…2ca060`），sha256 已核對；**使用者實測無誤** |
| v2.5.0-beta.2 | e5ddb36 | 預先發行；標題顯示實際版本、檢查新版本的說明；setup.exe 106.1 MB（`c962ac44…4828edb`）、zip 144.2 MB（`c46e0958…01fd121`），sha256 已核對；**使用者實測無誤** |
| v2.5.0-beta.1 | b913ab3 | 預先發行；本機檔案轉 MP3、播放清單檔 .m3u8；setup.exe 106.1 MB（`3094a708…2caac9f`）、zip 144.2 MB（`46b3cc1a…6305d7a`），sha256 已核對；使用者回報標題版本不一致 → beta.2（第一次 Run 的 tag 打成 `v2.5.0beta.1` 被擋下，第二次成功） |
| v2.4.0 | 48ac341 | 正式版；程式碼同 v2.4.0-beta.1；setup.exe 106.1 MB（`d27cbbe2…a876f1`）、zip 144.1 MB（`3608f00b…1181f3`），sha256 已核對；**使用者實測無誤** |
| v2.4.0-beta.1 | 18c3d1d | 預先發行；字幕、速度上限、自動帶入剪貼簿網址、新版本提醒、第三次檢查的修正；setup.exe 106.1 MB（`4fb3537b…7c3498`）、zip 144.1 MB（`f034d07d…c89ad`），sha256 已核對；**使用者實測無誤** |
| v2.3.0 | 3450eb4 | 正式版；程式碼同 v2.3.0-beta.1；setup.exe 106.1 MB（`6e2446e3…4595c6d`）、zip 144.1 MB（`49f6f0cd…167a5f`），sha256 已核對；**使用者實測無誤** |
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

**v2.8.1-beta.2**（使用者：「按下檢查更新應該跳出一個視窗說正在檢查更新，如果有進度條更好，下載和安裝更新也是一樣，成功或失敗都要顯示出來，不要讓使用者去看 log」）

| 項目 | 修改的檔案與重點 |
|---|---|
| 更新視窗 | 新檔 `gui/update_dialog.py`：`UpdateDialog`（非強制回應）＋ `UpdateView(state, message, progress)`；狀態 CHECKING / LATEST / CHECK_FAILED / PORTABLE / AVAILABLE / DOWNLOADING / DOWNLOAD_FAILED / READY / INSTALLING / UPDATED / INSTALL_FAILED，各有標題（成功「✓」綠、失敗「✕」紅）、說明、進度條（檢查與安裝為跑動的不定進度、下載為百分比）與按鈕；按鈕以 `actionRequested` 通知主視窗（retry_check / download / cancel / install / page / copy）。視窗只負責顯示 |
| 主視窗 | `gui/main_window.py`：`check_for_updates(manual=True)` 立即開啟視窗；`update_view()` 依目前狀態產生畫面（`_install_view` 優先，其次檢查中、檢查失敗、已是最新、免安裝版、可安裝、下載中、下載失敗、可下載）；`_refresh_update_dialog()` 在檢查結果、下載進度、下載完成時更新；`_on_update_action()`。手動檢查的結果不再用 QMessageBox。取消下載時工作執行緒送出 `UpdateCancelledError`，回到「可下載」。橫幅「下載並安裝 / 重試」與新的「顯示進度」連結會開啟視窗。`install_update()` 確認後顯示 INSTALLING 再啟動安裝程式；啟動失敗顯示 INSTALL_FAILED。`check_previous_update()` 重新開啟後 300 ms 開啟視窗：成功顯示 UPDATED；失敗顯示 INSTALL_FAILED（原因由 `updates.summarize_install_log()` 整理），橫幅「查看原因」重新開啟視窗；「複製詳細資訊」把原因與記錄最後 30 行複製到剪貼簿（取代舊的「開啟安裝記錄檔位置」） |
| 記錄檔整理 | `core/updates.py` `summarize_install_log()`：去掉時間戳；找不到記錄 → 安裝程式沒有執行（防毒 / 被刪除）；有「Installation process succeeded」但版本沒變 → 可能裝到其他資料夾；「Message box」/「Exception message:」後一行 → 「安裝程式顯示：…」；其他 → 被中斷或舊程式沒在時間內關閉 |
| 測試與文件 | `tests/test_gui.py`（檢查中的視窗與不定進度條、結果、失敗與重試、自動檢查失敗不開視窗、下載進度 42%、取消下載、下載失敗、重新開啟後成功 / 失敗原因與複製、安裝程式啟動失敗）、`tests/test_updates.py`（記錄檔整理）；README、WINDOWS_INTEGRATION_TESTS（C27b） |

**v2.8.1**（使用者測試自動更新時，日誌兩次出現 `HTTP Error 403: rate limit exceeded`，選擇「額度用完就改用網頁」）

| 項目 | 修改的檔案與重點 |
|---|---|
| 備用的版本查詢 | `core/updates.py`：`fetch_latest_release()` 先呼叫 `_fetch_from_api()`；任何 `OSError` / `ValueError`（含 403 / 429 額度用完）→ `_fetch_from_page()`：開啟 `RELEASES_PAGE`（`https://github.com/<repo>/releases/latest`），以轉址後的 `geturl()` 比對 `_TAG_URL`（只接受本儲存庫的 `/releases/tag/vX.Y.Z`，測試版與其他網址回傳 None），`setup_digest=None`；下載時只以 `.sha256` 驗證（`download_update` 原本就支援 digest 為 None）。兩者都失敗時拋出 `UpdateCheckError`（`RATE_LIMIT_MESSAGE` 或 `OFFLINE_MESSAGE`） |
| 白話訊息 | `gui/main_window.py` `_on_update_failed()`：手動檢查失敗時顯示 `UpdateCheckError` 的訊息 |
| 測試與文件 | `tests/test_updates.py`（額度用完改用網頁、網頁方式仍驗證 .sha256、異常轉址、兩者都失敗的訊息）、`tests/test_gui.py`；README、WINDOWS_INTEGRATION_TESTS（C27a）。已在雲端以真實 GitHub 確認網頁方式取得 2.8.0 |

**v2.8.0**（使用者從第三次「實用小工具」建議中選了四項）

| 項目 | 修改的檔案與重點 |
|---|---|
| 資料庫 v3 | `storage/database.py` MIGRATIONS 新增版本 3：`download_tasks` 加 `file_name`、`clip_start`、`clip_end`；`download_history` 加 `is_clip`；新增 `completed_downloads()`（已完成、非片段、新 → 舊）。`core/task_models.py`：`DownloadTask.file_name / clip_start / clip_end`、`is_clip`、`clip_text`；新函式 `parse_clock()`（「90」「1:30」「1:02:30」「1:30.5」、全形冒號）、`format_clock()`、`clip_text()`。`core/queue_manager.py` `TaskSpec` 同步新增三個欄位 |
| 只下載片段 | `core/downloader.py`：`clip_range()`（依影片長度檢查：開始超過長度 → 錯誤；結束超過長度 → 到結尾）、`clip_file_suffix()`（檔名加「（片段 1.20-4.35）」，Windows 檔名不能有「:」）；`_run_download(..., clip)` 設 `download_ranges`（`yt_dlp.utils.download_range_func`）且 `force_keyframes_at_cuts=False`；片段不下載字幕；實際品質附「；片段 …」。`gui/main_window.py`：網址列下方「只下載片段：開始～結束」、`clip_range()`、`_reset_clip()`（加入後自動取消勾選）；只允許一部影片（含 `watch?v=…&list=…` 時只下載該影片、不展開清單）。`gui/queue_table.py` 品質欄附「｜片段 …」；詳細資訊顯示片段 |
| 已下載過提醒 | 新檔 `core/download_index.py`：`video_key()`（同一影片的各種網址視為相同）、`DownloadedIndex`（同影片同格式取最新且檔案仍存在的紀錄）。`gui/main_window.py` `_finish_add(..., check_downloaded, confirmed)` → `_confirm_already_downloaded()` → `ask_already_downloaded()`（「略過已下載的」/「仍要下載」/「取消」；測試以 monkeypatch 取代 `ask_already_downloaded`）。從歷史紀錄重新下載、片段、選歌視窗勾選的影片不詢問 |
| 播放清單同步 | `gui/playlist_dialog.py` 重寫：`PlaylistGroup.names / downloaded`，欄位「影片名稱｜預計檔名｜長度｜已下載」；已下載的預設不勾選（從清單中某支影片加入時仍只勾選該影片）、「只選未下載的」按鈕、搜尋也比對預計檔名。`gui/main_window.py` `_on_playlists_expanded` 填入 names / downloaded；`_add_playlist_batch()` 把同資料夾已下載的歌以 `known_files` 帶入。`core/playlist_files.py` `add_batch(..., known_files)`：同資料夾＋清單名稱＋格式已有批次時沿用（同一個 .m3u8），`_same_folder` 改名為公開的 `same_folder` |
| 選歌時的預計檔名 | `core/downloader.py` `PlaylistEntry.channel`（extract_playlist 讀 channel / uploader）；`MainWindow.planned_name()`（與下載時相同的 `clean_title` 規則：MP3 用頻道補演出者、MP4 不補；設定關閉時原標題）。對話框點兩下只能編輯「預計檔名」欄（`itemDoubleClicked` → `editItem`）；`custom_names()` 只回傳勾選且改過的；`choose_playlist_entries()` 仍回傳 `list[list[str]]`，修改的檔名放在 `self._custom_names`。下載時 `task.file_name` 優先：檔名直接採用，「演出者 - 歌名」拆成歌曲資訊 |
| 測試與文件 | `tests/test_gui.py`（片段、已下載提醒三種回答、格式不同 / 檔案刪除 / 片段不算、重新下載不問、同步、m3u 包含舊歌、預計檔名、對話框）、`tests/test_download_index.py`（新）、`tests/test_database.py`（v2 → v3 migration）、`tests/test_task_models.py`、`tests/test_downloader.py`、`tests/test_playlist_files.py`、`tests/integration/test_local_pipeline.py`（真實 yt-dlp / FFmpeg 片段 MP3 / MP4、指定檔名寫入歌曲資訊）；README（功能表、專案架構補齊）、RELEASE_NOTES、WINDOWS_INTEGRATION_TESTS（C30–C33） |

**v2.7.1**（修正：使用者回報 v2.6.0 → v2.7.0 的「立即安裝並重新開啟」後程式沒有重新開啟、版本仍是 2.6.0）

| 項目 | 修改的檔案與重點 |
|---|---|
| 根本原因 | 程式啟動時把自己放進設有 `KILL_ON_JOB_CLOSE` 的 Windows Job Object（關閉程式時一併結束 ffmpeg）。舊的 `allow_children_to_outlive()` 用 **JobObjectBasicLimitInformation（class 2）** 想取消它，但 `KILL_ON_JOB_CLOSE` / `BREAKAWAY_OK` 是「延伸」旗標，class 2 **不會清除**；安裝程式又繼承了 Job，所以程式一關閉，剛啟動的安裝程式就被系統一起終止。舊的 CI 測試（`verify_self_update`）是由 CI 直接執行安裝程式，沒有經過程式的 Job，所以沒抓到 |
| Job Object 修正 | `utils/win_job.py` 重寫：`_kernel32()` 定義 `JOBOBJECT_EXTENDED_LIMIT_INFORMATION`，`_set_job_flags()` 一律用 class 9；`kill_children_on_exit()` 設 `KILL_ON_JOB_CLOSE`；`allow_children_to_outlive()` 改設 `BREAKAWAY_OK`（不含 KILL）；`CloseHandle` 補 argtypes（64 位元 handle 才不會被截斷，mutex 才真的釋放） |
| 啟動安裝程式 | `core/updates.py` `launch_installer()`：加 `CREATE_BREAKAWAY_FROM_JOB`（失敗時退回不加）、`/LOG=<資料資料夾>\updates\install.log`，回傳紀錄檔路徑；新增 `install_log_path()` |
| 失敗時讓使用者知道 | `storage/settings.py` 新增 `pending_update_version`；`gui/main_window.py` `install_update()` 啟動前記下目標版本，`check_previous_update()`（`__init__` 最後呼叫）在下次開啟時比對：版本仍舊 → 視窗上方顯示「上次自動更新到 X 沒有完成」＋「下載安裝程式」「查看安裝紀錄」；成功 → 狀態列「已更新到 X」 |
| CI 端到端驗證 | `app.py` 新增隱藏參數 `--install-update <setup.exe>`（只供 CI，經過與按鈕相同的 Job / mutex / `launch_installer()` 路徑）；`scripts/verify_installer.py` 新增 `verify_update_from_app()`：由已安裝的程式啟動安裝程式後立即結束，檢查 `install.log` 出現「Installation process succeeded」且程式被重新開啟 |
| 測試與文件 | `tests/test_updates.py`（breakaway 與退回、紀錄檔）、`tests/test_gui.py`（失敗 / 成功的下次開啟提示）；版本號 2.7.1；RELEASE_NOTES「已知限制」、WINDOWS_INTEGRATION_TESTS C27 |

**v2.7.0**（使用者從「實用小工具」建議中選了「整理舊檔案的歌名」；beta.2 依實測修正）

| 項目 | 修改的檔案與重點 |
|---|---|
| beta.2 修正：合輯資料夾與訊息 | `core/title_cleanup.py` 新增 `clean_playlist_title()`：「Mix - <完整標題>」→「合輯 - 演出者 - 歌名」（使用者自己的清單名稱不改）；`gui/main_window.py` `_playlist_folder()` 新下載即用整理後的資料夾名稱。`core/batch_rename.py`：`RenamePlan` / `RenameResult` 新增 `is_dir`，`scan()` 也列出合輯資料夾（含所選資料夾本身）、`media_files()`；`apply()` 先改檔案、再由深到淺改資料夾；`undo()` 反序。`utils/paths.py` 新增 `replace_path_prefix()`；`storage/database.py` `rename_folder()`、`core/queue_manager.py` `rename_folder()`、`core/playlist_files.py` `rename_folder()`；`gui/main_window.py` `_on_folder_renamed()`（也更新「儲存至」與設定的下載資料夾）。`gui/rename_dialog.py`：資料夾列以 📁 標示、摘要顯示「掃描了 N 個 MP3 / MP4：可以整理…；另有 K 個已經整理好」、所選資料夾被改名時欄位跟著更新、復原時依相反順序同步。`packaging/installer_notice.txt`：資料位置改為白話說明 |
| 整理舊檔案的歌名 | 新檔 `core/batch_rename.py`：`proposed_stem()`（以 `clean_title({"title": 檔名, "channel": ""})` 整理，保留「 (1)」重複編號）、`scan()`（只看 .mp3 / .mp4，略過以 `.` 開頭的檔案與資料夾如 `.ytmt_tmp`）、`apply()`（`sanitize_filename` 後以 `move_no_overwrite` 改名，已存在加「 (1)」，只差大小寫時略過；同名字幕 `影片.srt`、`影片.<語言>.srt` 一併改；最後更新同資料夾 `.m3u8` 的檔名行與 `#EXTINF` 標題）、`undo()`（原檔名已被使用時略過並回報）。新檔 `gui/rename_dialog.py`：資料夾、包含子資料夾、掃描、預覽表格（勾選、點兩下修改新檔名）、全選 / 全不選、改名（先確認）、復原上次改名。`storage/database.py` `rename_output_path()`（佇列與歷史，路徑比對不分大小寫）、`core/queue_manager.py` `rename_output_path()`（記憶體中的任務＋發出 TASK_UPDATED）、`core/playlist_files.py` `rename_file()`；`gui/main_window.py`：「工具 → 整理舊檔案的歌名…」、`open_rename_dialog()`、`on_files_renamed()`。`gui/theme.py`：`QTableView::indicator` 也加外框 |
| 測試與文件 | `tests/test_batch_rename.py`（新）、`tests/test_gui.py`（改名後佇列 / 歷史 / 播放仍正確、使用者修改檔名、播放清單紀錄跟著改名）；README、RELEASE_NOTES、WINDOWS_INTEGRATION_TESTS（C29） |

**v2.6.0**（使用者選了「歌名自動整理」與「自動下載並安裝更新」；beta.2、beta.3 依實測修正）

| 項目 | 修改的檔案與重點 |
|---|---|
| beta.3 修正：MP4 也整理、更多標題寫法 | `core/title_cleanup.py`：`clean_title(info, channel_fallback)`，MP4 傳 `False`——只在 YouTube 歌曲資訊或標題中找得到演出者時整理，否則回傳 None（vlog 等維持原標題）；歌名括號（含中文的 `[ ]`）改由 `_from_title_bracket()` 處理：演出者取括號**前**的文字（括號在最前面時取括號後到第一個分隔符），括號後緊接的「…版」（`_VERSION_MARK`，例如 5525版、5525+2版）接在歌名後，其餘（Official Stage Video、`|` 說明、`_` 描述）丟棄；`_plausible_artist()`：不含句子標點（含 ：＋）、每位中文演出者不超過 8 字；「Official Stage / Performance Video」視為雜訊。`core/downloader.py`：MP4 也套用。使用者截圖的 3 個標題已加入測試 |
| beta.2 修正：YouTube「合輯」讀不到 | `core/url_parser.py` 新增 `ParsedUrl.playlist_source_url`：清單 ID 以 `RD` 開頭（YouTube 自動產生的合輯）時改用播放頁面網址 `watch?v=…&list=RD…`（`playlist?list=RD<影片ID>` 也從 ID 推回影片），yt-dlp 會從播放頁面讀取合輯；一般清單仍用 `playlist?list=`。`gui/main_window.py` `_expand_playlists` 改用它。`core/errors.py`：「unviewable」錯誤改為中文說明 |
| beta.2 修正：相信音樂等的標題寫法 | `core/title_cleanup.py`：`[ ]` 內含中文時視為歌名（「歌手 [ 歌名 ]」）；合唱以 ╳ × ＆ 連接時每位演出者分別去掉英文（`_drop_translations`）；中英文之間沒有空格（「MAYDAY五月天」）也能拆（頻道名稱不拆，避免「SMG音乐」變「音乐」）；「Official Live Video」「纯享」視為雜訊；✦★♪ 等裝飾符號去掉；括號外是一句話（含，。！？或超過 40 字）時不當演出者。使用者合輯的 8 個標題已加入 `tests/test_title_cleanup.py` |
| 歌名自動整理（beta.1 只有 MP3；beta.3 起 MP4 也套用，見上） | 新檔 `core/title_cleanup.py`：`clean_title(info)` 優先用 YouTube 的 `track`＋`artists`；否則移除含雜訊字（Official、MV、Lyrics、動態歌詞、4K…）的括號與前後雜訊字，`【】《》「」『』` 內的文字視為歌名、括號外為演出者，否則以「 - 」「｜」拆成演出者與歌名（頻道名出現在哪邊，哪邊就是演出者），沒有演出者時用 `clean_channel()`（去掉 - Topic、VEVO、官方頻道…）；中文後的英文翻譯（以大寫開頭）去掉，但 Remix / Live / Acoustic 等版本字保留；`( )`、`[ ]` 中非雜訊的內容保留在歌名後。`core/downloader.py`：MP3 且 `DownloadPreferences.clean_titles` 時設定 `info["track"]`、`info["artist"]`、`info["artists"]`（供 FFmpegMetadata），檔名用 `演出者 - 歌名`；`DownloadResult.title` 仍為原標題。設定 `clean_titles`（預設開） |
| 自動下載並安裝更新 | `core/updates.py`：`fetch_latest_release()`（版本＋安裝程式在 API 的 `digest`）、`LatestRelease`（下載網址由固定的 `DOWNLOAD_BASE`＋tag 組成）、`download_update()`（先取 `.sha256`，與 API digest 不一致即停止；下載到 `.part` 邊算 SHA256，相符才改名；已下載且驗證過則沿用；清除舊檔；可取消；大小上限 1 GB）、`is_installed_build()`（frozen 且有 `unins000.exe`）、`launch_installer()`（`win_job.allow_children_to_outlive()`＋`release_app_mutex()` 後以 `/SILENT /SUPPRESSMSGBOXES /NORESTART /WAITPID=<pid> /RESTARTAPP=1` 啟動）；`_request()` 只允許 GitHub 的 https 網址。`gui/main_window.py`：`_on_update_checked` 接 `LatestRelease`、`start_update_download()`（背景執行緒＋`_UpdateSignals`）、`show_update_banner()`（下載中 / 已下載 / 失敗重試 / 安裝版 / 免安裝版五種狀態）、`install_update()`（確認、轉檔中拒絕、`_closing_for_update` 略過關閉時的下載詢問）。`utils/win_job.py`：`allow_children_to_outlive()`、`release_app_mutex()`。`packaging/installer.iss`：`InitializeSetup` 依 `/WAITPID` 用 OpenProcess＋WaitForSingleObject 等待（最多 60 秒）、`[Run]` 依 `/RESTARTAPP=1` 以 `runasoriginaluser` 重新開啟。設定 `auto_download_updates`（預設開）。下載位置 `%LOCALAPPDATA%\YT_Media_Tool\updates` |
| 測試與文件 | `tests/test_title_cleanup.py`（新，26 種標題）、`tests/test_updates.py`（下載驗證、檢查碼不符、不完整、取消、網址限制、安裝版判斷）、`tests/test_gui.py`（橫幅各狀態、安裝流程）、`tests/integration/test_local_pipeline.py`（整理後的檔名與 MP3 標籤）；`scripts/verify_installer.py` 新增 `verify_self_update()`：CI 實測覆蓋安裝會等待執行中的程序、完成後重新開啟程式；README、RELEASE_NOTES、WINDOWS_INTEGRATION_TESTS（C26–C28） |

**v2.5.0**（使用者從「實用小工具」建議中選了 2 項；beta.2 修正標題版本）

| 項目 | 修改的檔案與重點 |
|---|---|
| beta.2 修正：標題版本不一致 | `__init__.py`：`APP_DISPLAY_NAME = f"{APP_NAME} v{__version__}"`（原本寫死「YT Media Tool V2.0」，視窗與所有對話框標題都顯示 V2.0）；「關於」改顯示 `APP_NAME`＋版本；`packaging/version_info.txt` 檔案描述、README / THIRD_PARTY_NOTICES / main.py / setup_windows.bat 的「V2.0」移除；`--version` 輸出改為「YT Media Tool v2.5.0」 |
| beta.2 修正：檢查新版本的說明 | `gui/main_window.py` `_on_update_checked`：已是最新時說明「目前已是最新的正式版」，測試版不會自動提醒 |
| 本機檔案轉 MP3 | 新檔 `core/local_convert.py`：`convert_to_mp3()` 先 FFprobe 確認有音訊 → FFmpeg（參數清單、`-progress pipe:1` 回報進度、可取消）寫到輸出資料夾的隱藏暫存檔 `.ytmt_convert_<亂數>.mp3` → `verify_output` → `FileNameReserver`＋`move_no_overwrite` 改成 `原檔名.mp3`（已存在加「 (1)」）；失敗 / 取消只刪自己的暫存檔；`ConvertError` 為中文原因。新檔 `gui/convert_dialog.py`：非強制回應視窗、加入 / 拖曳檔案、音質、存到「原資料夾」或指定資料夾、逐檔進度與結果、雙擊在檔案總管中顯示、關閉時詢問取消。`gui/main_window.py`：「工具 → 本機檔案轉 MP3…」、`open_converter()`；把本機影音檔拖到主視窗即開啟轉檔視窗（網址仍放進輸入框）；主視窗關閉時若轉檔中先詢問 |
| 播放清單檔（.m3u8） | 新檔 `core/playlist_files.py`：`PlaylistFileStore` 把每個播放清單批次（資料夾、清單名稱、格式、影片順序、已完成檔名、清單檔名）存在 `application_settings` 的 `playlist_files.batches`（最多 50 筆）；任務完成時重寫清單檔（UTF-8、相對路徑、依清單順序、只列存在的檔案；暫存檔＋`os.replace`）；第一次建立時同名檔存在改用「 (1)」。`gui/main_window.py`：`_on_playlists_expanded` 登記批次（2 部以上）、`_on_task_finished` 更新（例外只記錄）。設定 `playlist_m3u`（預設開） |
| 測試與文件 | `tests/integration/test_local_convert.py`（新，真實 FFmpeg：轉檔、不覆蓋、沒有聲音 / 非影音檔、取消）、`tests/test_playlist_files.py`（新）、`tests/test_gui.py`（轉檔視窗、拖曳本機檔、播放清單下載後產生 .m3u8）；README、RELEASE_NOTES、WINDOWS_INTEGRATION_TESTS（C22–C25） |

**v2.4.0**（使用者第三次「使用者角度檢查」：修正 4 個問題＋使用者選定的 4 項新功能）

| 項目 | 修改的檔案與重點 |
|---|---|
| 修正：等待中任務「開啟位置」跳錯誤 | `gui/main_window.py` `_reveal()`：播放清單子資料夾在開始下載前還不存在 → 開啟最近的上層資料夾 |
| 修正：播放清單 / 歷史紀錄加入的任務先顯示網址 | `gui/main_window.py` `_finish_add(titles=...)`（`TaskSpec.title`）；`redownload(..., title)`；`gui/history_dialog.py` 回呼多傳影片名稱；`PASTED_VIDEO_TITLE` 佔位名稱不當成標題 |
| 修正：選擇視窗不知道會存到哪 | `gui/playlist_dialog.py` `destination` 參數；`choose_playlist_entries(groups, output_dir)` |
| 整理：設定對話框 | `gui/settings_dialog.py` 分成「下載」「其他功能」「FFmpeg（通常不需更改）」「YouTube 登入資訊」群組；「預設儲存資料夾」改為「下載資料夾」；內容放進 `QScrollArea`，`_fit_to_screen()` 最高為螢幕 90% |
| 修正：品質欄截斷「320 kbps → 128 kbp…」 | `gui/queue_table.py` 品質欄寬 150 → 185 |
| 新功能：下載速度上限 | `storage/settings.py` `rate_limit_mbps`（0＝不限制，上限 100）、`download_preferences()` 把合計上限平均分給 `max_concurrent`；`core/downloader.py` `DownloadPreferences.rate_limit` → yt-dlp `ratelimit`；設定對話框 `QDoubleSpinBox` |
| 新功能：下載字幕（MP4） | `core/downloader.py` `choose_subtitle()`（上傳者字幕依 繁中→中文→簡中→英文，其次任何語言，最後才用自動產生字幕）、`_download_subtitle()`（影片完成後另跑一次 `skip_download` 的 yt-dlp，`FFmpegSubtitlesConvertor` 轉 srt；失敗只加附註）、`_move_subtitle()`（`影片名.srt`，已存在改 `影片名.<語言>.srt`，不覆蓋）；`actual_quality` 結尾附「；字幕：繁體中文」等；主視窗「下載字幕」勾選框（只在 MP4 顯示，存於設定 `download_subtitles`） |
| 新功能：自動帶入剪貼簿網址 | `gui/main_window.py` `auto_paste_clipboard()`（`applicationStateChanged` 變為 Active 時）、`_on_clipboard_changed()`（程式在前景時複製的內容記為已處理）；略過輸入框或佇列中已有的網址；設定 `auto_paste_clipboard`（預設開） |
| 新功能：新版本提醒 | 新檔 `core/updates.py`（`fetch_latest_version()` 讀 GitHub `releases/latest` 的 `tag_name`、`is_newer()`；下載頁用固定網址 `RELEASES_PAGE`）；`gui/main_window.py` `check_for_updates()`（背景 `BackgroundJob`）、`update_banner`（「前往下載頁面 / 略過這個版本」）、選單「說明 → 檢查新版本…」；`app.py` 啟動 3 秒後檢查（不在 smoke test）；設定 `check_updates`、`skipped_update_version`；`gui/theme.py` `QLabel#infoLabel` |
| 重構 | `Downloader(metadata_provider=...)` 改為 `preferences_provider` → `DownloadPreferences(embed_metadata, rate_limit, subtitles)`，每個任務開始時讀取一次；`app_context.py` 對應修改 |
| 測試與文件 | `tests/test_updates.py`（新）、`tests/test_downloader.py`、`tests/test_gui.py`、`tests/integration/test_local_pipeline.py`（字幕成功 / 失敗 / 沒有字幕三種情況，以真實 yt-dlp＋FFmpeg）；README、RELEASE_NOTES、WINDOWS_INTEGRATION_TESTS（C18–C21） |

**v2.3.0**（使用者第二次「使用者角度檢查」後選定的 4 項新功能＋歷史紀錄改善）

| 功能 | 修改的檔案與重點 |
|---|---|
| 歌名、演出者與封面 | `core/converter.py`：`postprocessors(..., embed_metadata)` 加入 `FFmpegThumbnailsConvertor`（jpg、before_dl）、`FFmpegMetadata`、`EmbedThumbnail`；`core/downloader.py`：`metadata_provider`（v2.4.0 起併入 `preferences_provider`）、`writethumbnail`、`POSTPROCESSOR_STAGES` 新增「寫入歌曲資訊中」「嵌入封面中」、`SILENT_POSTPROCESSORS`；`app_context.py` 接上設定；`storage/settings.py` 新增 `embed_metadata`（預設開）；`gui/settings_dialog.py` 勾選框 |
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
  app.py                        進入點：日誌、Job Object、具名 mutex、單一執行個體鎖、Qt 中文翻譯、--smoke-test / --version、
                                --install-update <setup.exe>（隱藏參數，只供 CI 驗證程式內自動更新）
  app_context.py                組合 DB / 設定 / Downloader（cookies_provider、preferences_provider）/ QueueManager
  core/task_models.py           任務模型與狀態機（等待中 / 下載中 / 轉檔中 / 已完成 / 失敗 / 已取消）
  core/url_parser.py            網址分類、正規化、去重、錯誤原因
  core/downloader.py            yt-dlp 下載引擎（暫存隔離、取消、驗證、不覆蓋移動、播放清單讀取、字幕、DownloadPreferences）
  core/converter.py             FFmpeg / FFprobe / Deno 偵測、ffprobe 驗證、格式選擇、後處理（含歌名與封面）
  core/updates.py               新版本檢查、下載與驗證安裝程式、啟動安裝（自動更新；脫離 Job、安裝紀錄 updates\install.log）
  core/title_cleanup.py         歌名自動整理（演出者 - 歌名）
  core/batch_rename.py          舊檔案批次改名（字幕、.m3u8 同步；不覆蓋；可復原）
  core/download_index.py        已下載過的影片（依歷史紀錄；已下載過提醒、播放清單同步）
  core/local_convert.py         本機影音檔轉 MP3（暫存檔→驗證→不覆蓋移動、進度、取消）
  core/playlist_files.py        播放清單檔（.m3u8）批次記錄與產生
  core/cookies.py               YouTube cookies 設定 → yt-dlp 參數（cookies.txt 只用副本）
  core/queue_manager.py         佇列排程、取消、重試、保存與恢復（不依賴 Qt）
  core/errors.py                例外 → 中文說明（yt-dlp、FFmpeg、cookies、磁碟、權限）
  storage/database.py           SQLite（參數化 SQL、PRAGMA user_version migration，目前 v3）
  storage/settings.py           AppSettings（cookies、embed_metadata、playlist_subfolder、notify_on_complete、rate_limit_mbps、
                                download_subtitles、auto_paste_clipboard、check_updates、auto_download_updates、skipped_update_version、
                                pending_update_version、playlist_m3u、clean_titles 等）
  gui/main_window.py            主視窗（加入佇列、播放清單、拖曳、剪貼簿帶入、字幕勾選、雙擊播放、批次操作、完成通知、新版本提醒）
  gui/playlist_dialog.py        播放清單選擇對話框（勾選、預計檔名可修改、已下載標示與「只選未下載的」）
  gui/history_dialog.py         下載歷史（搜尋、在檔案總管中顯示、重新下載）
  gui/rename_dialog.py          整理舊檔案的歌名（預覽、改名、復原）
  gui/convert_dialog.py         本機檔案轉 MP3 視窗
  gui/queue_table.py            表格 model、品質 / 狀態文字、進度條與操作按鈕 delegate
  gui/settings_dialog.py        設定（含「YouTube 登入資訊（選用）」）
  gui/qt_bridge.py / workers.py / theme.py / i18n.py
  utils/paths.py                AppData、隨附檔位置、安全檔名、FileNameReserver
  utils/win_job.py              Job Object（延伸限制資訊 class 9；結束時終止子程序；自動更新前改為允許脫離）、具名 mutex（供安裝程式偵測；自動更新前釋放）
  utils/system_open.py          開啟資料夾、在檔案總管中選取檔案、以預設播放器開啟 MP3 / MP4
  utils/logging_utils.py
tests/                          單元、GUI（pytest-qt）、integration/（本機 HTTP＋真實 yt-dlp / FFmpeg）、fakes.py
scripts/
  setup_windows.bat / run_dev.bat / build_exe.bat   Windows 開發與打包
  build_installer.py / .bat     以 Inno Setup 建立 setup.exe 與 .sha256
  verify_installer.py           CI 中實際靜默安裝、啟動、轉檔、自動更新（/WAITPID、/RESTARTAPP；並經由已安裝程式的
                                --install-update 端到端驗證）、解除安裝並檢查捷徑與登錄
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
docs/WINDOWS_INTEGRATION_TESTS.md   Windows 實機測試清單（A–I 段；C12–C17、E6a 為 v2.3.0，C18–C21 為 v2.4.0，C22–C25 為 v2.5.0，C26–C28 為 v2.6.0，C29 為 v2.7.0，C30–C33 為 v2.8.0 新功能；C27 註明 v2.7.1 起才能自動更新成功）
docs/RELEASE_NOTES.md               Release 頁面說明（release.yml 會讀取）
THIRD_PARTY_NOTICES.md              第三方授權
```

---

## 3. 剛剛做的關鍵決定，以及為什麼這樣決定

### 3.1 最近幾輪（v2.1.3～v2.8.0）的決定

| 決定 | 原因 |
|---|---|
| 手動檢查、下載、安裝都在**同一個更新視窗**顯示每一步與結果；自動檢查（啟動時）仍只用橫幅，不跳視窗 | 使用者要求看得到進度與成功 / 失敗；啟動時自動檢查若每次跳視窗會打擾。安裝本身由 Inno Setup 的進度視窗顯示（`/SILENT`），程式已關閉無法顯示，所以重新開啟後再告訴使用者結果。 |
| 失敗原因從安裝記錄檔整理成白話，並提供「複製詳細資訊」 | 使用者不該去找 log；需要回報時一鍵複製即可。 |
| API 額度用完時改用 Releases 網頁的轉址判斷最新版（不讀網頁內容），驗證只靠 `.sha256` | 未登入的 GitHub API 每個網路每小時 60 次，家用 / 行動網路常多人共用同一個對外位址；網頁轉址沒有這個限制。少了 API 的第二份檢查碼，但 `.sha256` 與安裝程式都來自同一個 GitHub Release、走 https，仍能擋下下載不完整或被竄改的檔案。 |
| 片段用 yt-dlp 的 `download_ranges`（只抓需要的部分），不重新編碼（`force_keyframes_at_cuts=False`） | 從兩小時的演唱會截一首歌時不必下載整部影片；重新編碼影片很慢。代價是 MP4 開頭可能提早 1～2 秒（從前一個關鍵畫面開始），已寫在提示中；MP3 不受影響。 |
| 片段**一次只用於一部影片**，加入後自動取消勾選 | 多部影片很少需要同一段時間；忘記取消勾選會讓之後的下載都被截短。 |
| 片段檔名加「（片段 開始-結束）」、歷史紀錄標記 `is_clip` | 避免與完整版同名；片段不能算「已下載過整部影片」。 |
| 「已下載過」只看**同格式且檔案還在**的紀錄 | 使用者刪掉檔案或要另一種格式時，再下載是合理的，不該打擾。 |
| 選歌視窗勾選的影片不再跳「已下載過」詢問 | 選歌視窗已標示「✓ 已下載」並預設不勾選；使用者刻意勾選代表要再下載。 |
| 播放清單同步沿用**同一個 .m3u8**（同資料夾＋清單名稱＋格式），並把資料夾中已下載的歌一起列入 | 只下載新歌時若另建清單檔，會出現只有新歌的「清單 (1).m3u8」，音樂播放器裡清單就不完整。 |
| 預計檔名只在**使用者修改過**時才指定檔名；沒改的仍在下載時以完整資訊整理 | 選歌視窗只有標題與頻道，下載時有 YouTube 歌曲資訊（影片中的音樂）更準確。 |
| 資料庫升到 v3（新增欄位，舊資料預設空白） | 片段與指定檔名必須跟著任務保存，重新開啟程式、重試都不會遺失。 |
| 自動更新的安裝程式**脫離 Job Object**（`BREAKAWAY_OK` ＋ `CREATE_BREAKAWAY_FROM_JOB`），而不是乾脆不用 Job | Job 仍需要：關閉程式時一併結束 ffmpeg，避免殘留程式鎖住檔案。只有自動更新那一刻放行安裝程式。 |
| 新增 `--install-update` 隱藏參數讓 CI **經過程式本身**啟動安裝程式 | v2.6.0 的錯誤只在「由程式啟動、程式隨即結束」時出現；CI 直接執行安裝程式測不到。 |
| 寫安裝紀錄檔＋下次開啟比對版本 | 安裝程式是靜默執行，失敗時使用者什麼都看不到；至少要告訴使用者沒更新成功、給手動下載與紀錄檔。 |
| 不嘗試讓 v2.6.0 / v2.7.0「自己」更新成功 | 錯誤在舊版已安裝的程式碼裡，新版無法改變舊版的行為；只能請使用者手動安裝一次。 |
| 整理舊檔案**只改檔名、不改檔案內容**（不重寫 MP3 標籤） | 重寫標籤需要 FFmpeg 重新封裝整個檔案，風險與時間都較高；改名可完整復原。舊檔名本身沒有頻道資訊，所以不用頻道名稱補演出者。 |
| 改名時**同步字幕、.m3u8、佇列、歷史與播放清單紀錄** | 否則字幕不再自動載入、清單找不到歌、「雙擊播放」「在檔案總管中顯示」會說檔案不存在。 |
| 合輯資料夾名稱**下載時就整理**，且整理工具也能改**合輯資料夾**（只限「Mix - …」，使用者自己命名的資料夾不動） | 使用者實測發現最亂的是資料夾名稱（YouTube 合輯標題含第一首的完整標題）；一般資料夾名稱是使用者自己取的，不應自動改。 |
| 改資料夾時**先改檔案、再由深到淺改資料夾**，復原與同步紀錄都**依相反順序** | 檔案的新舊路徑都以改名當下的資料夾為準；順序錯了，佇列與歷史紀錄會對不上路徑。 |
| 掃描結果一定說明**掃描了幾個檔案、幾個已整理好** | 使用者實測時看到「沒有需要整理的檔案」以為沒反應；其實是檔案已在下載時整理好。 |
| 改名一定**先預覽、使用者確認**，並提供**復原** | 規則不可能每次都對；使用者可取消勾選或直接修改新檔名。 |
| YouTube「合輯」（`list=RD…`）改從**播放頁面網址**讀取（v2.6.0-beta.2） | 合輯沒有獨立的清單頁面，用 `playlist?list=` 會得到「unviewable」；yt-dlp 對 `watch?v=…&list=…` 會從播放頁面讀出合輯，一般清單則轉到清單頁面（查 yt-dlp `_extract_from_playlist` 原始碼確認）。只對 `RD` 開頭的清單改，降低影響範圍。 |
| 含中文的 `[ ]` 視為歌名括號；歌名括號後的「…版」**保留為版本**（v2.6.0-beta.2／beta.3） | 使用者常下載的相信音樂（五月天等）寫法是「歌手 [ 歌名 ] 5525版 Official Stage Video」；同一首歌有多個版本（5525版、5525+2版），保留才分得出來。英文標題的 `[Acoustic]`、`[Remastered]` 不含中文，仍接在歌名後。 |
| 演出者需「像名稱」才採用（不含句子標點、每位中文演出者不超過 8 字） | 中國節目頻道的標題常是「周深《歌名》_ 某人盛赞：…」或「光良联手陈卓璇对唱《勇气》，…」，括號外是描述句；寧可只留歌名。 |
| 自動更新**只在安裝版**自動下載與安裝，免安裝版導向下載頁 | 免安裝版沒有安裝程式可執行，也不能保證有權限覆寫資料夾；安裝版由 Inno Setup 處理升級（清除舊 `_internal`、捷徑、登錄）最可靠。 |
| 安裝程式需**同時符合** GitHub API 的 `digest` 與 Release 的 `.sha256` | 兩個來源互相核對，下載不完整或被竄改時不會執行；網址由程式固定組成，不採用 API 回傳的連結。 |
| 安裝**一定先詢問**，不在背景自動安裝 | 安裝要關閉程式，會中斷下載與轉檔；由使用者決定時機（轉檔進行中直接拒絕）。 |
| 安裝程式用 **`/WAITPID` 等舊程式結束**，程式先**取消 Job Object 的子程序終止並釋放 mutex** | 程式的 Job Object 會在結束時終止所有子程序（包括安裝程式）；安裝程式偵測到 mutex 會停止；舊程式未結束時覆蓋會遇到檔案使用中。三者都處理後才能「關閉 → 安裝 → 重開」。 |
| 歌名整理：MP3 一律整理；**MP4 只在標題中找得到演出者時整理**（beta.3 起）；佇列與歷史仍顯示原標題 | 使用者下載的音樂 MP4 也希望整理（beta.2 實測）；但 MP4 常是 vlog、教學，用頻道名稱補演出者會很奇怪，所以 MP4 只做有把握的整理。保留原標題讓使用者能對照。 |
| 歌名整理**優先用 YouTube 提供的歌曲資訊**，規則整理不出合理結果時保留原標題 | YouTube 的「影片中的音樂」資訊最準確；標題寫法五花八門，寧可不整理也不要整理錯。 |
| 標題**不再寫死「V2.0」**，`APP_DISPLAY_NAME` 由 `__version__` 產生 | 使用者發現標題「V2.0」與實際版本 2.4.0 不一致；原始規格的名稱「YT Media Tool V2.0」只是產品名，改為顯示實際版本以免誤會。安裝程式與捷徑使用 `APP_NAME`（不含版本），升級不受影響。 |
| 新版本提醒**不提醒測試版**（維持） | 測試版給使用者自己試用；一般使用者只該收到正式版提醒。訊息已說明此事。 |
| 播放清單檔用 **`.m3u8`（UTF-8）**，不用 `.m3u` | 使用者要求的是 .m3u 清單檔；.m3u 在許多播放器以系統編碼讀取，中文歌名會變亂碼，.m3u8 是同一種格式的 UTF-8 版本。 |
| 清單檔**每完成一首就重寫**，批次資訊存在資料庫 | 下載完成順序不固定、可能失敗後重試、程式可能中途關閉；每次依原清單順序重寫，只列出存在的檔案，最後一定完整。 |
| 只有從播放清單加入 **2 部以上**才產生清單檔 | 只下載一首時清單檔沒有意義。 |
| 本機轉檔先寫**隱藏暫存檔、驗證後才改名**，與下載相同的不覆蓋規則 | 沿用檔案安全設計：原檔絕不修改，轉一半失敗或取消不會留下殘缺的 .mp3，也不會蓋掉同名檔。 |
| 本機轉檔放在**獨立的非強制回應視窗**，不進下載佇列 | 轉檔與下載是不同的工作（沒有網址、速度、重試）；獨立視窗可邊轉檔邊操作主視窗。 |
| 本機轉檔的檔案類型以 FFprobe 判斷「有沒有聲音」，副檔名清單只用於篩選 | 副檔名不可靠；沒有聲音的影片會給清楚的原因，而不是 FFmpeg 錯誤訊息。 |
| **字幕另外跑一次 yt-dlp（`skip_download`），不與影片一起下載** | yt-dlp 下載字幕失敗時，除非開 `ignoreerrors` 否則會讓整個下載失敗；開 `ignoreerrors` 又會吞掉真正的下載錯誤。分開處理後字幕只是附加項目，失敗只在詳細資訊加附註。 |
| 字幕**只下載一種語言**，自己依偏好選，不用 yt-dlp 的 `subtitleslangs` 清單 | `subtitleslangs` 會下載清單中所有符合的語言；YouTube 自動翻譯字幕幾乎涵蓋所有語言，會產生一堆檔案。上傳者提供的字幕優先於自動產生字幕（品質較好）。 |
| 字幕存成 `影片名.srt`（不嵌入 MP4） | 依使用者選項的說明；同名 .srt 播放器會自動載入，也方便另外編輯。 |
| 「下載字幕」是**全域設定**（主視窗勾選框），不是每個任務各自記錄 | 每個任務記錄需要資料庫 migration；全域設定在任務開始時讀取，對尚未開始的任務也生效，提示文字已說明。 |
| 速度上限是**全部任務合計**，平均分給同時下載數 | yt-dlp 的 `ratelimit` 以單一下載計算；使用者在意的是整體網路佔用。變更後對下一個開始的任務生效。 |
| 自動帶入剪貼簿**只放進輸入框，不自動加入佇列** | 避免誤下載；使用者仍要按「加入佇列」。程式自己複製的網址（右鍵「複製網址」）不帶入，同一份剪貼簿只帶入一次。 |
| 新版本提醒用**固定的下載頁網址**、只讀 `tag_name`，自動檢查失敗不顯示錯誤 | 不信任 API 回傳的連結；只取得版本號、不傳送個人資料；離線時不打擾使用者。只比較正式版（`releases/latest` 不含預先發行）。 |
| 設定對話框加**捲動區域**並限制高度 | 群組化後內容變高，在小螢幕或 125% 縮放時「儲存」按鈕可能超出螢幕。 |
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
| 使用者**未選**的項目不做（詳見第 4 節） | 2026-10-31 兩次提出選項，使用者都只勾選了部分項目；未經同意不實作。 |

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

- **待辦 1**：v2.8.1-beta.2 已推送，等 Windows CI 通過 → 請使用者 Run `v2.8.1-beta.2` → 實測（C27a、C27b）→ 正式版 v2.8.1。
- **待辦 2：自動更新實測（C27）**：使用者正在測「v2.7.1 自動更新到 v2.8.0」。
  - 使用者曾把 v2.7.1 直接裝在 v2.8.0-beta.1 上，v2.7.1 開啟時出現「資料庫版本 3 比程式支援的版本 2 新」（預期中的降版保護）。
  - 已教使用者的測法：關閉程式 → 把 `%LOCALAPPDATA%\YT_Media_Tool\yt_media_tool.sqlite3`（含 `-wal`、`-shm`）移到備份資料夾 →
    開 v2.7.1（像全新安裝）→ 自動更新到 v2.8.0 → 測完關閉程式、刪掉新產生的資料庫、把備份搬回來。
  - 測試時兩次遇到 GitHub API `403 rate limit exceeded`（v2.7.1 沒有備用查詢方式），已建議等一小時或改用手機熱點。結果待使用者回報。
  - 若失敗：v2.7.1 / v2.8.0 會在橫幅提供「開啟安裝記錄檔位置」；v2.8.1-beta.2 起重新開啟後直接顯示原因，請使用者按「複製詳細資訊」貼過來。
  - **不要建議使用者在正常資料下改裝回舊版**：資料庫已是 v3，v2.7.1 以前的版本打不開。

之後可能的方向（**皆需使用者決定，未經同意不要做**）：

- 提出過但使用者未選的項目（2026-10-31～11-01）：
  - 多次未選：記住上次在主視窗選的格式與品質。
  - 第二次檢查（v2.3.0）未選：同時下載上限從 3 提高到 5。
  - 第三次檢查（v2.4.0）未選：自訂檔名格式（例如「演出者 - 標題」）。
  - 「實用小工具」建議中仍未選：依章節分割成多首、音量平衡、全部下載完成後自動睡眠 / 關機、另存影片縮圖。
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
- 安裝精靈的說明（`installer_notice.txt`）給一般使用者看：不要出現 `%LOCALAPPDATA%` 等環境變數，改用白話路徑。
- **任何改檔名的功能都要呼叫 `MainWindow.on_files_renamed()`**（或同等的 `queue.rename_output_path` 與 `PlaylistFileStore.rename_file`），否則佇列、歷史與播放清單紀錄會指向不存在的檔案。
- 有勾選框的表格 / 清單一定要有 `::indicator` 樣式（`gui/theme.py` 已涵蓋 QCheckBox、QTreeView、QTableView），否則深色主題下未勾選的框看不到。
- **YouTube「合輯」（`list=RD…`）不能用 `playlist?list=` 讀取**；讀取清單一律用 `ParsedUrl.playlist_source_url`。
- **資料庫 schema 已是 v3**：新增欄位只能在 `MIGRATIONS` 附加新版本，不可修改既有版本；舊版程式（v2.7.1 以前）開啟 v3 資料庫會顯示「資料庫版本比程式支援的版本新」（降版時會遇到）。
- `_TASK_COLUMNS` 與 `_task_values()`、`TaskSpec`、`QueueManager.add_tasks()` 要一起改，否則新欄位不會被保存。
- **片段的整合測試需要「索引在開頭」的 MP4**（`clip.mp4` 以 `-movflags +faststart` 產生）：測試用的本機 HTTP 伺服器不支援 Range，FFmpeg 跳到中間讀取會失敗（YouTube 支援 Range，實際使用沒問題）。不要改回用 `sample.mp4` 測片段。
- 片段的檔名後綴與 `actual_quality` 附註以 `clip_range()` 的實際範圍為準（結束超過影片長度時為「結尾」）。
- `MainWindow.ask_already_downloaded()` 是自訂按鈕的 QMessageBox（`exec()`），測試的 `Dialogs` 攔截不到；**測試一律 monkeypatch `ask_already_downloaded`**，否則會卡住。
- `PlaylistPickerDialog` 欄位順序改為「影片名稱｜預計檔名｜長度｜已下載」（`COL_*` 常數），長度在第 2 欄；預計檔名欄只能用 `itemDoubleClicked` 編輯（`NoEditTriggers`）。
- **Job Object 的 `KILL_ON_JOB_CLOSE`、`BREAKAWAY_OK` 是延伸旗標，一律用 `JobObjectExtendedLimitInformation`（class 9）設定**；
  用 Basic（class 2）不會報錯但旗標不會改，v2.6.0 的自動更新就是這樣失敗的。`win_job._set_job_flags()` 不要改回 Basic。
- 自動更新的驗證**必須經過程式本身**（`--install-update` → `verify_update_from_app()`）；只直接執行安裝程式的測試抓不到 Job 問題。
- **自動更新**：不要讓 `launch_installer()` 之外的地方啟動安裝程式；啟動前一定要 `allow_children_to_outlive()` 與 `release_app_mutex()`，
  否則安裝程式會被 Job Object 終止或停在「程式執行中」。`installer.iss` 的 `/WAITPID`、`/RESTARTAPP` 參數名稱與 `updates.launch_installer()` 必須一致，
  只能靠 Windows CI 的 `verify_self_update()`（直接執行安裝程式）與 `verify_update_from_app()`（經由程式本身）驗證。`[Run]` 重新開啟程式那一行不可加 `skipifsilent`（自動更新是靜默安裝）。
- 更新視窗的按鈕與狀態集中在 `gui/update_dialog.py` 的 `_BUTTONS` / `_TITLES`；新增狀態時兩個表都要加，`MainWindow.update_view()` 也要能產生該狀態。測試以 `dialog.state`、`dialog.button_widgets` 檢查。
- 新版本檢查的備用方式依賴 GitHub 的轉址網址格式（`/releases/latest` → `/releases/tag/vX.Y.Z`）；若 GitHub 改版導致比對失敗，`_fetch_from_page()` 會回傳 None（視為沒有新版），不會出錯。
- `updates._request()` 只允許 `https://api.github.com/` 與 `https://github.com/`；不要改成使用 API 回傳的 `browser_download_url`。
- 歌名整理的規則改動後務必跑 `tests/test_title_cleanup.py`；新增案例優先加在那裡。`DownloadResult.title` 必須保持原標題（佇列、歷史、播放清單比對都用它）。
- **不要再在任何地方寫死版本號或「V2.0」**；顯示用名稱一律用 `APP_DISPLAY_NAME`（含版本）或 `APP_NAME`（不含版本）。`installer.iss` 的 `AppName` 不可加版本號（會影響升級辨識與捷徑名稱）。
- 本機轉檔 `convert_to_mp3()`：**不可**讓 FFmpeg 直接寫到正式檔名或使用 `-y`；一律暫存檔 → 驗證 → `move_no_overwrite`。
  取消時由監看執行緒 `kill` FFmpeg，`finally` 刪除暫存檔。
- `PlaylistFileStore` 的 `os.replace` 只能用在本程式記錄的清單檔名（batch 的 `m3u`）；第一次建立一定先找未使用的檔名。
- 測試的 `db` fixture 把資料庫放在 `tmp_path`，檢查資料夾內容的測試要另建子資料夾。
- **測試中的主視窗已關閉自動帶入剪貼簿**（`window` fixture 設 `auto_paste_clipboard = False`）；否則剪貼簿內容會跨測試影響輸入框。
- **新版本檢查只能在 `app.py` 觸發**，不要放進 `MainWindow.__init__`（測試與 smoke test 會連網）。
- 字幕步驟 `_download_subtitle()` 必須維持「任何例外都只回傳附註」；`actual_quality` 結尾的「；字幕：…」附註不可放在開頭（`quality_text()` 從開頭比對「Np」）。
- `Downloader` 的偏好設定一律透過 `DownloadPreferences`，在 `download()` 開頭讀一次；不要在下載途中重新讀取。
- `MainWindow.choose_playlist_entries(groups, output_dir)` 回傳 **`list[list[str]]`（依清單分組）或 `None`（取消）**；測試以 monkeypatch 取代它（`lambda groups, *_:`），改簽名或回傳格式要一起改測試。
- 完成通知依賴 `_idle_timer` 延後判斷；**不要改成在 `_on_task_finished` 當下判斷**（會拆成多則通知，`test_notify_once_when_whole_queue_finishes` 守著）。
- 深色主題下 Fusion 的勾選框未勾選時與背景同色，**看不到**；`gui/theme.py` 的 `::indicator` 樣式不要刪。新增有勾選框的元件（例如 QListView）也要套用。
- `converter.probe_media()` 判斷影像串流時會略過 `attached_pic`（封面）；改這段會讓有封面的 MP3 被誤判為有影像、或 MP4 驗證錯誤。
- 狀態欄文字直接顯示 `task.stage`（例如「準備中」「取得影片資訊中」），測試中的 FakeDownloader 只會停在「準備中」。
- `PlaylistEntry` 的 `video_id` 用來判斷預先勾選；`extract_playlist()` 要持續填入。
- **新增一個設定要改四個地方**：`AppSettings` 欄位（含預設值）、`AppSettings.validated()`（型別與範圍）、
  `SettingsDialog` 的元件與 `result_settings()`；主視窗上的快速開關（例如「下載字幕」）以 `apply_settings` 存回。漏改 `validated()` 時壞掉的設定值會讓程式出錯。

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
- tag 格式常出錯：曾打成 `v2.0.0beta.5`、`v2.5.0beta.1`（少 `-`，發測試版時最常見）、「 v2.1.1」（前面有空白，`release.yml` 現已 `Trim()`）。請提醒格式 `vX.Y.Z` 或 `vX.Y.Z-beta.N`，
  且要從 workflow 頁面重新 Run，**不要 Re-run 失敗的那次**（會沿用錯誤的輸入與舊 commit）。使用者回報時常貼上舊的 run 連結：先用 API 確認是否真的有新 run。
- 背景監看 Release 時，**不要只看「監看開始後才建立」的 run**：使用者常在 CI 通過的同時就按下 Run workflow（v2.4.0-beta.1 的監看因此漏掉）。
  改用「run id 大於上一次 Release run 的 id」判斷，成功或失敗都回報（v2.4.0 正式版即以此方式監看，附錄 B 有範例）。
- 用 `pkill -f <腳本名>` 停止監看時，會連同執行 pkill 的那個 shell 一起結束（指令列含同樣字串）；改用 `TaskStop` 或記下 PID。
- 使用者回覆「沒問題」有時只是「好的」，有時是「實測無誤」：**先用 API 查是否真的有新的 Release run**，再依情況回覆。
- **不能推送 git tag**（代理 403）；**不能建立 / 刪除 GitHub Release**（屬公開動作，需使用者觸發；推 `release/v*` 分支也被拒）。發布一律請使用者按 Run workflow。
- 連不到 YouTube（代理擋）；`gh` CLI 的 token 無效。GitHub 公開 API（未驗證）可讀 runs / jobs / annotations / releases；job 日誌（`/actions/jobs/<job_id>/logs`）2026-11-01 測試可下載，但不保證一直可用——失敗原因仍以 `ci_run.ps1` / `junit_annotations.py` 轉成註解為主。
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
- 每次發布後要更新 handoff.md，且須包含本文件的五大項；使用者也會直接要求「更新 handoff.md」，此時要通讀全文修正過時描述。
- 使用者下載的多為**華語音樂**（五月天、周深等，常見頻道「相信音樂BinMusic」），MP3 與 MP4 都會下載；
  歌名整理的新規則請以使用者回報的實際標題為測試案例（`tests/test_title_cleanup.py`）。
- 回報問題時**常只貼截圖、不附文字**：先從截圖判斷問題（例如檔名沒整理、錯誤訊息），再說明原因與修正。
- 回報問題時常是**一句話描述現象**（例如「點選立即安裝並重新開啟後沒開啟且版本還是卡在 2.6.0」）：先找根本原因，並說明舊版是否需要手動處理。
- 會問版本相關的問題（例如「從幾版開始可以自動更新」）：回答時說明版本界線與條件（安裝版 / 免安裝版、正式版 / 測試版）。

## 附錄 B：常用指令（Linux 雲端環境）

```bash
# 開發環境（新環境需重建）
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# GUI 測試需要：
apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 fonts-noto-cjk

# 最新 CI 狀態；某個 run 的工作與步驟
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/runs?per_page=5"
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/runs/<run_id>/jobs"
# 某個 job 的註解（失敗原因、大小報告）；job 完整日誌（例如確認 verify_installer 的 [OK] 項目）
curl -sSL "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/jobs/<job_id>/logs" -o /tmp/joblog.txt
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/check-runs/<job_id>/annotations"
# Release 與附件 digest；最新正式版；.sha256 內容
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases"
curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/releases/latest"
curl -sSL "https://github.com/makodo123/YT_Media_Tool/releases/download/<tag>/YT_Media_Tool-<版本>-win64.zip.sha256"

# 背景監看：等待比上一次 Release run（AFTER_ID）更新的那一次完成（用 Bash run_in_background 執行）
AFTER_ID=<上一次 Release run 的 id>
until curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/workflows/release.yml/runs?per_page=3" \
  | python3 -c "import sys,json; r=[x for x in json.load(sys.stdin)['workflow_runs'] if x['id']>$AFTER_ID]; \
print(r[0]['id'], r[0]['conclusion']) if r and r[0]['status']=='completed' else sys.exit(1)"; do sleep 60; done
```
