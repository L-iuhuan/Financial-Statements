# AGENTS.md - 财务报表勾稽校验系统 强约束文档

> **每一步开发开始前必须阅读此文档，校准开发方向。**
> 本文档是项目的"宪法"，任何代码变更必须符合以下约束。
> 违反约束的代码不得合并。

---

## 0. 项目原则 (不可妥协)

| # | 原则 | 含义 |
|---|---|---|
| P1 | **宁可漏报不可误报** | 校验结果"通过"必须是确定的；"不通过"允许漏掉。即：容差偏向通过，规则保守。 |
| P2 | **确定性优先** | 所有校验逻辑必须是确定性的、可复现的。同输入同输出，不依赖随机数、时间、网络。 |
| P3 | **可审计可溯源** | 每一条校验结果必须能追溯到：哪条规则、哪个公式、哪些科目、原始数据在哪行哪列。 |
| P4 | **用户是财务人员** | UI 文案用财务术语，不用技术术语。错误信息要告诉用户"哪里出了问题"而非"抛了什么异常"。 |
| P5 | **模块隔离** | 生成、校验、导入、导出各自独立，通过数据模型解耦。校验引擎不知道报表来源。 |

---

## 1. 架构约束

### 1.1 分层架构

```
GUI层 (PySide6/qfluentwidgets)
    ↓ 用户操作 + 数据
业务层 (导入/生成/校验/导出)
    ↓ 标准数据模型
数据模型层 (Report / ReportItem / ValidationResult)
    ↓ 对象
持久化层 (SQLite WAL)
```

- 上层依赖下层，下层不依赖上层
- 同层模块之间通过数据模型通信，不直接调用
- **禁止跨层调用**：GUI 层不得直接操作 SQLite

### 1.2 模块职责边界

| 模块 | 职责 | 禁止 |
|---|---|---|
| `importer/` | 读取文件 -> 输出 Report 对象 | 禁止执行校验逻辑 |
| `engine/` | 接收 Report 对象 -> 输出 ValidationResult | 禁止读取文件、禁止操作 GUI |
| `generator/` | 从余额表/序时账 -> 输出 Report 对象 | 禁止执行校验逻辑 |
| `exporter/` | 接收 ValidationResult -> 输出文件 | 禁止修改校验结果 |
| `agent/` | 接收 ValidationResult -> 输出诊断建议 | 禁止修改校验结果 |
| `updater/` | 检查版本 + 下载安装 | 禁止访问业务数据 |

### 1.3 数据模型作为契约

所有模块通过以下数据模型通信：

- `Report` — 一张财务报表（含多个 ReportItem）
- `ReportItem` — 报表中的一个项目（科目/合计项）
- `ReconciliationRule` — 一条勾稽校验规则
- `ValidationResult` — 一条校验结果
- `ValidationContext` — 一次校验运行的上下文（含所有报表）

**规则引擎的输入永远是 `Report` 对象，不关心来源。** 导入来的 Report 和生成来的 Report 是同一个类型，校验引擎无法区分。

---

## 2. 编码规范

### 2.1 Python 版本与类型

- Python 3.11+
- **全类型注解**：所有函数参数、返回值必须有类型注解
- **禁止** `Any`、`# type: ignore`、`Optional` (用 `X | None` 替代)
- 使用 `from __future__ import annotations` 无需，3.11+ 原生支持

### 2.2 函数与文件大小

- 函数体 <= 50 行（不含空行和注释）
- 文件 <= 250 行纯代码（不含测试、注释、空行）
- 超过则拆分

### 2.3 错误处理

- **禁止空 catch**：`except Exception: pass` 是 BUG
- **禁止宽 catch**：catch 具体异常，不 catch `Exception`
- 自定义异常继承自 `FSAError`（项目根异常）
- 错误信息用中文，面向财务用户

### 2.4 数据精度

- 金额使用 `float`（MVP 阶段，simpleeval 兼容）
- 未来如需 Decimal，在数据模型层统一转换
- 容差比较：`abs(a - b) <= tolerance`，不用 `==`

### 2.5 日志

- 使用 `loguru`，不用 `print`
- 日志级别：DEBUG (开发) / INFO (关键流程) / WARNING (可恢复异常) / ERROR (不可恢复)
- 日志内容包含上下文（规则ID、报表类型、金额值）

### 2.6 导入规范

- 标准库优先
- 第三方库需在 pyproject.toml 声明
- 禁止 `from X import *`
- 导入顺序：标准库 -> 第三方库 -> 项目内模块

---

## 3. 测试规范

### 3.1 TDD 流程 (强制)

1. **先写测试**：写一个失败的测试
2. **再写实现**：写最少的代码让测试通过
3. **重构**：优化代码，测试仍通过

### 3.2 测试覆盖要求

每个函数必须有以下类型的测试：

| 类型 | 说明 | 示例 |
|---|---|---|
| 正常路径 | 典型输入，预期输出 | 资产=100, 负债=60, 权益=40 -> 通过 |
| 边界值 | 恰好在临界点 | 差额=0.01 (等于容差) -> 通过 |
| 边界外 | 恰好超过临界点 | 差额=0.011 (超过容差) -> 不通过 |
| 零值 | 全部为0 | 资产=0, 负债=0, 权益=0 -> 通过 |
| 负值 | 负数金额 | 资产=-100, 负债=-60, 权益=-40 -> 通过 |
| 缺失数据 | 必需字段不存在 | 报表缺少"资产总计" -> 报错 |
| None值 | 字段值为None | 某项目金额=None -> 报错 |
| 大数 | 1e15级别 | 资产=1e15 -> 正确计算 |
| 浮点精度 | 小数精度问题 | 0.1+0.2 != 0.3 但容差内通过 |
| 多个项目 | 同一key有多个item | 两个"资产总计" -> 报错或取第一个 |

### 3.3 测试命名

```
test_<被测函数>_<场景>_<期望结果>

# 示例
test_evaluate_exact_match_returns_pass
test_evaluate_diff_at_tolerance_returns_pass
test_evaluate_diff_over_tolerance_returns_fail
test_evaluate_missing_variable_raises_error
```

### 3.4 测试结构 (AAA)

```python
def test_evaluate_exact_match_returns_pass():
    # Arrange
    rule = make_rule(formula="a == b + c", tolerance=0.01)
    context = make_context(a=100.0, b=60.0, c=40.0)

    # Act
    result = rule.evaluate(context)

    # Assert
    assert result.passed is True
    assert result.diff == 0.0
```

### 3.5 覆盖率

- 行覆盖率 >= 90%
- 分支覆盖率 >= 80%
- 关键模块（engine/）覆盖率 100%

---

## 4. 命名规范

| 类型 | 风格 | 示例 |
|---|---|---|
| 类 | PascalCase | `ReportItem`, `ValidationResult` |
| 函数/方法 | snake_case | `get_amount`, `evaluate_rule` |
| 变量 | snake_case | `asset_total`, `diff_amount` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_TOLERANCE`, `MAX_FILE_SIZE` |
| 文件 | snake_case.py | `report.py`, `evaluator.py` |
| 测试文件 | test_<被测模块>.py | `test_report.py`, `test_evaluator.py` |
| 枚举值 | UPPER_SNAKE_CASE | `BALANCE_SHEET`, `EXACT` |
| 规则ID | 大写-数字 | `BS-BAL-001` |

### 4.1 变量名与公式

规则公式中的变量名使用 **snake_case 英文**：
- `asset_total` (资产总计)
- `liability_total` (负债合计)
- `equity_total` (所有者权益合计)
- `net_profit` (净利润)

`ReportItem.key` 字段与公式变量名一一对应。

---

## 5. 依赖策略

### 5.1 许可证策略

**本软件仅供内部使用，允许商业许可依赖。**

| 用途 | 许可证 | 说明 |
|---|---|---|
| 核心引擎 (engine/, models/) | 仅开源 (MIT/BSD/Apache/LGPL) | 核心逻辑不绑定商业库，保证可移植 |
| GUI 层 / 数据处理 / 工具 | 允许商业许可 | 内部使用无许可限制 |
| 可选增强 | 允许商业许可 | 如商业 PDF 库、商业图表库 |

> **注意**：如果将来考虑开源发布，所有商业依赖需要替换为开源替代。
> 核心引擎保持纯开源依赖，确保引擎逻辑可独立提取。

### 5.2 新增依赖流程

1. 在设计文档中记录新增理由
2. 确认许可证类型（内部使用不限制）
3. 在 AGENTS.md 依赖清单中登记
4. 最小化依赖：能用标准库解决的不引入第三方

### 5.3 当前依赖清单

| 依赖 | 版本 | 许可证 | 用途 |
|---|---|---|---|
| PySide6 | >=6.7 | LGPL | GUI 框架 |
| PySide6-Fluent-Widgets | >=1.0 | LGPL | Fluent Design 组件 |
| pandas | >=2.2 | BSD | 数据处理 |
| openpyxl | >=3.1 | MIT | Excel 读写 |
| simpleeval | >=1.0 | MIT | 安全表达式求值 |
| loguru | >=0.7 | MIT | 日志 |
| camelot-py | >=0.12 | MIT | PDF 表格提取 (V1) |
| pdfplumber | >=0.11 | MIT | PDF 文本提取 (V1) |
| requests | >=2.31 | Apache | HTTP 请求 (Agent/更新) |

### 5.4 开发依赖

| 依赖 | 用途 |
|---|---|
| pytest | 测试框架 |
| pytest-qt | Qt 组件测试 |
| pytest-cov | 覆盖率 |
| ruff | Linter |
| mypy | 类型检查 |

---

## 6. Git 规范

### 6.1 提交信息

```
<type>: <description>

type: feat | fix | test | refactor | docs | chore | build
```

### 6.2 分支

- `main` — 稳定，可发布
- `dev` — 开发主干
- `feat/<feature>` — 功能分支

---

## 7. 开发流程校准 (每步开始前必读)

开始任何开发任务前，回答以下问题：

1. **我要做什么？** 一句话描述目标
2. **涉及哪些模块？** 是否违反模块职责边界？
3. **数据模型是否够用？** 是否需要新增字段/类型？
4. **测试用例想好了吗？** 至少 5 个边界场景
5. **是否引入新依赖？** 许可证是否兼容？
6. **函数会超过 50 行吗？** 如果会，如何拆分？
7. **文件会超过 250 行吗？** 如果会，如何拆分？
8. **错误信息面向财务用户吗？** 是否使用了技术术语？

---

## 8. 当前阶段约束 (MVP)

- 只处理 Excel (.xlsx/.xls)
- 只支持三大主表（资产负债表、利润表、现金流量表）
- 44 条 CAS 规则
- 不做 PDF、不做报表生成、不做 Agent
- SQLite 存储，单机使用
- Python 3.11+，Windows 10 兼容
