# Issue: Command Output Not Displayed in Telegram

## Status: ✅ RESOLVED

## Problem Description

When Kiro executed commands, only the tool execution notification appeared in Telegram (e.g., "🔧 Running: echo hello"). The actual stdout/stderr output from the command was never displayed.

## Root Cause

The bot was only handling `tool_call` notifications but not `tool_call_update` messages. Kiro sends command output in the `tool_call_update` message with `status: "completed"`:

```json
{
  "sessionUpdate": "tool_call_update",
  "status": "completed",
  "rawOutput": {
    "items": [{
      "Json": {
        "exit_status": "exit status: 0",
        "stdout": "hello 1\nhello 2\n...",
        "stderr": ""
      }
    }]
  }
}
```

## Solution

Added `on_tool_update` callback handler in `kiro_session_acp.py` that:
1. Listens for `tool_call_update` messages with `status: "completed"`
2. Extracts stdout/stderr from `rawOutput`
3. Truncates long output (first 1000 + last 1000 bytes)
4. Sends to Telegram in code blocks

## Files Changed

- `kiro_session_acp.py`: Added `on_tool_update()` callback
- `acp_session.py`: Already had infrastructure for tool updates
- `README.md`: Updated documentation
- `tests/test_long_running_command.py`: Added test to verify behavior

## Testing

```bash
pytest tests/test_long_running_command.py -v
```

Verifies that stdout is captured and would be sent to Telegram.
