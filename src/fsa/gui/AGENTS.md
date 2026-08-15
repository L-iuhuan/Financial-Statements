# gui — PySide6 界面层

## OVERVIEW
自定义 chrome（**不用 FluentWindow**）：`Sidebar` 240px + `Topbar` 48px + `QStackedWidget` 5 页 + `AgentDrawer`/`AgentFAB`。页面间解耦全靠 `AppState` 信号（`reports_changed`/`results_changed`/`history_changed`）。

## STRUCTURE

- 根：`app.py`（引导）、`app_state.py`（状态+信号中枢，持有 Database+3 repos）、`theme.py`（设计令牌+QSS 生成）、`formula_display.py`（公式→中文展示）
- 主窗口拆分：`main_window.py`（壳/导航，272 行）+ `main_window_agent.py`（LLM 交互）+ `main_window_debate.py`（辩论）+ `main_window_drawer.py`（抽屉管理）
- 并发：`agent_worker.py` — `AgentWorker` 后台线程执行器（见线程约定）
- 导出：`export_helper.py` — 导出辅助（异常统一转中文提示）
- `pages/`：import / audit / rule / history / settings（+`settings_sections.py`）
- `widgets/`：sidebar, topbar, drop_zone, report_card, result_card, summary_card, agent_drawer, agent_sessions, agent_fab, custom_rule_dialog

## 线程约定（重要）

- **无 QThread 并发**（`QThread` 仅在 agent_drawer 用于当前线程断言）；统一模式 = `threading.Thread` + `QMetaObject.invokeMethod(QueuedConnection)` 回主线程
- **LLM 长任务全部后台化**：AgentLoop/诊断/辩论走 `AgentWorker`；启动新任务前 `_cancel_active_worker()` 取消旧任务；`on_finished` 统一走 `_on_worker_finished()`（恢复 UI + 释放引用）；`closeEvent` 先取消 worker 再关库——不要直接在主线程调 LLM
- 校验/导入/导出仍主线程同步执行
- SQLite `check_same_thread=False` + WAL 已为多线程预留

## 样式约定

- `setObjectName` PascalCase：`"Sidebar"`/`"Topbar"`/`"ResultCard"`/`"BtnPrimary"`/`"FilterTab"` 等；属性选择器驱动状态：`[active="true"]`、`[status="pass|fail|error"]`、`[drag="true"]`
- `theme.py` 单一 QSS 生成；品牌色精炼靛蓝 `BRAND_500=#5b5ee6`（由钢蓝灰演进，见 DESIGN_SYSTEM.md；HANDOFF.md"深青玉/钢蓝灰"表述已过时）；金额用 `get_mono_font()` + `{:,.2f}`
- Fluent 组件克制使用：仅 `FluentIcon`/`InfoBar`/`IconWidget`/`SwitchButton`；其余自定义 + QSS；**不用 Emoji 图标**
- 内联样式组件须用 `bind_theme_listener(self, fn)` 注册主题监听（自动随控件销毁注销，防泄漏）

## 惯例

- 批量重建先 `setUpdatesEnabled(False)`；删控件先 `hide()` 再 `deleteLater()`；筛选只切可见性不重建卡片
- 文件行数按根 §3.3 灵活口径（逻辑文件软目标 250，数据密集豁免）；大文件按职责拆分的实例：主窗口 4 文件、settings_sections、agent_sessions
- 用户可见文本全中文、面向财务人员（P4/P6）；异常 → 中文 InfoBar（"文件被占用，请关闭已打开的 Excel 文件后重试"，非异常栈）

## 边界

- GUI 不执行 SQL：一律经 `AppState` 暴露的 `history_repo/chat_repo/override_repo`；`gui/` 中 `import sqlite3` 仅为捕获 `DatabaseError`
- 文件访问经 core：`ImportService`/`AuditExporter`/`save_custom_rules`/`resource_path`
- 校验入口唯一：`import_page` → `services.PackageValidationService`
- `# type: ignore` 仅允许在 `gui/` 且必须带具体错误码（Qt override/method-assign/arg-type）

## QSettings 键

`theme_mode, default_tolerance, gross_margin_threshold, history_retention_days, update_manifest_url, llm_provider, llm_base_url, llm_model, llm_api_key, llm_allow_remote_ack`（组织/应用名：`FSA`/`FinancialAudit`；`_reset_to_defaults` 只重置前 5 个非 LLM 键）
