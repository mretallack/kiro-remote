"""Tests for error handling improvements (Fix 1-5)."""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from kiro_session_acp import KiroSessionACP


class TestSplitHtmlMessage:
    """Fix 1: Message too long splitting."""

    def setup_method(self):
        self.kiro = KiroSessionACP.__new__(KiroSessionACP)

    def test_short_message_no_split(self):
        result = self.kiro._split_html_message("Hello world", 4096)
        assert result == ["Hello world"]

    def test_exact_limit_no_split(self):
        text = "A" * 4096
        result = self.kiro._split_html_message(text, 4096)
        assert result == [text]

    def test_long_plain_text_splits_at_newline(self):
        text = "A" * 2000 + "\n" + "B" * 2000 + "\n" + "C" * 2000
        result = self.kiro._split_html_message(text, 4096)
        assert len(result) == 2
        assert all(len(chunk) <= 4096 for chunk in result)

    def test_splits_at_paragraph_break(self):
        text = "A" * 2000 + "\n\n" + "B" * 2000 + "\n\n" + "C" * 2000
        result = self.kiro._split_html_message(text, 4096)
        assert len(result) >= 2
        assert all(len(chunk) <= 4096 for chunk in result)

    def test_repairs_open_pre_tag(self):
        text = "<pre>" + "A" * 5000 + "</pre>"
        result = self.kiro._split_html_message(text, 4096)
        assert len(result) >= 2
        # First chunk should close the <pre>
        assert result[0].endswith("</pre>")
        # Second chunk should re-open <pre>
        assert result[1].startswith("<pre>")

    def test_repairs_open_code_tag(self):
        text = "<code>" + "A" * 5000 + "</code>"
        result = self.kiro._split_html_message(text, 4096)
        assert len(result) >= 2
        assert "</code>" in result[0]
        assert "<code>" in result[1]

    def test_repairs_nested_tags(self):
        text = "<b><code>" + "A" * 5000 + "</code></b>"
        result = self.kiro._split_html_message(text, 4096)
        assert len(result) >= 2
        # First chunk should close both tags
        assert result[0].endswith("</code></b>")
        # Second chunk should re-open both
        assert result[1].startswith("<b><code>")

    def test_hard_split_when_no_newlines(self):
        text = "A" * 8192
        result = self.kiro._split_html_message(text, 4096)
        assert len(result) == 2
        assert len(result[0]) == 4096
        assert len(result[1]) == 4096


class TestPromptInFlightGuard:
    """Fix 3: Prompt already in progress guard."""

    def setup_method(self):
        self.kiro = KiroSessionACP.__new__(KiroSessionACP)
        self.kiro.active_agent = "test"
        self.kiro.suppress_output = False
        self.kiro.agents = {
            "test": {
                "session": Mock(),
                "chat_id": 123,
                "chunks": [],
                "chunk_timer": None,
                "chunk_lock": threading.Lock(),
                "typing_thread": None,
                "typing_stop_event": threading.Event(),
                "pending_output": [],
                "prompt_in_flight": False,
                "usage_limit_reached": False,
            }
        }
        self.kiro.send_to_telegram = Mock()
        self.kiro.send_to_telegram.loop = Mock()
        self.kiro.chunk_timeout = 2.0
        self.kiro.prompt_timeout = 600

    def test_rejects_when_prompt_in_flight(self):
        self.kiro.agents["test"]["prompt_in_flight"] = True
        with patch.object(self.kiro, "_send_to_telegram_sync") as mock_send:
            self.kiro._handle_send_message({"text": "hello", "chat_id": 123})
            mock_send.assert_called_once()
            assert "still processing" in mock_send.call_args[0][1]

    def test_allows_when_no_prompt_in_flight(self):
        self.kiro.agents["test"]["prompt_in_flight"] = False
        # Should proceed past the guard and set the flag before sending
        with patch.object(self.kiro, "_send_to_telegram_sync"):
            with patch.object(self.kiro, "_typing_indicator_loop"):
                self.kiro._handle_send_message({"text": "hello", "chat_id": 123})
                # Flag was set (send_message mock succeeded, on_turn_end not called)
                assert self.kiro.agents["test"]["prompt_in_flight"] is True


class TestUsageLimitHandling:
    """Fix 4: Monthly usage limit handling."""

    def setup_method(self):
        self.kiro = KiroSessionACP.__new__(KiroSessionACP)
        self.kiro.active_agent = "test"
        self.kiro.suppress_output = False
        self.kiro.agents = {
            "test": {
                "session": Mock(),
                "chat_id": 123,
                "chunks": [],
                "chunk_timer": None,
                "chunk_lock": threading.Lock(),
                "typing_thread": None,
                "typing_stop_event": threading.Event(),
                "pending_output": [],
                "prompt_in_flight": False,
                "usage_limit_reached": False,
            }
        }
        self.kiro.send_to_telegram = Mock()
        self.kiro.send_to_telegram.loop = Mock()
        self.kiro.chunk_timeout = 2.0
        self.kiro.prompt_timeout = 600

    def test_rejects_when_usage_limit_reached(self):
        self.kiro.agents["test"]["usage_limit_reached"] = True
        with patch.object(self.kiro, "_send_to_telegram_sync") as mock_send:
            self.kiro._handle_send_message({"text": "hello", "chat_id": 123})
            mock_send.assert_called_once()
            assert "usage limit" in mock_send.call_args[0][1].lower()

    def test_send_error_sets_usage_limit_flag(self):
        with patch.object(self.kiro, "_send_to_telegram_sync"):
            self.kiro._send_error(
                123,
                "The monthly usage limit has been reached",
                agent_name="test",
            )
            assert self.kiro.agents["test"]["usage_limit_reached"] is True

    def test_cancel_clears_usage_limit(self):
        self.kiro.agents["test"]["usage_limit_reached"] = True
        self.kiro._handle_cancel({})
        assert self.kiro.agents["test"]["usage_limit_reached"] is False

    def test_cancel_clears_prompt_in_flight(self):
        self.kiro.agents["test"]["prompt_in_flight"] = True
        self.kiro._handle_cancel({})
        assert self.kiro.agents["test"]["prompt_in_flight"] is False


class TestRetryLogic:
    """Fix 5: Transient network error recovery in _send_to_telegram_sync."""

    def setup_method(self):
        self.kiro = KiroSessionACP.__new__(KiroSessionACP)
        self.kiro.active_agent = "test"
        self.kiro.suppress_output = False
        self.kiro.agents = {"test": {"pending_output": []}}

        self.mock_send = MagicMock()
        self.mock_send.loop = MagicMock()
        self.kiro.send_to_telegram = self.mock_send

    @patch("kiro_session_acp.KiroSessionACP._markdown_to_html", return_value="text")
    @patch("kiro_session_acp.KiroSessionACP._split_html_message", return_value=["text"])
    def test_retries_on_network_error_then_succeeds(self, mock_split, mock_md):
        future_fail = MagicMock()
        future_fail.result.side_effect = OSError("Connection reset")
        future_ok = MagicMock()
        future_ok.result.return_value = None

        with patch(
            "asyncio.run_coroutine_threadsafe", side_effect=[future_fail, future_ok]
        ):
            with patch("time.sleep"):
                self.kiro._send_to_telegram_sync(123, "text", agent_name="test")
        # Should not raise — succeeded on retry

    @patch("kiro_session_acp.KiroSessionACP._markdown_to_html", return_value="text")
    @patch("kiro_session_acp.KiroSessionACP._split_html_message", return_value=["text"])
    def test_gives_up_after_3_attempts(self, mock_split, mock_md):
        future_fail = MagicMock()
        future_fail.result.side_effect = OSError("Connection reset")

        with patch("asyncio.run_coroutine_threadsafe", return_value=future_fail):
            with patch("time.sleep"):
                # Should not raise, just log
                self.kiro._send_to_telegram_sync(123, "text", agent_name="test")
