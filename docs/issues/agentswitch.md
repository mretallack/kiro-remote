# kiro-cli ValidationException After Image + Model Switch

## Summary

kiro-cli returns ValidationException when sending a text prompt after:
1. Sending an image
2. Switching models

## Reproduction Steps

### Via Standard CLI (Confirmed)
1. Start kiro-cli: `kiro-cli chat`
2. Use default `auto` model
3. Send a prompt with image: `look at /path/to/image.jpg`
   - Auto model selects vision-capable model (e.g., Claude)
   - Image is processed successfully
4. Switch to text-only model: `/model` → select `deepseek-3.2`
5. Send a simple text prompt: `hi`

**Expected**: Text prompt is processed normally

**Actual**: kiro-cli crashes with ValidationException:
```
Kiro is having trouble responding right now: 
   0: Failed to send the request: An unknown error occurred: ValidationException
   1: An unknown error occurred: ValidationException
   2: unhandled error (ValidationException)
   3: service error
   4: unhandled error (ValidationException)
   5: Error { code: "ValidationException", message: "Improperly formed request.", aws_request_id: "bd421b23-0340-4fc9-8e71-82829bcbecb0" }

Location:
   crates/chat-cli/src/cli/chat/mod.rs:1460
```

### Via ACP Mode
1. Start kiro-cli in ACP mode: `kiro-cli acp`
2. Create a new session
3. Send a prompt with image content (via `session/prompt` with image type)
4. Switch model using `session/set_model` (e.g., to `deepseek-3.2`)
5. Send a simple text prompt (e.g., "hi")

**Expected**: Text prompt is processed normally

**Actual**: kiro-cli returns JSON-RPC error:
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": "Agent error"
  },
  "id": 9
}
```

## Environment

- **kiro-cli version**: Latest (2026-02-15)
- **Interfaces tested**: 
  - Standard CLI (`kiro-cli chat`)
  - Agent Client Protocol (ACP) via JSON-RPC (`kiro-cli acp`)
- **Tested via**: Direct CLI, Telegram bot bridge (remote-kiro)
- **Models tested**: deepseek-3.2, auto
- **Date**: 2026-02-15

## Error Details

### Standard CLI Error
- **Error Type**: ValidationException from AWS service
- **Error Message**: "Improperly formed request."
- **Location**: `crates/chat-cli/src/cli/chat/mod.rs:1460`
- **AWS Request ID**: `940a5a04-f7d9-43bc-8aaf-41b6373f62aa`

### ACP Mode Error
- **Error Type**: JSON-RPC Internal Error (-32603)
- **Error Message**: "Agent error"

## Logs

### Standard CLI Session

#### Successful Image Prompt (deepseek-3.2)
```
> look at /home/mark/.kiro/bot_attachments/1771141015_1224766270_photo_DeQADOgQ.jpg
✓ Successfully read image
[Response about image content]
▸ Credits: 0.15 • Time: 14s
```

#### Successful Model Switch (deepseek-3.2 → auto)
```
> /model
Using auto
```

#### Failed Text Prompt (auto model)
```
> hi
Kiro is having trouble responding right now: 
   0: Failed to send the request: An unknown error occurred: ValidationException
   [full error trace above]
```

### ACP Mode Session

#### Successful Image Prompt
```
2026-02-15 07:37:07 - Session update: agent_message_chunk (84 chunks total)
2026-02-15 07:37:07 - Result: {"stopReason":"end_turn"}
```

#### Successful Model Switch
```
2026-02-15 07:37:26 - Set model to: deepseek-3.2
2026-02-15 07:37:26 - Result: {}
```

#### Failed Text Prompt
```
2026-02-15 07:37:38 - Sending message: hi
2026-02-15 07:37:38 - Error: {"code":-32603,"message":"Internal error","data":"Agent error"}
```

## Analysis

The error occurs specifically when:
- Previous prompt contained image content
- Model was switched after the image prompt
- Next prompt is text-only

**Root Cause Confirmed**: When using `auto` model with an image, then switching to a model that doesn't support images (e.g., `deepseek-3.2`), kiro-cli crashes with ValidationException.

The sequence:
1. User sends image with `auto` model → Works (auto selects vision-capable model)
2. User switches to `deepseek-3.2` → Switch succeeds
3. User sends text prompt → **Crash**: ValidationException

**Why it happens**:
- The conversation history includes the image content from step 1
- When sending the new text prompt in step 3, kiro-cli includes the full conversation history
- DeepSeek 3.2 doesn't support image content
- AWS Bedrock rejects the request: "Improperly formed request."

**The bug**: kiro-cli doesn't filter or sanitize conversation history when switching to models with different capabilities. It blindly sends image content to text-only models.

**Code Location**: `crates/chat-cli/src/cli/chat/mod.rs:1460` - This is where the request is being sent to AWS Bedrock.

## Workaround

**Start a new session** after switching models if the previous conversation contained images.

In standard CLI:
```bash
# Exit and restart kiro-cli
# OR use /new command if available
```

In ACP mode:
```json
// Create a new session instead of reusing the existing one
{"jsonrpc": "2.0", "method": "session/create", "params": {}, "id": 1}
```

## Additional Notes

- The error is consistent across both CLI and ACP interfaces
- The underlying cause is the same (ValidationException from AWS Bedrock)
- ACP mode wraps the error as "Agent error" (-32603)
- Standard CLI shows the full error trace
- Session becomes unusable after this sequence
- The issue occurs regardless of which model is switched to (tested with `auto` and `deepseek-3.2`)

## Fix Requirements

The fix should:
1. **Detect model capabilities**: Know which models support images (vision) vs text-only
2. **Filter conversation history**: When switching to a text-only model, strip image content from history
3. **Options for handling**:
   - **Option A**: Automatically strip images and continue (silent)
   - **Option B**: Warn user that image context will be lost when switching
   - **Option C**: Prevent switching to text-only models if history contains images
4. Handle this gracefully without crashing or returning ValidationException

**Recommended approach**: Option A (auto-strip) with optional warning message:
```
⚠️  Switched to deepseek-3.2 (text-only model). Image content from conversation history has been removed.
```

**Models that support images** (as of 2026-02-15):
- Claude Opus 4.6
- Claude Opus 4.5  
- Claude Sonnet 4.5
- Claude Sonnet 4
- Claude Haiku 4.5
- Auto (delegates to vision-capable models when needed)

**Text-only models**:
- DeepSeek 3.2
- MiniMax M2.1

## Related Code

- **Error location**: `crates/chat-cli/src/cli/chat/mod.rs:1460`
- **ACP client**: `/home/mark/git/remote-kiro/acp_client.py`
- **Session handler**: `/home/mark/git/remote-kiro/acp_session.py`
- **Bot integration**: `/home/mark/git/remote-kiro/telegram_kiro_bot.py`
