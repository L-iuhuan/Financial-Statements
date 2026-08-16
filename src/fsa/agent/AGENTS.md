# agent — LLM 诊断

## OVERVIEW
接收 `ValidationResult` → 输出诊断建议（只读校验数据，禁止修改）。LLM 不可用时全链路确定性回退，用户永远得到中文答复。

## FILES

| 文件 | 职责 |
|---|---|
| `llm_client.py` | `LLMClient` Protocol + `OllamaProvider`/`OpenAICompatProvider` + `create_llm_client` 工厂；流式分块 + 离线/远程守卫；**仅用标准库 urllib，不引 requests** |
| `agent_loop.py` | 工具调用循环 ≤5 轮；六步推理系统提示；支持取消事件与流式输出 |
| `sanitize.py` | 输入消毒/防注入围栏/路径脱敏——外部输入进 prompt 前必过 |
| `tools.py` | 9 个只读工具（JSON schema + handler），只读 `AppState` |
| `diagnosis.py` | `DiagnosisEngine` 确定性五段式诊断；LLM 增强失败 → 回退 `diagnose()` |
| `fallback.py` | 无 LLM 应答：规则编号正则（`BS-BAL-001` 型）→ 规则定义；关键词意图 → 知识检索 |
| `debate.py` | 分析师 → 反方审计师 → 裁判三轮辩论（带阶段提示） |
| `knowledge.py` | 内置 CAS 条目 + 外部文档（`resources/knowledge/*.md`：CAS 准则原文 + 陈奕蔚答疑，1400 字符切块、120 重叠）关键词打分检索（无向量库）；**fsa.spec 未打包 knowledge 目录——冻结版静默无外部文档** |
| `ollama_client.py` | 旧版 `/api/generate` 客户端（遗留路径） |

## 调用链

ResultCard「AI 诊断」→ import_page.diagnose_requested → main_window_agent（`AgentWorker` 后台线程）→ `DiagnosisEngine`（LLMClient → Ollama → 纯规则）；抽屉自由提问 → `AgentLoop` 或 `fallback_answer`。

## INVARIANTS

- 工具全部只读：禁止在 `agent/` 修改校验结果或业务数据
- 任何 LLM 调用失败必须静默回退到确定性路径，不向用户抛技术异常
- 系统提示强制"先调用工具获取真实数据，不要臆测"
- 外部输入（用户提问/文件内容）进 prompt 前必须经 `sanitize.py` 消毒；输出含路径须脱敏
- provider 推断：URL 含 `localhost:11434` → Ollama；含 `/v1` → OpenAI 兼容
- AI 输出须标注"仅供参考"（LLM 可能误报根因，P1）

## 已知偏差

- `OllamaError`/`LLMError`/`UpdateError` 直接继承 `Exception`，未继承 `FSAError`（与根 AGENTS.md §3.4 冲突，新代码应按 FSAError 编写）
- 运行态 agent→gui 依赖两处：`agent_loop.py`（`from fsa.gui.app_state import AppState`）、`fallback.py`（AppState + `formula_display`）；`tools.py` 仅 TYPE_CHECKING（合规）。`app_state` 不 import agent，无环
