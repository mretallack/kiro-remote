#!/usr/bin/env python3.12
import configparser
import json
import logging
import os
import pty
import re
import select
import signal
import subprocess
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

# Import ACP session manager
from kiro_session_acp import KiroSessionACP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/telegram_kiro_bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Use ACP-based session manager
KiroSession = KiroSessionACP


class TelegramBot:
    def __init__(self, token, authorized_user, attachments_dir=None):
        self.token = token
        self.authorized_user = authorized_user
        self.attachments_dir = Path(
            attachments_dir or "~/.kiro/bot_attachments"
        ).expanduser()
        self._setup_attachments_dir()
        self.kiro = KiroSessionACP()

        # Set up async callback for Kiro to send messages back
        async def send_to_telegram(chat_id, text):
            await self.application.bot.send_message(
                chat_id=chat_id, text=text, parse_mode="HTML"
            )

        self.kiro.send_to_telegram = send_to_telegram

        # Conversation state for multi-step interactions
        self.user_states = {}  # chat_id -> state dict

        # Start fresh session (load_state removed for now - will add back later)
        print(f"[DEBUG] Starting fresh session")
        self.kiro.start_session()

        self.application = Application.builder().token(token).build()
        self.loop = None

        # Add message and command handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        # Note: Agent and chat commands are handled via interception
        # This allows backslash prefix support (\agent, \chat)

        # Attachment handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )

    def _setup_attachments_dir(self):
        """Create attachments directory if it doesn't exist"""
        try:
            self.attachments_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            logger.info(f"Attachments directory ready: {self.attachments_dir}")
        except Exception as e:
            logger.error(f"Failed to create attachments directory: {e}")
            raise

    def _sanitize_filename(self, filename):
        """Remove dangerous characters from filename"""
        safe = re.sub(r'[/\\:*?"<>|]', "_", filename)
        safe = safe.replace(" ", "_")
        return safe[:255]

    def _generate_attachment_path(self, user_id, filename):
        """Generate unique file path for attachment"""
        timestamp = int(time.time())
        safe_filename = self._sanitize_filename(filename)
        unique_filename = f"{timestamp}_{user_id}_{safe_filename}"
        return self.attachments_dir / unique_filename

    def _format_attachment_message(self, caption, file_path):
        """Format message with attachment info for Kiro CLI"""
        context = "Note: The user sent this via Telegram. The attachment was downloaded to the local filesystem at the path below."
        if caption:
            return f"{context}\\n\\n{caption}\\n\\nThe attachment is {file_path}"
        return f"{context}\\n\\nThe attachment is {file_path}"

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads"""
        username = update.effective_user.username
        if username != self.authorized_user:
            return

        try:
            # Get highest resolution photo
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            # Generate path and download
            user_id = update.effective_user.id
            filename = f"photo_{photo.file_id[-8:]}.jpg"
            file_path = self._generate_attachment_path(user_id, filename)

            await file.download_to_drive(file_path)
            logger.info(f"Downloaded photo to {file_path}")

            # Format message and send to Kiro
            caption = update.message.caption or ""
            message = self._format_attachment_message(caption, str(file_path))
            message = message.replace("\n", "\\n")

            # Send to Kiro CLI using existing message handling
            chat_id = update.effective_chat.id
            self.kiro.set_chat_id(chat_id)
            self.kiro.last_typing_indicator = 0
            self.kiro.send_to_kiro(message)

            # Show typing indicator
            await update.effective_chat.send_action(ChatAction.TYPING)

        except Exception as e:
            logger.error(f"Error handling photo: {e}")
            await update.message.reply_text(f"❌ Failed to process photo: {e}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads"""
        username = update.effective_user.username
        if username != self.authorized_user:
            return

        try:
            document = update.message.document
            file = await context.bot.get_file(document.file_id)

            # Generate path and download
            user_id = update.effective_user.id
            filename = document.file_name or f"document_{document.file_id[-8:]}"
            file_path = self._generate_attachment_path(user_id, filename)

            await file.download_to_drive(file_path)
            logger.info(f"Downloaded document to {file_path}")

            # Format message and send to Kiro
            caption = update.message.caption or ""
            message = self._format_attachment_message(caption, str(file_path))
            message = message.replace("\n", "\\n")

            # Send to Kiro CLI using existing message handling
            chat_id = update.effective_chat.id
            self.kiro.set_chat_id(chat_id)
            self.kiro.last_typing_indicator = 0
            self.kiro.send_to_kiro(message)

            # Show typing indicator
            await update.effective_chat.send_action(ChatAction.TYPING)

        except Exception as e:
            logger.error(f"Error handling document: {e}")
            await update.message.reply_text(f"❌ Failed to process document: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        # Store the event loop for thread-safe calls
        if not self.loop:
            import asyncio

            self.loop = asyncio.get_running_loop()
            # Set the loop on the callback so worker thread can use it
            self.kiro.send_to_telegram.loop = self.loop
            logger.info(f"Event loop set: {self.loop}")

        username = update.effective_user.username
        chat_id = update.effective_chat.id
        print(f"[DEBUG] Received message from user: {username}")

        if username != self.authorized_user:
            print(f"[DEBUG] Unauthorized user {username}, ignoring")
            return

        message_text = update.message.text

        # Check if user is in a conversation state
        if chat_id in self.user_states:
            await self.handle_conversation_state(update, context)
            return

        print(f"[DEBUG] About to check intercepted commands for: {message_text}")
        # Check for intercepted commands before processing
        if await self.handle_intercepted_commands(update, context):
            print(f"[DEBUG] Command was intercepted, returning")
            return

        print(f"[DEBUG] Command not intercepted, proceeding to kiro-cli")

        # Normal message processing
        message_text = message_text.replace("\n", "\\n")
        print(f"[DEBUG] Processing message: {message_text}")

        # Show typing indicator briefly
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        # Send to Kiro (non-blocking via queue)
        print(f"[DEBUG] Sending to Kiro: {message_text}")
        self.kiro.send_message(message_text, update.effective_chat.id)

    async def handle_intercepted_commands(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Handle intercepted kiro commands. Returns True if command was intercepted."""
        message_text = update.message.text.strip()
        print(f"[DEBUG] Checking interception for: {message_text}")

        # Normalize backslash to forward slash for consistent processing
        normalized_text = message_text.replace("\\", "/")
        print(f"[DEBUG] Normalized text: {normalized_text}")

        # Usage command
        if normalized_text == "/usage":
            print(f"[DEBUG] Intercepted usage command")
            await self.show_usage(update, context)
            return True

        # Cancel command
        if normalized_text == "/cancel":
            print(f"[DEBUG] Intercepted cancel command")
            self.kiro.cancel_operation()
            await update.message.reply_text("🛑 Cancelling operation...")
            return True

        # Model commands
        if normalized_text.startswith("/model"):
            print(f"[DEBUG] Intercepted model command")
            parts = normalized_text.split(maxsplit=1)
            if len(parts) == 2:
                if parts[1] == "list":
                    await self.show_models(update, context)
                    return True
                else:
                    # Set model
                    model_id = parts[1]
                    await self.set_model(update, context, model_id)
                    return True
            else:
                await update.message.reply_text(
                    "Usage: \\model list OR \\model <model_id>"
                )
                return True

        # Agent commands
        if normalized_text.startswith("/agent"):
            print(f"[DEBUG] Intercepted agent command")
            parts = normalized_text.split()
            if len(parts) == 1:
                # Just "/agent" with no subcommand
                await update.message.reply_text(
                    "Usage: /agent <create|list|swap|delete> [name]"
                )
                return True
            elif len(parts) >= 2:
                subcommand = parts[1]
                print(f"[DEBUG] Agent subcommand: {subcommand}")

                if subcommand == "create":
                    if len(parts) >= 3:
                        agent_name = parts[2]
                        await self.start_agent_creation(update, context, agent_name)
                    else:
                        await update.message.reply_text("Usage: /agent create <name>")
                    return True

                elif subcommand == "list":
                    print(f"[DEBUG] Calling list_agents")
                    await self.list_agents(update, context)
                    return True

                elif subcommand == "swap":
                    if len(parts) >= 3:
                        agent_name = parts[2]
                        await self.swap_agent(update, context, agent_name)
                    else:
                        await update.message.reply_text("Usage: /agent swap <name>")
                    return True

                elif subcommand == "delete":
                    if len(parts) >= 3:
                        agent_name = parts[2]
                        await self.delete_agent(update, context, agent_name)
                    else:
                        await update.message.reply_text("Usage: /agent delete <name>")
                    return True

        # Chat commands
        elif normalized_text.startswith("/chat"):
            print(f"[DEBUG] Intercepted chat command")
            parts = normalized_text.split()
            if len(parts) == 1:
                # Just "/chat" with no subcommand
                await update.message.reply_text("Usage: /chat <save|load|list> [name]")
                return True
            elif len(parts) >= 2:
                subcommand = parts[1]
                print(f"[DEBUG] Chat subcommand: {subcommand}")

                if subcommand == "save" and len(parts) >= 3:
                    chat_name = parts[2]
                    await self.save_chat(update, context, chat_name)
                    return True

                elif subcommand == "load" and len(parts) >= 3:
                    chat_name = parts[2]
                    await self.load_chat(update, context, chat_name)
                    return True

                elif subcommand == "list":
                    await self.list_chats(update, context)
                    return True

        return False

    async def start_agent_creation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_name: str
    ):
        """Start agent creation flow from intercepted command"""
        chat_id = update.effective_chat.id

        # Validate agent name
        valid, error_msg = self.validate_agent_name(agent_name)
        if not valid:
            await update.message.reply_text(f"❌ Invalid agent name: {error_msg}")
            return

        # Check if agent already exists
        agent_file = Path.home() / ".kiro" / "agents" / f"{agent_name}.json"
        if agent_file.exists():
            await update.message.reply_text(f"❌ Agent '{agent_name}' already exists!")
            return

        # Start conversation flow
        self.user_states[chat_id] = {
            "type": "create_agent",
            "step": "description",
            "agent_name": agent_name,
        }

        await update.message.reply_text(
            f"Creating agent '{agent_name}'...\n\nWhat's the agent description?"
        )

    async def list_agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle intercepted /agent list command"""
        print(f"[DEBUG] list_agents called")
        print(f"[DEBUG] Update object: {update}")
        print(f"[DEBUG] Context object: {context}")

        # Authorization check
        if update.effective_user.username != self.authorized_user:
            print(
                f"[DEBUG] Unauthorized user: {update.effective_user.username} != {self.authorized_user}"
            )
            return

        try:
            # Built-in agents
            builtin_agents = ["kiro_default", "kiro_planner"]
            print(f"[DEBUG] Built-in agents: {builtin_agents}")

            # Get custom agents from ~/.kiro/agents/
            custom_agents = []
            agents_dir = Path.home() / ".kiro" / "agents"
            print(f"[DEBUG] Checking agents dir: {agents_dir}")
            if agents_dir.exists():
                for agent_file in agents_dir.glob("*.json"):
                    custom_agents.append(agent_file.stem)
            print(f"[DEBUG] Custom agents: {custom_agents}")
            print(f"[DEBUG] Active agent: {self.kiro.active_agent}")

            # Format response (simplified, no markdown)
            response = "Available agents:\n\n"
            response += "Built-in agents:\n"
            for agent in builtin_agents:
                current_marker = " <- active" if agent == self.kiro.active_agent else ""
                response += f"• {agent}{current_marker}\n"

            if custom_agents:
                response += "\nCustom agents:\n"
                for agent in sorted(custom_agents):
                    current_marker = (
                        " <- active" if agent == self.kiro.active_agent else ""
                    )
                    response += f"• {agent}{current_marker}\n"

            print(f"[DEBUG] Final response length: {len(response)}")
            print(f"[DEBUG] Final response: '{response}'")
            print(f"[DEBUG] About to send reply_text")
            await update.message.reply_text(response)
            print(f"[DEBUG] Reply sent successfully")
        except Exception as e:
            print(f"[DEBUG] Error in list_agents: {e}")
            print(f"[DEBUG] Exception type: {type(e)}")
            import traceback

            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            await update.message.reply_text(f"Error: {e}")

    async def show_usage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle intercepted /usage command - show credits and billing info"""
        if update.effective_user.username != self.authorized_user:
            return

        try:
            # Send usage request to Kiro CLI
            chat_id = update.effective_chat.id
            self.kiro.send_message("/usage", chat_id)
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting usage info: {e}")

    async def show_models(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle intercepted /model list command"""
        if update.effective_user.username != self.authorized_user:
            return

        try:
            models_info = self.kiro.get_available_models()
            if not models_info:
                await update.message.reply_text("❌ No model information available")
                return

            current_model = models_info.get("currentModelId", "unknown")
            available_models = models_info.get("availableModels", [])

            if not available_models:
                await update.message.reply_text("❌ No models available")
                return

            # Format the response
            response = f"<b>Current Model:</b> <code>{current_model}</code>\n\n<b>Available Models:</b>\n"
            for model in available_models:
                model_id = model.get("modelId", "unknown")
                name = model.get("name", "unknown")
                description = model.get("description", "")
                marker = "→ " if model_id == current_model else "  "
                response += f"{marker}<code>{model_id}</code> - {description}\n"

            await update.message.reply_text(response, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error showing models: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def set_model(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, model_id: str
    ):
        """Handle intercepted /model <model_id> command"""
        if update.effective_user.username != self.authorized_user:
            return

        try:
            # Validate model exists
            models_info = self.kiro.get_available_models()
            if not models_info:
                await update.message.reply_text("❌ No model information available")
                return

            available_models = models_info.get("availableModels", [])
            valid_model_ids = [m["modelId"] for m in available_models]

            if model_id not in valid_model_ids:
                await update.message.reply_text(
                    f"❌ Invalid model: <code>{model_id}</code>\n\n"
                    f"Available models: {', '.join(f'<code>{m}</code>' for m in valid_model_ids)}",
                    parse_mode="HTML",
                )
                return

            # Set the model
            chat_id = update.effective_chat.id
            self.kiro.set_model(model_id, chat_id)

        except Exception as e:
            logger.error(f"Error setting model: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
            await update.message.reply_text(f"❌ Error getting models: {e}")

    async def swap_agent(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_name: str
    ):
        """Handle intercepted /agent swap command"""
        try:
            # Auto-save current state
            if not self.kiro.save_state():
                await update.message.reply_text(
                    "⚠️ Warning: Could not save current state"
                )

            # Restart with new agent
            await update.message.reply_text(f"🔄 Switching to agent '{agent_name}'...")
            if self.kiro.restart_with_agent(agent_name):
                # Wait for session to initialize
                import asyncio

                await asyncio.sleep(2)
                await update.message.reply_text(f"✅ Switched to agent '{agent_name}'")
            else:
                await update.message.reply_text(
                    f"❌ Failed to switch to agent '{agent_name}'"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error switching agent: {e}")

    async def delete_agent(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_name: str
    ):
        """Handle intercepted /agent delete command"""
        try:
            agent_file = Path.home() / ".kiro" / "agents" / f"{agent_name}.json"
            if not agent_file.exists():
                await update.message.reply_text(f"❌ Agent '{agent_name}' not found!")
                return

            agent_file.unlink()
            await update.message.reply_text(
                f"✅ Agent '{agent_name}' deleted successfully"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error deleting agent: {e}")

    async def save_chat(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_name: str
    ):
        """Handle intercepted /chat save command"""
        try:
            print(f"[DEBUG] save_chat called with name: {chat_name}")
            if self.kiro.save_conversation(chat_name):
                await update.message.reply_text(
                    f"✅ Conversation saved as '{chat_name}'"
                )
            else:
                await update.message.reply_text(f"❌ Failed to save conversation")
        except Exception as e:
            print(f"[ERROR] Exception in save_chat: {e}")
            await update.message.reply_text(f"❌ Error saving conversation: {e}")

    async def load_chat(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_name: str
    ):
        """Handle intercepted /chat load command"""
        try:
            if self.kiro.load_conversation(chat_name):
                await update.message.reply_text(f"✅ Conversation '{chat_name}' loaded")
            else:
                await update.message.reply_text(
                    f"❌ Failed to load conversation '{chat_name}'"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error loading conversation: {e}")

    async def list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle intercepted /chat list command"""
        try:
            conversations_dir = Path.home() / ".kiro" / "bot_conversations"
            if not conversations_dir.exists():
                await update.message.reply_text("No saved conversations found")
                return

            chat_files = list(conversations_dir.glob("*.json"))
            if not chat_files:
                await update.message.reply_text("No saved conversations found")
                return

            chat_list = []
            for chat_file in chat_files:
                if chat_file.name != "__auto_save__.json":
                    chat_list.append(chat_file.stem)

            if chat_list:
                await update.message.reply_text(
                    f"Saved conversations:\n• " + "\n• ".join(sorted(chat_list))
                )
            else:
                await update.message.reply_text("No saved conversations found")
        except Exception as e:
            await update.message.reply_text(f"❌ Error listing conversations: {e}")

    async def handle_conversation_state(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle multi-step conversation states"""
        chat_id = update.effective_chat.id
        state = self.user_states[chat_id]
        message_text = update.message.text.strip()

        if state["type"] == "create_agent":
            await self.handle_create_agent_flow(update, context, state, message_text)

    async def handle_create_agent_flow(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, state, message_text
    ):
        """Handle the create agent conversation flow"""
        chat_id = update.effective_chat.id

        if state["step"] == "description":
            state["description"] = message_text
            state["step"] = "instructions"
            await update.message.reply_text("What instructions should the agent have?")

        elif state["step"] == "instructions":
            state["instructions"] = message_text

            # Create the agent JSON using template
            agent_data = self.create_agent_json(
                state["agent_name"], state["description"], state["instructions"]
            )

            # Save agent file
            try:
                agents_dir = Path.home() / ".kiro" / "agents"
                agents_dir.mkdir(parents=True, exist_ok=True)

                agent_file = agents_dir / f"{state['agent_name']}.json"
                with open(agent_file, "w") as f:
                    json.dump(agent_data, f, indent=2)

                # Create agent-specific steering directory and overview.md
                steering_dir = agents_dir / state["agent_name"] / "steering"
                steering_dir.mkdir(parents=True, exist_ok=True)

                overview_file = steering_dir / "overview.md"
                with open(overview_file, "w") as f:
                    f.write(f"# {state['agent_name']}\n\n{state['description']}\n")

                # Create working directory under /home/mark/git
                working_dir = Path("/home/mark/git") / state["agent_name"]
                working_dir.mkdir(parents=True, exist_ok=True)

                # Update bot_agent_config.json
                config_file = Path.home() / ".kiro" / "bot_agent_config.json"
                if config_file.exists():
                    with open(config_file, "r") as f:
                        config = json.load(f)
                else:
                    config = {
                        "agents": {},
                        "default_directory": "/home/mark/git/remote-kiro",
                    }

                config["agents"][state["agent_name"]] = {
                    "working_directory": str(working_dir)
                }

                with open(config_file, "w") as f:
                    json.dump(config, f, indent=2)

                await update.message.reply_text(
                    f"✅ Agent '{state['agent_name']}' created successfully!\n\n"
                    f"📝 Description: {state['description']}\n"
                    f"🤖 Instructions: {state['instructions']}\n"
                    f"📁 Working directory: {working_dir}\n\n"
                    f"Use `/agent swap {state['agent_name']}` to activate it."
                )

            except Exception as e:
                await update.message.reply_text(f"❌ Error creating agent: {e}")

            # Clear conversation state
            del self.user_states[chat_id]

    def validate_agent_name(self, name):
        """Validate agent name format"""
        if not name:
            return False, "Agent name cannot be empty"
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            return (
                False,
                "Agent name can only contain letters, numbers, underscores, and hyphens",
            )
        if len(name) > 50:
            return False, "Agent name must be 50 characters or less"
        return True, ""

    def create_agent_json(self, name, description, instructions):
        """Create standardized agent JSON structure"""
        return {
            "name": name,
            "description": description,
            "prompt": instructions,
            "mcpServers": {},
            "tools": ["*"],
            "toolAliases": {},
            "allowedTools": [],
            "resources": [
                "file://~/.kiro/steering/**/*.md",
                f"file://~/.kiro/agents/{name}/steering/*.md",
                f"file://~/git/{name}/.kiro/steering/**/*.md",
            ],
            "hooks": {},
            "toolsSettings": {},
            "useLegacyMcpJson": True,
            "model": None,
        }

    async def create_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /create_agent command"""
        if update.effective_user.username != self.authorized_user:
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /create_agent <agent_name>")
            return

        agent_name = args[0]
        chat_id = update.effective_chat.id

        # Validate agent name
        valid, error_msg = self.validate_agent_name(agent_name)
        if not valid:
            await update.message.reply_text(f"❌ Invalid agent name: {error_msg}")
            return

        # Check if agent already exists
        agent_file = Path.home() / ".kiro" / "agents" / f"{agent_name}.json"
        if agent_file.exists():
            await update.message.reply_text(f"❌ Agent '{agent_name}' already exists!")
            return

        # Start conversation flow
        self.user_states[chat_id] = {
            "type": "create_agent",
            "step": "description",
            "agent_name": agent_name,
        }

        await update.message.reply_text(
            f"Creating agent '{agent_name}'...\n\nWhat's the agent description?"
        )

    async def switch_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /switch_agent command"""
        if update.effective_user.username != self.authorized_user:
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /switch_agent <agent_name>")
            return

        agent_name = args[0]

        try:
            # Auto-save current state
            if not self.kiro.save_state():
                await update.message.reply_text(
                    "⚠️ Warning: Could not save current state"
                )

            await update.message.reply_text(f"Switching to agent '{agent_name}'...")

            # Restart with new agent
            self.kiro.restart_session(agent_name)

            # Verify the agent switch worked
            if self.kiro.active_agent == agent_name:
                await update.message.reply_text(f"✅ Now using agent: {agent_name}")
            else:
                await update.message.reply_text(
                    f"⚠️ Agent switch may have failed. Active agent: {self.kiro.active_agent}"
                )

        except Exception as e:
            await update.message.reply_text(f"❌ Error switching agent: {e}")
            # Try to restart with default agent as fallback
            try:
                self.kiro.restart_session()
                await update.message.reply_text(
                    "🔄 Fallback: Restarted with default agent"
                )
            except Exception as fallback_error:
                await update.message.reply_text(f"💥 Critical error: {fallback_error}")

    def send_response_threadsafe(self, chat_id, text):
        """Send response to Telegram from thread"""
        print(f"[DEBUG] Thread-safe send for chat {chat_id}: {text[:100]}...")
        if self.loop:
            import asyncio

            future = asyncio.run_coroutine_threadsafe(
                self._send_message_async(chat_id, text), self.loop
            )
            # Don't wait for result to keep it non-blocking
        else:
            print("[DEBUG] No event loop available yet")

    def send_typing_indicator_threadsafe(self, chat_id):
        """Send typing indicator to Telegram from thread"""
        if self.loop:
            import asyncio

            future = asyncio.run_coroutine_threadsafe(
                self._send_typing_async(chat_id), self.loop
            )
            # Don't wait for result to keep it non-blocking

    async def _send_typing_async(self, chat_id):
        """Internal async method to send typing indicator"""
        try:
            await self.application.bot.send_chat_action(
                chat_id=chat_id, action=ChatAction.TYPING
            )
        except Exception as e:
            print(f"[DEBUG] Error sending typing indicator: {e}")

    async def _send_message_async(self, chat_id, text):
        """Internal async method to send message"""
        try:
            # Show typing indicator before sending response
            await self.application.bot.send_chat_action(
                chat_id=chat_id, action=ChatAction.TYPING
            )
            await self.application.bot.send_message(chat_id=chat_id, text=text)
            print("[DEBUG] Response sent successfully")
        except Exception as e:
            print(f"[DEBUG] Error sending response: {e}")

    def run(self):
        """Start the bot"""
        print("Telegram Kiro Bot started...")
        self.application.run_polling()


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("settings.ini")

    TOKEN = config.get("telegram", "token")
    AUTHORIZED_USER = config.get("bot", "authorized_user")
    ATTACHMENTS_DIR = config.get(
        "bot", "attachments_dir", fallback="~/.kiro/bot_attachments"
    )

    bot = TelegramBot(TOKEN, AUTHORIZED_USER, ATTACHMENTS_DIR)
    bot.run()
