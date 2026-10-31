# YT Media Tool 發行說明

## 安裝

**安裝版（建議）**：執行 `YT_Media_Tool-<版本>-win64-setup.exe`。

- 預設只為目前使用者安裝，不需要系統管理員權限；也可選擇為所有使用者安裝。
- 會建立開始功能表捷徑（桌面捷徑可選）。升級時直接執行新版安裝程式即可，設定與佇列會保留。
- 解除安裝：「設定 → 應用程式 → 已安裝的應用程式 → YT Media Tool」。會詢問是否一併刪除設定與紀錄；
  已下載的影片與音樂一律不會被刪除。

**免安裝版**：解壓縮 `YT_Media_Tool-<版本>-win64.zip`，執行 `YT_Media_Tool\YT_Media_Tool.exe`。
移除時刪除程式資料夾，以及 `%LOCALAPPDATA%\YT_Media_Tool`（設定與紀錄）即可。

兩種版本都不需要安裝 Python 或 FFmpeg。可用 `.sha256` 檔案核對完整性（PowerShell：`Get-FileHash <檔名>`）。
首次啟動若出現 SmartScreen 警告（未經程式碼簽章），請確認來源後選擇「其他資訊」→「仍要執行」。

## 主要功能

- YouTube 影片、Shorts、播放清單下載；播放清單會列出所有影片，可勾選要下載哪些（支援搜尋、全選 / 全不選）
- 多網址批次加入並自動去除重複
- MP4 720p / 1080p / 最高可用解析度；MP3 128 / 192 / 320 kbps；原始素材不足時明確顯示實際品質，並標示影片的最高可用解析度
- 下載佇列：並行 1–3 筆、單筆 / 全部取消、失敗重試、清除已完成、重新開啟時恢復未完成任務
- 批次操作：Ctrl / Shift 多選（Ctrl+A 全選）後「移除所選」、Delete 鍵或右鍵批次取消 / 重試 / 移除（不刪除檔案）
- 即時進度、速度、剩餘時間、合併與轉檔階段、詳細錯誤訊息；整體進度不計入失敗與取消的任務
- YouTube 登入資訊（選用）：遇到「登入以確認不是機器人」時，可在設定使用 Firefox 或 cookies.txt
  （Chrome / Edge 新版加密讓程式無法直接讀取，請用擴充功能匯出 cookies.txt）
- 同名檔案自動編號，不覆蓋既有檔案；下載過程只在任務專屬暫存資料夾中進行

## 隨附元件

- FFmpeg / FFprobe 9.0.2（LGPL 共用函式庫版本；版本、來源與 SHA256 見 `_internal\ffmpeg\VERSION.json`）
- Deno（yt-dlp 處理 YouTube 所需的 JavaScript 執行環境）
- 授權資訊見 `THIRD_PARTY_NOTICES.md`

## 已知限制

- FFmpeg 合併 / 轉檔進行中取消時，會在該步驟結束後才停止。
- 中斷的任務重新開始時會從頭下載。
- 不支援 DRM 保護的內容。需要登入的內容須在「設定 → YouTube 登入資訊」提供 cookies，且帳號本身有權觀看。
- YouTube 要求「登入以確認不是機器人」時，請在「設定 → YouTube 登入資訊」選擇已登入 YouTube 的 Firefox 或 cookies.txt。

## 使用聲明

本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。
