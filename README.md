# Telegram Kiro Bot

A Python service that bridges Telegram with Kiro CLI, maintaining persistent conversation context and providing agent management capabilities.

## ⚠️ Security Warning

**This bot automatically approves tool execution requests from Kiro.** Kiro can execute commands, modify files, and access your system resources. Only use this bot:
- On systems you control
- With trusted Telegram users (configure `authorized_user` in settings)
- When you understand the security implications

**The author is not responsible for any damage, data loss, or security issues that may occur from running this software on your system.** Use at your own risk.

## Features

- **Persistent Session**: Maintains Kiro CLI sessions with structured communication
- **Agent Management**: Create, switch, and manage Kiro agents with isolated contexts
- **Conversation Persistence**: Save and restore conversation sessions with session IDs
- **Attachment Support**: Send images (native ACP support) and documents to Kiro
- **Real-time Progress**: See tool execution status as Kiro works
- **Clean Communication**: Structured JSON-RPC protocol (no ANSI parsing needed)
- **User Filtering**: Only responds to authorized user (configurable)
- **Error Handling**: Robust error handling and automatic recovery
- **Fast Cancellation**: Immediate response to cancel commands

## Real-time Progress Updates

The bot shows what Kiro is doing in real-time:
- **Tool Execution**: "🔧 Execute Bash..." when running commands
- **File Operations**: "🔧 Fs Read..." when reading files
- **Progress Indicators**: Typing indicators during long operations

This helps you understand what Kiro is working on during longer tasks.

## Attachment Support

Send images and documents directly to Kiro for analysis, code review, or processing.

### Supported File Types
- **Photos**: JPEG, PNG, WebP (up to 10 MB)
- **Documents**: Any file type (up to 20 MB)

### Usage
Simply send a photo or document to the bot with an optional caption:
```
[Send image with caption: "What's in this image?"]
[Send Python file with caption: "Review this code"]
[Send document without caption - Kiro will receive the file path]
```

### Configuration
Set the attachments directory in `settings.ini`:
```ini
[bot]
attachments_dir = ~/.kiro/bot_attachments
```

Files are saved with the pattern: `{timestamp}_{user_id}_{filename}`

### How It Works
1. Bot downloads the attachment to the configured directory
2. For images: Sends via ACP's native image content type
3. For documents: Includes file path in message text
4. Kiro can read, analyze, or process the file as needed

**Note**: Image attachments use ACP's native image content type for better integration.

## Bot Commands

**Note:** Telegram bot commands use backslash (`\`) prefix, not forward slash (`/`).

### Managing Agents
```
\agent list           # List all available agents with their working directories
\agent swap <name>    # Switch to a different agent
\agent create <name>  # Create a new agent (interactive flow)
\agent delete <name>  # Delete an existing agent
```

### Conversation Management
```
\chat save <name>     # Save current conversation state
\chat load <name>     # Load and restore a saved conversation
\chat list            # List all saved conversations
```

### Operation Control
```
\cancel               # Cancel the current running operation (immediate response)
```

### Configuring Agent Working Directories

Each agent can be configured to start in a specific project directory. Edit `~/.kiro/bot_agent_config.json`:

```json
{
  "agents": {
    "facebook_dev": {
      "working_directory": "/home/mark/git/facebook"
    },
    "kiro_default": {
      "working_directory": "/home/mark/git/remote-kiro"
    }
  },
  "default_directory": "/home/mark/git/remote-kiro"
}
```

When you switch to an agent, Kiro will start in that agent's configured directory. This allows different agents to work on different projects without manual directory changes.

## How Multi-Agent System Works

The bot maintains multiple Kiro CLI processes simultaneously, one for each agent:

1. **Independent Sessions**: Each agent runs in its own Kiro CLI process with separate context
2. **Agent Switching**: Use `\agent swap <name>` to switch between active agents
3. **Lazy Loading**: Agent processes are only started when first accessed
4. **Working Directories**: Each agent starts in its configured project directory
5. **Context Isolation**: Conversations and context are isolated per agent
6. **Concurrent Agents**: Multiple agents can be running simultaneously, but only one is active at a time

### Agent Lifecycle
- **Creation**: `\agent create <name>` - Interactive flow to define agent properties
- **Activation**: First message to an agent or `\agent swap` starts its Kiro process
- **Switching**: `\agent swap <name>` switches active agent without stopping others
- **Deletion**: `\agent delete <name>` removes agent definition (stops process if running)

### Use Cases
- **Project Separation**: Different agents for different codebases (e.g., `facebook_dev`, `kiro_default`)
- **Role Specialization**: Agents with different instructions for specific tasks
- **Context Management**: Keep separate conversation contexts for different projects



## Agent File Structure

Custom agents are stored as JSON files in `~/.kiro/agents/`:
```json
{
  "name": "agent_name",
  "description": "Agent description",
  "instructions": "System instructions for the agent",
  "tools": [],
  "created_at": 1704067200.0,
  "version": "1.0"
}
```

## Conversation State Structure

Conversation states are stored in `~/.kiro/bot_conversations/`:
```json
{
  "current_agent": "agent_name",
  "session_id": "sess_abc123",
  "timestamp": 1704067200.0,
  "working_directory": "/home/mark/git/remote-kiro"
}
```

Sessions are automatically persisted by kiro-cli to `~/.kiro/sessions/cli/`.

## Setup

1. Copy settings template and configure:
```bash
cp settings.ini.template settings.ini
# Edit settings.ini with your bot token and authorized user
```

2. Setup and run:
```bash
# Setup virtual environment and run tests
make setup
make test

# Run the bot
make run
```

## Running as a Service

```bash
# Install and start service
make install
make service-start

# Check status and logs
make service-status
make service-logs

# Stop service
make service-stop
```

## How It Works

1. **Persistent Kiro Session**: Starts `kiro-cli acp` and maintains JSON-RPC communication
2. **Structured Protocol**: Uses Agent Client Protocol (ACP) for reliable message exchange
3. **Permission Handling**: Automatically approves tool execution requests via ACP protocol
4. **Session Management**: Explicit session IDs for save/load functionality
5. **Streaming Updates**: Receives real-time notifications for tool calls and progress
6. **Smart Response Buffering**: Accumulates message chunks until turn completion
7. **Message Processing**: Sends user messages via JSON-RPC, receives structured responses
8. **Queue-Based Architecture**: Async Telegram layer communicates with sync Kiro via message queue
9. **Telegram Integration**: Uses python-telegram-bot library with thread-safe async messaging

## Advantages over Text-Based Communication

- **True Persistence**: Single Kiro session maintains full context
- **Better Performance**: No process startup overhead per message
- **Structured Communication**: JSON-RPC eliminates text parsing and ANSI stripping
- **Real-time Progress**: See tool execution status as it happens
- **Reliable Cancellation**: Proper cancel mechanism via protocol
- **Error Recovery**: Handles timeouts and connection issues gracefully
- **Session Persistence**: Built-in session management with automatic persistence
- **Simpler Deployment**: Single Python file, easy to manage as service

## Logs

View logs with:
```bash
sudo journalctl -u telegram-kiro-bot -f
```
