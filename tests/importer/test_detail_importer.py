"""明细导入器测试: 从工作簿识别并解析余额表/序时账/现金流量明细。"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from fsa.core.importer.detail_importer import DetailImporter


def _write_sheet(ws: openpyxl.worksheet.worksheet.Worksheet, headers: list[str], rows: list[list[object]]) -> None:
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)
    for row_idx, row in enumerate(rows, 2):
        for col_idx, value in enumerate(row, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)


def _make_workbook(tmp_path: Path) -> Path:
    path = tmp_path / "detail.xlsx"
    wb = openpyxl.Workbook()
    ws_tb = wb.active
    ws_tb.title = "带辅助核算的科目余额表（1-本月）"
    _write_sheet(
        ws_tb,
        ["会计期间", "科目编码", "科目名称", "期初余额借方", "本期发生借方", "期末余额借方", "期末余额贷方"],
        [
            ["2026.01 - 2026.06", "1002", "银行存款", 100.0, 500.0, 600.0, 0.0],
            ["2026.01 - 2026.06", "1012", "其他货币资金", 0.0, 0.0, 100.0, 0.0],
        ],
    )
    ws_journal = wb.create_sheet("序时账（1-本月）")
    _write_sheet(
        ws_journal,
        ["日期", "凭证号数", "上级科目", "科目编码", "科目名称", "摘要", "方向", "金额"],
        [
            ["2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "收款", "贷", 500.0],
            ["2026-06-30", "记-0001", "应收账款", "1122", "应收账款", "收款", "借", 500.0],
        ],
    )
    ws_cf = wb.create_sheet("现金流量表（1-本月）")
    _write_sheet(
        ws_cf,
        ["2026年月", "2026年日", "凭证号", "现金流量项目", "摘要", "方向", "金额"],
        [
            [6, 30, "记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 500.0],
            [None, None, None, "销售商品、提供劳务收到的现金(01)", "小计", "流入", 500.0],
        ],
    )
    wb.save(str(path))
    return path


class TestDetailImporter:
    """明细导入器按表头识别工作表并解析数据。"""

    def test_import_parses_three_detail_kinds(self, tmp_path: Path) -> None:
        path = _make_workbook(tmp_path)
        dataset = DetailImporter(period="2026-06").import_file(str(path))

        assert len(dataset.trial_balance) == 2
        assert dataset.trial_balance[0].account_code == "1002"
        assert dataset.trial_balance[0].ending_debit == 600.0

        assert len(dataset.journal) == 2
        assert dataset.journal[0].voucher_no == "记-0001"
        assert dataset.journal[0].direction == "贷"

        assert len(dataset.cash_flow_detail) == 2
        assert dataset.cash_flow_detail[0].project == "销售商品、提供劳务收到的现金(01)"

    def test_current_month_sheet_goes_to_separate_list(self, tmp_path: Path) -> None:
        path = tmp_path / "detail_current.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "带辅助核算的科目余额表（本月）"
        _write_sheet(
            ws,
            ["科目编码", "科目名称", "期末余额借方"],
            [["1002", "银行存款", 123.0]],
        )
        wb.save(str(path))

        dataset = DetailImporter().import_file(str(path))
        assert dataset.trial_balance == []
        assert len(dataset.trial_balance_current) == 1
