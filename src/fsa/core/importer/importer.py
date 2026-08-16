"""报表导入服务: 主入口，编排读取 -> 识别 -> 提取 -> 构建 Report 全流程。

ImportService 是无状态的，每次调用 import_file 或 import_sheet 独立执行。
支持 Excel (.xlsx/.xls) 和 PDF (.pdf) 格式。
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from fsa.core.importer.excel_reader import RawSheetData, read_excel
from fsa.core.importer.item_extractor import extract_items
from fsa.core.importer.report_identifier import identify_reports
from fsa.core.importer.sce_extractor import extract_sce_items
from fsa.core.models.report import Report, ReportItem, ReportType


class ImportService:
    """财务报表导入服务。

    职责: 读取 Excel/PDF 文件 -> 输出 Report 对象列表。
    禁止: 执行校验逻辑。

    Attributes:
        period: 报告期间，如 "2024-12"，所有导入的报表共用此期间
    """

    def __init__(self, period: str = "") -> None:
        self.period = period

    def import_file(self, file_path: str) -> list[Report]:
        """导入文件中的所有报表。

        根据文件扩展名路由到对应的读取器:
        - .xlsx/.xls → read_excel (Excel 读取器)
        - .pdf → read_pdf (PDF 读取器)

        读取后委托 import_data 完成识别→提取→构建管线。

        Args:
            file_path: 文件路径

        Returns:
            Report 对象列表，仅包含成功识别的报表

        Raises:
            FileNotFoundError: 文件不存在
        """
        logger.info(f"导入文件: {file_path}")

        suffix = Path(file_path).suffix.lower()
        if suffix == ".pdf":
            from fsa.core.importer.pdf_reader import read_pdf

            raw_data = read_pdf(file_path)
        else:
            raw_data = read_excel(file_path)

        return self.import_data(raw_data, str(file_path), suffix)

    def import_data(
        self, data: dict[str, RawSheetData], source_file: str, suffix: str
    ) -> list[Report]:
        """从已读取的 RawSheetData 导入报表（读取后的识别→提取→构建管线）。

        与 import_file 的区别：import_file 负责读取文件，import_data
        负责读取后的全部处理。调用方可以先读取一次文件，再分别传给
        ImportService.import_data 和 DetailImporter.import_data，
        避免重复读取。

        Args:
            data: read_excel 或 read_pdf 返回的原始数据字典
            source_file: 源文件路径（用于 Report.source_file 和日志）
            suffix: 文件扩展名（".xlsx" / ".xls" / ".pdf"），
                    用于路由 SCE 提取器（PDF 的 SCE 矩阵暂不支持）

        Returns:
            Report 对象列表，仅包含成功识别的报表
        """
        identified = identify_reports(data)

        if not identified:
            logger.warning(f"文件中未识别到任何报表: {source_file}")
            return []

        reports: list[Report] = []
        for sheet_name, report_type in identified:
            raw = data[sheet_name]
            unmapped: list[str] = []
            unit_info: dict[str, str] = {}
            items = self._extract_for_type(
                raw, report_type, suffix, unmapped, unit_info
            )
            report = self._build_report(
                report_type, items, source_file, unmapped,
                unit_info.get("unit", "元"),
                unit_info.get("warning", ""),
            )
            reports.append(report)
            logger.info(f"  导入报表: {report_type.value}，共 {len(items)} 个项目")

        return reports

    def import_sheet(self, file_path: str, sheet_name: str) -> Report:
        """导入指定工作表的报表（仅支持 Excel）。

        Args:
            file_path: 文件路径
            sheet_name: 工作表名称

        Returns:
            Report 对象

        Raises:
            ValueError: 工作表不存在或无法识别报表类型
            FileNotFoundError: 文件不存在
        """
        logger.info(f"导入工作表: {file_path} / {sheet_name}")

        suffix = Path(file_path).suffix.lower()
        if suffix == ".pdf":
            raise ValueError(
                "PDF 文件不支持按工作表名称导入，请使用 import_file 导入全部报表"
            )

        raw_data = read_excel(file_path)

        if sheet_name not in raw_data:
            raise ValueError(f"文件中不存在工作表「{sheet_name}」")

        identified = identify_reports({sheet_name: raw_data[sheet_name]})
        if not identified:
            raise ValueError(f"无法识别工作表「{sheet_name}」的报表类型")

        _, report_type = identified[0]
        raw = raw_data[sheet_name]
        unmapped: list[str] = []
        unit_info: dict[str, str] = {}
        items = self._extract_for_type(
            raw, report_type, suffix, unmapped, unit_info
        )
        return self._build_report(
            report_type, items, file_path, unmapped,
            unit_info.get("unit", "元"), unit_info.get("warning", ""),
        )

    def _extract_for_type(
        self,
        raw: RawSheetData,
        report_type: ReportType,
        suffix: str,
        unmapped: list[str] | None = None,
        unit_info: dict[str, str] | None = None,
    ) -> list[ReportItem]:
        """按报表类型选择提取器。

        权益变动表 (SCE) 是矩阵布局, 用专用矩阵提取器;
        其余报表用标准"项目+金额"提取器。
        PDF 的 SCE 矩阵暂不支持 (返回空并告警)。
        """
        if report_type == ReportType.STATEMENT_OF_CHANGES_IN_EQUITY:
            if suffix == ".pdf":
                logger.warning("PDF 格式的所有者权益变动表矩阵提取暂不支持, 跳过")
                return []
            return extract_sce_items(raw)
        return extract_items(raw, report_type, unmapped, unit_info)

    def _build_report(
        self,
        report_type: ReportType,
        items: list[ReportItem],
        source_file: str,
        unmapped_names: list[str] | None = None,
        amount_unit: str = "元",
        unit_warning: str = "",
    ) -> Report:
        """构建 Report 对象。

        Args:
            report_type: 报表类型
            items: ReportItem 列表
            source_file: 源文件路径
            unmapped_names: 未能映射为标准科目的项目名称（可选）

        Returns:
            Report 对象
        """
        return Report(
            report_type=report_type,
            period=self.period,
            source_file=source_file,
            items=items,
            unmapped_names=unmapped_names or [],
            amount_unit=amount_unit,
            unit_warning=unit_warning,
        )
