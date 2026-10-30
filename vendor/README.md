# vendor

建置時的外部執行檔放置處（不納入版本控制，見 `.gitignore`）。

- `vendor/ffmpeg/bin/ffmpeg.exe`、`ffprobe.exe`、`vendor/ffmpeg/LICENSE*`、`vendor/ffmpeg/VERSION.json`
  由 `scripts\fetch_ffmpeg.ps1` 依 `packaging\ffmpeg_manifest.json` 下載並驗證 SHA256 後產生。
- 開發時程式也會在此尋找 FFmpeg，因此執行一次 `fetch_ffmpeg.ps1` 後不需另外設定 PATH。
