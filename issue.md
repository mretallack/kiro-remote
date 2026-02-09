# Issue: Kiro Response Not Sent to Telegram

## Problem Description

When Kiro executes commands and generates responses, **the response text never appears in Telegram**. The tool execution notifications appear (e.g., "🔧 Execute Bash..."), but Kiro's actual response message is never sent.

## Expected Behavior

After Kiro executes a command, the user should see Kiro's response text in Telegram explaining what happened or showing the results.

## Actual Behavior

- Tool execution notifications appear: "🔧 Execute Bash..."
- Command completes successfully
- **No response message from Kiro appears in Telegram**
- Logs show chunks being accumulated and `turn_end` being called, but message never sent

## Root Cause Analysis

From log analysis (test command at 15:05:41):

1. **15:05:41** - Tool call notification sent: "🔧 Execute Bash..."
2. **15:05:54** - Kiro starts generating response chunks (`agent_message_chunk`)
3. **15:06:24** - `stopReason: end_turn` received, `turn_end` callback fires
4. **15:06:24** - Log shows: "Worker: Turn end - 137 chunks accumulated"
5. **NO MESSAGE SENT TO TELEGRAM**

### The Bug

In `kiro_session_acp.py`, the `on_turn_end()` callback is defined but **the message is never actually sent**:

```python
def on_turn_end():
    chunks = agent_data['chunks']
    logger.info(f"Worker: Turn end - {len(chunks)} chunks accumulated")
    if chunks:
        message = "".join(chunks)
        logger.info(f"Worker: Sending final message (length: {len(message)})")
        self._send_to_telegram_sync(agent_data['chat_id'], message)  # This line exists
    else:
        logger.warning(f"Worker: Turn end but no chunks!")
```

The code **looks correct** - it should be calling `_send_to_telegram_sync()`. But the logs show:
- ✅ "Worker: Turn end - 137 chunks accumulated"
- ❌ NO "Worker: Sending final message" log
- ❌ NO "_send_to_telegram_sync called" log

This means the `if chunks:` condition is **failing** even though 137 chunks were accumulated.

## Investigation Steps

1. Check if `agent_data['chunks']` is being cleared somewhere before `on_turn_end()`
2. Verify the `on_turn_end` callback is properly registered
3. Check if there are multiple callback registrations causing issues
4. Examine the exact state of `agent_data` when `on_turn_end()` fires

## Likely Causes

### Hypothesis 1: Chunks Array Cleared Prematurely
The `agent_data['chunks']` array might be getting cleared or reset before `on_turn_end()` is called.

### Hypothesis 2: Wrong Agent Data Reference
The `on_turn_end` callback might be referencing a different `agent_data` dict than the one being populated by `on_chunk`.

### Hypothesis 3: Callback Registration Issue
Callbacks might be registered multiple times or cleared, causing the wrong version to execute.

## Debugging Steps

Add more logging to `_handle_send_message()`:

```python
def on_turn_end():
    logger.info(f"Worker: on_turn_end called")
    logger.info(f"Worker: agent_data keys: {agent_data.keys()}")
    logger.info(f"Worker: chunks type: {type(agent_data.get('chunks'))}")
    logger.info(f"Worker: chunks length: {len(agent_data.get('chunks', []))}")
    chunks = agent_data['chunks']
    logger.info(f"Worker: Turn end - {len(chunks)} chunks accumulated")
    logger.info(f"Worker: chunks bool: {bool(chunks)}")
    if chunks:
        message = "".join(chunks)
        logger.info(f"Worker: Sending final message (length: {len(message)})")
        self._send_to_telegram_sync(agent_data['chat_id'], message)
    else:
        logger.warning(f"Worker: Turn end but no chunks!")
```

## Potential Solutions (After Root Cause Found)

## Next Steps

1. Add detailed logging to `on_turn_end()` callback
2. Restart bot and run test command again
3. Analyze logs to see exact state when callback fires
4. Fix the bug once root cause is identified

## Test Case

```bash
for i in {1..10}; do
  echo "hello world $i"
  sleep 1
done
```

Expected: See Kiro's response after 10 seconds
Actual: No response appears in Telegram
