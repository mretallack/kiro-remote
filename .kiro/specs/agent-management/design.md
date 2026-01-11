# Agent Management Feature Design

## Architecture Overview

Since kiro-cli cannot be modified, the agent management system is implemented entirely within the telegram bot code:
1. **Agent Creator** - Bot commands that create agent JSON files and restart kiro-cli
2. **Conversation Manager** - Bot-level conversation state persistence
3. **Bot Restart Handler** - Bot manages kiro-cli process lifecycle

## Component Design

### 1. Agent Creator (Bot Implementation)

**New Bot Commands:**
- `/create_agent <name>` - Bot-handled agent creation
- `/list_agents` - Bot lists available agents
- `/switch_agent <name>` - Bot restarts kiro-cli with new agent

**Agent Creation Flow:**
```
User: /create_agent my-agent
Bot: What's the agent description?
User: [description]
Bot: What instructions should it have?
User: [instructions]
Bot: Creating agent file...
Bot: Restarting kiro-cli with new agent...
Bot: Agent 'my-agent' is now active
```

**Implementation:**
- Bot creates JSON file in `~/.kiro/agents/<name>.json`
- Bot restarts kiro-cli process with `--agent my-agent`
- No kiro-cli modifications needed

### 2. Conversation Manager (Bot Implementation)

**Bot-Level State Management:**
- Bot maintains conversation history in memory
- Bot saves state to `~/.kiro/bot_conversations/<name>.json`
- Bot handles save/load without kiro-cli involvement

**Bot Commands:**
- `/save_chat <name>` - Bot saves current conversation
- `/load_chat <name>` - Bot restarts kiro-cli and replays conversation
- `/list_chats` - Bot lists saved conversations

**State Storage:**
```json
{
  "conversation_id": "uuid",
  "timestamp": "2026-01-11T17:50:00Z",
  "current_agent": "agent-name",
  "messages": [
    {"user": "message", "bot": "response"},
    ...
  ],
  "working_directory": "/path/to/dir"
}
```

### 3. Bot Restart Handler

**Startup Behavior:**
- On initial bot startup: Start kiro-cli (defaults to `kiro_default` agent)
- On agent switch: Restart kiro-cli with `--agent <name>` flag
- On bot restart: Check for `__auto_save__.json` to restore previous agent

**Restart Process:**
1. Bot kills current kiro-cli process
2. Bot saves current conversation state with active agent name
3. Bot starts new kiro-cli process (with agent if specified)
4. Bot optionally replays conversation history to restore context

**Agent State Persistence:**
```json
{
  "current_agent": "dicio" | "kiro_default" | "kiro_planner" | null,
  "messages": [...],
  "timestamp": "..."
}
```

**Implementation Details:**
- Bot tracks current active agent name
- Bot starts kiro-cli without --agent flag (uses `kiro_default`)
- Bot uses `--agent <name>` flag when switching to custom or built-in agents
- Bot restores last used agent on restart if auto-save exists

## Implementation Considerations

### Agent File Creation
- Bot creates standard kiro agent JSON files
- Bot validates JSON structure before writing
- Bot uses templates for common agent types

### Process Management
- Bot manages kiro-cli as subprocess
- Bot handles graceful shutdown and restart
- Bot monitors process health and auto-restarts if needed

### Conversation Replay
- Bot can replay conversation history to restore context
- Bot filters out bot-specific commands from replay
- Bot handles long conversations with chunking

## Error Handling

### Agent Creation Failures
- Bot validates agent name and configuration
- Bot provides clear error messages
- Bot rolls back partial agent creation on failure

### Process Restart Failures
- Bot implements retry logic for failed restarts
- Bot maintains backup conversation state
- Bot provides manual recovery options

### Conversation Restore Failures
- Bot handles corrupted state files gracefully
- Bot offers partial restore options
- Bot warns about potential context loss

## Integration Points

### Existing Bot Code
- Extend telegram bot command handlers
- Add process management to bot lifecycle
- Implement conversation state tracking

### File System
- Create agent files in `~/.kiro/agents/`
- Store conversation state in `~/.kiro/bot_conversations/`
- Handle file permissions and access errors

### Kiro CLI Process
- Start kiro-cli with `--agent <name>` parameter
- Monitor process output and health
- Handle process communication and shutdown

## Security Considerations

- Validate agent configurations to prevent code injection
- Sanitize user inputs in agent creation
- Restrict file system access to designated directories
- Encrypt sensitive conversation data if needed

## Performance Optimizations

- Lazy load agent configurations
- Compress conversation state files
- Implement conversation history pruning
- Cache frequently accessed agents

## Integration Points

### Existing Kiro CLI
- Extend command parser for new `/agent` and `/chat` commands
- Modify agent loading mechanism for hot-reload
- Add hooks for state save/restore

### Telegram Bot
- Add restart capability to bot process management
- Implement state preservation in bot lifecycle
- Handle long-running operations during restart

## File Structure

```
~/.kiro/
├── agents/
│   ├── my-agent.json          # Created by bot
│   └── another-agent.json     # Created by bot
└── bot_conversations/         # Bot-managed state
    ├── important-session.json
    ├── __auto_save__.json
    └── backup-*.json
```

## Sequence Diagrams

### Agent Creation Flow
```
User -> Bot: /create_agent my-agent
Bot -> User: What's the description?
User -> Bot: [description]
Bot -> User: What are the instructions?
User -> Bot: [instructions]
Bot -> FileSystem: Write ~/.kiro/agents/my-agent.json
Bot -> Process: Kill current kiro-cli
Bot -> Process: Start kiro-cli --agent my-agent
Bot -> User: Agent 'my-agent' is now active
```

### Bot Restart Flow
```
User -> Bot: /switch_agent other-agent
Bot -> FileSystem: Save conversation to ~/.kiro/bot_conversations/__auto_save__.json
Bot -> Process: Kill current kiro-cli
Bot -> Process: Start kiro-cli --agent other-agent
Bot -> Bot: Replay conversation history (optional)
Bot -> User: Switched to 'other-agent'
```
