# Context Management via ACP - Tasks

## Phase 1: Core Infrastructure

### Task 1.1: Create ContextTracker Class
- [x] Create `context_tracker.py` module
- [x] Implement `ContextTracker` class with usage storage
- [x] Add `update_usage()`, `get_usage()` methods
- [x] Add `should_warn()` (80%) and `should_alert()` (90%) threshold checks
- [x] Add unit tests for threshold logic

**Expected Outcome**: Reusable context tracking component with threshold detection

### Task 1.2: Integrate Context Tracking with Metadata Notifications
- [x] Modify `acp_session.py` to expose metadata in notification handler
- [x] Add `ContextTracker` instance to `KiroSessionACP`
- [x] Hook metadata notifications to update context tracker
- [x] Log context usage updates at debug level

**Expected Outcome**: Context usage automatically tracked from ACP metadata notifications

### Task 1.3: Create ANSI Stripping Utility
- [x] Create `text_utils.py` module
- [x] Implement `strip_ansi()` function using regex
- [x] Add `truncate_message()` function (4000 char limit)
- [x] Add unit tests for ANSI stripping and truncation

**Expected Outcome**: Utility functions for formatting command output for Telegram

## Phase 2: Command Execution

### Task 2.1: Add \context Command Handler
- [x] Add `\context` command to `_handle_bot_command()` in `kiro_session_acp.py`
- [x] Display current context usage percentage
- [x] Handle case when usage is unknown
- [x] Format message with emoji indicator (📊)

**Expected Outcome**: Users can check context usage with `\context`

### Task 2.2: Add \context show Command Handler
- [x] Add `\context show` subcommand handler
- [x] Execute `/context show` via `ACPClient.execute_command()`
- [x] Strip ANSI codes from output
- [x] Truncate if needed and send to user
- [x] Handle command execution errors

**Expected Outcome**: Users can view detailed context info with `\context show`

### Task 2.3: Add \context clear Command Handler
- [x] Add `\context clear` subcommand handler
- [x] Execute `/context clear` via `ACPClient.execute_command()`
- [x] Send confirmation message to user
- [x] Handle command execution errors

**Expected Outcome**: Users can clear context rules with `\context clear`

### Task 2.4: Add \compact Command Handler
- [x] Add `\compact` command to `_handle_bot_command()`
- [x] Execute `/compact` via `ACPClient.execute_command()`
- [x] Send "🔄 Compacting conversation..." message
- [x] Handle command execution errors

**Expected Outcome**: Users can trigger manual compaction with `\compact`

## Phase 3: Status Notifications

### Task 3.1: Implement Compaction Status Tracking
- [x] Add compaction status callback in `KiroSessionACP`
- [x] Register callback with `ACPSession.on_compaction_status()`
- [x] Track compaction state (idle, in_progress, complete, failed)
- [x] Send status updates to user

**Expected Outcome**: Users see real-time compaction status updates

### Task 3.2: Implement Context Usage Warnings
- [x] Add warning state tracking to `KiroSessionACP`
- [x] Check thresholds after each context update
- [x] Send warning at 80%: "⚠️ Context usage: 80%. Consider using \compact"
- [x] Send alert at 90%: "🚨 Context usage: 90%. Recommend compacting now"
- [x] Throttle warnings (only once per threshold crossing)
- [x] Reset warning state after compaction

**Expected Outcome**: Users receive proactive warnings about high context usage

## Phase 4: Testing & Documentation

### Task 4.1: Add Integration Tests
- [x] Test `\context` command returns usage
- [x] Test `\context show` executes and returns output
- [x] Test `\context clear` executes successfully
- [x] Test `\compact` triggers compaction
- [x] Test context warnings at 80% and 90%
- [x] Test compaction status notifications

**Expected Outcome**: Comprehensive test coverage for new features

### Task 4.2: Update README Documentation
- [x] Add `\context` command to Bot Commands section
- [x] Add `\compact` command to Bot Commands section
- [x] Document context usage warnings
- [x] Add examples of command usage
- [x] Update feature list

**Expected Outcome**: Users can discover and understand new commands

### Task 4.3: Manual Testing
- [ ] Test all commands via Telegram bot
- [ ] Verify context usage tracking accuracy
- [ ] Test warning messages appear at correct thresholds
- [ ] Test compaction status updates
- [ ] Test error handling for invalid commands
- [ ] Test with different context usage levels

**Expected Outcome**: All features work correctly in production environment

## Phase 5: Polish & Refinement

### Task 5.1: Error Handling Improvements
- [x] Add graceful handling for missing command support
- [x] Improve error messages for command failures
- [x] Add fallback for missing context metadata
- [x] Log errors with full context for debugging

**Expected Outcome**: Robust error handling that doesn't crash bot

### Task 5.2: Performance Optimization
- [x] Ensure context tracking doesn't add latency
- [x] Optimize command execution to be non-blocking
- [x] Add timeout handling for long-running commands

**Expected Outcome**: No performance degradation from new features

### Task 5.3: User Experience Refinements
- [x] Review and improve message formatting
- [x] Add help text for new commands
- [x] Ensure consistent emoji usage
- [ ] Test message clarity with users

**Expected Outcome**: Intuitive and user-friendly command interface

## Dependencies

- Phase 2 depends on Phase 1 (needs ContextTracker and utilities)
- Phase 3 depends on Phase 2 (needs command handlers)
- Phase 4 can run in parallel with Phase 3
- Phase 5 depends on Phase 4 (needs testing feedback)

## Estimated Effort

- Phase 1: 2-3 hours
- Phase 2: 2-3 hours
- Phase 3: 1-2 hours
- Phase 4: 2-3 hours
- Phase 5: 1-2 hours

**Total**: 8-13 hours
