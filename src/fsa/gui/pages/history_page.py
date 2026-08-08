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
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fsa.gui.app_state import AppState


class HistoryCard(QFrame):
    """单条历史记录卡片。"""

    view_clicked = Signal(int)

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
        self.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e5e7eb; "
            "border-radius: 8px; }"
            "QFrame:hover { border-color: #c7d2fe; }"
        )
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # 左侧: 日期 + 期间
        info = QVBoxLayout()
        info.setSpacing(2)
        date_label = QLabel(date)
        date_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #111827;"
        )
        info.addWidget(date_label)

        period_label = QLabel(f"报告期间: {period}")
        period_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        info.addWidget(period_label)
        layout.addLayout(info)
        layout.addStretch()

        # 右侧: 统计
        stats = QHBoxLayout()
        stats.setSpacing(20)

        for label_text, count, color in [
            ("通过", passed, "#10b981"),
            ("不通过", failed, "#ef4444"),
            ("异常", errored, "#f59e0b"),
        ]:
            stat = QVBoxLayout()
            stat.setSpacing(0)
            num = QLabel(str(count))
            num.setStyleSheet(
                f"font-size: 18px; font-weight: 700; color: {color};"
            )
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat.addWidget(num)

            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; color: #9ca3af;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat.addWidget(lbl)
            stats.addLayout(stat)

        layout.addLayout(stats)

        # 操作按钮
        view_btn = QPushButton("查看")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.setFixedSize(56, 32)
        view_btn.setStyleSheet(
            "QPushButton { background-color: #ffffff; color: #6b7280; "
            "border: 1px solid #e5e7eb; border-radius: 6px; font-size: 12px; }"
            "QPushButton:hover { background-color: #f3f4f6; }"
        )
        view_btn.clicked.connect(self._on_view_clicked)
        layout.addWidget(view_btn)

    def _on_view_clicked(self) -> None:
        self.view_clicked.emit(self._history_id)


class HistoryPage(QWidget):
    """历史记录页面: 从 SQLite 加载校验历史并展示。"""

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
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题
        title = QLabel("校验历史")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        # 空状态
        self._empty_container = QFrame()
        self._empty_container.setStyleSheet(
            "QFrame { background-color: #ffffff; "
            "border: 2px dashed #e5e7eb; border-radius: 8px; }"
        )
        empty_layout = QVBoxLayout(self._empty_container)
        empty_layout.setContentsMargins(24, 48, 24, 48)
        empty_layout.setSpacing(8)

        empty_icon = QLabel("📋")
        empty_icon.setStyleSheet("font-size: 48px;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel("暂无校验记录")
        empty_title.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #6b7280;"
        )
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_desc = QLabel(
            "完成校验后，历史记录将自动保存至此处。\n"
            "您可以随时回溯查看历次校验结果。"
        )
        empty_desc.setStyleSheet("font-size: 13px; color: #9ca3af;")
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

        # 清空旧卡片
        for card in self._cards:
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
            self._cards_layout.addWidget(card)
            self._cards.append(card)

    def _show_empty(self) -> None:
        """显示空状态。"""
        self._empty_container.show()
        self._cards_container.hide()
