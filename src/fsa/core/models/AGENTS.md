# core/models — 数据模型层（契约层）

## OVERVIEW

全项目的数据契约：Report/ReportItem/ReconciliationRule/ValidationResult/DetailDataset。纯数据层——**仅依赖标准库 + loguru + core.exceptions**，不 import engine/importer/services/gui。约 39 个文件消费本包。

## FILES

| 文件 | 职责 |
|---|---|
| `report.py` | `ReportType`（BS/IS/CF/SCE/NOTES 枚举，值为中文名）；`ReportItem`（frozen，key/name/amount/beginning_amount/row/column/beginning_column）；`Report`（可变，items + `unmapped_names` + `amount_unit`） |
| `rule.py` | `ToleranceType`（EXACT/ABSOLUTE/RELATIVE/THRESHOLD）；`Severity`；`ReconciliationRule`（frozen） |
| `result.py` | `KNOWN_LINE_ITEM_KEYS`、`TraceItem`、`ValidationResult`（errored/skipped 标记 + trace）、`ValidationSummary`、`ValidationContext`（含 namespace 缓存） |
| `detail.py` | 明细六表行模型（全 frozen，均带 `row` 溯源）+ `DetailDataset`（可变，`merge()`/`is_empty`） |

## INVARIANTS（本包最隐蔽的坑都在这里）

- **`__init__.py` 保持空**——禁止添加 re-export；全项目一律深路径导入（`from fsa.core.models.result import ...`）
- **零值预填排除清单**（`KNOWN_LINE_ITEM_KEYS`，result.py 有大量 NOTE 注释）：刻意排除 `parent_equity`/`total_revenue`/`total_operating_cost`/`primary_revenue`/`other_revenue`/`dividends` 等 key——预填 0 会让对应规则对真实报表误报（P1）。排除 = 缺数据时规则 skip；包含 = 预填 0.0。**新增科目 key 时必须审查此集合的取舍**
- **frozen 与可变分层**：ReportItem/规则/明细行 frozen（含 `__post_init__` 校验）；Report/ValidationContext/DetailDataset/ValidationResult/ValidationSummary 可变
- `ValidationContext.build_namespace()` 返回**缓存引用**——调用方须复制后再改（runner 注入行业阈值变量时如此）；key 已带 `_ending`/`_beginning` 后缀者不再生成垃圾键
- key 唯一性双闸：`Report.__post_init__` 与 `add_item` 重复 key 均抛 `DuplicateItemError`（**函数内延迟导入** exceptions——规避循环导入的既有模式）
- `ValidationContext.add_report` 同类型覆盖 + loguru warning；`get_item` 遍历所有报表（含 `cf_notes_` key）
- `TraceItem.row` 语义：0 = 无源行号（阈值变量等）；PDF 行号是 `页码 * 10_000_000 + 表内行号` 编码（解码见 exporter `_format_source_row`）
- 金额一律 float；模型层**不做容差比较**（交给 engine/comparator）

## ANTI-PATTERNS

- 禁止模型层 import 任何上层模块（engine/services/gui/storage）
- 禁止往 `__init__.py` 加导出
- 禁止在 `__post_init__` 之外绕开校验构造非法对象（用工厂/构造器）
- `Report.unmapped_names` 不参与校验（仅供 Agent/人工排查）——勿把它当校验输入
