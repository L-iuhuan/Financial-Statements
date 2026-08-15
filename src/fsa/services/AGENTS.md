# services — 业务编排层

## OVERVIEW
GUI ↔ core 之间的编排层。不读文件、不碰 GUI、不写 SQL。依赖方向：`gui → services → core`，严格单向。

## FILES

| 文件 | 职责 |
|---|---|
| `validation_service.py` | `ValidationService`：主表规则执行 → `ValidationSummary` |
| `package_service.py` | `PackageValidationService`：主规则 + L2 明细一次执行合并——**GUI 唯一校验入口**（import_page）；`merge_summaries` |
| `detail_validation_service.py` | `DetailValidationService`：编排 12 组 `core.engine` 明细检查；`DetailCheckConfig`（tolerance / cash_equivalent_codes / tb_to_bs_mappings） |
| `entity_config.py` | `EntityConfig`（按主体覆盖容差/现金等价物/映射/**industry 行业**——驱动 `engine/thresholds.py` 的 LR-* 阈值覆写）+ `load_entity_configs` |
| `multi_entity_service.py` | 文件夹级批量校验 + ICF-002 双边核对；**当前无 GUI 消费方**（库式服务，测试使用） |

## 异常映射阶梯（`_run_rule_safe`，照抄此模式）

```
EvaluationError      → skip   (缺数据 ≠ 不通过, P1; 含 RelativeBaseZeroError)
FormulaParseError    → error  (规则定义错误)
FSAError             → error
具体异常族            → error + logger.error
  (ValueError/TypeError/KeyError/ArithmeticError/RuntimeError/OSError)
```

注意：最后一层是**具体异常族枚举**，不是 `except Exception`——新增异常类型时显式加入，不要退化为宽 catch。

## INVARIANTS

- 适用性过滤：`rule.statements` 的报表类型 ⊆ 已导入报表；缺报表的规则直接跳过，**不计入结果总数**
- `validate` 是纯编排：输入 reports+period，输出 `ValidationSummary`；不保存跨调用状态
- `merge_summaries` 重算统计字段，而非简单相加
- 错误信息全中文、面向财务用户（P4/P6）

## ANTI-PATTERNS

- 禁止在 services 读取文件（文件路径在 GUI/importer 层处理）
- 禁止 import `fsa.gui.*`（依赖反向）
- `validation_service.py:42` 有一行遗留 `print()`——新增代码不得效仿，应使用 loguru
