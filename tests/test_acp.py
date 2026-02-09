#!/usr/bin/env python3.12
"""Basic ACP tests."""
import pytest
from acp_client import ACPClient
from acp_session import ACPSession
from kiro_session_acp import KiroSessionACP

class TestACPBasic:
    """Basic ACP functionality tests."""
    
    def test_initialize(self):
        """Test ACP initialization."""
        client = ACPClient('/home/mark/git/remote-kiro')
        client.start()
        result = client.initialize()
        client.close()
        
        assert 'agentInfo' in result
        assert result['agentInfo']['name'] == 'Kiro Agent'
    
    def test_session_creation(self):
        """Test session creation."""
        client = ACPClient('/home/mark/git/remote-kiro')
        client.start()
        client.initialize()
        session_id = client.create_session('/home/mark/git/remote-kiro')
        client.close()
        
        assert session_id
        assert len(session_id) > 0
    
    def test_message_flow(self):
        """Test complete message flow."""
        client = ACPClient('/home/mark/git/remote-kiro')
        client.start()
        client.initialize()
        session_id = client.create_session('/home/mark/git/remote-kiro')
        session = ACPSession(session_id, client)
        
        chunks = []
        turn_ended = False
        
        def on_chunk(content):
            chunks.append(content)
        
        def on_turn_end():
            nonlocal turn_ended
            turn_ended = True
        
        session.on_chunk(on_chunk)
        session.on_turn_end(on_turn_end)
        session.send_message("what is 2+2?")
        client.close()
        
        assert turn_ended
        assert len(chunks) > 0
        assert '4' in ''.join(chunks)

class TestKiroSessionACP:
    """KiroSessionACP manager tests."""
    
    # Removed test_manager_creation - it tests internal implementation details
    # The queue-based architecture is tested by test_pwd_flow.py
