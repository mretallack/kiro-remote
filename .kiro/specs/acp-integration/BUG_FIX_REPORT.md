# ACP Integration - Bug Fix Report

## Issue
When sending messages to Kiro via ACP, the bot was not receiving replies.

## Root Cause
The implementation was waiting for a `TurnEnd` notification that **does not exist** in the ACP protocol specification.

According to the [official ACP spec](https://agentclientprotocol.com/protocol/prompt-turn), the turn completion is signaled by the **response** to the `session/prompt` request, not by a notification:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "stopReason": "end_turn"
  }
}
```

The implementation incorrectly expected a `session/update` notification with `type: "TurnEnd"`.

## How ACP Actually Works

### Message Flow
1. Client sends `session/prompt` request
2. Agent sends `session/update` notifications with message chunks:
   ```json
   {
     "jsonrpc": "2.0",
     "method": "session/update",
     "params": {
       "sessionId": "sess_abc123",
       "update": {
         "sessionUpdate": "agent_message_chunk",
         "content": {"type": "text", "text": "Hello"}
       }
     }
   }
   ```
3. Agent responds to the original `session/prompt` request with `stopReason`:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 2,
     "result": {"stopReason": "end_turn"}
   }
   ```

**The response in step 3 IS the turn end signal.**

## Fix Applied

### Changes Made

#### 1. `acp_client.py`
Changed `send_prompt()` to return the result:
```python
def send_prompt(self, session_id: str, content: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Send a prompt to the agent and return the result with stopReason."""
    # ... send request ...
    result = self._send_request("session/prompt", params)
    return result  # Returns {"stopReason": "end_turn"}
```

#### 2. `acp_session.py`
Modified `send_message()` and `send_image()` to trigger turn_end callbacks:
```python
def send_message(self, text: str) -> None:
    """Send a text message."""
    content = [{"type": "text", "text": text}]
    result = self.client.send_prompt(self.session_id, content)
    
    # Trigger turn_end when we get the response
    if result and result.get("stopReason"):
        for callback in self.turn_end_callbacks:
            callback()
```

Removed incorrect handling of non-existent `turn_end` notification:
```python
# REMOVED - this never fires
elif update_type in ["turn_end", "TurnEnd"]:
    for callback in self.turn_end_callbacks:
        callback()
```

## Verification

### Test Results

#### Basic Test (`test_turn_end.py`)
```
✅ SUCCESS: Turn end callback fired and message received!
```

#### Integration Tests (`test_acp_integration.py`)
```
✅ PASS: ACPClient
✅ PASS: ACPSession
✅ PASS: KiroSessionACP
```

#### End-to-End Test (`test_e2e.py`)
```
✅ END-TO-END TEST PASSED
- 3 messages exchanged successfully
- Tool calls working
- Turn completion working correctly
```

## Impact

### Before Fix
- Messages sent to Kiro
- Chunks received via notifications
- **Bot never sent reply** (waiting forever for TurnEnd)

### After Fix
- Messages sent to Kiro
- Chunks received via notifications
- **Bot sends reply immediately** when turn completes

## Lessons Learned

1. **Read the spec carefully**: The ACP documentation clearly states turn completion is via response, not notification
2. **Test against real protocol**: Integration tests caught this issue
3. **Don't assume patterns**: Just because other protocols use notifications doesn't mean ACP does

## References

- [ACP Prompt Turn Specification](https://agentclientprotocol.com/protocol/prompt-turn)
- [Kiro ACP Documentation](https://kiro.dev/docs/cli/acp/)
- Implementation: `.kiro/specs/acp-integration/`

## Status

✅ **FIXED AND VERIFIED**

The ACP integration is now fully functional and ready for deployment.
