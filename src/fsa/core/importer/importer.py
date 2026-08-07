"""报表导入服务: 主入口，编排读取 -> 识别 -> 提取 -> 构建 Report 全流程。

ImportService 是无状态的，每次调用 import_file 或 import_sheet 独立执行。
"""

from __future__ import annotations

from loguru import logger

from fsa.core.importer.excel_reader import read_excel
from fsa.core.importer.item_extractor import extract_items
from fsa.core.importer.report_identifier import identify_reports
from fsa.core.models.report import Report, ReportType


class ImportService:
    """Excel 报表导入服务。

    职责: 读取 Excel 文件 -> 输出 Report 对象列表。
    禁止: 执行校验逻辑。

    Attributes:
        period: 报告期间，如 "2024-12"，所有导入的报表共用此期间
    """

    def __init__(self, period: str = "") -> None:
        self.period = period

    def import_file(self, file_path: str) -> list[Report]:
        """导入 Excel 文件中的所有报表。

        读取文件 -> 识别每个工作表 -> 提取项目 -> 构建 Report 对象。

        Args:
            file_path: Excel 文件路径

        Returns:
            Report 对象列表，仅包含成功识别的报表

        Raises:
            FileNotFoundError: 文件不存在
        """
        logger.info(f"导入文件: {file_path}")

        raw_data = read_excel(file_path)
        identified = identify_reports(raw_data)

        if not identified:
            logger.warning(f"文件中未识别到任何报表: {file_path}")
            return []

        reports: list[Report] = []
        for sheet_name, report_type in identified:
            raw = raw_data[sheet_name]
            items = extract_items(raw, report_type)
            report = self._build_report(report_type, items, file_path)
            reports.append(report)
            logger.info(f"  导入报表: {report_type.value}，共 {len(items)} 个项目")

        return reports

    def import_sheet(self, file_path: str, sheet_name: str) -> Report:
        """导入指定工作表的报表。

        Args:
            file_path: Excel 文件路径
            sheet_name: 工作表名称

        Returns:
            Report 对象

        Raises:
            ValueError: 工作表不存在或无法识别报表类型
            FileNotFoundError: 文件不存在
        """
        logger.info(f"导入工作表: {file_path} / {sheet_name}")

        raw_data = read_excel(file_path)

        if sheet_name not in raw_data:
            raise ValueError(f"文件中不存在工作表「{sheet_name}」")

        identified = identify_reports({sheet_name: raw_data[sheet_name]})
        if not identified:
            raise ValueError(f"无法识别工作表「{sheet_name}」的报表类型")

        _, report_type = identified[0]
        raw = raw_data[sheet_name]
        items = extract_items(raw, report_type)
        return self._build_report(report_type, items, file_path)

    def _build_report(
        self,
        report_type: ReportType,
        items: list,
        source_file: str,
    ) -> Report:
        """构建 Report 对象。

        Args:
            report_type: 报表类型
            items: ReportItem 列表
            source_file: 源文件路径

        Returns:
            Report 对象
        """
        return Report(
            report_type=report_type,
            period=self.period,
            source_file=source_file,
            items=items,
        )
