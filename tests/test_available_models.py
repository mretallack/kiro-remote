#!/usr/bin/env python3.12
"""
Test that session/new returns availableModels information.
"""

import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

from acp_client import ACPClient


def test_available_models():
    print("=" * 80)
    print("TEST: Check availableModels in session/new response")
    print("=" * 80)

    client = ACPClient("/home/mark/git/remote-kiro")
    client.start()

    print("\n1. INITIALIZING...")
    result = client.initialize()
    print("   Initialized:", result.get("agentInfo"))

    print("\n2. CREATING SESSION...")
    # We need to capture the full response, not just the session_id
    # Let's call _send_request directly to get the full result
    params = {"cwd": "/home/mark/git/remote-kiro", "mcpServers": []}

    result = client._send_request("session/new", params)

    print("\n3. FULL SESSION/NEW RESPONSE:")
    print(json.dumps(result, indent=2))

    print("\n4. CHECKING FOR MODELS:")
    assert "sessionId" in result, "Response should contain sessionId"
    print(f"   ✓ sessionId: {result['sessionId']}")

    if "models" in result:
        print(f"   ✓ models field present")
        models = result["models"]

        if "currentModelId" in models:
            print(f"   ✓ currentModelId: {models['currentModelId']}")

        if "availableModels" in models:
            print(
                f"   ✓ availableModels present with {len(models['availableModels'])} models:"
            )
            for model in models["availableModels"]:
                print(f"      - {model.get('modelId')}: {model.get('name')}")
        else:
            print("   ✗ availableModels NOT found in models")
    else:
        print("   ✗ models field NOT found in response")

    client.close()

    # Assertions
    assert "models" in result, "Response should contain models field"
    assert (
        "availableModels" in result["models"]
    ), "models should contain availableModels"
    assert (
        len(result["models"]["availableModels"]) > 0
    ), "availableModels should not be empty"

    print("\nTEST PASSED")


if __name__ == "__main__":
    test_available_models()
    sys.exit(0)
