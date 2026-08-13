# 开发日志 (DEV_LOG)

> 本文件记录项目从调研到开发的每一步进展，确保过程可追溯。

---

## 2026-08-07 | Phase 0: 调研与设计

### 完成事项

#### 1. 并行调研 (4 路 librarian)
- **bg_c85e36f4** - 现有项目盘点: 调研 10 个 GitHub/Gitee 开源项目 + 4 个商业软件参考
  - 发现 GAP: 无"离线+开源+CAS专用+确定性+可审计+中小企业Excel"的桌面工具
  - MIT 可复用: AlphaBee(schema分层)、tieout(声明式JSON spec)、malkkiel-FI(跨期比较)
  - 无 License 参考: XuekaiChen(三分校验+外置规则)、Willsgao/audit_engine(三规则引擎+容差)
- **bg_d5509e9c** - 技术栈对比: GUI 框架 + PDF 库
  - GUI 推荐: PySide6 (LGPL, 60-118MB, 2.1s, 52MB, 原生pandas, CJK一流)
  - PDF 推荐: Camelot(MIT) + pdfplumber(MIT) + PaddleOCR(Apache, V2)
  - 排除: PyQt6(GPL), Electron(243MB/184MB), PyMuPDF(AGPL), tabula-py(JRE), pdf2htmlEX(归档)
- **bg_9a55e835** - 规则引擎 + SQLite
  - 所有现成引擎排除 (不支持算术/范式错误/已废弃)
  - 推荐: 自研 ~200行 AST DSL (基于 simpleeval MIT 安全求值器)
  - SQLite: 4MB数据量, WAL模式46万QPS, 绰绰有余
- **bg_e69fd166** - CAS 勾稽规则目录
  - 44 条规则落盘 `cas_gouji_rule_library.json`
  - A表内平衡16 + B表间勾稽14 + C逻辑合理性14
  - 官方准则引用: CAS 30号/31号/18号, 审计准则1313号

#### 2. 初步方案形成
- 技术栈: PySide6 + qfluentwidgets + pandas/openpyxl + simpleeval + SQLite(WAL)
- 架构: 6层 (GUI -> 导入标准化 -> 规则引擎 -> 数据模型 -> SQLite -> Agent预留)

#### 3. 边界决策 (用户确认)
| 决策 | 选择 |
|---|---|
| 许可证 | 开源 MIT |
| MVP范围 | Excel-only + 三大主表 + 规则引擎 |
| PDF时机 | MVP不做, V1做Camelot+pdfplumber |
| Agent时机 | MVP仅预留接口, V1接Ollama |
| 合并/IFRS | MVP只做CAS单体, 预留 |

#### 4. 对抗式审查
- 识别 10 项挑战点，形成 10 项补充清单
- 关键发现:
  - PyMuPDF(AGPL)与MIT项目不兼容 -> PDF改用Camelot+pdfplumber
  - CAS科目映射系统缺失 -> 新增核心组件
  - qfluentwidgets解决"现代美观UI"需求
  - "宁可漏报不可误报" -> 宽容容差 + 保守规则

#### 5. 文档输出
- `design.md` - 完整设计文档 (6项任务 + 对抗审查 + 风险登记册)
- `project_structure.md` - 项目结构 + 模块接口 + 开发计划 + 依赖清单
- `cas_gouji_rule_library.json` - CAS默认规则库 (44条)
- `DEV_LOG.md` - 本文件
- `LICENSE` - MIT
- `.gitignore` - Python
- `README.md` - 项目说明

### 关键决策记录

| # | 决策 | 理由 | 替代方案(已排除) |
|---|---|---|---|
| D01 | PySide6 (非PyQt6) | LGPL免费; PyQt6 GPL会感染MIT项目 | PyQt6(license) |
| D02 | PySide6 (非Tauri/Electron) | pandas原生in-process; 无IPC开销 | Tauri/Electron(IPC重) |
| D03 | qfluentwidgets (非手写QSS) | Fluent Design全套组件, 减少UI维护负担 | 手写QSS(维护成本高) |
| D04 | Camelot+pdfplumber (非PyMuPDF) | MIT兼容; PyMuPDF是AGPL | PyMuPDF(AGPL) |
| D05 | 自研规则引擎 (非现成库) | 所有现成库不支持算术/范式错误/废弃 | python-rule-engine等 |
| D06 | simpleeval (非eval) | AST白名单安全求值; 非eval() | eval(不安全) |
| D07 | SQLite+WAL (非PostgreSQL) | 4MB数据量无需服务器; WAL支持并发读写 | PostgreSQL(过度设计) |
| D08 | PyInstaller (首选) / Nuitka (可选) | onedir启动快; Nuitka更小但编译慢 | - |
| D09 | Ollama优先 (云端可选) | 财务数据敏感, 必须支持完全离线 | 仅云端(隐私风险) |
| D10 | CAS科目字典+别名映射 | 桥接企业科目名与规则标准名 | 无映射(规则无法执行) |

### 待办 (下一步)

- [x] 初始化 git 仓库 + GitHub 仓库 (已完成: commit acd14a2, pushed to origin/main)
- [ ] 创建项目骨架 (src/fsa/ 目录结构)
- [ ] MVP Week 1-2: 数据模型 + SQLite schema + init_db.py
- [ ] MVP Week 2-3: ExcelImporter + ReportTypeDetector + AccountMapper
- [ ] MVP Week 3-4: 规则引擎 (parser+evaluator+runner) + 44规则导入
- [ ] MVP Week 4-5: GUI 主框架 (qfluentwidgets)
- [ ] MVP Week 5-6: 结果看板 + 差异追溯 + Excel导出
- [ ] MVP Week 6-7: 集成测试 + **Inno Setup 安装器** (build_installer.iss)
- [ ] MVP Week 7-8: 示例文件 + 文档

### 反思

**做得好的**:
- 并行调研节省了大量时间 (4路同时跑, 7-9分钟完成)
- 对抗式审查发现了 PyMuPDF AGPL 兼容性问题 (在编码前)
- CAS规则库直接落盘 JSON, 可直接用于 MVP

**待改进**:
- CAS科目别名字典尚未创建 (MVP Week 2 补)
- 示例 Excel 文件尚未准备 (MVP Week 7 补)
- simpleeval 中文标识符兼容性未验证 (MVP Week 3 首先验证)

---

## 2026-08-07 | Phase 0.5: 新增需求设计 (部署更新 + 报表生成)

### 用户需求

#### 需求 1: 部署与自动更新
- 同事电脑一般为 Win10, 需要安装版 (非便携版)
- 支持指定路径安装
- 开发者更新后, 用户启动软件时弹出更新提示
- 内网环境, 通过 Git 工作流发布

#### 需求 2: 报表自动生成
- 从余额表 + 序时账自动生成三大财务报表
- 生成后自动执行勾稽校验
- 输出审计底稿

### 设计方案

#### 部署与更新 (design.md 附录 A)
- **打包**: PyInstaller --onedir -> Inno Setup 安装器 (自定义路径/桌面快捷方式/卸载器)
- **更新机制**: 内网共享目录放置 `version.json` (版本号+下载URL+SHA256+更新说明)
- **启动检查**: 应用启动时异步读取内网 `version.json`, 有新版本则弹窗提示
- **更新流程**: 用户确认 -> 下载安装包 -> SHA256校验 -> 静默安装 (Inno Setup /SILENT) -> 重启
- **Git工作流**: main分支发布release, tag标记版本, CI/CD或手动构建安装包推送到内网

#### 报表自动生成 (design.md 附录 B)
- **资产负债表+利润表**: 从余额表生成 (科目->报表项目映射, CAS标准映射表~200条)
- **现金流量表**: 从序时账生成 (直接法, 筛选现金类科目分录, 按对方科目分类)
- **生成+校验一体化**: 生成后自动运行44条勾稽规则, 一份Excel输出 (报表+底稿+校验结果)
- **审计底稿**: 科目到报表项目映射底稿 + 现金流分类底稿 (可追溯)

### 文档更新

| 文件 | 更新内容 |
|---|---|
| `design.md` | 新增附录 A (部署与更新) + 附录 B (报表自动生成) |
| `project_structure.md` | 目录树新增 `core/generator/` + `core/updater/`; 脚本新增 `build_installer.iss` + `publish.py`; 新增模块接口 §2.5 生成层 + §2.6 更新层; 开发计划调整 (MVP+安装器, V1.0+自动更新, V1.5+报表生成, V2.0+间接法CF); 依赖新增 Inno Setup |
| `README.md` | 核心功能新增报表自动生成+自动更新; 开发路线更新 |
| `scripts/build_installer.iss` | 新建: Inno Setup 安装器模板脚本 |

### 关键决策记录 (续)

| # | 决策 | 理由 | 替代方案(已排除) |
|---|---|---|---|
| D11 | Inno Setup (非NSIS/便携版) | Win10成熟稳定, 免费, 支持自定义路径/快捷方式/卸载; 用户要求安装版 | 便携版(用户否决), NSIS(脚本更复杂) |
| D12 | 内网共享+version.json (非HTTP服务器) | 内网无专用服务器, 文件共享最简单; 无需额外部署 | HTTP更新服务器(过度设计) |
| D13 | SHA256校验+静默安装 | 确保下载完整性; Inno Setup /SILENT 原生支持 | 无校验(安全风险) |
| D14 | 余额表->BS/IS, 序时账->CF | BS/IS是时点数据(余额表), CF是流量数据(需要明细); CAS标准做法 | 全部从余额表(CF无法生成) |
| D15 | 科目映射可自定义覆盖 | 企业科目编码不同, 需支持自定义; 默认映射表覆盖CAS标准 | 硬编码(不灵活) |
| D16 | 生成后自动校验 (生成+校验一体化) | 用户一键获得"报表+校验结果", 无需手动导入再校验 | 分离(多一步操作) |

### 待办 (更新)

- [x] 初始化 git 仓库 + GitHub 仓库
- [x] 新增需求设计文档 (design.md 附录 A + B)
- [x] 更新 project_structure.md (新模块+接口+计划)
- [x] 创建 build_installer.iss 模板
- [ ] 提交并推送到 GitHub
- [ ] 创建项目骨架 (src/fsa/ 目录结构)
- [ ] MVP Week 1-2: 数据模型 + SQLite schema + init_db.py

---

## 2026-08-08 | Phase 1: MVP 核心开发

### 完成事项

#### 1. 核心校验引擎 (TDD, commit 9f3d406)
- **数据模型层** (`core/models/`):
  - `Report` - 一张财务报表（含多个 ReportItem）
  - `ReportItem` - 报表项目（key/名称/金额/行号）
  - `ReconciliationRule` - 勾稽规则（ID/公式/容差/描述/适用报表）
  - `ValidationResult` - 校验结果（通过/不通过/差额/错误信息/`errored` 标记）
  - `ValidationSummary` - 校验汇总（总数/通过/失败/出错/跳过/成功率/失败明细）
- **引擎层** (`core/engine/`):
  - `comparator.py` - 容差比较器（`abs(a-b) <= tolerance`，不使用 `==`）
  - `evaluator.py` - 基于 simpleeval 的安全表达式求值器
  - `runner.py` - 规则执行器（接收 Report 对象 -> 输出 ValidationResult）
  - `rule_loader.py` - JSON -> ReconciliationRule 对象加载器
  - `registry.py` - 规则注册表（启用/禁用/容差调整/筛选）
- **异常体系** (`core/exceptions.py`):
  - `FSAError`（根异常）-> `MissingItemError`、`DuplicateItemError`、`FormulaParseError`、`EvaluationError`、`InvalidToleranceError`
- **测试**: 按 AAA 模式编写，覆盖正常/边界/零值/负值/缺失/None/大数/浮点精度

#### 2. 设计语言文档 + UI Demo (commit 5201f89, 67e5a2d)
- `DESIGN_SYSTEM.md` - 靛蓝品牌色、HarmonyOS Sans SC 字体、明暗主题令牌系统
- `demo/demo.html` v3 - 5 页完整原型（数据导入/审计底稿/规则管理/历史记录/系统设置 + AI 诊断面板）

#### 3. Excel 导入器 + 规则加载器 (commit facfd7f)
- `importer/name_mapper.py` - 100+ 中文科目名 -> snake_case key 映射
- `importer/excel_reader.py` - openpyxl 读取 Excel 工作表
- `importer/report_identifier.py` - 根据 Sheet 名识别报表类型
- `importer/item_extractor.py` - 提取报表项目（项目列 + 金额列）
- `importer/importer.py` - ImportService 编排模块，输出 Report 对象
- `engine/rule_loader.py` + `engine/registry.py` - JSON 加载 + 注册表管理

#### 4. 校验编排服务 (commit 9c80749)
- `ValidationService` - 编排 ImportService + RuleRegistry + RuleRunner -> ValidationSummary
- 按可用报表类型过滤规则（缺少必需报表的规则自动跳过）
- 捕获 FSAError + 未预期异常 -> 转为 errored 结果
- **299 测试全部通过, 覆盖率 93.95%**

#### 5. PySide6 GUI 初版 (commit 5ccbf15)
- `theme.py` - 设计令牌映射
- `app_state.py` - 共享状态 + Qt 信号
- `main_window.py` - FluentWindow 三页导航 + Ctrl+D 主题切换
- `pages/import_page.py` - 拖拽导入 + 校验 + 结果卡片
- `pages/rule_page.py` - 44 条规则表格 + 启用/禁用
- `pages/settings_page.py` - 期间输入 + 深色模式
- `widgets/drop_zone.py` - Excel 拖放区域
- `widgets/result_card.py` - 校验结果卡片
- `app.py` + `__main__.py` - 入口

#### 6. 端到端验证
- 测试 Excel（BS 13项 + IS 13项 + CF 7项）完整跑通
- 36 条规则执行: 6 通过, 0 失败, 30 出错, 8 跳过
- 6 条通过规则: BS-BAL-001~003, IS-BAL-002~003, CF-BAL-004

#### 7. AGENTS.md 新增 P6 中文输出原则 (commit 80a0541)

### 质量指标
| 指标 | 数值 |
|------|------|
| 测试总数 | 299 通过 |
| 代码覆盖率 | 93.95% |
| Git 提交 | 8 个 (main 分支) |
| 规则加载 | 44 条 CAS 规则 |

---

## 2026-08-08 | 用户审查反馈与问题诊断

### 用户反馈 (6 项问题)

#### 问题 1: GUI 与 Demo 完全不符
- **诊断**: 兼具设计问题和实现问题，但主要是实现差距。
- Demo HTML 包含: 5 页（数据导入/审计底稿/规则管理/历史记录/系统设置）、自定义侧边栏（logo/分区标签/底部版本）、顶栏（标题/副标题/操作按钮组）、4 列汇总卡片、筛选标签栏（全部/错误/警告/通过）、可展开规则卡片（含追溯表 + AI 诊断按钮）、审计底稿表格页、历史记录页、完整设置页、AI 助手浮动按钮 + 滑出抽屉面板。
- 实际 GUI 仅有: 3 页（导入/规则/设置）、FluentWindow 默认导航（无 logo/分区/底部）、无顶栏、无汇总卡片（仅文字标签）、无筛选标签、基础 ResultCard（无展开/无追溯/无 AI 按钮）、无审计底稿页、无历史记录页、无 AI 面板。
- **结论**: GUI 实现是最低限度脚手架，完全没有遵循 Demo 设计。

#### 问题 2: 测试可行性差
- **诊断**: 现有测试仅从代码角度验证规则引擎能执行，但测试数据（13+13+7 个项目）远不足以覆盖 44 条规则所需的全部变量。30 条规则出错正是因为测试数据缺少必要科目。
- **需要**: 真实财务场景的测试数据，覆盖更多科目变量，使更多规则能实际执行而非报错。

#### 问题 3: 校验概览和明细卡片设计过于"AI 味"
- **诊断**: Demo 中的汇总卡片使用了 28px 大号字体 + 渐变色 + sparkles 图标，与"克制的专业感"设计哲学矛盾。
- **需要**: 更克制、更像真实财务软件的设计（参考用友、金蝶的表格/数据风格，去除渐变和花哨元素）。

#### 问题 4: AI 助手抽屉需改进
- **当前**: 固定 420px 宽，无拖拽缩放，点击外部不收起。
- **需要**:
  1. 可左右拖动调整宽度
  2. 点击其他区域自动收起
  3. 再点击浮动按钮打开
  4. 问答内容持久化（SQLite 或 JSON）
  5. 跨页面保持问答上下文
  6. 内网同步：问答内容同步到更新文件夹，可做指导参考

#### 问题 5: 需要更新设计方案文档
- **需要**: 所有未实现待办和规划事项全部更新到设计方案中，后续逐步实现。
- **需要**: 不断更新完成事项和待办事项，防止上下文过长遗忘。

#### 问题 6: LR-* 规则公式不支持
- 约 14 条逻辑合理性规则使用范围/条件表达式（如 `0 <= x <= 1`），simpleeval 求值器不支持。
- 需要扩展 DSL 或新增求值策略。

---

## 全局待办清单 (持续更新)

> 每次开发会话结束时更新此清单的状态。
> `[x]` = 已完成 | `[ ]` = 待办 | `[~]` = 进行中

### A. GUI 重建 (优先级: 高)

- [x] A1. 重新设计 Demo HTML v4 - 去除"AI 味"，校验概览/明细卡片改为更克制的财务风格 (commit 0feb21f)
- [x] A2. 实现自定义侧边栏（logo + 分区标签 + 底部版本信息）(commit 9a048c4)
- [x] A3. 实现顶栏组件（页面标题 + 副标题 + 操作按钮组：主题切换/重置/执行校验/导出底稿）(commit 9a048c4)
- [x] A4. 实现汇总卡片组件（4 列：通过/错误/警告/总数，克制设计 - 22px数字+圆点指示器）(commit 9a048c4)
- [x] A5. 实现筛选标签栏（全部/不通过/异常/通过，带计数）
- [x] A6. 重建校验明细卡片（白底+3px左边框+浅色badge+AI诊断按钮）(commit 9a048c4+后续)
- [x] A7. 新增审计底稿页面（表格形式展示全部校验结果 + 导出按钮 + 空状态）
- [x] A8. 新增历史记录页面（历史卡片 + 空状态提示）
- [x] A9. 完善系统设置页面（外观主题/校验参数/数据存储/关于 - 4 分区）
- [x] A10. 主题系统重建 - 正确实现明暗双套配色 (commit 9a048c4)

### B. AI 助手抽屉 (优先级: 高)

- [x] B1. 实现可拖拽缩放的抽屉面板（4px拖拽手柄, 280-600px）(commit 9a048c4)
- [x] B2. 点击抽屉外区域自动收起，再点击浮动按钮打开 (commit 9a048c4)
- [x] B3. 问答内容持久化（SQLite 表存储对话记录）
- [x] B4. 跨页面保持问答上下文（全局单例面板，不随页面切换消失）(commit 9a048c4)
- [ ] B5. 内网同步：问答内容导出/同步到更新文件夹（UI 已实现，功能待接入）
- [x] B6. 每张校验卡片独立 AI 诊断按钮 -> 打开抽屉并预填上下文 (commit 9a048c4+后续)

### C. 核心功能补全 (优先级: 中)

- [x] C1. SQLite 持久化层（存储报表、校验结果、校验历史）
- [x] C2. Excel 导出器（审计底稿导出，含公式追溯）
- [x] C3. LR-* 规则公式扩展（支持范围/条件表达式）
- [x] C4. 测试数据丰富化（真实财务场景 Excel fixture + 24 条端到端集成测试）

### D. 规划后续功能 (优先级: 低)

- [x] D1. PDF 导入 (V1)
- [ ] D2. 报表自动生成 (V1.5)
- [~] D3. Ollama AI 诊断引擎接入 (V1, 客户端已实现, 本地服务未实测)
- [x] D4. 自动更新模块 (V1.0)
- [~] D5. Inno Setup 安装器 (脚本已提交, 干净机器编译安装未验证)
- [ ] D6. 间接法现金流量表 (V2.0)
- [ ] D7. 合并报表 (V2.0)
- [ ] D8. IFRS 支持 (V2.0)

### E. 已完成事项

- [x] E1. Phase 0 调研与设计 (commit acd14a2)
- [x] E2. Phase 0.5 部署+生成需求设计 (commit 219ab59)
- [x] E3. 核心校验引擎 - models + engine + exceptions (commit 9f3d406)
- [x] E4. 设计语言文档 + UI Demo v2/v3 (commit 5201f89, 67e5a2d)
- [x] E5. Excel 导入器 + 规则加载器/注册表 (commit facfd7f)
- [x] E6. 校验编排服务 ValidationService (commit 9c80749)
- [x] E7. PySide6 GUI 初版 (commit 5ccbf15)
- [x] E8. AGENTS.md 新增 P6 中文输出原则 (commit 80a0541)
- [x] E9. 端到端验证通过（Excel -> 导入 -> 校验 -> 结果展示）
- [x] E10. Demo HTML v4 重新设计 - 去除 AI 味 + AI 抽屉改进 (commit 0feb21f)
- [x] E11. DESIGN_SYSTEM.md 新增 S14 设计修正 + S15 AI 抽屉规范 (commit 0feb21f)
- [x] E12. GUI 架构重建 - QMainWindow + 自定义侧边栏/顶栏/AI抽屉/汇总卡片 (commit 9a048c4)
- [x] E13. 校验明细卡片重建 - 白底+3px边框+AI诊断按钮 (commit 后续)
- [x] E14. 299测试全通过 + 冒烟测试通过 (GUI重建后验证)
- [x] E15. 规则管理页面重建 - 搜索框+分类筛选标签+规则卡片+启用开关
- [x] E16. 审计底稿页面 - 表格展示校验结果+导出按钮+空状态
- [x] E17. 历史记录页面 - 历史卡片+空状态提示
- [x] E18. 系统设置页面重建 - 外观主题/校验参数/数据存储/关于 4分区
- [x] E19. 侧边栏 set_active_nav 修复 - 程序化切换时正确触发页面跳转
- [x] E20. 全部5个页面接入 MainWindow + 冒烟测试通过 (299 tests pass)
- [x] E21. 导入页筛选标签栏 - 全部/不通过/异常/通过 4个带计数标签 + 点击筛选
- [x] E22. 真实财务场景 Excel fixture - 三大表 47 个科目, 数据内部一致
- [x] E23. 端到端集成测试 24 条 - 导入/校验/数据一致性全覆盖 (323 tests pass)
- [x] E24. SQLite 持久化层 - Database+HistoryRepo+ChatRepo+58条测试+GUI全接线 (381 tests pass)

---

*日志格式: 每次开发会话记录: 完成事项 + 决策 + 反思 + 下一步*
*待办清单: 每次会话结束时更新 [x]/[ ] 状态，防止上下文丢失*

---

## 2026-08-13 | 导入层通用化适配（feat/importer-adaptability）

### 目标

不针对某一家企业的报表做硬编码，而是按标准报表形态强化 Excel 导入的通用适配能力，
容忍行列位置变动与项目名中的多余字符。

### 完成事项

- `excel_reader` 重写为矩阵式统一读取：
  - 支持 `.xlsx`（openpyxl）与 `.xls`（pandas + xlrd）
  - 表头行自动定位（含标题行、无「项目」列、金额关键词回退）
  - 捕获连续多层表头 `header_rows`（供权益变动表矩阵解析）
  - 重复列名自动去重（如左右两栏的「期末余额」→「期末余额#2」）
- `item_extractor` 通用化：
  - 金额列识别：标准列名 → 期间列模式（2026年1-6月 / 日期序列号）→ 纯数值列回退
  - 资产负债表左右双栏同时提取
  - 项目名统一走 `name_mapper.clean_name`
- `name_mapper` 新增行尾括号注释剥离（净利润（净亏损以“-”号填列）等）
- `sce_extractor` 支持多层表头组件映射
- 依赖声明补齐：`pdfplumber`、`xlrd` 进入 pyproject；`xlwt` 进入 dev
- 文档对齐：README 快速开始与规则条数、AGENTS 依赖清单、HANDOFF/DEV_LOG 状态

### 验证

- `tests/importer` 222 个测试通过（新增双栏、期间列、后缀清洗、多层表头、.xls 用例）
- 非 GUI 测试 607 个通过（3 个 GUI 用例因本机缺 PySide6/pytest-qt 未收集）
- 茅台/格力 2023 年报回归：导入项目数与校验结果不变（0 fail / 0 error）

### 下一步

- Excel COM 读取适配器（DLP 加密环境的导入通道）
- 余额表/序时账/现金流量明细数据模型（附表 2）
- 用真实杰为数据做端到端回归并固化为 fixture

---

## 2026-08-13 | Excel COM 读取适配器（feat/importer-adaptability）

### 完成事项

- `excel_reader.read_excel_com`：通过 pywin32 启动隐藏 Excel 读取工作表，
  复用 `_matrix_to_raw` 的通用表头/多行表头/去重逻辑
- `read_excel` 增加 `use_com` 参数；常规读取失败（BadZipFile/XLRDError 等，
  即 DLP 密文）时自动回退到 COM，并把两类失败统一为中文 FSAError
- 依赖声明：pywin32 进入 pyproject；AGENTS 依赖清单登记
- 测试：`tests/importer/test_excel_reader_com.py`（环境守卫：无 pywin32/Excel 时跳过）

### 端到端验证（真实 DLP 加密文件）

```text
附表1（2026.06，加密 .xlsx）
  openpyxl 失败(File is not a zip file) -> 自动回退 Excel COM -> 读取 5 个工作表
  识别 4 张报表: BS 23 项 / IS 15 项 / CF 21 项 / SCE 15 项
  规则: 37 条, 执行 25, 通过 18, 不通过 7, 异常 0, 跳过 12
  其中 7 条不通过为真实经营信号（收入同比 -90%、流动比率 0.70 等），
  SCE-BAL-002 属单体报表无"归属于母公司权益"的规则适用性瑕疵，待规则层修正。
```

---

## 2026-08-13 | 明细数据模型与 L2 勾稽检查（feat/importer-adaptability）

### 完成事项

- 明细模型 `core/models/detail.py`: TrialBalanceRow / JournalRow / CashFlowDetailRow / DetailDataset
- 明细导入器 `core/importer/detail_importer.py`: 按表头识别余额表/序时账/现金流明细，
  按"本月 / 1-本月"分流（复用 Excel COM 自动回退）
- L2 检查函数 `core/engine/detail_checks.py`:
  - JNL-BAL-001 序时账逐凭证借贷平衡
  - CF-DTL-001 现金流量明细各项目合计 = 现金流量表主表
  - CF-JNL-001 现金流明细 = 序时账现金等价物科目净变动（口径可配置）
  - TB-BS-001 余额表期末余额 = 资产负债表项目（科目映射可配置）
- 编排服务 `services/detail_validation_service.py` + DetailCheckConfig
- 测试: 明细检查 7 例 + 导入器 2 例；全量非 GUI 617 通过

### 真实数据端到端（加密附表1+附表2）

```text
明细: 余额表 1600 行 / 序时账 4847 行 / 现金流明细 307 行
明细校验: 执行 17, 通过 12, 不通过 3, 异常 2, 跳过 0
真实差异:
  CF 投资所支付的现金 明细 106,730,000 vs 主表 121,730,000（差 15,000,000）
  应收账款 余额表 655,024 vs 报表 653,023（差 2,001，重分类/坏账待解释）
  应付账款 余额表 -7,497 vs 报表 559,155.44（重分类所致，待按明细口径配置）
已通过: 序时账 67 凭证借贷平衡、现金流明细=序时账(1002口径)、货币资金 1002+1012 一致
```

---

## 2026-08-13 | L4 现金流选择正确性检查（feat/importer-adaptability）

### 完成事项

- 规则库 `core/engine/cash_flow_rules.py`: 8 条常见现金流项目 ↔ 对方科目规则
- 检查函数 `core/engine/cash_flow_checks.py`:
  - CF-CLS-001~008 凭证级分类复核（保守提示，供人工确认）
  - CF-CLS-901 现金流明细覆盖率（有现金变动但未指定项目的凭证）
  - 项目名「所」字差异容错（投资所支付 ↔ 投资支付）
- 接入 DetailValidationService；测试 5 例（含「所」字变体）

### 真实数据验证（加密附表 2）

```text
覆盖率: 所有现金凭证均已指定现金流项目 (通过)
分类复核: 销售收款/采购付款/职工薪酬/税费 通过
          收回投资 17 张凭证可疑（对方科目 1012 理财/6111 收益等，需按公司口径复核）
          投资支付 12 张凭证可疑（同上）
说明: 默认规则不含 1012 理财科目，提示即"该口径需要主体配置确认"，
      符合宁可漏报不可误报的复核式设计。
```

---

## 2026-08-13 | 附表3 往来重分类检查（feat/importer-adaptability）

### 完成事项

- 明细模型新增 ReclassificationRow；导入器按表头识别往来重分类明细
- `core/engine/reclassification_checks.py`:
  - RC-001 负数重分类规则（负数转正 + 科目落到对应往来科目）
  - RC-002 重分类后各往来科目合计 = 资产负债表项目
- 修复 excel_reader 多层表头捕获误吞数据行的问题（序号列为空且含数值时停止）
- 测试: 重分类检查 5 例 + 表头回归 1 例

### 真实数据验证（加密附表3 + 附表1）

```text
重分类明细 19 行（工作表其余为空白格式行）
RC-001: 通过
RC-002: 预收款项/应付账款/预付款项/其他应付款 与资产负债表一致
        应收账款 +2,021、其他应收款 +3,389.82 差异，合计恰为利润表
  信用减值损失 5,410.82 → 系坏账准备口径，需人工确认（已写入提示语）
```

---

## 2026-08-13 | 附表4/5/6 检查（feat/importer-adaptability）

### 完成事项

- 明细模型新增 RelatedPartyPurchaseRow / SalesDetailRow / InternalCashFlowRow，
  DetailDataset 增加 merge 方法（六表一次导入合并）
- 导入器按表头识别三张附表并解析
- `core/engine/supplementary_checks.py`:
  - RP-001 关联方采购总金额 = 成本/费用分类合计
  - SAL-001 销售收入成本明细一致性（成本构成缺失时跳过，仅核毛利率）
  - SAL-002 销售明细收入/成本合计 = 利润表
  - ICF-001 内部现金流各项目合计 ≤ 主表现金流量表项目
- 测试: 附表4/5/6 检查 7 例 + 导入器扩展

### 真实六表端到端（加密文件，全自动）

```text
明细合并: 余额表 1600 / 序时账 4847 / 现金流明细 307 / 重分类 19 /
          关联方采购 5 / 销售明细 32 / 内部现金流 8
明细校验: 执行 39, 通过 29, 不通过 8, 异常 2, 跳过 0
已定位差异（需财务确认）:
  CF 投资支付 明细 1.067 亿 vs 主表 1.217 亿（差 1,500 万）
  应收账款/其他应收款 重分类明细与报表差 2,021 / 3,389.82（坏账准备口径）
  应付账款余额表 -7,497 vs 报表 559,155.44（重分类口径）
  内部现金流「收到其他经营现金」9,932,877.64 超主表 7,424,050.44（2,508,827.20）
 现金流分类 29 张凭证待复核（1012 理财口径）
```

---

## 2026-08-13 | GUI 报表包接线（feat/importer-adaptability）

### 完成事项

- `services/package_service.py`: PackageValidationService + merge_summaries，
  主表规则与明细勾稽一次执行、合并为一份 ValidationSummary
- AppState 增加 detail_dataset；DropZone 支持多文件拖入（files_dropped）
- ImportPage 支持一次拖入主表+附表（1~6）：主表去重合并、明细数据集 merge，
  顶栏校验按钮执行合并校验；重置清空明细数据
- 测试: package merge 单测 + GUI 报表包导入端到端测试

### 验证

- 本机安装 PySide6/pytest-qt/PySide6-Fluent-Widgets 后，GUI 测试
  101 通过（6 个设置持久化用例因沙箱注册表权限失败，与代码无关）
- 新增 GUI 用例通过：一次导入主表+明细 → 3 张报表 + 明细数据 → 合并校验

---

## 2026-08-13 | 端到端对抗式审查与修复（feat/importer-adaptability）

### 审查发现与修复

| # | 问题 | 修复 |
|---|---|---|
| 1 | 仅导入主表时明细校验空跑，产生无意义"通过"结果 | DetailDataset.is_empty + PackageValidationService 跳过 |
| 2 | .xls 空白单元格经 pandas 读为 NaN，污染校验结果 | 导入器与提取器统一 NaN→0/None |
| 3 | GUI 多文件导入中单个文件异常会中断整批 | 逐文件捕获 FSAError，只记录失败继续 |
| 4 | 现金流分类规则无对应凭证时提示"复核通过"误导 | 区分"本期无对应凭证"与"复核通过" |
| 5 | ruff 静态检查问题（import 排序/SIM/B007 等） | 全部修复，src/fsa 通过 ruff |

### 审查验证

- ruff: src/fsa 全部通过
- 非 GUI 测试 639 通过、2 跳过；GUI 测试 102 通过
  （6 个设置持久化用例为沙箱注册表权限环境项）
- 真实六表包端到端: 74 项执行、57 通过、15 不通过、2 异常、10 跳过；
  不通过项均为已定位真实差异，无新引入异常

---

## 2026-08-13 | Agent 使用体验优化（feat/importer-adaptability）

### 完成事项

- 诊断引擎为明细层规则新增针对性建议分支：
  JNL-BAL-001 / CF-DTL-001 / CF-JNL-001 / TB-BS-001 / RC-001/002 /
  RP-001 / SAL-001/002 / ICF-001 / CF-CLS-*（并修正 CF-* 分支优先级）
- 知识库新增明细勾稽、现金流分类复核、往来重分类、附表4/5/6 等条目，
  无 LLM 时的回退问答可覆盖新校验能力
- 测试: 新增明细规则建议断言，tests/agent 57 个测试全部通过
