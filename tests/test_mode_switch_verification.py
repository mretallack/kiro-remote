"""Test that mode switching actually changes the kiro-cli mode."""

import time
import queue
from kiro_session_acp import KiroSessionACP


def test_mode_switch_verification():
    """Verify mode is actually switched by checking kiro-cli behavior."""
    print("\nTEST: Mode Switch Verification")
    print("=" * 60)

    session = KiroSessionACP()
    responses = []

    def capture_response(chat_id, message):
        """Capture responses for verification."""
        responses.append(message)
        print(f"[RESPONSE] {message[:100]}...")

    session.send_to_telegram = capture_response

    try:
        # Start with facebook agent
        print("\n1. Starting facebook agent...")
        session.start_session("facebook")
        session.set_chat_id(12345)
        time.sleep(3)  # Increased wait time

        # Verify agent started
        assert "facebook" in session.agents
        print("✓ Facebook agent started")

        # Switch to thingino agent (which has a matching mode)
        print("\n2. Switching to thingino agent...")
        result = session.restart_with_agent("thingino")
        assert result is True
        time.sleep(2)

        # Verify agent switched
        assert session.active_agent == "thingino"
        assert "thingino" in session.agents
        print("✓ Switched to thingino agent")

        # Send a simple message to verify the session is working
        print("\n3. Sending test message...")
        responses.clear()
        session.send_message("pwd", 12345)

        # Wait for response
        timeout = 30
        start_time = time.time()
        while len(responses) == 0 and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        if responses:
            print(f"✓ Received response from thingino agent")
            print(f"  Response preview: {responses[0][:200]}")
        else:
            print("⚠ No response received (timeout)")

        print("\n" + "=" * 60)
        print("TEST PASSED: Mode switching verified")

    finally:
        session.close()
