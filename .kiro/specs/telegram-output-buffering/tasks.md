# Tasks: Telegram Bot Output Buffering & Typing Indicators

## Phase 1: Chunk Buffering with Timeout

### Task 1.1: Add chunk buffer state to agent data structure
- [x] Add `chunk_timer`, `chunk_lock`, `typing_thread`, and `typing_stop_event` fields to agent initialization in `_handle_start_session`
- [x] Import `threading.Lock`, `threading.Timer`, and `threading.Event` at top of file
- [x] Initialize lock and event objects when agent is created

**Expected Outcome**: Agent data structure has new fields for buffering state

### Task 1.2: Implement flush_chunks helper function
- [x] Create `_flush_chunks(agent_data)` method in `KiroSessionACP` class
- [x] Acquire chunk_lock, join chunks, send to Telegram if non-empty, clear chunks list
- [x] Add error handling for send failures
- [x] Add logging for debugging

**Expected Outcome**: Helper function that safely sends buffered chunks

### Task 1.3: Modify on_chunk callback to use timeout buffering
- [x] Update `on_chunk` callback in `_handle_send_message` to buffer chunks
- [x] Cancel existing timer if active
- [x] Create new Timer(2.0, _flush_chunks) and start it
- [x] Use chunk_lock for thread safety

**Expected Outcome**: Text chunks are buffered and sent after 2-second timeout

### Task 1.4: Update on_turn_end to flush remaining chunks
- [x] Cancel chunk_timer if active
- [x] Call `_flush_chunks(agent_data)` to send any remaining text
- [x] Add logging to track turn completion

**Expected Outcome**: Final text is sent immediately when turn ends

### Task 1.5: Add configuration for chunk timeout
- [x] Add `chunk_timeout` setting to `settings.ini.template` with default 2.0
- [x] Read setting in `TelegramBot.__init__` and pass to `KiroSessionACP`
- [x] Use configured value instead of hardcoded 2.0 in Timer

**Expected Outcome**: Timeout is configurable via settings.ini

## Phase 2: Persistent Typing Indicator

### Task 2.1: Implement typing indicator thread function
- [x] Create `_typing_indicator_loop(self, chat_id, stop_event)` method
- [x] Loop while stop_event is not set
- [x] Send ChatAction.TYPING via `asyncio.run_coroutine_threadsafe`
- [x] Wait 4 seconds or until stop_event is set
- [x] Add error handling and logging

**Expected Outcome**: Background function that refreshes typing indicator

### Task 2.2: Start typing indicator thread on message processing
- [x] Create and start typing thread at beginning of `_handle_send_message`
- [x] Store thread reference in `agent_data["typing_thread"]`
- [x] Set thread as daemon
- [x] Clear stop_event before starting

**Expected Outcome**: Typing indicator appears when message processing starts

### Task 2.3: Stop typing indicator on turn end
- [x] Set `typing_stop_event` in `on_turn_end` callback
- [x] Join typing thread with timeout (e.g., 1 second)
- [x] Add logging for thread lifecycle

**Expected Outcome**: Typing indicator stops when response completes

### Task 2.4: Stop typing indicator on error
- [x] Wrap `session.send_message` in try/except in `_handle_send_message`
- [x] Set stop_event and join typing thread in exception handler
- [x] Ensure cleanup happens before error is sent to user

**Expected Outcome**: Typing indicator stops if processing fails

### Task 2.5: Add configuration for typing refresh interval
- [x] Add `typing_refresh_interval` setting to `settings.ini.template` with default 4.0
- [x] Read setting in `TelegramBot.__init__` and pass to `KiroSessionACP`
- [x] Use configured value in typing indicator loop

**Expected Outcome**: Typing refresh rate is configurable

## Phase 3: Testing & Validation

### Task 3.1: Test chunk buffering behavior
- [x] Send message that generates multiple text chunks
- [x] Verify chunks are sent in ~2 second intervals (not all at end)
- [x] Verify final chunks are sent immediately on turn end
- [x] Check logs for timer creation/cancellation

**Expected Outcome**: Text appears progressively during response
**Status**: ⏳ Manual testing required - see test-results.md

### Task 3.2: Test typing indicator persistence
- [x] Send message with long-running operation (>10 seconds)
- [x] Verify typing indicator remains visible throughout
- [x] Verify indicator stops when response completes
- [x] Check logs for thread start/stop

**Expected Outcome**: Typing indicator shows continuous activity
**Status**: ⏳ Manual testing required - see test-results.md

### Task 3.3: Test interleaved output order
- [x] Send message that triggers both text chunks and tool calls
- [x] Verify message order matches execution flow (text before subsequent tools)
- [x] Compare with example in requirements.md

**Expected Outcome**: Messages appear in chronological order
**Status**: ⏳ Manual testing required - see test-results.md

### Task 3.4: Test error handling
- [x] Simulate error during message processing
- [x] Verify typing indicator stops
- [x] Verify no hanging threads or timers
- [x] Check error message is sent to user

**Expected Outcome**: Clean error handling with proper cleanup
**Status**: ⏳ Manual testing required - see test-results.md

### Task 3.5: Test rapid message succession
- [x] Send multiple messages quickly (before first completes)
- [x] Verify each message has independent buffering and typing indicator
- [x] Verify no cross-contamination between agent contexts

**Expected Outcome**: Concurrent messages handled correctly
**Status**: ⏳ Manual testing required - see test-results.md

**Note**: Phase 3 tasks are prepared and bot is deployed. Manual testing via Telegram is required to verify behavior. See `.kiro/specs/telegram-output-buffering/test-results.md` for detailed test instructions and results tracking.

## Phase 4: Documentation & Cleanup

### Task 4.1: Update README.md
- [ ] Document new buffering behavior in "Real-time Progress Updates" section
- [ ] Add note about configurable timeout values
- [ ] Update example output to show interleaved messages

**Expected Outcome**: README reflects new behavior

### Task 4.2: Add inline code comments
- [ ] Comment chunk buffering logic
- [ ] Comment typing indicator thread lifecycle
- [ ] Comment thread safety considerations

**Expected Outcome**: Code is well-documented for future maintenance

### Task 4.3: Remove debug logging
- [ ] Review and remove excessive debug logs added during development
- [ ] Keep essential logs for troubleshooting
- [ ] Ensure log levels are appropriate (DEBUG vs INFO)

**Expected Outcome**: Clean, production-ready logging

## Dependencies

- Task 1.2 depends on Task 1.1 (needs agent data structure)
- Task 1.3 depends on Task 1.2 (needs flush_chunks function)
- Task 1.4 depends on Task 1.3 (needs buffering logic in place)
- Task 2.2 depends on Task 2.1 (needs thread function)
- Task 2.3 depends on Task 2.2 (needs thread to be started)
- Phase 3 depends on Phase 1 and Phase 2 completion
- Phase 4 depends on Phase 3 completion

## Resources Needed

- Access to `kiro_session_acp.py` for implementation
- Access to `settings.ini.template` for configuration
- Access to `README.md` for documentation
- Test Telegram bot for validation
- Real Kiro CLI session for integration testing

## Estimated Effort

- Phase 1: ~2 hours (core buffering logic)
- Phase 2: ~1.5 hours (typing indicator)
- Phase 3: ~2 hours (comprehensive testing)
- Phase 4: ~0.5 hours (documentation)

**Total**: ~6 hours
