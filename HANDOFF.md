# 财务报表勾稽校验系统 — 开发交接文档

> 更新日期: 2026-08-13
> 用途: 跨机器开发的交接与续作指南
> 当前版本: v0.1.0 (MVP+), 规则库 CAS v1.2.0 (37 条)

---

## 一、快速开始 (新机器)

```bash
# 1. 克隆
git clone git@github.com:L-iuhuan/Financial-Statements.git
cd Financial-Statements

# 2. 安装依赖 (Python 3.11+)
pip install -e ".[dev]"

# 3. 启动
python -m fsa

# 4. 测试
python -m pytest -q          # 753 个测试
python -m ruff check src/    # 静态检查
```

**注意**: 推送用 SSH (`git@github.com:...`)。新机器需生成 SSH 密钥并把公钥加到 GitHub
(Settings → SSH and GPG keys)。HTTPS 在国内网络下连不通。

---

## 二、当前完成状态 (全部已验证)

### 核心引擎
- [x] 37 条 CAS 勾稽规则 (v1.2.0), 茅台/格力真实年报 0 失败 0 异常
- [x] 双金额列引擎 (期末/期初 _ending/_beginning 变量)
- [x] 补充资料提取 (cf_notes_ 前缀, 茅台 CF 22→40 项)
- [x] 科目追溯 trace (行列定位, P3 可审计)

### 数据导入
- [x] Excel (.xlsx/.xls) 三大主表（.xls 走 pandas+xlrd）
- [x] 表头自动定位 + 多层表头捕获 + 重复列名去重
- [x] 资产负债表左右双栏 / 期间列模式识别 / 项目名后缀清洗
- [x] PDF 导入 (pdfplumber, RawSheetData 兼容)
- [x] 所有者权益变动表 SCE (矩阵解析)

### 导出
- [x] Excel 审计底稿 (汇总+明细+科目追溯三表)

### AI 助手
- [x] 规则化诊断引擎 (确定性兜底)
- [x] AgentLoop: 多轮对话 + 9 工具调用 + 分步推理
- [x] Provider 抽象: Ollama / OpenAI 兼容 (公司本地/在线全参数模型)
- [x] DebateEngine: 多模型辩论 (分析师/反方/裁判)
- [x] 智能回退 (无 LLM 时用知识库+规则查询回答)
- [x] 会话管理: 新建/切换/清空/持久化/自动重命名

### UI/UX
- [x] 深青玉配色 + 天平 logo + FluentIcon 图标 (无 Emoji)
- [x] 深色主题 (完整生效)
- [x] 规则卡片重设计 + 自定义规则 (增删/持久化/公式校验)
- [x] 公式中文化显示 (tooltip 保留英文)
- [x] 设置页: 全项可用+持久化+对齐+恢复默认+自动保存提示
- [x] FAB 仅工作区显示 + 角标 + 抽屉拖拽锚定右缘
- [x] 筛选闪动修复 + 输入框自动增高 + 建议气泡动态化+防抖

### 持久化
- [x] SQLite WAL (历史/会话/容差覆写)
- [x] QSettings (主题/容差/阈值/更新地址/LLM配置)
- [x] 自定义规则 custom_rules.json

### 打包
- [x] PyInstaller 137MB exe (已排除 ML 重包)
- [x] Inno Setup 安装脚本 installer.iss
- [x] 一键构建 scripts/build_installer.ps1

### 测试
- [x] 753 测试全绿 (含 20 个压力/边界测试, 48 个 GUI 功能测试)
- [x] TEST_PLAN.md 测试方案 (9 模块 48 用例)

---

## 三、接下来要做的 (按优先级)

### P0 — 真实场景验证 (最优先)
- [ ] **多行业真实年报压测**: 当前仅茅台+格力两份。需收集银行/地产/制造业等不同
  行业年报 (格式差异大), 放入 `tests/fixtures/real_reports/` 后运行
  `python scripts/validate_real_data.py`, 暴露不同格式的识别/校验边界问题。
- [x] **Excel COM 读取适配器**: 公司 DLP 加密环境下 openpyxl/xlrd 无法读文件，
  Excel 本体可透明解密；已实现 `read_excel_com`，常规读取失败时自动回退。
- [x] **明细数据模型（附表 2）**: 余额表/序时账/现金流量明细模型、按表头识别导入、
  L2 首批检查（凭证平衡、现金流明细↔主表/序时账、余额表↔资产负债表）已实现；
  L4 现金流分类规则库（8 条）与覆盖率检查已实现（凭证级复核式提示）；
  往来重分类等附表 3~6 仍待扩展。

### P1 — 功能增强
- [ ] **容差持久化的默认值回写**: 规则页改容差已存 SQLite, 但"恢复默认"未重置规则容差
- [ ] **自定义规则的公式变量联想**: 新增规则时输入变量名自动补全
- [ ] **AgentLoop 深度集成**: 把 DebateEngine 的"深度辩论"按钮接入规则卡片(已部分接入),
  优化辩论结果在抽屉中的展示 (目前是三长段文本, 可分 tab/折叠)
- [ ] **知识库扩充**: knowledge.py 目前是手工摘要, 可接入真实 CAS 准则文档做检索

### P2 — V1.5 (大功能, 需排期)
- [ ] **报表自动生成**: 从余额表+序时账自动生成三大报表 + 审计底稿
- [ ] **附注/NOTES 规则**: 需重新设计公式 (当前是占位符)

### P3 — 工程化
- [ ] **CI/CD**: GitHub Actions 跑测试 (注意国内网络, 可能需镜像)
- [ ] **真实 Ollama/公司模型联调**: 当前用 DeepSeek 在线 API 测过, 本地 Ollama 未实测

---

## 四、目录结构

```
├── src/fsa/
│   ├── core/           # 引擎+模型+导入+导出
│   │   ├── engine/     # 校验引擎 (evaluator/runner/registry/comparator)
│   │   ├── importer/   # 导入 (excel/pdf/sce/name_mapper)
│   │   ├── exporter/   # Excel 底稿导出
│   │   └── models/     # 数据模型 (report/result/rule)
│   ├── agent/          # AI 助手 (agent_loop/debate/diagnosis/tools/knowledge/fallback/llm_client)
│   ├── services/       # 校验服务编排
│   ├── storage/        # SQLite (database/history_repo/chat_repo/override_repo)
│   ├── updater/        # 自动更新
│   └── gui/            # PySide6 界面
├── tests/              # 753 测试
├── scripts/            # 验证/构建脚本
├── resources/          # logo/图标
├── demo/               # demo.html 设计稿
├── cas_gouji_rule_library.json   # 规则库 v1.2.0
└── fsa.spec / installer.iss      # 打包配置
```

---

## 五、关键约束 (AGENTS.md 原则, 必须遵守)

- **P1 宁可漏报不可误报**: 缺数据时规则跳过而非误报
- **P2 确定性**: 同输入同输出, 校验不依赖随机/时间/网络
- **P3 可审计可溯源**: 每条结果能追溯到科目+行列
- **P4 面向财务用户**: 中文文案, 不用技术术语
- **P6 中文输出**: 所有面向用户的输出必须中文
- 全类型注解, 函数≤50行, 文件≤250行, 无 `as any`/`# type: ignore`/空 catch

---

## 六、环境备忘

- **LLM 测试**: 环境变量 `DEEPSEEK_API_KEY` (在线 DeepSeek API, OpenAI 兼容)
- **GitHub 推送**: 用 SSH, 国内 HTTPS 不通
- **打包**: `powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1`
- **Inno Setup**: 需单独装 Inno Setup 6 才能编译安装器 (当前只出 exe)
