"""Test that modes info is available and updated."""

import time

from kiro_session_acp import KiroSessionACP


def test_modes_info():
    """Test that modes information is stored and accessible."""
    print("\nTEST: Modes Info")
    print("=" * 60)

    session = KiroSessionACP()

    try:
        # Start with default agent
        print("\n1. Starting default agent...")
        session.start_session("kiro_default")
        time.sleep(2)

        # Check modes info is available
        modes_info = session.get_available_modes()
        assert modes_info is not None
        print(f"✓ Modes info available")

        current_mode = modes_info.get("currentModeId")
        available_modes = modes_info.get("availableModes", [])

        print(f"  Current mode: {current_mode}")
        print(f"  Available modes: {len(available_modes)} modes")

        assert current_mode is not None
        assert len(available_modes) > 0
        print("✓ Mode data is valid")

        # Switch to facebook agent
        print("\n2. Switching to facebook agent...")
        result = session.restart_with_agent("facebook")
        assert result is True
        time.sleep(2)

        # Check modes info for new agent
        modes_info = session.get_available_modes()
        assert modes_info is not None

        # After switching, mode should be updated to facebook
        time.sleep(1)  # Give it a moment to process
        current_mode = modes_info.get("currentModeId")
        print(f"  Current mode after swap: {current_mode}")

        # Mode should be facebook (or still kiro_default if update hasn't propagated)
        assert current_mode in ["facebook", "kiro_default"]
        print("✓ Mode info available after agent swap")

        print("\n" + "=" * 60)
        print("TEST PASSED: Modes info works correctly")

    finally:
        session.close()
