# 财务报表勾稽校验系统 — 全面审查报告

> 审查基准：`git HEAD = 7419c68`（2026-08-13 00:20:20，本地与 origin/main 一致，无更新提交）
> 审查方式：主代理通读核心引擎/模型/规则库 + 两个只读子代理分片深审（数据链路 / agent·gui·updater）+ 架构审计脚本（`architecture-audit.md`）
> 说明：每条发现带 `file:line` 证据；勾选框用于对照另一台电脑的修改逐项核对，修好请打 `[x]`

---

## 0. 总览

| 维度 | 评价 |
|---|---|
| 规模 | 源码 68 文件 / 9014 行，测试 753 个，规则库 37 条（v1.2.0） |
| 架构 | 分层总体健康：engine 不依赖 GUI、导入不掺校验、无包级环（除 agent→gui 反向依赖）、导入图无环 |
| 确定性 | P2 合规：校验逻辑无随机/网络/时间依赖 |
| 测试 | 本会话收集 753 个；沙箱环境 585 通过，其余失败均为环境写权限（QSettings 注册表/临时目录/~/.fsa）被沙箱拦截，未发现代码逻辑导致的失败 |
| 核心风险 | **P1 误报链**（导入静默丢项 × 预填0 × 无质量门禁）> 打包/文档漂移 > GUI 主线程阻塞 |

---

## 1. 财务方案核心问题（引擎 + 规则库 + 数据模型）

### 1.1 误报链（P1 红线，最优先）

- [ ] **【高】** `result.py:279` 所有 KNOWN_LINE_ITEM_KEYS 无条件预填 0，无法区分"企业确实无此科目"与"导入提取失败"；叠加导入层静默丢项（见 §3），缺一个"负债合计"就会算出"资产100亿 ≠ 0+0"报**假不通过**。`tests/services/test_validation_service.py:150-170`（`test_validate_rule_with_missing_variable_defaults_zero_fails`）把这个行为固化成了预期。
  → 建议：导入层加"提取质量门禁"（关键科目缺失→该规则跳过并提示"未能提取到 XX 科目"，而非报不通过）；预填 0 仅用于报表完整且确认无此科目的场景。
- [ ] **【高】** `importer.py:68-73` items 为空的报表照常构建 0-item Report 且无告警 → 空报表全量按 0 求值产生大量假失败。
- [ ] **【高】** `item_extractor.py:201-212` 金额转换失败仅 warning 静默跳过（文本"1,234.56"、"(1,234)"、"—" 全丢）→ 同上链路。

### 1.2 阈值规则参数失效

- [ ] **【高】** 阈值规则走 `evaluate_boolean`（`runner.py:107`），**不经过 ToleranceComparator**：`LR-DAR-001` 公式硬编码 0.85 但 `default_tolerance=0.70`；`LR-ART-001` 硬编码 0.30 但容差 0.20；`LR-QUICK-001`/`LR-SALES-001`/`LR-GM-002`/`LR-FLUC-001` 同类。规则页/设置页改容差存 SQLite 后**不生效**，且界面显示两个矛盾数字。
  → 建议：阈值参数化注入公式（如 `<= {threshold}` 替换），或对 threshold 类型规则隐藏/禁用容差编辑。
- [ ] **【中】** `runner.py:168-184` `_build_threshold_message` 失败时只回显公式文本，不给实际计算值（如"资产负债率 0.9"）→ 财务用户看不懂（违反 P4）。

### 1.3 SCE 可审计性断裂（P3）

- [ ] **【高】** SCE 提取器存的是带后缀完整 key（`sce_paid_in_capital_ending`，`sce_extractor.py:128`），而 `runner.py:257-292` 的 trace 查询会把 `_ending` 剥掉再查基名 → 查不到 → 追溯表显示"金额 0.0、原始行 0"。**权益变动表规则能校验但差异追溯全是假数据**，审计底稿"科目追溯"sheet 对 SCE 形同虚设。
- [ ] **【低】** `result.py:298` 对 SCE 键再拼 `_ending` 生成 `sce_x_ending_ending` 垃圾命名空间键（无害但暴露双列引擎与 SCE 引擎两套半成品机制重叠）。

### 1.4 同类型报表静默覆盖

- [ ] **【高】** `result.py:236-238` `ValidationContext.add_report` 同类型直接覆盖：合并报表+母公司报表同文件时只剩后一张；"现金流量表"与"现金流量表补充资料"两个 Sheet 互相覆盖可能挤掉主表。→ 建议：告警/报错/支持多实例。
- [ ] **【中】** PDF 多页同标题互相覆盖（`pdf_reader.py:75`）：跨页续表只保留最后一页碎片。

### 1.5 引擎其他

- [ ] **【中】** `exceptions.py:13` `MissingItemError` 从未被 raise（死代码，docstring 误导）。
- [ ] **【中】** `result.py:291-296` 跨报表重复 key 抛裸 `ValueError` → 被 `validation_service.py:124` 宽 catch 吞成"未预期错误"，掩盖真实原因。
- [ ] **【低】** `registry.py:12-16,52-61` `get_for_report_types` 只映射三大主表（SCE/NOTES 缺失）且无调用方（死代码）。
- [ ] **【低】** `ValidationSummary.success_rate`（`result.py:209-213`）errored 计分母不计分子、skipped 剔除，语义未文档化，易与 UI"总规则数"混淆。

### 1.6 规则库财务口径（供财务复核）

- [ ] **【中】** `IS-CF-002`（`cas_gouji_rule_library.json`）：`cf_notes_impairment + credit_impairment + asset_impairment == 0` 假定间接法减值加回=利润表信用+资产减值损失，实务加回额还含存货跌价等 → 潜在误报（目前 warning 级）。
- [ ] **【中】** `IS-TAX-001`：递延所得税变动未剔除直接计入权益的部分，公式做不到 notes 声称的剔除。
- [ ] **【中】** `LR-DAR-001`（0.85）、`LR-ART-001`（0.30）等行业敏感阈值未参数化，金融/地产等行业会误报。
- [ ] **【低】** 3 条实质死规则：`SCE-BAL-001`（占位符永远跳过）、`NOTES-001/002`（依赖永不存在的 `notes_item_detail` 等变量）→ 37 条实际生效约 34 条。
- [ ] **【低】** `LR-OCF-001` `tolerance_type=threshold` + `default_tolerance=1.0` 语义混乱（容差字段无意义）。

---

## 2. 导入层

### 2.1 Excel（excel_reader.py）

- [ ] **【高】** `excel_reader.py:84-100` 表头行检测只查**第1列=="项目"（精确匹配）**，找不到就静默默认第 1 行：行次列在前/表头带空格/表头在 5 行之后的报表 → 标题行当表头、数据全错、提取 0 科目 → 全部预填 0 假失败。→ 建议：任意列包含"项目"即命中；找不到显式告警而非默认。
- [ ] **【高】** `excel_reader.py:103-117` 只读单行表头：两行表头（"期末余额"合并跨列）下合并区非锚点单元格为 None → 金额列大量为空静默丢。
- [ ] **【中】** `excel_reader.py:49-54` 只捕获 FileNotFoundError/OSError：`.xls` 抛 InvalidFileException、损坏文件抛 BadZipFile 未捕获 → 技术异常直抛给财务用户（P4）。且 README:19 与 AGENTS.md:276 声称支持 `.xls`，openpyxl 根本不读 `.xls`。
- [ ] **【中】** `excel_reader.py:50` `data_only=True`：程序生成的无缓存公式单元格返回 None → 金额列整列静默丢失。→ 建议：检测"金额列全空但有公式"并告警。

### 2.2 PDF（pdf_reader.py）

- [ ] **【高】** `pdf_reader.py:202-219` 数据行无**行宽校验**：合并单元格使某行少一列时后续值整体左移挂到错误表头 → **错误金额当正确数据导入**（P1 红线）。→ 建议：单元格数≠表头数时丢弃该行并告警（宁可漏报）。
- [ ] **【高】** `pdf_reader.py:110-118` 表头要求精确等于"项目"（带空格/换行/序号即整表丢弃）；`pdf_reader.py:70` 每页只取 `tables[0]`；`pdf_reader.py:75` 同标题页互相覆盖（跨页续表丢数据）。
- [ ] **【中】** `pdf_reader.py:238-257` `_parse_cell_value` 只剥 ASCII 逗号/空格：括号负号 `(1,234)`、全角空格/负号、`—` 占位全部解析失败退回字符串后被静默跳过；`float("1e400")` 得 inf 也能进金额。→ 建议：统一金额解析器（去千分位、括号转负、全角归一、'—'→None、拒绝 inf/nan）。
- [ ] **【中】** `pdf_reader.py:63-79` `page.extract_tables()` 无异常保护，pdfminer 底层异常直接崩导入。
- [ ] **【低】** `pdf_reader.py:32` `_AMOUNT_HEADER_CANDIDATES` 死代码。

### 2.3 科目映射（name_mapper.py）

- [ ] **【中】** `name_mapper.py:17` `_PREFIX_RE` 剥离"其中："前缀 → "其中：应收账款"明细行被映射成 accounts_receivable，与主行形成重复 key，取哪个取决于行序（`item_extractor.py:194-199` 保留首个）→ **金额语义错误且顺序依赖**。→ 建议：明细行单独映射或跳过。
- [ ] **【中】** `name_mapper.py:154-169` 别名碰撞："应收账款净额"→accounts_receivable、"固定资产净值"→fixed_assets 与标准名同 key，同表并存时取毛额还是净额取决于行序。→ 建议：净额独立 key 或碰撞告警。
- [ ] **【中】** 标准 CAS 全名缺失：`购建固定资产、无形资产和其他长期资产支付的现金`（只有简写）、`取得/处置子公司及其他营业单位…现金净额`、`归属于母公司所有者的净利润`、`持续/终止经营净利润`、`其他流动资产/非流动负债`、`合同负债`、`应收款项融资` 等未映射 → 真实报表科目静默丢弃。→ 建议：按 CAS 标准表单全量补齐 + 测试。

### 2.4 提取器（item_extractor.py / report_identifier.py）

- [ ] **【高】** `item_extractor.py:201-212` 金额转换失败静默跳过（见 1.1）。
- [ ] **【中】** `item_extractor.py:207,219` `# type: ignore[arg-type]` 违反 AGENTS.md 2.1（另 `sce_extractor.py:152` 同）；Excel 与 PDF 金额清洗不一致（Excel 不剥千分位、PDF 剥）→ 建议抽统一 `parse_amount`。
- [ ] **【中】** `item_extractor.py:235-251` 名称列回退"第一列"无文本占比校验（第一列是"行次"数字列→全部项目名变数字→0 科目）。
- [ ] **【中】** `item_extractor.py:279-284` 金额列表头**全等匹配**："期末余额 "（尾空格）、"期末余额(元)" 失配 → 整表 0 科目仅 warning。
- [ ] **【低】** `item_extractor.py:100` 补充资料标记用 `in` 子串匹配："注：详见补充资料"误切模式且永不退出。
- [ ] **【中】** `report_identifier.py:96-102` 内容识别只查 `row.get("项目")` 精确 key（表头为"项目名称"时失效）。
- [ ] **【中】** `report_identifier.py:26-27` 缺"股东权益变动表"模式（上市公司最常用表名）→ 整表静默跳过。
- [ ] **【低】** `report_identifier.py:79-82` 名称子串包含："资产负债表（附注）"误判为 BS。

### 2.5 导入编排（importer.py / sce_extractor.py）

- [ ] **【高】** `importer.py:68-73` 空 items 报表照常构建（见 1.1）。
- [ ] **【中】** `importer.py:110` `import_sheet` 直接调 `extract_items` 绕过 `_extract_for_type`（113-127）→ SCE 经 import_sheet 用错提取器 → 0 科目。
- [ ] **【中】** `importer.py:53-59` 除 .pdf 外一律走 read_excel，`.xls/.csv` 抛原生异常无中文提示。
- [ ] **【高】** `sce_extractor.py:78-88` `_build_column_map` 依赖单行表头+精确列名：常见 SCE **双行表头矩阵**（第 1 行"本年金额"合并 8 列）→ column_map 空 → 整个 SCE 矩阵 0 科目。
- [ ] **【低】** `sce_extractor.py:124,131` 重复表头列取最后一列；`seen` 跨行去重使"上年年末余额/本年年初余额"只留一个。

---

## 3. 导出层（audit_exporter.py）

- [ ] **【中】** `audit_exporter.py:160` `_write_detail_row(self, ws, row, result)` 的 `result` 缺类型注解（违反 2.1）。
- [ ] **【中】** 阈值规则 left_value/right_value/diff 恒为 0（`runner.py:122-124`），导出底稿金额列显示 0.00 误导 → 建议对阈值规则输出实际计算值或留空。
- [ ] **【低】** 预填 0 变量的追溯显示"原始行 0"（`runner.py:282-292`）误导（P3）→ 建议标注"无来源（视为 0）"。
- [ ] **【低】** `audit_exporter.py:80` 用 `assert` 做运行时检查（-O 下失效）；`formula/message` 原样写入单元格，规则库若被篡改为 "=" 开头有公式注入风险 → 写前转义。
- [ ] **【低】** `audit_exporter.py:107` `datetime.now()` 写入审计元数据（P2 允许，快照对比时注意）。

---

## 4. 存储层

- [ ] **【中】** `database.py:115-118` `check_same_thread=False` + 单连接多线程共享无锁：并发 execute 会抛 "Recursive use of cursors"，与 docstring"支持多线程访问"矛盾。→ 建议 threading.Lock 或每线程独立连接。
- [ ] **【中】** `history_repo.py:46-61` `save` 插入 history 后逐条插明细**无显式事务/回滚**：中途失败时隐式事务保持打开，后续操作把半条历史一起提交（汇总与明细不一致，P3）。
- [ ] **【中】** `chat_repo.py:126-130` `add_message` 对不存在 session 插入 → FK 违规抛未捕获 IntegrityError（P4）。
- [ ] **【中】** `override_repo.py:23-38` `set` 不校验容差：可写入 NaN/负值；NaN 使 `abs(a-b)<=nan` 恒 False → **规则永久误报**；`InvalidToleranceError` 已定义却未用。→ 建议 `math.isfinite(t) and t >= 0` 校验。
- [ ] **【低】** `database.py:151-152` `__exit__` 三参数缺注解；`datetime('now','localtime')` 依赖机器时区。

---

## 5. 校验服务（validation_service.py）

- [ ] **【高/宪法违反】** `validation_service.py:124` `except Exception as e` 宽 catch，违反 AGENTS.md 2.3；并把跨表重复 key 的 ValueError（`result.py:291-296`）吞成"未预期错误"掩盖真问题。→ 建议：只捕获 FSAError 子类，其余上抛由顶层转中文。
- [ ] **【中】** `validation_service.py:116-126` from_skip/from_error 拼 `str(e)`：非 FSAError 底层异常 message 可能英文技术化（P4/P6）→ 建议异常→中文映射表。
- [ ] **【低】** `validation_service.py:158-165` `_get_required_types` 对规则库中未知报表名静默忽略 → 建议告警。

---

## 6. Agent 层

- [ ] **【中/分层违反】** `agent_loop.py:14` 运行时 `from fsa.gui.app_state import AppState`、`fallback.py:81` `from fsa.gui.formula_display import formula_to_chinese`、`tools.py:13-14`（TYPE_CHECKING）→ **业务层反向依赖 GUI 层**，gui↔agent 形成包级环，agent 无法脱离 GUI 独立测试。→ 建议：只读数据访问抽象到 core/storage；`formula_to_chinese` 下沉 core。
- [ ] **【中】** `diagnosis.py:228` `except Exception:` 宽 catch（LLM 兜底应 catch 具体异常族：OllamaError/LLMError/OSError/TimeoutError/ValueError）。
- [ ] **【低】** `diagnosis.py:27` `_build_header` "已通过（异常）"标签错误：passed=True 且 errored=False 也显示该文案（当前调用方只传失败规则，潜在边界）。
- [ ] **【低】** `ollama_client.py:81-82` `list_models` 元素非 dict 时 `"name" in m` 抛 TypeError 未捕获；`ollama_client.py:97-104` `generate` 无 `num_predict` 限制，可返回超长文本。
- [ ] **【中】** `llm_client.py:64-79` `_post_json` 未捕获 `OSError`（IncompleteRead/连接中断）→ 原始异常逃逸，`main_window.py:485` 只 catch LLMError → 用户无中文提示。
- [ ] **【低】** `llm_client.py:139-143,221-224` 工具参数 JSON 解析失败静默降级 `{}` 无日志；文件 263 行超 250 行上限。
- [ ] **【中】** `tools.py:266-277` `_get_unmapped_items` 输出与工具 schema 描述不符（描述"未识别科目清单"，实现只有"识别 N 个"计数）→ LLM 拿到误导数据。→ 建议 importer 侧记录未识别科目并提供真实列表。
- [ ] **【低】** `tools.py:243-247` `_compare_with_history` 依赖"get_recent 第一条即本次"，查看历史（persist=False）时错位；`tools.py:220-221` 子串匹配无消歧（"现金"命中"现金等价物"）；`tools.py:289` 靠 message 内"跳过 - "字符串解析脆弱。
- [ ] **【低】** `agent_loop.py:82-83` LLM 空响应直接返回 `""` → 抽屉空气泡；`agent_loop.py:86-96` 工具结果无截断，上下文膨胀。
- [ ] **【中】** `debate.py:62-108` 无空响应/取消/成本上限（3×60s）；`debate.py:113-115` 置信度靠"高/中/低"字符串匹配；辩论输出不可复现（P2），LLM 可能误报根因（P1）→ 建议强制标注"AI 建议仅供参考"；**debate.py / fallback.py 零测试**。

---

## 7. GUI 层

- [ ] **【高/体验】** 全 GUI 主线程同步执行重活（src/fsa 零 QThread）：`main_window.py:483`（AgentLoop ≤5×60s）、`main_window.py:573-574`（辩论 ~3 分钟）、`main_window.py:646`（诊断 30s）、`settings_page.py:252/296`（更新检查 10s/下载 120s）、`import_page.py:185/214`（导入+校验）、`main_window.py:405-410`（历史查询）。→ 建议统一 QThread + 信号回传。
- [ ] **【高】** `main_window.py:467-474,639-643` `_ollama_available` 缓存跨 provider 污染：配置 OpenAI 后诊断仍误判"Ollama 可用"白等 30s；缓存永不失效。
- [ ] **【中】** `main_window.py:505-509,636` `_diagnose_rule` 恒用 `_get_ollama_client()`，完全忽略设置页配置的 provider/base_url/model → **AI 诊断配置不生效**。
- [ ] **【中】** `main_window.py:472,576,642` 宽 catch ×3；`main_window.py:576-580` 把原始异常 `{e}` 直接展示给财务用户（可能英文技术细节，P4）。
- [ ] **【中】** API key 明文读写 QSettings（`main_window.py:525`、`settings_sections.py:315-319`）；base_url 未强制 https → 建议提示 + 文档说明。
- [ ] **【低】** `main_window.py:451-453` 上下文规则存在时所有提问强制改判规则诊断；`main_window.py:404-406` 历史全量拉取后 Python 侧过滤。
- [ ] **【中/泄漏】** `theme.py:55,823-825` `_theme_listeners` 模块级只增不减；`result_card.py:55`、`agent_drawer.py:67` 注册不注销 → 每次校验重建 44 张卡片累积死监听器（无界增长）；主题切换靠 `theme.py:831` `suppress(Exception)`（本身宽 catch）吞 RuntimeError。→ 建议 unregister/弱引用 + destroy 时移除。
- [ ] **【中】** `app.py:28-29` `except Exception: pass` 空 catch（宪法禁止）；`settings_page.py:139-140` 同。
- [ ] **【中】** `settings_page.py:150-151` `_save_tolerance` `except ValueError: pass` 静默吞无效输入，用户输入"abc"无反馈（P4）。
- [ ] **【中】** `audit_page.py:140-141` `result.passed` → 绿色"通过"，而 `from_skip` 规则 passed=True+skipped=True（`result.py:166-167`）被显示为"通过" → **财务用户误以为跳过规则已通过**（P4/P1 语义）。→ 建议"跳过"灰显。
- [ ] **【低】** `audit_page.py:237-246` `_render_print` rule_name 直接拼 HTML 未转义。
- [ ] **【低】** `rule_page.py:359-361` 容差保存 `override_repo.set` 无 try/except（DB 异常用户无感知）；`rule_page.py:169-175` 无效输入静默忽略；删除自定义规则无二次确认。
- [ ] **【低】** `settings_sections.py:153` 访问 `state._db.path` 私有属性；`settings_sections.py:194` 硬编码"37 条规则"（与 AGENTS.md"44 条"矛盾，实际 37 条正确）。
- [ ] **【低】** `sidebar.py:128` 硬编码"版本 0.1.0 (MVP)"，与 `core/version.py` APP_VERSION 不同步。
- [ ] **【低】** `import_page.py:190` 把 ValueError 消息直接拼接展示（可能英文术语）；`import_page.py:298` 通过计数含跳过。
- [ ] **【中】** `agent_drawer.py:262,493,643-645` `# type: ignore` ×5（违反 2.1），monkey-patch 实例方法脆弱；`agent_drawer.py:565-579` 每条消息同步写 SQLite。
- [ ] **【低】** `app_state.py:105-112` `_default_tolerance` 未在 `__init__` 初始化，靠 `getattr` 兜底。

---

## 8. Updater（updater.py）

- [ ] **【高】** `updater.py:155-198` 下载**无哈希/签名校验**：内网文件被篡改/替换无法甄别。→ 建议 manifest 加 sha256，下载后校验、失败删除报错。
- [ ] **【中】** `updater.py:186-196` 无原子写/回滚：中途 OSError 留半截 exe。→ 建议写 `.part` 再 rename，失败清理。
- [ ] **【中】** `updater.py:54-57` 版本解析 `int(p)` 遇非数字段（"0.1.0-beta"）抛裸 ValueError，`check_for_update`（131-145）未包成 UpdateError → 设置页只 catch UpdateError，用户无提示。
- [ ] **【低】** `updater.py:194` 进度回调 total 恒 -1（可用 Content-Length 取总长）。

---

## 9. 测试与脚本

- [ ] **【高】** `scripts/verify_export.py:96-97` 硬编码 `"1.1.1"`，规则库已是 1.2.0 → **该脚本当前必然 FAIL**（验证逻辑自身失效）。→ 建议从规则库 JSON 读版本再断言。
- [ ] **【中】** `tests/rules/test_rule_library_v11.py:220-236` `test_scalable_rules_skip_cleanly` 是只有 `pass` 的空测试；`test_exactly_39_rules`（151-154）名字与断言 37 矛盾；文件名 v11 与库版本 1.2.0 不一致。
- [ ] **【中】** `llm_client.py`（主路径）、`debate.py`、`fallback.py` **零测试**；tools.py 四个查询函数未测。
- [ ] **【中】** 28 处测试函数缺返回注解（test_validation_service.py 等）；`tests/agent/conftest.py:12` 每测试创建真实 AppState（默认路径 SQLite），与 GUI 测试共享库文件，有污染风险 → 建议 tmp_path 隔离。
- [ ] **【低】** verify 脚本全用 print（AGENTS.md 禁 print，建议明确豁免或改 loguru）；`verify_agent.py` 无 `if __name__ == "__main__"` guard；`validate_real_data.py:36` 宽 catch。
- [ ] **【低】** updater 无非数字版本段崩溃路径测试、无"写入失败残留半截文件"测试；GUI 的 _on_diagnose/_on_debate/_check_for_update 网络路径无测试。

---

## 10. 打包与依赖

- [ ] **【高】** `fsa.spec:46` excludes 把 **pdfplumber 排除** → 打包后的 exe 里 PDF 导入功能是坏的（运行时 import 失败）。PDF 是 V1 核心卖点，不能为减体积排除。
- [ ] **【中】** `pyproject.toml:12-29` 未声明 pdfplumber（`pdf_reader.py:16` 直接 import，违反 AGENTS.md 2.6）；声明的 pandas/camelot/requests 实际未使用（AGENTS.md 5.3 清单同漂移）。
- [ ] **【低】** `fsa.spec:24-25` 只打包 logo_32/256，resources/ 其余图标未打包。

---

## 11. 文档漂移（README / AGENTS.md / DEV_LOG / design.md / project_structure.md）

- [ ] **【中】** "44 条规则"共 20 处（README:22,61、AGENTS.md:279、design.md:66,754,1484,1848,1875,2179、DEV_LOG:25,53,127,206,225,240、project_structure.md:112,815,893,901,939）——实际 **37 条**（v1.1 删 5 条 + v1.1.1 删 2 条后未同步文档）。
- [ ] **【中】** README:47-51 快速开始引用不存在的 `scripts/init_db.py`、`scripts/import_rules.py`、`resources/rules/cas_gouji_rule_library.json`（实际规则库在项目根，加载靠 `resource_path`）。
- [ ] **【中】** DEV_LOG 全局待办停更在 08-08：C2 导出器、D1 PDF、D3 Agent、D4 更新均已完成但未勾选。
- [ ] **【中】** AGENTS.md §8 MVP 约束（只 Excel/44 条/不做 PDF/不做 Agent）与实现严重漂移。
- [ ] **【低】** HANDOFF 说"753 测试"与本会话收集一致（可信）；HANDOFF P0 多行业压测、P3 CI 仍未做。

---

## 12. 建议修复顺序

| 优先级 | 条目 | 理由 |
|---|---|---|
| P0 | §1.1 误报链（质量门禁+关键科目缺失跳过）、§2 金额/表头解析鲁棒化 | 斩断假"不通过"，P1 红线 |
| P0 | §1.2 阈值容差参数化、§9 verify_export 修复、§10 fsa.spec 恢复 pdfplumber、§11 文档同步 37 条 | 立即可修、影响可信度 |
| P1 | §1.3 SCE trace、§1.4 同类型覆盖、§2 报表识别（股东权益变动表/双行表头/SCE 矩阵） | 真实场景覆盖率 |
| P1 | §7 主线程阻塞改 QThread、AI 诊断走配置 provider、§8 updater sha256+原子写 | 体验与安全 |
| P2 | §4 存储事务/容差校验、§5 宽 catch、§6 agent→gui 分层、§7 监听器泄漏、跳过状态灰显 | 合规与工程质量 |
| P3 | CI、llm_client/debate/fallback 补测试、多行业真实年报压测（HANDOFF P0） | 长期保障 |

---

*本报告所有行号以 `7419c68` 工作区文件为准；如另一台电脑已有修改，请以勾选框逐项核对后更新本文件。*
