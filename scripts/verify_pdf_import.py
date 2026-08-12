"""PDF 导入验证脚本: 导入生成的 PDF 测试文件，运行校验，打印结果。

用法:
    python scripts/verify_pdf_import.py
"""

from __future__ import annotations

from pathlib import Path

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.importer import ImportService
from fsa.core.models.report import ReportType
from fsa.services.validation_service import ValidationService

PDF_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "real_reports" / "测试报表_三大报表.pdf"
RULES_PATH = Path(__file__).parent.parent / "cas_gouji_rule_library.json"


def main() -> None:
    print("=" * 60)
    print("PDF 导入验证")
    print("=" * 60)

    # 1. 导入 PDF
    service = ImportService(period="2024-12")
    reports = service.import_file(str(PDF_PATH))

    print(f"\n导入结果: {len(reports)} 张报表")
    print("-" * 40)

    for report in reports:
        print(f"  {report.report_type.value}: {len(report.items)} 个项目")
        # 打印关键项目
        key_items = _get_key_items(report)
        for key, name in key_items:
            item = report.get_item(key)
            if item is not None:
                ba = f" (期初: {item.beginning_amount:,.2f})" if item.beginning_amount is not None else ""
                print(f"    {name}: {item.amount:,.2f}{ba}")

    # 2. 运行校验
    print(f"\n校验结果:")
    print("-" * 40)

    registry = RuleRegistry.from_json(str(RULES_PATH))
    validation = ValidationService(registry)
    summary = validation.validate(reports, period="2024-12")

    print(f"  总规则: {summary.total}")
    print(f"  通过: {summary.passed}")
    print(f"  不通过: {summary.failed}")
    print(f"  异常: {summary.errored}")
    print(f"  跳过: {summary.skipped}")

    # 3. 重点检查 BS-BAL-001
    print(f"\n重点规则:")
    print("-" * 40)
    for rule_id in ["BS-BAL-001", "IS-BAL-001", "CF-BAL-001"]:
        for r in summary.results:
            if r.rule_id == rule_id:
                status = "通过" if r.passed else "不通过"
                print(f"  {rule_id}: {status} - {r.message}")

    # 4. 汇总
    print(f"\n" + "=" * 60)
    if summary.failed == 0:
        print("结果: 全部通过")
    else:
        print(f"结果: {summary.failed} 条不通过")


def _get_key_items(report) -> list[tuple[str, str]]:
    """获取各报表类型的关键项目列表。"""
    bs_keys = [
        ("asset_total", "资产总计"),
        ("liability_total", "负债合计"),
        ("equity_total", "所有者权益合计"),
    ]
    is_keys = [
        ("revenue", "营业收入"),
        ("operating_cost", "营业成本"),
        ("net_profit", "净利润"),
    ]
    cf_keys = [
        ("operating_net", "经营活动现金流量净额"),
        ("investing_net", "投资活动现金流量净额"),
        ("financing_net", "筹资活动现金流量净额"),
        ("net_increase_cash", "现金及现金等价物净增加额"),
    ]

    if report.report_type == ReportType.BALANCE_SHEET:
        return bs_keys
    elif report.report_type == ReportType.INCOME_STATEMENT:
        return is_keys
    elif report.report_type == ReportType.CASH_FLOW_STATEMENT:
        return cf_keys
    return []


if __name__ == "__main__":
    main()