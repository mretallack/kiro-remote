#!/usr/bin/env python3.12
"""
Test sending usage command to Kiro and checking response.

DISABLED: The /usage command does not appear to be supported in ACP mode.
It works in regular CLI mode but returns "I don't have a /usage command available"
when sent via ACP session/prompt.
"""

import sys
import logging

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

from acp_client import ACPClient
from acp_session import ACPSession

def test_usage_flow_DISABLED():
    print("=" * 80)
    print("TEST: Send backslash usage to Kiro")
    print("=" * 80)
    
    client = ACPClient("/home/mark/git/remote-kiro")
    client.start()
    
    print("\n1. INITIALIZING...")
    result = client.initialize()
    print("   Initialized:", result.get("agentInfo"))
    
    print("\n2. CREATING SESSION...")
    session_id = client.create_session("/home/mark/git/remote-kiro")
    print("   Session ID:", session_id)
    
    session = ACPSession(session_id, client)
    
    chunks_received = []
    
    def on_chunk(content):
        chunks_received.append(content)
    
    session.on_chunk(on_chunk)
    
    print("\n3. SENDING: /usage")
    session.send_message("/usage")
    
    full_message = "".join(chunks_received)
    print("\n4. RESPONSE:\n" + full_message)
    
    client.close()
    
    assert len(chunks_received) > 0, "Should have received response"
    assert "credit" in full_message.lower() or "billing" in full_message.lower() or "usage" in full_message.lower(), "Response should contain billing/credits information"
    
    print("\nTEST PASSED")

if __name__ == "__main__":
    print("Test disabled - /usage command not supported in ACP mode")
    sys.exit(0)
