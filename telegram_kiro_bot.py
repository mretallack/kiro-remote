#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import json
import configparser
from pathlib import Path
from queue import Queue, Empty
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

class KiroSession:
    def __init__(self):
        self.process = None
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.current_chat_id = None
        self.telegram_bot = None
        self.response_buffer = []
        self.last_activity = time.time()
        self.current_agent = None  # Track current agent
        self.conversation_history = []  # Track conversation for replay
        self.start_session()
    
    def start_session(self, agent_name=None):
        """Start persistent Kiro session with threaded I/O"""
        print(f"[DEBUG] Starting Kiro session with agent: {agent_name}")
        
        # Stop existing session if running
        if self.process and self.process.poll() is None:
            self.stop_session()
        
        env = os.environ.copy()
        env['NO_COLOR'] = '1'
        env['EDITOR'] = 'cat'
        env['VISUAL'] = 'cat'
        env['TERM'] = 'dumb'
        
        # Build command with optional agent
        cmd = ['kiro-cli', 'chat', '--trust-all-tools']
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
        print(f"[DEBUG] Kiro process started with PID: {self.process.pid}, agent: {self.current_agent}")
        
        # Start I/O threads
        threading.Thread(target=self._input_thread, daemon=True).start()
        threading.Thread(target=self._output_thread, daemon=True).start()
        threading.Thread(target=self._response_processor, daemon=True).start()
        threading.Thread(target=self._timeout_checker, daemon=True).start()
        
        # Trust all tools
        self.send_to_kiro('/tools trust-all')
        time.sleep(1)
    
    def stop_session(self):
        """Stop the current Kiro session"""
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
    
    def restart_session(self, agent_name=None):
        """Restart Kiro session with optional different agent"""
        print(f"[DEBUG] Restarting session with agent: {agent_name}")
        self.stop_session()
        time.sleep(1)  # Brief pause
        self.start_session(agent_name)
    
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
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"[DEBUG] State saved to {state_file}")
            return True
        except Exception as e:
            print(f"[DEBUG] Error saving state: {e}")
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
            
            self.current_agent = state.get("current_agent", "kiro_default")
            self.conversation_history = state.get("conversation_history", [])
            
            print(f"[DEBUG] State loaded from {state_file}, agent: {self.current_agent}")
            return True
        except Exception as e:
            print(f"[DEBUG] Error loading state: {e}")
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
    
    def set_chat_id(self, chat_id):
        """Set current chat ID for responses"""
        self.current_chat_id = chat_id

class TelegramBot:
    def __init__(self, token, authorized_user):
        self.token = token
        self.authorized_user = authorized_user
        self.kiro = KiroSession()
        self.kiro.telegram_bot = self
        
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
        self.application.add_handler(CommandHandler("create_agent", self.create_agent))
        self.application.add_handler(CommandHandler("list_agents", self.list_agents))
        self.application.add_handler(CommandHandler("switch_agent", self.switch_agent))
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
        print(f"[DEBUG] Received message from user: {username}")
        
        if username != self.authorized_user:
            print(f"[DEBUG] Unauthorized user {username}, ignoring")
            return
        
        message_text = update.message.text.replace('\n', '\\n')
        print(f"[DEBUG] Processing message: {message_text}")
        
        # Show typing indicator briefly
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action=ChatAction.TYPING
        )
        
        # Set chat ID and send to Kiro immediately (non-blocking)
        print(f"[DEBUG] Setting chat_id to {update.effective_chat.id}")
        self.kiro.set_chat_id(update.effective_chat.id)
        print(f"[DEBUG] Sending to Kiro: {message_text}")
        self.kiro.send_to_kiro(message_text)
    
    async def create_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /create_agent command"""
        if update.effective_user.username != self.authorized_user:
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /create_agent <agent_name>")
            return
        
        agent_name = args[0]
        await update.message.reply_text(f"Creating agent '{agent_name}'...\nWhat's the agent description?")
        # TODO: Implement interactive agent creation
    
    async def list_agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list_agents command"""
        if update.effective_user.username != self.authorized_user:
            return
        
        try:
            # Get agents from kiro-cli
            result = subprocess.run(['kiro-cli', 'agent', 'list'], 
                                  capture_output=True, text=True, cwd='/home/mark/git/remote-kiro')
            
            if result.returncode == 0:
                await update.message.reply_text(f"Available agents:\n```\n{result.stdout}\n```", parse_mode='Markdown')
            else:
                await update.message.reply_text(f"Error listing agents: {result.stderr}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    
    async def switch_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /switch_agent command"""
        if update.effective_user.username != self.authorized_user:
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /switch_agent <agent_name>")
            return
        
        agent_name = args[0]
        
        # Auto-save current state
        self.kiro.save_state()
        
        await update.message.reply_text(f"Switching to agent '{agent_name}'...")
        
        # Restart with new agent
        self.kiro.restart_session(agent_name)
        
        await update.message.reply_text(f"Now using agent: {agent_name}")
    
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
    
    async def _send_message_async(self, chat_id, text):
        """Internal async method to send message"""
        try:
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
