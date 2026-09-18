"""主体选择对话框：从多主体根目录中勾选要做校验/对比的主体。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class EntitySelectDialog(QDialog):
    """让用户勾选一组主体（子文件夹名）的模态对话框。"""

    def __init__(
        self,
        entities: list[str],
        descriptions: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entities = entities
        self._descriptions = descriptions or {}
        self.setWindowTitle("选择主体")
        self.setModal(True)
        self.resize(420, 460)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("选择要校验/对比的主体")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("勾选要校验的主体；选择 2 个即可做跨主体双边核对")
        subtitle.setObjectName("MetaLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._list = QListWidget()
        self._list.setObjectName("EntitySelectList")
        for entity in self._entities:
            item = QListWidgetItem(entity)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            desc = self._descriptions.get(entity)
            if desc:
                item.setToolTip(desc)
            self._list.addItem(item)
        self._list.itemChanged.connect(self._update_count)
        layout.addWidget(self._list)

        bottom = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_none_btn = QPushButton("全不选")
        for btn in (select_all_btn, select_none_btn):
            btn.setObjectName("BtnSecondary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # 最小高度而非固定高度: 高 DPI/字体缩放下固定像素会裁切文字
            btn.setMinimumHeight(32)
        select_all_btn.clicked.connect(self._select_all)
        select_none_btn.clicked.connect(self._select_none)
        bottom.addWidget(select_all_btn)
        bottom.addWidget(select_none_btn)
        bottom.addStretch()

        self._count_label = QLabel("")
        self._count_label.setObjectName("MetaLabel")
        bottom.addWidget(self._count_label)
        layout.addLayout(bottom)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("开始校验")
        ok_btn.setObjectName("BtnPrimary")
        ok_btn.setMinimumHeight(32)
        cancel_btn = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("取消")
        cancel_btn.setObjectName("BtnSecondary")
        cancel_btn.setMinimumHeight(32)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._update_count()

    def _select_all(self) -> None:
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Checked)

    def _select_none(self) -> None:
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _update_count(self) -> None:
        selected = self.selected_entities()
        self._count_label.setText(f"已选 {len(selected)} / {len(self._entities)} 个主体")
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(selected))

    def selected_entities(self) -> list[str]:
        """按原始顺序返回已勾选的主体名。"""
        return [
            self._list.item(i).text()
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]
