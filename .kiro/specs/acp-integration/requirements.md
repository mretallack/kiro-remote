# ACP Integration Requirements

## Overview

Evaluate whether Agent Client Protocol (ACP) can simplify the Telegram bot's interface with kiro-cli by replacing the current subprocess stdin/stdout text parsing approach with a structured JSON-RPC protocol.

## Current State

The Telegram bot currently:
- Spawns `kiro-cli chat --trust-all-tools` as a subprocess
- Sends messages via stdin as plain text
- Parses stdout using regex patterns to detect prompts and responses
- Strips ANSI escape codes manually
- Implements custom timeout logic for response buffering
- Handles tool trust prompts through text pattern matching

## User Stories

### US-1: Structured Communication
**AS A** bot developer  
**I WANT** structured JSON-RPC communication with kiro-cli  
**SO THAT** I can avoid fragile text parsing and ANSI code stripping

**Acceptance Criteria:**
- WHEN the bot sends a message to kiro-cli THEN it uses JSON-RPC format
- WHEN kiro-cli responds THEN the response is structured JSON
- WHEN tool calls occur THEN they are reported as structured events

### US-2: Session Management
**AS A** bot developer  
**I WANT** explicit session lifecycle management  
**SO THAT** I can reliably create, persist, and restore conversation sessions

**Acceptance Criteria:**
- WHEN the bot starts THEN it can create a new ACP session
- WHEN a user saves a conversation THEN the session ID is persisted
- WHEN a user loads a conversation THEN the session is restored via `session/load`
- WHEN the bot restarts THEN existing sessions can be resumed

### US-3: Real-time Progress Updates
**AS A** bot user  
**I WANT** to see what kiro is doing in real-time  
**SO THAT** I understand the agent's progress on long-running tasks

**Acceptance Criteria:**
- WHEN kiro executes a tool THEN the bot receives `ToolCall` notifications
- WHEN a tool is running THEN the bot receives `ToolCallUpdate` notifications
- WHEN kiro streams a response THEN the bot receives `AgentMessageChunk` notifications
- WHEN a turn completes THEN the bot receives a `TurnEnd` notification

### US-4: Multi-Agent Support
**AS A** bot user  
**I WANT** to switch between different agents  
**SO THAT** I can work on different projects with isolated contexts

**Acceptance Criteria:**
- WHEN the user runs `\agent swap <name>` THEN a new ACP session is created with the agent's working directory
- WHEN multiple agents exist THEN each has an independent ACP session
- WHEN switching agents THEN the previous session remains available
- WHEN an agent is deleted THEN its ACP session is terminated

### US-5: Cancellation Support
**AS A** bot user  
**I WANT** to cancel long-running operations  
**SO THAT** I can interrupt kiro when needed

**Acceptance Criteria:**
- WHEN the user runs `\cancel` THEN the bot sends `session/cancel` notification
- WHEN cancellation occurs THEN kiro stops the current operation
- WHEN cancellation completes THEN the session remains usable

### US-6: Backward Compatibility
**AS A** bot operator  
**I WANT** the bot to work with both old and new kiro-cli versions  
**SO THAT** I can upgrade incrementally

**Acceptance Criteria:**
- WHEN kiro-cli supports ACP THEN the bot uses ACP mode
- WHEN kiro-cli doesn't support ACP THEN the bot falls back to text mode
- WHEN switching modes THEN existing functionality is preserved

## Technical Requirements

### TR-1: Protocol Compliance
WHEN the bot communicates via ACP THE SYSTEM SHALL follow JSON-RPC 2.0 specification

### TR-2: Transport Layer
WHEN the bot spawns kiro-cli THE SYSTEM SHALL use stdio transport with newline-delimited JSON messages

### TR-3: Capability Negotiation
WHEN establishing connection THE SYSTEM SHALL exchange capabilities via `initialize` method

### TR-4: Error Handling
WHEN JSON-RPC errors occur THE SYSTEM SHALL handle them gracefully and report to user

### TR-5: Session Persistence
WHEN sessions are saved THE SYSTEM SHALL store session IDs for later restoration

### TR-6: Logging
WHEN ACP communication occurs THE SYSTEM SHALL log messages for debugging

## Non-Functional Requirements

### NFR-1: Performance
WHEN using ACP THE SYSTEM SHALL respond no slower than current text-based approach

### NFR-2: Reliability
WHEN using ACP THE SYSTEM SHALL maintain 99.9% message delivery success rate

### NFR-3: Maintainability
WHEN using ACP THE SYSTEM SHALL reduce code complexity compared to text parsing

## Out of Scope

- HTTP transport (stdio only for now)
- Custom ACP extensions beyond kiro's built-in extensions
- File system operations (fs/read_text_file, fs/write_text_file)
- Terminal operations (terminal/create, etc.)
- Slash command execution via `_kiro.dev/commands/execute`

## Success Metrics

1. **Code Reduction**: Remove ANSI stripping, prompt detection, and response buffering logic
2. **Reliability**: Eliminate parsing errors and timeout issues
3. **Feature Parity**: All current bot features work via ACP
4. **User Experience**: Users see real-time progress updates during tool execution
