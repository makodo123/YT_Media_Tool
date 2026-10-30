<#
.SYNOPSIS
  下載並驗證要隨附的 FFmpeg / FFprobe（Windows x64），放入 vendor\ffmpeg。

.DESCRIPTION
  版本、下載網址與 SHA256 均來自 packaging\ffmpeg_manifest.json，確保建置可重現。
  - manifest 中 sha256 有值：下載後必須完全符合，否則中止。
  - sha256 為空：預設中止；加上 -AllowUnpinned 時會下載並顯示計算出的 SHA256，
    請人工比對官方公布的雜湊後寫回 manifest 並提交。
  也可用 -ZipPath 指定已下載的壓縮檔（離線建置）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1
  powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1 -ZipPath D:\ffmpeg-7.1.1-essentials_build.zip
#>
[CmdletBinding()]
param(
    [string]$ZipPath = "",
    [switch]$AllowUnpinned,
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Manifest = Get-Content (Join-Path $Root "packaging\ffmpeg_manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Vendor = Join-Path $Root "vendor\ffmpeg"
$BinDir = Join-Path $Vendor "bin"
$Downloads = Join-Path $Root "vendor\downloads"

if ((Test-Path (Join-Path $BinDir "ffmpeg.exe")) -and (Test-Path (Join-Path $BinDir "ffprobe.exe")) -and -not $Force) {
    Write-Host "vendor\ffmpeg 已存在，略過（使用 -Force 重新下載）。"
    exit 0
}

New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
if (-not $ZipPath) {
    $ZipPath = Join-Path $Downloads ([System.IO.Path]::GetFileName($Manifest.url))
    if (-not (Test-Path $ZipPath)) {
        Write-Host "下載 FFmpeg $($Manifest.version)：$($Manifest.url)"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $Manifest.url -OutFile $ZipPath -UseBasicParsing
    }
}

$Hash = (Get-FileHash -Algorithm SHA256 -Path $ZipPath).Hash.ToLowerInvariant()
if ($Manifest.sha256) {
    if ($Hash -ne $Manifest.sha256.ToLowerInvariant()) {
        Remove-Item $ZipPath -ErrorAction SilentlyContinue
        throw "SHA256 不符！預期 $($Manifest.sha256)，實際 $Hash。檔案可能損毀或遭竄改，已中止。"
    }
    Write-Host "SHA256 驗證通過：$Hash"
} elseif ($AllowUnpinned) {
    Write-Warning "manifest 尚未設定 sha256。本次檔案的 SHA256：$Hash"
    Write-Warning "請與官方公布的雜湊比對後，寫入 packaging\ffmpeg_manifest.json 的 sha256 欄位並提交。"
} else {
    throw "packaging\ffmpeg_manifest.json 未設定 sha256。計算值為 $Hash；請比對官方雜湊後寫入 manifest，或使用 -AllowUnpinned。"
}

$Extract = Join-Path $Downloads "extract"
if (Test-Path $Extract) { Remove-Item -Recurse -Force $Extract }
Expand-Archive -Path $ZipPath -DestinationPath $Extract
$Ffmpeg = Get-ChildItem -Path $Extract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$Ffprobe = Get-ChildItem -Path $Extract -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
if (-not $Ffmpeg -or -not $Ffprobe) { throw "壓縮檔中找不到 ffmpeg.exe 或 ffprobe.exe" }

if (Test-Path $Vendor) { Remove-Item -Recurse -Force $Vendor }
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item $Ffmpeg.FullName $BinDir
Copy-Item $Ffprobe.FullName $BinDir
$PackageRoot = Split-Path -Parent $Ffmpeg.Directory.FullName
Get-ChildItem -Path $PackageRoot -File | Where-Object { $_.Name -match '^(LICENSE|README)' } |
    ForEach-Object { Copy-Item $_.FullName $Vendor }

$VersionLine = (& (Join-Path $BinDir "ffmpeg.exe") -hide_banner -version | Select-Object -First 1)
$Info = [ordered]@{
    version        = $Manifest.version
    version_output = $VersionLine
    url            = $Manifest.url
    sha256         = $Hash
    license        = $Manifest.license
    license_url    = $Manifest.license_url
    source_code    = $Manifest.source_code
    fetched_at     = (Get-Date).ToUniversalTime().ToString("o")
}
$Info | ConvertTo-Json | Set-Content -Path (Join-Path $Vendor "VERSION.json") -Encoding UTF8
Remove-Item -Recurse -Force $Extract
Write-Host "完成：$BinDir"
Write-Host $VersionLine
