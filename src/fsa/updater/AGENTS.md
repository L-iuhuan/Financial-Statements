# updater — 内网自动更新

## OVERVIEW

`Updater` 检查版本 → 下载（SHA256 校验）→ 静默安装。**仅用标准库 urllib，禁止 requests**（包 docstring + 根 §6.2，保护打包体积）。所有失败统一为中文 `UpdateError(FSAError)`。

## version.json 清单格式

```json
{
  "version": "0.2.0",             // 必需
  "download_url": "http://...",   // 必需
  "release_notes": "...",         // 可选
  "sha256": "hex lowercase"       // 可选；缺失时跳过校验仅 warning
}
```

清单地址来源：QSettings `update_manifest_url` → 缺省 `edition.get_edition_config().default_update_url`（内部版默认内网/共享盘，通用版 HTTPS）。支持 UNC 路径（`\\server\share` → `file://` 转换）与本地文件路径直读。

## INVARIANTS

- **install() 生命周期契约**：`cmd /c timeout /t 3 && "<installer>" /SILENT /NOCANCEL` 分离进程启动——3 秒延迟是给本应用退出的时间窗，**调用方（GUI）必须立即退出**，安装器随后替换程序文件
- **SHA256 尽力而为**：清单缺 sha256 → warning + 不阻塞下载（向后兼容）；但一旦取得哈希且不匹配 → **删除已下载文件** + 抛 `UpdateError`
- 异常收窄：只 catch `URLError/TimeoutError/OSError/json.JSONDecodeError`，无宽 catch；`subprocess` 函数内惰性导入，Popen 带 `# noqa: S603` + 理由注释
- `compare_versions`：去前导 v/V，按 `.` 分段数值比较，短段补 0
- `check_for_update` 是纯只读操作；启动时后台检查失败仅记日志，不打扰用户（gui/app.py `_UpdateCheckBridge`）
- 当前版本号由调用方传入（`core/version.py` 的 `APP_VERSION`）——updater 自己不 import version

## GOTCHA

- **`compute_sha256` 与 `core/resources.py` 的 `sha256_file` 是两套实现**：updater 版失败抛 `OSError`；resources 版失败返回 `""`。勿混用、勿"合并优化"
- 内部版域检查在 `core/edition.py`（启动期），不在本模块——本模块只认清单地址

## 消费方

`gui/app.py`（启动后台检查）、`gui/pages/settings_page.py`（手动检查/下载/确认后 install）、`scripts/verify_update.py`；测试 `tests/updater/test_updater.py`。
