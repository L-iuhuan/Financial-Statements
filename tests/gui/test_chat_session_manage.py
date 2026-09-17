"""AI 会话管理补全测试：删除当前会话 / 清空全部会话。"""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from fsa.gui.widgets.agent_drawer import AgentDrawer


class _SpyChatRepo:
    """记录调用并模拟少量会话的 ChatRepo 替身。"""

    def __init__(self, sessions: list[dict[str, object]] | None = None) -> None:
        self.sessions: list[dict[str, object]] = sessions or [{"id": 1, "title": "新对话"}]
        self.calls: list[tuple[str, object]] = []
        self._next_id = max((cast(int, s["id"]) for s in self.sessions), default=0) + 1

    def get_sessions(self, limit: int = 50) -> list[dict[str, object]]:
        return self.sessions[:limit]

    def create_session(self, title: str = "新对话", context_rule_id: str = "") -> int:
        sid = self._next_id
        self._next_id += 1
        self.sessions.insert(0, {"id": sid, "title": title})
        return sid

    def get_messages(self, session_id: int) -> list[dict[str, object]]:
        return []

    def add_message(self, session_id: int, role: str, content: str) -> None:
        pass

    def update_title(self, session_id: int, title: str) -> None:
        pass

    def clear_messages(self, session_id: int) -> None:
        self.calls.append(("clear_messages", session_id))

    def delete_session(self, session_id: int) -> None:
        self.calls.append(("delete_session", session_id))
        self.sessions = [s for s in self.sessions if s["id"] != session_id]

    def delete_all_sessions(self) -> int:
        count = len(self.sessions)
        self.calls.append(("delete_all_sessions", count))
        self.sessions = []
        return count

    def count_sessions(self) -> int:
        return len(self.sessions)


class TestDeleteCurrentSession:
    """删除当前会话的确认与刷新。"""

    def test_cancelled_does_not_delete(self, qapp, qtbot) -> None:
        """取消确认后不调 delete_session。"""
        repo = _SpyChatRepo()
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)
        drawer._session_id = 1

        with patch.object(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No):
            drawer._delete_current_session()

        assert not any(c[0] == "delete_session" for c in repo.calls)
        assert drawer._session_id == 1

    def test_confirmed_selects_latest_remaining(self, qapp, qtbot) -> None:
        """删除当前会话后，自动切换到最近的剩余会话。"""
        repo = _SpyChatRepo([{"id": 1, "title": "A"}, {"id": 2, "title": "B"}])
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)
        drawer._session_id = 1

        with patch.object(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes):
            drawer._delete_current_session()

        assert ("delete_session", 1) in repo.calls
        assert drawer._session_id == 2

    def test_confirmed_last_session_creates_new(self, qapp, qtbot) -> None:
        """删除唯一会话后，自动新建空会话。"""
        repo = _SpyChatRepo([{"id": 1, "title": "A"}])
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)
        drawer._session_id = 1

        with patch.object(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes):
            drawer._delete_current_session()

        assert ("delete_session", 1) in repo.calls
        assert drawer._session_id == 2
        assert repo.sessions[0]["id"] == 2


class TestClearAllSessions:
    """清空全部会话的强确认与刷新。"""

    def test_cancelled_does_not_clear(self, qapp, qtbot) -> None:
        """取消确认后不调 delete_all_sessions。"""
        repo = _SpyChatRepo([{"id": 1, "title": "A"}])
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)

        with patch.object(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No):
            drawer._clear_all_sessions()

        assert not any(c[0] == "delete_all_sessions" for c in repo.calls)

    def test_confirmed_clears_and_creates_new(self, qapp, qtbot) -> None:
        """确认清空全部后，删除所有会话并新建空会话。"""
        repo = _SpyChatRepo([{"id": 1, "title": "A"}, {"id": 2, "title": "B"}])
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)
        drawer._session_id = 1

        with patch.object(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes):
            drawer._clear_all_sessions()

        assert ("delete_all_sessions", 2) in repo.calls
        assert drawer._session_id == 3
        assert repo.sessions[0]["id"] == 3

    def test_clear_all_button_hidden_without_repo(self, qapp, qtbot) -> None:
        """无 chat_repo 时「全部清空」按钮不显示。"""
        drawer = AgentDrawer(chat_repo=None)
        qtbot.addWidget(drawer)

        assert drawer._clear_all_btn.isHidden()
