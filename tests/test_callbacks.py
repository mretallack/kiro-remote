"""Tests for KiroSessionACP callback logic (compaction status, context alerts)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from context_tracker import ContextTracker


class TestCompactionCallback:
    """Test the compaction status callback logic."""

    def _make_callback(self, kiro, agent_name="test_agent"):
        """Build the on_compaction_status callback as done in _handle_start_session."""

        def on_compaction_status(params):
            status = params.get("status", {})
            status_type = status.get("type")

            agent_data = kiro.agents.get(agent_name, {})
            current_chat_id = agent_data.get("chat_id")

            if (
                current_chat_id
                and hasattr(kiro, "send_to_telegram")
                and kiro.send_to_telegram
            ):
                if hasattr(kiro, "event_loop") and kiro.event_loop:
                    if status_type == "started":
                        asyncio.run_coroutine_threadsafe(
                            kiro.send_to_telegram(
                                current_chat_id, "🔄 Compacting conversation..."
                            ),
                            kiro.event_loop,
                        )
                    elif status_type == "completed":
                        asyncio.run_coroutine_threadsafe(
                            kiro.send_to_telegram(
                                current_chat_id, "✅ Compaction complete"
                            ),
                            kiro.event_loop,
                        )
                    elif status_type == "failed":
                        error = status.get("error", "Unknown error")
                        asyncio.run_coroutine_threadsafe(
                            kiro.send_to_telegram(
                                current_chat_id,
                                f"❌ Compaction failed: {error}",
                            ),
                            kiro.event_loop,
                        )

        return on_compaction_status

    def _make_kiro_mock(self, chat_id=12345):
        kiro = Mock()
        kiro.agents = {"test_agent": {"chat_id": chat_id}}
        kiro.send_to_telegram = Mock(return_value=None)  # sync mock, not async
        kiro.event_loop = Mock()
        return kiro

    def test_compaction_started_sends_message(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"status": {"type": "started"}})
            mock_run.assert_called_once()
            kiro.send_to_telegram.assert_called_once_with(
                12345, "🔄 Compacting conversation..."
            )

    def test_compaction_completed_sends_message(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe"):
            cb({"status": {"type": "completed"}})
            kiro.send_to_telegram.assert_called_once_with(
                12345, "✅ Compaction complete"
            )

    def test_compaction_failed_sends_error(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe"):
            cb({"status": {"type": "failed", "error": "Out of memory"}})
            kiro.send_to_telegram.assert_called_once_with(
                12345, "❌ Compaction failed: Out of memory"
            )

    def test_compaction_failed_default_error(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe"):
            cb({"status": {"type": "failed"}})
            kiro.send_to_telegram.assert_called_once_with(
                12345, "❌ Compaction failed: Unknown error"
            )

    def test_no_chat_id_skips_send(self):
        kiro = self._make_kiro_mock()
        kiro.agents = {"test_agent": {}}  # No chat_id
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"status": {"type": "started"}})
            mock_run.assert_not_called()

    def test_no_send_to_telegram_skips_send(self):
        kiro = self._make_kiro_mock()
        kiro.send_to_telegram = None
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"status": {"type": "started"}})
            mock_run.assert_not_called()

    def test_unknown_agent_skips_send(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro, agent_name="nonexistent")

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"status": {"type": "started"}})
            mock_run.assert_not_called()

    def test_empty_status_does_nothing(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({})
            mock_run.assert_not_called()


class TestMetadataContextAlerts:
    """Test the metadata callback for context usage alerts."""

    def _make_callback(self, kiro, agent_name="test_agent"):
        """Build the on_metadata callback as done in _handle_start_session."""
        context_tracker = kiro.context_tracker

        def on_metadata(params):
            context_usage = params.get("contextUsagePercentage")
            if context_usage is not None:
                session_id = "test-session"
                context_tracker.update_usage(session_id, context_usage)

                agent_data = kiro.agents.get(agent_name, {})
                current_chat_id = agent_data.get("chat_id")

                if context_tracker.should_alert(session_id):
                    if (
                        current_chat_id
                        and hasattr(kiro, "send_to_telegram")
                        and kiro.send_to_telegram
                    ):
                        if hasattr(kiro, "event_loop") and kiro.event_loop:
                            asyncio.run_coroutine_threadsafe(
                                kiro.send_to_telegram(
                                    current_chat_id,
                                    f"🚨 Context usage: {context_usage:.1f}%. Recommend using \\compact now",
                                ),
                                kiro.event_loop,
                            )
                elif context_tracker.should_warn(session_id):
                    if (
                        current_chat_id
                        and hasattr(kiro, "send_to_telegram")
                        and kiro.send_to_telegram
                    ):
                        if hasattr(kiro, "event_loop") and kiro.event_loop:
                            asyncio.run_coroutine_threadsafe(
                                kiro.send_to_telegram(
                                    current_chat_id,
                                    f"⚠️ Context usage: {context_usage:.1f}%. Consider using \\compact",
                                ),
                                kiro.event_loop,
                            )

        return on_metadata

    def _make_kiro_mock(self, chat_id=12345):
        kiro = Mock()
        kiro.agents = {"test_agent": {"chat_id": chat_id}}
        kiro.send_to_telegram = Mock(return_value=None)  # sync mock, not async
        kiro.event_loop = Mock()
        kiro.context_tracker = ContextTracker()
        return kiro

    def test_alert_at_95_percent(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe"):
            cb({"contextUsagePercentage": 95.0})
            kiro.send_to_telegram.assert_called_once()
            msg = kiro.send_to_telegram.call_args[0][1]
            assert "🚨" in msg
            assert "95.0%" in msg

    def test_warn_at_85_percent(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe"):
            cb({"contextUsagePercentage": 85.0})
            kiro.send_to_telegram.assert_called_once()
            msg = kiro.send_to_telegram.call_args[0][1]
            assert "⚠️" in msg
            assert "85.0%" in msg

    def test_no_warning_at_70_percent(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"contextUsagePercentage": 70.0})
            mock_run.assert_not_called()

    def test_no_duplicate_warnings(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe"):
            cb({"contextUsagePercentage": 85.0})
            cb({"contextUsagePercentage": 86.0})
            # Should only warn once
            assert kiro.send_to_telegram.call_count == 1

    def test_no_chat_id_skips_alert(self):
        kiro = self._make_kiro_mock()
        kiro.agents = {"test_agent": {}}  # No chat_id
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"contextUsagePercentage": 95.0})
            mock_run.assert_not_called()

    def test_no_context_usage_in_params(self):
        kiro = self._make_kiro_mock()
        cb = self._make_callback(kiro)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            cb({"someOtherField": "value"})
            mock_run.assert_not_called()
