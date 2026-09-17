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
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget, IndeterminateProgressRing

_ANIMATION_DURATION_MS = 250
_ANIMATION_EASING = QEasingCurve.Type.OutCubic
_ROW_TARGET_HEIGHT = 40
# 状态/失败原因列的最大宽度 (超出省略号截断, 完整内容见 tooltip) —— 无约束时
# 超长失败原因会把行撑破容器 (2026-09-17 实测溢出缺陷)
_STATUS_MAX_WIDTH = 320


def _clean_reason(reason: str, file_path: str) -> str:
    """去掉错误原因中的「路径:」前缀, 便于在行内显示。"""
    prefix = f"{file_path}: "
    if reason.startswith(prefix):
        return reason[len(prefix) :]
    return reason


class ImportFileRow(QFrame):
    """单个导入文件行: 图标 + 文件名 + 操作按钮 + 状态区。"""

    remove_requested = Signal(QWidget)
    retry_requested = Signal(QWidget)

    def __init__(self, file_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._full_name = Path(file_path).name
        self._status = "waiting"
        self._status_anim: QPropertyAnimation | None = None
        self._fade_anim: QPropertyAnimation | None = None
        self._opacity_anim: QPropertyAnimation | None = None
        self._remove_btn: QPushButton | None = None
        self._retry_btn: QPushButton | None = None
        self._action_container: QWidget | None = None
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

        self._name_label = QLabel(self._full_name)
        self._name_label.setObjectName("ImportFileName")
        # 超长文件名不撑破行宽: 水平方向不参与最小宽度协商 + resize 时中部截断
        self._name_label.setMinimumWidth(0)
        self._name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self._name_label.setToolTip(self._full_name)
        layout.addWidget(self._name_label, stretch=1)

        self._action_container = QWidget()
        action_layout = QHBoxLayout(self._action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)

        self._remove_btn = self._create_action_btn("移除")
        self._remove_btn.setToolTip("从列表移除该文件")
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        action_layout.addWidget(self._remove_btn)

        self._retry_btn = self._create_action_btn("重试")
        self._retry_btn.setToolTip("重新导入该文件")
        self._retry_btn.clicked.connect(self._on_retry_clicked)
        action_layout.addWidget(self._retry_btn)

        layout.addWidget(self._action_container)

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
        # 失败原因可能很长: 限宽 + 省略号截断, 完整原因见 tooltip
        self._status_label.setMaximumWidth(_STATUS_MAX_WIDTH)
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._status_label)

    def file_path(self) -> str:
        """返回文件完整路径。"""
        return self._file_path

    @staticmethod
    def _create_action_btn(text: str) -> QPushButton:
        """创建行内小型操作按钮（移除/重试）。"""
        btn = QPushButton(text)
        btn.setObjectName("TextBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setFixedWidth(44)
        return btn

    def _on_remove_clicked(self) -> None:
        """点击移除: completed 状态需确认, 其余直接移除。"""
        if self._status == "completed":
            answer = QMessageBox.question(
                self,
                "确认移除",
                "仅从列表移除，不影响已导入的报表",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.remove_requested.emit(self)

    def _on_retry_clicked(self) -> None:
        """点击重试: 通知外部执行单文件后台导入。"""
        self.retry_requested.emit(self)

    def _sync_action_buttons(self) -> None:
        """按当前状态显隐移除/重试按钮。"""
        if self._remove_btn is None or self._retry_btn is None:
            return
        self._remove_btn.setVisible(self._status != "importing")
        self._retry_btn.setVisible(self._status == "failed")
        if self._action_container is not None:
            self._action_container.setVisible(
                self._remove_btn.isVisible() or self._retry_btn.isVisible()
            )

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
        self._sync_action_buttons()
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
                full_reason = _clean_reason(reason, self._file_path)
                text += f"：{self._elide_reason(full_reason)}"
                self._status_label.setToolTip(full_reason)
            self._status_label.setText(text)
        self._repolish(self._status_label)
        self._apply_elided_name()
        self._animate_transition()

    def _elide_reason(self, reason: str) -> str:
        """失败原因按状态列宽度省略号截断 (完整原因见 tooltip)。"""
        fm = self._status_label.fontMetrics()
        prefix_width = fm.horizontalAdvance("失败：")
        return fm.elidedText(
            reason,
            Qt.TextElideMode.ElideRight,
            max(60, _STATUS_MAX_WIDTH - prefix_width),
        )

    def _apply_elided_name(self) -> None:
        """文件名按当前行宽中部截断 (保住扩展名), 全名见 tooltip。

        可用宽度按「行宽 - 固定占用 - 操作按钮区 - 状态区」确定性计算,
        不读 label 几何 —— resizeEvent 内 layout.activate() 会被 Qt 推迟到
        事件循环之后, label 宽度是旧值会导致省略号误判"放得下"
        (2026-09-17 溢出回归点)。
        """
        fm = self._name_label.fontMetrics()
        # 固定占用: 左右 margin 12+12, 文件图标 16, 文件名与按钮/按钮与状态区间距 8+8
        reserved = 12 + 16 + 8 + 8 + 8 + 12
        # 操作按钮区
        action_w = 0
        if self._action_container is not None and self._action_container.isVisible():
            action_w = self._action_container.sizeHint().width()
        # 状态区: 状态文本 (sizeHint 确定性计算, 上限 320) + 状态图标/转圈
        status_w = min(self._status_label.sizeHint().width(), _STATUS_MAX_WIDTH)
        if self._status_icon.isVisible():
            status_w += 16 + 8
        if self._spinner.isVisible():
            status_w += 16 + 8
        available = max(40, self.width() - reserved - action_w - status_w)
        self._name_label.setText(
            fm.elidedText(self._full_name, Qt.TextElideMode.ElideMiddle, available)
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """行宽变化时重新截断文件名, 防止超长名撑破容器。"""
        super().resizeEvent(event)
        self._apply_elided_name()

    def showEvent(self, event) -> None:  # type: ignore[override]
        """首次显示时按布局分配的实际宽度截断 (隐藏状态下 resize 事件被
        Qt 延迟到 show 时才派发, 初始截断不能只依赖 resizeEvent)。"""
        super().showEvent(event)
        self._apply_elided_name()

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
    row_retry_requested = Signal(QWidget)

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
        self._summary_label.setWordWrap(True)
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
            row.remove_requested.connect(self._on_row_remove)
            row.retry_requested.connect(self._on_row_retry)
            self._rows.append(row)
            rows_layout.addWidget(row)
            row.fade_in()

    def rows(self) -> list[ImportFileRow]:
        """返回当前所有文件行（只读副本）。"""
        return list(self._rows)

    def index_of(self, row: QWidget) -> int:
        """返回指定行在列表中的索引, 不存在返回 -1。"""
        if isinstance(row, ImportFileRow) and row in self._rows:
            return self._rows.index(row)
        return -1

    def _on_row_remove(self, row: QWidget) -> None:
        """从列表移除指定行。"""
        if not isinstance(row, ImportFileRow) or row not in self._rows:
            return
        self._rows.remove(row)
        rows_layout = self._rows_container.layout()
        assert rows_layout is not None
        rows_layout.removeWidget(row)
        row.hide()
        row.setParent(None)
        row.deleteLater()

    def _on_row_retry(self, row: QWidget) -> None:
        """将单文件重试请求转发给页面处理。"""
        if isinstance(row, ImportFileRow):
            self.row_retry_requested.emit(row)

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

    def set_validate_running(self, running: bool) -> None:
        """校验进行期间禁用「开始校验」按钮 (防连点触发多条提示叠加)。"""
        self._start_btn.setEnabled(not running)

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
