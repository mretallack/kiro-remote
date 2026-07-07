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
- **Voice Messages**: Automatic speech-to-text transcription via Whisper
- **Real-time Progress**: See tool execution status as Kiro works
- **Clean Communication**: Structured JSON-RPC protocol (no ANSI parsing needed)
- **User Filtering**: Only responds to authorized user (configurable)
- **Error Handling**: Robust error handling and automatic recovery
- **Fast Cancellation**: Immediate response to cancel commands

## Real-time Progress Updates

The bot shows what Kiro is doing in real-time:
- **Tool Execution**: "🔧 Execute Bash..." when running commands
- **Command Output**: Stdout/stderr from executed commands (truncated if >2000 bytes)
- **File Operations**: "🔧 Fs Read..." when reading files
- **Progress Indicators**: Typing indicators during long operations

This helps you understand what Kiro is working on during longer tasks.

**Command Output Behavior**: When you run a command, you'll see:
1. Tool execution notification (e.g., "🔧 Running: echo hello")
2. Command stdout/stderr output (if any)
3. Kiro's summary/analysis of the result

Long outputs are automatically truncated to show the first 1000 and last 1000 bytes.

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

## Voice Messages

Send voice messages or audio files to the bot — they are automatically transcribed to text and sent to Kiro.

### How It Works
1. Send a voice message or audio file to the bot
2. Bot shows "🎤 Transcribing..." while processing
3. Speech is transcribed using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper small model, int8, CPU)
4. Transcription is sent to Kiro as: `[Voice message transcription (Xs)]: "your words"`
5. Kiro responds to the transcribed text

### Supported Formats
- **Voice messages**: Telegram's native voice recordings (OGG/Opus)
- **Audio files**: Any audio file sent as an attachment

### Details
- Uses VAD (Voice Activity Detection) to skip silence
- Whisper model is lazy-loaded on first voice message (avoids startup overhead)
- Transcription runs in a background thread to keep the bot responsive
- Works in both 1-to-1 chats and group topics

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

### Context Management
```
\context              # Show current context usage percentage
\context show         # Show detailed context information
\context clear        # Clear context rules
\compact              # Trigger manual conversation compaction
```

**Context Usage Warnings**: The bot automatically monitors context usage and sends warnings:
- ⚠️ Warning at 80%: "Consider using \compact"
- 🚨 Alert at 90%: "Recommend compacting now"

### Model Management
```
\model list           # List all available models and show current model
\model <model_id>     # Set the model for the current session
```

Examples:
```
\model list                    # Show available models
\model claude-sonnet-4.5       # Switch to Claude Sonnet 4.5
\model claude-opus-4.6         # Switch to Claude Opus 4.6
```

### Limitations

**Usage/Billing Command**: The `/usage` command is listed in `_kiro.dev/commands/available` but does not work via `_kiro.dev/commands/execute` in ACP mode. When called, kiro-cli returns zero messages (no RPC response, no notifications), causing the request to hang indefinitely until timeout. This is likely a terminal-only UI command. To check your account usage and credits, use the regular CLI:
```bash
kiro-cli chat
/usage
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
5. **Automatic Mode Switching**: When switching agents, the bot automatically sets the kiro-cli mode to match the agent name (if a matching mode exists)
6. **Context Isolation**: Conversations and context are isolated per agent
7. **Concurrent Agents**: Multiple agents can be running simultaneously, but only one is active at a time

### Automatic Mode Switching

When you swap to an agent (e.g., `\agent swap facebook`), the bot automatically:
1. Switches to the agent's kiro-cli process
2. Changes to the agent's working directory
3. Sets the kiro-cli mode to match the agent name (if available)

This gives each agent the right context automatically. If no matching mode exists, the agent continues with the default mode.

### Agent Lifecycle
- **Creation**: `\agent create <name>` - Interactive flow to define agent properties
- **Activation**: First message to an agent or `\agent swap` starts its Kiro process
- **Switching**: `\agent swap <name>` switches active agent without stopping others
- **Deletion**: `\agent delete <name>` removes agent definition (stops process if running)

### Use Cases
- **Project Separation**: Different agents for different codebases (e.g., `facebook_dev`, `kiro_default`)
- **Role Specialization**: Agents with different instructions for specific tasks
- **Context Management**: Keep separate conversation contexts for different projects

## Group Topics

Use a Telegram group with forum topics enabled to interact with multiple agents simultaneously — each topic maps to one agent.

### Setup

1. Create a Telegram group and enable "Topics" in group settings
2. Add the bot to the group and make it admin (needs `can_manage_topics` permission)
3. Create topics named after your agents (case-insensitive matching)
4. Or use `\topic sync` in any topic to auto-create topics for all agents

### Configuration

Add to `settings.ini`:
```ini
[group]
# Optional: restrict to specific group ID
# group_id = -1003610178913
# Path to topic-agent mapping cache
topic_cache = ~/.kiro/topic_agent_map.json
```

### Topic Commands

These commands work within group topics and are scoped to the topic's agent:

```
\topic register <agent>  # Manually map this topic to an agent
\topic sync              # Create topics for all agents that don't have one
\cancel                  # Cancel the topic's agent operation
\context                 # Show context usage for the topic's agent
\compact                 # Compact the topic's agent conversation
\model list              # List models for the topic's agent
\model <model_id>        # Set model for the topic's agent
\agent list              # List all agents (works in any topic)
```

### How It Works

1. **Topic Name Matching**: Topic names are matched case-insensitively to agent names
2. **Automatic Caching**: Once resolved, topic-to-agent mappings are cached persistently
3. **Background Sessions**: Agents started from topics don't change the active DM agent
4. **Lifecycle Events**: Topic creation/rename automatically updates the cache
5. **Attachments**: Photos and documents sent in topics route to the correct agent

### Naming Convention

Topic names should match agent names. For example:
- Topic "facebook_dev" → agent `facebook_dev`
- Topic "Kiro Default" → agent `kiro_default` (case-insensitive, spaces/underscores normalized)

If automatic matching fails, use `\topic register <agent>` to manually map a topic.

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

## Send File Skill

Kiro can send files directly to you in Telegram. This works two ways:

1. **Via `\send` command**: Type `\send /path/to/file` in chat
2. **Via Kiro skill**: Kiro autonomously sends files when you ask (e.g., "send me that report")

### Skill Setup

The send-file skill is not included in git — create it manually:

```bash
mkdir -p ~/.kiro/skills/send-file
cat > ~/.kiro/skills/send-file/SKILL.md << 'EOF'
---
name: send-file
description: Send a file to the user via Telegram. Use when you need to deliver a generated file, export, or any file to the user.
---

# Send File to User

Send a file to the user via Telegram by printing a special marker that the bot intercepts.

## Command

```bash
echo "SEND_FILE:/absolute/path/to/file"
```

## Rules

- Path MUST be absolute (start with `/` or use `$HOME`)
- File must exist and be under 50MB
- The echo output must be exactly `SEND_FILE:<path>` with no other output in the same command
- Use `~` expansion is supported (e.g., `SEND_FILE:~/reports/output.pdf`)

## Example

```bash
echo "SEND_FILE:/tmp/report.pdf"
```

## When to Use

- User asks you to send/share/deliver a file
- You've generated a file the user needs (PDF, image, export, archive)
- User says "send me", "give me the file", "share that file"
EOF
```

### How It Works

When Kiro executes `echo "SEND_FILE:/path/to/file"`, the bot intercepts the `SEND_FILE:` pattern in stdout and sends the file via `bot.send_document()`. The file is never included in Kiro's response text.

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

The bot runs as a user systemd service (no sudo required):

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
journalctl --user-unit telegram-kiro-bot -f
```

## TODO / Future Enhancements

### Context Management
- ✅ **Context usage warnings**: Alert user when context window usage exceeds 80%
- ✅ **Context reset command**: Add command to clear context and start fresh
- **Automatic compaction**: Trigger compaction automatically at configurable threshold
- **Context usage history**: Track and display usage over time

### Tool Execution Feedback
- **Long-running tool notifications**: Show "Still running..." message for commands taking > 10 seconds
- **Tool execution time**: Display how long commands took to complete
- **Progress indicators**: Show progress for multi-step operations

### Error Handling

- ✅ **Message too long splitting**
  - Problem: Kiro sometimes returns responses that exceed Telegram's 4096 character message limit, causing the message to fail to send entirely.
  - Found: `telegram.error.BadRequest: Message is too long` in journal logs (Apr 12 18:20).
  - Solution: Detect message length before sending and split into multiple sequential messages, preserving markdown formatting across chunks.

- ✅ **Prompt timeout handling**
  - Problem: Long-running Kiro tasks (e.g. complex code generation, docker builds) exceed the prompt timeout, causing the request to fail and the user to get no response.
  - Found: `Exception: Timeout waiting for response to session/prompt` — ~20 occurrences across Apr 11–12, the most frequent error in the logs.
  - Solution: Make the prompt timeout configurable in `settings.ini`. Consider increasing the default, and send the user a notification when a timeout occurs rather than silently failing.

- ✅ **Prompt already in progress guard**
  - Problem: When a prompt times out, the user retries, but the original prompt is still running server-side. The retry hits `Prompt already in progress` and also fails.
  - Found: `Exception: JSON-RPC error: {'code': -32603, 'message': 'Internal error', 'data': 'Prompt already in progress'}` — ~10 occurrences, always following a timeout.
  - Solution: Track prompt state and prevent sending a new prompt while one is in-flight. Queue incoming messages and notify the user that a previous request is still processing. Optionally cancel the in-flight prompt before retrying.

- ✅ **Monthly usage limit handling**
  - Problem: When the Kiro monthly usage limit is reached, every prompt fails with an unhandled exception. The bot keeps trying and failing on each user message.
  - Found: `Exception: JSON-RPC error: ... 'The monthly usage limit has been reached'` — 4 occurrences in quick succession (Apr 12 17:44–17:49) before the service was restarted.
  - Solution: Detect this specific error, notify the user with a friendly message ("Monthly usage limit reached — try again next month or check your plan"), and suppress further prompt attempts until the session is restarted or a configurable cooldown expires.

- ✅ **Transient network error recovery**
  - Problem: Occasional Telegram API connectivity issues cause unhandled exceptions that get logged but aren't recovered from gracefully.
  - Found: `telegram.error.NetworkError: httpx.ReadError:` (5 occurrences) and `telegram.error.NetworkError: Bad Gateway` (1 occurrence, Apr 12 02:10) in journal logs.
  - Solution: Add retry logic with exponential backoff for Telegram API calls. The python-telegram-bot library may already handle some retries — verify and configure appropriately. Register an error handler via `application.add_error_handler()` to catch and log these instead of letting them propagate unhandled.

- **Enhanced error messages**: Include more context and suggestions for common errors
- **Error recovery suggestions**: Provide actionable steps when operations fail
- **Retry mechanism**: Automatic retry for transient failures

### Performance Monitoring
- **Response time tracking**: Log and optionally display response times
- **Token usage display**: Show token consumption per message
- **Session statistics**: Track messages, tools used, errors per session

### Agent Management
- **Agent swap back**: Allow `\agent swap` (no name) to swap back to the previous agent
- **Prompt timeout investigation**: Review how chunk_timeout works — does it reset on each chunk received, or is it measured from send to end? Document and potentially make configurable
- **Typing indicator on agent swap**: Verify typing status is correctly updated when switching between agents — may not clear/set properly
- **Agent monitoring mode**: `\agent` with no subcommand enters monitoring mode — watches all running agents and notifies the user when any agent finishes (e.g., "✅ facebook_dev is finished and awaiting next instruction")
- ✅ **Agent list copy-to-clipboard**: Format agent names in `\agent list` so they are tappable/copyable in Telegram (using inline code formatting)

### User Experience
- **Configurable chunk timeout**: Per-user or per-agent timeout settings
- **Typing indicator customization**: Option to disable or adjust refresh rate
- **Tool output filtering**: Option to hide/show specific tool outputs
- **Message formatting options**: Markdown vs HTML, code highlighting preferences

### ACP Notifications (Unhandled)
- **Inbox notifications** (`_kiro.dev/session/inbox_notification`): Shows when subagent results are delivered to the main agent (`messageCount`, `senders`). Could display "📬 Subagent results received (3)" so the user knows the main agent is processing subagent output.
- **Tool call chunks** (`_kiro.dev/session/update` → `tool_call_chunk`): Streaming tool output from subagents (file contents, command output as it runs). Very noisy (~50/min during active subagent work). Could optionally show live subagent output, but would flood the chat without filtering/summarisation.
- **Commands available** (`_kiro.dev/commands/available`): Full list of slash commands with descriptions, sent after session creation. Could validate commands in `\help`, provide autocomplete suggestions, or detect typos in user commands.

### ACP Features (Not Yet Implemented)
- **`/chat new`**: Start fresh conversation without restarting the kiro-cli process. Would avoid the full session restart overhead.
- **`/spawn`**: Explicitly kick off parallel agent sessions from Telegram. Fire-and-forget background tasks with completion notifications.
- **`/transcript`**: Review conversation history. Could be exposed as a `\transcript` bot command.
- **`_session/terminate`**: ✅ Implemented as `\subagents kill <name>`
