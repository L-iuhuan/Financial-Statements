"""文件拖放区域组件。

用户可以将 .xlsx/.xls/.pdf 文件拖到此处, 触发 file_dropped 信号。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class DropZone(QFrame):
    """财务报表文件拖放区域。"""

    file_dropped = Signal(str)
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("DropZone")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("将财务报表文件拖拽到此处")
        hint.setObjectName("DropZoneText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        sub_hint = QLabel("支持 .xlsx / .xls / .pdf · 可一次拖入主表与附表（1~6）")
        sub_hint.setObjectName("DropZoneHint")
        sub_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_hint)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("drag", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setProperty("drag", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("drag", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        if not urls:
            return
        paths = [url.toLocalFile() for url in urls]
        supported = [
            path for path in paths if path.lower().endswith((".xlsx", ".xls", ".pdf"))
        ]
        if supported:
            event.acceptProposedAction()
            self.files_dropped.emit(supported)
            self.file_dropped.emit(supported[0])
