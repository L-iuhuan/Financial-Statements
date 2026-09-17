"""导入文件列表组件。

显示拖入/选择的待导入文件列表, 并随后台导入进度逐行更新状态。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget, IndeterminateProgressRing

_ANIMATION_DURATION_MS = 250
_ANIMATION_EASING = QEasingCurve.Type.OutCubic
_ROW_TARGET_HEIGHT = 40


def _clean_reason(reason: str, file_path: str) -> str:
    """去掉错误原因中的「路径:」前缀, 便于在行内显示。"""
    prefix = f"{file_path}: "
    if reason.startswith(prefix):
        return reason[len(prefix) :]
    return reason


class ImportFileRow(QFrame):
    """单个导入文件行: 图标 + 文件名 + 状态区。"""

    def __init__(self, file_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._status = "waiting"
        self._status_anim: QPropertyAnimation | None = None
        self._fade_anim: QPropertyAnimation | None = None
        self._opacity_anim: QPropertyAnimation | None = None
        self.setObjectName("ImportFileRow")
        self.setFixedHeight(_ROW_TARGET_HEIGHT)
        self._setup_ui()
        self.set_status("waiting")

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        file_icon = IconWidget(FluentIcon.DOCUMENT)
        file_icon.setFixedSize(16, 16)
        file_icon.setObjectName("ImportFileIcon")
        layout.addWidget(file_icon)

        self._name_label = QLabel(Path(self._file_path).name)
        self._name_label.setObjectName("ImportFileName")
        layout.addWidget(self._name_label, stretch=1)

        self._status_icon = IconWidget()
        self._status_icon.setFixedSize(16, 16)
        self._status_icon.setObjectName("ImportFileStatusIcon")
        self._status_icon.setVisible(False)
        layout.addWidget(self._status_icon)

        self._spinner = IndeterminateProgressRing(self)
        self._spinner.setFixedSize(16, 16)
        self._spinner.setVisible(False)
        layout.addWidget(self._spinner)

        self._status_label = QLabel("等待中")
        self._status_label.setObjectName("ImportFileStatus")
        layout.addWidget(self._status_label)

    def status(self) -> str:
        """返回当前状态。"""
        return self._status

    def set_status(self, status: str, reason: str | None = None) -> None:
        """更新行状态并触发过渡动画。"""
        self._status = status
        self.setProperty("status", status)
        self._repolish(self)
        self._status_icon.setVisible(status in ("completed", "failed"))
        self._spinner.setVisible(status == "importing")
        if status == "waiting":
            self._status_label.setText("等待中")
        elif status == "importing":
            self._status_label.setText("导入中")
        elif status == "completed":
            self._status_label.setText("完成")
            self._status_icon.setIcon(FluentIcon.ACCEPT)
            self._status_icon.setProperty("status", "completed")
            self._repolish(self._status_icon)
        elif status == "failed":
            self._status_icon.setIcon(FluentIcon.CANCEL)
            self._status_icon.setProperty("status", "failed")
            self._repolish(self._status_icon)
            text = "失败"
            if reason:
                text += f"：{_clean_reason(reason, self._file_path)}"
            self._status_label.setText(text)
        self._repolish(self._status_label)
        self._animate_transition()

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _animate_transition(self) -> None:
        """状态迁移时透明度 0.7 -> 1.0, 250ms OutCubic。"""
        effect = self.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        effect.setOpacity(0.7)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(_ANIMATION_DURATION_MS)
        anim.setStartValue(0.7)
        anim.setEndValue(1.0)
        anim.setEasingCurve(_ANIMATION_EASING)
        anim.start()
        self._status_anim = anim

    def fade_in(self) -> None:
        """新增行时高度 0 -> 40、透明度 0 -> 1 展开。"""
        self.setMaximumHeight(0)
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.0)
        self.setGraphicsEffect(effect)

        height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        height_anim.setDuration(_ANIMATION_DURATION_MS)
        height_anim.setStartValue(0)
        height_anim.setEndValue(_ROW_TARGET_HEIGHT)
        height_anim.setEasingCurve(_ANIMATION_EASING)
        height_anim.start()

        opacity_anim = QPropertyAnimation(effect, b"opacity", self)
        opacity_anim.setDuration(_ANIMATION_DURATION_MS)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(_ANIMATION_EASING)
        opacity_anim.start()

        self._fade_anim = height_anim
        self._opacity_anim = opacity_anim


class ImportFileList(QFrame):
    """导入文件列表容器, 包含文件行、完成汇总与「开始校验」按钮。"""

    start_validate_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportFileList")
        self._rows: list[ImportFileRow] = []
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        self._rows_container = QWidget()
        rows_layout = QVBoxLayout(self._rows_container)
        rows_layout.setSpacing(4)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._rows_container)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("ImportFileSummary")
        self._summary_label.setVisible(False)
        layout.addWidget(self._summary_label)

        self._start_btn = QPushButton("开始校验")
        self._start_btn.setObjectName("BtnPrimary")
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self.start_validate_clicked.emit)
        self._start_btn.setVisible(False)
        layout.addWidget(self._start_btn)

    def set_files(self, file_paths: list[str]) -> None:
        """重置并填充文件列表, 所有行初始为「等待中」。"""
        self.clear()
        self.setVisible(True)
        self._summary_label.setVisible(False)
        self._start_btn.setVisible(False)
        rows_layout = self._rows_container.layout()
        assert rows_layout is not None
        for path in file_paths:
            row = ImportFileRow(path)
            self._rows.append(row)
            rows_layout.addWidget(row)
            row.fade_in()

    def set_importing(self, index: int) -> None:
        """将指定索引行设为「导入中」。"""
        if 0 <= index < len(self._rows):
            self._rows[index].set_status("importing")

    def set_completed(self, index: int) -> None:
        """将指定索引行设为「完成」。"""
        if 0 <= index < len(self._rows):
            self._rows[index].set_status("completed")

    def set_failed(self, index: int, reason: str) -> None:
        """将指定索引行设为「失败」并显示原因。"""
        if 0 <= index < len(self._rows):
            self._rows[index].set_status("failed", reason)

    def finish_batch(self, total_reports: int, total_detail_rows: int) -> None:
        """全部文件处理完成后显示汇总与「开始校验」按钮。"""
        self._summary_label.setText(
            f"共 {len(self._rows)} 个文件，{total_reports} 张报表、{total_detail_rows} 行明细"
        )
        self._summary_label.setVisible(True)
        self._start_btn.setVisible(total_reports > 0 or total_detail_rows > 0)

    def fail_all_pending(self, reason: str) -> None:
        """批量异常收尾: 未到终态的行全部标记失败并显示中止汇总 (无开始按钮)。

        后台导入线程整体异常时, 正在导入/等待中的行不会再收到任何事件,
        不收尾会永远停在「导入中」且汇总与「开始校验」永不出现。
        """
        pending = 0
        for row in self._rows:
            if row.status() not in ("completed", "failed"):
                row.set_status("failed", reason)
                pending += 1
        brief = reason if len(reason) <= 80 else reason[:80] + "…"
        if pending:
            self._summary_label.setText(f"导入已中止: {pending} 个文件未完成（{brief}）")
        else:
            self._summary_label.setText(f"导入失败: {brief}")
        self._summary_label.setVisible(True)
        self._start_btn.setVisible(False)

    def clear(self) -> None:
        """清空列表并重置状态。"""
        rows_layout = self._rows_container.layout()
        assert rows_layout is not None
        for row in self._rows:
            row.hide()
            rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows = []
        self._summary_label.setVisible(False)
        self._start_btn.setVisible(False)
        self.setVisible(False)
