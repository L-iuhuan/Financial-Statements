"""历史记录页面: 展示历次校验记录。

匹配 Demo v4 设计: 历史卡片列表 + 空状态。
从 SQLite 加载校验历史, 通过 history_changed 信号自动刷新。
"""

from __future__ import annotations

import sqlite3

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget

from fsa.gui.app_state import AppState
from fsa.gui.theme import get_mono_font


class HistoryCard(QFrame):
    """单条历史记录卡片 (Demo v4)。

    - 40x40 图标 (brand-50 背景)
    - 日期 + 期间信息
    - 统计: 通过/不通过/异常 (primary 色值)
    - 查看 + 删除 按钮
    """

    view_clicked = Signal(int)
    delete_clicked = Signal(int)

    def __init__(
        self,
        history_id: int,
        date: str,
        period: str,
        total: int,
        passed: int,
        failed: int,
        errored: int,
    ) -> None:
        super().__init__()
        self._history_id = history_id
        self.setObjectName("HistoryCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 左侧: 40x40 图标
        icon_frame = QFrame()
        icon_frame.setObjectName("IconFrame")
        icon_frame.setFixedSize(40, 40)
        icon_layout = QHBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_widget = IconWidget(FluentIcon.HISTORY)
        icon_widget.setFixedSize(20, 20)
        icon_layout.addWidget(icon_widget)
        layout.addWidget(icon_frame)

        # 中间: 日期 + 期间 (允许压缩, 避免小窗口出现水平滚动条)
        info = QVBoxLayout()
        info.setSpacing(2)
        date_label = QLabel(date)
        date_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        date_label.setMinimumWidth(0)
        info.addWidget(date_label)

        period_label = QLabel(f"报告期间: {period}")
        period_label.setObjectName("MetaLabel")
        period_label.setMinimumWidth(0)
        info.addWidget(period_label)
        layout.addLayout(info, stretch=1)

        # 右侧: 统计 (通过/不通过/异常)
        stats = QHBoxLayout()
        stats.setSpacing(12)

        for label_text, count in [
            ("通过", passed),
            ("不通过", failed),
            ("异常", errored),
        ]:
            stat = QVBoxLayout()
            stat.setSpacing(0)
            num = QLabel(str(count))
            num.setFont(get_mono_font(14))
            num.setStyleSheet("font-size: 20px; font-weight: 700;")
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat.addWidget(num)

            lbl = QLabel(label_text)
            lbl.setObjectName("MetaLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat.addWidget(lbl)
            stats.addLayout(stat)

        layout.addLayout(stats)

        # 操作按钮: 查看 + 删除 (最小尺寸, 允许按文字扩展避免截断)
        view_btn = QPushButton("查看")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.setMinimumSize(56, 28)
        view_btn.setObjectName("TextBtn")
        view_btn.clicked.connect(self._on_view_clicked)
        layout.addWidget(view_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setMinimumSize(56, 28)
        delete_btn.setObjectName("DangerBtn")
        delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(delete_btn)

    def _on_view_clicked(self) -> None:
        self.view_clicked.emit(self._history_id)

    def _on_delete_clicked(self) -> None:
        self.delete_clicked.emit(self._history_id)


class HistoryPage(QWidget):
    """历史记录页面: 从 SQLite 加载校验历史并展示。"""

    view_requested = Signal(int)  # history_id -> 主窗口加载并跳转

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("HistoryPage")
        self._state = state
        self._cards: list[HistoryCard] = []
        self._setup_ui()
        self._connect_signals()

    def _connect_signals(self) -> None:
        self._state.history_changed.connect(self._load_history)

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题
        title = QLabel("校验历史")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        # 空状态
        self._empty_container = QFrame()
        self._empty_container.setObjectName("EmptyContainer")
        empty_layout = QVBoxLayout(self._empty_container)
        empty_layout.setContentsMargins(24, 48, 24, 48)
        empty_layout.setSpacing(8)

        empty_icon = IconWidget(FluentIcon.HISTORY)
        empty_icon.setFixedSize(48, 48)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel("暂无校验记录")
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_desc = QLabel(
            "完成校验后，历史记录将自动保存至此处。\n"
            "您可以随时回溯查看历次校验结果。"
        )
        empty_desc.setObjectName("EmptyLabel")
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_desc)

        # 卡片容器
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._empty_container)
        layout.addWidget(self._cards_container)
        layout.addStretch()

        scroll.setWidget(content)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        self._load_history()

    def _load_history(self) -> None:
        """从 SQLite 加载校验历史, 刷新卡片列表。"""
        repo = self._state.history_repo
        if repo is None:
            self._show_empty()
            return

        try:
            records = repo.get_recent(limit=50)
        except sqlite3.DatabaseError:
            logger.exception("加载校验历史失败")
            self._show_empty()
            return
        except RuntimeError:
            logger.exception("数据库未连接, 无法加载历史")
            self._show_empty()
            return

        # 清空旧卡片 (先隐藏再删除, 避免闪现为独立窗口)
        for card in self._cards:
            card.hide()
            card.deleteLater()
        self._cards.clear()

        if not records:
            self._show_empty()
            return

        # 创建新卡片
        self._empty_container.hide()
        self._cards_container.show()
        for record in records:
            card = HistoryCard(
                history_id=record["id"],
                date=record["created_at"],
                period=record["period"] or "未设置",
                total=record["total"],
                passed=record["passed"],
                failed=record["failed"],
                errored=record["errored"],
            )
            card.delete_clicked.connect(self._on_delete_history)
            card.view_clicked.connect(self.view_requested.emit)
            self._cards_layout.addWidget(card)
            self._cards.append(card)

    def _on_delete_history(self, history_id: int) -> None:
        """删除历史记录 (带二次确认) 并刷新列表。"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条校验记录吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        repo = self._state.history_repo
        if repo is None:
            return
        try:
            repo.delete(history_id)
        except sqlite3.DatabaseError:
            logger.exception("删除校验历史失败")
            return
        except RuntimeError:
            logger.exception("数据库未连接, 无法删除历史")
            return
        self._load_history()

    def _show_empty(self) -> None:
        """显示空状态。"""
        self._empty_container.show()
        self._cards_container.hide()
