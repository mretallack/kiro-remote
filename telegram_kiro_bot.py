#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import configparser
from queue import Queue, Empty
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, ContextTypes

class KiroSession:
    def __init__(self):
        self.process = None
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.current_chat_id = None
        self.telegram_bot = None
        self.response_buffer = []
        self.last_activity = time.time()
        self.start_session()
    
    def start_session(self):
        """Start persistent Kiro session with threaded I/O"""
        print("[DEBUG] Starting Kiro session")
        env = os.environ.copy()
        env['NO_COLOR'] = '1'
        env['EDITOR'] = 'cat'
        env['VISUAL'] = 'cat'
        env['TERM'] = 'dumb'
        
        self.process = subprocess.Popen(
            ['kiro-cli', 'chat', '--trust-all-tools'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0,
            env=env,
            cwd='/home/mark/git/remote-kiro'
        )
        print(f"[DEBUG] Kiro process started with PID: {self.process.pid}")
        
        # Start I/O threads
        threading.Thread(target=self._input_thread, daemon=True).start()
        threading.Thread(target=self._output_thread, daemon=True).start()
        threading.Thread(target=self._response_processor, daemon=True).start()
        threading.Thread(target=self._timeout_checker, daemon=True).start()
        
        # Trust all tools
        self.send_to_kiro('/tools trust-all')
        time.sleep(1)
    
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
        
        self.input_queue.put(message)
    
    def set_chat_id(self, chat_id):
        """Set current chat ID for responses"""
        self.current_chat_id = chat_id

class TelegramBot:
    def __init__(self, token, authorized_user):
        self.token = token
        self.authorized_user = authorized_user
        self.kiro = KiroSession()
        self.kiro.telegram_bot = self
        self.application = Application.builder().token(token).build()
        self.loop = None
        
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
    
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
