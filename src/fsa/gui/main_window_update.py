"""主窗口软件更新集成 (mixin): 顶栏角标 -> 更新对话框。

从 main_window 拆出的更新入口接线: 启动检查发现新版时显示顶栏角标,
点击角标弹出更新对话框 (模态)。由 MainWindow 继承组合使用。

依赖宿主 (MainWindow) 提供的属性: _topbar (widgets.topbar.Topbar)。
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame

from fsa.gui.update_dialog import UpdateDialog
from fsa.gui.widgets.topbar import Topbar
from fsa.updater.updater import UpdateInfo


class MainWindowUpdateMixin(QFrame):
    """顶栏更新角标与更新对话框接线 (QFrame 继承仅用于类型标注, 运行期由宿主组合)。"""

    _topbar: Topbar
    # 启动检查发现的新版本信息缓存 (供对话框使用); 由 app.py 注入
    _pending_update_info: UpdateInfo | None = None

    def show_update_badge(self, version: str) -> None:
        """显示顶栏更新角标 (带版本 tooltip)。"""
        self._topbar.show_update_badge(version)

    def hide_update_badge(self) -> None:
        """隐藏顶栏更新角标。"""
        self._topbar.hide_update_badge()

    def _open_update_dialog(self) -> None:
        """点击角标弹出更新对话框 (无可用更新信息时不弹)。"""
        info = self._pending_update_info
        if not isinstance(info, UpdateInfo):
            return
        dialog = UpdateDialog(info, parent=self)
        dialog.exec()
        dialog.deleteLater()
