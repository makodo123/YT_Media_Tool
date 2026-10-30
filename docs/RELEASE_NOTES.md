# YT Media Tool V2.0.0 發行說明

## 安裝

1. 解壓縮 `YT_Media_Tool-2.0.0-win64.zip`（可用 `.sha256` 檔案核對完整性：
   PowerShell 執行 `Get-FileHash YT_Media_Tool-2.0.0-win64.zip`）。
2. 執行 `YT_Media_Tool\YT_Media_Tool.exe`。不需安裝 Python。
3. 首次啟動若出現 SmartScreen 警告（EXE 未經程式碼簽章），請確認來源後選擇「仍要執行」。

資料庫、設定與日誌存放於 `%LOCALAPPDATA%\YT_Media_Tool`；移除程式時刪除程式資料夾與該資料夾即可。

## 主要功能

- YouTube 影片、Shorts、播放清單（需確認）下載；多網址批次加入並自動去除重複
- MP4 720p / 1080p / 最高可用解析度；MP3 128 / 192 / 320 kbps；原始素材不足時明確顯示實際品質
- 下載佇列：並行 1–3 筆、單筆 / 全部取消、失敗重試、清除已完成、重新開啟時恢復未完成任務
- 批次操作：Ctrl / Shift 多選（Ctrl+A 全選）後「移除所選」、Delete 鍵或右鍵批次取消 / 重試 / 移除（不刪除檔案）
- 即時進度、速度、剩餘時間、合併與轉檔階段、詳細錯誤訊息；整體進度不計入失敗與取消的任務
- YouTube 登入資訊（選用）：遇到「登入以確認不是機器人」時，可在設定使用 Firefox 或 cookies.txt
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
