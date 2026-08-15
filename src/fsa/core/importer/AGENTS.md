# core/importer — 数据导入

## OVERVIEW
文件 → `Report` 对象。格式无关管线：reader → `RawSheetData` → `identify_reports` → `extract_items` → `Report`。禁止执行校验逻辑（模块 docstring 明载）。

## FILES

| 文件 | 职责 |
|---|---|
| `importer.py` | `ImportService` 编排入口（仅持 period，无状态）；`import_file`/`import_sheet` |
| `excel_reader.py` | openpyxl(.xlsx) + pandas/xlrd(.xls) → `RawSheetData`；COM 回退（DLP 加密环境） |
| `pdf_reader.py` | pdfplumber 按页 `extract_tables` → 同一 `RawSheetData`（标题=sheet 名） |
| `report_identifier.py` | 两级类型识别：sheet 名（含英文关键词）→ 内容特征科目 |
| `item_extractor.py` | 主表项目提取：三级金额列定位（标准列名→期间模式→数值占比）；BS 双栏；补充资料区 → `cf_notes_*` |
| `sce_extractor.py` | 权益变动表矩阵提取（仅 Excel）→ `sce_*` keys |
| `name_mapper.py` | 科目名→key 映射（标准名 + 企业别名 + `cf_notes_*`）；`MappingProxyType` 只读 |
| `amount_parser.py` | **统一金额解析器**：千分位/括号负数/全角字符/`—`占位→None/拒绝 inf·nan——所有读取器共用，禁止各自再写解析 |
| `detail_importer.py` | 按表头特征识别 7 类明细表 → `DetailDataset`（"1-本月"累计 vs "本月"分列） |
| `detail_parsers.py` | 明细行解析辅助（`_number` 返回 `float | None`，调用方区分解析失败与有效零值） |

## RawSheetData 契约

`headers`（去重，重复加 `#2` 后缀）+ `header_rows`（≤4 层子表头）+ `rows`（dict，键=列名，`"_row"`=1-based 源行号）。新增格式 = 新增 reader，下游不动。

## COM 回退（excel_reader）

openpyxl/xlrd 抛 `_NATIVE_READ_ERRORS`（BadZipFile/OSError/ValueError/KeyError/TypeError/XLRDError）→ `read_excel_com`：`DispatchEx` + ReadOnly + `UsedRange.Value` → 同一 `_matrix_to_raw`。DLP 加密文件只有 COM 能读；`use_com=True` 可强制。

## INVARIANTS

- 重复 key **首个出现者胜**（`Report` 构造会抛 `DuplicateItemError`，extractor 必须先 dedupe）
- 每个 `ReportItem` 携带 row/column 溯源（P3）
- 未映射科目静默丢弃 + debug 日志——导入是有损的，映射即契约
- `clean_name` 管线：strip → 去尾括号 → 去尾冒号 → 去前缀（一、/减:/加:/其中:）→ 再去尾冒号
- 表头匹配先去除全部空白（含全角）；原始表头文本保留为 dict 键
- 明细行数值解析策略：关键金额解析失败 → 整行跳过（不伪造 0.0，P1）；非关键构成字段 → 0.0；无效行整行跳过
- `.xls` 空白单元格经 pandas 读为 NaN → 统一 NaN→0/None，避免污染校验结果（§3.5）

## 未映射科目追踪

主表提取时，"有金额但无法映射为标准科目"的项目名记入 `Report.unmapped_names`（Agent 工具 `get_unmapped_items` 据此给出真实清单）。

## ANTI-PATTERNS

- 禁止在本模块执行任何校验逻辑
- 禁止运行期修改 `NAME_TO_KEY`/`KEY_TO_NAME`（`MappingProxyType` 即为此设）
- 禁止抛英文或技术性错误给上层——读取失败统一包装为 `FSAError` 中文消息（`raise ... from error` 链接）
- 禁止绕过 `amount_parser.py` 自写金额解析（历史教训：Excel/PDF 解析不一致导致静默丢数）
