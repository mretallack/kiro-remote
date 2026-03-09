"""Tests for context_tracker module."""

import pytest

from context_tracker import ContextTracker


def test_update_and_get_usage():
    tracker = ContextTracker()
    tracker.update_usage("session1", 50.0)
    assert tracker.get_usage("session1") == 50.0
    assert tracker.get_usage("session2") is None


def test_should_warn_at_80_percent():
    tracker = ContextTracker()
    tracker.update_usage("session1", 85.0)
    assert tracker.should_warn("session1") is True
    # Should not warn again
    assert tracker.should_warn("session1") is False


def test_should_not_warn_below_80_percent():
    tracker = ContextTracker()
    tracker.update_usage("session1", 75.0)
    assert tracker.should_warn("session1") is False


def test_should_alert_at_90_percent():
    tracker = ContextTracker()
    tracker.update_usage("session1", 95.0)
    assert tracker.should_alert("session1") is True
    # Should not alert again
    assert tracker.should_alert("session1") is False


def test_should_not_alert_below_90_percent():
    tracker = ContextTracker()
    tracker.update_usage("session1", 85.0)
    assert tracker.should_alert("session1") is False


def test_reset_warnings():
    tracker = ContextTracker()
    tracker.update_usage("session1", 95.0)
    tracker.should_warn("session1")
    tracker.should_alert("session1")

    tracker.reset_warnings("session1")

    # Should warn/alert again after reset
    assert tracker.should_warn("session1") is True
    assert tracker.should_alert("session1") is True


def test_clear_session():
    tracker = ContextTracker()
    tracker.update_usage("session1", 95.0)
    tracker.should_warn("session1")

    tracker.clear_session("session1")

    assert tracker.get_usage("session1") is None
    # Should warn again if usage goes back up
    tracker.update_usage("session1", 95.0)
    assert tracker.should_warn("session1") is True
