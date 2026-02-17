# Restart Command Design

## Architecture Overview

The `\restart` command will restart the Kiro CLI engine process for the currently active agent while preserving agent selection and configuration.

**Restart Mechanism**: This design uses **process termination and respawn**, not an ACP protocol command. The ACP specification does not include a restart method - only session management methods like `session/new`, `session/load`, and `session/cancel`. Therefore, we terminate the existing `kiro-cli acp` subprocess and spawn a new one with the same configuration.

## Component Interactions

```
┌─────────────┐
│   Telegram  │
│     Bot     │
└──────┬──────┘
       │ \restart command
       ▼
┌─────────────────────────┐
│ handle_intercepted_     │
│      commands()         │
└──────┬──────────────────┘
       │ restart_agent()
       ▼
┌─────────────────────────┐
│  KiroSessionACP         │
│  - Queue restart msg    │
└──────┬──────────────────┘
       │ Worker thread
       ▼
┌─────────────────────────┐
│ _handle_restart()       │
│ 1. Get active agent     │
│ 2. Stop ACPClient       │
│ 3. Start new session    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│   ACPClient.close()     │
│   - Terminate process   │
│   - Wait/kill           │
└─────────────────────────┘
```

## Sequence Diagram

```
User          TelegramBot       KiroSessionACP      ACPClient       kiro-cli
 │                │                   │                 │               │
 │  \restart      │                   │                 │               │
 ├───────────────>│                   │                 │               │
 │                │                   │                 │               │
 │                │ queue restart msg │                 │               │
 │                ├──────────────────>│                 │               │
 │                │                   │                 │               │
 │  "🔄 Restarting..."                │                 │               │
 │<───────────────┤                   │                 │               │
 │                │                   │                 │               │
 │                │              [Worker Thread]        │               │
 │                │                   │                 │               │
 │                │                   │ close()         │               │
 │                │                   ├────────────────>│               │
 │                │                   │                 │ terminate()   │
 │                │                   │                 ├──────────────>│
 │                │                   │                 │               │
 │                │                   │                 │ wait(5s)      │
 │                │                   │                 │               │
 │                │                   │                 │ kill() if hung│
 │                │                   │                 ├──────────────>│
 │                │                   │                 │               │
 │                │                   │ start_session() │               │
 │                │                   ├─────────────────┤               │
 │                │                   │                 │ spawn new     │
 │                │                   │                 ├──────────────>│
 │                │                   │                 │               │
 │                │                   │ initialize()    │               │
 │                │                   ├────────────────>│               │
 │                │                   │                 │               │
 │  "✓ Restarted: agent_name"         │                 │               │
 │<───────────────┤                   │                 │               │
```

## Implementation Details

### 1. Command Interception (TelegramBot)

**Location**: `telegram_kiro_bot.py::handle_intercepted_commands()`

Add restart command handling:

```python
# Restart command
if normalized_text == "/restart":
    await self.restart_agent(update, context)
    return True
```

### 2. Restart Handler (TelegramBot)

**Location**: `telegram_kiro_bot.py` (new method)

```python
async def restart_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart the Kiro CLI engine for the active agent."""
    chat_id = update.effective_chat.id
    
    # Get current agent name before restart
    current_agent = self.kiro.active_agent
    
    if not current_agent:
        await update.message.reply_text("❌ No active agent to restart")
        return
    
    await update.message.reply_text(f"🔄 Restarting {current_agent}...")
    
    # Queue restart in worker thread
    self.kiro.restart_agent(chat_id)
```

### 3. Queue Restart Message (KiroSessionACP)

**Location**: `kiro_session_acp.py` (new method)

```python
def restart_agent(self, chat_id: int):
    """Restart the active agent (async-safe)."""
    self.message_queue.put({
        "type": "restart",
        "chat_id": chat_id
    })
```

### 4. Worker Thread Handler (KiroSessionACP)

**Location**: `kiro_session_acp.py::_worker_loop()`

Add case to handle restart:

```python
elif msg_type == "restart":
    self._handle_restart(msg)
```

### 5. Restart Implementation (KiroSessionACP)

**Location**: `kiro_session_acp.py` (new method)

```python
def _handle_restart(self, msg: Dict[str, Any]):
    """Handle restart request in worker thread."""
    chat_id = msg["chat_id"]
    
    if not self.active_agent or self.active_agent not in self.agents:
        self._send_error(chat_id, "No active agent to restart")
        return
    
    agent_name = self.active_agent
    agent_data = self.agents[agent_name]
    working_dir = agent_data["working_dir"]
    
    logger.info(f"Worker: Restarting agent {agent_name}")
    
    try:
        # 1. Stop existing session
        client = agent_data["client"]
        client.close()  # Terminates process, waits 5s, kills if needed
        
        # 2. Remove old agent data
        del self.agents[agent_name]
        
        # 3. Start new session with same config
        self._handle_start_session({
            "agent_name": agent_name,
            "working_dir": working_dir
        })
        
        # 4. Confirm success
        self._send_to_telegram_sync(chat_id, f"✓ Restarted: {agent_name}")
        logger.info(f"Worker: Successfully restarted {agent_name}")
        
    except Exception as e:
        logger.error(f"Worker: Error restarting agent: {e}")
        self._send_error(chat_id, f"Failed to restart: {str(e)}")
```

### 6. Enhanced Process Termination (ACPClient)

**Location**: `acp_client.py::close()`

Update to handle forceful kill:

```python
def close(self) -> None:
    """Close the connection and terminate subprocess."""
    self.running = False

    if self.process:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Process didn't terminate, killing forcefully")
            self.process.kill()
            self.process.wait()

    if self.reader_thread:
        self.reader_thread.join(timeout=5)

    logger.info("Closed ACP connection")
```

## Error Handling

### Scenario 1: No Active Agent
- **Detection**: Check `self.active_agent` is not None
- **Response**: Send error message "❌ No active agent to restart"

### Scenario 2: Process Won't Terminate
- **Detection**: `wait(timeout=5)` raises `TimeoutExpired`
- **Response**: Call `process.kill()` to force termination
- **Logging**: Log warning about forceful kill

### Scenario 3: New Session Fails to Start
- **Detection**: Exception in `_handle_start_session()`
- **Response**: Send error message with exception details
- **State**: Agent removed from `self.agents`, user must manually start

### Scenario 4: Restart During Active Operation
- **Handling**: `close()` terminates process regardless of state
- **Result**: Operation is cancelled, new session starts fresh

## State Management

### Before Restart
```python
self.agents = {
    "agent_name": {
        "client": <ACPClient>,
        "session": <ACPSession>,
        "session_id": "sess_abc123",
        "working_dir": "/path/to/project",
        "chunks": [...],
        "chat_id": 12345,
        "models": {...},
        "modes": {...}
    }
}
self.active_agent = "agent_name"
```

### During Restart
1. Store `agent_name` and `working_dir`
2. Call `client.close()` - terminates subprocess
3. Delete agent from `self.agents`
4. Call `_handle_start_session()` with stored config

### After Restart
```python
self.agents = {
    "agent_name": {
        "client": <NEW ACPClient>,
        "session": <NEW ACPSession>,
        "session_id": "sess_xyz789",  # NEW session ID
        "working_dir": "/path/to/project",  # SAME
        "chunks": [],  # FRESH
        "chat_id": None,  # RESET
        "models": {...},  # NEW from server
        "modes": {...}   # NEW from server
    }
}
self.active_agent = "agent_name"  # SAME
```

## User Experience

### Success Flow
```
User: \restart
Bot:  🔄 Restarting kiro_default...
      [2-5 seconds]
Bot:  ✓ Restarted: kiro_default
```

### Error Flow
```
User: \restart
Bot:  🔄 Restarting kiro_default...
      [timeout]
Bot:  ❌ Failed to restart: Connection timeout
```

## Testing Considerations

### Unit Tests
- Test restart with active agent
- Test restart with no active agent
- Test restart preserves agent name and working directory
- Test restart creates new session ID

### Integration Tests
- Test restart during idle state
- Test restart during active operation
- Test restart with hung process (mock timeout)
- Test restart followed by immediate message

### Manual Tests
- Restart after crash (simulate by killing kiro-cli)
- Restart during long-running operation
- Restart multiple times in succession
- Restart different agents

## Performance Considerations

- **Termination timeout**: 5 seconds before forceful kill
- **Total restart time**: ~5-10 seconds (terminate + spawn + initialize)
- **User feedback**: Immediate acknowledgment, completion notification
- **No blocking**: All operations in worker thread

## Security Considerations

- Only authorized user can restart (existing auth check)
- No arbitrary command execution
- Process cleanup prevents zombie processes
- Working directory preserved from agent config

## Future Enhancements (Out of Scope)

- Auto-restart on crash detection
- Restart all agents command
- Preserve conversation history across restarts
- Configurable restart behavior per agent
- Health check before restart
