#!/usr/bin/env python3.12
"""
Test to see what ACP sends when a tool executes.
"""

import logging
import time

from acp_client import ACPClient
from acp_session import ACPSession

logging.basicConfig(level=logging.INFO, format="%(message)s")


def test_tool_output():
    print("=" * 80)
    print("TEST: What does ACP send when a tool executes?")
    print("=" * 80)

    client = ACPClient("/home/mark/git/remote-kiro")
    client.start()
    client.initialize()

    session_id = client.create_session("/home/mark/git/remote-kiro")
    print(f"\nSession ID: {session_id}")

    session = ACPSession(session_id, client)

    all_chunks = []
    all_updates = []

    def on_chunk(content):
        print(f"📝 CHUNK: {repr(content)}")
        all_chunks.append(content)

    def on_tool_call(tool):
        print(f"🔧 TOOL CALL: {tool}")
        all_updates.append(("tool_call", tool))

    def on_turn_end():
        print(f"✅ TURN END")
        full_message = "".join(all_chunks)
        print(f"\n{'=' * 80}")
        print(f"FULL MESSAGE ({len(full_message)} chars):")
        print(f"{'=' * 80}")
        print(full_message)
        print(f"{'=' * 80}")

    session.on_chunk(on_chunk)
    session.on_tool_call(on_tool_call)
    session.on_turn_end(on_turn_end)

    # Send a command that will execute a tool
    print("\n📤 Sending: 'for i in {1..5}; do echo hello $i; sleep 1; done'")

    import threading

    result = {"done": False}

    def send():
        try:
            session.send_message("for i in {1..5}; do echo hello $i; sleep 1; done")
            result["done"] = True
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()

    thread = threading.Thread(target=send, daemon=True)
    thread.start()
    thread.join(timeout=30)

    if not result["done"]:
        print("⏱️  Timeout waiting for response")

    client.close()

    print(f"\n{'=' * 80}")
    print(f"SUMMARY:")
    print(f"  Total chunks: {len(all_chunks)}")
    print(f"  Total updates: {len(all_updates)}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    test_tool_output()
