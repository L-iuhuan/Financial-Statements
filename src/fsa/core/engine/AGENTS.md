# core/engine — 规则引擎

## OVERVIEW
接收 `Report` 对象 → 输出 `ValidationResult`。两套路由：42 条 JSON 声明式规则（`RuleRunner`，规则库 v1.3.0）+ 12 组 Python 明细检查（`*_checks.py`，由 `services/DetailValidationService` 编排，绕过 `RuleRunner`）。

## FILES

| 文件 | 职责 |
|---|---|
| `runner.py` | `RuleRunner.run(rule, context)` 单规则执行入口；构建 namespace/trace/中文消息；注入行业阈值变量 |
| `evaluator.py` | simpleeval 求值；`split_formula`（恰好一个 `==`）；`evaluate_boolean`（阈值式） |
| `comparator.py` | 4 种容差比较 → `(passed, diff)`；`RelativeBaseZeroError`（见下） |
| `thresholds.py` | 行业阈值参数化：LR-* 规则的阈值变量（`dar_threshold`/`current_ratio_threshold` 等）按行业取值，`EntityConfig.industry` 覆写，默认 `general`；未知行业告警并回落 |
| `registry.py` | `RuleRegistry` 启停/按类过滤/容差覆写/自定义规则 CRUD |
| `rule_loader.py` | `cas_gouji_rule_library.json` → `list[ReconciliationRule]` |
| `custom_rules.py` | `custom_rules.json` 读写（冻结模式写 `~/.fsa/`） |
| `detail_checks.py` | L2：凭证平衡、现金流明细 vs 主表/序时账、余额表 vs 资产负债表 |
| `cash_flow_checks.py` + `cash_flow_rules.py` | L4 凭证级现金流分类检查（CF-CLS-001..008/901，保守 WARNING） |
| `reclassification_checks.py` | L2 往来重分类（RC-001/002） |
| `supplementary_checks.py` | L2 关联方采购/销售明细/内部现金流（RP/SAL/ICF） |

`__init__.py` 为空：无包级导出，消费者直接 import 子模块。

## 规则 JSON 格式（单条）

```json
{"id": "BS-BAL-001", "category": "A-表内平衡", "statements": ["资产负债表"],
 "formula": "asset_total == liability_total + equity_total",
 "tolerance_type": "exact", "default_tolerance": 0.01, "severity": "error",
 "cas_ref": "...", "notes": "..."}
```

- formula 两种形态：等式（恰好一个 `==`）或阈值布尔式（`<=`/`>=`/`and`/`or`）
- 可用函数仅 `abs/min/max/round/sum`；变量 = `ReportItem.key`；双列后缀 `_ending`/`_beginning`；附注变量 `cf_notes_*`
- LR-* 行业敏感阈值**已参数化**：公式写阈值变量名（如 `liability_total / asset_total <= dar_threshold`），由 runner 从 `thresholds.py` 按行业注入；`INDUSTRY_THRESHOLD_RULES` 记录规则ID↔变量名映射供审计追溯
- 容差语义：`exact/absolute/threshold` → `abs(l-r)<=tol`；`relative` → `abs(diff)/abs(right)<=tol`，right=0 时：left=0→通过，left≠0→`RelativeBaseZeroError`（继承 `EvaluationError` → 走 skip 路径，P1）

## 执行流

`registry.get_active()` → services 按 `rule.statements` 过滤适用性 → `RuleRunner.run`（注入行业阈值变量）→ `context.build_namespace()` → evaluate → `ToleranceComparator.compare` → `ValidationResult`（含 trace 左右侧变量）

## INVARIANTS（本模块特有）

- trace 查询先整 key 命中再剥 `_ending`/`_beginning` 后缀（SCE 键如 `sce_x_ending` 可正确溯源）；namespace 不再生成 `_ending_ending` 类垃圾键
- **P1 偏通过**：`KNOWN_LINE_ITEM_KEYS` 预填 0.0；`EvaluationError` → skip 而非 fail。`models/result.py` 注释记录了刻意排除的 key（`total_revenue`/`dividends` 等——预填 0 会误报，故移出让规则 skip）
- 永不 `==` 比浮点，一律 `abs(a-b) <= tolerance`；负容差双层拒绝（`ReconciliationRule.__post_init__` + comparator）；|金额|>1e14 时 warning 提示精度边界（不改变判定，P2）
- 引擎不读报表数据文件；`rule_loader`/`custom_rules` 读写的是规则配置 JSON（注册期加载，非数据），这是对"禁止读取文件"的受控解释
- 缺主表/缺数据时明细检查一律 skip（skipped 结果或空列表，P1）；CF-DTL-001 明细项目未匹配主表时降级为 skipped+WARNING 提示（不再计为异常）
- 受控共享依赖：`detail/reclassification/supplementary_checks` import `importer.name_mapper.clean_name`

## ANTI-PATTERNS

- 禁止新增 `eval()`；公式只走 simpleeval 白名单
- 禁止让缺数据导致"不通过"——缺失必须 skip（P1）
- 禁止在 LR-* 公式中硬编码行业敏感数字——必须走 `thresholds.py` 阈值变量
- `MissingItemError` 已定义但当前未使用；缺变量实际走 simpleeval `NameNotDefined` → `EvaluationError` → skip
