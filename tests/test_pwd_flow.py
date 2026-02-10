#!/usr/bin/env python3.12
"""
Test the exact flow of asking for pwd and handling permission requests.
"""

import json
import logging
import sys
import time

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)

print("Starting test...", flush=True)

from acp_client import ACPClient
from acp_session import ACPSession

print("Imports successful", flush=True)


def test_pwd_flow():
    print("=" * 80)
    print("TEST: Ask Kiro 'what is the pwd'")
    print("=" * 80)

    # Start client
    client = ACPClient("/home/mark/git/remote-kiro")
    client.start()

    # Initialize
    print("\n1. INITIALIZING...")
    result = client.initialize()
    print(f"   Initialized: {result['agentInfo']}")

    # Create session
    print("\n2. CREATING SESSION...")
    session_id = client.create_session("/home/mark/git/remote-kiro")
    print(f"   Session ID: {session_id}")

    # Create session wrapper
    session = ACPSession(session_id, client)

    # Track what we receive
    messages_received = []
    chunks_received = []
    tools_called = []
    permission_requests = []

    def on_chunk(content):
        print(f"   📝 CHUNK: {repr(content[:50])}")
        chunks_received.append(content)

    def on_tool_call(tool):
        tool_name = tool.get("title", "unknown")
        print(f"   🔧 TOOL CALL: {tool_name}")
        tools_called.append(tool)

    def on_turn_end():
        print(f"   ✅ TURN END - {len(chunks_received)} chunks received")
        full_message = "".join(chunks_received)
        print(f"   📨 FULL MESSAGE: {full_message}")

    # Register callbacks
    session.on_chunk(on_chunk)
    session.on_tool_call(on_tool_call)
    session.on_turn_end(on_turn_end)

    # Intercept permission requests
    original_handler = session._handle_notification

    def intercept_notification(message):
        method = message.get("method")
        if method == "session/request_permission":
            print(f"\n   ⚠️  PERMISSION REQUEST RECEIVED:")
            print(f"       Request ID: {message.get('id')}")
            print(
                f"       Tool: {message.get('params', {}).get('toolCall', {}).get('title')}"
            )
            print(
                f"       Options: {[opt.get('name') for opt in message.get('params', {}).get('options', [])]}"
            )
            permission_requests.append(message)
        original_handler(message)

    session._handle_notification = intercept_notification

    # Send prompt
    print("\n3. SENDING PROMPT: 'what is the pwd'")
    print("   Waiting for response (10 second timeout)...")

    import threading

    result_container = {"completed": False, "error": None}

    def send_with_timeout():
        try:
            session.send_message("what is the pwd")
            result_container["completed"] = True
            print("\n4. SEND_MESSAGE RETURNED SUCCESSFULLY")
        except Exception as e:
            result_container["error"] = str(e)
            print(f"\n4. ERROR: {e}")

    thread = threading.Thread(target=send_with_timeout, daemon=True)
    thread.start()
    thread.join(timeout=10)

    if not result_container["completed"] and not result_container["error"]:
        print("\n4. TIMEOUT - send_message did not return within 10 seconds")
        print("   This means the permission request is blocking")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Tools called: {len(tools_called)}")
    for tool in tools_called:
        print(f"  - {tool.get('title')}")
    print(f"Permission requests: {len(permission_requests)}")
    for req in permission_requests:
        print(f"  - Request ID: {req.get('id')}")
        print(f"    Tool: {req.get('params', {}).get('toolCall', {}).get('title')}")
    print(f"Chunks received: {len(chunks_received)}")
    print(f"Full message: {''.join(chunks_received)}")

    # Cleanup
    client.close()

    # Assert for pytest
    assert len(chunks_received) > 0, "Should have received chunks"
    assert len(tools_called) > 0, "Should have called tools"


if __name__ == "__main__":
    success = test_pwd_flow()
    # Don't return, just exit with code
    import sys

    sys.exit(0 if success else 1)
