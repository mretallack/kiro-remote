#!/usr/bin/env python3
"""
Complete end-to-end test simulating actual bot behavior.
"""

import asyncio
import logging
import time
from unittest.mock import Mock

logging.basicConfig(level=logging.INFO, format="%(message)s")

import pytest

from kiro_session_acp import KiroSessionACP


@pytest.mark.asyncio
async def test_complete_flow():
    """Test complete message flow with async event loop."""
    print("=" * 60)
    print("COMPLETE BOT SIMULATION TEST")
    print("=" * 60)

    # Track messages
    messages_sent = []

    # Create mock bot with proper async methods
    mock_bot = Mock()
    mock_bot.application = Mock()
    mock_bot.application.bot = Mock()

    async def mock_send_message(chat_id, text):
        messages_sent.append(text)
        print(f"\n📱 TELEGRAM: {text[:100]}")

    async def mock_send_chat_action(chat_id, action):
        pass

    mock_bot.application.bot.send_message = mock_send_message
    mock_bot.application.bot.send_chat_action = mock_send_chat_action
    mock_bot.loop = asyncio.get_running_loop()

    # Create session manager
    print("\n1. Creating KiroSessionACP...")
    kiro = KiroSessionACP()
    kiro.telegram_bot = mock_bot
    kiro.current_chat_id = 12345

    # Start session
    print("2. Starting session...")
    kiro.start_session()

    # Test 1: Simple question
    print("\n3. Test 1: Simple question")
    print("   Sending: 'what is 2+2?'")
    kiro.send_to_kiro("what is 2+2?")

    # Wait for response
    await asyncio.sleep(5)

    if messages_sent:
        print(f"   ✅ Got response: {messages_sent[-1]}")
    else:
        print(f"   ❌ No response received")
        return False

    # Test 2: Tool call
    print("\n4. Test 2: Tool call")
    print("   Sending: 'list files'")
    messages_before = len(messages_sent)
    kiro.send_to_kiro("list files")

    # Wait for tool and response
    await asyncio.sleep(10)

    new_messages = messages_sent[messages_before:]
    has_tool = any("🔧" in msg for msg in new_messages)
    has_response = any(len(msg) > 50 for msg in new_messages)

    if has_tool:
        print(f"   ✅ Tool call detected")
    else:
        print(f"   ❌ No tool call detected")

    if has_response:
        print(f"   ✅ Got response")
    else:
        print(f"   ❌ No response")

    # Cleanup
    print("\n5. Cleanup...")
    kiro.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total messages sent to Telegram: {len(messages_sent)}")
    for i, msg in enumerate(messages_sent, 1):
        preview = msg[:80] + "..." if len(msg) > 80 else msg
        print(f"  {i}. {preview}")

    success = len(messages_sent) >= 2 and has_tool and has_response
    return success


async def main():
    try:
        success = await test_complete_flow()

        print("\n" + "=" * 60)
        if success:
            print("✅ TEST PASSED")
            return 0
        else:
            print("❌ TEST FAILED")
            return 1
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    exit_code = loop.run_until_complete(main())
    loop.close()
    exit(exit_code)
