#!/usr/bin/env python3
"""
Test script to verify typing indicator behavior.

This script monitors the bot logs to verify that:
1. Typing indicator thread starts when message is received
2. Typing indicator continues during processing
3. Typing indicator stops when response completes
"""

import subprocess
import sys
import time
from datetime import datetime


def monitor_logs(duration=30):
    """Monitor bot logs for typing indicator activity."""
    print(f"Monitoring logs for {duration} seconds...")
    print("=" * 60)
    print("Send a message to the bot now that takes >10 seconds to process")
    print("Example: 'Count from 1 to 20 slowly with 1 second between each'")
    print("=" * 60)
    print()

    # Start log monitoring
    cmd = [
        "sudo",
        "journalctl",
        "-u",
        "telegram-kiro-bot.service",
        "-f",
        "--since",
        "now",
    ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )

    typing_started = False
    typing_stopped = False
    typing_count = 0
    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            line = process.stdout.readline()
            if not line:
                break

            timestamp = datetime.now().strftime("%H:%M:%S")

            # Check for typing indicator events
            if "Typing indicator thread started" in line:
                typing_started = True
                print(f"[{timestamp}] ✅ TYPING STARTED")

            elif "send_chat_action" in line and "TYPING" in line:
                typing_count += 1
                print(f"[{timestamp}] 🔄 Typing indicator refresh #{typing_count}")

            elif "Typing indicator thread stopped" in line:
                typing_stopped = True
                print(f"[{timestamp}] ⏹️  TYPING STOPPED")

            elif "Worker: Sending message:" in line:
                print(f"[{timestamp}] 📨 Message received by bot")

            elif "Worker: Turn end complete" in line:
                print(f"[{timestamp}] ✅ Response complete")

            elif "Typing indicator error:" in line:
                print(f"[{timestamp}] ❌ ERROR: {line.strip()}")

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")

    finally:
        process.terminate()
        process.wait()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Typing started: {'✅ YES' if typing_started else '❌ NO'}")
    print(f"Typing refreshes: {typing_count}")
    print(f"Typing stopped: {'✅ YES' if typing_stopped else '❌ NO'}")
    print()

    if typing_started and typing_count > 0 and typing_stopped:
        print("✅ TEST PASSED: Typing indicator working correctly!")
        return 0
    else:
        print("❌ TEST FAILED: Issues detected")
        if not typing_started:
            print("  - Typing indicator never started")
        if typing_count == 0:
            print("  - No typing indicator refreshes detected")
        if not typing_stopped:
            print("  - Typing indicator never stopped")
        return 1


if __name__ == "__main__":
    print("Telegram Bot Typing Indicator Test")
    print("=" * 60)
    print()

    # Check if bot is running
    result = subprocess.run(
        ["sudo", "systemctl", "is-active", "telegram-kiro-bot"],
        capture_output=True,
        text=True,
    )

    if result.stdout.strip() != "active":
        print("❌ Bot service is not running!")
        print("Start it with: sudo systemctl start telegram-kiro-bot")
        sys.exit(1)

    print("✅ Bot service is running")
    print()

    # Run monitoring
    exit_code = monitor_logs(duration=60)
    sys.exit(exit_code)
