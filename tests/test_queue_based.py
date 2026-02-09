#!/usr/bin/env python3.12
"""Test queue-based implementation."""
import asyncio
import logging
import pytest

logging.basicConfig(level=logging.INFO, format='%(message)s')

from kiro_session_acp import KiroSessionACP

@pytest.mark.asyncio
async def test_queue_based():
    """Test the queue-based implementation."""
    print("="*60)
    print("TESTING QUEUE-BASED IMPLEMENTATION")
    print("="*60)
    
    messages_received = []
    
    # Create async callback for sending to Telegram
    async def send_to_telegram(chat_id, text):
        messages_received.append(text)
        print(f"\n📱 TELEGRAM: {text[:100]}")
    
    # Store the event loop on the callback
    send_to_telegram.loop = asyncio.get_running_loop()
    
    # Create session manager
    print("\n1. Creating KiroSessionACP...")
    kiro = KiroSessionACP()
    kiro.send_to_telegram = send_to_telegram
    kiro.current_chat_id = 12345
    
    # Start session
    print("2. Starting session...")
    kiro.start_session()
    
    # Wait for session to start
    await asyncio.sleep(2)
    
    # Send message
    print("\n3. Sending message: 'what is 2+2?'")
    kiro.send_message("what is 2+2?", 12345)
    
    # Wait for response
    print("4. Waiting for response...")
    for i in range(10):
        await asyncio.sleep(1)
        if messages_received:
            break
    
    # Check results
    print(f"\n5. Results:")
    print(f"   Messages received: {len(messages_received)}")
    for i, msg in enumerate(messages_received, 1):
        print(f"   {i}. {msg[:100]}")
    
    # Cleanup
    print("\n6. Cleanup...")
    kiro.close()
    
    if len(messages_received) > 0:
        print("\n✅ SUCCESS!")
        return True
    else:
        print("\n❌ FAILURE: No messages received")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_queue_based())
    exit(0 if success else 1)
