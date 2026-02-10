#!/usr/bin/env python3.12
"""
Test sending usage command to Kiro and checking response - with debug output.
"""

import sys
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from acp_client import ACPClient
from acp_session import ACPSession

def test_usage_flow():
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
    
    print("\n3. SENDING MESSAGE: /usage")
    print("   This will be sent as JSON-RPC session/prompt with:")
    print(json.dumps([{"type": "text", "text": "/usage"}], indent=2))
    
    session.send_message("/usage")
    
    full_message = "".join(chunks_received)
    print("\n4. FULL RESPONSE RECEIVED:")
    print("-" * 80)
    print(full_message)
    print("-" * 80)
    
    print("\n5. CHECKING RESPONSE CONTENT:")
    print(f"   Contains 'credit': {'credit' in full_message.lower()}")
    print(f"   Contains 'billing': {'billing' in full_message.lower()}")
    print(f"   Contains 'usage': {'usage' in full_message.lower()}")
    print(f"   Contains 'make': {'make' in full_message.lower()}")
    print(f"   Contains 'telegram': {'telegram' in full_message.lower()}")
    
    client.close()
    
    print("\nTEST COMPLETE")

if __name__ == "__main__":
    test_usage_flow()
    sys.exit(0)
