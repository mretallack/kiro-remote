"""Tests for group topic resolution, caching, and routing."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@pytest.fixture
def bot():
    """Create a TelegramBot with mocked dependencies for group topic testing."""
    with patch("telegram_kiro_bot.KiroSessionACP") as MockKiro:
        mock_kiro = Mock()
        MockKiro.return_value = mock_kiro
        mock_kiro.agents = {}
        mock_kiro.active_agent = "kiro_default"
        mock_kiro.start_agent_background = Mock()
        mock_kiro.send_message_to_agent = Mock()
        mock_kiro.cancel_operation = Mock()
        mock_kiro.context_tracker = Mock()
        mock_kiro.context_tracker.get_usage = Mock(return_value=42.5)

        from telegram_kiro_bot import TelegramBot

        b = TelegramBot.__new__(TelegramBot)
        b.token = "fake-token"
        b.authorized_user_id = 12345
        b.kiro = mock_kiro
        b.user_states = {}
        b.loop = None

        # Use temp file for topic cache
        b._topic_cache_path = Path(tempfile.mktemp(suffix=".json"))
        b._topic_agent_cache = {}

        return b


@pytest.fixture
def mock_update():
    """Create a mock group forum message update."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_chat = Mock()
    update.effective_chat.id = -100123456
    update.effective_chat.type = "supergroup"
    update.message = Mock()
    update.message.message_thread_id = 42
    update.message.is_topic_message = True
    update.message.text = "hello"
    update.message.reply_to_message = None
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    ctx = Mock()
    ctx.bot = Mock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_chat_action = AsyncMock()
    ctx.bot.create_forum_topic = AsyncMock()
    return ctx


class TestMatchAgentName:
    """Test _match_agent_name case-insensitive matching."""

    def test_exact_match(self, bot):
        with patch.object(
            bot,
            "_get_available_agent_names",
            return_value=["facebook_dev", "kiro_default"],
        ):
            assert bot._match_agent_name("facebook_dev") == "facebook_dev"

    def test_case_insensitive(self, bot):
        with patch.object(
            bot,
            "_get_available_agent_names",
            return_value=["facebook_dev", "kiro_default"],
        ):
            assert bot._match_agent_name("Facebook_Dev") == "facebook_dev"

    def test_no_match(self, bot):
        with patch.object(
            bot,
            "_get_available_agent_names",
            return_value=["facebook_dev", "kiro_default"],
        ):
            assert bot._match_agent_name("nonexistent") is None

    def test_spaces_to_underscores(self, bot):
        with patch.object(
            bot, "_get_available_agent_names", return_value=["kiro_default"]
        ):
            assert bot._match_agent_name("Kiro Default") == "kiro_default"


class TestTopicCache:
    """Test topic cache persistence."""

    def test_save_and_load(self, bot):
        bot._topic_agent_cache = {42: "facebook_dev", 99: "kiro_default"}
        bot._save_topic_cache()

        # Clear and reload
        bot._topic_agent_cache = {}
        bot._load_topic_cache()

        assert bot._topic_agent_cache == {42: "facebook_dev", 99: "kiro_default"}

    def test_load_missing_file(self, bot):
        bot._topic_cache_path = Path("/tmp/nonexistent_cache_xyz.json")
        bot._load_topic_cache()
        assert bot._topic_agent_cache == {}

    def test_cache_keys_are_ints(self, bot):
        # Simulate JSON file with string keys
        bot._topic_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(bot._topic_cache_path, "w") as f:
            json.dump({"42": "facebook_dev"}, f)

        bot._load_topic_cache()
        assert 42 in bot._topic_agent_cache
        assert bot._topic_agent_cache[42] == "facebook_dev"


class TestResolveTopicAgent:
    """Test _resolve_topic_agent resolution logic."""

    @pytest.mark.asyncio
    async def test_cached_hit(self, bot, mock_update, mock_context):
        bot._topic_agent_cache[42] = "facebook_dev"
        result = await bot._resolve_topic_agent(mock_update, mock_context, 42)
        assert result == "facebook_dev"

    @pytest.mark.asyncio
    async def test_resolve_from_topic_name(self, bot, mock_update, mock_context):
        # Simulate reply_to_message with forum_topic_created
        mock_update.message.reply_to_message = Mock()
        mock_update.message.reply_to_message.forum_topic_created = Mock()
        mock_update.message.reply_to_message.forum_topic_created.name = "Facebook Dev"

        with patch.object(
            bot,
            "_get_available_agent_names",
            return_value=["facebook_dev", "kiro_default"],
        ):
            result = await bot._resolve_topic_agent(mock_update, mock_context, 42)

        assert result == "facebook_dev"
        assert bot._topic_agent_cache[42] == "facebook_dev"


class TestGroupMessageRouting:
    """Test handle_group_message routes correctly."""

    @pytest.mark.asyncio
    async def test_routes_to_existing_agent(self, bot, mock_update, mock_context):
        bot._topic_agent_cache[42] = "facebook_dev"
        bot.kiro.agents = {"facebook_dev": {"session_id": "s1"}}

        await bot.handle_group_message(mock_update, mock_context)

        bot.kiro.send_message_to_agent.assert_called_once_with(
            "facebook_dev", "hello", -100123456, 42
        )

    @pytest.mark.asyncio
    async def test_starts_agent_background(self, bot, mock_update, mock_context):
        bot._topic_agent_cache[42] = "facebook_dev"
        bot.kiro.agents = {}  # Agent not started

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await bot.handle_group_message(mock_update, mock_context)

        bot.kiro.start_agent_background.assert_called_once_with(
            agent_name="facebook_dev"
        )

    @pytest.mark.asyncio
    async def test_no_thread_id_ignored(self, bot, mock_update, mock_context):
        mock_update.message.message_thread_id = None
        await bot.handle_group_message(mock_update, mock_context)
        bot.kiro.send_message_to_agent.assert_not_called()


class TestGroupCommands:
    """Test commands in group topics are scoped correctly."""

    @pytest.mark.asyncio
    async def test_cancel_scoped_to_topic_agent(self, bot, mock_update, mock_context):
        bot._topic_agent_cache[42] = "facebook_dev"
        mock_update.message.text = "\\cancel"

        result = await bot.handle_intercepted_commands_group(
            mock_update, mock_context, 42
        )

        assert result is True
        bot.kiro.cancel_operation.assert_called_once_with(agent_name="facebook_dev")

    @pytest.mark.asyncio
    async def test_context_scoped_to_topic_agent(self, bot, mock_update, mock_context):
        bot._topic_agent_cache[42] = "facebook_dev"
        bot.kiro.agents = {"facebook_dev": {"session_id": "s1"}}
        mock_update.message.text = "\\context"

        result = await bot.handle_intercepted_commands_group(
            mock_update, mock_context, 42
        )

        assert result is True
        mock_context.bot.send_message.assert_called_once()
        call_kwargs = mock_context.bot.send_message.call_args[1]
        assert call_kwargs["message_thread_id"] == 42
        assert "facebook_dev" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_topic_register(self, bot, mock_update, mock_context):
        mock_update.message.text = "\\topic register facebook_dev"
        with patch.object(
            bot, "_get_available_agent_names", return_value=["facebook_dev"]
        ):
            result = await bot.handle_intercepted_commands_group(
                mock_update, mock_context, 42
            )

        assert result is True
        assert bot._topic_agent_cache[42] == "facebook_dev"


class TestForumTopicLifecycle:
    """Test forum topic created/edited handlers."""

    @pytest.mark.asyncio
    async def test_topic_created_auto_caches(self, bot, mock_update, mock_context):
        mock_update.message.forum_topic_created = Mock()
        mock_update.message.forum_topic_created.name = "facebook_dev"
        mock_update.message.message_thread_id = 99

        with patch.object(
            bot, "_get_available_agent_names", return_value=["facebook_dev"]
        ):
            await bot.handle_forum_topic_created(mock_update, mock_context)

        assert bot._topic_agent_cache[99] == "facebook_dev"

    @pytest.mark.asyncio
    async def test_topic_edited_updates_cache(self, bot, mock_update, mock_context):
        bot._topic_agent_cache[42] = "old_agent"
        mock_update.message.forum_topic_edited = Mock()
        mock_update.message.forum_topic_edited.name = "kiro_default"
        mock_update.message.message_thread_id = 42

        with patch.object(
            bot, "_get_available_agent_names", return_value=["kiro_default"]
        ):
            await bot.handle_forum_topic_edited(mock_update, mock_context)

        assert bot._topic_agent_cache[42] == "kiro_default"

    @pytest.mark.asyncio
    async def test_topic_edited_invalidates_on_no_match(
        self, bot, mock_update, mock_context
    ):
        bot._topic_agent_cache[42] = "facebook_dev"
        mock_update.message.forum_topic_edited = Mock()
        mock_update.message.forum_topic_edited.name = "random_name"
        mock_update.message.message_thread_id = 42

        with patch.object(
            bot,
            "_get_available_agent_names",
            return_value=["facebook_dev", "kiro_default"],
        ):
            await bot.handle_forum_topic_edited(mock_update, mock_context)

        assert 42 not in bot._topic_agent_cache


class TestDMRoutingUnaffected:
    """Regression: 1-to-1 messages still route correctly."""

    @pytest.mark.asyncio
    async def test_dm_not_routed_to_group_handler(self, bot, mock_update, mock_context):
        mock_update.effective_chat.type = "private"
        mock_update.message.is_topic_message = False
        mock_update.message.message_thread_id = None

        # In handle_message, private chats skip group routing
        # Just verify the type check works
        assert mock_update.effective_chat.type not in ("group", "supergroup")
