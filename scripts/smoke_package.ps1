# Windows 打包产物冒烟测试
# 用法: powershell -ExecutionPolicy Bypass -File scripts\smoke_package.ps1 [-Exe dist\fsa\fsa.exe]
param(
    [string]$Exe = "dist\fsa\fsa.exe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path $Exe)) {
    Write-Error "未找到打包产物: $Exe"
    exit 1
}

Write-Host "=== 启动打包应用: $Exe ===" -ForegroundColor Cyan
$proc = Start-Process -FilePath (Resolve-Path $Exe) -PassThru
Start-Sleep -Seconds 8

if ($proc.HasExited) {
    Write-Error "应用启动后提前退出, ExitCode=$($proc.ExitCode)"
    exit 1
}

$db = Join-Path $HOME ".fsa\data.db"
if (Test-Path $db) {
    Write-Host "SQLite 数据库已创建: $db" -ForegroundColor Green
} else {
    Write-Warning "未检测到数据库文件: $db"
}

# 正常关闭应用
Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "打包应用冒烟测试通过。" -ForegroundColor Green
