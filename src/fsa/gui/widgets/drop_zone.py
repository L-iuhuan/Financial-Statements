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
        self.setMinimumHeight(120)
        self.setObjectName("DropZone")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("拖拽 Excel 文件到此处")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #64748b; font-size: 14px;")
        layout.addWidget(hint)

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
