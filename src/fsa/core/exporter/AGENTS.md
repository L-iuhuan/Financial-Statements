# core/exporter — 审计底稿导出

## OVERVIEW

`AuditExporter.export(summary, file_path)` 接收 `ValidationSummary` → 输出格式化 Excel 审计底稿。**只读契约：禁止修改校验结果**（包 docstring 明文）。唯一生产消费方是 `gui/export_helper.py`。

## FILES

| 文件 | 职责 |
|---|---|
| `audit_exporter.py` | `AuditExporter` + 4 个 sheet 写入 + 模块级辅助函数 |
| `_styles.py` | openpyxl 样式常量；docstring 明载「不含任何业务逻辑」 |

## 输出（4 个 sheet）

1. **校验汇总**：期间/时间/规则统计/涉及报表/规则库版本 + 结论文案
2. **校验明细**：`规则ID|规则名称|分类|校验结果|左侧值|右侧值|差额|容差|公式|说明`；状态行着色（绿/红/黄/灰 = 通过/不通过/异常/跳过）；金额列 `#,##0.00`；`freeze_panes="A2"`
3. **科目追溯**：`规则ID|规则名称|侧|科目名称|金额|原始行|原始列`；**skipped 结果不输出**
4. **底稿说明**：期间/编制时间/规则库版本/源文件 + SHA256 + 文件大小 + 金额单位留痕 + 空白「编制人/复核人/复核意见」手填区（P3 审计证据链）

## INVARIANTS

- **不嵌入 Excel 公式对象**——公式列写的是公式**文本**（供人工复核）
- **公式注入防护强制**：所有可能以 `= + - @` 开头的字符串单元格必须过 `_safe_text()`（前缀 `'`）——公式列和 message 列都走此路径
- **PDF 行号解码**：`_PDF_ROW_BASE = 10_000_000`（与 `importer/pdf_reader.py` 的 D-01 编码契约联动）；`row<=0` → `""`；`row>=base` → `第X页表内第N行`；否则 Excel 1-based 行号
- **阈值/布尔规则**（`_is_threshold_rule`：公式不含 `==`）left/right/diff 显示 `—`（保守判定，仅影响展示）
- 规则库版本经 `resource_path("cas_gouji_rule_library.json")` 读取（兼容 PyInstaller 冻结模式），失败返回 `""`
- 异常契约：`PermissionError`（文件被占用）/`OSError`/`RuntimeError`；中文转换在 GUI 层

## ANTI-PATTERNS

- 禁止修改传入的 `ValidationSummary`（只读）
- 禁止在 exporter 调引擎/读 Report/写业务逻辑（阈值判定仅用于展示）
- 禁止绕过 `_safe_text()` 直接写用户/报表来源的字符串单元格
- 新增 sheet 或列时同步更新 `tests/exporter/test_audit_exporter.py`（约 680 行，覆盖全 sheet）
