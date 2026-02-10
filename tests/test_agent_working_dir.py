#!/usr/bin/env python3.12
"""
Test agent switching with working directory configuration.
"""

import json
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

from acp_client import ACPClient
from acp_session import ACPSession


def load_agent_config():
    """Load agent configuration."""
    config_path = os.path.expanduser("~/.kiro/bot_agent_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {"agents": {}, "default_directory": "/home/mark/git/remote-kiro"}


def test_agent_working_directory():
    """Test that agents start in their configured working directory."""
    print("=" * 80)
    print("TEST: Agent Working Directory")
    print("=" * 80)

    config = load_agent_config()

    # Test AndroidRTSP agent
    agent_name = "AndroidRTSP"
    expected_dir = config["agents"].get(agent_name, {}).get("working_directory")

    if not expected_dir:
        print(f"⚠️  Agent {agent_name} not found in config, skipping test")
        return

    print(f"\n1. Testing agent: {agent_name}")
    print(f"   Expected working directory: {expected_dir}")

    # Start client with the configured directory
    client = ACPClient(expected_dir)
    client.start()
    client.initialize()

    # Create session
    session_id = client.create_session(expected_dir)
    print(f"   Session ID: {session_id}")

    session = ACPSession(session_id, client)

    # Track response
    chunks_received = []

    def on_chunk(content):
        chunks_received.append(content)

    def on_tool_call(tool):
        print(f"   🔧 Tool: {tool.get('title')}")

    def on_turn_end():
        full_message = "".join(chunks_received)
        print(f"   📨 Response: {full_message}")

    session.on_chunk(on_chunk)
    session.on_tool_call(on_tool_call)
    session.on_turn_end(on_turn_end)

    # Ask for pwd
    print("\n2. Asking 'what is the pwd'")

    import threading

    result_container = {"completed": False}

    def send_with_timeout():
        try:
            session.send_message("what is the pwd")
            result_container["completed"] = True
        except Exception as e:
            print(f"   ❌ Error: {e}")

    thread = threading.Thread(target=send_with_timeout, daemon=True)
    thread.start()
    thread.join(timeout=15)

    if not result_container["completed"]:
        print("   ⏱️  Timeout")
        client.close()
        assert False, "Request timed out"

    # Check the response
    full_response = "".join(chunks_received)

    print("\n3. Verification:")
    print(f"   Expected directory in response: {expected_dir}")
    print(f"   Actual response: {full_response}")

    # Cleanup
    client.close()

    # Assert
    assert (
        expected_dir in full_response
    ), f"Expected {expected_dir} in response, got: {full_response}"
    print(f"\n✅ SUCCESS: Agent started in correct directory")


if __name__ == "__main__":
    test_agent_working_directory()
