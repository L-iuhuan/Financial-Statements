"""历史记录页面: 展示历次校验记录。

匹配 Demo v4 设计: 历史卡片列表 + 空状态。
从 SQLite 加载校验历史, 通过 history_changed 信号自动刷新。
"""

from __future__ import annotations

import sqlite3

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget

from fsa.gui.app_state import AppState
from fsa.gui.theme import get_mono_font
from fsa.storage.history_repo import HistoryRecord


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
        source_files: list[str] | None = None,
        rule_version: str = "",
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
        date_label.setObjectName("RuleName")
        date_label.setMinimumWidth(0)
        info.addWidget(date_label)

        files = source_files or []
        meta_parts = [f"报告期间: {period}"]
        if files:
            meta_parts.append(f"源文件: {len(files)} 个")
        if rule_version:
            meta_parts.append(f"规则 CAS v{rule_version}")
        period_label = QLabel(" · ".join(meta_parts))
        period_label.setObjectName("MetaLabel")
        period_label.setMinimumWidth(0)
        if files:
            period_label.setToolTip("\n".join(files))
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
            num = QLabel(f"{count:,}")
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
        self._all_records: list[HistoryRecord] = []
        self._search_text = ""
        self._history_loaded = False
        self._setup_ui()
        self._connect_signals()
        # 注意: _load_history() 延迟到首次展示时调用 (见 _show_hook)

    def _show_hook(self) -> None:
        """首次展示时加载历史数据 (仅一次)。"""
        if not self._history_loaded:
            self._history_loaded = True
            self._load_history()

    def _connect_signals(self) -> None:
        self._state.history_changed.connect(self._load_history)
        self._search_input.textChanged.connect(self._on_search_changed)

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题 + 搜索 + 对比
        title_row = QHBoxLayout()
        title = QLabel("校验历史")
        title.setObjectName("PageTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self._search_input = QLineEdit()
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText("搜索期间 / 源文件 / 规则版本")
        self._search_input.setFixedWidth(260)
        self._search_input.setClearButtonEnabled(True)
        title_row.addWidget(self._search_input)
        self._compare_btn = QPushButton("对比最近两次")
        self._compare_btn.setObjectName("BtnSecondary")
        self._compare_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compare_btn.clicked.connect(self._compare_recent_two)
        self._compare_btn.setEnabled(False)
        title_row.addWidget(self._compare_btn)
        layout.addLayout(title_row)

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

        self._all_records = records
        self._compare_btn.setEnabled(len(records) >= 2)
        self._rebuild_cards(records)

    def _on_search_changed(self, text: str) -> None:
        """搜索历史记录 (期间/日期/源文件/规则版本)。"""
        self._search_text = text.strip().lower()
        self._rebuild_cards(self._all_records)

    def _record_matches_search(self, record: HistoryRecord) -> bool:
        """判断历史记录是否匹配当前搜索文本。"""
        if not self._search_text:
            return True
        haystack_parts: list[str] = [
            str(record.get("period", "")),
            str(record.get("created_at", "")),
            str(record.get("rule_version", "")),
            "、".join(str(r) for r in record.get("report_types", [])),
        ]
        source_files = record.get("source_files", [])
        if isinstance(source_files, list):
            haystack_parts.extend(str(path) for path in source_files)
        return self._search_text in "\n".join(haystack_parts).lower()

    def _rebuild_cards(self, records: list[HistoryRecord]) -> None:
        """按当前搜索条件重建卡片列表。"""
        for card in self._cards:
            card.hide()
            card.deleteLater()
        self._cards.clear()

        filtered = [record for record in records if self._record_matches_search(record)]
        if not filtered:
            if records:
                self._show_no_match()
            else:
                self._show_empty()
            return

        self._empty_container.hide()
        self._cards_container.show()
        for record in filtered:
            card = HistoryCard(
                history_id=int(record["id"]),
                date=str(record["created_at"]),
                period=str(record["period"] or "未设置"),
                total=int(record["total"]),
                passed=int(record["passed"]),
                failed=int(record["failed"]),
                errored=int(record["errored"]),
                source_files=(
                    list(record["source_files"])
                    if isinstance(record.get("source_files"), list)
                    else []
                ),
                rule_version=str(record.get("rule_version", "")),
            )
            card.delete_clicked.connect(self._on_delete_history)
            card.view_clicked.connect(self.view_requested.emit)
            self._cards_layout.addWidget(card)
            self._cards.append(card)

    def _show_no_match(self) -> None:
        """搜索无匹配时显示空态。"""
        self._empty_container.show()
        self._cards_container.hide()

    def _compare_recent_two(self) -> None:
        """对比最近两次校验结果: 展示每条规则的状态变化。"""
        repo = self._state.history_repo
        if repo is None:
            return
        records = repo.get_recent(limit=2)
        if len(records) < 2:
            self._compare_btn.setEnabled(False)
            return

        older, newer = records[1], records[0]
        try:
            older_results = repo.get_detail(older["id"])
            newer_results = repo.get_detail(newer["id"])
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("加载对比明细失败")
            return

        status_of: dict[str, dict[str, str]] = {}
        for prefix, results in (("前", older_results), ("后", newer_results)):
            for result in results:
                if result.errored:
                    status = "异常"
                elif result.skipped:
                    status = "跳过"
                elif result.passed:
                    status = "通过"
                else:
                    status = "不通过"
                status_of.setdefault(result.rule_id, {"name": result.rule_name})
                status_of[result.rule_id][prefix] = status

        dialog = QDialog(self)
        dialog.setWindowTitle("最近两次校验结果对比")
        layout = QVBoxLayout(dialog)
        info = QLabel(
            f"前一次: {older['period'] or '未设置'}  ·  "
            f"后一次: {newer['period'] or '未设置'}"
        )
        info.setObjectName("MetaLabel")
        layout.addWidget(info)

        table = QTableWidget(len(status_of), 5)
        table.setHorizontalHeaderLabels(["规则 ID", "规则名称", "前一次", "后一次", "变化"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.horizontalHeader().setStretchLastSection(True)
        for row_idx, (rule_id, item) in enumerate(sorted(status_of.items())):
            before = item.get("前", "—")
            after = item.get("后", "—")
            changed = "相同" if before == after else f"{before} → {after}"
            table.setItem(row_idx, 0, QTableWidgetItem(rule_id))
            table.setItem(row_idx, 1, QTableWidgetItem(item.get("name", "")))
            table.setItem(row_idx, 2, QTableWidgetItem(before))
            table.setItem(row_idx, 3, QTableWidgetItem(after))
            table.setItem(row_idx, 4, QTableWidgetItem(changed))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.resize(760, 480)
        dialog.exec()

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
