# Telegram Kiro Bot

A Python service that bridges Telegram with Kiro CLI, maintaining persistent conversation context and providing agent management capabilities.

## ⚠️ Security Warning

**This bot runs Kiro CLI with full system permissions (`--trust-all-tools`).** Kiro can execute commands, modify files, and access your system resources. Only use this bot:
- On systems you control
- With trusted Telegram users (configure `authorized_user` in settings)
- When you understand the security implications

**The author is not responsible for any damage, data loss, or security issues that may occur from running this software on your system.** Use at your own risk.

## Features

- **Persistent Session**: Maintains a single Kiro CLI session across all messages
- **Agent Management**: Create, switch, and manage Kiro agents without CLI restarts
- **Conversation Persistence**: Save and restore conversation sessions
- **Attachment Support**: Send images and documents to Kiro for analysis
- **Auto Tool Trust**: Automatically trusts all tools to avoid prompts
- **Clean Output**: Strips ANSI escape codes for Telegram compatibility  
- **User Filtering**: Only responds to authorized user (configurable)
- **Error Handling**: Robust error handling and automatic recovery
- **Progress Updates**: Shows typing indicators during processing

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
2. Formats a message: `{your_caption}\n\nThe attachment is {file_path}`
3. Sends the message to Kiro CLI for processing
4. Kiro can read, analyze, or process the file as needed

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
\cancel               # Cancel the current running operation (sends Ctrl-C to Kiro)
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
  "timestamp": 1704067200.0,
  "conversation_history": [
    {"user": "message", "bot": "response", "timestamp": 1704067200.0}
  ],
  "working_directory": "/home/mark/git/remote-kiro"
}
```

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

1. **Persistent Kiro Session**: Starts `kiro-cli chat --trust-all-tools` once and keeps it running
2. **Threaded I/O**: Uses separate threads for input, output, and response processing
3. **Auto Tool Trust**: Automatically trusts all tools using `/tools trust-all` command and handles prompts
4. **Smart Response Buffering**: Accumulates output until prompt detected or timeout (3 seconds)
5. **Message Processing**: Sends user messages to Kiro, captures and buffers responses
6. **Output Cleaning**: Removes ANSI codes, filters prompts, and handles multi-line messages
7. **Timeout Handling**: Automatically sends buffered responses after inactivity
8. **Telegram Integration**: Uses python-telegram-bot library with thread-safe async messaging

## Advantages over shell2telegram

- **True Persistence**: Single Kiro session maintains full context
- **Better Performance**: No process startup overhead per message
- **Cleaner Output**: Proper ANSI stripping and response filtering
- **Error Recovery**: Handles timeouts and connection issues
- **Simpler Deployment**: Single Python file, easy to manage as service

## Logs

View logs with:
```bash
sudo journalctl -u telegram-kiro-bot -f
```
