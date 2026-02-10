#!/usr/bin/env python3.12
"""Test model list functionality"""
import sys
from kiro_session_acp import KiroSessionACP

def test_model_list():
    print("Testing model list functionality...")
    
    session = KiroSessionACP()
    session.start_session()
    
    # Wait for session to start
    import time
    time.sleep(3)
    
    models = session.get_available_models()
    print(f"\nModels info: {models}")
    
    if models:
        print(f"\nCurrent model: {models.get('currentModelId')}")
        print(f"\nAvailable models:")
        for model in models.get('availableModels', []):
            print(f"  - {model.get('modelId')}: {model.get('description')}")
        print("\n✓ TEST PASSED")
    else:
        print("\n✗ TEST FAILED: No models returned")
        sys.exit(1)

if __name__ == "__main__":
    test_model_list()
