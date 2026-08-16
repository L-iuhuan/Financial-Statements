# 一键构建脚本: PyInstaller -> (可选) Inno Setup 安装器
# 用法:
#   通用版: powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
#   内部版: powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Edition internal -DomainWhitelist "corp.example.com"
# 参数:
#   -Edition          internal(内部版, 启动域控制) / general(通用版, 默认)
#   -DomainWhitelist  内部版允许的 AD 域名, 逗号分隔
#   -UpdateUrl        构建期固化的默认更新清单地址 (HTTPS 或内网 UNC)
#   -SignThumbprint   构建完成后用当前用户证书存储中的代码签名证书签名
# 前置: pip install pyinstaller; 如需生成安装器, 安装 Inno Setup 6
# 签名: scripts\sign_build.ps1 (docs\RELEASE_AND_SIGNING.md)

param(
    [ValidateSet("internal", "general")] [string]$Edition = "general",
    [string]$UpdateUrl = "",
    [string]$DomainWhitelist = "",
    [string]$SignThumbprint = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$EditionFile = "src\fsa\core\_edition_override.py"

function Write-EditionOverride {
    $domainList = @()
    if ($DomainWhitelist) {
        $domainList = @($DomainWhitelist.Split(",;；") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    $domainTuple = ($domainList | ForEach-Object { '"' + $_.ToLower() + '"' }) -join ", "
    $content = @"
# 构建期生成的版本通道配置 (由 build_installer.ps1 写入, 不要手工编辑/提交)
EDITION = "$Edition"
DOMAIN_WHITELIST = ($domainTuple)
DEFAULT_UPDATE_URL = "$UpdateUrl"
"@
    Set-Content -Path $EditionFile -Value $content -Encoding UTF8
    Write-Host "  版本通道: $Edition  (白名单: $($domainList -join ', '), 更新地址: $UpdateUrl)" -ForegroundColor Green
}

Write-Host "=== 1/4 写入版本通道配置 ===" -ForegroundColor Cyan
Write-EditionOverride

try {
    Write-Host "=== 2/4 清理旧构建 ===" -ForegroundColor Cyan
    Remove-Item -Recurse -Force build, dist, installer_output -ErrorAction SilentlyContinue

    Write-Host "=== 3/4 PyInstaller 打包 exe ===" -ForegroundColor Cyan
    python -m PyInstaller --noconfirm --clean fsa.spec
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller 构建失败"; exit 1 }

    $size = (Get-ChildItem dist\fsa -Recurse | Measure-Object Length -Sum).Sum / 1MB
    Write-Host ("  产物: dist\fsa\fsa.exe  ({0:N0} MB)" -f $size) -ForegroundColor Green

    Write-Host "=== 4/4 编译 Inno Setup 安装器 ===" -ForegroundColor Cyan
    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($iscc) {
        & $iscc installer.iss
        if ($LASTEXITCODE -eq 0) {
            # 按版本通道重命名安装包, 内部版带"_内部版"后缀
            $versionLine = Select-String -Path "src\fsa\core\version.py" -Pattern 'APP_VERSION.*=.*"([^"]+)"'
            $version = $versionLine.Matches[0].Groups[1].Value
            $genericName = "财务报表勾稽校验系统_Setup_$version.exe"
            $genericPath = Join-Path "installer_output" $genericName
            if ($Edition -eq "internal") {
                $internalName = "财务报表勾稽校验系统_内部版_Setup_$version.exe"
                Rename-Item -Path $genericPath -NewName $internalName
                Write-Host "  安装器已生成: installer_output\$internalName" -ForegroundColor Green
            } else {
                Write-Host "  安装器已生成: installer_output\$genericName" -ForegroundColor Green
            }
        } else {
            Write-Error "Inno Setup 编译失败"; exit 1
        }
    } else {
        Write-Host "  未检测到 Inno Setup 6, 跳过安装器编译。" -ForegroundColor Yellow
        Write-Host "  可分发 dist\fsa\ 整个目录 (绿色免安装), 或安装 Inno Setup 6 后重跑本脚本生成安装器。" -ForegroundColor Yellow
    }

    if ($SignThumbprint) {
        Write-Host "=== 5/5 数字签名 ===" -ForegroundColor Cyan
        & powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\sign_build.ps1") -CertThumbprint $SignThumbprint
        if ($LASTEXITCODE -ne 0) { Write-Error "数字签名失败"; exit 1 }
    }

    Write-Host "=== 构建完成 ($Edition) ===" -ForegroundColor Cyan
} finally {
    # 清理构建期覆写文件, 避免被误提交到 git
    Remove-Item -Force $EditionFile -ErrorAction SilentlyContinue
}
