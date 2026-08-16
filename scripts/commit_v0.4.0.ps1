$ErrorActionPreference = "Stop"
$Root = Join-Path $PSScriptRoot ".."
Set-Location $Root

git add -A
if ($LASTEXITCODE -ne 0) {
    Write-Error "git add failed"
    exit 1
}

git commit -F "scripts\commit_v0.4.0_message.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Error "git commit failed"
    exit 1
}

Write-Host "v0.4.1 commit created. Next (optional):" -ForegroundColor Green
Write-Host "  git tag v0.4.1"
Write-Host "  git push origin fix/review-2026-08-13 --tags"
