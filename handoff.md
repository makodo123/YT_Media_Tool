# YT Media Tool 交接文件

> 更新時間：2026-11-01（v2.6.0 開發中）｜儲存庫：https://github.com/makodo123/YT_Media_Tool （分支 `main`，最新 commit 見 `git log`）
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

使用者詢問「還能做什麼實用小工具」後，選了「本機檔案轉 MP3」與「產生播放清單檔」（v2.5.0），之後又選了「歌名自動整理」與「自動下載並安裝更新」（v2.6.0）。

最近幾輪的工作方式：使用者要求「**以使用者角度檢查文字與功能（及是否可新增功能）**」→ 修正並發測試版 →
使用者實機測試回報 → 修正 → 使用者確認後發正式版。

---

## 2. 目前已經完成什麼、改了哪些檔

### 2.1 目前狀態

- **最新正式版 `v2.5.0`**（標示為 Latest）：2026-11-01 發布，4 個附件與 `.sha256` 已核對；**使用者實測下載無誤**。
  https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.5.0
- v2.5.0 的程式碼與使用者實測無誤的 `v2.5.0-beta.2`（e5ddb36）相同，之後只改 handoff.md。
- **進行中：v2.6.0**（歌名自動整理、自動下載並安裝更新）。`v2.6.0-beta.1` 已發布（預先發行）：
  https://github.com/makodo123/YT_Media_Tool/releases/tag/v2.6.0-beta.1 ；等使用者實測，無誤再以 tag `v2.6.0` 發布正式版。
  已確認實際 Release 的安裝程式有 GitHub `digest`，且與 `.sha256` 一致（自動更新的雙重檢查可用）。
- 使用者實測 beta.1 回報（2026-11-01）：YouTube「合輯」（Mix，`list=RD…`）網址讀取失敗「This playlist type is unviewable」。
  修正已推送到 `main`（版本號仍 2.6.0），Windows CI 通過（8744a12，run 41266889745），已請使用者發布 `v2.6.0-beta.2`。
- v2.5.0 開發中使用者回報（beta.1 實測時）：標題「YT Media Tool V2.0」與版本不一致 → beta.2 改由 `__version__` 產生；
  2.4.0 檢查不到 2.5.0 → 因當時只有測試版（設計如此），已改寫訊息說明。
- 使用者實測紀錄：v2.1.0（下載、cookies、MP4 / MP3、批次移除、總進度、安裝 / 升級 / 解除安裝）、v2.1.2、
  v2.2.0-beta.2、v2.2.0、v2.3.0-beta.1、v2.3.0、v2.4.0-beta.1、v2.4.0、v2.5.0-beta.2、v2.5.0 皆回報無誤。
- 測試：304 個通過＋1 個僅 Windows 執行（單元、GUI、以本機 HTTP 伺服器搭配真實 yt-dlp / FFmpeg 的整合測試；不連線 YouTube）。

### 2.2 發行紀錄（新 → 舊）

| 版本 | commit | 狀態 |
|---|---|---|
| v2.6.0-beta.1 | d67afc0 | 預先發行；歌名自動整理、自動下載並安裝更新；setup.exe 106.1 MB（`3ddc1a30…b63759`）、zip 144.2 MB（`7d9b6966…c925e59`），sha256 已核對；使用者回報合輯網址讀不到 → beta.2 |
| **v2.5.0** | dba2aa7 | **正式版（Latest）**；程式碼同 v2.5.0-beta.2；setup.exe 106.1 MB（`cd2314ba…a4edc67`）、zip 144.1 MB（`665fd29c…2ca060`），sha256 已核對；**使用者實測無誤** |
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

**v2.6.0**（未發布；使用者選了「歌名自動整理」與「自動下載並安裝更新」）

| 項目 | 修改的檔案與重點 |
|---|---|
| beta.2 修正：YouTube「合輯」讀不到 | `core/url_parser.py` 新增 `ParsedUrl.playlist_source_url`：清單 ID 以 `RD` 開頭（YouTube 自動產生的合輯）時改用播放頁面網址 `watch?v=…&list=RD…`（`playlist?list=RD<影片ID>` 也從 ID 推回影片），yt-dlp 會從播放頁面讀取合輯；一般清單仍用 `playlist?list=`。`gui/main_window.py` `_expand_playlists` 改用它。`core/errors.py`：「unviewable」錯誤改為中文說明 |
| beta.2 修正：相信音樂等的標題寫法 | `core/title_cleanup.py`：`[ ]` 內含中文時視為歌名（「歌手 [ 歌名 ]」）；合唱以 ╳ × ＆ 連接時每位演出者分別去掉英文（`_drop_translations`）；中英文之間沒有空格（「MAYDAY五月天」）也能拆（頻道名稱不拆，避免「SMG音乐」變「音乐」）；「Official Live Video」「纯享」視為雜訊；✦★♪ 等裝飾符號去掉；括號外是一句話（含，。！？或超過 40 字）時不當演出者。使用者合輯的 8 個標題已加入 `tests/test_title_cleanup.py` |
| 歌名自動整理（MP3） | 新檔 `core/title_cleanup.py`：`clean_title(info)` 優先用 YouTube 的 `track`＋`artists`；否則移除含雜訊字（Official、MV、Lyrics、動態歌詞、4K…）的括號與前後雜訊字，`【】《》「」『』` 內的文字視為歌名、括號外為演出者，否則以「 - 」「｜」拆成演出者與歌名（頻道名出現在哪邊，哪邊就是演出者），沒有演出者時用 `clean_channel()`（去掉 - Topic、VEVO、官方頻道…）；中文後的英文翻譯（以大寫開頭）去掉，但 Remix / Live / Acoustic 等版本字保留；`( )`、`[ ]` 中非雜訊的內容保留在歌名後。`core/downloader.py`：MP3 且 `DownloadPreferences.clean_titles` 時設定 `info["track"]`、`info["artist"]`、`info["artists"]`（供 FFmpegMetadata），檔名用 `演出者 - 歌名`；`DownloadResult.title` 仍為原標題。設定 `clean_titles`（預設開） |
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
  app.py                        進入點：日誌、Job Object、具名 mutex、單一執行個體鎖、Qt 中文翻譯、--smoke-test / --version
  app_context.py                組合 DB / 設定 / Downloader（cookies_provider、preferences_provider）/ QueueManager
  core/task_models.py           任務模型與狀態機（等待中 / 下載中 / 轉檔中 / 已完成 / 失敗 / 已取消）
  core/url_parser.py            網址分類、正規化、去重、錯誤原因
  core/downloader.py            yt-dlp 下載引擎（暫存隔離、取消、驗證、不覆蓋移動、播放清單讀取、字幕、DownloadPreferences）
  core/converter.py             FFmpeg / FFprobe / Deno 偵測、ffprobe 驗證、格式選擇、後處理（含歌名與封面）
  core/updates.py               新版本檢查、下載與驗證安裝程式、啟動安裝（自動更新）
  core/title_cleanup.py         歌名自動整理（演出者 - 歌名）
  core/local_convert.py         本機影音檔轉 MP3（暫存檔→驗證→不覆蓋移動、進度、取消）
  core/playlist_files.py        播放清單檔（.m3u8）批次記錄與產生
  core/cookies.py               YouTube cookies 設定 → yt-dlp 參數（cookies.txt 只用副本）
  core/queue_manager.py         佇列排程、取消、重試、保存與恢復（不依賴 Qt）
  core/errors.py                例外 → 中文說明（yt-dlp、FFmpeg、cookies、磁碟、權限）
  storage/database.py           SQLite（參數化 SQL、PRAGMA user_version migration，目前 v2）
  storage/settings.py           AppSettings（cookies、embed_metadata、playlist_subfolder、notify_on_complete、rate_limit_mbps、
                                download_subtitles、auto_paste_clipboard、check_updates、auto_download_updates、skipped_update_version、
                                playlist_m3u、clean_titles 等）
  gui/main_window.py            主視窗（加入佇列、播放清單、拖曳、剪貼簿帶入、字幕勾選、雙擊播放、批次操作、完成通知、新版本提醒）
  gui/playlist_dialog.py        播放清單選擇對話框（勾選要下載的影片，可依清單分組取得）
  gui/history_dialog.py         下載歷史（搜尋、在檔案總管中顯示、重新下載）
  gui/convert_dialog.py         本機檔案轉 MP3 視窗
  gui/queue_table.py            表格 model、品質 / 狀態文字、進度條與操作按鈕 delegate
  gui/settings_dialog.py        設定（含「YouTube 登入資訊（選用）」）
  gui/qt_bridge.py / workers.py / theme.py / i18n.py
  utils/paths.py                AppData、隨附檔位置、安全檔名、FileNameReserver
  utils/win_job.py              Job Object（結束時終止子程序；自動更新前可取消）、具名 mutex（供安裝程式偵測；自動更新前釋放）
  utils/system_open.py          開啟資料夾、在檔案總管中選取檔案、以預設播放器開啟 MP3 / MP4
  utils/logging_utils.py
tests/                          單元、GUI（pytest-qt）、integration/（本機 HTTP＋真實 yt-dlp / FFmpeg）、fakes.py
scripts/
  setup_windows.bat / run_dev.bat / build_exe.bat   Windows 開發與打包
  build_installer.py / .bat     以 Inno Setup 建立 setup.exe 與 .sha256
  verify_installer.py           CI 中實際靜默安裝、啟動、轉檔、自動更新（/WAITPID、/RESTARTAPP）、解除安裝並檢查捷徑與登錄
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
docs/WINDOWS_INTEGRATION_TESTS.md   Windows 實機測試清單（A–I 段；C12–C17、E6a 為 v2.3.0，C18–C21 為 v2.4.0，C22–C25 為 v2.5.0，C26–C28 為 v2.6.0 新功能）
docs/RELEASE_NOTES.md               Release 頁面說明（release.yml 會讀取）
THIRD_PARTY_NOTICES.md              第三方授權
```

---

## 3. 剛剛做的關鍵決定，以及為什麼這樣決定

### 3.1 最近幾輪（v2.1.3～v2.5.0）的決定

| 決定 | 原因 |
|---|---|
| 自動更新**只在安裝版**自動下載與安裝，免安裝版導向下載頁 | 免安裝版沒有安裝程式可執行，也不能保證有權限覆寫資料夾；安裝版由 Inno Setup 處理升級（清除舊 `_internal`、捷徑、登錄）最可靠。 |
| 安裝程式需**同時符合** GitHub API 的 `digest` 與 Release 的 `.sha256` | 兩個來源互相核對，下載不完整或被竄改時不會執行；網址由程式固定組成，不採用 API 回傳的連結。 |
| 安裝**一定先詢問**，不在背景自動安裝 | 安裝要關閉程式，會中斷下載與轉檔；由使用者決定時機（轉檔進行中直接拒絕）。 |
| 安裝程式用 **`/WAITPID` 等舊程式結束**，程式先**取消 Job Object 的子程序終止並釋放 mutex** | 程式的 Job Object 會在結束時終止所有子程序（包括安裝程式）；安裝程式偵測到 mutex 會停止；舊程式未結束時覆蓋會遇到檔案使用中。三者都處理後才能「關閉 → 安裝 → 重開」。 |
| 歌名整理**只用在 MP3**，佇列與歷史仍顯示原標題 | MP4 多半不是歌曲（vlog、教學），套用「演出者 - 標題」反而奇怪；保留原標題讓使用者能對照、整理錯也看得出來。 |
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

- **待辦**：v2.6.0-beta.2 的 Windows CI 通過 → 請使用者發布 `v2.6.0-beta.2` → 確認附件 → 使用者實測（合輯網址、C26、C28）
  → 發布正式版 `v2.6.0` → 確認附件與 Latest → 更新本文件。
- **自動更新的完整流程（C27）要等 v2.6.0 之後的下一個正式版才能實測**：必須先裝有 v2.6.0（含自動更新功能），
  再發布更新的正式版。2.5.0 以前的版本沒有自動更新，只會顯示提醒。下一次發版時請使用者特別確認 C27。

之後可能的方向（**皆需使用者決定，未經同意不要做**）：

- 提出過但使用者未選的項目（2026-10-31）：
  - 兩次都未選：記住上次在主視窗選的格式與品質、加入前提醒「歷史紀錄中已下載過」。
  - 第二次檢查（v2.3.0）未選：同時下載上限從 3 提高到 5。
  - 第三次檢查（v2.4.0）未選：只下載片段（指定開始 / 結束時間）、自訂檔名格式（例如「演出者 - 標題」）。
  - 「實用小工具」建議中仍未選：播放清單同步（只下載新歌）、依章節分割成多首、音量平衡、
    全部下載完成後自動睡眠 / 關機、另存影片縮圖。
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
- **YouTube「合輯」（`list=RD…`）不能用 `playlist?list=` 讀取**；讀取清單一律用 `ParsedUrl.playlist_source_url`。
- **自動更新**：不要讓 `launch_installer()` 之外的地方啟動安裝程式；啟動前一定要 `allow_children_to_outlive()` 與 `release_app_mutex()`，
  否則安裝程式會被 Job Object 終止或停在「程式執行中」。`installer.iss` 的 `/WAITPID`、`/RESTARTAPP` 參數名稱與 `updates.launch_installer()` 必須一致，
  只能靠 Windows CI 的 `verify_self_update()` 驗證。`[Run]` 重新開啟程式那一行不可加 `skipifsilent`（自動更新是靜默安裝）。
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

# 背景監看：等待比上一次 Release run（AFTER_ID）更新的那一次完成（用 Bash run_in_background 執行）
AFTER_ID=<上一次 Release run 的 id>
until curl -sS "https://api.github.com/repos/makodo123/YT_Media_Tool/actions/workflows/release.yml/runs?per_page=3" \
  | python3 -c "import sys,json; r=[x for x in json.load(sys.stdin)['workflow_runs'] if x['id']>$AFTER_ID]; \
print(r[0]['id'], r[0]['conclusion']) if r and r[0]['status']=='completed' else sys.exit(1)"; do sleep 60; done
```
