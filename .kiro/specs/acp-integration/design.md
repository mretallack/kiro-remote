# ACP Integration Design

## Architecture Overview

The Telegram bot will transition from text-based subprocess communication to structured JSON-RPC communication using the Agent Client Protocol (ACP).

### Current Architecture

```
Telegram Bot
    ↓ (spawn subprocess)
kiro-cli chat --trust-all-tools
    ↓ stdin: plain text messages
    ↑ stdout: text with ANSI codes + prompts
    
Bot parses stdout with regex:
- Strip ANSI codes
- Detect prompts ("> ", "kiro> ")
- Buffer responses with timeout
- Handle tool trust prompts
```

### Proposed ACP Architecture

```
Telegram Bot (ACP Client)
    ↓ (spawn subprocess)
kiro-cli acp
    ↓ stdin: JSON-RPC requests (newline-delimited)
    ↑ stdout: JSON-RPC responses/notifications (newline-delimited)
    
Bot processes structured messages:
- session/update notifications (streaming chunks)
- ToolCall/ToolCallUpdate events
- TurnEnd signals
- No parsing needed
```

## Protocol Flow

### 1. Initialization

```
Bot → Kiro: initialize request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": 1,
    "clientCapabilities": {},
    "clientInfo": {
      "name": "telegram-kiro-bot",
      "version": "1.0.0"
    }
  }
}

Kiro → Bot: initialize response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": 1,
    "agentCapabilities": {
      "loadSession": true,
      "promptCapabilities": {"image": true}
    },
    "agentInfo": {
      "name": "kiro-cli",
      "version": "1.5.0"
    }
  }
}
```

### 2. Session Creation

```
Bot → Kiro: session/new request
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "session/new",
  "params": {
    "cwd": "/home/mark/git/remote-kiro",
    "mcpServers": []
  }
}

Kiro → Bot: session/new response
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "sessionId": "sess_abc123"
  }
}
```

### 3. Sending Prompts

```
Bot → Kiro: session/prompt request
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "session/prompt",
  "params": {
    "sessionId": "sess_abc123",
    "content": [
      {
        "type": "text",
        "text": "What files are in this directory?"
      }
    ]
  }
}

Kiro → Bot: session/update notifications (streaming)
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_abc123",
    "update": {
      "type": "ToolCall",
      "id": "tool_1",
      "name": "execute_bash",
      "parameters": {"command": "ls -la"},
      "status": "running"
    }
  }
}

{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_abc123",
    "update": {
      "type": "AgentMessageChunk",
      "content": "I'll list the files..."
    }
  }
}

{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_abc123",
    "update": {
      "type": "TurnEnd"
    }
  }
}

Kiro → Bot: session/prompt response
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "stopReason": "end_turn"
  }
}
```

### 4. Cancellation

```
Bot → Kiro: session/cancel notification
{
  "jsonrpc": "2.0",
  "method": "session/cancel",
  "params": {
    "sessionId": "sess_abc123"
  }
}
```

### 5. Session Loading

```
Bot → Kiro: session/load request
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "session/load",
  "params": {
    "sessionId": "sess_abc123"
  }
}

Kiro → Bot: session/load response
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "sessionId": "sess_abc123",
    "cwd": "/home/mark/git/remote-kiro"
  }
}
```

### 6. Mode Switching (Agent Swap)

```
Bot → Kiro: session/set_mode request
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "session/set_mode",
  "params": {
    "sessionId": "sess_abc123",
    "mode": "facebook_dev"
  }
}

Kiro → Bot: session/set_mode response
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {}
}
```

### 7. Model Selection

```
Bot → Kiro: session/set_model request
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "session/set_model",
  "params": {
    "sessionId": "sess_abc123",
    "model": "claude-3-5-sonnet-20241022"
  }
}

Kiro → Bot: session/set_model response
{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {}
}
```

### 8. Slash Command Execution (Kiro Extension)

```
Bot → Kiro: _kiro.dev/commands/execute request
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "_kiro.dev/commands/execute",
  "params": {
    "sessionId": "sess_abc123",
    "command": "/agent swap facebook_dev"
  }
}

Kiro → Bot: _kiro.dev/commands/execute response
{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "output": "Switched to agent: facebook_dev"
  }
}
```

### 9. Available Commands Notification (Kiro Extension)

```
Kiro → Bot: _kiro.dev/commands/available notification
{
  "jsonrpc": "2.0",
  "method": "_kiro.dev/commands/available",
  "params": {
    "sessionId": "sess_abc123",
    "commands": [
      {
        "name": "/agent",
        "description": "Manage agents",
        "subcommands": ["list", "swap", "create", "delete"]
      },
      {
        "name": "/context",
        "description": "Manage context",
        "subcommands": ["add", "remove", "list"]
      }
    ]
  }
}
```

### 10. Context Compaction Status (Kiro Extension)

```
Kiro → Bot: _kiro.dev/compaction/status notification
{
  "jsonrpc": "2.0",
  "method": "_kiro.dev/compaction/status",
  "params": {
    "sessionId": "sess_abc123",
    "status": "compacting",
    "progress": 0.5
  }
}
```

### 11. MCP Server Events (Kiro Extension)

```
Kiro → Bot: _kiro.dev/mcp/server_initialized notification
{
  "jsonrpc": "2.0",
  "method": "_kiro.dev/mcp/server_initialized",
  "params": {
    "sessionId": "sess_abc123",
    "serverName": "github",
    "tools": ["search_repos", "create_issue"]
  }
}

Kiro → Bot: _kiro.dev/mcp/oauth_request notification
{
  "jsonrpc": "2.0",
  "method": "_kiro.dev/mcp/oauth_request",
  "params": {
    "sessionId": "sess_abc123",
    "serverName": "github",
    "authUrl": "https://github.com/login/oauth/authorize?..."
  }
}
```

## Component Design

### ACPClient Class

Manages JSON-RPC communication with kiro-cli acp subprocess.

**Responsibilities:**
- Spawn `kiro-cli acp` subprocess
- Send JSON-RPC requests with unique IDs
- Receive and parse newline-delimited JSON messages
- Route responses to pending requests
- Route notifications to handlers
- Handle connection lifecycle

**Key Methods:**
```python
class ACPClient:
    def __init__(self, working_directory: str)
    def start() -> None
    def initialize() -> dict
    def create_session(cwd: str, mcp_servers: list = []) -> str  # returns session_id
    def load_session(session_id: str) -> dict
    def send_prompt(session_id: str, content: list) -> None
    def cancel(session_id: str) -> None
    def set_mode(session_id: str, mode: str) -> None
    def set_model(session_id: str, model: str) -> None
    def execute_command(session_id: str, command: str) -> dict  # Kiro extension
    def on_notification(callback: Callable) -> None
    def close() -> None
```

### ACPSession Class

Represents a single ACP session with kiro-cli.

**Responsibilities:**
- Track session ID
- Accumulate message chunks
- Emit events for tool calls and updates
- Signal turn completion
- Handle Kiro extension notifications

**Key Methods:**
```python
class ACPSession:
    def __init__(self, session_id: str, client: ACPClient)
    def send_message(text: str) -> None
    def send_image(path: str, caption: str = "") -> None
    def on_chunk(callback: Callable) -> None
    def on_tool_call(callback: Callable) -> None
    def on_tool_update(callback: Callable) -> None
    def on_turn_end(callback: Callable) -> None
    def on_commands_available(callback: Callable) -> None
    def on_compaction_status(callback: Callable) -> None
    def on_mcp_event(callback: Callable) -> None
    def cancel() -> None
    def set_mode(mode: str) -> None
    def set_model(model: str) -> None
```

### AgentManager Integration

Update AgentManager to use ACP instead of text-based communication.

**Changes:**
- Replace `KiroProcess` with `ACPClient`
- Store session IDs instead of parsing state
- Remove ANSI stripping and prompt detection
- Remove response buffering logic

### Conversation Persistence

Update conversation save/load to use ACP session IDs.

**Current Format:**
```json
{
  "current_agent": "agent_name",
  "timestamp": 1704067200.0,
  "conversation_history": [...],
  "working_directory": "/path"
}
```

**New Format:**
```json
{
  "current_agent": "agent_name",
  "timestamp": 1704067200.0,
  "session_id": "sess_abc123",
  "working_directory": "/path"
}
```

## Benefits Analysis

### Code Simplification

**Removed Code:**
- ANSI escape code stripping (~50 lines)
- Prompt detection regex (~30 lines)
- Response buffering with timeout (~80 lines)
- Tool trust prompt handling (~40 lines)
- Output parsing state machine (~100 lines)

**Total Reduction:** ~300 lines of fragile parsing logic

### Reliability Improvements

**Current Issues:**
- Prompt detection fails if kiro changes prompt format
- ANSI codes occasionally leak through
- Timeout logic causes premature message sends
- Tool trust prompts sometimes missed

**ACP Solutions:**
- Structured events eliminate parsing
- No ANSI codes in JSON
- TurnEnd signal eliminates timeouts
- Tool calls are explicit events

### New Capabilities

**Real-time Progress:**
- Show tool names and status to users
- Display "Kiro is running execute_bash..." messages
- Update typing indicator based on tool execution
- Show tool call parameters and results

**Better Session Management:**
- Explicit session IDs for persistence
- Reliable session restoration via `session/load`
- Multiple concurrent sessions per agent
- Sessions persisted to `~/.kiro/sessions/cli/`

**Proper Cancellation:**
- Send structured cancel request via `session/cancel`
- No need to send Ctrl-C to stdin

**Mode and Model Control:**
- Switch agent modes via `session/set_mode`
- Change models via `session/set_model`
- Dynamic agent configuration

**Slash Command Integration:**
- Execute slash commands via `_kiro.dev/commands/execute`
- Receive available commands via `_kiro.dev/commands/available`
- Get command autocomplete via `_kiro.dev/commands/options`

**MCP Server Support:**
- Receive MCP server initialization events
- Handle OAuth requests for MCP servers
- Pass MCP servers to session creation

**Context Management:**
- Monitor compaction status via `_kiro.dev/compaction/status`
- Track context clearing via `_kiro.dev/clear/status`

## Implementation Considerations

### Error Handling

**JSON-RPC Errors:**
- Parse errors (invalid JSON)
- Method not found
- Invalid params
- Internal errors

**Strategy:**
- Log all errors
- Report user-friendly messages to Telegram
- Attempt recovery or restart subprocess

### Backward Compatibility

**Detection:**
```python
def supports_acp() -> bool:
    result = subprocess.run(
        ["kiro-cli", "acp", "--help"],
        capture_output=True
    )
    return result.returncode == 0
```

**Fallback:**
- Keep existing text-based implementation
- Use ACP if available, otherwise fall back
- Eventually deprecate text mode

### Threading Model

**Current:**
- Input thread (sends to stdin)
- Output thread (reads from stdout)
- Response thread (buffers and sends to Telegram)

**ACP:**
- Input thread (sends JSON-RPC requests)
- Output thread (reads JSON-RPC messages, routes to handlers)
- Notification handlers run in output thread
- Response futures resolved in output thread

### Message Buffering

**Current:** Buffer text until timeout or prompt detected

**ACP:** Accumulate `AgentMessageChunk` notifications until `TurnEnd`

### Attachment Support

**Current:** Send file path as text in message

**ACP:** Use structured content with image type
```json
{
  "type": "image",
  "source": {
    "type": "file",
    "path": "/path/to/image.jpg"
  }
}
```

Kiro advertises `promptCapabilities.image: true` during initialization.

### Logging and Debugging

**ACP Logs:** Written to `$XDG_RUNTIME_DIR/kiro-log/kiro-chat.log` on Linux

**Environment Variables:**
```bash
KIRO_LOG_LEVEL=debug  # Control verbosity
KIRO_CHAT_LOG_FILE=/custom/path.log  # Custom log location
```

**Bot Integration:**
- Set `KIRO_LOG_LEVEL=debug` when spawning `kiro-cli acp`
- Monitor log file for debugging ACP communication
- Parse stderr for additional logging output

## Testing Strategy

### Unit Tests
- ACPClient message serialization/deserialization
- Session state management
- Notification routing
- Error handling
- Request ID generation and tracking

### Integration Tests
- Full initialization flow
- Session creation and loading
- Prompt/response cycle with streaming
- Cancellation
- Multi-session management
- Mode and model switching
- Slash command execution
- MCP server event handling

### Compatibility Tests
- Test with ACP-enabled kiro-cli
- Test fallback with old kiro-cli
- Test version negotiation
- Test capability detection

### Kiro Extension Tests
- Available commands notification
- Command execution
- Compaction status tracking
- MCP OAuth flow
- Session termination

## Migration Path

### Phase 1: Parallel Implementation
- Implement ACP client alongside existing code
- Add feature flag to enable ACP mode
- Test with subset of users

### Phase 2: Default to ACP
- Make ACP the default if available
- Keep text mode as fallback
- Monitor for issues

### Phase 3: Deprecation
- Remove text-based implementation
- Require ACP-capable kiro-cli
- Update documentation

## Open Questions

1. **Session Persistence:** Does kiro-cli persist sessions to disk automatically, or do we need to manage this?
   - ✅ **Answer:** Yes, sessions are persisted to `~/.kiro/sessions/cli/` with two files per session:
     - `<session-id>.json` - Session metadata and state
     - `<session-id>.jsonl` - Event log (conversation history)

2. **Multi-Agent Sessions:** Can we have multiple ACP sessions in a single kiro-cli process, or do we need separate processes per agent?
   - ❓ **Need to test:** Likely need separate processes per agent for isolation

3. **Attachment Handling:** Does ACP support image content in prompts?
   - ✅ **Answer:** Yes, `promptCapabilities.image: true` indicates support

4. **Tool Trust:** How does ACP handle tool trust? Is `--trust-all-tools` still needed?
   - ❓ **Need to investigate:** May need to handle `session/request_permission` callbacks or pass trust settings during session creation

5. **Working Directory:** Can we change working directory per session, or is it per process?
   - ✅ **Answer:** Set via `cwd` parameter in `session/new`

6. **Agent Mode Mapping:** How do Kiro's agent modes map to our custom agents?
   - ❓ **Need to investigate:** Does `session/set_mode` work with custom agent names, or do we need to use slash commands?

7. **Slash Command vs Native Methods:** Should we use `_kiro.dev/commands/execute` for agent swapping, or `session/set_mode`?
   - ❓ **Need to test:** Determine which approach provides better control and error handling

8. **MCP Server Configuration:** How do we pass MCP server configurations to sessions?
   - ✅ **Answer:** Via `mcpServers` parameter in `session/new` (empty array `[]` for none)

9. **Session Restoration:** When loading a session, does it restore the full conversation context?
   - ❓ **Need to test:** Verify that `session/load` restores all conversation history and state

## Conclusion

ACP provides significant benefits:
- **Simplification:** Removes ~300 lines of parsing code
- **Reliability:** Eliminates fragile text parsing
- **Features:** Enables real-time progress updates, mode switching, model selection
- **Maintainability:** Structured protocol is easier to debug
- **Extensibility:** Kiro extensions provide slash commands, MCP integration, context management
- **Session Management:** Built-in persistence to `~/.kiro/sessions/cli/`
- **Logging:** Standardized logging to `$XDG_RUNTIME_DIR/kiro-log/kiro-chat.log`

**Recommendation:** Implement ACP support with fallback to text mode for backward compatibility.

### Key Implementation Priorities

1. **Core ACP Protocol:** Initialize, session/new, session/prompt, session/cancel
2. **Session Persistence:** Use session IDs for save/load functionality
3. **Streaming Updates:** Handle AgentMessageChunk, ToolCall, ToolCallUpdate, TurnEnd
4. **Mode Management:** Use session/set_mode or slash commands for agent switching
5. **Kiro Extensions:** Leverage available commands, compaction status, MCP events
6. **Logging:** Configure KIRO_LOG_LEVEL for debugging
7. **Backward Compatibility:** Detect ACP support and fallback gracefully
