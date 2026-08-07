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

## 后续日志

> MVP 开发阶段的日志将在编码开始后追加。

### [日期] | Phase 1: MVP 开发

*待编码开始后填写*

---

*日志格式: 每次开发会话记录: 完成事项 + 决策 + 反思 + 下一步*
