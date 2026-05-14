"""Tests for ACPSession notification handling."""

from unittest.mock import MagicMock, Mock

import pytest

from acp_session import ACPSession


@pytest.fixture
def session():
    """Create an ACPSession with a mocked client."""
    client = Mock()
    client.on_notification = Mock()
    s = ACPSession("test-session-123", client)
    return s


def test_metadata_callback_called(session):
    """Test that metadata notifications trigger registered callbacks."""
    received = []
    session.on_metadata(lambda params: received.append(params))

    session._handle_notification(
        {
            "method": "_kiro.dev/metadata",
            "params": {"sessionId": "test-session-123", "contextUsagePercentage": 75.0},
        }
    )

    assert len(received) == 1
    assert received[0]["contextUsagePercentage"] == 75.0


def test_compaction_status_callback_called(session):
    """Test that compaction status notifications trigger registered callbacks."""
    received = []
    session.on_compaction_status(lambda params: received.append(params))

    session._handle_notification(
        {
            "method": "_kiro.dev/compaction/status",
            "params": {"sessionId": "test-session-123", "status": {"type": "started"}},
        }
    )

    assert len(received) == 1
    assert received[0]["status"]["type"] == "started"


def test_unknown_kiro_notification_does_not_crash(session):
    """Test that unknown _kiro.dev/ notifications are handled gracefully."""
    session._handle_notification(
        {
            "method": "_kiro.dev/some/unknown/method",
            "params": {"sessionId": "test-session-123", "data": "test"},
        }
    )
    # Should not raise


def test_notification_ignored_for_different_session(session):
    """Test that notifications for other sessions are ignored."""
    received = []
    session.on_metadata(lambda params: received.append(params))

    session._handle_notification(
        {
            "method": "_kiro.dev/metadata",
            "params": {"sessionId": "other-session", "contextUsagePercentage": 99.0},
        }
    )

    assert len(received) == 0


def test_permission_request_from_subagent_approved(session):
    """Test that permission requests from subagent sessions are auto-approved."""
    session._handle_notification(
        {
            "method": "session/request_permission",
            "id": 99,
            "params": {
                "sessionId": "subagent-session-456",
                "toolCall": {"toolCallId": "tc-sub"},
                "options": [
                    {"kind": "allow_once", "optionId": "opt-sub-1"},
                ],
            },
        }
    )

    session.client.respond_to_permission.assert_called_once_with(
        99, "subagent-session-456", "tc-sub", "opt-sub-1"
    )


def test_permission_request_auto_approved(session):
    """Test that permission requests are auto-approved with allow_once."""
    session._handle_notification(
        {
            "method": "session/request_permission",
            "id": 42,
            "params": {
                "sessionId": "test-session-123",
                "toolCall": {"toolCallId": "tc-1"},
                "options": [
                    {"kind": "allow_once", "optionId": "opt-1"},
                    {"kind": "allow_always", "optionId": "opt-2"},
                ],
            },
        }
    )

    session.client.respond_to_permission.assert_called_once_with(
        42, "test-session-123", "tc-1", "opt-1"
    )


def test_permission_request_fallback_to_allow_always(session):
    """Test fallback to allow_always when allow_once not available."""
    session._handle_notification(
        {
            "method": "session/request_permission",
            "id": 43,
            "params": {
                "sessionId": "test-session-123",
                "toolCall": {"toolCallId": "tc-2"},
                "options": [
                    {"kind": "deny", "optionId": "opt-deny"},
                    {"kind": "allow_always", "optionId": "opt-always"},
                ],
            },
        }
    )

    session.client.respond_to_permission.assert_called_once_with(
        43, "test-session-123", "tc-2", "opt-always"
    )


def test_session_update_chunk(session):
    """Test that agent_message_chunk updates trigger chunk callbacks."""
    chunks = []
    session.on_chunk(lambda c: chunks.append(c))

    session._handle_notification(
        {
            "method": "session/update",
            "params": {
                "sessionId": "test-session-123",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"text": "Hello world"},
                },
            },
        }
    )

    assert chunks == ["Hello world"]


def test_session_update_tool_call(session):
    """Test that tool_call updates trigger tool call callbacks."""
    calls = []
    session.on_tool_call(lambda t: calls.append(t))

    session._handle_notification(
        {
            "method": "session/update",
            "params": {
                "sessionId": "test-session-123",
                "update": {"sessionUpdate": "tool_call", "name": "shell"},
            },
        }
    )

    assert len(calls) == 1
    assert calls[0]["name"] == "shell"


def test_commands_available_callback(session):
    """Test that commands_available notifications trigger callbacks."""
    received = []
    session.on_commands_available(lambda cmds: received.append(cmds))

    session._handle_notification(
        {
            "method": "_kiro.dev/commands/available",
            "params": {
                "sessionId": "test-session-123",
                "commands": ["/help", "/compact"],
            },
        }
    )

    assert received == [["/help", "/compact"]]


def test_accumulated_message(session):
    """Test message chunk accumulation."""
    session._handle_notification(
        {
            "method": "session/update",
            "params": {
                "sessionId": "test-session-123",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"text": "Hello "},
                },
            },
        }
    )
    session._handle_notification(
        {
            "method": "session/update",
            "params": {
                "sessionId": "test-session-123",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"text": "world"},
                },
            },
        }
    )

    assert session.get_accumulated_message() == "Hello world"
