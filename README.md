# Telegram Kiro Bot

A Python service that bridges Telegram with Kiro CLI, maintaining persistent conversation context and providing agent management capabilities.

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

## Agent Management Commands

### Creating Agents
```
/agent create <name>
```
Interactively create a new global agent. The bot will prompt for:
- Agent description
- Agent instructions

Example:
```
/agent create my_helper
> Creating agent 'my_helper'...
> What's the agent description?
A helpful coding assistant
> What instructions should the agent have?  
You are a helpful coding assistant focused on Python development.
> ✅ Agent 'my_helper' created successfully!
```

### Managing Agents
```
/agent list           # List all available agents (built-in + custom)
/agent swap <name>    # Switch to a different agent
```

### Conversation Management
```
/save_chat <name>     # Save current conversation state
/load_chat <name>     # Load and restore a saved conversation
/list_chats           # List all saved conversations
```

## How Agent Management Works

1. **Agent Creation**: Creates JSON files in `~/.kiro/agents/` with standardized structure
2. **Agent Switching**: Automatically saves current state, restarts kiro-cli with new agent
3. **State Persistence**: Conversation history and agent state saved to `~/.kiro/bot_conversations/`
4. **Auto-Recovery**: Bot automatically restores previous session on restart

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
