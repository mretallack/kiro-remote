# Design: Telegram Bot Output Buffering & Typing Indicators

## Architecture Overview

The solution involves two independent mechanisms:

1. **Chunk Buffer with Timeout**: Accumulates text chunks and sends them after a timeout period
2. **Typing Indicator Thread**: Continuously refreshes Telegram's typing indicator during processing

Both mechanisms operate within the existing worker thread architecture without requiring major refactoring.

## Component Design

### 1. Chunk Buffer Manager

**Location**: `kiro_session_acp.py` - within `_handle_send_message` method

**State Variables** (per agent):
```python
agent_data = {
    "chunks": [],              # Accumulated text chunks
    "chunk_timer": None,       # threading.Timer for timeout
    "chunk_lock": Lock(),      # Thread safety for chunk operations
    "typing_thread": None,     # Thread for typing indicator
    "typing_stop_event": Event(),  # Signal to stop typing thread
    ...
}
```

**Timeout Logic**:
```
on_chunk(content):
    1. Acquire chunk_lock
    2. Append content to chunks[]
    3. Cancel existing chunk_timer (if any)
    4. Create new Timer(2.0, flush_chunks)
    5. Start timer
    6. Release chunk_lock

flush_chunks():
    1. Acquire chunk_lock
    2. If chunks[] is not empty:
        a. Join chunks into message
        b. Send to Telegram
        c. Clear chunks[]
    3. Release chunk_lock

on_turn_end():
    1. Cancel chunk_timer (if active)
    2. Call flush_chunks() to send any remaining text
    3. Signal typing_stop_event
```

### 2. Typing Indicator Thread

**Location**: `kiro_session_acp.py` - within `_handle_send_message` method

**Thread Function**:
```python
def typing_indicator_loop(chat_id, stop_event):
    while not stop_event.is_set():
        try:
            # Send typing action
            asyncio.run_coroutine_threadsafe(
                send_typing_action(chat_id),
                loop
            )
        except Exception as e:
            logger.error(f"Typing indicator error: {e}")
        
        # Wait 4 seconds or until stop signal
        stop_event.wait(4.0)
```

**Lifecycle**:
- **Start**: When `_handle_send_message` begins processing
- **Stop**: When `on_turn_end` is called or error occurs
- **Cleanup**: Thread joins with timeout to prevent hanging

### 3. Integration Points

#### Existing Callbacks
```python
def on_chunk(content):
    # NEW: Buffer with timeout instead of immediate append
    buffer_chunk_with_timeout(content)

def on_tool_call(tool):
    # UNCHANGED: Send tool notification immediately
    send_tool_notification(tool)

def on_tool_update(update):
    # UNCHANGED: Send stdout/stderr immediately
    send_command_output(update)

def on_turn_end():
    # NEW: Flush remaining chunks and stop typing
    flush_chunks()
    stop_typing_indicator()
```

## Sequence Diagram

```
User                Telegram Bot           Worker Thread         Kiro CLI
 |                       |                       |                    |
 |---"remove CSV"------->|                       |                    |
 |                       |---send_message------->|                    |
 |                       |                       |---start_typing---->|
 |                       |                       |                    |
 |                       |                       |<---chunk: "You're right"
 |                       |                       |                    |
 |                       |                  [buffer + start timer]    |
 |                       |                       |                    |
 |                       |                       |<---chunk: "Let me remove"
 |                       |                       |                    |
 |                       |                  [buffer + reset timer]    |
 |                       |                       |                    |
 |                       |              [2s timeout expires]          |
 |                       |                       |                    |
 |<---"You're right. Let me remove..."----------|                    |
 |                       |                       |                    |
 |                       |                  [typing indicator refresh]|
 |                       |                       |                    |
 |                       |                       |<---tool_call: write|
 |                       |                       |                    |
 |<---"🔧 write"---------|                       |                    |
 |                       |                       |                    |
 |                       |                       |<---chunk: "Now let me"
 |                       |                       |                    |
 |                       |                  [buffer + start timer]    |
 |                       |                       |                    |
 |                       |              [2s timeout expires]          |
 |                       |                       |                    |
 |<---"Now let me also update..."---------------|                    |
 |                       |                       |                    |
 |                       |                       |<---turn_end        |
 |                       |                       |                    |
 |                       |                  [flush chunks]            |
 |                       |                  [stop typing]             |
 |                       |                       |                    |
 |<---"Perfect! I've removed..."----------------|                    |
```

## Implementation Considerations

### Thread Safety

**Problem**: Multiple threads accessing `agent_data["chunks"]`:
- Worker thread's `on_chunk` callback (appends chunks)
- Timer thread's `flush_chunks` (reads and clears chunks)
- Worker thread's `on_turn_end` (flushes remaining chunks)

**Solution**: Use `threading.Lock()` to protect chunk operations:
```python
chunk_lock = threading.Lock()

# In on_chunk
with chunk_lock:
    chunks.append(content)
    # Reset timer

# In flush_chunks
with chunk_lock:
    if chunks:
        message = "".join(chunks)
        send_message(message)
        chunks.clear()
```

### Timer Management

**Problem**: Timers can fire after `on_turn_end` completes

**Solution**: 
- Cancel timer in `on_turn_end` before flushing
- Check if chunks exist before sending in `flush_chunks`
- Use daemon threads for typing indicator

### Async/Sync Bridge

**Problem**: Worker thread is synchronous, but Telegram bot uses async

**Current Solution**: `_send_to_telegram_sync` already handles this via `asyncio.run_coroutine_threadsafe`

**For Typing Indicator**: Use same pattern:
```python
future = asyncio.run_coroutine_threadsafe(
    application.bot.send_chat_action(chat_id, ChatAction.TYPING),
    loop
)
future.result(timeout=5.0)  # Wait for completion
```

### Timeout Value Selection

**Considerations**:
- Too short (< 1s): Many small messages, chatty output
- Too long (> 3s): Feels unresponsive
- **Recommended**: 2 seconds balances responsiveness and message consolidation

### Error Handling

**Scenarios**:
1. **Timer fires after agent deleted**: Check agent exists in `flush_chunks`
2. **Typing thread fails**: Log error but don't crash worker
3. **Send message fails**: Log error, continue processing

## Testing Strategy

### Unit Tests
- Chunk buffering with timeout
- Timer cancellation on turn_end
- Thread safety with concurrent chunk appends
- Typing indicator start/stop

### Integration Tests
- Full message flow with interleaved tool calls
- Multiple rapid messages
- Long-running operations (> 10 seconds)
- Error during processing

### Manual Testing
- Visual verification of message order
- Typing indicator persistence
- Timeout behavior observation

## Rollout Plan

1. **Phase 1**: Implement chunk buffering with timeout
2. **Phase 2**: Add typing indicator thread
3. **Phase 3**: Test with real Telegram bot
4. **Phase 4**: Tune timeout value based on user feedback

## Alternative Approaches Considered

### 1. Streaming Individual Tokens
**Rejected**: Kiro already sends sentence-level chunks; token streaming would be too granular and create message spam

### 2. Editing Previous Messages
**Rejected**: Telegram bot architecture uses append-only messaging; editing would require significant refactoring

### 3. Single Timeout for Entire Response
**Rejected**: Doesn't solve the interleaving problem; text would still appear in one burst at the end

## Configuration

Add to `settings.ini`:
```ini
[bot]
chunk_timeout = 2.0          # Seconds to wait before flushing chunks
typing_refresh_interval = 4.0 # Seconds between typing indicator refreshes
```

## Backward Compatibility

No breaking changes. The modification is internal to `kiro_session_acp.py` and doesn't affect:
- External API
- Message format
- Command handling
- Agent management
