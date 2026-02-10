#!/usr/bin/env python3.12
"""Test model set functionality via Telegram bot command"""
import sys
import time
import asyncio
import threading
from kiro_session_acp import KiroSessionACP

def test_model_set():
    print("Testing model set functionality...")
    
    session = KiroSessionACP()
    
    # Track messages sent to telegram
    messages_sent = []
    
    # Create event loop in separate thread for async callback
    loop = asyncio.new_event_loop()
    
    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    
    async def mock_send_to_telegram(chat_id, text):
        print(f"[TELEGRAM] {text}")
        messages_sent.append(text)
    
    session.send_to_telegram = mock_send_to_telegram
    session.send_to_telegram.loop = loop
    
    session.start_session()
    
    # Wait for session to start
    time.sleep(3)
    
    # Get available models first
    models = session.get_available_models()
    if not models or not models.get('availableModels'):
        print("\n✗ TEST FAILED: No models available")
        loop.call_soon_threadsafe(loop.stop)
        sys.exit(1)
    
    current_model = models.get('currentModelId')
    available_models = models.get('availableModels', [])
    
    print(f"\nCurrent model: {current_model}")
    print(f"Available models: {[m['modelId'] for m in available_models]}")
    
    # Find a different model to switch to
    target_model = None
    for model in available_models:
        if model['modelId'] != current_model:
            target_model = model['modelId']
            break
    
    if not target_model:
        print("\n✗ TEST FAILED: Need at least 2 models to test switching")
        loop.call_soon_threadsafe(loop.stop)
        sys.exit(1)
    
    print(f"\nSwitching to model: {target_model}")
    
    # Test the set_model functionality via the queue-based API
    try:
        chat_id = 12345
        session.set_model(target_model, chat_id)
        
        # Wait for worker thread to process
        time.sleep(2)
        
        # Check that success message was sent
        if not messages_sent:
            print("\n✗ TEST FAILED: No messages sent to Telegram")
            loop.call_soon_threadsafe(loop.stop)
            sys.exit(1)
        
        success_msg = messages_sent[-1]
        if "✓" in success_msg and target_model in success_msg:
            print(f"\n✓ Success message sent: {success_msg}")
            print("\n✓ TEST PASSED")
        else:
            print(f"\n✗ TEST FAILED: Unexpected message: {success_msg}")
            loop.call_soon_threadsafe(loop.stop)
            sys.exit(1)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        loop.call_soon_threadsafe(loop.stop)
        sys.exit(1)
    finally:
        session.close()
        loop.call_soon_threadsafe(loop.stop)
        time.sleep(0.5)

if __name__ == "__main__":
    test_model_set()
