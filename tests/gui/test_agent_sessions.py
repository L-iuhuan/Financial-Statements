"""AgentSessionMixin 会话管理基本测试 (offscreen, 替身 ChatRepo)。"""

from __future__ import annotations

from fsa.gui.widgets.agent_drawer import AgentDrawer


class _StubChatRepo:
    """内存版会话仓储替身 (方法签名与 ChatRepo 对齐)。"""

    def __init__(self) -> None:
        self.sessions: list[dict[str, object]] = [{"id": 1, "title": "新对话"}]
        self.messages: list[tuple[int, str, str]] = []
        self._next_id = 2

    def get_sessions(self, limit: int = 20) -> list[dict[str, object]]:
        return self.sessions[:limit]

    def create_session(self, title: str = "新对话") -> int:
        session_id = self._next_id
        self._next_id += 1
        self.sessions.insert(0, {"id": session_id, "title": title})
        return session_id

    def get_messages(self, session_id: int) -> list[dict[str, object]]:
        return [
            {"role": role, "content": content}
            for sid, role, content in self.messages
            if sid == session_id
        ]

    def add_message(self, session_id: int, role: str, content: str) -> None:
        self.messages.append((session_id, role, content))

    def update_title(self, session_id: int, title: str) -> None:
        for session in self.sessions:
            if session["id"] == session_id:
                session["title"] = title

    def clear_messages(self, session_id: int) -> None:
        self.messages = [m for m in self.messages if m[0] != session_id]


class TestSessionLoading:
    """初始化会话加载。"""

    def test_no_repo_hides_session_button(self, qapp, qtbot) -> None:
        """无仓储时隐藏会话选择按钮。"""
        drawer = AgentDrawer(None)
        qtbot.addWidget(drawer)

        assert drawer._session_btn.isHidden()
        assert drawer.get_chat_history() == []

    def test_loads_latest_session_on_init(self, qapp, qtbot) -> None:
        """有仓储时初始化即定位到最近会话。"""
        drawer = AgentDrawer(_StubChatRepo())  # type: ignore[arg-type]
        qtbot.addWidget(drawer)

        assert drawer._session_id == 1

    def test_new_session(self, qapp, qtbot) -> None:
        """新建会话切换 session_id 并清空消息区。"""
        repo = _StubChatRepo()
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)

        drawer._new_session()

        assert drawer._session_id == 2
        assert repo.sessions[0]["id"] == 2

    def test_switch_session_same_id_noop(self, qapp, qtbot) -> None:
        """切换到当前会话是无操作。"""
        drawer = AgentDrawer(_StubChatRepo())  # type: ignore[arg-type]
        qtbot.addWidget(drawer)
        drawer._messages_loaded = False

        drawer._switch_session(1)

        assert drawer._session_id == 1
        assert drawer._messages_loaded is False


class TestMessagePersistence:
    """消息持久化与历史读取。"""

    def test_persist_message_auto_renames(self, qapp, qtbot) -> None:
        """首条用户消息保存后自动以内容前 12 字重命名会话。"""
        repo = _StubChatRepo()
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)

        drawer._persist_message("user", "资产负债表不平怎么排查")

        assert repo.messages == [(1, "user", "资产负债表不平怎么排查")]
        assert repo.sessions[0]["title"] == "资产负债表不平怎么排查"

    def test_get_chat_history_converts(self, qapp, qtbot) -> None:
        """get_chat_history 返回 ChatMessage 列表 (时间正序)。"""
        repo = _StubChatRepo()
        repo.messages.append((1, "user", "问题一"))
        repo.messages.append((1, "assistant", "回答一"))
        drawer = AgentDrawer(repo)  # type: ignore[arg-type]
        qtbot.addWidget(drawer)

        history = drawer.get_chat_history(limit=10)

        assert [m.role for m in history] == ["user", "assistant"]
        assert history[0].content == "问题一"


class TestDrawerMinWidth:
    """C P2-4: 抽屉最小宽度对齐 DESIGN_SYSTEM §15.1。"""

    def test_min_width_280(self, qapp) -> None:
        assert AgentDrawer.MIN_WIDTH == 280
