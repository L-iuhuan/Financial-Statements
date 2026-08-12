# GUI功能完善实现计划

> **目标**: 让PySide6 GUI在功能上达到HTML demo的同等水平

**技术栈**: PySide6, qfluentwidgets, pytest-qt

---

## 文件变更清单

### 新建文件
- `src/fsa/gui/widgets/report_card.py` — 报表卡片组件
- `tests/gui/test_import_page_filters.py` — 筛选逻辑测试
- `tests/gui/test_rule_page.py` — 规则管理页测试
- `tests/gui/test_result_card.py` — 结果卡片trace测试
- `tests/gui/test_agent_fab.py` — FAB角标测试
- `tests/gui/test_settings_page.py` — 设置页测试
- `scripts/verify_w3.py` — W3端到端验证脚本

### 修改文件
- `src/fsa/gui/pages/import_page.py` — ReportCard网格、筛选标签语义、汇总标签
- `src/fsa/gui/widgets/result_card.py` — trace表格、分类标签
- `src/fsa/gui/pages/rule_page.py` — severity标签、容差编辑、禁用视觉
- `src/fsa/gui/pages/settings_page.py` — 跟随系统主题、QSettings持久化
- `src/fsa/gui/pages/audit_page.py` — 打印预览、状态颜色、真实分类
- `src/fsa/gui/widgets/agent_fab.py` — 角标
- `src/fsa/gui/main_window.py` — 角标逻辑、主题持久化
- `src/fsa/gui/app.py` — 启动时应用存储的主题和设置
- `src/fsa/gui/app_state.py` — default_tolerance存储

---

## Task 1: ReportCard组件 + 导入页集成

- [ ] 新建 `report_card.py`: QFrame#ReportCard, icon(QFrame#ReportCardIcon)、名称、状态badge(QFrame#ReportCardStatus)、meta(QFrame#MetaLabel)
- [ ] 修改 `import_page.py`: 用QGridLayout/flow布局替换_reports_info，显示3张ReportCard；导入后隐藏drop_zone和empty_state；reset后恢复
- [ ] Empty state: 添加FluentIcon.SHIELD图标 + "等待导入财务报表" + 提示文本

## Task 2: ResultCard trace表格

- [ ] 修改 `result_card.py` _build_detail: 在formula块后添加QTableWidget (columns: 科目, 金额, 侧, 位置)
- [ ] 从result.trace填充数据；side显示"左"/"右"；位置显示"行{row}·{column}"（row=0时隐藏行号）
- [ ] 在header添加category标签（tertiary颜色）

## Task 3: 规则管理页增强

- [ ] 修改 `rule_page.py` RuleCard: 添加severity QLabel（通过palette着色，objectName+status property+QSS）
- [ ] 保留category/statements meta，添加容差QLineEdit（mono字体, ~80px），editingFinished时调用registry.set_tolerance
- [ ] 禁用视觉: 通过`disabled` dynamic property + QSS规则 `QFrame#RuleCard[disabled="true"] QLabel { color: text_disabled }`

## Task 4: 导入页筛选标签 + 汇总标签

- [ ] 修改筛选标签: 全部 / 错误 / 警告 / 通过
  - 错误 = failed & severity==ERROR（含errored，severity视为ERROR）
  - 警告 = failed & severity in (WARNING, INFO)
  - 通过 = passed
- [ ] 汇总卡片重命名: 通过 / 错误 / 警告 / 规则总数（子标签按demo文案）

## Task 5: 设置页主题持久化

- [ ] 添加"跟随系统"按钮（auto）。Auto模式通过QStyleHints.colorScheme()检测（PySide6 6.5+）
- [ ] QSettings("FSA", "FinancialAudit")存储: theme_mode, default_tolerance, gross_margin_threshold, history_retention_days
- [ ] 容差/阈值/保留天数输入框变更时写入QSettings
- [ ] app.py启动时读取theme_mode应用；将default_tolerance存入AppState
- [ ] main_window._toggle_theme切换时保存显式模式到QSettings

## Task 6: 审计底稿页增强

- [ ] 添加"打印预览"按钮: QPrintPreviewDialog + QTextDocument渲染HTML表格
- [ ] 状态单元格: QTableWidgetItem.setForeground使用palette颜色
- [ ] 分类列: 使用result.category而非rule_id推断

## Task 7: FAB角标

- [ ] 修改 `agent_fab.py`: 添加badge QLabel（error背景、白色文字、圆形、右上角），默认隐藏
- [ ] 添加 `set_badge(visible: bool)` 方法
- [ ] main_window._on_results_ready: 当failed+errored>0时显示角标；抽屉打开/reset时隐藏

## Task 8: 导航活动指示器

- [ ] 检查theme.py QSS: QPushButton#NavItem[active="true"]已有border-left: 3px solid brand_600，已完成

## Task 9: 测试与验证

- [ ] 新建GUI测试: test_import_page_filters.py（筛选语义）
- [ ] test_rule_page.py（容差setter调用）
- [ ] test_result_card.py（trace表格存在性）
- [ ] test_agent_fab.py（角标显示/隐藏）
- [ ] test_settings_page.py（QSettings读写）
- [ ] 新建 scripts/verify_w3.py: offscreen启动、导入真实报表、触发校验、截图、断言
- [ ] 运行 pytest --tb=short -q，确保全部通过
- [ ] 运行 scripts/verify_theme.py，确保不破坏暗色模式
