#!/usr/bin/env python3.12
"""
Test agent switching via restart_with_agent (simulates bot behavior).
"""

import sys
import time
import logging

logging.basicConfig(level=logging.WARNING)  # Reduce noise

from kiro_session_acp import KiroSessionACP

def test_agent_swap():
    """Test agent swap like the bot does."""
    print("=" * 80)
    print("TEST: Agent Swap (Bot Simulation)")
    print("=" * 80)
    
    # Create session manager
    kiro = KiroSessionACP()
    
    # Start with default agent
    print("\n1. Starting with kiro_default")
    kiro.start_session('kiro_default')
    time.sleep(1.5)
    
    print(f"   Active agent: {kiro.active_agent}")
    
    # Swap to AndroidRTSP (like bot does)
    print("\n2. Swapping to AndroidRTSP")
    result = kiro.restart_with_agent('AndroidRTSP')
    print(f"   Swap result: {result}")
    time.sleep(1.5)
    
    print(f"   Active agent: {kiro.active_agent}")
    
    # Check working directory
    print("\n3. Checking working directory")
    
    if 'AndroidRTSP' in kiro.agents:
        agent_info = kiro.agents['AndroidRTSP']
        working_dir = agent_info.get('working_dir')
        print(f"   AndroidRTSP working_dir: {working_dir}")
        
        expected_dir = "/home/mark/git/cams"
        if working_dir == expected_dir:
            print(f"   ✅ Correct working directory!")
        else:
            print(f"   ❌ Wrong directory! Expected {expected_dir}, got {working_dir}")
            kiro.close()
            assert False, f"Expected {expected_dir}, got {working_dir}"
    else:
        print(f"   ❌ AndroidRTSP agent not found in: {list(kiro.agents.keys())}")
        kiro.close()
        assert False, "AndroidRTSP agent not created"
    
    kiro.close()
    print("\n✅ TEST PASSED")

if __name__ == "__main__":
    test_agent_swap()
