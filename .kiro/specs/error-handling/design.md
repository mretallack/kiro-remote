# Error Handling Improvements — Design

## Architecture Overview

All five fixes modify existing files with minimal new abstractions. No new modules are needed — changes are localized to `kiro_session_acp.py`, `telegram_kiro_bot.py`, and `acp_client.py`.

```
telegram_kiro_bot.py          kiro_session_acp.py          acp_client.py
┌─────────────────────┐      ┌──────────────────────┐     ┌──────────────────┐
│ _send_message_safe()│      │ prompt_in_flight flag │     │ configurable     │
│ (split + retry)     │◄────►│ usage_limit_reached   │────►│ prompt timeout   │
│ global error handler│      │ message queueing      │     │                  │
└─────────────────────┘      └──────────────────────┘     └──────────────────┘
```

## Fix 1: Message Too Long Splitting

### Location
`kiro_session_acp.py` — `_send_to_telegram_sync()` method

### Approach
Add a `_split_html_message()` helper that splits HTML text into chunks ≤4096 chars. Call it before sending.

### Split Algorithm
1. If message ≤ 4096 chars, send as-is
2. Split at `\n\n` (paragraph) boundaries where possible
3. Fall back to `\n` (line) boundaries
4. Last resort: split at 4096 char boundary
5. Track open `<pre>` and `<code>` tags — close before split, reopen after
6. Send chunks sequentially

### Tag Tracking
Maintain a simple stack of open tags (`<pre>`, `<code>`, `<b>`, `<i>`). When splitting:
- Append closing tags for any open tags at split point
- Prepend reopening tags at start of next chunk

## Fix 2: Configurable Prompt Timeout

### Location
- `settings.ini.template` — add `prompt_timeout` setting
- `telegram_kiro_bot.py` — read setting, pass to `KiroSessionACP`
- `kiro_session_acp.py` — store `prompt_timeout`, pass to agent's `ACPClient`
- `acp_client.py` — accept timeout parameter in `_send_request()`

### Flow
```
settings.ini → TelegramBot.__init__() → KiroSessionACP.prompt_timeout
                                              ↓
                                    _handle_start_session()
                                              ↓
                                    ACPClient._send_request(timeout=self.prompt_timeout)
```

### Changes
- `ACPClient._send_request()`: Change hardcoded `timeout=600` to accept a parameter with default 600
- `ACPClient`: Add `prompt_timeout` attribute, set from `KiroSessionACP`
- `_handle_send_message()`: Catch timeout exception specifically, send user-friendly message

### Timeout Notification
On timeout, send: "⏱️ Request timed out after {N}s. The operation may still be running — use `\cancel` to stop it."

## Fix 3: Prompt Already In Progress Guard

### Location
`kiro_session_acp.py` — `_handle_send_message()` and agent data structure

### Approach
Add `prompt_in_flight` boolean to each agent's data dict. Check before sending, set on send, clear on completion/error.

### State Machine
```
IDLE ──send_message──► IN_FLIGHT ──turn_end/error──► IDLE
                           │
                    new message arrives
                           │
                    reply "still processing"
```

### Changes
- Agent data dict: add `"prompt_in_flight": False`
- `_handle_send_message()`: Check flag at start, set to `True` before `session.send_message()`, clear in `on_turn_end` and error handler
- When blocked: send "⏳ Previous request still processing..." to user

## Fix 4: Monthly Usage Limit Handling

### Location
`kiro_session_acp.py` — `_send_error()` and `_handle_send_message()`

### Approach
Detect the specific error string in `_send_error()`, set a `usage_limit_reached` flag on the agent. Check flag at start of `_handle_send_message()`.

### Changes
- Agent data dict: add `"usage_limit_reached": False`
- `_send_error()`: When error contains "monthly usage limit", set flag
- `_handle_send_message()`: Check flag at start, reject with friendly message
- `_handle_cancel()`: Clear the flag (allows retry after cancel)
- `restart_with_agent()`: Clear the flag on agent restart

## Fix 5: Transient Network Error Recovery

### Location
`kiro_session_acp.py` — `_send_to_telegram_sync()`  
`telegram_kiro_bot.py` — `run()` method

### Approach — Retry in `_send_to_telegram_sync()`
Wrap the `future.result()` call in a retry loop (3 attempts, exponential backoff: 1s, 2s, 4s). Only retry on `NetworkError`.

### Approach — Global Error Handler
Register `application.add_error_handler(error_handler)` in `TelegramBot.__init__()`. The handler logs the error and continues.

### Retry Logic
```python
for attempt in range(max_retries):
    try:
        future = asyncio.run_coroutine_threadsafe(...)
        future.result(timeout=10.0)
        break
    except Exception as e:
        if "NetworkError" in str(type(e).__name__) or "NetworkError" in str(e):
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
        raise
```

## Configuration Changes

### settings.ini.template additions
```ini
# Timeout in seconds for Kiro prompt responses (default: 600)
prompt_timeout = 600
```

## Error Handling Summary

| Error | Detection | User Message | Recovery |
|-------|-----------|-------------|----------|
| Message too long | len(text) > 4096 after HTML conversion | (transparent split) | Automatic |
| Prompt timeout | `queue.Empty` exception | "⏱️ Request timed out..." | User cancels or waits |
| Prompt in progress | `prompt_in_flight` flag | "⏳ Previous request still processing..." | Auto-processes after completion |
| Usage limit | Error string match | "❌ Monthly usage limit reached..." | Cancel or restart agent |
| Network error | `NetworkError` exception type | (transparent retry) | Automatic with backoff |

## Testing Strategy

- Unit tests for `_split_html_message()` with various edge cases (nested tags, long code blocks, empty messages)
- Unit tests for prompt-in-flight guard logic
- Unit tests for usage limit flag set/clear lifecycle
- Integration test for retry logic with mocked network failures
- Existing tests must continue to pass
