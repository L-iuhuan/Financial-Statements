# 签名构建脚本: 对 dist exe 与 Inno Setup 安装包进行 Authenticode 签名
# 用法:
#   检查现状: powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1 -CheckOnly
#   证书指纹: powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1 -CertThumbprint "<SHA1指纹>"
#   PFX 证书: powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1 -PfxPath cert.pfx -PfxPassword "<密码>"
# 说明: 仅对当前用户证书存储中的代码签名证书进行签名; 建议在构建机部署证书后使用指纹方式。
# 参考: docs\RELEASE_AND_SIGNING.md

param(
    [string]$CertThumbprint = "",
    [string]$PfxPath = "",
    [string]$PfxPassword = "",
    [string[]]$Targets = @(),
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$timestampServers = @(
    "http://timestamp.digicert.com",
    "http://timestamp.sectigo.com"
)

function Get-TargetFiles {
    if ($Targets.Count -gt 0) {
        return $Targets | ForEach-Object { (Resolve-Path $_).Path }
    }
    $files = @()
    if (Test-Path "dist\fsa\fsa.exe") { $files += (Resolve-Path "dist\fsa\fsa.exe").Path }
    if (Test-Path "installer_output") {
        $files += Get-ChildItem "installer_output" -Filter *.exe | ForEach-Object { $_.FullName }
    }
    if ($files.Count -eq 0) {
        Write-Error "未找到待签名文件, 请先执行 build_installer.ps1"
    }
    return $files
}

$targetFiles = Get-TargetFiles

if ($CheckOnly) {
    Write-Host "=== 签名状态检查 ===" -ForegroundColor Cyan
    foreach ($file in $targetFiles) {
        $sig = Get-AuthenticodeSignature $file
        $status = $sig.Status
        Write-Host ("  {0}: {1} ({2})" -f $file, $status, $sig.SignerCertificate.Subject)
    }
    exit 0
}

if (-not $CertThumbprint -and -not $PfxPath) {
    Write-Error "请提供 -CertThumbprint 或 -PfxPath; 使用 -CheckOnly 可只检查现有签名。"
}

$cert = $null
if ($PfxPath) {
    if (-not $PfxPassword) {
        Write-Error "使用 -PfxPath 时必须提供 -PfxPassword"
    }
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(
        (Resolve-Path $PfxPath).Path,
        $PfxPassword,
        [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable
    )
} else {
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object { $_.Thumbprint -ieq $CertThumbprint } |
        Select-Object -First 1
    if (-not $cert) {
        Write-Error "当前用户证书存储中未找到指纹为 $CertThumbprint 的代码签名证书"
    }
}

Write-Host "=== 开始签名 (证书: $($cert.Subject)) ===" -ForegroundColor Cyan
foreach ($file in $targetFiles) {
    $signed = $false
    foreach ($server in $timestampServers) {
        try {
            Set-AuthenticodeSignature -FilePath $file -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $server | Out-Null
            $signed = $true
            break
        } catch {
            Write-Warning "时间戳服务器 $server 失败: $_"
        }
    }
    if (-not $signed) {
        # 内网环境在线时间戳不可达时, 无时间戳签名 (签名在证书有效期内有效)
        Write-Warning "在线时间戳均不可达, 改用无时间戳签名 (内网场景可用)"
        Set-AuthenticodeSignature -FilePath $file -Certificate $cert -HashAlgorithm SHA256 | Out-Null
    }
    $sig = Get-AuthenticodeSignature $file
    Write-Host ("  已签名: {0} -> {1}" -f (Split-Path $file -Leaf), $sig.Status) -ForegroundColor Green
}

Write-Host "=== 签名完成 ===" -ForegroundColor Cyan
