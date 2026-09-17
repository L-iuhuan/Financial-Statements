"""规则结果的「大白话」说明 — 面向财务用户的解读文案 (P4/P6)。

背景 (用户反馈 2026-09-17): 校验明细里"为何有差、为何警告"看不懂——旧消息
直接展示公式/内部逻辑。本模块为每条规则提供小白可读的解读:

- 【级别说明】该级别代表什么 (错误必须改 / 警告是分析性提示);
- 【为什么关注】这条勾稽的业务含义;
- 【常见原因】为何会出现差异 (优先给最常见、可自查的原因);
- 【建议】下一步核对动作;
- 阈值类规则另附【实际值】指标 (用本次数据实时算出, 如 资产负债率 = 88.0%)。

消息构建时仅对"未通过/未满足"结果追加 (通过结果不追加, 避免噪音)。
本文件行数主要来自规则文案数据 (与 name_mapper 映射表同类, 属数据密集型),
不按纯代码行数拆分。
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from fsa.core.engine.evaluator import ExpressionEvaluator
from fsa.core.exceptions import EvaluationError


@dataclass(frozen=True)
class RuleHint:
    """一条规则的小白解读文案。"""

    why: str  # 为什么关注 (业务含义)
    causes: str = ""  # 常见原因 (为何会有差)
    advice: str = ""  # 建议核对 (下一步动作)
    metric_expr: str = ""  # 阈值类规则: 实际值指标表达式 (与公式同一变量词汇)
    metric_label: str = ""  # 指标中文名, 如 "资产负债率"
    metric_format: str = "number"  # percent / currency / number
    criterion_var: str = ""  # 判断标准取用的阈值变量名 (按行业动态显示, 如 "dar_threshold")
    criterion_format: str = "percent"  # 阈值变量显示格式: percent / number
    # 判断方向 (显式声明, 勿依赖格式隐式约定——oracle 评审 2026-09-17 阻断项:
    # LR-SALES-001 收现比为「不低于」阈值, 此前按 percent→「不超过」渲染, 方向反了):
    #   "max" -> 不超过阈值;  "min" -> 不低于阈值;  "" -> 仅展示 criterion_text
    criterion_direction: str = ""
    criterion_text: str = ""  # 判断标准静态文案 (无行业变量时使用)


# 各严重级别的含义 (回答"为何警告": 异常 ≠ 做错账)
SEVERITY_MEANINGS: dict[str, str] = {
    "error": "必须改正 — 会计基本勾稽关系被破坏，通常属于报表编制或取数错误。",
    "warning": "提示性检查 — 异常不等于做错账，属于分析程序中的异常信号，需结合业务解释。",
    "info": "供参考 — 不影响结论，建议关注。",
}

RULE_HINTS: dict[str, RuleHint] = {
    # ── A/表内平衡 (资产负债表) ────────────────────────────────
    "BS-BAL-001": RuleHint(
        why="会计恒等式「资产 = 负债 + 所有者权益」是资产负债表成立的根本。",
        causes="① 报表未经结转/过账；② 手工填写错误；③ 导入时漏行或串行；④ 科目余额表与报表口径不一致。",
        advice="先看两侧金额差多少；若差异恰为某一科目的金额，多为漏行，重新导入完整报表即可。",
    ),
    "BS-BAL-002": RuleHint(
        why="资产分类小计（流动+非流动）必须等于资产总计。",
        causes="① 有资产项目漏填；② 汇总行未包含某明细行；③ 模板改动导致部分行未识别。",
        advice="逐项核对资产类明细行与合计数，找出未纳入合计的项目。",
    ),
    "BS-BAL-003": RuleHint(
        why="负债分类小计（流动+非流动）必须等于负债合计。",
        causes="① 负债项目漏填；② 一年内到期的非流动负债等归类行未纳入合计。",
        advice="逐项核对负债类明细行与合计数。",
    ),
    "BS-BAL-004": RuleHint(
        why="所有者权益各组成项（实收资本、资本公积、盈余公积、未分配利润等）合计应等于权益合计。",
        causes="① 少数股东权益或专项储备等行漏填；② 库存股符号方向错误（应为负数抵减）。",
        advice="核对权益各组成行是否齐全、符号是否正确。",
    ),
    # ── B/表内平衡 (利润表) ────────────────────────────────────
    "IS-BAL-001": RuleHint(
        why="营业利润由收入、成本、费用与各项收益按固定结构构成，是利润表的核心小计。",
        causes="① 费用/收益项目漏行；② 信用减值、资产减值等行符号方向错误。",
        advice="按利润表自上而下逐行核对，找出未参与营业利润计算的项目。",
    ),
    "IS-BAL-002": RuleHint(
        why="利润总额 = 营业利润 + 营业外收入 − 营业外支出。",
        causes="① 营业外收支漏填；② 政府补助等错放项目。",
        advice="核对营业外收入/支出两行金额是否完整。",
    ),
    "IS-BAL-003": RuleHint(
        why="净利润 = 利润总额 − 所得税费用。",
        causes="① 所得税费用漏填；② 利润总额本身有误（先修 IS-BAL-002）。",
        advice="核对所得税费用行；若利润总额已不平，先解决上游规则。",
    ),
    "IS-BAL-004": RuleHint(
        why="营业收入（含税口径的报表行）应等于主营业务收入 + 其他业务收入。",
        causes="① 其他业务收入漏填；② 收入分类归属不同。",
        advice="核对主营/其他业务收入两行。",
    ),
    "IS-BAL-005": RuleHint(
        why="综合收益总额 = 净利润 + 其他综合收益（税后）。",
        causes="① 其他综合收益漏填；② 税后金额未用税后口径。",
        advice="核对其他综合收益行（税后口径）。",
    ),
    # ── 现金流量表 ────────────────────────────────────────────
    "CF-BAL-001": RuleHint(
        why="现金及现金等价物净增加额 = 经营 + 投资 + 筹资净额 + 汇率影响。",
        causes="① 三类活动净额或汇率影响额漏填；② 正表小计行计算错误。",
        advice="核对三类活动净额与汇率影响额，先保证各自小计正确。",
    ),
    "CF-BAL-002": RuleHint(
        why="经营活动净额在正表（直接法）与附注（间接法）应一致，两者互相印证。",
        causes="① 附注未填或未同步更新；② 间接法调节项遗漏。",
        advice="若正表无误，多为附注漏填/未更新；以正表为基础核对附注。",
    ),
    "CF-BAL-003": RuleHint(
        why="正表现金净变动应与附注（补充资料）的现金净变动一致。",
        causes="① 附注金额未同步；② 附注口径差异（如含受限资金）。",
        advice="核对附注「现金及现金等价物净增加额」与正表是否同口径。",
    ),
    "CF-BAL-004": RuleHint(
        why="期末现金 = 期初现金 + 本期净增加，是现金项目的滚动勾稽。",
        causes="① 期初/期末数取错列；② 净增加额本身有误（先修 CF-BAL-001）。",
        advice="核对期初、期末两列取数是否来自正确表页。",
    ),
    # ── 所有者权益变动表 ──────────────────────────────────────
    "SCE-BAL-001": RuleHint(
        why="权益变动表每个组成部分：期初余额 ± 本期变动 = 期末余额（横向勾稽）。",
        causes="① 变动列漏填（如综合收益、股东投入）；② 期末列取数错误。",
        advice="按行核对「期初 + 变动 = 期末」，找出未反映的变动。",
    ),
    "SCE-BAL-002": RuleHint(
        why="合并口径下：所有者权益合计 = 归属于母公司 + 少数股东权益。",
        causes="① 少数股东权益未列示；② 仅单体报表却按合并口径取数。",
        advice="核对少数股东权益列；单体报表不适用本规则。",
    ),
    # ── 表间勾稽 ──────────────────────────────────────────────
    "BS-IS-001": RuleHint(
        why="未分配利润期末−期初 应等于 净利润−分红−提取盈余公积+前期调整（表间核心勾稽）。",
        causes="① 分红或提取盈余公积未在变动中反映；② 前期调整未填；③ 未分配利润取数错列。",
        advice="按「净利润−分红−盈余公积提取」自行验算；差异不大时先确认是否有分红/调整事项。",
    ),
    "IS-CF-001": RuleHint(
        why="现金流量表附注的净利润应与利润表净利润一致（间接法起点）。",
        causes="① 附注未同步利润表；② 附注填了母公司口径而利润表为合并口径。",
        advice="核对两处净利润口径与金额是否一致。",
    ),
    "IS-CF-002": RuleHint(
        why="附注减值项目（资产减值+信用减值）应与利润表相关科目对应（损失以负数列示）。",
        causes="① 附注减值漏填；② 符号方向不一致（附注取负、利润表取正或反之）。",
        advice="核对两表减值金额与符号方向。",
    ),
    "SCE-IS-001": RuleHint(
        why="权益变动表的净利润（归属母公司）应等于利润表的归属净利润。",
        causes="① 两表口径不同（单体 vs 合并）；② 变动表净利润列漏填。",
        advice="核对两表净利润金额与口径。",
    ),
    "SCE-IS-002": RuleHint(
        why="权益变动表的其他综合收益应等于利润表其他综合收益（税后）。",
        causes="① 变动表漏填 OCI；② 税前/税后口径混用。",
        advice="核对两表其他综合收益金额。",
    ),
    "SCE-IS-003": RuleHint(
        why="权益变动表的综合收益总额应等于利润表的综合收益总额。",
        causes="① 净利润或 OCI 单项有误（先修 SCE-IS-001/002）；② 变动表合计行漏填。",
        advice="先核对净利润与 OCI 两行，再看合计。",
    ),
    "SCE-BS-001": RuleHint(
        why="权益变动表期末实收资本（股本）应等于资产负债表实收资本。",
        causes="① 期末列取数错误；② 本期增资未在变动表反映。",
        advice="核对变动表期末列与资产负债表。",
    ),
    "SCE-BS-002": RuleHint(
        why="权益变动表期末资本公积应等于资产负债表资本公积。",
        causes="① 期末列取数错误；② 资本溢价变动未反映。",
        advice="核对变动表期末列与资产负债表。",
    ),
    "SCE-BS-003": RuleHint(
        why="权益变动表期末盈余公积应等于资产负债表盈余公积。",
        causes="① 提取盈余公积未在变动表反映；② 期末列取数错误。",
        advice="核对提取金额与期末列。",
    ),
    "SCE-BS-004": RuleHint(
        why="权益变动表期末未分配利润应等于资产负债表未分配利润。",
        causes="① 分配/提取未反映；② 期末列取数错误。",
        advice="结合 BS-IS-001 一并核对。",
    ),
    "SCE-BS-005": RuleHint(
        why="权益变动表期末权益合计应等于资产负债表所有者权益合计。",
        causes="① 期末列漏填或串行；② 少数股东权益口径不一致。",
        advice="核对变动表合计行与资产负债表权益合计。",
    ),
    "IS-TAX-001": RuleHint(
        why="所得税费用 = 当期所得税 + 递延所得税变动。",
        causes="① 递延所得税未填；② 递延资产/负债变动方向颠倒。",
        advice="核对递延所得税资产/负债变动与当期所得税加总。",
    ),
    "NOTES-001": RuleHint(
        why="附注明细合计应等于主表对应项目（附注是主表的展开）。",
        causes="① 附注明细漏行；② 附注与主表口径/期间不一致。",
        advice="将附注明细逐项加总后与主表项目比对，找出漏项。",
    ),
    "NOTES-002": RuleHint(
        why="应收账款附注（账龄/坏账准备）计算结果应与主表应收账款余额衔接。",
        causes="① 账龄划分与坏账计提比例不一致；② 附注未含某类应收。",
        advice="按「余额−坏账准备=净额」自行验算附注。",
    ),
    # ── C/逻辑合理性 (分析性提示) ─────────────────────────────
    "LR-GM-001": RuleHint(
        why="毛利率反映产品盈利能力；低于 0% 或高于 100% 通常是成本归类或收入确认的信号。",
        causes="① 成本与收入不匹配（某类成本未归集）；② 行业特性（清仓、困境）；③ 季节性波动。",
        advice="结合业务解释即可；本项为分析性提示，不直接定性为错误。",
        metric_expr="(revenue - operating_cost) / revenue",
        metric_label="毛利率",
        metric_format="percent",
        criterion_text="应在 0%～100% 区间内",
    ),
    "LR-GM-002": RuleHint(
        why="毛利率同比大幅波动往往暗示收入/成本跨期或分类变化。",
        causes="① 产品结构或售价变化；② 成本结转口径变化；③ 上期数据错误。",
        advice="对比两期收入、成本结构，确认波动是否有业务支撑。",
        metric_expr=(
            "(revenue - operating_cost) / revenue"
            " - (revenue_beginning - operating_cost_beginning) / revenue_beginning"
        ),
        metric_label="毛利率同比变动",
        metric_format="percent",
        criterion_var="gm_yoy_threshold",
        criterion_direction="max",
    ),
    "LR-DAR-001": RuleHint(
        why="资产负债率越高，偿债压力越大；超出行业常见水平时需关注负债完整性。",
        causes="① 借款/应付增加；② 资产减少；③ 行业特性（金融、地产杠杆天然偏高）。",
        advice="核对长短期借款与资产科目；特殊行业可在「设置」中切换行业阈值后重算。",
        metric_expr="liability_total / asset_total",
        metric_label="资产负债率",
        metric_format="percent",
        criterion_var="dar_threshold",
        criterion_direction="max",
    ),
    "LR-OCF-001": RuleHint(
        why="净利润为正但经营现金流为负，说明利润的「含金量」存疑（赊销多、存货积压）。",
        causes="① 应收账款、存货大幅增加；② 收入确认时点早于回款；③ 一次性非现金收益。",
        advice="对比应收账款/存货变动与收入增速，确认现金流滞后是否合理。",
        metric_expr="operating_net",
        metric_label="经营活动净现金流量",
        metric_format="currency",
        criterion_text="净利润为正时，经营活动净现金流量应为正",
    ),
    "LR-ART-001": RuleHint(
        why="应收账款占营业收入比例过高，说明回款慢、坏账风险上升。",
        causes="① 放宽信用政策；② 关联方或大客户赊销；③ 收入确认提前。",
        advice="关注账龄结构与坏账准备计提是否充分。",
        metric_expr="accounts_receivable / revenue",
        metric_label="应收账款占营业收入比",
        metric_format="percent",
        criterion_var="ar_to_revenue_threshold",
        criterion_direction="max",
    ),
    "LR-FLUC-001": RuleHint(
        why="营业收入同比波动超过三成，需确认是否有跨期确认或数据错取。",
        causes="① 新增大客户或业务收缩；② 收入跨期；③ 合并范围变化。",
        advice="对比两期收入明细，确认波动有业务依据；高增长企业可在设置中放宽阈值。",
        metric_expr="(revenue - revenue_beginning) / revenue_beginning",
        metric_label="营业收入同比变动",
        metric_format="percent",
        criterion_var="yoy_fluctuation_threshold",
        criterion_direction="max",
    ),
    "LR-RE-001": RuleHint(
        why="应收账款贷方余额应重分类至预收/合同负债；应付账款借方余额应重分类至预付。",
        causes="① 收付款超付形成反向余额；② 科目挂账方向错误。",
        advice="在报表中重分类列示；金额较小的可直接沿用。",
    ),
    "LR-RE-002": RuleHint(
        why="其他应收款/其他应付款出现负数余额，说明挂账方向存在问题。",
        causes="① 收付超额；② 科目使用不当（应走往来或借款）。",
        advice="核对该明细的原始凭证，必要时重分类。",
    ),
    "LR-SALES-001": RuleHint(
        why="销售收现比过低说明收入的回款质量差，或存在大额赊销。",
        causes="① 应收账款激增；② 票据结算占比高；③ 收入虚增。",
        advice="核对应收/票据与收入变动是否匹配。",
        metric_expr="cash_received_from_sales / revenue",
        metric_label="销售收现比",
        metric_format="percent",
        criterion_var="sales_cash_ratio_threshold",
        criterion_direction="min",
    ),
    "LR-QUICK-001": RuleHint(
        why="流动比率低于 1 说明流动资产不足以覆盖流动负债，短期偿付有压力。",
        causes="① 流动负债集中到期；② 存货/应收占比高但变现慢。",
        advice="结合速动资产与债务到期结构评估；零售等负现金周期行业可放宽。",
        metric_expr="current_assets / current_liabilities",
        metric_label="流动比率",
        metric_format="number",
        criterion_var="current_ratio_threshold",
        criterion_format="number",
        criterion_direction="min",
    ),
    "LR-OCF-002": RuleHint(
        why="经营活动现金流连续为负，是企业持续「失血」的信号。",
        causes="① 业务扩张期垫资；② 回款恶化；③ 亏损经营。",
        advice="结合行业与融资能力评估持续经营风险；如有融资安排需在报告期后事项披露。",
        metric_expr="operating_net",
        metric_label="本期经营活动净现金流量",
        metric_format="currency",
        criterion_text="至少有一期经营活动净现金流量为正",
    ),
    "LR-NONREC-001": RuleHint(
        why="扣非净利润为负但净利润为正，说明盈利依赖一次性收益。",
        causes="① 政府补助/资产处置收益；② 投资收益贡献大。",
        advice="关注非经常性损益的可持续性与披露完整性。",
        metric_expr="non_recurring_net_profit",
        metric_label="扣除非经常性损益后净利润",
        metric_format="currency",
        criterion_text="应为正（盈利不依赖一次性收益）",
    ),
    "IS-LR-001": RuleHint(
        why="信用/资产减值损失通常以负数（抵减）或费用列示；出现正数可能列示方向有误。",
        causes="① 符号方向填反；② 转回冲销未用负数表达。",
        advice="核对减值损失行的列示方向与金额。",
    ),
    # ── 明细勾稽 (L2/L4) ──────────────────────────────────────
    "JNL-BAL-001": RuleHint(
        why="每张记账凭证借贷必须相等，这是账务数据可信的前提。",
        causes="① 源数据凭证未平衡；② 金额列错位/串列；③ 多借多贷拆分错误。",
        advice="按提示的凭证号在序时账中复核该凭证的借贷方金额。",
    ),
    "CF-DTL-001": RuleHint(
        why="现金流量明细（附表）各项目金额应与现金流量表对应项目一致。",
        causes="① 明细漏行；② 明细与主表口径/期间不一致。",
        advice="按项目名称逐项比对明细合计与主表金额。",
    ),
    "CF-JNL-001": RuleHint(
        why="现金流量明细应与序时账中的现金类科目发生额相互印证。",
        causes="① 明细归类与账务不符；② 部分凭证未纳入明细。",
        advice="核对差异涉及的项目与凭证笔数，检查归类是否正确。",
    ),
    "TB-BS-001": RuleHint(
        why="科目余额表是报表的原始依据；按映射口径汇总后应与资产负债表项目一致。",
        causes="① 报表调整未回写余额表；② 映射关系未覆盖某科目；③ 口径差异（净额/总额）。",
        advice="核对差异科目的余额与报表列示，确认映射口径是否适用。",
    ),
    "CF-CLS-001": RuleHint(
        why="「销售商品收到的现金」的对方科目通常为应收/收入/预收类；异常对手方可能是分类错误。",
        causes="① 现金流项目归类错误；② 代收代付混入；③ 往来科目未清理。",
        advice="抽查提示的凭证，核对对方科目与该笔款项的业务实质。",
    ),
    "CF-CLS-002": RuleHint(
        why="「购买商品支付的现金」的对方科目通常为应付/存货/成本类；异常对手方可能是分类错误。",
        causes="① 现金流项目归类错误；② 费用性支出误入采购付款。",
        advice="抽查提示的凭证，核对对方科目与业务实质。",
    ),
    "CF-CLS-003": RuleHint(
        why="「支付给职工及为职工支付的现金」的对方科目通常为应付职工薪酬/个税等。",
        causes="① 薪酬支付误计其他项目；② 劳务费分类不当。",
        advice="抽查提示的凭证，确认是否属职工薪酬性质。",
    ),
    "CF-CLS-004": RuleHint(
        why="「支付的各项税费」的对方科目通常为应交税费/税金及附加/所得税。",
        causes="① 税费与往来混记；② 代扣代缴项目分类错误。",
        advice="抽查提示的凭证，核对税种与对方科目。",
    ),
    "CF-CLS-005": RuleHint(
        why="「收回投资收到的现金」的对方科目通常为投资类科目；异常对手方可能是分类错误。",
        causes="① 投资收回与经营收现混淆；② 理财赎回未正确归类。",
        advice="抽查提示的凭证，核对投资标的与金额。",
    ),
    "CF-CLS-006": RuleHint(
        why="「投资支付的现金」的对方科目通常为投资类科目；异常对手方可能是分类错误。",
        causes="① 理财/股权投资误入经营或筹资；② 资本性支出与投资支付混淆。",
        advice="抽查提示的凭证，核对投资性质（理财/股权/债权）。",
    ),
    "CF-CLS-007": RuleHint(
        why="「取得投资收益收到的现金」的对方科目通常为投资收益/应收股利利息。",
        causes="① 投资收益与投资收回混淆；② 利息收入归类不当。",
        advice="抽查提示的凭证，核对收益性质与金额。",
    ),
    "CF-CLS-008": RuleHint(
        why="「购建固定资产等支付的现金」的对方科目通常为在建工程/固定资产/无形资产。",
        causes="① 资本性支出与经营支出混淆；② 预付工程款归类。",
        advice="抽查提示的凭证，核对资产购建性质。",
    ),
    "CF-CLS-901": RuleHint(
        why="该检查用于确认现金类科目覆盖是否完整；未覆盖说明部分凭证未参与分类检查。",
        causes="① 现金等价物科目未配置；② 新科目未纳入。",
        advice="如公司有新增现金类科目，在设置中补充现金等价物科目编码。",
    ),
    "RC-001": RuleHint(
        why="应收账款贷方/应付账款借方余额应重分类（预收/预付），报表列示才真实。",
        causes="① 超付/预收挂错科目；② 未做重分类调整。",
        advice="按提示科目在报表中重分类列示。",
    ),
    "RC-002": RuleHint(
        why="其他应收款/其他应付款负数余额应重分类列示。",
        causes="① 收付超额；② 科目使用不当。",
        advice="核对原始凭证，必要时重分类。",
    ),
    "RP-001": RuleHint(
        why="关联方采购明细（附表4）各用途分类合计应与采购总额一致，并与账务衔接。",
        causes="① 用途分类漏项/重复；② 与序时账口径不一致。",
        advice="核对各用途列合计与总额，逐行与账务比对。",
    ),
    "SAL-001": RuleHint(
        why="销售收入报表（附表5）收入与成本应匹配，毛利率异常需解释。",
        causes="① 成本未匹配结转；② 收入/成本跨期。",
        advice="核对收入成本配对情况与毛利异常行。",
    ),
    "SAL-002": RuleHint(
        why="销售收入明细合计应与利润表营业收入衔接。",
        causes="① 明细漏行；② 期间/口径不一致。",
        advice="将明细逐项加总后与利润表收入比对。",
    ),
    "ICF-001": RuleHint(
        why="内部交易现金流量明细应与现金流量表相关项目衔接，为合并抵销提供依据。",
        causes="① 内部交易未完整登记；② 与主表口径不一致。",
        advice="核对内部交易明细与主表对应项目金额。",
    ),
    "ICF-002": RuleHint(
        why="集团内一方「收到的现金」应等于另一方「支付的现金」（内部交易双边核对）。",
        causes="① 单边挂账（对方未登记）；② 双方分类不一致（经营/投资/筹资）；③ 金额或期间不一致。",
        advice="与对方主体核对同一笔交易的项目归类与金额；差异需在合并抵销前解决。",
    ),
    "RPS-001": RuleHint(
        why="一方采购应等于对方销售（关联方购销双边核对），是合并抵销的基础。",
        causes="① 单边确认（对方未入账）；② 含税/不含税口径不一致；③ 跨期确认；④ 集团内购销未同步。",
        advice="与对方主体核对合同、发票与入账期间；差异在合并抵销前解决。",
    ),
}


def format_hint_block(rule_id: str, severity: str) -> str:
    """生成追加到"未通过"消息后的解读说明 (未收录规则返回空串)。

    Args:
        rule_id: 规则编号
        severity: 严重级别字符串 ("error"/"warning"/"info")

    Returns:
        以换行开头的说明文本; 规则未收录或说明为空时返回空串
    """
    hint = RULE_HINTS.get(rule_id)
    lines: list[str] = []
    meaning = SEVERITY_MEANINGS.get(severity, "")
    if meaning:
        lines.append(f"【级别说明】{meaning}")
    if hint is not None:
        if hint.why:
            lines.append(f"【为什么关注】{hint.why}")
        if hint.causes:
            lines.append(f"【常见原因】{hint.causes}")
        if hint.advice:
            lines.append(f"【建议】{hint.advice}")
    if not lines:
        return ""
    return "\n\n" + "\n".join(lines)


def format_metric_line(
    rule_id: str,
    namespace: dict[str, float],
    threshold_vars: dict[str, float] | None = None,
) -> str:
    """计算阈值类规则的【实际值】行 (用本次数据实时算出)。

    Args:
        rule_id: 规则编号
        namespace: 规则求值命名空间 (变量 -> 数值)
        threshold_vars: 本次运行注入的行业阈值变量 (用于展示实际判断标准)

    Returns:
        以换行开头的指标文本, 如 "\\n【实际值】资产负债率 = 88.0%（判断标准：不超过 85%）";
        规则无指标表达式、表达式求值失败或结果非有限数时返回空串 (P1 不影响判定)
    """
    hint = RULE_HINTS.get(rule_id)
    if hint is None or not hint.metric_expr:
        return ""
    try:
        value = ExpressionEvaluator.evaluate(hint.metric_expr, namespace)
    except (EvaluationError, ArithmeticError, ValueError, TypeError, KeyError) as error:
        logger.debug(f"规则 {rule_id} 指标「{hint.metric_label}」计算失败, 跳过: {error}")
        return ""
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return ""
    if hint.metric_format == "percent":
        rendered = f"{value:.1%}"
    elif hint.metric_format == "currency":
        rendered = f"{value:,.2f} 元"
    else:
        rendered = f"{value:,.2f}"
    criterion = _render_criterion(hint, threshold_vars)
    suffix = f"（判断标准：{criterion}）" if criterion else ""
    return f"\n【实际值】{hint.metric_label} = {rendered}{suffix}"


def _render_criterion(hint: RuleHint, threshold_vars: dict[str, float] | None) -> str:
    """渲染判断标准: 优先按行业阈值变量动态取值, 否则用静态文案。

    方向由 criterion_direction 显式声明 ("max"=不超过 / "min"=不低于),
    不依赖 metric_format 隐式约定 (oracle 评审 2026-09-17: 隐式约定曾致
    LR-SALES-001 收现比方向渲染反了)。百分比阈值非整时保留一位小数
    (0.355 -> 35.5%), 保证展示与实际判定一致 (P3 可审计)。
    """
    if hint.criterion_var and threshold_vars and hint.criterion_var in threshold_vars:
        threshold = threshold_vars[hint.criterion_var]
        direction = (
            "不低于" if hint.criterion_direction == "min" else "不超过"
        ) if hint.criterion_direction else ""
        if hint.criterion_format == "number":
            rendered = f"{threshold:,.2f}"
        elif abs(threshold * 100 - round(threshold * 100)) < 1e-9:
            rendered = f"{threshold:.0%}"
        else:
            rendered = f"{threshold:.1%}"
        return f"{direction} {rendered}" if direction else rendered
    return hint.criterion_text
