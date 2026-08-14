"""导入页批量导入测试: 单文件失败不中断整批，失败文件数据不入结果。

覆盖审查报告 #5（批量导入中断）与 #6（dataset 半状态）修复。
使用 pytest-qt 的 qapp 提供 Qt 应用环境，构造真实 ImportPage 实例，
通过 monkeypatch 注入受控的导入行为。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fsa.core.models.detail import DetailDataset, JournalRow, TrialBalanceRow
from fsa.core.models.report import Report, ReportType
from fsa.gui.app_state import AppState
from fsa.gui.pages.import_page import ImportPage


def _make_page() -> tuple[ImportPage, AppState]:
    """创建独立的 ImportPage 与 AppState。"""
    state = AppState()
    page = ImportPage(state)
    return page, state


def _balance_sheet_report(file_path: str) -> Report:
    from tests.conftest import make_balance_sheet

    report = make_balance_sheet(asset_total=100.0, liability_total=60.0, equity_total=40.0)
    report.source_file = file_path
    return report


def _cash_flow_report(file_path: str) -> Report:
    from tests.conftest import make_cash_flow_statement

    report = make_cash_flow_statement(operating_net=500.0)
    report.source_file = file_path
    return report


class TestBatchImportIsolation:
    """测试批量导入的单文件失败隔离（#5）。"""

    def test_third_file_still_processed_after_middle_keyerror(
        self, qapp, monkeypatch
    ) -> None:
        """三文件导入（正常/触发 KeyError/正常）：第三个文件仍被处理。"""
        page, state = _make_page()

        def fake_import_main(file_path: str) -> list[Report]:
            if file_path == "bad.xlsx":
                raise KeyError("缺失列")
            if file_path == "a.xlsx":
                return [_balance_sheet_report(file_path)]
            return [_cash_flow_report(file_path)]

        def fake_import_detail(file_path: str) -> DetailDataset:
            if file_path == "bad.xlsx":
                raise KeyError("缺失列")
            ds = DetailDataset(source_file=file_path)
            if file_path == "a.xlsx":
                ds.journal.append(
                    JournalRow(
                        date="2026-06-30", voucher_no="记-0001", parent_account="",
                        account_code="1002", account_name="银行存款", summary="收款",
                        direction="贷", amount=500.0,
                    )
                )
            else:
                ds.trial_balance.append(
                    TrialBalanceRow(
                        account_code="1002", account_name="银行存款", ending_debit=600.0
                    )
                )
            return ds

        messages: list[tuple[str, str]] = []
        page._importer.import_file = fake_import_main
        page._detail_importer.import_file = fake_import_detail
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["a.xlsx", "bad.xlsx", "c.xlsx"])

        # 第一个与第三个文件的主表均被导入，第二个被跳过
        types = {r.report_type for r in state.reports}
        assert ReportType.BALANCE_SHEET in types
        assert ReportType.CASH_FLOW_STATEMENT in types
        assert len(state.reports) == 2

        # 第一个与第三个文件的明细数据均进入 dataset
        ds = state.detail_dataset
        assert ds is not None
        assert len(ds.journal) == 1
        assert len(ds.trial_balance) == 1

        # 中文提示包含成功/失败文件数
        assert messages
        message, kind = messages[-1]
        assert "成功导入 2 个文件" in message
        assert "1 个文件失败" in message
        assert kind == "warning"
        assert "bad.xlsx" in message

    def test_failed_file_detail_not_merged(self, qapp) -> None:
        """失败文件的明细数据不进入 dataset（#6）。"""
        page, state = _make_page()

        def fake_import_main(file_path: str) -> list[Report]:
            if file_path == "bad.xlsx":
                raise TypeError("错误的列类型")
            return [_balance_sheet_report(file_path)]

        def fake_import_detail(file_path: str) -> DetailDataset:
            if file_path == "bad.xlsx":
                raise TypeError("错误的列类型")
            ds = DetailDataset(source_file=file_path)
            ds.trial_balance.append(
                TrialBalanceRow(account_code="1002", account_name="银行存款", ending_debit=999.0)
            )
            return ds

        page._importer.import_file = fake_import_main
        page._detail_importer.import_file = fake_import_detail

        page._on_files(["good.xlsx", "bad.xlsx"])

        ds = state.detail_dataset
        assert ds is not None
        # 只含成功文件的数据
        assert len(ds.trial_balance) == 1
        assert ds.trial_balance[0].ending_debit == 999.0
        # 失败文件的数据未混入：source_file 指向成功文件
        assert "bad.xlsx" not in ds.source_file
        # 主表仅来自成功文件
        assert len(state.reports) == 1
        assert state.reports[0].source_file == "good.xlsx"

    def test_all_files_success_shows_success_message(self, qapp) -> None:
        """全部成功时显示成功提示且不含失败计数。"""
        page, state = _make_page()

        def fake_import_main(file_path: str) -> list[Report]:
            return [_balance_sheet_report(file_path)]

        def fake_import_detail(file_path: str) -> DetailDataset:
            return DetailDataset(source_file=file_path)

        messages: list[tuple[str, str]] = []
        page._importer.import_file = fake_import_main
        page._detail_importer.import_file = fake_import_detail
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["a.xlsx", "b.xlsx"])

        assert messages
        message, kind = messages[-1]
        assert "成功导入 2 个文件" in message
        assert "失败" not in message
        assert kind == "success"

    def test_keyerror_message_contains_filename(self, qapp) -> None:
        """单文件失败的错误信息包含文件名（#5）。"""
        page, state = _make_page()

        def fake_import_main(file_path: str) -> list[Report]:
            raise KeyError("缺失列")

        def fake_import_detail(file_path: str) -> DetailDataset:
            raise KeyError("缺失列")

        messages: list[tuple[str, str]] = []
        page._importer.import_file = fake_import_main
        page._detail_importer.import_file = fake_import_detail
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["only_bad.xlsx"])

        assert messages
        message, _ = messages[-1]
        assert "only_bad.xlsx" in message
        # 唯一文件失败 → 无报表，早退提示
        assert len(state.reports) == 0
