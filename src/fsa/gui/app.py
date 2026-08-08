"""应用入口: 创建 QApplication, 加载规则, 显示主窗口。

启动方式:
    python -m fsa
"""

from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import apply_theme, get_qss


def main() -> None:
    """启动财务报表勾稽校验系统。"""

    def exception_hook(exctype, value, tb) -> None:
        logger.error(f"未处理异常: {value}", exc_info=(exctype, value, tb))
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    apply_theme()
    app.setStyleSheet(get_qss(False))

    state = AppState()
    ok, msg = state.load_registry()
    if not ok:
        logger.warning(f"规则库加载失败: {msg}")

    window = MainWindow(state)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
