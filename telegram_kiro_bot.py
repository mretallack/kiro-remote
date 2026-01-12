#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import json
import configparser
import logging
from pathlib import Path
from queue import Queue, Empty
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/telegram_kiro_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KiroSession:
    def __init__(self):
        self.process = None
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.current_chat_id = None
        self.telegram_bot = None
        self.response_buffer = []
        self.last_activity = time.time()
        self.last_typing_indicator = 0
        self.current_agent = None  # Track current agent
        self.conversation_history = []  # Track conversation for replay
        self.start_session()
    
    def start_session(self, agent_name=None):
        """Start persistent Kiro session with threaded I/O"""
        logger.info(f"Starting Kiro session with agent: {agent_name}")
        
        try:
            # Stop existing session if running
            if self.process and self.process.poll() is None:
                self.stop_session()
            
            env = os.environ.copy()
            env['NO_COLOR'] = '1'
            env['EDITOR'] = 'cat'
            env['VISUAL'] = 'cat'
            env['TERM'] = 'dumb'
            env['PATH'] = '/home/mark/.local/bin:' + env.get('PATH', '')
            
            # Build command with optional agent
            cmd = ['/home/mark/.local/bin/kiro-cli', 'chat', '--trust-all-tools']
            if agent_name:
                cmd.extend(['--agent', agent_name])
                self.current_agent = agent_name
            else:
                self.current_agent = 'kiro_default'
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,
                env=env,
                cwd='/home/mark/git/remote-kiro'
            )
            logger.info(f"Kiro process started with PID: {self.process.pid}, agent: {self.current_agent}")
            
            # Start I/O threads
            threading.Thread(target=self._input_thread, daemon=True).start()
            threading.Thread(target=self._output_thread, daemon=True).start()
            threading.Thread(target=self._response_processor, daemon=True).start()
            threading.Thread(target=self._timeout_checker, daemon=True).start()
            
            # Trust all tools
            self.send_to_kiro('/tools trust-all')
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to start Kiro session: {e}")
            self.current_agent = 'kiro_default'  # Fallback
            if self.telegram_bot and self.current_chat_id:
                self.telegram_bot.send_response_threadsafe(
                    self.current_chat_id, 
                    f"❌ Error starting Kiro session: {e}"
                )
    
    def stop_session(self):
        """Stop the current Kiro session"""
        try:
            if self.process and self.process.poll() is None:
                print(f"[DEBUG] Stopping Kiro process {self.process.pid}")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[DEBUG] Force killing Kiro process")
                    self.process.kill()
                    self.process.wait()
            self.process = None
        except Exception as e:
            print(f"[ERROR] Error stopping session: {e}")
            self.process = None
    
    def restart_session(self, agent_name=None):
        """Restart Kiro session with optional different agent"""
        print(f"[DEBUG] Restarting session with agent: {agent_name}")
        try:
            self.stop_session()
            time.sleep(1)  # Brief pause
            self.start_session(agent_name)
        except Exception as e:
            print(f"[ERROR] Error restarting session: {e}")
            # Try fallback to default agent
            try:
                self.start_session()
            except Exception as fallback_error:
                print(f"[ERROR] Fallback session start failed: {fallback_error}")
                if self.telegram_bot and self.current_chat_id:
                    self.telegram_bot.send_response_threadsafe(
                        self.current_chat_id,
                        "❌ Critical error: Unable to start Kiro session. Please restart the bot."
                    )
    
    def _input_thread(self):
        """Thread to handle input to Kiro"""
        while self.process and self.process.poll() is None:
            try:
                command = self.input_queue.get(timeout=1)
                if command:
                    print(f"[DEBUG] SENDING: {repr(command)}")
                    self.process.stdin.write(command + '\n')
                    self.process.stdin.flush()
            except Empty:
                continue
            except Exception as e:
                print(f"[DEBUG] Input thread error: {e}")
                break
    
    def _output_thread(self):
        """Thread to handle output from Kiro"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
            except Exception as e:
                print(f"[DEBUG] Output thread error: {e}")
                break
    
    def _timeout_checker(self):
        """Check for response timeout and send buffered content"""
        while True:
            time.sleep(2)  # Check every 2 seconds
            if (self.response_buffer and 
                time.time() - self.last_activity > 3 and  # 3 seconds of inactivity
                self.current_chat_id):
                print("[DEBUG] Timeout detected, sending buffered response")
                self._send_buffered_response()
    
    def _response_processor(self):
        """Thread to process Kiro output and send to Telegram"""
        while True:
            try:
                line = self.output_queue.get(timeout=1)
                self.last_activity = time.time()  # Update activity timestamp
                self._handle_line(line)
            except Empty:
                continue
            except Exception as e:
                print(f"[DEBUG] Response processor error: {e}")
                break
    
    def _handle_line(self, line):
        """Handle a single line from Kiro"""
        clean_line = self._strip_ansi(line.strip())
        print(f"[DEBUG] RAW: {repr(clean_line)}")
        
        # Send typing indicator every 4 seconds while processing
        current_time = time.time()
        if (self.current_chat_id and self.telegram_bot and 
            current_time - self.last_typing_indicator > 4):
            self.last_typing_indicator = current_time
            self.telegram_bot.send_typing_indicator_threadsafe(self.current_chat_id)
        
        # Skip thinking lines and empty lines
        if (re.match(r'^. Thinking\.\.\.$', clean_line) or 
            not clean_line or
            clean_line.startswith('▸ Credits:')):
            return
        
        # Handle prompts automatically
        if self._handle_auto_trust(line):
            return
        
        # Check if this is end of response (prompt returned)
        # Look for various prompt patterns
        if (clean_line.strip() == '>' or 
            clean_line.strip() == '!>' or
            clean_line.strip().endswith('> ') or
            clean_line.strip().endswith('!> ') or
            (len(clean_line.strip()) <= 3 and ('>' in clean_line or '!>' in clean_line))):
            print(f"[DEBUG] Detected end of response with prompt: {repr(clean_line)}")
            self._send_buffered_response()
            return
        
        # Extract content after prompt marker if present
        if '> ' in clean_line and not clean_line.strip().endswith('> '):
            parts = clean_line.split('> ', 1)
            if len(parts) > 1 and parts[1].strip():
                print(f"[DEBUG] Adding to buffer (after >): {repr(parts[1].strip())}")
                self.response_buffer.append(parts[1].strip())
        elif '!> ' in clean_line and not clean_line.strip().endswith('!> '):
            parts = clean_line.split('!> ', 1)
            if len(parts) > 1 and parts[1].strip():
                print(f"[DEBUG] Adding to buffer (after !>): {repr(parts[1].strip())}")
                self.response_buffer.append(parts[1].strip())
        elif clean_line and not clean_line.strip().endswith('> ') and not clean_line.strip().endswith('!> '):
            print(f"[DEBUG] Adding to buffer (full line): {repr(clean_line)}")
            self.response_buffer.append(clean_line)
    
    def _send_buffered_response(self):
        """Send accumulated response to Telegram"""
        print(f"[DEBUG] _send_buffered_response called. Buffer: {len(self.response_buffer)} lines, chat_id: {self.current_chat_id}")
        
        if not self.response_buffer or not self.current_chat_id or not self.telegram_bot:
            print(f"[DEBUG] Skipping send - buffer empty: {not self.response_buffer}, no chat_id: {not self.current_chat_id}, no bot: {not self.telegram_bot}")
            return
        
        response = '\n'.join(self.response_buffer)
        self.response_buffer = []
        
        # Track bot response in conversation history
        if self.conversation_history and response.strip():
            self.conversation_history[-1]["bot"] = response.strip()
        
        print(f"[DEBUG] Sending response: {response[:200]}...")
        
        # Smart truncation
        if len(response) > 4000:
            beginning = response[:1500]
            end = response[-1500:]
            response = f"{beginning}\n\n...(truncated)...\n\n{end}"
        
        # Send response using thread-safe async call
        self.telegram_bot.send_response_threadsafe(self.current_chat_id, response or "No response")
    
    def _handle_auto_trust(self, line):
        """Auto-handle trust prompts"""
        if '[y/n/t]' in line:
            self.send_to_kiro('t')
            return True
        elif '(y/n)' in line or '[y/N]' in line:
            self.send_to_kiro('y')
            return True
        elif '!>!>' in line or '!>' in line:
            self.send_to_kiro('')
            return True
        return False
    
    def _strip_ansi(self, text):
        """Remove ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def send_to_kiro(self, message):
        """Send message to Kiro (non-blocking)"""
        # Map backslash to forward slash
        if message.startswith('\\'):
            message = '/' + message[1:]
        
        # Track conversation history (exclude bot commands)
        if not message.startswith('/'):
            self.conversation_history.append({"user": message, "timestamp": time.time()})
        
        self.input_queue.put(message)
    
    def save_state(self, name="__auto_save__"):
        """Save current conversation state to file"""
        try:
            state_dir = Path.home() / ".kiro" / "bot_conversations"
            state_dir.mkdir(parents=True, exist_ok=True)
            
            state = {
                "current_agent": self.current_agent,
                "timestamp": time.time(),
                "conversation_history": self.conversation_history,
                "working_directory": "/home/mark/git/remote-kiro"
            }
            
            state_file = state_dir / f"{name}.json"
            
            # Create backup if file exists
            if state_file.exists():
                backup_file = state_dir / f"{name}_backup_{int(time.time())}.json"
                state_file.rename(backup_file)
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"[DEBUG] State saved to {state_file}")
            return True
        except Exception as e:
            print(f"[ERROR] Error saving state: {e}")
            return False
    
    def load_state(self, name="__auto_save__"):
        """Load conversation state from file"""
        try:
            state_file = Path.home() / ".kiro" / "bot_conversations" / f"{name}.json"
            if not state_file.exists():
                print(f"[DEBUG] State file {state_file} does not exist")
                return False
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            # Validate state structure
            if not isinstance(state, dict):
                raise ValueError("Invalid state format")
            
            self.current_agent = state.get("current_agent", "kiro_default")
            self.conversation_history = state.get("conversation_history", [])
            
            # Validate conversation history
            if not isinstance(self.conversation_history, list):
                self.conversation_history = []
            
            print(f"[DEBUG] State loaded from {state_file}, agent: {self.current_agent}")
            return True
        except Exception as e:
            print(f"[ERROR] Error loading state: {e}")
            # Reset to defaults on error
            self.current_agent = "kiro_default"
            self.conversation_history = []
            return False
    
    def replay_conversation(self):
        """Replay conversation history to restore context"""
        if not self.conversation_history:
            return
        
        print(f"[DEBUG] Replaying {len(self.conversation_history)} messages")
        for entry in self.conversation_history:
            if "user" in entry:
                self.send_to_kiro(entry["user"])
                time.sleep(0.5)  # Brief pause between messages
    
    def restart_with_agent(self, agent_name):
        """Restart kiro-cli with specified agent"""
        try:
            # Save current state
            self.save_state()
            
            # Stop current session
            self.stop_session()
            
            # Brief pause to ensure clean shutdown
            time.sleep(0.5)
            
            # Start new session with agent
            self.start_session(agent_name)
            
            # Wait for initialization and send initial trust command
            time.sleep(1.5)
            self.send_to_kiro('/tools trust-all')
            time.sleep(0.5)
            
            print(f"[DEBUG] Restarted with agent: {agent_name}")
            return True
        except Exception as e:
            print(f"[ERROR] Error restarting with agent: {e}")
            return False
    
    def save_conversation(self, name):
        """Save conversation with custom name"""
        return self.save_state(name)
    
    def load_conversation(self, name):
        """Load conversation with custom name"""
        if self.load_state(name):
            # Restart with the loaded agent
            if self.current_agent:
                self.restart_with_agent(self.current_agent)
            return True
        return False
    
    def set_chat_id(self, chat_id):
        """Set current chat ID for responses"""
        self.current_chat_id = chat_id

class TelegramBot:
    def __init__(self, token, authorized_user):
        self.token = token
        self.authorized_user = authorized_user
        self.kiro = KiroSession()
        self.kiro.telegram_bot = self
        
        # Conversation state for multi-step interactions
        self.user_states = {}  # chat_id -> state dict
        
        # Try to restore previous session
        if self.kiro.load_state():
            print(f"[DEBUG] Restored previous session with agent: {self.kiro.current_agent}")
            self.kiro.restart_session(self.kiro.current_agent)
        
        self.application = Application.builder().token(token).build()
        self.loop = None
        
        # Add message and command handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        # Note: Agent commands are now handled via interception (/agent create|list|swap|delete)
        # Chat commands still use old format for now
        self.application.add_handler(CommandHandler("save_chat", self.save_chat))
        self.application.add_handler(CommandHandler("load_chat", self.load_chat))
        self.application.add_handler(CommandHandler("list_chats", self.list_chats))
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        # Store the event loop for thread-safe calls
        if not self.loop:
            import asyncio
            self.loop = asyncio.get_running_loop()
        
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
        message_text = message_text.replace('\n', '\\n')
        print(f"[DEBUG] Processing message: {message_text}")
        
        # Show typing indicator briefly
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action=ChatAction.TYPING
        )
        
        # Set chat ID and send to Kiro immediately (non-blocking)
        print(f"[DEBUG] Setting chat_id to {update.effective_chat.id}")
        self.kiro.set_chat_id(update.effective_chat.id)
        # Reset typing indicator timestamp for new message
        self.kiro.last_typing_indicator = 0
        print(f"[DEBUG] Sending to Kiro: {message_text}")
        self.kiro.send_to_kiro(message_text)
    
    async def handle_intercepted_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Handle intercepted kiro commands. Returns True if command was intercepted."""
        message_text = update.message.text.strip()
        print(f"[DEBUG] Checking interception for: {message_text}")
        
        # Normalize backslash to forward slash for consistent processing
        normalized_text = message_text.replace('\\', '/')
        print(f"[DEBUG] Normalized text: {normalized_text}")
        
        # Agent commands
        if normalized_text.startswith('/agent'):
            print(f"[DEBUG] Intercepted agent command")
            parts = normalized_text.split()
            if len(parts) == 1:
                # Just "/agent" with no subcommand
                await update.message.reply_text("Usage: /agent <create|list|swap|delete> [name]")
                return True
            elif len(parts) >= 2:
                subcommand = parts[1]
                print(f"[DEBUG] Agent subcommand: {subcommand}")
                
                if subcommand == 'create':
                    if len(parts) >= 3:
                        agent_name = parts[2]
                        await self.start_agent_creation(update, context, agent_name)
                    else:
                        await update.message.reply_text("Usage: /agent create <name>")
                    return True
                    
                elif subcommand == 'list':
                    print(f"[DEBUG] Calling list_agents")
                    await self.list_agents(update, context)
                    return True
                    
                elif subcommand == 'swap':
                    if len(parts) >= 3:
                        agent_name = parts[2]
                        await self.swap_agent(update, context, agent_name)
                    else:
                        await update.message.reply_text("Usage: /agent swap <name>")
                    return True
                    
                elif subcommand == 'delete':
                    if len(parts) >= 3:
                        agent_name = parts[2]
                        await self.delete_agent(update, context, agent_name)
                    else:
                        await update.message.reply_text("Usage: /agent delete <name>")
                    return True
        
        # Chat commands
        elif normalized_text.startswith('/chat'):
            print(f"[DEBUG] Intercepted chat command")
            parts = normalized_text.split()
            if len(parts) == 1:
                # Just "/chat" with no subcommand
                await update.message.reply_text("Usage: /chat <save|load|list> [name]")
                return True
            elif len(parts) >= 2:
                subcommand = parts[1]
                print(f"[DEBUG] Chat subcommand: {subcommand}")
                
                if subcommand == 'save' and len(parts) >= 3:
                    chat_name = parts[2]
                    await self.save_chat(update, context, chat_name)
                    return True
                    
                elif subcommand == 'load' and len(parts) >= 3:
                    chat_name = parts[2]
                    await self.load_chat(update, context, chat_name)
                    return True
                    
                elif subcommand == 'list':
                    await self.list_chats(update, context)
                    return True
        
        return False
    
    async def start_agent_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_name: str):
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
            "agent_name": agent_name
        }
        
        await update.message.reply_text(f"Creating agent '{agent_name}'...\n\nWhat's the agent description?")
    
    async def list_agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle intercepted /agent list command"""
        print(f"[DEBUG] list_agents called")
        print(f"[DEBUG] Update object: {update}")
        print(f"[DEBUG] Context object: {context}")
        
        # Authorization check
        if update.effective_user.username != self.authorized_user:
            print(f"[DEBUG] Unauthorized user: {update.effective_user.username} != {self.authorized_user}")
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
            print(f"[DEBUG] Current agent: {self.kiro.current_agent}")
            
            # Format response (simplified, no markdown)
            response = "Available agents:\n\n"
            response += "Built-in agents:\n"
            for agent in builtin_agents:
                current_marker = " <- current" if agent == self.kiro.current_agent else ""
                response += f"• {agent}{current_marker}\n"
            
            if custom_agents:
                response += "\nCustom agents:\n"
                for agent in sorted(custom_agents):
                    current_marker = " <- current" if agent == self.kiro.current_agent else ""
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
    
    async def swap_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_name: str):
        """Handle intercepted /agent swap command"""
        try:
            # Auto-save current state
            if not self.kiro.save_state():
                await update.message.reply_text("⚠️ Warning: Could not save current state")
            
            # Restart with new agent
            await update.message.reply_text(f"🔄 Switching to agent '{agent_name}'...")
            if self.kiro.restart_with_agent(agent_name):
                # Wait for session to initialize
                import asyncio
                await asyncio.sleep(2)
                await update.message.reply_text(f"✅ Switched to agent '{agent_name}'")
            else:
                await update.message.reply_text(f"❌ Failed to switch to agent '{agent_name}'")
        except Exception as e:
            await update.message.reply_text(f"❌ Error switching agent: {e}")
    
    async def delete_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_name: str):
        """Handle intercepted /agent delete command"""
        try:
            agent_file = Path.home() / ".kiro" / "agents" / f"{agent_name}.json"
            if not agent_file.exists():
                await update.message.reply_text(f"❌ Agent '{agent_name}' not found!")
                return
            
            agent_file.unlink()
            await update.message.reply_text(f"✅ Agent '{agent_name}' deleted successfully")
        except Exception as e:
            await update.message.reply_text(f"❌ Error deleting agent: {e}")
    
    async def save_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_name: str):
        """Handle intercepted /chat save command"""
        try:
            if self.kiro.save_conversation(chat_name):
                await update.message.reply_text(f"✅ Conversation saved as '{chat_name}'")
            else:
                await update.message.reply_text(f"❌ Failed to save conversation")
        except Exception as e:
            await update.message.reply_text(f"❌ Error saving conversation: {e}")
    
    async def load_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_name: str):
        """Handle intercepted /chat load command"""
        try:
            if self.kiro.load_conversation(chat_name):
                await update.message.reply_text(f"✅ Conversation '{chat_name}' loaded")
            else:
                await update.message.reply_text(f"❌ Failed to load conversation '{chat_name}'")
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
                await update.message.reply_text(f"Saved conversations:\n• " + "\n• ".join(sorted(chat_list)))
            else:
                await update.message.reply_text("No saved conversations found")
        except Exception as e:
            await update.message.reply_text(f"❌ Error listing conversations: {e}")
    
    async def handle_conversation_state(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle multi-step conversation states"""
        chat_id = update.effective_chat.id
        state = self.user_states[chat_id]
        message_text = update.message.text.strip()
        
        if state["type"] == "create_agent":
            await self.handle_create_agent_flow(update, context, state, message_text)
    
    async def handle_create_agent_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state, message_text):
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
                state["agent_name"],
                state["description"], 
                state["instructions"]
            )
            
            # Save agent file
            try:
                agents_dir = Path.home() / ".kiro" / "agents"
                agents_dir.mkdir(parents=True, exist_ok=True)
                
                agent_file = agents_dir / f"{state['agent_name']}.json"
                with open(agent_file, 'w') as f:
                    json.dump(agent_data, f, indent=2)
                
                await update.message.reply_text(
                    f"✅ Agent '{state['agent_name']}' created successfully!\n\n"
                    f"📝 Description: {state['description']}\n"
                    f"🤖 Instructions: {state['instructions']}\n\n"
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
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return False, "Agent name can only contain letters, numbers, underscores, and hyphens"
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
            "resources": ["file://~/.kiro/steering/**/*.md"],
            "hooks": {},
            "toolsSettings": {},
            "useLegacyMcpJson": True,
            "model": None,
            "created_at": time.time(),
            "version": "1.0"
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
            "agent_name": agent_name
        }
        
        await update.message.reply_text(f"Creating agent '{agent_name}'...\n\nWhat's the agent description?")
    

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
                await update.message.reply_text("⚠️ Warning: Could not save current state")
            
            await update.message.reply_text(f"Switching to agent '{agent_name}'...")
            
            # Restart with new agent
            self.kiro.restart_session(agent_name)
            
            # Verify the agent switch worked
            if self.kiro.current_agent == agent_name:
                await update.message.reply_text(f"✅ Now using agent: {agent_name}")
            else:
                await update.message.reply_text(f"⚠️ Agent switch may have failed. Current agent: {self.kiro.current_agent}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error switching agent: {e}")
            # Try to restart with default agent as fallback
            try:
                self.kiro.restart_session()
                await update.message.reply_text("🔄 Fallback: Restarted with default agent")
            except Exception as fallback_error:
                await update.message.reply_text(f"💥 Critical error: {fallback_error}")
    
    async def save_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /save_chat command"""
        if update.effective_user.username != self.authorized_user:
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /save_chat <name>")
            return
        
        name = args[0]
        if self.kiro.save_state(name):
            await update.message.reply_text(f"Conversation saved as '{name}'")
        else:
            await update.message.reply_text("Error saving conversation")
    
    async def load_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /load_chat command"""
        if update.effective_user.username != self.authorized_user:
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /load_chat <name>")
            return
        
        name = args[0]
        if self.kiro.load_state(name):
            await update.message.reply_text(f"Loading conversation '{name}'...")
            
            # Restart with saved agent
            self.kiro.restart_session(self.kiro.current_agent)
            
            # Replay conversation
            self.kiro.replay_conversation()
            
            await update.message.reply_text(f"Conversation '{name}' restored")
        else:
            await update.message.reply_text(f"Error loading conversation '{name}'")
    
    async def list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list_chats command"""
        if update.effective_user.username != self.authorized_user:
            return
        
        try:
            state_dir = Path.home() / ".kiro" / "bot_conversations"
            if not state_dir.exists():
                await update.message.reply_text("No saved conversations found")
                return
            
            chat_files = list(state_dir.glob("*.json"))
            if not chat_files:
                await update.message.reply_text("No saved conversations found")
                return
            
            chat_list = []
            for chat_file in chat_files:
                name = chat_file.stem
                if name == "__auto_save__":
                    continue
                
                try:
                    with open(chat_file, 'r') as f:
                        state = json.load(f)
                    timestamp = state.get("timestamp", 0)
                    agent = state.get("current_agent", "unknown")
                    date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))
                    chat_list.append(f"• {name} ({agent}) - {date_str}")
                except:
                    chat_list.append(f"• {name} (corrupted)")
            
            if chat_list:
                await update.message.reply_text("Saved conversations:\n" + "\n".join(chat_list))
            else:
                await update.message.reply_text("No saved conversations found")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    
    def send_response_threadsafe(self, chat_id, text):
        """Send response to Telegram from thread"""
        print(f"[DEBUG] Thread-safe send for chat {chat_id}: {text[:100]}...")
        if self.loop:
            import asyncio
            future = asyncio.run_coroutine_threadsafe(
                self._send_message_async(chat_id, text), 
                self.loop
            )
            # Don't wait for result to keep it non-blocking
        else:
            print("[DEBUG] No event loop available yet")
    
    def send_typing_indicator_threadsafe(self, chat_id):
        """Send typing indicator to Telegram from thread"""
        if self.loop:
            import asyncio
            future = asyncio.run_coroutine_threadsafe(
                self._send_typing_async(chat_id), 
                self.loop
            )
            # Don't wait for result to keep it non-blocking
    
    async def _send_typing_async(self, chat_id):
        """Internal async method to send typing indicator"""
        try:
            await self.application.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )
        except Exception as e:
            print(f"[DEBUG] Error sending typing indicator: {e}")
    
    async def _send_message_async(self, chat_id, text):
        """Internal async method to send message"""
        try:
            # Show typing indicator before sending response
            await self.application.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )
            await self.application.bot.send_message(chat_id=chat_id, text=text)
            print("[DEBUG] Response sent successfully")
        except Exception as e:
            print(f"[DEBUG] Error sending response: {e}")
    
    def run(self):
        """Start the bot"""
        print("Telegram Kiro Bot started...")
        self.application.run_polling()

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('settings.ini')
    
    TOKEN = config.get('telegram', 'token')
    AUTHORIZED_USER = config.get('bot', 'authorized_user')
    
    bot = TelegramBot(TOKEN, AUTHORIZED_USER)
    bot.run()
