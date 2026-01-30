#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import signal
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
    
    def _response_processor(self):
        """Thread to process Kiro output and send to Telegram"""
        while True:
            try:
                line = self.output_queue.get(timeout=1)
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
        if (clean_line.strip() == '>' or 
            (len(clean_line.strip()) <= 3 and clean_line.strip().endswith('>'))):
            self._send_buffered_response()
            return
        
        # Extract content after prompt marker if present
        if '> ' in clean_line and not clean_line.strip().endswith('> '):
            parts = clean_line.split('> ', 1)
            if len(parts) > 1 and parts[1].strip():
                self.response_buffer.append(parts[1].strip())
        elif clean_line and not clean_line.strip().endswith('> '):
            self.response_buffer.append(clean_line)
    
    def _send_buffered_response(self):
        """Send accumulated response to Telegram"""
        if not self.response_buffer or not self.current_chat_id or not self.telegram_bot:
            return
        
        response = '\n'.join(self.response_buffer)
        self.response_buffer = []
        
        # Smart truncation
        if len(response) > 4000:
            beginning = response[:1500]
            end = response[-1500:]
            response = f"{beginning}\n\n...(truncated)...\n\n{end}"
        
        # Queue the response to be sent by Telegram
        self.telegram_bot.send_response_async(self.current_chat_id, response or "No response")
    
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
        # Handle cancel command
        if message.strip() == '\\cancel':
            self.cancel_current_operation()
            return
        
        # Map backslash to forward slash
        if message.startswith('\\'):
            message = '/' + message[1:]
        
        self.input_queue.put(message)
    
    def cancel_current_operation(self):
        """Send SIGINT (Ctrl-C) to Kiro process"""
        if self.process and self.process.poll() is None:
            print(f"[DEBUG] Sending SIGINT to Kiro process (PID: {self.process.pid})")
            self.process.send_signal(signal.SIGINT)
    
    def set_chat_id(self, chat_id):
        """Set current chat ID for responses"""
        self.current_chat_id = chat_id

class TelegramBot:
    def __init__(self, token, authorized_user):
        self.token = token
        self.authorized_user = authorized_user
        self.response_queue = Queue()
        self.kiro = KiroSession()
        self.kiro.telegram_bot = self
        self.application = Application.builder().token(token).build()
        
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Start response sender thread
        threading.Thread(target=self._response_sender, daemon=True).start()
    
    def _response_sender(self):
        """Thread to send queued responses to Telegram"""
        import asyncio
        
        async def send_responses():
            while True:
                try:
                    chat_id, text = self.response_queue.get(timeout=1)
                    await self.application.bot.send_message(chat_id=chat_id, text=text)
                except Empty:
                    continue
                except Exception as e:
                    print(f"[DEBUG] Response sender error: {e}")
        
        # Run the async sender in this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_responses())
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        username = update.effective_user.username
        
        if username != self.authorized_user:
            return
        
        message_text = update.message.text
        print(f"Processing: {message_text}")
        
        # Show typing indicator briefly
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action=ChatAction.TYPING
        )
        
        # Set chat ID and send to Kiro immediately (non-blocking)
        self.kiro.set_chat_id(update.effective_chat.id)
        self.kiro.send_to_kiro(message_text)
    
    def send_response_async(self, chat_id, text):
        """Queue response to be sent to Telegram"""
        self.response_queue.put((chat_id, text))
    
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
