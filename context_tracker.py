"""Context usage tracker for monitoring Kiro CLI context window usage."""

from typing import Optional


class ContextTracker:
    """Track context usage per session and provide threshold alerts."""

    def __init__(self):
        self.usage_by_session = {}  # session_id -> percentage
        self.warned_at_80 = set()  # sessions that have been warned at 80%
        self.warned_at_90 = set()  # sessions that have been warned at 90%

    def update_usage(self, session_id: str, percentage: float) -> None:
        """Update context usage for a session."""
        self.usage_by_session[session_id] = percentage

    def get_usage(self, session_id: str) -> Optional[float]:
        """Get current context usage for a session."""
        return self.usage_by_session.get(session_id)

    def should_warn(self, session_id: str) -> bool:
        """Check if usage exceeds 80% and hasn't been warned yet."""
        usage = self.get_usage(session_id)
        if usage is not None and usage > 80.0 and session_id not in self.warned_at_80:
            self.warned_at_80.add(session_id)
            return True
        return False

    def should_alert(self, session_id: str) -> bool:
        """Check if usage exceeds 90% and hasn't been alerted yet."""
        usage = self.get_usage(session_id)
        if usage is not None and usage > 90.0 and session_id not in self.warned_at_90:
            self.warned_at_90.add(session_id)
            return True
        return False

    def reset_warnings(self, session_id: str) -> None:
        """Reset warning state after compaction."""
        self.warned_at_80.discard(session_id)
        self.warned_at_90.discard(session_id)

    def clear_session(self, session_id: str) -> None:
        """Clear all data for a session."""
        self.usage_by_session.pop(session_id, None)
        self.warned_at_80.discard(session_id)
        self.warned_at_90.discard(session_id)
