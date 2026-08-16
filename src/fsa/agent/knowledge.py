"""财务知识库: CAS 准则要点 + 勾稽规则说明 + 软件使用手册。

为 Agent 的 search_knowledge 工具提供检索内容。
轻量实现: 内存中的关键词匹配检索 (无需向量库, 保护打包体积)。
"""

from __future__ import annotations

import html
import json
import re

from fsa.core.resources import resource_path

# 外部文档切块参数: 单块上限/块间重叠/单次检索输出上限
_CHUNK_MAX_CHARS = 1400
_CHUNK_OVERLAP_CHARS = 120
_SEARCH_OUTPUT_MAX_CHARS = 5200

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", flags=re.IGNORECASE | re.DOTALL)
_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n\s*\n+")

# 知识条目: (主题关键词, 内容)
_KNOWLEDGE: list[tuple[str, str]] = [
    (
        "勾稽关系",
        "勾稽关系是指财务报表各项目之间的内在逻辑对应关系。最基本的是会计恒等式: "
        "资产 = 负债 + 所有者权益。此外还包括: 报表内部的合计关系(流动+非流动=总计)、"
        "报表之间的勾稽(利润表净利润应等于权益变动表的未分配利润变动)、"
        "主表与附注的衔接。勾稽校验是审计的基本程序, 用于发现报表编制错误。",
    ),
    (
        "资产负债表 平衡",
        "资产负债表必须满足: 资产总计 = 负债合计 + 所有者权益合计。"
        "若不平衡, 常见原因: 科目取数错误、存在重复或遗漏科目、重分类调整未处理、"
        "合并抵销不完整。本软件的 BS-BAL-001 规则即校验此恒等式。",
    ),
    (
        "利润表 净利润 营业利润",
        "利润表多步式结构: 营业利润 = 营业总收入 - 营业总成本 + 其他收益 + 投资收益等; "
        "利润总额 = 营业利润 + 营业外收入 - 营业外支出; 净利润 = 利润总额 - 所得税费用。"
        "信用减值损失和资产减值损失以负数填列(损失为负)。",
    ),
    (
        "现金流量表 直接法 间接法",
        "现金流量表主表用直接法(经营/投资/筹资三活动), 补充资料用间接法"
        "(从净利润调节到经营净额)。现金净增加额 = 经营净额 + 投资净额 + 筹资净额 + 汇率变动影响。"
        "期末现金余额 = 期初余额 + 净增加额。",
    ),
    (
        "容差 精确 相对 阈值",
        "容差是校验允许的误差范围。精确容差(exact): 差额绝对值不超过容差(如0.01元); "
        "相对容差(relative): 差额占基准值的比例(如0.1%); 阈值(threshold): 判断条件是否满足"
        "(如资产负债率≤85%)。可在规则管理中为每条规则调整容差。",
    ),
    (
        "跳过 缺少数据",
        "某些规则显示'跳过'是因为报表中缺少该规则所需的数据。例如: 权益变动表规则需要"
        "导入所有者权益变动表; 期初期末衔接规则需要报表含期初数。跳过不算不通过, "
        "遵循'宁可漏报不可误报'原则——数据不足时宁可不校验, 也不误报。",
    ),
    (
        "导入 支持格式 Excel PDF",
        "本软件支持导入 Excel(.xlsx/.xls/.xlsm)、CSV 和 PDF 格式的财务报表。将文件拖拽到导入区即可。"
        "支持资产负债表、利润表、现金流量表、所有者权益变动表。"
        "导入后自动识别报表类型并提取标准科目。",
    ),
    (
        "导出 审计底稿",
        "校验完成后, 点击顶栏'导出底稿'或审计底稿页的'导出 Excel', "
        "可生成含校验汇总、校验明细、科目追溯、底稿说明四张表的审计底稿, 供人工复核。"
        "科目追溯表会标注每个科目来自原报表的第几行第几列。",
    ),
    (
        "新增规则 自定义规则",
        "在规则管理页点击'新增规则', 可用公式模板快速创建自定义校验规则, "
        "也可手动编写公式。公式用变量名引用科目(如 asset_total 表示资产总计), "
        "支持 == 平衡校验和 <=/>= 阈值校验。自定义规则保存在 custom_rules.json。",
    ),
    (
        "未识别 科目 映射",
        "导入时若某些科目未显示在识别结果中, 通常是因为: 科目名称与标准名称不一致"
        "(可在别名映射中补充)、属于'其中:'明细行、或非标准科目。未识别科目不参与校验, "
        "不影响已识别科目的勾稽校验。",
    ),
    (
        "货币资金 现金及现金等价物",
        "资产负债表的'货币资金'通常大于现金流量表的'现金及现金等价物', "
        "因为货币资金包含受限资金和定期存款等非现金等价物。两者的差异属于正常现象, "
        "不等于报表错误。",
    ),
    (
        "减值损失 信用减值 资产减值 符号",
        "利润表中'信用减值损失'和'资产减值损失'以负数填列(损失为负值)。"
        "若为正数表示转回(收益)。校验公式直接将减值损失相加, 依赖报表按规范填列符号。",
    ),
    (
        "明细勾稽 余额表 序时账 现金流量明细",
        "明细层勾稽覆盖: 序时账逐凭证借贷平衡; 现金流量明细各项目合计=现金流量表主表; "
        "现金流明细=序时账现金等价物科目净变动; 余额表期末余额=资产负债表项目。"
        "发现差异时优先排查重分类、坏账准备、现金等价物口径等调整项。",
    ),
    (
        "现金流分类 现金流项目 复核",
        "现金流选择正确性按'现金流量项目↔对方科目'规则复核。对方科目不在常见范围时输出"
        "复核提示而非直接判错(宁可漏报不可误报)。常见特殊情况: 理财产品(1012)按投资活动、"
        "保证金按受限资金、复合凭证多科目混入, 需结合摘要确认。",
    ),
    (
        "往来重分类 六大往来 负数",
        "六大往来: 应收账款/预收款项、应付账款/预付款项、其他应收款/其他应付款。"
        "期末明细余额为负数时, 应重分类到对应往来科目并转正。"
        "重分类后合计与资产负债表勾稽时, 差额通常来自坏账准备等报表调整。",
    ),
    (
        "权益变动表 所有者权益变动表 实收资本 盈余公积 未分配利润",
        "所有者权益变动表反映实收资本、资本公积、盈余公积、未分配利润等权益项目"
        "从期初到期末的变动。表内须满足: 期初余额+本年增减变动=期末余额; "
        "与主表勾稽: 净利润、其他综合收益、综合收益总额与利润表一致, "
        "各权益项目期末余额与资产负债表对应项目一致。"
        "依据: 财会〔2019〕6号一般企业财务报表格式。",
    ),
    (
        "财务比率 毛利率 资产负债率 周转率 速动比率 非经常性损益",
        "逻辑合理性规则(LR)基于财务比率提示异常, 属业务提示而非硬性错误: "
        "毛利率异常波动、资产负债率过高、应收账款周转率异常、流动/速动比率偏离区间、"
        "经营现金流与净利润背离(净现比)、销售收现比率异常、关键科目同比波动超30%、"
        "扣非净利润为负但净利润为正等。判断需结合行业特征与企业实际经营情况, "
        "依据: 中国注册会计师审计准则第1313号分析程序。",
    ),
    (
        "关联方采购 销售收入 内部现金流 附表",
        "附表4核对关联方采购总金额与存货/成本/费用分类合计; 附表5核对收入成本明细与利润表; "
        "附表6核对内部交易现金流不超过主表对应项目。内部现金流超主表提示口径或分类待确认。",
    ),
]


_CACHED_RULE_KNOWLEDGE: list[tuple[str, str]] | None = None


def _rule_knowledge() -> list[tuple[str, str]]:
    """从规则库读取 CAS 准则引用与规则说明, 作为可检索知识源。"""
    global _CACHED_RULE_KNOWLEDGE
    if _CACHED_RULE_KNOWLEDGE is not None:
        return _CACHED_RULE_KNOWLEDGE
    entries: list[tuple[str, str]] = []
    path = resource_path("cas_gouji_rule_library.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rules = payload["ruleLibrary"]["rules"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    for rule in rules:
        topic = f"{rule['id']} {rule['name']}"
        content = (
            f"规则 {rule['id']}: {rule['name']}\n"
            f"公式: {rule.get('formula', '')}\n"
            f"CAS 依据: {rule.get('cas_ref', '')}\n"
            f"说明: {rule.get('notes', '')}"
        )
        entries.append((topic, content))
    _CACHED_RULE_KNOWLEDGE = entries
    return entries


def _external_knowledge() -> list[tuple[str, str]]:
    """读取内置 CAS/财政部/陈版主文档 (resources/knowledge/*.md|txt)。

    - 去 HTML 标签与脚本块, 还原常见实体
    - 长文档按段落切块 (重叠衔接), 避免整篇 25 万字符被一刀截断
    """
    entries: list[tuple[str, str]] = []
    base = resource_path("resources/knowledge")
    if not base.exists() or not base.is_dir():
        return entries
    for path in sorted(base.iterdir()):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        clean = _strip_html(content)
        if not clean:
            continue
        for index, chunk in enumerate(_chunk_text(clean), 1):
            entries.append((f"{path.stem}#{index}", chunk))
    return entries


def _strip_html(text: str) -> str:
    """移除 HTML 标签/脚本样式块并还原实体, 压缩多余空白。

    块级标签先转成换行, 其余标签直接删除, 避免中英文单词被空格错分;
    标签内容相邻时不会产生多余空格。
    """
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = re.sub(r"<(p|div|br|li|tr|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def _chunk_text(text: str) -> list[str]:
    """按段落聚合切块, 块间保留少量重叠; 超长段落按句子边界再分。"""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if not buffer:
            buffer = paragraph
            continue
        if len(buffer) + len(paragraph) + 2 <= _CHUNK_MAX_CHARS:
            buffer += "\n\n" + paragraph
            continue
        chunks.append(buffer)
        overlap = buffer[-_CHUNK_OVERLAP_CHARS:]
        buffer = overlap + "\n\n" + paragraph if overlap else paragraph

    if buffer:
        chunks.append(buffer)

    # 超长段落 (无自然空行) 按句子边界切分, 保证单块可读
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= _CHUNK_MAX_CHARS:
            final.append(chunk)
            continue
        sentences = re.split(r"(?<=[。！？；])", chunk)
        piece = ""
        for sentence in sentences:
            if not sentence.strip():
                continue
            if len(piece) + len(sentence) <= _CHUNK_MAX_CHARS:
                piece += sentence
                continue
            if piece:
                final.append(piece)
            piece = sentence[-_CHUNK_MAX_CHARS:]
        if piece:
            final.append(piece)
    return [item for item in final if item.strip()]


def search_knowledge(query: str) -> str:
    """按关键词检索知识库, 返回匹配的知识条目。

    简单的关键词匹配: 任一关键词命中主题或内容即返回。
    轻量实现, 不依赖向量库。

    Args:
        query: 检索关键词 (可含空格分隔的多个词)

    Returns:
        匹配的知识条目文本, 无匹配时返回提示
    """
    query = query.strip()
    if not query:
        return "请提供检索关键词。"

    keywords = [w for w in query.split() if w]
    scored: list[tuple[int, str]] = []

    sources = (
        [(topic, content, "内置知识") for topic, content in _KNOWLEDGE]
        + [(topic, content, "规则库 CAS") for topic, content in _rule_knowledge()]
        + [(topic, content, "外部文档") for topic, content in _external_knowledge()]
    )
    seen_contents: set[str] = set()
    for topic, content, source in sources:
        score = sum(1 for kw in keywords if kw in topic or kw in content)
        if score <= 0:
            continue
        fingerprint = re.sub(r"\s+", "", content)
        if fingerprint in seen_contents:
            continue
        seen_contents.add(fingerprint)
        scored.append((score, f"【{source} · {topic}】\n{content}"))

    if not scored:
        return (
            f"知识库中未找到与「{query}」相关的内容。可尝试: 勾稽关系/容差/跳过/导入/导出/新增规则/现金流量表等关键词。"
        )

    # 同分优先短块 (命中密度更高), 再按来源顺序稳定排序
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    selected: list[str] = []
    total = 0
    for _, text in scored:
        if len(selected) >= 3 or total + len(text) > _SEARCH_OUTPUT_MAX_CHARS:
            continue
        selected.append(text)
        total += len(text)
    return "\n\n".join(selected)
