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

### 2.0 生产环境固化参数（2026-08-17 实测确认）

本企业内部版构建以以下域信息为准（首次入域实测于构建机 910373@toll.cn）：

| 项 | 值 | 说明 |
|---|---|---|
| DNS 域名 | `toll.cn` | 主判定依据（`USERDNSDOMAIN`） |
| NetBIOS 域名 | `TOLL` | 兜底（旧客户端/工作组场景 `USERDOMAIN`） |
| 域控服务器 | `\\XAGC` | 参考信息 |

**标准内部版构建命令（后续构建以此为准）**：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 `
  -Edition internal `
  -DomainWhitelist "toll.cn,TOLL"
```

白名单同时包含 DNS 名与 NetBIOS 名（大小写不敏感），覆盖：
- 正常入域机器：`USERDNSDOMAIN=toll.cn` 命中；
- 旧客户端/异常环境仅暴露 NetBIOS 名时：`USERDOMAIN=TOLL` 兜底命中。

### 2.1 域判定逻辑

- 启动时读取 `USERDNSDOMAIN`（首选）与 `USERDOMAIN`（白名单显式接受时回退）。
- `USERDNSDOMAIN` 为空即视为未加入域，弹出中文错误并拒绝启动。
- 白名单为空表示“允许任何域环境运行”；建议构建时通过 `-DomainWhitelist`
  固化正式 AD 域名，避免内部版被带出企业环境使用。
- 域策略分发建议：把安装器放入内网共享盘，并通过组策略软件安装
  (Computer Configuration → Policies → Software Settings → Assigned Applications)。

## 3. 更新通道

### 3.0 生产环境共享盘配置（2026-08-17 实测联通）

更新清单与安装包统一发布到内网共享盘：

```
\\192.168.8.3\财务部\办公软件\SoftwareUpdate\财务报表校验\
├── version.json          # 更新清单 (发布脚本自动生成, 含 sha256)
└── 财务报表勾稽校验系统_内部版_Setup_<版本>.exe
```

**标准发布命令（一条完成构建+校验+发布）**：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\publish_update.ps1 `
  -Version 0.4.2 -ReleaseNotes "更新说明"
# 已有安装包时跳过构建: 加 -SkipBuild
```

**客户端更新闭环**（内部版构建时经 `-UpdateUrl` 固化清单地址，无需用户配置）：

1. 客户端启动 → 后台读共享盘 `version.json`（失败仅记日志不打扰）
2. 发现新版本 → 设置页提示更新（版本号 + 更新说明）
3. 用户确认 → 自动下载安装包 → SHA256 校验（不匹配即删除并报中文错误）
4. 静默安装（`/SILENT /NOCANCEL`，覆盖旧版程序文件）→ 自动重启应用
5. **数据保留**：SQLite 历史/会话/覆写在 `~/.fsa/data.db`，QSettings 在注册表
   `HKCU\Software\FSA`——均在安装目录之外，覆盖安装/卸载均不触碰

已实测（2026-08-17）：发布脚本推送 v0.4.1 到共享盘成功；客户端以 0.4.0 身份
读取清单正确返回 has_update=True、UNC 下载地址与中文更新说明。

### 3.1 清单格式

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

### 4.0 本企业环境现状（2026-08-17 实测）

- 构建机（910373@toll.cn）当前**无代码签名证书**（Cert:\CurrentUser\My 与
  LocalMachine\My 均无）。
- 域内企业 CA 在线：`xadc.toll.cn\toll-XADC-CA`（certutil ping 500ms 连通）。
  证书模板枚举需企业管理员权限，**需向 IT 申请一张代码签名证书**
  （Code Signing 模板，导出私钥可选项建议允许，便于构建机签名）。
- 拿到证书前：内部版可无签名分发（共享盘运行未签名安装器会触发
  SmartScreen 蓝色提示，用户点"仍要运行"即可；签名后该提示消失）。
- 本地构建的 exe 直接运行无 Windows 提示属正常——SmartScreen 只拦截
  带"网络下载标记"(MOTW) 的文件，本地构建产物没有该标记。

### 4.1 内部版（自签名 + 域策略信任，已落地 2026-08-17）

**生产证书（已创建并启用）**：

| 项 | 值 |
|---|---|
| 主题 | `CN=TOLL FSA Internal Release, O=TOLL Finance` |
| 指纹 | `1511AB0EDEF9B262D50F4B7C50F93A1D4BD17A6C` |
| 存储 | 构建机 `Cert:\CurrentUser\My`（私钥可导出，有效期 5 年） |
| 公钥分发文件 | 共享盘 `\\192.168.8.3\财务部\办公软件\SoftwareUpdate\财务报表校验\TOLL-FSA-CodeSign.cer` |

**签名命令（标准发布流程，publish_update.ps1 构建后执行）**：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1 `
  -CertThumbprint "1511AB0EDEF9B262D50F4B7C50F93A1D4BD17A6C"
```

> 注意：内网机器访问不了在线时间戳服务器时，脚本自动降级为无时间戳签名
> （2026-08-17 修复，签名在证书 5 年有效期内有效）。

**域内信任分发（域管理员在域控执行一次，全域生效）**：

1. 从共享盘取 `TOLL-FSA-CodeSign.cer`；
2. 域控打开「组策略管理」→ 编辑默认域策略（或新建"FSA 证书信任"GPO）：
   `计算机配置 → 策略 → Windows 设置 → 安全设置 → 公钥策略 →
   受信任的根证书颁发机构` → 右键「导入」→ 选择该 .cer；
3. 客户端执行 `gpupdate /force` 或次日自动刷新后，
   签名状态从 UnknownError 转为 **Valid**，SmartScreen 不再拦截。

> 已实测（2026-08-17 构建机）：证书导入受信根前 `Get-AuthenticodeSignature` 状态为
> UnknownError（签名本身已写入），导入后 fsa.exe 与安装器均为 **Valid**。

自签名代码签名证书（重新创建时参考）：

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
