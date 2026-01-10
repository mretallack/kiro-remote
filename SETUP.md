# Telegram Kiro Bot Setup Guide

## Overview
This project provides a Telegram bot interface to the Kiro CLI, allowing users to interact with Kiro through Telegram messages. The bot maintains a persistent Kiro session and forwards messages between Telegram and the CLI.

## Quick Start
```bash
# Run the bot (installs dependencies automatically)
make run

# Or manually:
make setup  # Install dependencies
python3 telegram_kiro_bot.py
```

## Project Structure
- `telegram_kiro_bot.py` - Main bot application
- `settings.ini` - Bot configuration (token, authorized users)
- `requirements.txt` - Python dependencies
- `Makefile` - Build and run commands
- `telegram-kiro-bot.service` - Systemd service file

## Configuration
Edit `settings.ini`:
```ini
[telegram]
token = YOUR_BOT_TOKEN

[bot]
authorized_user = your_telegram_username
auto_trust = true
progress_updates = true
```

## Available Commands
- `make run` - Start the bot
- `make test` - Run tests
- `make install` - Install as systemd service
- `make service-start` - Start service
- `make service-stop` - Stop service
- `make service-status` - Check service status
- `make clean` - Clean up virtual environment

## How It Works
1. Bot starts persistent `kiro-cli chat` session
2. Receives Telegram messages from authorized users
3. Forwards messages to Kiro CLI
4. Returns Kiro responses back to Telegram
5. Handles tool trust prompts automatically (if enabled)
6. Maintains session state with `/save` and `/load`

## Troubleshooting
- Check `bot.log` for errors
- Ensure Kiro CLI is installed and accessible
- Verify Telegram bot token is valid
- Check authorized user matches your Telegram username
