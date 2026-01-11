# Telegram Kiro Bot

A Python service that bridges Telegram with Kiro CLI, maintaining persistent conversation context.

## Features

- **Persistent Session**: Maintains a single Kiro CLI session across all messages
- **Auto Tool Trust**: Automatically trusts all tools to avoid prompts
- **Clean Output**: Strips ANSI escape codes for Telegram compatibility  
- **User Filtering**: Only responds to authorized user (configurable)
- **Error Handling**: Robust error handling and automatic recovery
- **Progress Updates**: Shows typing indicators during processing

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
2. **Auto Tool Trust**: Automatically trusts all tools using `/tools trust-all` command
3. **Message Processing**: Sends user messages to Kiro, captures responses
4. **Output Cleaning**: Removes ANSI codes and filters out prompts
5. **Telegram Integration**: Uses python-telegram-bot library for robust API handling

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
