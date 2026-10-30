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
- 即時進度、速度、剩餘時間、合併與轉檔階段、詳細錯誤訊息
- 同名檔案自動編號，不覆蓋既有檔案

## 隨附元件

- FFmpeg / FFprobe（版本、來源與 SHA256 見 `_internal\ffmpeg\VERSION.json`）
- Deno（yt-dlp 處理 YouTube 所需的 JavaScript 執行環境）
- 授權資訊見 `THIRD_PARTY_NOTICES.md`

## 已知限制

- FFmpeg 合併 / 轉檔進行中取消時，會在該步驟結束後才停止。
- 中斷的任務重新開始時會從頭下載。
- 不支援需要登入、會員專屬、年齡限制或 DRM 保護的內容。

## 使用聲明

本工具僅供下載您擁有權利、已獲授權或平台明確允許下載的內容。
