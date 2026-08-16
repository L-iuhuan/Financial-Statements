# 项目结构与开发计划

> **归档说明 (2026-08-15)**: 本文为历史设计/过程文档，其中规则数量、目录结构、依赖清单等具体数值可能与现行代码不一致；一切以根 AGENTS.md 与代码为准。


> ## ⚠️ 已归档 / 已过时
>
> **本文档是早期规划稿（更新日期 2026-08-07），内容已严重过时，仅供参考，不再维护。**
> 与实际代码不符之处包括：
> - 目录结构：实际模块为 `src/fsa/` 下的顶层包 `agent/ core/ gui/ services/ storage/ updater/`，
>   不存在 `ui/`、`core/generator/`、`core/storage/` 等旧路径（详见 AGENTS.md §1.2）
> - 依赖：已移除 `camelot-py`、`requests`（updater/agent 用 stdlib urllib）
> - 规则数：本文写 44 条，实际为 **42 条（v1.3.0）**
>
> **请以 [AGENTS.md](./AGENTS.md) 为权威文档（模块布局见其 §1.2，规则库见其 §5.1）。**

> **配套文档**: [design.md](./design.md)  
> **许可证**: MIT  
> **更新日期**: 2026-08-07（已过时，见上）

---

## 一、项目目录结构

```
财务报表自动稽核/
│
├── design.md                          # 完整设计文档
├── project_structure.md               # 本文档
├── DEV_LOG.md                         # 开发日志
├── README.md                          # 项目说明
├── LICENSE                            # MIT 许可证
├── .gitignore                         # Python gitignore
├── pyproject.toml                     # 项目配置 (依赖/工具)
│
├── src/
│   └── fsa/                           # Financial Statement Auditor (主包)
│       ├── __init__.py
│       ├── __main__.py                # 入口: python -m fsa
│       ├── app.py                     # QApplication 启动
│       │
│       ├── ui/                        # GUI 层 (PySide6 + qfluentwidgets)
│       │   ├── __init__.py
│       │   ├── main_window.py         # MainWindow 主窗口
│       │   ├── widgets/
│       │   │   ├── drop_zone.py       # 拖拽导入区
│       │   │   ├── result_card.py     # 结果卡片 (分色展示)
│       │   │   ├── diff_trace.py     # 差异追溯面板
│       │   │   └── status_bar.py     # 状态栏
│       │   ├── dialogs/
│       │   │   ├── import_wizard.py  # 导入向导 (报表类型识别+确认)
│       │   │   ├── rule_manager.py   # 规则管理器 (增删改查)
│       │   │   ├── template_editor.py # 模板编辑器
│       │   │   ├── settings.py       # 设置对话框
│       │   │   └── account_mapper.py  # 科目映射对话框
│       │   └── theme/
│       │       └── style.qss         # QSS 主题样式 (备用)
│       │
│       ├── core/                      # 核心业务层
│       │   ├── __init__.py
│       │   ├── models/                # 数据模型
│       │   │   ├── __init__.py
│       │   │   ├── report.py         # Report, ReportItem
│       │   │   ├── rule.py           # ReconciliationRule, RuleType, Severity
│       │   │   ├── result.py         # ValidationResult, ValidationContext
│       │   │   └── template.py       # ReportTemplate, ColumnMapping
│       │   │
│       │   ├── importer/              # 数据导入与标准化
│       │   │   ├── __init__.py
│       │   │   ├── base.py            # Importer 抽象基类
│       │   │   ├── excel_importer.py  # Excel 导入 (openpyxl+pandas)
│       │   │   ├── pdf_importer.py    # PDF 导入 (V1: Camelot+pdfplumber)
│       │   │   ├── csv_importer.py    # CSV 导入
│       │   │   ├── type_detector.py   # 报表类型识别
│       │   │   ├── account_mapper.py  # 科目字典+别名映射
│       │   │   └── standardizer.py    # 数据标准化
│       │   │
│       │   ├── engine/                # 规则引擎
│       │   │   ├── __init__.py
│       │   │   ├── parser.py          # 表达式解析 (simpleeval)
│       │   │   ├── evaluator.py       # 规则求值器 (容差比较)
│       │   │   ├── runner.py           # 批量执行器
│       │   │   └── loader.py          # 规则加载器 (SQLite->内存)
│       │   │
│       │   ├── agent/                 # Agent 智能诊断 (V1)
│       │   │   ├── __init__.py
│       │   │   ├── llm_abstraction.py # LLM 抽象层 (Ollama/Cloud)
│       │   │   ├── context_builder.py # AgentContext 构建
│       │   │   ├── prompts.py         # Prompt 模板
│       │   │   └── response_parser.py # 响应解析
│       │   │
│       │   ├── generator/             # 报表自动生成 (V1.5)
│       │   │   ├── __init__.py
│       │   │   ├── account_mapping.py # 科目->报表项目映射 (CAS默认映射表)
│       │   │   ├── report_generator.py # BS/IS 从余额表生成
│       │   │   ├── cash_flow_generator.py # CF 从序时账生成 (直接法+间接法)
│       │   │   ├── cash_flow_rules.py  # 现金流分类规则
│       │   │   └── workpaper_generator.py # 审计底稿生成
│       │   │
│       │   ├── updater/              # 自动更新 (V1.0)
│       │   │   ├── __init__.py
│       │   │   ├── version_checker.py # 版本检查 (读内网version.json)
│       │   │   └── update_installer.py # 下载+校验+安装更新
│       │   │
│       │   ├── exporter/              # 导出层
│       │   │   ├── __init__.py
│       │   │   ├── excel_workpaper.py # Excel 审计底稿 (带公式)
│       │   │   └── diff_report.py     # 差异调整建议清单
│       │   │
│       │   └── storage/               # 持久化层
│       │       ├── __init__.py
│       │       ├── database.py        # SQLite 连接+初始化
│       │       ├── rule_repo.py      # 规则 CRUD
│       │       ├── history_repo.py   # 历史记录 CRUD
│       │       ├── template_repo.py  # 模板 CRUD
│       │       └── settings_repo.py   # 设置 CRUD
│       │
│       └── utils/                     # 工具
│           ├── __init__.py
│           ├── number.py              # 数值解析 (千分位/括号负数)
│           ├── logger.py             # 日志
│           └── config.py             # 配置加载
│
├── resources/                        # 资源文件
│   ├── rules/
│   │   └── cas_gouji_rule_library.json  # CAS 默认规则库 (44条)
│   ├── aliases/
│   │   └── cas_account_aliases.json     # CAS 科目别名字典
│   ├── templates/
│   │   └── default_templates.json       # 默认报表模板
│   └── icons/                           # 图标
│
├── tests/                             # 测试
│   ├── __init__.py
│   ├── conftest.py                    # pytest fixtures
│   ├── test_engine/                   # 规则引擎测试
│   │   ├── test_parser.py
│   │   ├── test_evaluator.py
│   │   └── test_tolerance.py
│   ├── test_importer/                 # 导入测试
│   │   ├── test_excel_importer.py
│   │   ├── test_type_detector.py
│   │   └── test_account_mapper.py
│   ├── test_models/                   # 模型测试
│   │   └── test_report.py
│   └── test_storage/                  # 存储测试
│       └── test_database.py
│
├── examples/                          # 示例文件
│   ├── sample_balance_sheet.xlsx      # 示例资产负债表
│   ├── sample_income_statement.xlsx   # 示例利润表
│   └── sample_cash_flow.xlsx          # 示例现金流量表
│
├── docs/                              # 文档
│   ├── design.md -> ../design.md      # 软链
│   ├── architecture.png              # 架构图
│   └── dev_log.md -> ../DEV_LOG.md    # 软链
│
└── scripts/                           # 脚本
    ├── init_db.py                     # 初始化数据库
    ├── import_rules.py                # 导入规则库
    ├── build.py                       # PyInstaller 打包脚本
    ├── build_installer.iss            # Inno Setup 安装器脚本 (Win10安装包)
    └── publish.py                     # 发布脚本 (打包+构建安装器+生成version.json)
```

---

## 二、核心模块接口定义

### 2.1 数据导入层

```python
# core/importer/base.py

from abc import ABC, abstractmethod
from core.models.report import Report
from core.models.template import ReportTemplate

class Importer(ABC):
    """数据导入器抽象基类"""

    @abstractmethod
    def import_file(
        self,
        file_path: str,
        template: ReportTemplate | None = None,
    ) -> list[Report]:
        """
        导入文件，返回报表列表 (一个文件可能含多张报表)

        Args:
            file_path: 文件路径
            template: 报表模板 (None=自动识别)

        Returns:
            Report 列表 (每张报表一个 Report 对象)
        """
        ...

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """支持的文件扩展名"""
        ...
```

```python
# core/importer/excel_importer.py

import openpyxl
import pandas as pd
from core.importer.base import Importer
from core.importer.type_detector import ReportTypeDetector
from core.importer.account_mapper import AccountMapper
from core.importer.standardizer import DataStandardizer
from core.models.report import Report, ReportItem, ReportType
from core.models.template import ReportTemplate

class ExcelImporter(Importer):
    """Excel 导入器 (openpyxl + pandas)"""

    def __init__(
        self,
        type_detector: ReportTypeDetector,
        account_mapper: AccountMapper,
        standardizer: DataStandardizer,
    ):
        self._type_detector = type_detector
        self._account_mapper = account_mapper
        self._standardizer = standardizer

    def import_file(
        self,
        file_path: str,
        template: ReportTemplate | None = None,
    ) -> list[Report]:
        """
        导入 Excel 文件

        流程:
        1. openpyxl 打开工作簿
        2. 遍历每个 sheet
        3. 报表类型识别 (无模板时)
        4. 按模板提取数据 (header_row, column_mappings)
        5. 处理合并单元格 (merge_cell_strategy)
        6. 科目标准化 (account_mapper)
        7. 构建 Report 对象
        """
        wb = openpyxl.load_workbook(file_path, data_only=True)
        reports = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            report = self._parse_sheet(ws, sheet_name, file_path, template)
            if report:
                reports.append(report)
        return reports

    def supported_extensions(self) -> list[str]:
        return [".xlsx", ".xls"]

    def _parse_sheet(
        self,
        ws,
        sheet_name: str,
        file_path: str,
        template: ReportTemplate | None,
    ) -> Report | None:
        """解析单个 sheet"""
        # 1. 识别报表类型
        report_type = self._type_detector.detect(ws, template)
        if report_type is None:
            return None  # 非报表 sheet

        # 2. 加载/推断模板
        tpl = template or self._type_detector.infer_template(ws, report_type)

        # 3. 提取数据
        items = self._extract_items(ws, tpl)

        # 4. 科目标准化
        items = self._account_mapper.map_items(items)

        # 5. 构建 Report
        return Report(
            id=str(uuid4()),
            report_type=report_type,
            # ...其他字段
            items=items,
            source_file=file_path,
            source_sheet=sheet_name,
        )

    def _extract_items(self, ws, template: ReportTemplate) -> list[ReportItem]:
        """按模板提取科目项"""
        # 处理合并单元格
        # 按 column_mappings 映射列
        # 识别小计行
        ...
```

```python
# core/importer/type_detector.py

from core.models.report import ReportType

class ReportTypeDetector:
    """报表类型识别器"""

    # 关键词 -> 报表类型 映射
    KEYWORD_MAP: dict[str, ReportType] = {
        "资产负债表": ReportType.BALANCE_SHEET,
        "平衡表": ReportType.BALANCE_SHEET,
        "balance sheet": ReportType.BALANCE_SHEET,
        "利润表": ReportType.INCOME_STATEMENT,
        "损益表": ReportType.INCOME_STATEMENT,
        "income statement": ReportType.INCOME_STATEMENT,
        "现金流量表": ReportType.CASH_FLOW,
        "cash flow": ReportType.CASH_FLOW,
        "所有者权益变动表": ReportType.EQUITY_CHANGES,
        "股东权益变动表": ReportType.EQUITY_CHANGES,
    }

    def detect(self, ws, template=None) -> ReportType | None:
        """
        识别报表类型

        策略 (按优先级):
        1. 模板已指定类型 -> 直接返回
        2. sheet名关键词匹配
        3. 表头行关键词匹配
        4. 列结构特征匹配 (如: 有"资产"和"负债"列 -> BS)
        5. 仍不确定 -> 返回None (UI层弹窗让用户确认)
        """
        ...

    def infer_template(self, ws, report_type: ReportType) -> ReportTemplate:
        """自动推断模板 (无预定义模板时)"""
        ...
```

```python
# core/importer/account_mapper.py

import difflib
from core.models.report import ReportItem

class AccountMapper:
    """科目名称映射器 - 桥接企业科目与标准科目"""

    def __init__(self, alias_dict: dict[str, str]):
        """
        Args:
            alias_dict: {别名: 标准名} 字典
                        如 {"现金": "货币资金", "银行存款": "货币资金"}
        """
        self._alias_dict = alias_dict
        # 构建反向索引 + 标准名列表 (用于模糊匹配)
        self._standard_names = list(set(alias_dict.values()))

    def map_items(self, items: list[ReportItem]) -> list[ReportItem]:
        """
        批量映射科目名称

        策略 (按优先级):
        1. 精确匹配 (account_name == 标准名)
        2. 别名字典查找 (account_name in alias_dict)
        3. 模糊匹配 (difflib ratio > 0.8, 标记 confidence)
        4. 未匹配 -> standard_name = account_name, confidence = 0 (UI标记)
        """
        for item in items:
            item.standard_name = self._map(item.account_name)
        return items

    def _map(self, name: str) -> str:
        """单个映射"""
        # 1. 精确匹配
        if name in self._standard_names:
            return name
        # 2. 别名查找
        if name in self._alias_dict:
            return self._alias_dict[name]
        # 3. 模糊匹配
        matches = difflib.get_close_matches(name, self._standard_names, n=1, cutoff=0.8)
        if matches:
            return matches[0]
        # 4. 未匹配
        return name  # 保持原名, confidence=0
```

### 2.2 规则引擎层

```python
# core/engine/parser.py

from simpleeval import simple_eval
from core.models.rule import ReconciliationRule, ToleranceType

SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}

def wrap_tolerance(
    expression: str,
    tolerance: float,
    tolerance_type: ToleranceType,
) -> str:
    """将 == 表达式包装为容差比较"""
    if "==" not in expression:
        return expression

    lhs, rhs = expression.split("==", 1)
    lhs, rhs = lhs.strip(), rhs.strip()

    if tolerance_type in (ToleranceType.EXACT, ToleranceType.ABSOLUTE):
        return f"abs({lhs} - ({rhs})) <= {tolerance}"
    elif tolerance_type == ToleranceType.RELATIVE:
        return f"abs({lhs} - ({rhs})) / max(abs({rhs}), 0.01) <= {tolerance}"
    return expression


def evaluate(expression: str, names: dict[str, float]) -> tuple[bool, str | None]:
    """
    安全求值

    Returns:
        (result, error_message)
        - 成功: (True/False, None)
        - 失败: (False, "错误描述")
    """
    try:
        result = simple_eval(
            expression,
            functions=SAFE_FUNCTIONS,
            names=names,
        )
        return bool(result), None
    except NameNotDefined as e:
        return False, f"科目未找到: {e}"
    except SyntaxError as e:
        return False, f"表达式语法错误: {e}"
    except ZeroDivisionError:
        return False, "除以零"
    except Exception as e:
        return False, f"求值错误: {e}"
```

```python
# core/engine/runner.py

from dataclasses import dataclass
from core.engine.parser import wrap_tolerance, evaluate
from core.models.report import Report
from core.models.rule import ReconciliationRule
from core.models.result import ValidationResult, ValidationContext

class ValidationRunner:
    """批量校验执行器"""

    def __init__(self, reports: dict[str, Report], rules: list[ReconciliationRule]):
        """
        Args:
            reports: {report_type_str: Report} 字典
            rules: 参与校验的规则列表
        """
        self._reports = reports
        self._rules = rules

    def run(self) -> ValidationContext:
        """执行全部校验，返回完整上下文"""
        import time
        start = time.time()

        results = []
        for rule in self._rules:
            result = self._evaluate_rule(rule)
            results.append(result)

        elapsed_ms = int((time.time() - start) * 1000)
        return self._build_context(results, elapsed_ms)

    def _evaluate_rule(self, rule: ReconciliationRule) -> ValidationResult:
        """评估单条规则"""
        # 1. 提取涉及科目的值
        names = self._extract_values(rule.involved_fields)

        # 2. 包装容差
        expr = wrap_tolerance(rule.expression, rule.tolerance, rule.tolerance_type)

        # 3. 求值
        passed, error = evaluate(expr, names)

        # 4. 构建结果
        return ValidationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type.value,
            severity=rule.severity.value,
            passed=passed,
            formula=rule.expression,
            expression=rule.expression,
            involved_items=self._build_involved_items(rule.involved_fields, names),
            tolerance_type=rule.tolerance_type.value,
            tolerance=rule.tolerance,
            # expected/actual/difference 从表达式提取 (V1增强)
        )

    def _extract_values(self, fields: list[str]) -> dict[str, float]:
        """从报表中提取科目值"""
        names = {}
        for field in fields:
            for report in self._reports.values():
                item = report.get_item(field)
                if item:
                    names[field] = item.amount
                    # 也提供 "field_期末" / "field_期初" 变体
                    names[f"{field}_期末"] = item.amount
                    if item.prior_amount is not None:
                        names[f"{field}_期初"] = item.prior_amount
                    break
        return names

    def _build_involved_items(
        self, fields: list[str], names: dict[str, float]
    ) -> list[dict]:
        """构建涉及科目详情 (用于差异追溯)"""
        items = []
        for field in fields:
            value = names.get(field)
            if value is not None:
                # 找到来源
                source = ""
                for report in self._reports.values():
                    item = report.get_item(field)
                    if item:
                        source = f"{item.raw_sheet}!R{item.raw_row}"
                        break
                items.append({"name": field, "value": value, "source": source})
        return items
```

### 2.3 持久化层

```python
# core/storage/database.py

import sqlite3
from pathlib import Path

class Database:
    """SQLite 数据库连接管理"""

    def __init__(self, db_path: str = "~/.fsa/data.db"):
        self._path = Path(db_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """连接并配置 WAL 模式"""
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,  # 允许多线程 (GUI+worker)
        )
        # 性能配置
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # Row factory (返回字典式行)
        self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_schema(self) -> None:
        """初始化数据库 schema"""
        schema = """
        CREATE TABLE IF NOT EXISTS rules (...);
        CREATE TABLE IF NOT EXISTS validation_history (...);
        CREATE TABLE IF NOT EXISTS templates (...);
        CREATE TABLE IF NOT EXISTS account_aliases (...);
        CREATE TABLE IF NOT EXISTS settings (...);
        -- 索引
        CREATE INDEX IF NOT EXISTS idx_rules_type_grouping ON ...;
        """
        self._conn.executescript(schema)
        self._conn.commit()
```

```python
# core/storage/rule_repo.py

from core.models.rule import ReconciliationRule, RuleType, Severity, ToleranceType
import json

class RuleRepository:
    """规则 CRUD"""

    def __init__(self, db):
        self._db = db

    def fetch_all_enabled(self) -> list[ReconciliationRule]:
        """获取所有启用的规则 (热更新用)"""
        rows = self._db.execute(
            "SELECT * FROM rules WHERE enabled = 1 ORDER BY grouping, id"
        ).fetchall()
        return [self._row_to_rule(r) for r in rows]

    def fetch_by_report_type(self, report_type: str) -> list[ReconciliationRule]:
        """按报表类型获取规则"""
        rows = self._db.execute(
            "SELECT * FROM rules WHERE enabled = 1 AND report_types LIKE ?",
            (f'%"{report_type}"%',),
        ).fetchall()
        return [self._row_to_rule(r) for r in rows]

    def upsert(self, rule: ReconciliationRule) -> None:
        """插入或更新规则"""
        self._db.execute(
            """INSERT INTO rules (id, name, rule_type, severity, grouping,
               expression, involved_fields, tolerance_type, tolerance,
               standards, report_types, cas_ref, enabled, is_default, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, rule_type=excluded.rule_type,
               severity=excluded.severity, expression=excluded.expression,
               updated_at=datetime('now','localtime')""",
            (rule.id, rule.name, rule.rule_type.value, rule.severity.value,
             rule.grouping, rule.expression, json.dumps(rule.involved_fields),
             rule.tolerance_type.value, rule.tolerance,
             json.dumps(rule.standards), json.dumps(rule.report_types),
             rule.cas_ref, int(rule.enabled), int(rule.is_default),
             rule.description),
        )
        self._db.commit()

    def delete(self, rule_id: str) -> None:
        """删除规则 (仅非默认规则)"""
        self._db.execute(
            "DELETE FROM rules WHERE id = ? AND is_default = 0", (rule_id,)
        )
        self._db.commit()

    def _row_to_rule(self, row) -> ReconciliationRule:
        """数据库行 -> ReconciliationRule 对象"""
        return ReconciliationRule(
            id=row["id"],
            name=row["name"],
            rule_type=RuleType(row["rule_type"]),
            severity=Severity(row["severity"]),
            grouping=row["grouping"],
            expression=row["expression"],
            involved_fields=json.loads(row["involved_fields"]),
            tolerance_type=ToleranceType(row["tolerance_type"]),
            tolerance=row["tolerance"],
            standards=json.loads(row["standards"]),
            report_types=json.loads(row["report_types"]),
            cas_ref=row["cas_ref"],
            enabled=bool(row["enabled"]),
            is_default=bool(row["is_default"]),
            description=row["description"],
        )
```

### 2.4 导出层

```python
# core/exporter/excel_workpaper.py

import openpyxl
from openpyxl.styles import Font, PatternFill, Border
from core.models.result import ValidationContext

class ExcelWorkpaperExporter:
    """Excel 审计底稿导出器 - 带勾稽公式"""

    def export(self, context: ValidationContext, output_path: str) -> None:
        """
        导出带公式的 Excel 审计底稿

        结构:
        - Sheet 1: 校验结果总览 (红/黄/蓝分色)
        - Sheet 2: 差异明细 (每条失败规则 + 涉及科目 + 计算公式)
        - Sheet 3: 数据底稿 (原始数据 + Excel公式可复算)
        """
        wb = openpyxl.Workbook()
        self._write_summary(wb, context)
        self._write_diff_detail(wb, context)
        self._write_data_workpaper(wb, context)
        wb.save(output_path)

    def _write_data_workpaper(self, wb, context: ValidationContext):
        """
        写入数据底稿 - 关键: 用 Excel 公式表达勾稽关系
        让财务人员可直接在 Excel 中复核
        """
        ws = wb.create_sheet("数据底稿")
        # 写入科目数据
        # 在旁边列写入公式:
        #   =B5-(B10+B15)  (资产总计 - (负债合计 + 权益合计))
        # 公式结果非零 = 差异
        ...
```

---

### 2.5 报表自动生成层 (V1.5)

```python
# core/generator/account_mapping.py

from core.models.report import Report, ReportItem
from core.models.validation import ReportType

class AccountMapping:
    """CAS 科目 -> 报表项目映射器"""

    # 内置 CAS 标准映射表 (可被用户自定义覆盖)
    DEFAULT_MAPPINGS: dict[ReportType, dict[str, str]] = {
        ReportType.BALANCE_SHEET: {
            "1001": "货币资金", "1002": "货币资金",       # 库存现金+银行存款
            "1122": "应收账款", "1123": "其他应收款",
            "1241": "存货", "1601": "固定资产",
            "2202": "应付账款", "2203": "预收账款",
            "4001": "实收资本", "4101": "盈余公积",
            "4103": "本年利润", "4104": "利润分配",
            # ... ~200 条标准映射
        },
        ReportType.INCOME_STATEMENT: {
            "5001": "营业收入", "5051": "其他业务收入",
            "5401": "营业成本", "5402": "其他业务成本",
            "5601": "销售费用", "5602": "管理费用", "5603": "研发费用",
            "5701": "财务费用", "5801": "资产减值损失",
            "6101": "公允价值变动收益", "6111": "投资收益",
            "6301": "营业外收入", "6711": "营业外支出",
            "6801": "所得税费用",
        },
    }

    def map_account(self, account_code: str, report_type: ReportType) -> str | None:
        """科目代码 -> 报表项目名称 (支持级次: 1001.01 -> 货币资金)"""
        ...

    def map_all(self, trial_balance: list) -> dict[ReportType, list[ReportItem]]:
        """批量映射: 余额表 -> 各报表项目聚合"""
        ...


# core/generator/report_generator.py

from core.models.report import Report, ReportItem, ReportType
from core.generator.account_mapping import AccountMapping

class ReportGenerator:
    """从余额表自动生成资产负债表 + 利润表"""

    def __init__(self, mapping: AccountMapping):
        self.mapping = mapping

    def generate_balance_sheet(self, trial_balance: list) -> Report:
        """
        余额表 -> 资产负债表

        流程:
        1. 按科目映射聚合到报表项目
        2. 计算合计 (流动资产合计、非流动资产合计、资产总计...)
        3. 校验: 资产总计 == 负债和所有者权益总计
        4. 生成 Report 对象 (含所有 ReportItem)
        """
        ...

    def generate_income_statement(self, trial_balance: list) -> Report:
        """
        余额表 -> 利润表

        流程:
        1. 损益类科目余额 -> 报表项目
        2. 计算营业收入、营业成本、期间费用、营业利润、利润总额、净利润
        3. 生成 Report 对象
        """
        ...


# core/generator/cash_flow_generator.py

from core.models.report import Report

class CashFlowGenerator:
    """从序时账 (明细账) 自动生成现金流量表 - 直接法"""

    def __init__(self, cash_flow_rules: dict):
        """
        cash_flow_rules: 现金流分类规则
        {
            "1001": "经营活动",   # 库存现金
            "1002": "经营活动",   # 银行存款
            "1002.01": "经营活动",  # 银行存款-活期
            "1002.02": "投资活动",  # 银行存款-定期(>3月)
            "1002.03": "筹资活动",  # 银行存款-保证金
        }
        """
        self.rules = cash_flow_rules

    def generate(self, journal_entries: list) -> Report:
        """
        序时账 -> 现金流量表 (直接法)

        流程:
        1. 筛选涉及现金类科目的分录
        2. 按对方科目分类 (经营/投资/筹资)
        3. 按具体活动细分 (销售商品收到的现金、购买商品支付的现金...)
        4. 汇总各活动现金流入流出净额
        5. 生成 Report 对象
        """
        ...


# core/generator/workpaper_generator.py

class WorkpaperGenerator:
    """生成审计底稿 - 与校验报告合并输出"""

    def generate(self, reports: list[Report], validation_results: list) -> str:
        """
        输出一份 Excel, 包含:
        - Sheet 1: 资产负债表 (生成)
        - Sheet 2: 利润表 (生成)
        - Sheet 3: 现金流量表 (生成)
        - Sheet 4: 勾稽校验结果 (44条规则)
        - Sheet 5: 科目到报表项目映射底稿 (可追溯)
        - Sheet 6: 现金流分类底稿 (每笔分录的分类依据)
        """
        ...
```

---

### 2.6 自动更新层 (V1.0)

```python
# core/updater/version_checker.py

from dataclasses import dataclass

@dataclass
class VersionInfo:
    version: str           # "1.0.0"
    download_url: str      # 内网共享路径
    file_hash: str         # SHA256
    release_notes: str     # 更新说明
    min_app_version: str   # 最低兼容版本 (低于此版本必须全量更新)

class VersionChecker:
    """检查内网更新服务器上的版本"""

    UPDATE_SERVER_URL = r"\\内网服务器\share\fsa-updates\version.json"

    def check_latest(self) -> VersionInfo | None:
        """读取内网 version.json, 返回最新版本信息"""
        ...

    def is_update_available(self, current_version: str) -> tuple[bool, VersionInfo | None]:
        """比较版本号, 返回 (是否需要更新, 最新版本信息)"""
        ...


# core/updater/update_installer.py

class UpdateInstaller:
    """下载并安装更新"""

    def download(self, version_info: VersionInfo, progress_callback) -> str:
        """
        下载安装包到临时目录
        - 显示下载进度 (通过 progress_callback)
        - 下载完成后校验 SHA256
        - 返回下载文件路径
        """
        ...

    def install(self, installer_path: str) -> None:
        """
        静默安装更新:
        1. 关闭当前应用
        2. 运行安装包 (Inno Setup /SILENT /NOCANCEL)
        3. 重启应用
        """
        ...

    def verify_hash(self, file_path: str, expected_hash: str) -> bool:
        """SHA256 校验"""
        ...
```

---

## 三、分阶段开发计划

### MVP (6-8 周) - Excel 勾稽校验可用 + 安装器

**目标**: 非技术财务人员可拖入 Excel，一键获得勾稽校验结果，且可通过安装包部署

| 周 | 任务 | 交付物 |
|---|---|---|
| 1-2 | 项目骨架 + 数据模型 + SQLite | 项目结构、models、database.py、init_db.py |
| 2-3 | Excel 导入 + 类型识别 + 科目映射 | excel_importer.py、type_detector.py、account_mapper.py |
| 3-4 | 规则引擎 (parser+evaluator+runner) | engine/ 全部、44 条规则导入 SQLite |
| 4-5 | GUI 主框架 (qfluentwidgets) | main_window.py、drop_zone.py、import_wizard.py |
| 5-6 | 结果看板 + 差异追溯 + 导出 | result_card.py、diff_trace.py、excel_workpaper.py |
| 6-7 | 集成测试 + **Inno Setup 安装器** | tests/、build.py、build_installer.iss、安装包 |
| 7-8 | 示例文件 + 文档 + 磨合 | examples/、README、DEV_LOG |

**MVP 验收标准**:
- [ ] 拖入 3 张 Excel (BS+IS+CF) -> 3 秒内识别完成
- [ ] 44 条规则校验 -> 5 秒内完成
- [ ] 结果看板红/黄/蓝分色展示
- [ ] 点击差异 -> 显示公式 + 涉及科目 + 原始行列
- [ ] 导出 Excel 审计底稿 (带公式可复算)
- [ ] **Inno Setup 安装包** (自定义路径 + 桌面快捷方式 + 卸载器)
- [ ] 安装包 < 120MB, Win10 兼容

### V1.0 (4-6 周) - PDF + Agent + 自动更新 + 权益变动表

| 周 | 任务 |
|---|---|
| 1-2 | PDF 导入 (Camelot lattice + pdfplumber) + HITL 纠正 UI |
| 2-3 | 所有者权益变动表支持 (规则扩展) |
| 3-4 | **自动更新机制** (版本检查+下载+安装+更新提示弹窗) |
| 4-5 | Ollama Agent 集成 (本地 LLM 诊断) |
| 5-6 | 历史记录对比分析 + 递延所得税/商誉规则增强 |

**V1.0 验收标准**:
- [ ] PDF 导入 + HITL 纠正 (准确率 > 80%)
- [ ] 四大报表完整校验
- [ ] **启动时自动检查内网更新服务器, 弹窗提示新版本**
- [ ] **一键更新: 下载安装包 -> 校验SHA256 -> 静默安装 -> 重启**
- [ ] Agent 诊断 (Ollama 本地) -> 问题总结 + 根因 + 建议
- [ ] 历史校验结果对比

### V1.5 (4-6 周) - 报表自动生成 + 配置完善

| 周 | 任务 |
|---|---|
| 1-2 | **余额表导入 + BS/IS 自动生成** (科目->报表项目映射) |
| 2-3 | **序时账导入 + CF 直接法自动生成** (现金流分类规则) |
| 3-4 | **生成+校验一体化** (生成后自动运行44规则验证) |
| 4-5 | 规则编辑器 UI + 模板管理器 + 科目映射 UI |
| 5-6 | 规则导入导出 (JSON/YAML) + 多主题 |

**V1.5 验收标准**:
- [ ] **导入余额表 -> 自动生成资产负债表 + 利润表**
- [ ] **导入序时账 -> 自动生成现金流量表 (直接法)**
- [ ] **生成的报表自动通过44条勾稽校验**
- [ ] **输出: 三大报表 + 审计底稿 + 勾稽校验报告 (一份Excel)**
- [ ] 规则/模板/科目映射可视化编辑

### V2.0 (8-12 周) - 高级功能

| 周 | 任务 |
|---|---|
| 1-3 | ML PDF 提取 (PaddleOCR PP-StructureV3) |
| 3-5 | 合并报表支持 (抵销分录规则库) |
| 5-7 | IFRS 准则支持 (双规则库 + 切换) |
| 7-9 | 云端 LLM 支持 (OpenAI/Claude API) |
| 9-12 | **间接法现金流量表自动生成** + 性能优化 + 国际化 + 发布 |

---

## 四、依赖清单 (pyproject.toml)

```toml
[project]
name = "financial-statement-auditor"
version = "0.1.0"
description = "财务报表勾稽关系自动校验桌面软件"
license = {text = "MIT"}
requires-python = ">=3.11"

dependencies = [
    # GUI
    "PySide6>=6.7,<7",
    "PySide6-Fluent-Widgets>=1.0",       # Fluent Design 组件库

    # 数据处理
    "pandas>=2.2,<3",
    "openpyxl>=3.1,<4",

    # PDF (V1)
    "camelot-py[cv]>=0.12",               # PDF表格提取 (base)
    "pdfplumber>=0.11",                    # PDF文本/表格提取

    # 规则引擎
    "simpleeval>=1.0",                     # 安全表达式求值

    # 存储
    # sqlite3 (标准库, 无需安装)

    # Agent (V1)
    "requests>=2.31",                      # Ollama HTTP 调用

    # 工具
    "loguru>=0.7",                         # 日志
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.4",                     # Qt测试
    "pytest-cov>=5.0",
    "ruff>=0.5",                           # linter
    "mypy>=1.10",                          # 类型检查
]
build = [
    "pyinstaller>=6.0",                   # 打包
    # "nuitka>=2.0",                      # 可选打包 (更小)
]
# 外部工具 (非pip):
#   - Inno Setup 6+ (https://jrsoftware.org/isdl.php)  -- Win10安装包构建
#   - Git (内网发布工作流)
ml = [
    # V2: ML PDF提取
    "paddleocr>=2.7",
    "paddlepaddle>=2.6",
]
```

---

## 五、Git 工作流 (GitHub 同步)

```
main              # 稳定发布分支
├── develop       # 开发主线
│   ├── feature/mvp-excel-importer   # 功能分支
│   ├── feature/rule-engine
│   ├── feature/result-dashboard
│   └── feature/v1-pdf-importer
├── release/v0.1.0-mvp              # 发布分支
└── hotfix/xxx                      # 紧急修复
```

**提交规范** (Conventional Commits):
```
feat: 新功能
fix: 修复
docs: 文档
refactor: 重构
test: 测试
chore: 构建/依赖

示例:
feat(engine): 实现 simpleeval 规则求值器
fix(importer): 修复合并单元格值丢失
docs(design): 更新对抗式审查记录
```

---

## 六、风险登记册 (详细)

| ID | 风险 | 等级 | 概率 | 影响 | 规避方案 | 阶段 |
|---|---|---|---|---|---|---|
| R01 | PDF 财务表提取准确率低 (F1≤0.24) | 高 | 高 | PDF 功能不可用 | V1 必须带 HITL UI；V2 引入 PaddleOCR ML | V1 |
| R02 | 科目名称映射不准 | 高 | 高 | 规则无法执行 | 别名字典+模糊匹配+手动映射 fallback | MVP |
| R03 | simpleeval 中文标识符兼容性 | 中 | 中 | 规则表达式报错 | MVP 首先验证中文标识符；备选转拼音映射 | MVP |
| R04 | openpyxl 大文件(>10MB)性能 | 中 | 低 | 导入缓慢 | 分块读取；提示用户精简文件 | MVP |
| R05 | Ollama 模型质量不稳定 | 中 | 中 | Agent 诊断不准 | 提供推荐模型列表；结果标记"仅供参考" | V1 |
| R06 | PySide6 打包体积超限 | 低 | 低 | 安装包>200MB | 裁剪Qt模块；Nuitka onefile；实测验证 | MVP |
| R07 | 合并报表逻辑复杂 | 高 | 高(V2) | V2 延期 | 抵销分录规则库独立设计；预留数据模型字段 | V2 |
| R08 | 规则热更新与正在执行的校验冲突 | 低 | 低 | 结果不一致 | 读时复制规则快照；执行期间锁定 | MVP |
| R09 | SQLite WAL 文件膨胀 | 低 | 低 | 磁盘占用 | 定期 wal_checkpoint(TRUNCATE) | MVP |
| R10 | 多准则切换时规则混淆 | 中 | 中(V2) | IFRS 用错 CAS 规则 | 准则字段过滤；切换时清空缓存 | V2 |
| R11 | qfluentwidgets 版本兼容性 | 低 | 低 | UI 组件异常 | 锁定版本；备选手写 QSS | MVP |
| R12 | Excel 合并单元格多样式 | 中 | 中 | 数据提取错误 | 多策略(fill_down/keep_first/skip) + 测试覆盖 | MVP |

---

*文档结束。开发进度记录于 DEV_LOG.md。*
