<#
.SYNOPSIS
  CI 用：執行指令並即時輸出；失敗時把最後 80 行輸出轉成 GitHub Actions 錯誤註解，
  讓失敗原因不需下載完整日誌就能在執行頁面看到。

.EXAMPLE
  ./scripts/ci_run.ps1 -Title "pytest" -Command ".venv\Scripts\python.exe -m pytest -q"
#>
param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Command
)
$ErrorActionPreference = "Continue"
$lines = New-Object System.Collections.Generic.List[string]
cmd /d /c "$Command 2>&1" | ForEach-Object {
    $text = "$_"
    Write-Output $text
    $lines.Add($text)
}
$code = $LASTEXITCODE
if ($code -ne 0) {
    $tail = ($lines | Select-Object -Last 80) -join "`n"
    $message = $tail.Replace("%", "%25").Replace("`r", "").Replace("`n", "%0A")
    Write-Output "::error title=$Title 失敗（exit $code）::$message"
    exit $code
}
