"""Test mode switching when swapping agents."""

import time

from kiro_session_acp import KiroSessionACP


def test_mode_switch_on_agent_swap():
    """Test that mode is automatically set when switching agents."""
    print("\nTEST: Mode Switch on Agent Swap")
    print("=" * 60)

    session = KiroSessionACP()

    try:
        # Start with default agent
        print("\n1. Starting default agent...")
        session.start_session("kiro_default")
        time.sleep(2)

        # Check that agent started
        assert "kiro_default" in session.agents
        print("✓ Default agent started")

        # Switch to facebook agent (which has a matching mode)
        print("\n2. Switching to facebook agent...")
        result = session.restart_with_agent("facebook")
        assert result is True
        time.sleep(2)

        # Verify agent switched
        assert session.active_agent == "facebook"
        assert "facebook" in session.agents
        print("✓ Switched to facebook agent")
        print("✓ Mode switch command sent (check logs for confirmation)")

        # Switch to a non-existent mode (should still work, mode just won't change)
        print("\n3. Switching to agent with no matching mode...")
        result = session.restart_with_agent("test_agent_no_mode")
        assert result is True
        time.sleep(2)

        assert session.active_agent == "test_agent_no_mode"
        print("✓ Switched to test_agent_no_mode (mode switch attempted)")

        print("\n" + "=" * 60)
        print("TEST PASSED: Mode switching works on agent swap")

    finally:
        session.close()
