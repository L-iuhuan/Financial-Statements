# 一键构建脚本: PyInstaller -> (可选) Inno Setup 安装器
# 用法: powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
# 前置: pip install pyinstaller; 如需生成安装器, 安装 Inno Setup 6

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== 1/3 清理旧构建 ===" -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist, installer_output -ErrorAction SilentlyContinue

Write-Host "=== 2/3 PyInstaller 打包 exe ===" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean fsa.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller 构建失败"; exit 1 }

$size = (Get-ChildItem dist\fsa -Recurse | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("  产物: dist\fsa\fsa.exe  ({0:N0} MB)" -f $size) -ForegroundColor Green

Write-Host "=== 3/3 编译 Inno Setup 安装器 ===" -ForegroundColor Cyan
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc installer.iss
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  安装器已生成: installer_output\" -ForegroundColor Green
    } else {
        Write-Error "Inno Setup 编译失败"; exit 1
    }
} else {
    Write-Host "  未检测到 Inno Setup 6, 跳过安装器编译。" -ForegroundColor Yellow
    Write-Host "  可分发 dist\fsa\ 整个目录 (绿色免安装), 或安装 Inno Setup 6 后重跑本脚本生成安装器。" -ForegroundColor Yellow
}

Write-Host "=== 构建完成 ===" -ForegroundColor Cyan
