"""Tests that all bot handlers reject unauthorized user IDs."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

AUTHORIZED_ID = 99999
UNAUTHORIZED_ID = 11111


@pytest.fixture
def bot():
    with patch("telegram_kiro_bot.KiroSessionACP") as MockKiro:
        mock_kiro = Mock()
        MockKiro.return_value = mock_kiro

        from telegram_kiro_bot import TelegramBot

        b = TelegramBot.__new__(TelegramBot)
        b.token = "fake"
        b.authorized_user_id = AUTHORIZED_ID
        b.kiro = mock_kiro
        b.kiro.active_agent = "kiro_default"
        b.kiro.send_to_kiro = Mock()
        b.user_states = {}
        b._topic_agent_cache = {}
        return b


@pytest.fixture
def unauth_update():
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = UNAUTHORIZED_ID
    update.effective_user.username = "hacker"
    update.effective_chat = Mock()
    update.effective_chat.id = 123
    update.effective_chat.type = "private"
    update.message = Mock()
    update.message.text = "hello"
    update.message.reply_text = AsyncMock()
    update.message.photo = [Mock(file_id="abc123")]
    update.message.document = Mock(file_id="doc123", file_name="test.txt")
    update.message.caption = "test"
    update.message.forum_topic_created = Mock(name="test_topic")
    update.message.forum_topic_edited = Mock(name="renamed")
    update.message.message_thread_id = None
    return update


@pytest.fixture
def mock_context():
    ctx = Mock()
    ctx.bot = Mock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.get_file = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_handle_message_rejects_unauthorized(bot, unauth_update, mock_context):
    bot.loop = None
    await bot.handle_message(unauth_update, mock_context)
    bot.kiro.send_to_kiro.assert_not_called()


@pytest.mark.asyncio
async def test_handle_photo_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.handle_photo(unauth_update, mock_context)
    mock_context.bot.get_file.assert_not_called()


@pytest.mark.asyncio
async def test_handle_document_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.handle_document(unauth_update, mock_context)
    mock_context.bot.get_file.assert_not_called()


@pytest.mark.asyncio
async def test_handle_forum_topic_created_rejects_unauthorized(
    bot, unauth_update, mock_context
):
    await bot.handle_forum_topic_created(unauth_update, mock_context)
    # Should return early without caching
    assert bot._topic_agent_cache == {}


@pytest.mark.asyncio
async def test_handle_forum_topic_edited_rejects_unauthorized(
    bot, unauth_update, mock_context
):
    await bot.handle_forum_topic_edited(unauth_update, mock_context)
    assert bot._topic_agent_cache == {}


@pytest.mark.asyncio
async def test_list_agents_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.list_agents(unauth_update, mock_context)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_show_subagents_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.show_subagents(unauth_update, mock_context)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_show_usage_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.show_usage(unauth_update, mock_context)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_show_models_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.show_models(unauth_update, mock_context)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_set_model_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.set_model(unauth_update, mock_context, "claude-sonnet-4.5")
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_create_agent_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.create_agent(unauth_update, mock_context)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_switch_agent_rejects_unauthorized(bot, unauth_update, mock_context):
    await bot.switch_agent(unauth_update, mock_context)
    unauth_update.message.reply_text.assert_not_called()
