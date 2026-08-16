"""后台 LLM 任务执行器。

将 AI 诊断、深度辩论等长耗时的 LLM 调用放入后台线程执行,
避免阻塞主线程导致界面 (UI) 冻结。
任务结果通过 QMetaObject.invokeMethod (QueuedConnection) 回传主线程。
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from loguru import logger
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Slot


class AgentWorker(QObject):
    """在后台线程运行一个无参可调用对象, 结果/错误/分块回传主线程。

    Args:
        target: 后台执行的任务 (无参, 返回 str)
        on_success: 主线程回调, 接收任务返回值
        on_error: 主线程回调, 接收错误信息 (str)
        on_finished: 主线程回调, 任务结束后调用 (无论成败), 用于恢复 UI 状态
        on_chunk: 主线程回调, 接收流式内容分块 (后台线程经 emit_chunk 回传)
        on_reasoning_chunk: 主线程回调, 接收流式推理分块 (后台线程经 emit_reasoning_chunk 回传)

    用法::

        worker = AgentWorker(target=..., on_success=..., on_error=..., on_finished=...)
        worker.start()
    """

    def __init__(
        self,
        target: Callable[[], str],
        on_success: Callable[[str], None],
        on_error: Callable[[str], None],
        on_finished: Callable[[], None] | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_reasoning_chunk: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._target = target
        self._on_success = on_success
        self._on_error = on_error
        self._on_finished = on_finished
        self._on_chunk = on_chunk
        self._on_reasoning_chunk = on_reasoning_chunk
        # P1 取消机制: 取消事件, 后台任务可读取检查, 任意线程可触发
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """请求取消当前后台任务 (幂等, 任意线程可调用)。

        后台任务应通过 cancel_event 检查取消状态并尽快退出;
        任务退出后按 on_error 路径把 LLMError("已取消") 回传主线程。
        """
        self._cancel_event.set()

    @property
    def cancel_event(self) -> threading.Event:
        """只读: 取消事件, 供后台任务检查取消状态。"""
        return self._cancel_event

    def start(self) -> None:
        """启动后台线程 (daemon, 不阻塞主线程)。"""
        threading.Thread(target=self._run, daemon=True).start()

    def emit_chunk(self, text: str) -> None:
        """后台线程调用: 将内容分块回传主线程 (经 on_chunk)。"""
        QMetaObject.invokeMethod(
            self,
            "_deliver_chunk",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, text),
        )

    def emit_reasoning_chunk(self, text: str) -> None:
        """后台线程调用: 将推理分块回传主线程 (经 on_reasoning_chunk)。"""
        QMetaObject.invokeMethod(
            self,
            "_deliver_reasoning_chunk",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, text),
        )

    def _run(self) -> None:
        try:
            value = self._target()
        except Exception as e:
            # 防御性兜底: 后台任务 (LLM 调用/辩论引擎) 可能抛出任意异常,
            # 必须回传主线程以中文提示用户, 不能让后台线程静默死亡
            logger.error(f"后台 LLM 任务失败: {e}")
            QMetaObject.invokeMethod(
                self,
                "_deliver_error",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"{type(e).__name__}: {e}"),
            )
        else:
            QMetaObject.invokeMethod(
                self,
                "_deliver_success",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, value),
            )
        finally:
            if self._on_finished is not None:
                QMetaObject.invokeMethod(
                    self,
                    "_deliver_finished",
                    Qt.ConnectionType.QueuedConnection,
                )

    @Slot(str)
    def _deliver_success(self, value: str) -> None:
        """主线程: 成功回传。已取消的任务结果不再投递（取消后竞态守卫）。"""
        if self._cancel_event.is_set():
            return
        self._on_success(value)

    @Slot(str)
    def _deliver_error(self, message: str) -> None:
        """主线程: 错误回传。"""
        self._on_error(message)

    @Slot(str)
    def _deliver_chunk(self, text: str) -> None:
        """主线程: 内容分块回传 (已取消后丢弃迟到的分块)。"""
        if self._cancel_event.is_set():
            return
        if self._on_chunk is not None:
            self._on_chunk(text)

    @Slot(str)
    def _deliver_reasoning_chunk(self, text: str) -> None:
        """主线程: 推理分块回传 (已取消后丢弃迟到的分块)。"""
        if self._cancel_event.is_set():
            return
        if self._on_reasoning_chunk is not None:
            self._on_reasoning_chunk(text)

    @Slot()
    def _deliver_finished(self) -> None:
        """主线程: 任务结束 (恢复 UI 状态)。"""
        if self._on_finished is not None:
            self._on_finished()
