# AGENTS.md - 财务报表勾稽校验系统 强约束文档

> **每一步开发开始前必须阅读此文档，校准开发方向。**
> 本文档是项目的"宪法"，任何代码变更必须符合以下约束。
> 违反约束的代码不得合并。

---

## 0. 项目原则 (不可妥协)

| # | 原则 | 含义 |
|---|---|---|
| P1 | **宁可漏报不可误报** | 校验结果"通过"必须是确定的；"不通过"允许漏掉。即：容差偏向通过，规则保守。缺数据时规则**跳过**而非误报（见 BS-IS-001「三大主表无此数据时跳过」）。 |
| P2 | **确定性优先** | 所有校验逻辑必须是确定性的、可复现的。同输入同输出，不依赖随机数、时间、网络。 |
| P3 | **可审计可溯源** | 每一条校验结果必须能追溯到：哪条规则、哪个公式、哪些科目、原始数据在哪行哪列（`TraceItem` 含 row/column）。 |
| P4 | **用户是财务人员** | UI 文案用财务术语，不用技术术语。错误信息要告诉用户"哪里出了问题"而非"抛了什么异常"。 |
| P5 | **模块隔离** | 生成、校验、导入、导出各自独立，通过数据模型解耦。校验引擎不知道报表来源。 |
| P6 | **中文输出** | 所有面向用户的输出（总结、报告、状态说明、错误信息）必须以中文呈现。技术代码内部可用英文，但任何交付给用户的内容必须中文。 |

---

## 1. 架构与模块边界

### 1.1 分层架构

```
GUI层 (PySide6/qfluentwidgets)            src/fsa/gui/
    ↓ 用户操作 + 数据
业务层 (导入/校验/导出/编排)              src/fsa/core/, src/fsa/services/
    ↓ 标准数据模型
数据模型层 (Report / ReportItem / ...)    src/fsa/core/models/
    ↓ 对象
持久化层 (SQLite WAL)                      src/fsa/storage/
```

- 上层依赖下层，下层不依赖上层
- 同层模块之间通过数据模型通信，不直接调用
- **禁止跨层调用**：GUI 层不得直接操作 SQLite（经 `storage/` 仓库访问）

### 1.2 实际模块布局与职责边界

源码全部在 `src/fsa/` 下（`pyproject.toml` 的 `tool.setuptools.packages.find` 指向 `src/`）：

| 模块 | 路径 | 职责 | 禁止 |
|---|---|---|---|
| 引擎 | `core/engine/` | 接收 Report -> 输出 ValidationResult；含主表规则与明细勾稽（detail/cash_flow/reclassification/supplementary_checks） | 禁止读取文件、禁止操作 GUI |
| 导入 | `core/importer/` | 读取 Excel/PDF -> 输出 Report；含明细数据导入 | 禁止执行校验逻辑 |
| 导出 | `core/exporter/` | 接收 ValidationResult -> 输出 Excel 审计底稿 | 禁止修改校验结果 |
| 模型 | `core/models/` | Report/ReportItem/ReconciliationRule/ValidationResult/DetailDataset | - |
| 核心公共 | `core/`（顶层） | exceptions(FSAError 根)/version(APP_VERSION)/resources(resource_path)/edition(internal·general 双版本通道+域检查)/logging(日志文件轮转) | 纯工具，无业务规则 |
| 编排 | `services/` | ValidationService / DetailValidationService / PackageValidationService / MultiEntityService / EntityConfig / ProblemPackage(问题包导出) | 编排，不含业务规则 |
| AI助手 | `agent/` | 接收 ValidationResult -> 输出诊断建议（AgentLoop/Debate/LLM + 知识库检索） | 禁止修改校验结果 |
| 存储 | `storage/` | SQLite WAL（history/chat/override 仓库） | - |
| 更新 | `updater/` | 检查版本 + 下载安装（**仅用 stdlib urllib，不依赖 requests**） | 禁止访问业务数据 |
| GUI | `gui/` | PySide6 界面 | 禁止直接操作 SQLite |

> **注意**：不存在 `generator/` 目录——报表自动生成（余额表/序时账->三大报表）是 V1.5 规划，尚未实现。`agent/`、`services/`、`storage/`、`updater/` 是 `src/fsa/` 下的顶层包，不在 `core/` 内。

### 1.3 数据模型作为契约

- `Report` - 一张财务报表（含多个 ReportItem）
- `ReportItem` - 报表项目（key/名称/金额/行号）
- `ReconciliationRule` - 一条勾稽校验规则（ID/公式/容差/描述/适用报表）
- `ValidationResult` - 一条校验结果（含 `errored` 标记 + `trace` 追溯）
- `ValidationContext` - 一次校验运行的上下文（含所有报表）
- `DetailDataset` - 明细数据集（余额表/序时账/现金流明细等六表合并）

**规则引擎的输入永远是 `Report` 对象，不关心来源。** 导入来的 Report 和（未来）生成来的 Report 是同一个类型，校验引擎无法区分。

---

## 2. 开发命令

```bash
# 安装（可编辑 + 开发依赖）
pip install -e ".[dev]"

# 启动桌面应用（入口 src/fsa/__main__.py -> gui.app.main）
python -m fsa

# 测试（pytest 已配 testpaths=tests, pythonpath=src, qt_api=pyside6, 默认跳过 slow 压测）
# 注意: 依赖真实年报 fixture 的用例需先准备 tests/fixtures/real_reports/
# （可再生文件用 tests/fixtures/generate_*.py 重建；真实年报已移出 git，需手动放置，
#  缺失时相关用例以 skipif 跳过而非失败）
python -m pytest                 # 日常全量（1000+ 测试；不含 slow 压测；勿手填数字，以实际收集数为准）
python -m pytest -q              # 安静模式
python -m pytest -m slow         # 耗时压测（test_drawer_stress.py 20 例，改动抽屉/主题/布局或发布前跑）
python -m pytest tests/engine/test_evaluator.py -q   # 单文件
python -m pytest -k "exact_match" -q                  # 按名筛选

# 静态检查（提交前必跑）
python -m ruff check src/        # Lint
python -m mypy src/fsa           # 类型检查（strict 模式）

# 覆盖率（fail_under=90）
python -m pytest --cov=src/fsa --cov-report=term-missing

# 焦点端到端验证脚本（scripts/ 下，非 pytest，各自独立可跑）
python scripts/validate_real_data.py   # 真实年报压测（需先放 fixtures/real_reports/）
python scripts/verify_agent.py         # AgentLoop mock 验证
python scripts/verify_pdf_import.py    # PDF 导入
python scripts/verify_export.py        # 导出
python scripts/verify_ollama.py        # 本地 Ollama 连通
# 其他: verify_{sce,update,diagnosis,theme,w3}.py / ux_shots.py (页面截图)
#       build_real_corpus.py + validate_corpus.py (真实语料构建/校验)
#       update_manifest_whitelist.py (更新清单白名单) / generate_logo.py (图标再生)
#       benchmark_app.py + benchmark_import.py (性能基准，发布前人工跑)
#       collect_cas_sources.py + ingest_knowledge_ocrflow.py (CAS 知识库维护)
# 打包运维: build_installer.ps1 -> sign_build.ps1 (签名) -> smoke_package.ps1 (冒烟)
# （脚本分类与运行约定详见 scripts/AGENTS.md）
```

提交前顺序：`ruff check` -> `mypy` -> `pytest`。

CI（`.github/workflows/ci.yml`，push main/fix/** 与所有 PR 触发）：ubuntu+windows × py3.11/3.12 矩阵跑 ruff+mypy+pytest；**mypy 在 CI 固定 `--python-version 3.12`**（numpy>=2.4 stubs 需 3.12 语法，本地 pyproject 仍为 3.11）；CI lint 范围为 `src tests`；**覆盖率双门槛**--core/services/storage >=90%，整体基线 >=84%（逐步提升至 90%）；package-windows job 以 `build_installer.ps1 -Edition general` 出包上传 artifact。

---

## 3. 代码规范与工具链

### 3.1 Python 版本与类型

- Python 3.11+（`requires-python = ">=3.11"`）
- **全类型注解**：所有函数参数、返回值必须有类型注解
- **禁止** `Any`、`Optional`（用 `X | None` 替代）
- `# type: ignore` 原则上禁止；**唯一例外**：`gui/` 目录内 Qt 交互需要（如 override/method-assign），且必须带具体错误码（如 `# type: ignore[override]`），不得裸写（gui/ 外实例已于 2026-08-16 清零——excel_reader.py COM 回退处已改 `cast`）
- mypy `strict = true`、`warn_return_any = true`--类型不通过即报错

### 3.2 工具链配置（pyproject.toml 实际值）

- **ruff**: `target-version = "py311"`, `line-length = 120`, select `E/F/W/I/UP/B/SIM`, ignore `E501`
  - 注意：`E501`（行过长）被忽略，但仍以 **120 字符**为软上限
- **mypy**: `strict = true`, `python_version = "3.11"`, `warn_return_any = true`, `warn_unused_configs = true`
- **pytest**: `qt_api = "pyside6"`, `pythonpath = ["src"]`（无需手动设 PYTHONPATH）, `addopts = "-v --tb=short -m \"not slow\""`（slow 标记已注册）
- **coverage**: `source = ["src/fsa"]`, `fail_under = 90`, `omit = ["*/tests/*"]`, `show_missing = true`

### 3.3 函数与文件大小（灵活限制）

- 函数体 <= 50 行（不含空行和注释）——硬性约束，超过必须拆分
- 逻辑文件以 **<= 250 行纯代码**为软目标，超过时优先考虑拆分，但不强制
- **豁免**：数据密集型文件不受行数约束（如 `gui/theme.py` 的 QSS 令牌、`importer/name_mapper.py` 的映射表、`engine/thresholds.py` 的行业阈值表）——这类文件的"行数"是数据量而非复杂度
- 非豁免文件超过 **400 行纯代码**时，必须在文件 docstring 中写明不拆分的理由；超过 **600 行**强制拆分

### 3.4 错误处理

- **禁止空 catch**：`except Exception: pass` 是 BUG
- **禁止宽 catch**：catch 具体异常，不 catch `Exception`
- 自定义异常继承自 `FSAError`（`core/exceptions.py` 根异常）：
  `MissingItemError` / `DuplicateItemError` / `FormulaParseError` / `EvaluationError` / `InvalidToleranceError`
- 已知偏差：`OllamaError`/`LLMError`/`UpdateError` 直接继承 `Exception`（历史遗留，见 agent/AGENTS.md）--新代码必须按 FSAError 编写
- 错误信息用中文，面向财务用户

### 3.5 数据精度

- 金额接口使用 `float`（simpleeval 兼容）；**容差比较内部在 Decimal 域执行**（comparator 经 `str()` 转换，避免二进制尾数污染），输入输出保持 float
- 容差比较：`abs(a - b) <= tolerance`，**不用 `==`**（`core/engine/comparator.py`）
- `.xls` 空白单元格经 pandas 读为 NaN--导入器与提取器统一 NaN->0/None，避免污染校验结果

### 3.6 日志与导入

- 使用 `loguru`，不用 `print`
- 日志内容包含上下文（规则ID、报表类型、金额值）
- 标准库优先；禁止 `from X import *`
- 导入顺序：标准库 -> 第三方库 -> 项目内模块

---

## 4. 测试规范

### 4.1 TDD 流程 (强制)

1. 先写失败的测试 -> 2. 写最少代码让测试通过 -> 3. 重构，测试仍通过

### 4.2 测试覆盖要求

每个函数必须覆盖以下场景（`tests/conftest.py` 提供工厂函数 `make_item` / `make_balance_sheet` / `make_rule_bs_bal_001` / `make_context`）：

| 类型 | 示例 |
|---|---|
| 正常路径 | 资产=100, 负债=60, 权益=40 -> 通过 |
| 边界值 | 差额=0.01（等于容差）-> 通过 |
| 边界外 | 差额=0.011（超过容差）-> 不通过 |
| 零值 | 全部为0 -> 通过 |
| 负值 | 资产=-100, 负债=-60, 权益=-40 -> 通过 |
| 缺失数据 | 报表缺少"资产总计" -> 报错 |
| None值 | 某项目金额=None -> 报错 |
| 大数 | 资产=1e15 -> 正确计算 |
| 浮点精度 | 0.1+0.2 != 0.3 但容差内通过 |
| 多个项目 | 同一key有多个item -> 报错或取第一个 |

### 4.3 测试命名与结构

- 命名：`test_<被测函数>_<场景>_<期望结果>`，如 `test_evaluate_diff_over_tolerance_returns_fail`
- 结构：AAA（Arrange / Act / Assert），见 `tests/conftest.py` 工厂函数用法

### 4.4 覆盖率

- 行覆盖率 >= 90%（core/engine 等核心模块目标）；整体基线 84（pyproject `tool.coverage.report.fail_under = 84` 与 CI 一致），core/services/storage ≥90% 由 CI 单独门禁
- 关键模块（`core/engine/`）覆盖率 100%

---

## 5. 命名与公式

| 类型 | 风格 | 示例 |
|---|---|---|
| 类 | PascalCase | `ReportItem`, `ValidationResult` |
| 函数/方法/变量 | snake_case | `get_amount`, `asset_total` |
| 常量/枚举值 | UPPER_SNAKE_CASE | `DEFAULT_TOLERANCE`, `BALANCE_SHEET`, `EXACT` |
| 文件 | snake_case.py | `report.py`, `evaluator.py` |
| 测试文件 | test_<被测模块>.py | `test_report.py`, `test_evaluator.py` |
| 规则ID | 大写-数字 | `BS-BAL-001` |

### 5.1 变量名与公式

规则公式中的变量名使用 **snake_case 英文**（`ReportItem.key` 与公式变量名一一对应）：

- `asset_total`（资产总计）、`liability_total`（负债合计）、`equity_total`（所有者权益合计）、`net_profit`（净利润）
- 双金额列引擎：期末/期初用 `_ending` / `_beginning` 后缀（如 `revenue_beginning`）
- 现金流附注用 `cf_notes_` 前缀；权益变动表用 `sce_` 前缀

规则库 `cas_gouji_rule_library.json`（v1.3.0，**42 条**）：A-表内平衡 / B-表间勾稽 / C-逻辑合理性。

---

## 6. 依赖策略

### 6.1 许可证策略

**本软件仅供内部使用，允许商业许可依赖。** 核心引擎（`core/engine/`、`core/models/`）仅用开源依赖（MIT/BSD/Apache/LGPL），保证可移植；GUI/数据处理/工具允许商业许可。

> 若将来开源，所有商业依赖需替换为开源替代。

### 6.2 当前依赖清单（以 pyproject.toml 为准）

| 依赖 | 版本约束 | 许可证 | 用途 |
|---|---|---|---|
| PySide6 | >=6.7,<7 | LGPL | GUI 框架 |
| PySide6-Fluent-Widgets | >=1.0 | LGPL | Fluent Design 组件 |
| pandas | >=2.2,<3 | BSD | 数据处理 |
| openpyxl | >=3.1,<4 | MIT | Excel 读写 |
| xlrd | >=2.0,<3 | BSD | 旧版 .xls 读取（pandas 引擎） |
| pywin32 | >=306 (仅Windows) | PSF | Excel COM 读取（DLP 加密环境回退） |
| pdfplumber | >=0.11,<1 | MIT | PDF 表格提取 |
| simpleeval | >=1.0 | MIT | 安全表达式求值 |
| loguru | >=0.7 | MIT | 日志 |

> **sqlite3** 为标准库，无需声明。
> **不依赖 `requests`**--updater 与 agent 的 HTTP 均用 stdlib `urllib`（保护打包体积）。
> **不依赖 `camelot-py`**--PDF 仅用 pdfplumber。

### 6.3 开发依赖

| 依赖 | 用途 |
|---|---|
| pytest / pytest-qt / pytest-cov | 测试（qt_api=pyside6） |
| ruff | Linter |
| mypy | 类型检查（strict） |
| xlwt >=1.3,<2 | 测试中生成 .xls 文件 |

### 6.4 新增依赖流程

1. 设计文档记录理由 2. 确认许可证 3. 在 pyproject.toml 声明 4. 能用标准库解决的不引入第三方

---

## 7. 环境与打包

### 7.1 DLP 加密环境（关键）

公司 DLP（透明加密）环境下 openpyxl/xlrd 无法读取加密 .xlsx。`excel_reader.read_excel_com` 通过 pywin32 启动隐藏 Excel 透明解密读取，**常规读取失败时自动回退**（`BadZipFile`/`XLRDError` 即密文）。两类失败统一为中文 `FSAError`。

### 7.2 Git 推送

**推送用 SSH**（`git@github.com:...`），国内网络下 HTTPS 连不通。新机器需生成 SSH 密钥并加到 GitHub。

### 7.3 打包

```bash
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
```

- 流程：构建期写入版本通道 `src/fsa/core/_edition_override.py` -> 清理 -> PyInstaller（`fsa.spec`，onedir，约 225MB——已剔除环境泄漏包与未用 Qt DLL/非中文翻译；**所有 .ps1 必须 UTF-8 带 BOM**，否则 PS 5.1 解析失败）-> Inno Setup 编译安装器 -> （可选）签名；finally 删除 `_edition_override.py` 防误提交
- 参数：`-Edition general|internal`（内部版要求计算机入域+域名白名单，安装包名加"_内部版"后缀）、`-DomainWhitelist`、`-UpdateUrl`、`-SignThumbprint`
- **Inno Setup 6 需单独安装**才能编译安装器；未安装时脚本只出 exe，跳过安装器
- 配置：根目录 `fsa.spec` + `installer.iss`；中文语言文件在 `Languages/`
- 配套脚本：`sign_build.ps1`（Authenticode 签名，用法见 docs/RELEASE_AND_SIGNING.md）、`smoke_package.ps1`（打包冒烟：启动 exe 确认存活 + SQLite 已建；内部版须在入域机器上跑）

### 7.4 LLM / Agent

- Provider 自动推断：URL 含 `localhost:11434` -> Ollama；含 `/v1` -> OpenAI 兼容
- 在线测试用环境变量 `DEEPSEEK_API_KEY`（DeepSeek API，OpenAI 兼容）
- 公司本地 GLM 端点已联调通过；**本地 Ollama 未实测**
- 无 LLM 可用时回退规则化诊断（不影响核心校验）
- AgentLoop 在后台线程运行（LLM 长响应不冻结 UI）
- CAS 知识库：内置条目 + `resources/knowledge/` 外部文档（CAS 准则原文 + 陈奕蔚答疑，由 `scripts/collect_cas_sources.py` / `ingest_knowledge_ocrflow.py` 维护）；**打包版不含外部知识文档**（fsa.spec 未收录该目录）

### 7.5 GUI 测试环境

- GUI 测试需安装 PySide6 + pytest-qt + PySide6-Fluent-Widgets
- 约 6 个设置持久化用例在沙箱环境因注册表权限失败--属环境问题，与代码无关

---

## 8. Git 规范

- 提交信息：`<type>: <description>`，type = feat | fix | test | refactor | docs | chore | build
- 分支：`main`（稳定，可发布）/ `dev`（开发主干）/ `feat/<feature>` / `fix/<issue>`（修复分支）

---

## 9. 当前范围与边界

**已实现（v0.4.1）**：

- Excel (.xlsx/.xls) 三大主表导入（含表头自动定位/BS双栏/期间列模式/.xls 走 pandas+xlrd）
- PDF 导入（pdfplumber）
- 所有者权益变动表 SCE（矩阵解析）
- 明细数据六表模型 + 勾稽检查（L2 凭证平衡/余额表/现金流明细；L4 现金流分类复核；附表3 重分类；附表4/5/6 关联方/销售/内部现金流）
- 42 条 CAS 勾稽规则（v1.3.0），真实年报压测 0 失败 0 异常
- Excel 审计底稿导出（汇总+明细+科目追溯+底稿说明四表，含源文件 SHA256 留痕）
- Agent 诊断（AgentLoop + DebateEngine + 规则化兜底，Ollama/OpenAI 兼容）
- SQLite WAL 持久化（历史/会话/容差覆写）+ QSettings
- 自动更新（内网 version.json + SHA256 + 静默安装）
- 双版本通道（internal 内部版：入域检查+域名白名单 / general 通用版；构建期固化 `_edition_override.py`）
- PyInstaller 打包 + Inno Setup 安装器 + Authenticode 签名 + 打包冒烟测试
- GitHub Actions CI（双 OS × 双 Python 矩阵 + 覆盖率双门槛 + Windows 打包 artifact）
- CAS 知识库检索（内置条目 + resources/knowledge 外部文档）+ 问题包导出（日志/DB/环境信息打包 zip）

**未实现（规划中）**：

- 报表自动生成（余额表/序时账 -> 三大报表）-- V1.5
- 间接法现金流量表 -- V2.0
- 合并报表 / IFRS 支持 -- V2.0

---

## 10. 开发流程校准 (每步开始前必读)

开始任何开发任务前，回答以下问题：

1. **我要做什么？** 一句话描述目标
2. **涉及哪些模块？** 是否违反模块职责边界（§1.2）？
3. **数据模型是否够用？** 是否需要新增字段/类型？
4. **测试用例想好了吗？** 至少覆盖 §4.2 的边界场景
5. **是否引入新依赖？** 许可证是否兼容？能否用标准库替代？
6. **函数会超过 50 行吗？** 文件会超过 250 行吗？如果会，如何拆分？
7. **错误信息面向财务用户吗？** 是否使用了技术术语？
8. **遵守 P1 宁可漏报不可误报？** 缺数据时规则是否跳过而非误报？
