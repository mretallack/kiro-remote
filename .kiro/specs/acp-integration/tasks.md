# ACP Integration Tasks

## Phase 1: Core ACP Infrastructure

### Task 1.1: Create ACPClient Base Class
- [x] Create `acp_client.py` module
- [x] Implement subprocess spawning for `kiro-cli acp`
- [x] Implement JSON-RPC message serialization/deserialization
- [x] Implement newline-delimited message reading from stdout
- [x] Implement newline-delimited message writing to stdin
- [x] Implement request ID generation and tracking
- [x] Implement response routing to pending requests
- [x] Implement notification routing to handlers

**Expected Outcome:** ACPClient can spawn kiro-cli acp and exchange JSON-RPC messages

**Dependencies:** None

**Resources:** 
- https://agentclientprotocol.com/protocol/transports
- https://www.jsonrpc.org/specification

### Task 1.2: Implement Initialize Method
- [x] Add `initialize()` method to ACPClient
- [x] Send initialize request with client capabilities
- [x] Parse initialize response with agent capabilities
- [x] Store agent capabilities for later use
- [x] Handle protocol version negotiation
- [x] Handle initialization errors

**Expected Outcome:** ACPClient can successfully initialize connection with kiro-cli acp

**Dependencies:** Task 1.1

**Resources:** https://kiro.dev/docs/cli/acp/#example-initialize-connection

### Task 1.3: Implement Session Management Methods
- [x] Add `create_session(cwd, mcp_servers)` method
- [x] Add `load_session(session_id)` method
- [x] Handle session creation response
- [x] Handle session load response
- [x] Store session IDs
- [x] Handle session errors

**Expected Outcome:** ACPClient can create and load sessions

**Dependencies:** Task 1.2

**Resources:** https://agentclientprotocol.com/protocol/session-setup

### Task 1.4: Implement Prompt Method
- [x] Add `send_prompt(session_id, content)` method
- [x] Format content array for text messages
- [x] Format content array for image messages
- [x] Send session/prompt request
- [x] Handle prompt response
- [x] Handle prompt errors

**Expected Outcome:** ACPClient can send prompts to kiro

**Dependencies:** Task 1.3

**Resources:** https://agentclientprotocol.com/protocol/prompt-turn

### Task 1.5: Implement Notification Handlers
- [x] Add notification callback registration
- [x] Route `session/update` notifications to handlers
- [x] Parse `AgentMessageChunk` updates
- [x] Parse `ToolCall` updates
- [x] Parse `ToolCallUpdate` updates
- [x] ~~Parse `TurnEnd` updates~~ (REMOVED - doesn't exist in ACP spec)
- [x] Handle unknown notification types gracefully
- [x] **BUG FIX:** Turn end is signaled by `session/prompt` response, not notification

**Expected Outcome:** ACPClient routes all notification types to registered handlers

**Dependencies:** Task 1.1

**Resources:** https://kiro.dev/docs/cli/acp/#session-updates

**Note:** The ACP spec does NOT include a `TurnEnd` notification. Turn completion is signaled by the response to `session/prompt` with a `stopReason` field.

### Task 1.6: Implement Cancellation
- [x] Add `cancel(session_id)` method
- [x] Send `session/cancel` notification
- [x] Handle cancellation in progress tracking
- [x] Test cancellation during tool execution

**Expected Outcome:** ACPClient can cancel ongoing operations

**Dependencies:** Task 1.4

**Resources:** https://agentclientprotocol.com/protocol/prompt-turn#cancellation

### Task 1.7: Implement Mode and Model Methods
- [x] Add `set_mode(session_id, mode)` method
- [x] Add `set_model(session_id, model)` method
- [x] Handle set_mode response
- [x] Handle set_model response
- [x] Handle mode/model errors

**Expected Outcome:** ACPClient can switch modes and models

**Dependencies:** Task 1.3

**Resources:** https://agentclientprotocol.com/protocol/session-modes

## Phase 2: Kiro Extensions (Optional)

### Task 2.1: Implement Slash Command Execution
- [x] Add `execute_command(session_id, command)` method
- [x] Send `_kiro.dev/commands/execute` request
- [x] Parse command execution response
- [x] Handle command errors
- [ ] Test with `/agent list`, `/context add`

**Expected Outcome:** ACPClient can execute slash commands

**Dependencies:** Task 1.3

**Resources:** https://kiro.dev/docs/cli/acp/#slash-commands

### Task 2.2: Handle Available Commands Notification
- [x] Register handler for `_kiro.dev/commands/available`
- [x] Parse available commands list
- [x] Store available commands
- [x] Expose available commands to bot

**Expected Outcome:** Bot knows which slash commands are available

**Dependencies:** Task 1.5

**Resources:** https://kiro.dev/docs/cli/acp/#slash-commands

### Task 2.3: Handle MCP Server Events
- [x] Register handler for `_kiro.dev/mcp/server_initialized`
- [x] Register handler for `_kiro.dev/mcp/oauth_request`
- [x] Log MCP server initialization
- [x] Log OAuth requests (for future implementation)

**Expected Outcome:** Bot receives MCP server events

**Dependencies:** Task 1.5

**Resources:** https://kiro.dev/docs/cli/acp/#mcp-server-events

### Task 2.4: Handle Context Management Events
- [x] Register handler for `_kiro.dev/compaction/status`
- [x] Register handler for `_kiro.dev/clear/status`
- [x] Log compaction progress
- [x] Log clear status

**Expected Outcome:** Bot receives context management events

**Dependencies:** Task 1.5

**Resources:** https://kiro.dev/docs/cli/acp/#session-management

## Phase 3: ACPSession Wrapper

### Task 3.1: Create ACPSession Class
- [x] Create `acp_session.py` module
- [x] Implement session initialization with ACPClient
- [x] Store session ID
- [x] Implement message chunk accumulation
- [x] Implement callback registration for events

**Expected Outcome:** ACPSession provides high-level session interface

**Dependencies:** Task 1.4, Task 1.5

### Task 3.2: Implement Message Sending
- [x] Add `send_message(text)` method
- [x] Add `send_image(path, caption)` method
- [x] Format text content
- [x] Format image content
- [x] Delegate to ACPClient.send_prompt()

**Expected Outcome:** ACPSession can send text and image messages

**Dependencies:** Task 3.1

### Task 3.3: Implement Event Callbacks
- [x] Add `on_chunk(callback)` method
- [x] Add `on_tool_call(callback)` method
- [x] Add `on_tool_update(callback)` method
- [x] Add `on_turn_end(callback)` method
- [x] Wire callbacks to ACPClient notifications

**Expected Outcome:** ACPSession provides typed event callbacks

**Dependencies:** Task 3.1

### Task 3.4: Implement Session Operations
- [x] Add `cancel()` method
- [x] Add `set_mode(mode)` method
- [x] Add `set_model(model)` method
- [x] Delegate to ACPClient methods

**Expected Outcome:** ACPSession provides session control methods

**Dependencies:** Task 3.1, Task 1.6, Task 1.7

## Phase 4: Bot Integration

### Task 4.1: Add ACP Detection
- [x] Create function to detect if kiro-cli supports ACP
- [x] Run `kiro-cli acp --help` and check exit code
- [x] Store ACP availability flag
- [x] Log ACP detection result

**Expected Outcome:** Bot knows if ACP is available

**Dependencies:** None

### Task 4.2: Create ACP-based AgentManager
- [x] Create `kiro_session_acp.py` module
- [x] Implement agent creation with ACPClient
- [x] Implement agent switching with new sessions
- [x] Implement agent deletion with session cleanup
- [x] Store session IDs per agent

**Expected Outcome:** AgentManager works with ACP

**Dependencies:** Task 3.4

### Task 4.3: Update Message Handler for ACP
- [x] Update message handler to use ACPSession
- [x] Accumulate chunks until TurnEnd
- [x] Send accumulated message to Telegram
- [x] Handle tool call notifications
- [x] Show tool execution status to user

**Expected Outcome:** Bot sends/receives messages via ACP

**Dependencies:** Task 4.2

### Task 4.4: Update Attachment Handler for ACP
- [x] Detect image vs document by extension
- [x] Use image content type for images
- [x] Use text with file path for documents
- [x] Test with JPEG, PNG, WebP
- [x] Test with Python, text, PDF files

**Expected Outcome:** Attachments work with ACP

**Dependencies:** Task 4.3

### Task 4.5: Update Cancel Command for ACP
- [x] Update `\cancel` handler to use ACPSession.cancel()
- [x] Remove Ctrl-C sending logic
- [x] Test cancellation during tool execution
- [x] Verify session remains usable after cancel

**Expected Outcome:** Cancel command works with ACP

**Dependencies:** Task 4.3

### Task 4.6: Update Conversation Persistence for ACP
- [x] Update save format to include session_id
- [x] Update load to use session/load method
- [x] Test save/load cycle
- [x] Verify conversation history restored correctly

**Expected Outcome:** Chat save/load works with ACP

**Dependencies:** Task 4.3

### Task 4.7: Add Real-time Progress Updates
- [x] Show typing indicator on AgentMessageChunk
- [x] Show tool execution status on ToolCall
- [x] Format tool names for display (e.g., "Running execute_bash...")
- [x] Update typing indicator on ToolCallUpdate
- [x] Clear typing indicator on TurnEnd

**Expected Outcome:** Users see real-time progress updates

**Dependencies:** Task 4.3

## Phase 5: Testing

### Task 5.1: Unit Tests for ACPClient
- [x] Test message serialization/deserialization
- [x] Test request ID generation
- [x] Test response routing
- [x] Test notification routing
- [x] Test error handling
- [x] Test subprocess lifecycle

**Expected Outcome:** ACPClient has comprehensive unit tests

**Dependencies:** Task 1.7

### Task 5.2: Integration Tests for Session Flow
- [x] Test initialize → create_session → send_prompt flow
- [x] Test session loading
- [x] Test cancellation
- [x] Test mode switching
- [x] Test model switching
- [x] Test error recovery

**Expected Outcome:** Full session lifecycle is tested

**Dependencies:** Task 3.4

### Task 5.3: Integration Tests for Bot
- [x] Test message sending/receiving
- [x] Test attachment handling (images and documents)
- [x] Test cancel command
- [x] Test agent switching
- [x] Test conversation save/load
- [x] Test real-time progress updates

**Expected Outcome:** Bot functionality is tested with ACP

**Dependencies:** Task 4.7

### Task 5.4: Compatibility Tests
- [x] Test with ACP-enabled kiro-cli
- [x] Test fallback detection
- [x] Test version negotiation
- [x] Test capability detection

**Expected Outcome:** ACP compatibility is verified

**Dependencies:** Task 4.1

## Phase 6: Documentation

### Task 6.1: Update README.md
- [x] Add "Real-time Progress Updates" section
- [x] Update "How It Works" section
- [x] Update "Advantages" section
- [x] Update "Bot Commands" section (note improved cancel)
- [x] Update "Attachment Support" section (note image content type)
- [x] Add optional commands section (model/mode switching)

**Expected Outcome:** README reflects ACP changes

**Dependencies:** Task 4.7

**Resources:** See design.md "Documentation Requirements" section

### Task 6.2: Update Code Comments
- [x] Add docstrings to ACPClient methods
- [x] Add docstrings to ACPSession methods
- [x] Add inline comments for complex logic
- [x] Document JSON-RPC message formats

**Expected Outcome:** Code is well-documented

**Dependencies:** Task 3.4

### Task 6.3: Create Migration Guide
- [x] Document ACP detection behavior
- [x] Document fallback mechanism (if implemented)
- [x] Document any breaking changes
- [x] Document new features

**Expected Outcome:** Users understand migration path

**Dependencies:** Task 6.1

## Phase 7: Deployment

### Task 7.1: Test on Development System
- [ ] Deploy to test environment
- [ ] Test with real Telegram bot
- [ ] Test all commands
- [ ] Test attachments
- [ ] Monitor logs for errors

**Expected Outcome:** Bot works in test environment

**Dependencies:** Task 5.3, Task 6.1

### Task 7.2: Monitor and Fix Issues
- [ ] Monitor bot logs
- [ ] Fix any discovered issues
- [ ] Test fixes
- [ ] Update documentation if needed

**Expected Outcome:** Bot is stable and reliable

**Dependencies:** Task 7.1

### Task 7.3: Deploy to Production
- [ ] Stop production bot service
- [ ] Pull latest code
- [ ] Restart bot service
- [ ] Monitor logs
- [ ] Test basic functionality

**Expected Outcome:** Bot is running in production with ACP

**Dependencies:** Task 7.2

## Optional: Fallback Implementation

### Task 8.1: Keep Text-based Implementation
- [ ] Preserve existing text-based code
- [ ] Add feature flag for ACP vs text mode
- [ ] Test both modes
- [ ] Document mode selection

**Expected Outcome:** Bot can fall back to text mode if ACP unavailable

**Dependencies:** Task 4.1

**Note:** Only implement if backward compatibility is required

## Summary

**Total Tasks:** 43 tasks across 8 phases
**Estimated Effort:** 
- Phase 1 (Core): High priority, ~2-3 days
- Phase 2 (Extensions): Medium priority, ~1 day
- Phase 3 (Session): High priority, ~1 day
- Phase 4 (Integration): High priority, ~2-3 days
- Phase 5 (Testing): High priority, ~1-2 days
- Phase 6 (Documentation): High priority, ~0.5 day
- Phase 7 (Deployment): High priority, ~0.5 day
- Phase 8 (Fallback): Low priority, optional

**Critical Path:** Phase 1 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
