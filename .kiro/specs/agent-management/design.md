# Agent Management Feature Design

## Architecture Overview

The agent management system intercepts Kiro's native commands within the telegram bot, handling them without passing to kiro-cli:
1. **Command Interceptor** - Bot intercepts `/agent` and `/chat` commands before they reach kiro-cli
2. **Agent Manager** - Bot handles agent creation, listing, and switching
3. **Conversation Manager** - Bot-level conversation state persistence
4. **Bot Restart Handler** - Bot manages kiro-cli process lifecycle

## Component Design

### 1. Command Interceptor

**Intercepted Commands:**
- `/agent create <name>` or `\agent create <name>` - Bot handles agent creation
- `/agent list` or `\agent list` - Bot lists available agents  
- `/agent swap <name>` or `\agent swap <name>` - Bot switches agents
- `/agent delete <name>` or `\agent delete <name>` - Bot removes agents
- `/chat save <name>` or `\chat save <name>` - Bot saves conversation
- `/chat load <name>` or `\chat load <name>` - Bot loads conversation
- `/chat list` or `\chat list` - Bot lists saved conversations

**Interception Flow:**
```
User: /agent create my-agent  (or \agent create my-agent)
Bot: [Intercepts command, doesn't pass to kiro-cli]
Bot: What's the agent description?
User: [description]
Bot: What instructions should it have?
User: [instructions]
Bot: Creating agent file...
Bot: Restarting kiro-cli with new agent...
Bot: Agent 'my-agent' is now active
```

### 2. Agent Manager (Bot Implementation)

**Agent Creation Flow:**
- Bot intercepts `/agent create <name>`
- Bot prompts for description and instructions via Telegram
- Bot creates JSON file in `~/.kiro/agents/<name>.json`
- Bot restarts kiro-cli process with `--agent <name>`

**Agent Operations:**
- `/agent list` - Bot reads from `~/.kiro/agents/` and shows built-in + custom agents
- `/agent swap <name>` - Bot restarts kiro-cli with new agent
- `/agent delete <name>` - Bot removes agent file and confirms deletion

**Implementation:**
- Bot maintains list of built-in agents: `kiro_default`, `kiro_planner`, `dicio`
- Bot scans `~/.kiro/agents/` for custom agents
- Bot validates agent names and configurations

### 3. Conversation Manager (Bot Implementation)

**Intercepted Chat Commands:**
- `/chat save <name>` - Bot saves current conversation state
- `/chat load <name>` - Bot restarts kiro-cli and replays conversation  
- `/chat list` - Bot lists saved conversations

**Bot-Level State Management:**
- Bot maintains conversation history in memory
- Bot saves state to `~/.kiro/bot_conversations/<name>.json`
- Bot handles save/load without kiro-cli involvement

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

### 4. Bot Restart Handler

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

## Command Interception Logic

### Message Processing Flow
```
1. User sends message to bot
2. Bot checks if message starts with intercepted commands:
   - /agent create|list|swap|delete or \agent create|list|swap|delete
   - /chat save|load|list or \chat save|load|list
3. If intercepted: Bot handles internally, doesn't pass to kiro-cli
4. If not intercepted: Bot passes message to kiro-cli as normal
```

### Interception Implementation
- Bot maintains list of intercepted command patterns for both "/" and "\" prefixes
- Bot uses regex matching to identify commands with either prefix
- Bot normalizes "\" to "/" internally for consistent processing
- Bot extracts command parameters for processing
- Bot provides appropriate responses without kiro-cli involvement

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
User -> Bot: /agent create my-agent
Bot -> Bot: [Intercepts command]
Bot -> User: What's the description?
User -> Bot: [description]
Bot -> User: What are the instructions?
User -> Bot: [instructions]
Bot -> FileSystem: Write ~/.kiro/agents/my-agent.json
Bot -> Process: Kill current kiro-cli
Bot -> Process: Start kiro-cli --agent my-agent
Bot -> User: Agent 'my-agent' is now active
```

### Command Interception Flow
```
User -> Bot: /agent list  (or \agent list)
Bot -> Bot: [Intercepts command, doesn't pass to kiro-cli]
Bot -> FileSystem: Read ~/.kiro/agents/
Bot -> Bot: Combine with built-in agents list
Bot -> User: Available agents: kiro_default, kiro_planner, dicio, my-agent, other-agent
```

### Bot Restart Flow
```
User -> Bot: /agent swap other-agent  (or \agent swap other-agent)
Bot -> Bot: [Intercepts command]
Bot -> FileSystem: Save conversation to ~/.kiro/bot_conversations/__auto_save__.json
Bot -> Process: Kill current kiro-cli
Bot -> Process: Start kiro-cli --agent other-agent
Bot -> Bot: Replay conversation history (optional)
Bot -> User: Switched to 'other-agent'
```
