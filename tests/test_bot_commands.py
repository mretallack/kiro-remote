"""Tests for Telegram bot command interception and routing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# We need to test handle_intercepted_commands and show_help
# without starting the full bot. We'll import TelegramBot and mock its dependencies.


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update object."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.username = "testuser"
    update.effective_chat = Mock()
    update.effective_chat.id = 12345
    update.message = Mock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    return Mock()


@pytest.fixture
def bot():
    """Create a TelegramBot with mocked dependencies."""
    with patch("telegram_kiro_bot.KiroSessionACP") as MockKiro:
        mock_kiro = Mock()
        MockKiro.return_value = mock_kiro

        from telegram_kiro_bot import TelegramBot

        b = TelegramBot.__new__(TelegramBot)
        b.token = "fake-token"
        b.authorized_user_id = 12345
        b.kiro = mock_kiro
        b.kiro.active_agent = "kiro_default"
        b.user_states = {}
        return b


@pytest.mark.asyncio
async def test_help_command_intercepted(bot, mock_update, mock_context):
    """Test that \\help command is intercepted and shows help text."""
    mock_update.message.text = "\\help"
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    mock_update.message.reply_text.assert_called_once()
    help_text = mock_update.message.reply_text.call_args[0][0]
    assert "Agent Management" in help_text
    assert "\\help" in help_text


@pytest.mark.asyncio
async def test_context_show_sent_as_message(bot, mock_update, mock_context):
    """Test that \\context show is forwarded as a message to Kiro."""
    mock_update.message.text = "\\context show"
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.kiro.send_message.assert_called_once_with("/context show", 12345)


@pytest.mark.asyncio
async def test_context_clear_sent_as_message(bot, mock_update, mock_context):
    """Test that \\context clear is forwarded as a message to Kiro."""
    mock_update.message.text = "\\context clear"
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.kiro.send_message.assert_called_once_with("/context clear", 12345)


@pytest.mark.asyncio
async def test_compact_sent_as_message(bot, mock_update, mock_context):
    """Test that \\compact is forwarded as a message to Kiro."""
    mock_update.message.text = "\\compact"
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.kiro.send_message.assert_called_once_with("/compact", 12345)


@pytest.mark.asyncio
async def test_cancel_command(bot, mock_update, mock_context):
    """Test that \\cancel calls cancel_operation."""
    mock_update.message.text = "\\cancel"
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.kiro.cancel_operation.assert_called_once()
    mock_update.message.reply_text.assert_called_once_with("🛑 Cancelling operation...")


@pytest.mark.asyncio
async def test_model_list_intercepted(bot, mock_update, mock_context):
    """Test that \\model list is intercepted."""
    mock_update.message.text = "\\model list"

    # Mock show_models to avoid full execution
    bot.show_models = AsyncMock()
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.show_models.assert_called_once()


@pytest.mark.asyncio
async def test_agent_list_intercepted(bot, mock_update, mock_context):
    """Test that \\agent list is intercepted."""
    mock_update.message.text = "\\agent list"

    bot.list_agents = AsyncMock()
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.list_agents.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_command_not_intercepted(bot, mock_update, mock_context):
    """Test that regular messages are not intercepted."""
    mock_update.message.text = "hello world"
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is False


@pytest.mark.asyncio
async def test_usage_command_intercepted(bot, mock_update, mock_context):
    """Test that \\usage is intercepted."""
    mock_update.message.text = "\\usage"

    bot.show_usage = AsyncMock()
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.show_usage.assert_called_once()


@pytest.mark.asyncio
async def test_agent_swap_intercepted(bot, mock_update, mock_context):
    """Test that \\agent swap <name> is intercepted."""
    mock_update.message.text = "\\agent swap myagent"

    bot.swap_agent = AsyncMock()
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.swap_agent.assert_called_once_with(mock_update, mock_context, "myagent")


@pytest.mark.asyncio
async def test_chat_save_intercepted(bot, mock_update, mock_context):
    """Test that \\chat save <name> is intercepted."""
    mock_update.message.text = "\\chat save mysession"

    bot.save_chat = AsyncMock()
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.save_chat.assert_called_once_with(mock_update, mock_context, "mysession")


@pytest.mark.asyncio
async def test_context_usage_no_subcommand(bot, mock_update, mock_context):
    """Test that \\context with no subcommand shows usage."""
    mock_update.message.text = "\\context"

    bot.show_context_usage = AsyncMock()
    result = await bot.handle_intercepted_commands(mock_update, mock_context)

    assert result is True
    bot.show_context_usage.assert_called_once()
