"""文件拖放区域组件。

用户可以将 .xlsx/.xls 文件拖到此处, 触发 file_dropped 信号。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class DropZone(QFrame):
    """Excel 文件拖放区域。"""

    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("DropZone")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("将财务报表 Excel 文件拖拽到此处")
        hint.setObjectName("DropZoneText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        sub_hint = QLabel("支持 .xlsx / .xls 格式 · 资产负债表、利润表、现金流量表")
        sub_hint.setObjectName("DropZoneHint")
        sub_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_hint)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "DropZone { border: 2px dashed #4f46e5; "
                "border-radius: 8px; background-color: #eef2ff; }"
            )

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path.lower().endswith((".xlsx", ".xls")):
            event.acceptProposedAction()
            self.file_dropped.emit(path)
