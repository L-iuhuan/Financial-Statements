# 发布与签名手册（内部版 / 通用版）

本文档给出双版本构建、域控制部署、更新通道与数字签名的落地步骤。
本软件不计划商用，内部使用场景不要求购买公共代码签名证书。

## 1. 构建双版本

在 Windows 构建机执行：

```powershell
# 通用版 (默认): 无域检查, 更新走 HTTPS 清单
powershell -ExecutionPolicy Bypass -File scriptsuild_installer.ps1

# 内部版: 启动时校验 AD 域 + 域名白名单, 可固化内网/共享盘更新清单
powershell -ExecutionPolicy Bypass -File scriptsuild_installer.ps1 `
  -Edition internal `
  -DomainWhitelist "corp.example.com,audit.example.com" `
  -UpdateUrl "\\\\fs-fileserver\\fsa\\version.json"
```

- 构建脚本会临时写入 `src/fsa/core/_edition_override.py`（已被 .gitignore 忽略），
  PyInstaller 打包后自动删除，不会污染源码仓库。
- 产物：
  - 免安装目录：`distsa\`（`fsa.exe` + `_internal`）
  - 安装器：`installer_output\财务报表勾稽校验系统_Setup_<版本>.exe`
  - 内部版安装器：`installer_output\财务报表勾稽校验系统_内部版_Setup_<版本>.exe`
- 开发环境可用环境变量快速验证内部版行为（不打包）：
  `$env:FSA_EDITION="internal"; $env:FSA_DOMAIN_WHITELIST="corp.example.com"`

## 2. 内部版域控制

- 启动时读取 `USERDNSDOMAIN`（首选）与 `USERDOMAIN`（白名单显式接受时回退）。
- `USERDNSDOMAIN` 为空即视为未加入域，弹出中文错误并拒绝启动。
- 白名单为空表示“允许任何域环境运行”；建议构建时通过 `-DomainWhitelist`
  固化正式 AD 域名，避免内部版被带出企业环境使用。
- 域策略分发建议：把安装器放入内网共享盘，并通过组策略软件安装
  (Computer Configuration → Policies → Software Settings → Assigned Applications)。

## 3. 更新通道

更新清单 JSON（HTTPS 或共享盘 UNC 均可）示例：

```json
{
  "version": "0.5.0",
  "download_url": "https://updates.example.com/fsa/财务报表勾稽校验系统_Setup_0.5.0.exe",
  "release_notes": "修复若干问题",
  "sha256": "<安装包 SHA256 小写十六进制>"
}
```

- 通用版：`download_url` 使用 HTTPS 地址。
- 内部版：`download_url` 可填 `\\\\server\\share\\fsa\\...exe` 或 `file:///...`；
  软件下载后按清单中的 `sha256` 校验，通过后经 `cmd /c timeout` 延迟 3 秒
  调用安装器 `/SILENT /NOCANCEL`，随后应用退出完成替换。
- 启动时软件仅在“系统设置 → 更新清单地址”已配置（或构建期固化）时异步检查，
  失败只记日志不打扰用户。

## 4. 数字签名

### 4.1 内部版（推荐：AD CS 或自签名 + 域策略信任，零费用）

自签名代码签名证书（在受控构建机上执行一次）：

```powershell
$cert = New-SelfSignedCertificate -Type CodeSigningCert `
  -Subject "CN=FSA Internal Release, O=FinanceAudit" `
  -KeyUsage DigitalSignature -KeyExportPolicy Exportable `
  -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddYears(5)
# 复制指纹
$cert.Thumbprint
```

签名构建产物：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1 -CertThumbprint "<指纹>"
```

域内信任（域管理员执行，全域生效）：

```powershell
# 1) 导出证书公钥
Export-Certificate -Cert $cert -FilePath \dc\sharesa-release.cer
# 2) 域控制器上导入到 "受信任的发布者" GPO:
#    Computer Configuration → Policies → Windows Settings → Security Settings
#    → Public Key Policies → Trusted Publishers → Import
```

### 4.2 通用版

按分发范围选择，本软件不计划商用时可先沿用内部自签名；如向外部分发：

- 购买 OV 代码签名证书（DigiCert / Sectigo 等），或
- Azure Trusted Signing（需 Entra ID/微软账号体系，按月/按签名量付费）。
证书安装到构建机 `Cert:\CurrentUser\My` 后，同样执行 `sign_build.ps1 -CertThumbprint "<指纹>"`。

### 4.3 验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1 -CheckOnly
Get-AuthenticodeSignature distsasa.exe | Format-List Status, StatusMessage, SignerCertificate
```

## 5. 发布冒烟检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke_package.ps1 -Exe distsasa.exe
```

- 脚本启动打包 exe，等待 8 秒确认进程存活，并检查 `%USERPROFILE%\.fsa\data.db` 已创建。
- 内部版在未加入域或未授权域的机器上应**主动退出并提示**（这是预期行为），
  因此内部版冒烟测试必须放在已入域且白名单命中的测试机上执行。
- 回滚：保留上一版本安装包即可覆盖安装回退；升级失败时安装器不会删除旧版本。

## 6. 更新包哈希与可选签名校验

- 更新包完整性：清单 `sha256` 必填，下载后先校验再安装（当前已实现）。
- 可选签名校验：安装器签名由 Windows SmartScreen/Authenticode 在安装时自行校验；
  如需应用内校验，可在版本清单增加 `signature` 字段后扩展 `Updater`（P2）。
