"""审计底稿导出公共逻辑。

main_window 与 audit_page 的导出入口共用同一套流程:
路径选择 -> 写文件 -> 异常处理 -> 中文 InfoBar 反馈 (P4 用户可感知)。
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, StateToolTip

from fsa.core.exporter.audit_exporter import AuditExporter
from fsa.core.models.result import ValidationSummary


def export_audit_workbook(
    parent: QWidget,
    summary: ValidationSummary | None,
    show_progress: bool = True,
) -> None:
    """导出审计底稿 (路径选择 + 错误处理 + 中文反馈)。

    Args:
        parent: 宿主窗口 (用于对话框与 InfoBar 定位)
        summary: 校验汇总; None 时提示先执行校验后返回
        show_progress: 是否显示 StateToolTip 进度提示 (main_window 使用)
    """
    if summary is None:
        _show_warning(parent, "请先执行校验，再导出底稿")
        return

    period = summary.period or "未命名"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_name = f"审计底稿_{period}_{timestamp}.xlsx"

    path, _ = QFileDialog.getSaveFileName(
        parent,
        "导出审计底稿",
        default_name,
        "Excel 文件 (*.xlsx)",
    )
    if not path:
        return

    progress = _start_progress(parent) if show_progress else None
    try:
        exporter = AuditExporter()
        exporter.export(summary, path)
    except PermissionError:
        _stop_progress(progress)
        _show_error(parent, "文件被占用，请关闭已打开的 Excel 文件后重试")
        return
    except OSError:
        _stop_progress(progress)
        _show_error(parent, "无法写入文件，请检查路径权限")
        return
    except Exception as e:  # 兜底: openpyxl 等写入异常, 以中文提示用户, 不崩溃
        _stop_progress(progress)
        logger.error(f"导出审计底稿失败: {e}")
        _show_error(
            parent,
            f"导出过程中发生错误，请检查文件格式或稍后重试。\n详细信息: {e}",
        )
        return
    _finish_progress(progress)
    InfoBar.success(
        "导出成功",
        f"已导出到 {path}",
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=5000,
        parent=parent,
    )


def _start_progress(parent: QWidget) -> StateToolTip | None:
    """创建并显示导出进度提示。"""
    progress = StateToolTip("正在导出", "审计底稿生成中…", parent)
    progress.move(parent.width() // 2 - progress.width() // 2, parent.height() - 120)
    progress.show()
    return progress


def _finish_progress(progress: StateToolTip | None) -> None:
    """将进度提示置为完成态。"""
    if progress is not None:
        progress.setContent("导出完成")
        progress.setState(True)


def _stop_progress(progress: StateToolTip | None) -> None:
    """关闭进度提示 (出错时调用)。"""
    if progress is not None:
        progress.close()


def _show_warning(parent: QWidget, message: str) -> None:
    """以中文 InfoBar 提示操作前置条件不满足。"""
    InfoBar.warning(
        "提示",
        message,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=3000,
        parent=parent,
    )


def _show_error(parent: QWidget, message: str) -> None:
    """以中文 InfoBar 提示导出错误。"""
    InfoBar.error(
        "导出失败",
        message,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=5000,
        parent=parent,
    )
