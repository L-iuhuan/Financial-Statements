"""审计底稿 Excel 导出器。

将 ValidationSummary 导出为格式化的 Excel 审计底稿，包含三个 sheet:
- 校验汇总: 统计概览和结论
- 校验明细: 每条规则的校验结果
- 科目追溯: 每个科目的来源追踪 (P3 可审计可溯源)
"""

from __future__ import annotations

import json
from datetime import datetime

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from fsa.core.models.result import ValidationSummary
from fsa.core.resources import resource_path

# 状态颜色
_FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
_FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
_FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
_FILL_GRAY = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
_FILL_HEADER = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

_FONT_HEADER = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
_FONT_NORMAL = Font(name="微软雅黑", size=10)
_FONT_TITLE = Font(name="微软雅黑", size=14, bold=True)

_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)

_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
_ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")
_ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

# 规则库文件路径 (支持开发模式与 PyInstaller 冻结模式)
_RULES_FILE = resource_path("cas_gouji_rule_library.json")


def _get_rule_library_version() -> str:
    """从规则库 JSON 文件中读取版本号。"""
    try:
        with open(_RULES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("ruleLibrary", {}).get("version", ""))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""


class AuditExporter:
    """审计底稿 Excel 导出器。

    接收 ValidationSummary，输出格式化的 .xlsx 文件。
    职责: 接收校验结果 -> 输出文件。禁止修改校验结果。
    """

    def export(self, summary: ValidationSummary, file_path: str) -> None:
        """将校验汇总导出为 Excel 审计底稿。

        Args:
            summary: 校验汇总结果
            file_path: 输出文件路径 (.xlsx)

        Raises:
            PermissionError: 文件被占用
            OSError: 写入失败
        """
        wb = Workbook()

        # Sheet 1: 校验汇总
        ws_summary = wb.active
        assert ws_summary is not None
        ws_summary.title = "校验汇总"
        self._write_summary_sheet(ws_summary, summary)

        # Sheet 2: 校验明细
        ws_detail = wb.create_sheet("校验明细")
        self._write_detail_sheet(ws_detail, summary)

        # Sheet 3: 科目追溯
        ws_trace = wb.create_sheet("科目追溯")
        self._write_trace_sheet(ws_trace, summary)

        wb.save(file_path)

    # ── 校验汇总 sheet ──

    def _write_summary_sheet(
        self, ws: Worksheet, summary: ValidationSummary
    ) -> None:
        """写入校验汇总 sheet。"""
        ws.merge_cells("A1:B1")
        title_cell = ws.cell(row=1, column=1, value="财务报表勾稽校验审计底稿")
        title_cell.font = _FONT_TITLE
        title_cell.alignment = _ALIGN_CENTER

        rows: list[tuple[str, str]] = [
            ("报告期间", summary.period),
            ("校验时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("规则总数", str(summary.total)),
            ("通过", str(summary.passed)),
            ("不通过", str(summary.failed)),
            ("异常", str(summary.errored)),
            ("跳过", str(summary.skipped)),
            ("涉及报表", "、".join(rt.value for rt in summary.report_types)),
            ("规则库版本", _get_rule_library_version()),
        ]

        if summary.failed + summary.errored == 0:
            rows.append(("结论", "全部通过 ✓"))
        else:
            count = summary.failed + summary.errored
            rows.append(("结论", f"存在 {count} 项不通过或异常"))

        for i, (label, value) in enumerate(rows, start=2):
            label_cell = ws.cell(row=i, column=1, value=label)
            label_cell.font = Font(name="微软雅黑", size=10, bold=True)
            label_cell.alignment = _ALIGN_RIGHT
            label_cell.border = _THIN_BORDER

            value_cell = ws.cell(row=i, column=2, value=value)
            value_cell.font = _FONT_NORMAL
            value_cell.alignment = _ALIGN_LEFT
            value_cell.border = _THIN_BORDER

        ws.column_dimensions["A"].width = 16
        ws.column_dimensions["B"].width = 40

    # ── 校验明细 sheet ──

    def _write_detail_sheet(
        self, ws: Worksheet, summary: ValidationSummary
    ) -> None:
        """写入校验明细 sheet。"""
        headers = [
            "规则ID", "规则名称", "分类", "校验结果",
            "左侧值", "右侧值", "差额", "容差", "公式", "说明",
        ]
        self._write_header_row(ws, headers)

        for i, result in enumerate(summary.results, start=2):
            self._write_detail_row(ws, i, result)

        # 列宽
        col_widths = [14, 28, 14, 10, 18, 18, 18, 10, 40, 40]
        for col_idx, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.freeze_panes = "A2"

    def _write_detail_row(
        self, ws: Worksheet, row: int, result
    ) -> None:
        """写入校验明细的一行数据。"""
        # 确定状态文本和颜色
        if result.errored:
            status = "异常"
            fill = _FILL_YELLOW
        elif result.skipped:
            status = "跳过"
            fill = _FILL_GRAY
        elif result.passed:
            status = "通过"
            fill = _FILL_GREEN
        else:
            status = "不通过"
            fill = _FILL_RED

        values = [
            result.rule_id,
            result.rule_name,
            result.category,
            status,
            result.left_value,
            result.right_value,
            result.diff,
            result.tolerance,
            result.formula,
            result.message,
        ]

        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.font = _FONT_NORMAL
            cell.border = _THIN_BORDER

            if col == 4:  # 校验结果列
                cell.fill = fill
                cell.alignment = _ALIGN_CENTER
            elif col in (5, 6, 7):  # 金额列
                cell.number_format = "#,##0.00"
                cell.alignment = _ALIGN_RIGHT
            elif col == 8:  # 容差列
                cell.alignment = _ALIGN_CENTER
            elif col in (9, 10):  # 公式和说明
                cell.alignment = _ALIGN_LEFT

    # ── 科目追溯 sheet ──

    def _write_trace_sheet(
        self, ws: Worksheet, summary: ValidationSummary
    ) -> None:
        """写入科目追溯 sheet。"""
        headers = [
            "规则ID", "规则名称", "侧", "科目名称",
            "金额", "原始行", "原始列",
        ]
        self._write_header_row(ws, headers)

        row = 2
        for result in summary.results:
            if result.skipped:
                continue
            for trace_item in result.trace:
                side_label = "左" if trace_item.side == "left" else "右"
                values = [
                    result.rule_id,
                    result.rule_name,
                    side_label,
                    trace_item.name,
                    trace_item.amount,
                    trace_item.row,
                    trace_item.column,
                ]
                for col, value in enumerate(values, start=1):
                    cell = ws.cell(row=row, column=col, value=value)
                    cell.font = _FONT_NORMAL
                    cell.border = _THIN_BORDER
                    if col == 5:  # 金额列
                        cell.number_format = "#,##0.00"
                        cell.alignment = _ALIGN_RIGHT
                    elif col in (6, 7):  # 行列
                        cell.alignment = _ALIGN_CENTER
                    else:
                        cell.alignment = _ALIGN_LEFT
                row += 1

        # 列宽
        col_widths = [14, 28, 6, 24, 18, 10, 12]
        for col_idx, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.freeze_panes = "A2"

    # ── 通用样式 ──

    @staticmethod
    def _write_header_row(ws: Worksheet, headers: list[str]) -> None:
        """写入表头行并应用样式。"""
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = _FONT_HEADER
            cell.fill = _FILL_HEADER
            cell.alignment = _ALIGN_CENTER
            cell.border = _THIN_BORDER
