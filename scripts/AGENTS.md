# scripts — 手动验证与运维脚本

## OVERVIEW

24 个脚本（19 .py + 4 .ps1 + 1 历史 txt）：pytest 覆盖不到的焦点验证、性能基准、真实语料构建、知识库工具、打包发布。**非应用运行时代码**，各自独立可跑。

## 分类索引

| 类别 | 脚本 |
|---|---|
| 发布门禁 | `validate_real_data.py` — 真实年报跑全部 42 条规则，**0 fail 0 error**，exit 0/1；改规则库或发布前必跑 |
| 模块验证 | `verify_{agent,pdf_import,export,ollama,sce,update,diagnosis,theme,w3}.py`；`ux_shots.py`（全页面双主题截图到 `ux_shots/`） |
| 性能基准 | `benchmark_app.py`（导入+校验/主题切换/历史加载）；`benchmark_import.py`（默认 10 万行序时账导入计时）——发布前人工跑 |
| 真实语料 | `build_real_corpus.py`（akshare 拉 18 家 A 股年报 + manifest.json；**akshare 为脚本级依赖**，需 `pip install akshare`，不入 pyproject）→ `validate_corpus.py`（按 manifest 回归，白名单判定）→ `update_manifest_whitelist.py`（人工审查写入白名单） |
| 知识库 | `collect_cas_sources.py`（CAS 准则原文 → MD）；`ingest_knowledge_ocrflow.py`（PDF/docx 经 OCRFlow MCP → MD）——均写入 `resources/knowledge/` |
| 打包发布 | `build_installer.ps1` → `sign_build.ps1`（Authenticode，见 docs/RELEASE_AND_SIGNING.md）→ `smoke_package.ps1`（启动 exe 确认存活 + SQLite 已建） |
| 资产/历史 | `generate_logo.py`（需 cairosvg+PIL，**均不在 pyproject 依赖**，按需自装）；`commit_v0.4.0.ps1` + `.txt`（一次性发布脚本，**勿复用**） |

## 约定

- **根定位**：一律 `Path(__file__).resolve().parent.parent`
- **import fsa 靠 editable install**（`pip install -e ".[dev]"`）；仅 3 个脚本显式 `sys.path.insert(0, 项目根)`（validate_real_data / validate_corpus / verify_export），validate_corpus 需 `# ruff: noqa: E402`
- **须在项目根目录运行**的脚本（相对路径）：`verify_sce.py`（fixture 路径）、`ux_shots.py`（写 `ux_shots/`）、`benchmark_app.py`（相对读规则库）；4 个 .ps1 自 `Set-Location $Root`，对 cwd 免疫
- **GUI 脚本**先设 `QT_QPA_PLATFORM=offscreen`（benchmark_app/ux_shots/verify_theme/verify_w3）；中文输出脚本 `sys.stdout.reconfigure(encoding='utf-8')`（verify_sce/verify_theme/ux_shots/build_real_corpus）
- **依赖真实年报 fixture**（git 忽略，需手动放置或 build_real_corpus 生成）：validate_real_data / validate_corpus / verify_pdf_import / verify_export / verify_sce / verify_w3 / ux_shots
- 合规红线：真实年报数据**严禁提交 git**（tests/fixtures/real_reports/ 已 gitignore）

## resources/knowledge/ 联动（本目录脚本的产出）

- 两种来源格式：CAS 原文类（`# 外部知识文档` + `来源: <url>` 头，collect_cas_sources 产出）与陈奕蔚答疑类（YAML frontmatter + 正文，ingest_knowledge_ocrflow/人工投入）
- 唯一消费者 `agent/knowledge.py::_external_knowledge()`：遍历 `*.md|txt` → 去 HTML → 段落切块（1400 字符/120 重叠）→ 关键词打分检索；**frontmatter 不结构化解析，当普通文本**
- **打包缺口**：fsa.spec datas 不含 knowledge 目录——冻结模式静默返回空（不报错），即打包版无外部文档知识。若需随包发布须改 fsa.spec
