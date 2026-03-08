# Context Management via ACP - Design

## Architecture Overview

The context management feature extends the Telegram bot to track and manage Kiro CLI context usage through the ACP protocol. It leverages existing ACP mechanisms:

1. **Metadata notifications** - Track context usage via `_kiro.dev/metadata` notifications
2. **Command execution** - Execute slash commands via `_kiro.dev/commands/execute` RPC method
3. **Compaction status** - Monitor compaction via `_kiro.dev/compaction/status` notifications

## Component Design

### 1. Context Tracker

**Purpose**: Track and store context usage per session

**Implementation**:
```python
class ContextTracker:
    def __init__(self):
        self.usage_by_session = {}  # session_id -> percentage
        
    def update_usage(self, session_id: str, percentage: float):
        self.usage_by_session[session_id] = percentage
        
    def get_usage(self, session_id: str) -> Optional[float]:
        return self.usage_by_session.get(session_id)
```

**Integration Point**: Hook into existing `_kiro.dev/metadata` notification handler in `acp_session.py`

### 2. Command Executor

**Existing Support**: `ACPClient.execute_command()` already exists, uses `_kiro.dev/commands/execute`

### 3. Bot Command Handlers

**New Commands**:
- `\context` - Show current context usage
- `\context show` - Execute `/context show`
- `\context clear` - Execute `/context clear`
- `\compact` - Execute `/compact`

**Implementation Location**: `kiro_session_acp.py` in `_handle_bot_command()`

## Sequence Diagrams

### Context Usage Tracking

```
User -> Kiro CLI: Send message
Kiro CLI -> Bot: _kiro.dev/metadata (contextUsagePercentage: 64.7)
Bot -> ContextTracker: update_usage(session_id, 64.7)
Bot -> User: [Optional warning if > 80%]
```

### Manual Compaction

```
User -> Bot: \compact
Bot -> ACPClient: execute_command(session_id, "/compact")
ACPClient -> Kiro CLI: _kiro.dev/commands/execute {command: "/compact"}
Kiro CLI -> Bot: Result
Bot -> User: "🔄 Compacting conversation..."
Kiro CLI -> Bot: _kiro.dev/compaction/status {status: "complete"}
Bot -> User: "✅ Compaction complete"
```

## Data Structures

### Metadata Notification
```json
{
  "jsonrpc": "2.0",
  "method": "_kiro.dev/metadata",
  "params": {
    "sessionId": "51107f87-9ac7-4f97-ae3c-9280f3d971e1",
    "contextUsagePercentage": 64.67
  }
}
```

### Command Execution Request
```json
{
  "jsonrpc": "2.0",
  "method": "_kiro.dev/commands/execute",
  "params": {
    "sessionId": "51107f87-9ac7-4f97-ae3c-9280f3d971e1",
    "command": "/compact"
  },
  "id": 123
}
```

## Implementation Considerations

### 1. Context Usage Storage
- Store in `KiroSessionACP` instance (per-agent)
- No persistence needed
- Reset on agent swap

### 2. Warning Throttling
- Track last warning time per session
- Only warn once per threshold crossing
- Reset after compaction

### 3. Command Output Formatting
- Strip ANSI codes before sending to Telegram
- Truncate if exceeds 4096 chars

### 4. Error Handling
- Command failures should not crash bot
- Display user-friendly error messages
- Log full errors for debugging

### 5. Compaction Status Tracking
- Use existing `on_compaction_status()` callback
- Display status updates in real-time

## Dependencies

### Existing Components
- `ACPClient.execute_command()` - Already implemented
- `ACPSession.on_compaction_status()` - Already implemented
- `_kiro.dev/metadata` notifications - Already received

### New Components
- `ContextTracker` class
- New bot command handlers
- ANSI stripping utility

## Risks and Mitigations

**Risk**: Command output too large  
**Mitigation**: Truncate to 4000 chars

**Risk**: Kiro CLI version compatibility  
**Mitigation**: Gracefully handle missing command support

**Risk**: Context metadata not available  
**Mitigation**: Show "Unknown" status
