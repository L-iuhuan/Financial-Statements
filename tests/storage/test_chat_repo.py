"""ChatRepo AI 对话仓库测试。

覆盖: 创建会话、读取列表、追加消息、删除会话、更新标题。
"""

from __future__ import annotations

import pytest

from fsa.storage.chat_repo import ChatRepo


class TestChatRepoCreateSession:
    """创建会话测试。"""

    def test_create_session_returns_valid_id(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act
        session_id = chat_repo.create_session()

        # Assert
        assert session_id > 0

    def test_create_session_with_title(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act
        session_id = chat_repo.create_session(title="关于 BS-BAL-001")

        # Assert
        sessions = chat_repo.get_sessions()
        assert sessions[0]["title"] == "关于 BS-BAL-001"

    def test_create_session_with_context_rule_id(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act
        session_id = chat_repo.create_session(
            context_rule_id="BS-BAL-001"
        )

        # Assert
        sessions = chat_repo.get_sessions()
        assert sessions[0]["context_rule_id"] == "BS-BAL-001"

    def test_create_session_default_title(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act
        chat_repo.create_session()

        # Assert
        sessions = chat_repo.get_sessions()
        assert sessions[0]["title"] == "新对话"


class TestChatRepoGetSessions:
    """读取会话列表测试。"""

    def test_get_sessions_empty(self, chat_repo: ChatRepo) -> None:
        # Act
        result = chat_repo.get_sessions()

        # Assert
        assert result == []

    def test_get_sessions_returns_desc_order(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        for i in range(3):
            chat_repo.create_session(title=f"会话{i}")

        # Act
        result = chat_repo.get_sessions()

        # Assert
        assert len(result) == 3
        assert result[0]["title"] == "会话2"
        assert result[2]["title"] == "会话0"

    def test_get_sessions_respects_limit(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        for _ in range(10):
            chat_repo.create_session()

        # Act
        result = chat_repo.get_sessions(limit=5)

        # Assert
        assert len(result) == 5

    def test_get_sessions_includes_all_fields(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act
        chat_repo.create_session(title="测试", context_rule_id="R1")
        result = chat_repo.get_sessions()

        # Assert
        record = result[0]
        assert record["id"] > 0
        assert record["created_at"] != ""
        assert record["updated_at"] != ""
        assert record["title"] == "测试"
        assert record["context_rule_id"] == "R1"


class TestChatRepoAddMessage:
    """追加消息测试。"""

    def test_add_message_returns_valid_id(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        message_id = chat_repo.add_message(session_id, "user", "你好")

        # Assert
        assert message_id > 0

    def test_add_user_message(self, chat_repo: ChatRepo) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        chat_repo.add_message(session_id, "user", "这是什么规则?")

        # Assert
        messages = chat_repo.get_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "这是什么规则?"

    def test_add_assistant_message(self, chat_repo: ChatRepo) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        chat_repo.add_message(
            session_id, "assistant", "这是资产=负债+所有者权益的校验规则。"
        )

        # Assert
        messages = chat_repo.get_messages(session_id)
        assert messages[0]["role"] == "assistant"

    def test_add_multiple_messages_preserve_order(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        chat_repo.add_message(session_id, "user", "第一条")
        chat_repo.add_message(session_id, "assistant", "第二条")
        chat_repo.add_message(session_id, "user", "第三条")

        # Assert
        messages = chat_repo.get_messages(session_id)
        assert len(messages) == 3
        assert messages[0]["content"] == "第一条"
        assert messages[1]["content"] == "第二条"
        assert messages[2]["content"] == "第三条"

    def test_add_message_updates_session_updated_at(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()
        before = chat_repo.get_sessions()[0]["updated_at"]

        # Act
        chat_repo.add_message(session_id, "user", "测试消息")
        after = chat_repo.get_sessions()[0]["updated_at"]

        # Assert
        assert after >= before

    def test_add_message_invalid_role_raises(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act + Assert
        with pytest.raises(ValueError, match="消息角色必须是"):
            chat_repo.add_message(session_id, "system", "非法角色")

    def test_add_message_empty_content_allowed(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        message_id = chat_repo.add_message(session_id, "user", "")

        # Assert
        assert message_id > 0
        messages = chat_repo.get_messages(session_id)
        assert messages[0]["content"] == ""


class TestChatRepoGetMessages:
    """读取消息测试。"""

    def test_get_messages_empty_session(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        result = chat_repo.get_messages(session_id)

        # Assert
        assert result == []

    def test_get_messages_nonexistent_session_returns_empty(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act
        result = chat_repo.get_messages(9999)

        # Assert
        assert result == []

    def test_get_messages_includes_all_fields(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        chat_repo.add_message(session_id, "user", "测试内容")
        result = chat_repo.get_messages(session_id)

        # Assert
        record = result[0]
        assert record["id"] > 0
        assert record["role"] == "user"
        assert record["content"] == "测试内容"
        assert record["created_at"] != ""


class TestChatRepoDeleteSession:
    """删除会话测试。"""

    def test_delete_session_removes_it(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()

        # Act
        chat_repo.delete_session(session_id)

        # Assert
        assert chat_repo.count_sessions() == 0

    def test_delete_session_cascades_messages(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        session_id = chat_repo.create_session()
        chat_repo.add_message(session_id, "user", "消息1")
        chat_repo.add_message(session_id, "assistant", "消息2")

        # Act
        chat_repo.delete_session(session_id)

        # Assert
        assert chat_repo.get_messages(session_id) == []

    def test_delete_nonexistent_session_is_noop(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act (should not raise)
        chat_repo.delete_session(9999)


class TestChatRepoUpdateTitle:
    """更新标题测试。"""

    def test_update_title(self, chat_repo: ChatRepo) -> None:
        # Arrange
        session_id = chat_repo.create_session(title="旧标题")

        # Act
        chat_repo.update_title(session_id, "新标题")

        # Assert
        sessions = chat_repo.get_sessions()
        assert sessions[0]["title"] == "新标题"

    def test_update_title_nonexistent_session_is_noop(
        self, chat_repo: ChatRepo
    ) -> None:
        # Act (should not raise)
        chat_repo.update_title(9999, "不存在")


class TestChatRepoCount:
    """计数测试。"""

    def test_count_sessions_empty(self, chat_repo: ChatRepo) -> None:
        assert chat_repo.count_sessions() == 0

    def test_count_sessions_after_creates(
        self, chat_repo: ChatRepo
    ) -> None:
        # Arrange
        for _ in range(5):
            chat_repo.create_session()

        # Act + Assert
        assert chat_repo.count_sessions() == 5
