#!/usr/bin/env python3.12
"""
Test long-running command to verify Kiro sends output after completion.
"""

import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from acp_client import ACPClient
from acp_session import ACPSession

def test_long_running_command():
    print("=" * 80)
    print("TEST: Long-running command (for loop with sleep)")
    print("=" * 80)
    
    # Start client
    client = ACPClient("/home/mark/git/remote-kiro")
    client.start()
    
    # Initialize
    print("\n1. INITIALIZING...")
    result = client.initialize()
    print(f"   Initialized: {result['agentInfo']['name']}")
    
    # Create session
    print("\n2. CREATING SESSION...")
    session_id = client.create_session("/home/mark/git/remote-kiro")
    print(f"   Session ID: {session_id}")
    
    # Create session wrapper
    session = ACPSession(session_id, client)
    
    # Track what we receive
    chunks_received = []
    tools_called = []
    tool_updates_received = []
    tool_start_time = None
    tool_end_time = None
    
    def on_chunk(content):
        nonlocal tool_end_time
        if tool_start_time and not tool_end_time:
            tool_end_time = time.time()
            elapsed = tool_end_time - tool_start_time
            print(f"   📝 FIRST CHUNK after {elapsed:.1f}s: {repr(content[:50])}")
        chunks_received.append(content)
    
    def on_tool_call(tool):
        nonlocal tool_start_time
        tool_name = tool.get('title', 'unknown')
        tool_start_time = time.time()
        print(f"   🔧 TOOL CALL: {tool_name}")
        tools_called.append(tool)
    
    def on_tool_update(update):
        print(f"   🔄 TOOL UPDATE: status={update.get('status')}")
        tool_updates_received.append(update)
        
        # Check for stdout
        if update.get('status') == 'completed':
            raw_output = update.get('rawOutput', {})
            items = raw_output.get('items', [])
            if items:
                output_data = items[0].get('Json', {})
                stdout = output_data.get('stdout', '').strip()
                if stdout:
                    print(f"   📤 STDOUT RECEIVED ({len(stdout)} bytes):")
                    print(f"      {stdout[:100]}")
    
    def on_turn_end():
        elapsed = time.time() - tool_start_time if tool_start_time else 0
        print(f"   ✅ TURN END after {elapsed:.1f}s - {len(chunks_received)} chunks received")
        full_message = "".join(chunks_received)
        print(f"   📨 FULL MESSAGE ({len(full_message)} chars):")
        print(f"      {full_message[:200]}")
    
    # Register callbacks
    session.on_chunk(on_chunk)
    session.on_tool_call(on_tool_call)
    session.on_tool_update(on_tool_update)
    session.on_turn_end(on_turn_end)
    
    # Send prompt - ask for 5 iterations (5 seconds total)
    print("\n3. SENDING PROMPT: 'for i in {1..5}; do echo hello $i; sleep 1; done'")
    print("   Expected: Tool executes for ~5 seconds, then Kiro sends response")
    
    import threading
    result_container = {"completed": False, "error": None}
    
    def send_with_timeout():
        try:
            session.send_message("for i in {1..5}; do echo hello $i; sleep 1; done")
            result_container["completed"] = True
            print("\n4. SEND_MESSAGE RETURNED SUCCESSFULLY")
        except Exception as e:
            result_container["error"] = str(e)
            print(f"\n4. ERROR: {e}")
    
    thread = threading.Thread(target=send_with_timeout, daemon=True)
    thread.start()
    thread.join(timeout=15)  # 5s for command + 10s buffer
    
    if not result_container["completed"]:
        print("\n4. TIMEOUT - send_message did not return within 15 seconds")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Tools called: {len(tools_called)}")
    print(f"Tool updates received: {len(tool_updates_received)}")
    print(f"Chunks received: {len(chunks_received)}")
    if tool_start_time and tool_end_time:
        print(f"Time until first chunk: {tool_end_time - tool_start_time:.1f}s")
        print(f"Expected: ~5s (command duration)")
    
    full_message = "".join(chunks_received)
    print(f"\nFull response ({len(full_message)} chars):")
    print(full_message)
    
    # Cleanup
    client.close()
    
    # Assertions
    assert len(chunks_received) > 0, "Should have received chunks"
    assert len(tools_called) > 0, "Should have called tools"
    if tool_start_time and tool_end_time:
        elapsed = tool_end_time - tool_start_time
        assert elapsed >= 4.5, f"First chunk should arrive after ~5s, got {elapsed:.1f}s"
        print(f"\n✅ VERIFIED: Kiro waits for command completion before sending response")

if __name__ == "__main__":
    test_long_running_command()
