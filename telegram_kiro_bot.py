#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import json
import configparser
import logging
import signal
import pty
import select
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
        self.agents = {}  # agent_name -> agent_data dict
        self.active_agent = None
        self.current_chat_id = None
        self.telegram_bot = None
        self.last_typing_indicator = 0
        self.conversation_history = []
        self.start_session()
    
    def _get_agent_data(self, agent_name):
        """Get or create agent data structure"""
        if agent_name not in self.agents:
            self.agents[agent_name] = {
                'process': None,
                'input_queue': Queue(),
                'output_queue': Queue(),
                'response_buffer': [],
                'last_activity': time.time(),
                'last_periodic_send': time.time(),
                'cached_output': []  # Store output when agent is inactive
            }
        return self.agents[agent_name]
    
    def _get_agent_working_directory(self, agent_name):
        """Get working directory for agent from config"""
        try:
            config_file = Path.home() / ".kiro" / "bot_agent_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    agents = config.get('agents', {})
                    if agent_name in agents:
                        working_dir = agents[agent_name].get('working_directory')
                        if working_dir and Path(working_dir).exists():
                            logger.info(f"Using working directory for {agent_name}: {working_dir}")
                            return working_dir
                    # Fallback to default
                    default_dir = config.get('default_directory', '/home/mark/git/remote-kiro')
                    logger.info(f"Using default directory for {agent_name}: {default_dir}")
                    return default_dir
        except Exception as e:
            logger.error(f"Error reading agent config: {e}")
        
        return '/home/mark/git/remote-kiro'
    
    def start_session(self, agent_name=None):
        """Start persistent Kiro session with threaded I/O"""
        if agent_name is None:
            agent_name = 'kiro_default'
        
        # If agent already running, just switch to it
        if agent_name in self.agents and self.agents[agent_name]['process'] and self.agents[agent_name]['process'].poll() is None:
            self._switch_to_agent(agent_name)
            return
        
        logger.info(f"Starting Kiro session with agent: {agent_name}")
        
        try:
            agent_data = self._get_agent_data(agent_name)
            
            env = os.environ.copy()
            env['NO_COLOR'] = '1'
            env['EDITOR'] = 'cat'
            env['VISUAL'] = 'cat'
            env['TERM'] = 'dumb'
            env['PATH'] = '/home/mark/.local/bin:' + env.get('PATH', '')
            
            # Build command with agent
            cmd = ['/home/mark/.local/bin/kiro-cli', 'chat', '--trust-all-tools']
            if agent_name != 'kiro_default':
                cmd.extend(['--agent', agent_name])
            
            # Get working directory from agent config
            working_dir = self._get_agent_working_directory(agent_name)
            
            agent_data['process'] = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,
                env=env,
                cwd=working_dir,
                preexec_fn=os.setsid
            )
            logger.info(f"Kiro process started with PID: {agent_data['process'].pid}, agent: {agent_name}")
            
            # Start I/O threads for this agent
            threading.Thread(target=self._input_thread, args=(agent_name,), daemon=True).start()
            threading.Thread(target=self._output_thread, args=(agent_name,), daemon=True).start()
            threading.Thread(target=self._response_processor, args=(agent_name,), daemon=True).start()
            
            # Start timeout checker if not already running
            if not hasattr(self, '_timeout_checker_started'):
                threading.Thread(target=self._timeout_checker, daemon=True).start()
                self._timeout_checker_started = True
            
            # Trust all tools
            agent_data['input_queue'].put('/tools trust-all')
            time.sleep(1)
            
            # Switch to this agent
            self.active_agent = agent_name
            
        except Exception as e:
            logger.error(f"Failed to start Kiro session: {e}")
            if self.telegram_bot and self.current_chat_id:
                self.telegram_bot.send_response_threadsafe(
                    self.current_chat_id, 
                    f"❌ Error starting Kiro session: {e}"
                )
    
    def _switch_to_agent(self, agent_name):
        """Switch active agent and send cached output"""
        if agent_name not in self.agents:
            return False
        
        self.active_agent = agent_name
        agent_data = self.agents[agent_name]
        
        # Send any cached output from this agent
        if agent_data['cached_output'] and self.telegram_bot and self.current_chat_id:
            cached_text = '\n'.join(agent_data['cached_output'])
            
            # Snip middle if too large (>4000 chars)
            if len(cached_text) > 4000:
                lines = agent_data['cached_output']
                keep_lines = 20
                if len(lines) > keep_lines * 2:
                    top = '\n'.join(lines[:keep_lines])
                    bottom = '\n'.join(lines[-keep_lines:])
                    cached_text = f"{top}\n\n... ({len(lines) - keep_lines * 2} lines omitted) ...\n\n{bottom}"
            
            self.telegram_bot.send_response_threadsafe(
                self.current_chat_id,
                f"📋 Cached output from '{agent_name}':\n\n{cached_text}"
            )
            agent_data['cached_output'] = []
        
        return True
    
    def stop_session(self):
        """Stop all Kiro sessions"""
        try:
            for agent_name, agent_data in self.agents.items():
                if agent_data['process'] and agent_data['process'].poll() is None:
                    print(f"[DEBUG] Stopping Kiro process {agent_data['process'].pid} for agent {agent_name}")
                    agent_data['process'].terminate()
                    try:
                        agent_data['process'].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"[DEBUG] Force killing Kiro process for agent {agent_name}")
                        agent_data['process'].kill()
                        agent_data['process'].wait()
                agent_data['process'] = None
        except Exception as e:
            print(f"[ERROR] Error stopping sessions: {e}")
    
    def restart_session(self, agent_name=None):
        """Restart Kiro session with optional different agent - now just switches"""
        if agent_name is None:
            agent_name = 'kiro_default'
        print(f"[DEBUG] Switching to agent: {agent_name}")
        self.start_session(agent_name)
    
    def _input_thread(self, agent_name):
        """Thread to handle input to Kiro"""
        agent_data = self.agents[agent_name]
        while agent_data['process'] and agent_data['process'].poll() is None:
            try:
                command = agent_data['input_queue'].get(timeout=1)
                if command:
                    print(f"[DEBUG] SENDING to {agent_name}: {repr(command)}")
                    agent_data['process'].stdin.write(command + '\n')
                    agent_data['process'].stdin.flush()
            except Empty:
                continue
            except Exception as e:
                print(f"[DEBUG] Input thread error for {agent_name}: {e}")
                break
    
    def _output_thread(self, agent_name):
        """Thread to handle output from Kiro"""
        agent_data = self.agents[agent_name]
        while agent_data['process'] and agent_data['process'].poll() is None:
            try:
                line = agent_data['process'].stdout.readline()
                if line:
                    agent_data['output_queue'].put(line)
            except Exception as e:
                print(f"[DEBUG] Output thread error for {agent_name}: {e}")
                break
    
    def _timeout_checker(self):
        """Check for response timeout and send buffered content"""
        while True:
            time.sleep(2)  # Check every 2 seconds
            current_time = time.time()
            
            if not self.active_agent or self.active_agent not in self.agents:
                continue
            
            agent_data = self.agents[self.active_agent]
            
            # Send buffered content if we have a 3-second timeout OR 20 seconds since last send
            should_send_timeout = (agent_data['response_buffer'] and 
                                 current_time - agent_data['last_activity'] > 3 and  
                                 self.current_chat_id)
            
            should_send_periodic = (agent_data['response_buffer'] and 
                                  current_time - agent_data['last_periodic_send'] > 20 and
                                  self.current_chat_id)
            
            if should_send_timeout:
                print(f"[DEBUG] Timeout detected for {self.active_agent}, sending buffered response")
                self._send_buffered_response(self.active_agent)
            elif should_send_periodic:
                print(f"[DEBUG] 20-second periodic update for {self.active_agent}, sending buffered response")
                self._send_buffered_response(self.active_agent)
    
    def _response_processor(self, agent_name):
        """Thread to process Kiro output and send to Telegram"""
        agent_data = self.agents[agent_name]
        while True:
            try:
                line = agent_data['output_queue'].get(timeout=1)
                agent_data['last_activity'] = time.time()
                self._handle_line(agent_name, line)
            except Empty:
                continue
            except Exception as e:
                print(f"[DEBUG] Response processor error for {agent_name}: {e}")
                break
    
    def _handle_line(self, agent_name, line):
        """Handle a single line from Kiro"""
        agent_data = self.agents[agent_name]
        clean_line = self._strip_ansi(line.strip())
        print(f"[DEBUG] {agent_name} RAW: {repr(clean_line)}")
        
        # Send typing indicator every 4 seconds while processing (only for active agent)
        if agent_name == self.active_agent:
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
        if self._handle_auto_trust(agent_name, line):
            return
        
        # Check if this is end of response (prompt returned)
        if (clean_line.strip() == '>' or 
            clean_line.strip() == '!>' or
            clean_line.strip().endswith('> ') or
            clean_line.strip().endswith('!> ') or
            (len(clean_line.strip()) <= 3 and ('>' in clean_line or '!>' in clean_line))):
            print(f"[DEBUG] Detected end of response with prompt: {repr(clean_line)}")
            self._send_buffered_response(agent_name)
            return
        
        # Extract content after prompt marker if present
        content = None
        if '> ' in clean_line and not clean_line.strip().endswith('> '):
            parts = clean_line.split('> ', 1)
            if len(parts) > 1 and parts[1].strip():
                content = parts[1].strip()
        elif '!> ' in clean_line and not clean_line.strip().endswith('!> '):
            parts = clean_line.split('!> ', 1)
            if len(parts) > 1 and parts[1].strip():
                content = parts[1].strip()
        elif clean_line and not clean_line.strip().endswith('> ') and not clean_line.strip().endswith('!> '):
            content = clean_line
        
        if content:
            print(f"[DEBUG] Adding to buffer for {agent_name}: {repr(content)}")
            # If this is the active agent, add to response buffer
            # Otherwise, add to cached output
            if agent_name == self.active_agent:
                agent_data['response_buffer'].append(content)
            else:
                agent_data['cached_output'].append(content)
                # Save to file if cached output gets large (>100 lines)
                if len(agent_data['cached_output']) > 100:
                    self._save_cached_output_to_file(agent_name)
    
    def _save_cached_output_to_file(self, agent_name):
        """Save large cached output to file"""
        agent_data = self.agents[agent_name]
        if not agent_data['cached_output']:
            return
        
        cache_dir = Path.home() / ".kiro" / "bot_agent_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{agent_name}_{int(time.time())}.txt"
        
        with open(cache_file, 'w') as f:
            f.write('\n'.join(agent_data['cached_output']))
        
        # Keep only summary in memory
        agent_data['cached_output'] = [
            f"[Large output saved to {cache_file}]",
            f"First lines: {agent_data['cached_output'][0]}",
            "...",
            f"Last lines: {agent_data['cached_output'][-1]}"
        ]
    
    def _send_buffered_response(self, agent_name):
        """Send accumulated response to Telegram"""
        agent_data = self.agents[agent_name]
        print(f"[DEBUG] _send_buffered_response called for {agent_name}. Buffer: {len(agent_data['response_buffer'])} lines, chat_id: {self.current_chat_id}")
        
        if not agent_data['response_buffer'] or not self.current_chat_id or not self.telegram_bot:
            print(f"[DEBUG] Skipping send - buffer empty or no chat")
            return
        
        # Only send if this is the active agent
        if agent_name != self.active_agent:
            print(f"[DEBUG] Agent {agent_name} is not active, caching output")
            return
        
        response = '\n'.join(agent_data['response_buffer'])
        agent_data['response_buffer'] = []
        agent_data['last_periodic_send'] = time.time()
        
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
    
    def _handle_auto_trust(self, agent_name, line):
        """Auto-handle trust prompts"""
        agent_data = self.agents[agent_name]
        if '[y/n/t]' in line:
            agent_data['input_queue'].put('t')
            return True
        elif '(y/n)' in line or '[y/N]' in line:
            agent_data['input_queue'].put('y')
            return True
        elif '!>!>' in line or '!>' in line:
            agent_data['input_queue'].put('')
            return True
        return False
    
    def _strip_ansi(self, text):
        """Remove ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def send_to_kiro(self, message):
        """Send message to active Kiro agent (non-blocking)"""
        if not self.active_agent or self.active_agent not in self.agents:
            print("[DEBUG] No active agent to send message to")
            return
        
        # Handle cancel command
        if message.strip() == '\\cancel':
            self.cancel_current_operation()
            return
        
        # Map backslash to forward slash
        if message.startswith('\\'):
            message = '/' + message[1:]
        
        # Track conversation history (exclude bot commands)
        if not message.startswith('/'):
            self.conversation_history.append({"user": message, "timestamp": time.time()})
        
        agent_data = self.agents[self.active_agent]
        agent_data['input_queue'].put(message)
    
    def cancel_current_operation(self):
        """Send SIGINT (Ctrl-C) to active Kiro process"""
        if not self.active_agent or self.active_agent not in self.agents:
            return
        
        agent_data = self.agents[self.active_agent]
        if agent_data['process'] and agent_data['process'].poll() is None:
            print(f"[DEBUG] Sending SIGINT to Kiro process group (PID: {agent_data['process'].pid})")
            try:
                # Send SIGINT to the entire process group
                os.killpg(os.getpgid(agent_data['process'].pid), signal.SIGINT)
                print(f"[DEBUG] SIGINT sent successfully to process group")
            except Exception as e:
                print(f"[ERROR] Failed to send SIGINT to process group: {e}")
                # Fallback to sending to process directly
                try:
                    agent_data['process'].send_signal(signal.SIGINT)
                    print(f"[DEBUG] SIGINT sent to process directly")
                except Exception as e2:
                    print(f"[ERROR] Failed to send SIGINT to process: {e2}")
            
            if self.telegram_bot and self.current_chat_id:
                self.telegram_bot.send_response_threadsafe(self.current_chat_id, "⚠️ Cancelled")
    
    def save_state(self, name="__auto_save__"):
        """Save current conversation state to file"""
        try:
            print(f"[DEBUG] save_state called with name: {name}")
            state_dir = Path.home() / ".kiro" / "bot_conversations"
            state_dir.mkdir(parents=True, exist_ok=True)
            
            state = {
                "active_agent": self.active_agent,
                "timestamp": time.time(),
                "conversation_history": self.conversation_history,
                "working_directory": "/home/mark/git/remote-kiro"
            }
            
            state_file = state_dir / f"{name}.json"
            print(f"[DEBUG] Saving to: {state_file}")
            
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
            import traceback
            traceback.print_exc()
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
            
            # Support both old and new format
            self.active_agent = state.get("active_agent") or state.get("current_agent", "kiro_default")
            self.conversation_history = state.get("conversation_history", [])
            
            # Validate conversation history
            if not isinstance(self.conversation_history, list):
                self.conversation_history = []
            
            print(f"[DEBUG] State loaded from {state_file}, agent: {self.active_agent}")
            return True
        except Exception as e:
            print(f"[ERROR] Error loading state: {e}")
            # Reset to defaults on error
            self.active_agent = "kiro_default"
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
        """Switch to agent (starts if not running)"""
        try:
            # Save current state
            self.save_state()
            
            # Start or switch to agent
            self.start_session(agent_name)
            
            # Wait for initialization
            time.sleep(1.5)
            
            print(f"[DEBUG] Switched to agent: {agent_name}")
            return True
        except Exception as e:
            print(f"[ERROR] Error switching to agent: {e}")
            return False
    
    def save_conversation(self, name):
        """Save conversation with custom name"""
        return self.save_state(name)
    
    def load_conversation(self, name):
        """Load conversation with custom name"""
        if self.load_state(name):
            # Switch to the loaded agent
            if self.active_agent:
                self.start_session(self.active_agent)
            return True
        return False
    
    def set_chat_id(self, chat_id):
        """Set current chat ID for responses"""
        self.current_chat_id = chat_id

class TelegramBot:
    def __init__(self, token, authorized_user, attachments_dir=None):
        self.token = token
        self.authorized_user = authorized_user
        self.attachments_dir = Path(attachments_dir or '~/.kiro/bot_attachments').expanduser()
        self._setup_attachments_dir()
        self.kiro = KiroSession()
        self.kiro.telegram_bot = self
        
        # Conversation state for multi-step interactions
        self.user_states = {}  # chat_id -> state dict
        
        # Try to restore previous session
        if self.kiro.load_state():
            print(f"[DEBUG] Restored previous session with agent: {self.kiro.active_agent}")
            self.kiro.start_session(self.kiro.active_agent)
        
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
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
    
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
        safe = re.sub(r'[/\\:*?"<>|]', '_', filename)
        safe = safe.replace(' ', '_')
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
            message = message.replace('\n', '\\n')
            
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
            message = message.replace('\n', '\\n')
            
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
                    current_marker = " <- active" if agent == self.kiro.active_agent else ""
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
            print(f"[DEBUG] save_chat called with name: {chat_name}")
            if self.kiro.save_conversation(chat_name):
                await update.message.reply_text(f"✅ Conversation saved as '{chat_name}'")
            else:
                await update.message.reply_text(f"❌ Failed to save conversation")
        except Exception as e:
            print(f"[ERROR] Exception in save_chat: {e}")
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
                
                # Create agent-specific steering directory and overview.md
                steering_dir = agents_dir / state['agent_name'] / "steering"
                steering_dir.mkdir(parents=True, exist_ok=True)
                
                overview_file = steering_dir / "overview.md"
                with open(overview_file, 'w') as f:
                    f.write(f"# {state['agent_name']}\n\n{state['description']}\n")
                
                # Create working directory under /home/mark/git
                working_dir = Path("/home/mark/git") / state['agent_name']
                working_dir.mkdir(parents=True, exist_ok=True)
                
                # Update bot_agent_config.json
                config_file = Path.home() / ".kiro" / "bot_agent_config.json"
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                else:
                    config = {"agents": {}, "default_directory": "/home/mark/git/remote-kiro"}
                
                config["agents"][state['agent_name']] = {
                    "working_directory": str(working_dir)
                }
                
                with open(config_file, 'w') as f:
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
            "resources": [
                "file://~/.kiro/steering/**/*.md",
                f"file://~/.kiro/agents/{name}/steering/*.md",
                f"file://~/git/{name}/.kiro/steering/**/*.md"
            ],
            "hooks": {},
            "toolsSettings": {},
            "useLegacyMcpJson": True,
            "model": None
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
            if self.kiro.active_agent == agent_name:
                await update.message.reply_text(f"✅ Now using agent: {agent_name}")
            else:
                await update.message.reply_text(f"⚠️ Agent switch may have failed. Active agent: {self.kiro.active_agent}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error switching agent: {e}")
            # Try to restart with default agent as fallback
            try:
                self.kiro.restart_session()
                await update.message.reply_text("🔄 Fallback: Restarted with default agent")
            except Exception as fallback_error:
                await update.message.reply_text(f"💥 Critical error: {fallback_error}")
    

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
    ATTACHMENTS_DIR = config.get('bot', 'attachments_dir', fallback='~/.kiro/bot_attachments')
    
    bot = TelegramBot(TOKEN, AUTHORIZED_USER, ATTACHMENTS_DIR)
    bot.run()
