# Windows 打包产物冒烟测试
# 用法:
#   通用版: powershell -ExecutionPolicy Bypass -File scripts\smoke_package.ps1
#   指定产物: powershell -ExecutionPolicy Bypass -File scripts\smoke_package.ps1 -Exe dist\fsa\fsa.exe
# 说明:
#   - 启动 exe 后等待并确认进程存活, 检查 SQLite 数据库已创建。
#   - 内部版带域控制, 在未入域机器上会主动退出并弹提示 (预期行为),
#     因此内部版冒烟必须在已入域且命中白名单的机器上执行。
param(
    [string]$Exe = "dist\fsa\fsa.exe",
    [int]$StartupSeconds = 8
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path $Exe)) {
    Write-Error "未找到打包产物: $Exe"
    exit 1
}

$exePath = (Resolve-Path $Exe).Path
$version = (Get-Item $exePath).VersionInfo
Write-Host "=== 打包产物信息 ===" -ForegroundColor Cyan
Write-Host "  路径: $exePath"
Write-Host "  文件版本: $($version.FileVersion) / 产品版本: $($version.ProductVersion)"
$internalDir = Join-Path (Split-Path $exePath -Parent) "_internal"
if (Test-Path $internalDir) {
    Write-Host "  onedir _internal 目录存在。" -ForegroundColor Green
} else {
    Write-Warning "未找到 _internal 目录, 若为 onedir 构建请检查 fsa.spec 的 COLLECT。"
}

Write-Host "=== 启动打包应用 ===" -ForegroundColor Cyan
$proc = Start-Process -FilePath $exePath -PassThru
Start-Sleep -Seconds $StartupSeconds

if ($proc.HasExited) {
    Write-Error "应用启动后提前退出, ExitCode=$($proc.ExitCode)。内部版需检查域控制配置; 其他情况请查看日志。"
    exit 1
}

$db = Join-Path $HOME ".fsa\data.db"
if (Test-Path $db) {
    Write-Host "SQLite 数据库已创建: $db" -ForegroundColor Green
} else {
    Write-Warning "未检测到数据库文件: $db"
}

Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "打包应用冒烟测试通过。" -ForegroundColor Green
