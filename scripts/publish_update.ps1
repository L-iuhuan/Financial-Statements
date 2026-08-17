# 发布更新到共享盘: 构建产物 -> 计算 SHA256 -> 写 version.json -> 拷贝安装包
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\publish_update.ps1 -Version 0.4.2
#   (可选) -SkipBuild  跳过构建, 直接发布 installer_output 中已有的安装包
#   (可选) -Edition general  发布通用版 (默认 internal 内部版)
#
# 发布后: 各客户端启动时后台检查共享盘 version.json, 发现新版本 -> 设置页提示更新
#   -> 用户确认 -> 自动下载安装包 -> SHA256 校验 -> 静默安装 -> 自动重启
#   数据不受安装影响 (SQLite/配置在用户目录, 见 RELEASE_AND_SIGNING.md §3)

param(
    [Parameter(Mandatory=$true)] [string]$Version,
    [string]$Edition = "internal",
    [string]$SharePath = "\\192.168.8.3\财务部\办公软件\SoftwareUpdate\财务报表校验",
    [string]$ReleaseNotes = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== 发布更新 v$Version ($Edition) 到共享盘 ===" -ForegroundColor Cyan

# ── 1. 构建 (可选跳过) ──
if (-not $SkipBuild) {
    Write-Host "--- 构建安装包 ---" -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 `
        -Edition $Edition `
        -DomainWhitelist "toll.cn,TOLL" `
        -UpdateUrl "$SharePath\version.json"
    if ($LASTEXITCODE -ne 0) { Write-Error "构建失败"; exit 1 }
}

# ── 2. 定位安装包 ──
$suffix = if ($Edition -eq "internal") { "_内部版" } else { "" }
$installer = "installer_output\财务报表勾稽校验系统${suffix}_Setup_${Version}.exe"
if (-not (Test-Path $installer)) {
    Write-Error "安装包不存在: $installer`n请检查版本号或先去掉 -SkipBuild 重新构建"
    exit 1
}
Write-Host "  安装包: $installer ($([math]::Round((Get-Item $installer).Length/1MB,1)) MB)" -ForegroundColor Green

# ── 3. 计算 SHA256 ──
Write-Host "--- 计算 SHA256 ---" -ForegroundColor Cyan
$hash = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
Write-Host "  sha256: $hash" -ForegroundColor Green

# ── 4. 写 version.json ──
$manifest = @{
    version = $Version
    download_url = "$SharePath\$(Split-Path $installer -Leaf)"
    release_notes = $ReleaseNotes
    sha256 = $hash
} | ConvertTo-Json
$manifestPath = "$SharePath\version.json"
if (-not (Test-Path $SharePath)) {
    Write-Error "共享盘路径不可达: $SharePath"
    exit 1
}
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8
Write-Host "  清单已写入: $manifestPath" -ForegroundColor Green

# ── 5. 拷贝安装包到共享盘 ──
Write-Host "--- 拷贝安装包到共享盘 ---" -ForegroundColor Cyan
Copy-Item $installer -Destination $SharePath -Force
Write-Host "  已拷贝到: $SharePath" -ForegroundColor Green

Write-Host "=== 发布完成 ===" -ForegroundColor Cyan
Write-Host "客户端下次启动时将检测到新版本 $Version 并提示更新。" -ForegroundColor Green
