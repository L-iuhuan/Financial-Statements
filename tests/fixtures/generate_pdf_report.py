"""生成 PDF 测试报表: 使用 reportlab 创建包含三大报表的 PDF 文件。

生成的 PDF 包含 3 页:
- 第1页: 资产负债表（期末余额 + 年初余额）
- 第2页: 利润表（本期金额 + 上期金额）
- 第3页: 现金流量表（本期金额 + 上期金额）

数字内部一致: 资产=负债+所有者权益, 现金流勾稽正确。
使用标准科目名，确保 name_mapper 可识别。
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# 注册中文字体（SimSun 宋体，Windows 自带）
_FONT_DIR = "C:/Windows/Fonts"
_SIMSUN_TTF = f"{_FONT_DIR}/simsun.ttc"
try:
    pdfmetrics.registerFont(TTFont("SimSun", _SIMSUN_TTF))
    _CN_FONT = "SimSun"
except Exception:
    _CN_FONT = "Helvetica"

OUTPUT_DIR = Path(__file__).parent / "real_reports"
OUTPUT_PATH = OUTPUT_DIR / "测试报表_三大报表.pdf"


def _make_table_style(col_count: int) -> TableStyle:
    """创建带边框的表格样式。"""
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), _CN_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])


def _make_header_style() -> TableStyle:
    """表头样式: 加粗 + 居中。"""
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), _CN_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 1), (-1, 1), _CN_FONT),
        ("FONTSIZE", (0, 1), (-1, 1), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.Color(0.9, 0.9, 0.9)),
    ])


def _build_balance_sheet() -> list[list[str]]:
    """构建资产负债表表格数据: 项目, 期末余额, 年初余额。

    资产总计 = 2000000, 负债合计 = 1000000, 所有者权益合计 = 1000000
    等式: 2000000 = 1000000 + 1000000 ✓
    """
    title = "资产负债表"
    data = [
        [title, "", ""],
        ["项目", "期末余额", "年初余额"],
        ["货币资金", "100000.00", "80000.00"],
        ["交易性金融资产", "50000.00", "40000.00"],
        ["应收票据", "60000.00", "50000.00"],
        ["应收账款", "180000.00", "160000.00"],
        ["预付款项", "50000.00", "45000.00"],
        ["其他应收款", "30000.00", "25000.00"],
        ["存货", "200000.00", "180000.00"],
        ["流动资产合计", "720000.00", "630000.00"],
        ["固定资产", "800000.00", "750000.00"],
        ["在建工程", "200000.00", "150000.00"],
        ["无形资产", "150000.00", "140000.00"],
        ["长期待摊费用", "50000.00", "45000.00"],
        ["递延所得税资产", "30000.00", "25000.00"],
        ["非流动资产合计", "1280000.00", "1220000.00"],
        ["资产总计", "2000000.00", "1850000.00"],
        ["短期借款", "100000.00", "90000.00"],
        ["应付票据", "50000.00", "40000.00"],
        ["应付账款", "300000.00", "280000.00"],
        ["预收款项", "100000.00", "90000.00"],
        ["应付职工薪酬", "60000.00", "55000.00"],
        ["应交税费", "40000.00", "35000.00"],
        ["其他应付款", "50000.00", "45000.00"],
        ["流动负债合计", "700000.00", "635000.00"],
        ["长期借款", "200000.00", "180000.00"],
        ["应付债券", "50000.00", "50000.00"],
        ["递延所得税负债", "50000.00", "35000.00"],
        ["非流动负债合计", "300000.00", "265000.00"],
        ["负债合计", "1000000.00", "900000.00"],
        ["实收资本", "500000.00", "500000.00"],
        ["资本公积", "100000.00", "100000.00"],
        ["其他综合收益", "50000.00", "40000.00"],
        ["盈余公积", "80000.00", "70000.00"],
        ["未分配利润", "270000.00", "240000.00"],
        ["所有者权益合计", "1000000.00", "950000.00"],
    ]
    return data


def _build_income_statement() -> list[list[str]]:
    """构建利润表表格数据: 项目, 本期金额, 上期金额。

    净利润 = 405000.00
    """
    title = "利润表"
    data = [
        [title, "", ""],
        ["项目", "本期金额", "上期金额"],
        ["营业收入", "3000000.00", "2800000.00"],
        ["营业成本", "2000000.00", "1900000.00"],
        ["税金及附加", "50000.00", "48000.00"],
        ["销售费用", "200000.00", "180000.00"],
        ["管理费用", "150000.00", "140000.00"],
        ["研发费用", "80000.00", "75000.00"],
        ["财务费用", "30000.00", "28000.00"],
        ["其他收益", "20000.00", "15000.00"],
        ["投资收益", "50000.00", "40000.00"],
        ["信用减值损失", "-5000.00", "0.00"],
        ["资产减值损失", "-10000.00", "0.00"],
        ["资产处置收益", "0.00", "0.00"],
        ["营业利润", "545000.00", "484000.00"],
        ["营业外收入", "5000.00", "3000.00"],
        ["营业外支出", "10000.00", "8000.00"],
        ["利润总额", "540000.00", "479000.00"],
        ["所得税费用", "135000.00", "119750.00"],
        ["净利润", "405000.00", "359250.00"],
        ["税后其他综合收益", "10000.00", "5000.00"],
        ["综合收益总额", "415000.00", "364250.00"],
    ]
    return data


def _build_cash_flow() -> list[list[str]]:
    """构建现金流量表表格数据: 项目, 本期金额, 上期金额。

    现金及现金等价物净增加额 + 期初余额 = 期末余额
    205000 + 800000 = 1005000 ✓
    """
    title = "现金流量表"
    data = [
        [title, "", ""],
        ["项目", "本期金额", "上期金额"],
        ["销售商品、提供劳务收到的现金", "3200000.00", "3000000.00"],
        ["收到的税费返还", "50000.00", "40000.00"],
        ["收到其他与经营活动有关的现金", "30000.00", "20000.00"],
        ["经营活动现金流入小计", "3280000.00", "3060000.00"],
        ["购买商品、接受劳务支付的现金", "2400000.00", "2200000.00"],
        ["支付给职工以及为职工支付的现金", "250000.00", "230000.00"],
        ["支付的各项税费", "150000.00", "140000.00"],
        ["支付其他与经营活动有关的现金", "80000.00", "70000.00"],
        ["经营活动现金流出小计", "2880000.00", "2640000.00"],
        ["经营活动产生的现金流量净额", "400000.00", "420000.00"],
        ["收回投资收到的现金", "100000.00", "80000.00"],
        ["取得投资收益收到的现金", "50000.00", "40000.00"],
        ["投资活动现金流入小计", "150000.00", "120000.00"],
        ["购建固定资产支付的现金", "300000.00", "240000.00"],
        ["投资支付的现金", "100000.00", "80000.00"],
        ["投资活动现金流出小计", "400000.00", "320000.00"],
        ["投资活动产生的现金流量净额", "-250000.00", "-200000.00"],
        ["取得借款收到的现金", "500000.00", "400000.00"],
        ["筹资活动现金流入小计", "500000.00", "400000.00"],
        ["偿还债务支付的现金", "300000.00", "280000.00"],
        ["分配股利支付现金", "100000.00", "80000.00"],
        ["筹资活动现金流出小计", "400000.00", "360000.00"],
        ["筹资活动产生的现金流量净额", "100000.00", "40000.00"],
        ["汇率变动对现金的影响", "-45000.00", "-37000.00"],
        ["现金及现金等价物净增加额", "205000.00", "223000.00"],
        ["期初现金及现金等价物余额", "800000.00", "577000.00"],
        ["期末现金及现金等价物余额", "1005000.00", "800000.00"],
    ]
    return data


def _build_merged_balance_sheet() -> list[list[str]]:
    """构建合并资产负债表: 标题含"合并资产负债表"。

    数字与标准资产负债表相同，但标题不同。
    """
    title = "合并资产负债表"
    data = [
        [title, "", ""],
        ["项目", "期末余额", "年初余额"],
        ["货币资金", "100000.00", "80000.00"],
        ["应收账款", "180000.00", "160000.00"],
        ["存货", "200000.00", "180000.00"],
        ["流动资产合计", "720000.00", "630000.00"],
        ["固定资产", "800000.00", "750000.00"],
        ["非流动资产合计", "1280000.00", "1220000.00"],
        ["资产总计", "2000000.00", "1850000.00"],
        ["应付账款", "300000.00", "280000.00"],
        ["流动负债合计", "700000.00", "635000.00"],
        ["非流动负债合计", "300000.00", "265000.00"],
        ["负债合计", "1000000.00", "900000.00"],
        ["实收资本", "500000.00", "500000.00"],
        ["未分配利润", "270000.00", "240000.00"],
        ["所有者权益合计", "1000000.00", "950000.00"],
    ]
    return data


def _add_title_spacer(story: list, title_text: str) -> None:
    """添加标题和间距。"""
    styles = getSampleStyleSheet()
    styles["Heading1"].fontName = _CN_FONT
    title = Paragraph(title_text, styles["Heading1"])
    story.append(title)
    story.append(Spacer(1, 6 * mm))


def _add_table(story: list, data: list[list[str]], col_widths: list[float] | None = None) -> None:
    """添加带边框的表格。"""
    if col_widths is None:
        col_widths = [80 * mm, 50 * mm, 50 * mm]

    t = Table(data, colWidths=col_widths)
    base_style = _make_table_style(len(data[0]))
    header_style = _make_header_style()
    t.setStyle(TableStyle(base_style.getCommands() + header_style.getCommands()))
    story.append(t)


def generate_three_reports(path: str | None = None) -> str:
    """生成包含三大报表的 PDF 文件。

    Args:
        path: 输出路径，默认为 tests/fixtures/real_reports/测试报表_三大报表.pdf

    Returns:
        生成的文件路径
    """
    if path is None:
        path = str(OUTPUT_PATH)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    story: list = []

    # 第1页: 资产负债表
    _add_title_spacer(story, "资产负债表")
    _add_table(story, _build_balance_sheet())
    story.append(PageBreak())

    # 第2页: 利润表
    _add_title_spacer(story, "利润表")
    _add_table(story, _build_income_statement())
    story.append(PageBreak())

    # 第3页: 现金流量表
    _add_title_spacer(story, "现金流量表")
    _add_table(story, _build_cash_flow())

    doc.build(story)
    print(f"已生成: {path}")
    return path


def generate_merged_balance_sheet(path: str | None = None) -> str:
    """生成仅含合并资产负债表的 PDF 文件。

    Args:
        path: 输出路径

    Returns:
        生成的文件路径
    """
    if path is None:
        path = str(OUTPUT_DIR / "测试报表_合并资产负债表.pdf")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    story: list = []
    _add_title_spacer(story, "合并资产负债表")
    _add_table(story, _build_merged_balance_sheet())

    doc.build(story)
    print(f"已生成: {path}")
    return path


if __name__ == "__main__":
    generate_three_reports()
    generate_merged_balance_sheet()
