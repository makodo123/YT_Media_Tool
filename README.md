# YT Media Tool

[![Windows CI](https://github.com/makodo123/YT_Media_Tool/actions/workflows/windows-ci.yml/badge.svg)](https://github.com/makodo123/YT_Media_Tool/actions/workflows/windows-ci.yml)

Windows 10 / 11 的 YouTube 影音下載工具（繁體中文介面）。貼上 YouTube 網址，就能下載成 **MP4 影片**或 **MP3 音樂**：
歌名自動整理成「演出者 - 歌名」、整個播放清單可以勾選要哪幾首、還能只下載影片中的一段。

> **使用聲明**：本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。
> 本工具不實作、也不協助繞過 DRM 或其他存取限制；遇到受 DRM 保護的內容時會直接顯示「不支援」。

**目錄**：[下載與安裝](#下載與安裝) ｜ [功能](#功能) ｜ [常見問題](#常見問題) ｜ [資料存放位置](#資料存放位置) ｜
[已知限制](#已知限制) ｜ [開發者說明](#開發者說明)

---

## 下載與安裝

到 [Releases](https://github.com/makodo123/YT_Media_Tool/releases/latest) 下載最新版本，以下兩種擇一：

**安裝版（建議）**

1. 下載 `YT_Media_Tool-<版本>-win64-setup.exe` 並執行
2. 依畫面指示安裝：預設只為目前使用者安裝，不需要系統管理員權限；也可以選擇為所有使用者安裝
3. 從開始功能表或桌面捷徑開啟「YT Media Tool」

**免安裝版**

1. 下載 `YT_Media_Tool-<版本>-win64.zip`
2. 解壓縮到任意資料夾（例如 `D:\Apps\YT_Media_Tool`）
3. 執行 `YT_Media_Tool\YT_Media_Tool.exe`

兩種版本都不需要另外安裝 Python 或 FFmpeg（已隨附）。

**系統需求**：Windows 10 / 11（64 位元）。

### 更新到新版本

- **安裝版**：有新的正式版時，程式會在視窗上方提醒，並在背景下載；下載完成後按「**立即安裝並重新開啟**」即可，
  程式會自動關閉、安裝，再重新開啟新版，設定、佇列與歷史紀錄都會保留。也可以隨時從「說明 → 檢查新版本」手動檢查，
  視窗會顯示檢查、下載進度與安裝結果。
- **免安裝版**：程式會提醒有新版，請到 Releases 下載新的 zip，解壓縮後取代舊的資料夾（設定與紀錄存在別處，不會遺失）。
- **使用 2.6.0 或 2.7.0 的使用者**：這兩版的自動更新有錯誤，按「立即安裝並重新開啟」不會成功。
  請手動下載並執行最新的安裝程式一次，之後就能正常自動更新。

### 解除安裝

「設定 → 應用程式 → 已安裝的應用程式 → YT Media Tool」。解除安裝時會詢問是否一併刪除設定與紀錄；
**已下載的影片與音樂一律不會被刪除**。免安裝版直接刪除程式資料夾即可。

## 功能

**下載**

| 功能 | 說明 |
|---|---|
| 貼上網址 | 可一次貼上多個網址，或直接從瀏覽器把網址拖曳進視窗；在瀏覽器複製 YouTube 網址後切回程式會自動帶入（可在設定關閉）。同一部影片的不同網址寫法會自動去除重複；不支援的網址會逐一說明原因 |
| 格式與品質 | MP4：720p / 1080p / 最高可用解析度；MP3：128 / 192 / 320 kbps |
| 播放清單 | 貼上播放清單網址（或播放清單中某首歌的網址），會列出清單中每首歌的名稱、長度與「預計檔名」（點兩下可修改），勾選要下載哪些（可搜尋、全選 / 全不選；一次最多 500 部）。從清單中某首歌的網址加入時，預設只勾選那一首。下載的歌存到以清單名稱命名的子資料夾，並產生依原順序排列的清單檔「清單名稱.m3u8」，音樂播放器可直接開啟（皆可在設定關閉） |
| 播放清單同步 | 之前下載過（同格式、檔案還在）的歌在選歌視窗標示「✓ 已下載」並預設不勾選；再次加入同一個播放清單時，只會下載新加入的歌（也可按「只選未下載的」）。清單檔 .m3u8 會沿用原本那一個，並包含之前下載的歌 |
| 已下載過提醒 | 貼上之前已經下載過的影片（同格式、檔案還在）時，會先詢問「略過已下載的」或「仍要下載」（再下載不會覆蓋原檔）；從歷史紀錄「重新下載」則不會詢問 |
| 只下載片段 | 勾選「只下載片段」並輸入開始 / 結束時間（例如 1:20～4:35；留白表示從頭或到結尾），只下載影片中的一段，適合從演唱會或節目中截出一首歌，不必下載整部影片。檔名會加上「（片段 1.20-4.35）」；一次用於一部影片 |
| 字幕 | 主視窗勾選「下載字幕」後，MP4 會一併下載字幕，存成與影片同名的 .srt（優先順序：繁體中文 → 中文 → 簡體中文 → 英文；沒有時使用 YouTube 自動產生的字幕）。字幕下載失敗不影響影片 |
| 速度上限 | 可在設定限制下載速度（例如 5 MB/s），避免佔滿網路 |
| 同時下載數量 | 預設一次下載 1 部，可設定為 1～3 部 |

**歌名與檔案整理**

| 功能 | 說明 |
|---|---|
| 歌名自動整理 | 檔名與歌曲資訊自動整理成「演出者 - 歌名」，例如「周杰倫 Jay Chou【晴天】Official MV」→「周杰倫 - 晴天」。MP3 一律整理；MP4 只在標題中找得到演出者時整理（vlog 等影片維持原標題）。優先使用 YouTube 提供的歌曲資訊，整理不出合理結果時保留原標題；佇列中仍顯示原標題（可在設定關閉） |
| 歌名、演出者與封面 | MP3 / MP4 會寫入歌名、演出者（整理後的演出者，找不到時用頻道名稱），並以影片縮圖作為封面，手機與音樂播放器會顯示（可在設定關閉） |
| 整理舊檔案的歌名 | 「工具 → 整理舊檔案的歌名」：掃描資料夾中之前下載的 MP3 / MP4（以及 YouTube 合輯的「Mix - …」資料夾），預覽「目前名稱 → 整理後名稱」，可勾選、可修改，確認後才改名，也可以復原。同名檔案不會被覆蓋；同名的字幕檔與 .m3u8 清單會一併更新 |
| 本機檔案轉 MP3 | 「工具 → 本機檔案轉 MP3」，或直接把電腦裡的影音檔拖進主視窗，就能轉成 MP3（128 / 192 / 320 kbps）。原檔不會被修改；同名 MP3 已存在時自動加上編號 |

**下載佇列與紀錄**

| 功能 | 說明 |
|---|---|
| 下載佇列 | 顯示每筆的影片名稱、格式、品質、進度、速度、剩餘時間與狀態；可單筆取消、全部取消、重試失敗的任務、清除已完成、右鍵上移 / 下移、暫停 / 開始佇列。雙擊已完成的任務直接播放；選取任務可在下方看到詳細資訊與失敗原因 |
| 批次操作 | 按住 Ctrl / Shift 多選（Ctrl+A 全選）後，可按「移除所選」或 Delete 鍵移除，也可用右鍵一次取消、重試或移除。移除只會刪除佇列中的紀錄，不會刪除已下載的檔案 |
| 實際畫質 / 音質提示 | 影片本身沒有您選的解析度時，品質欄會顯示「1080p → 720p ⚠」；影片還有更高解析度時顯示「720p（最高 1080p）」。MP3 的原始音質低於您選的品質時顯示「192 kbps → 124 kbps ⚠」（轉成較高位元率也不會變好聽）。滑鼠停在品質欄上可看詳細說明 |
| 完成通知 | 佇列全部下載完成時，如果程式不在最上層，工作列圖示會閃爍並顯示系統通知（可在設定關閉） |
| 下載歷史紀錄 | 「工具 → 下載歷史紀錄」：可搜尋；雙擊在檔案總管中顯示檔案；右鍵可複製網址或以相同格式重新下載 |
| 重新開啟時接續 | 關閉程式時還沒下載完的任務，下次開啟會詢問是否繼續下載 |

**更新與設定**

| 功能 | 說明 |
|---|---|
| 使用說明 | 「說明 → 使用說明」（或按 F1）以瀏覽器開啟這份說明 |
| 新版本提醒 | 啟動時向 GitHub 查詢是否有新的正式版（只讀取版本號，不傳送任何個人資料），有新版時在視窗上方提醒；可略過這個版本，或在設定關閉 |
| 自動更新（安裝版） | 有新版時在背景下載安裝程式，並核對檢查碼確認檔案完整；完成後按「立即安裝並重新開啟」即可更新。從「說明 → 檢查新版本」手動檢查時，視窗會依序顯示「正在檢查 → 下載進度 → 可以安裝 → 安裝中」；更新後重新開啟程式時會告訴您是否成功，失敗時直接說明原因，並可一鍵複製詳細資訊回報問題 |
| 設定（工具 → 設定） | 下載資料夾（會記住上次使用的資料夾）、同時下載數量、速度上限、預設格式與品質、自動帶入剪貼簿網址、全部完成後開啟資料夾、完成通知、保留歷史紀錄、寫入歌名與封面、自動整理歌名、播放清單子資料夾、播放清單檔（.m3u8）、啟動時檢查新版本、有新版本時自動在背景下載、FFmpeg 資料夾、YouTube 登入資訊（選用） |
| 檔案安全 | 下載過程都在隱藏的暫存資料夾中進行，完成並檢查檔案沒問題後，才放進下載資料夾；同名檔案會自動加上編號，**絕不覆蓋您原本的檔案**；取消或失敗時只清除這次的暫存檔 |

## 常見問題

### 第一次開啟時出現「Windows 已保護您的電腦」（SmartScreen）

因為程式沒有購買數位簽章，Windows 不認得它。確認是從本專案的 Releases 下載後，按「其他資訊」→「仍要執行」即可。

### YouTube 要求「登入以確認不是機器人」

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
- 也可以先試著關閉 VPN 或換一個網路。

### 出現「資料庫版本 3 比程式支援的版本 2 新，請更新程式」

代表電腦上裝的程式版本**比之前用過的版本舊**（例如用過 2.8.0 之後又裝回 2.7.1）。新版會把資料升級成新格式，舊版看不懂，
為了不弄壞您的資料而停止開啟。請到 Releases 下載並安裝**最新版**，設定與紀錄都還在。

### 有新版本，但程式沒有提醒

- 確認「工具 → 設定 → 啟動時檢查是否有新版本」有勾選，且沒有按過「略過這個版本」。
- 測試版（版本名稱含 beta）不會自動提醒，只有正式版會。
- 2.8.0 以前的版本，在短時間內反覆開關程式（同一個網路每小時約 60 次）會被 GitHub 暫時擋下查詢；等一小時再開即可。
  2.8.1 起遇到這種情況會自動改用其他方式查詢。

### 主視窗上方顯示找不到 FFmpeg

一般下載的版本已隨附 FFmpeg，不會出現這個訊息。若出現，請重新安裝最新版；或到「工具 → 檢查程式元件」查看說明，
也可以在「工具 → 設定 → FFmpeg 資料夾」指定含有 `ffmpeg.exe` 與 `ffprobe.exe` 的資料夾。

## 資料存放位置

| 項目 | 位置 |
|---|---|
| 設定、下載佇列與歷史紀錄 | `%LOCALAPPDATA%\YT_Media_Tool\yt_media_tool.sqlite3` |
| 日誌（每個檔案 2 MB，保留 5 份） | `%LOCALAPPDATA%\YT_Media_Tool\logs\yt_media_tool.log` |
| 預設下載資料夾 | 「下載」資料夾中的 `YT_Media_Tool` |
| 下載中的暫存檔 | 下載資料夾中隱藏的 `.ytmt_tmp` 資料夾（下載完成、失敗或取消時會自動刪除） |

在檔案總管的網址列貼上 `%LOCALAPPDATA%\YT_Media_Tool` 按 Enter，就能打開設定與紀錄所在的資料夾。
程式不會在安裝資料夾中寫入任何資料。

## 已知限制

- 在合併影音或轉檔的步驟中按取消，會等該步驟結束（通常幾秒）才停止並清除暫存檔，期間狀態會顯示「取消中…」。
- 關閉程式時被中斷的任務，下次會從頭重新下載（不會接續下載到一半的檔案）。
- 不支援受 DRM 保護的內容與頻道網址。需要登入才能看的內容（年齡限制、會員專屬等），只有在設定 YouTube 登入資訊、
  且該帳號本身有權觀看時才能下載。
- YouTube 改版時，可能暫時無法下載；請更新到最新版（程式會提醒）。

## 授權

本專案以 [Apache License 2.0](LICENSE) 授權。隨附的第三方元件（FFmpeg、Qt、Deno 等）依其各自的授權散布，
詳見 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

---

## 開發者說明

以下內容供開發與打包使用，一般使用者不需要閱讀。

**使用的技術**：介面 PySide6、下載 yt-dlp、影音合併與 MP3 轉檔 FFmpeg / FFprobe、佇列與設定 SQLite、
打包 PyInstaller（one-folder EXE）＋ Inno Setup 安裝程式。

**系統需求（開發）**：Python **3.12**（64 位元）、PowerShell 5.1 以上，且需能連線至 PyPI 與 FFmpeg 下載來源。
以 `--no-ffmpeg` 建置的精簡版不隨附 FFmpeg，需自行安裝。

**資料位置（開發）**：預設下載資料夾以 Known Folder API 取得（支援資料夾重新導向）；暫存資料夾為
`<下載資料夾>\.ytmt_tmp\task_<編號>_<亂數>\`。測試或可攜環境可用環境變數 `YTMT_DATA_DIR` 指定資料位置、
`YTMT_FFMPEG_DIR` 指定 FFmpeg 位置。

### Windows 安裝與啟動（原始碼）

#### 步驟 1：安裝必要工具（只需做一次）

開啟「命令提示字元」或「PowerShell」，執行：

```bat
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
```

安裝完成後，請**關閉並重新開啟**命令提示字元，讓新安裝的程式生效。

#### 步驟 2：下載原始碼

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

#### 步驟 3：建立執行環境（只需做一次）

```bat
scripts\setup_windows.bat
```

此步驟會建立 `.venv` 虛擬環境，並安裝 `requirements-dev.txt` 中的套件（全部固定版本）。需要網路連線，約需數分鐘。

#### 步驟 4：啟動程式

```bat
scripts\run_dev.bat
```

#### 若程式提示找不到 FFmpeg

以下方法擇一：

- 執行 `powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1`：會依 `packaging\ffmpeg_manifest.json` 下載並驗證 FFmpeg，
  放到 `vendor\ffmpeg\bin`，程式會自動找到。
- 執行 `winget install -e --id Gyan.FFmpeg`，安裝後重新啟動程式。
- 在程式的「工具 → 設定 → FFmpeg 資料夾」，指定含有 `ffmpeg.exe` 與 `ffprobe.exe` 的資料夾。

### 打包 EXE

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

#### 建立安裝程式

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

#### 發布新版本到 GitHub Releases

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

#### FFmpeg 部署方式（可重現）

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

#### FFmpeg 尋找順序

程式**不假設**使用者已設定 PATH，會依下列順序尋找：

1. 設定中指定的 FFmpeg 資料夾
2. 環境變數 `YTMT_FFMPEG_DIR`
3. 隨附資料夾 `_internal\ffmpeg`（開發時為 `vendor\ffmpeg\bin`）
4. EXE 同層的 `ffmpeg` 資料夾
5. 系統 PATH

若都找不到，主視窗頂端會顯示警示，且無法加入任務；可在「工具 → 檢查程式元件」查看搜尋過的位置與安裝指引。

### 專案架構

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
│   │   ├── title_cleanup.py        歌名自動整理（演出者 - 歌名）
│   │   ├── batch_rename.py         整理舊檔案的歌名（預覽、改名、復原）
│   │   ├── download_index.py       已下載過的影片（已下載過提醒、播放清單同步）
│   │   ├── playlist_files.py       播放清單檔（.m3u8）
│   │   ├── local_convert.py        本機檔案轉 MP3
│   │   ├── updates.py              新版本檢查與自動更新
│   │   └── errors.py               錯誤訊息轉換（yt-dlp、FFmpeg、cookies、磁碟、權限）
│   ├── storage/
│   │   ├── database.py             SQLite（參數化 SQL、user_version migration）
│   │   └── settings.py             設定模型與驗證
│   ├── gui/
│   │   ├── main_window.py          主視窗
│   │   ├── queue_table.py          佇列表格模型、進度條與操作按鈕 delegate
│   │   ├── settings_dialog.py      設定
│   │   ├── history_dialog.py       下載歷史
│   │   ├── playlist_dialog.py      選擇播放清單中要下載的影片（預計檔名、已下載標示）
│   │   ├── rename_dialog.py        整理舊檔案的歌名
│   │   ├── convert_dialog.py       本機檔案轉 MP3
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

#### 執行緒模型

- GUI 主執行緒只處理介面；每個下載任務在獨立的工作執行緒中執行 yt-dlp。
- yt-dlp 的 progress hooks / postprocessor hooks 回報進度 → `QueueManager` 更新狀態（每 0.2 秒節流）
  → `QueueEventBridge` 以 Qt signal 排入主執行緒更新表格。
- 播放清單在 `QThreadPool` 中於背景展開。

#### 下載流程與檔案安全

1. 取得影片資訊（不下載），判斷實際可取得的品質，並檢查磁碟空間與寫入權限。
2. 在任務專屬的暫存資料夾中下載與後處理（yt-dlp 的輸出目錄就是暫存資料夾，**不會接觸下載資料夾中的任何既有檔案**）。
3. 以 FFprobe 驗證成品（MP4 需有影像串流，MP3 需有音訊串流）。
4. 以「不覆蓋」方式移到下載資料夾（同名時自動加上 ` (1)`、` (2)`…）。
5. 全部完成才標記為「已完成」；任何一步失敗或取消，都只刪除該任務自己的暫存資料夾。

關閉程式時，Windows Job Object 會讓 ffmpeg.exe / deno.exe 等子程序一併結束，不會殘留並鎖住檔案。

### 測試

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
