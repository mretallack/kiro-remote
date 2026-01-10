#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import configparser
from queue import Queue, Empty
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

class KiroSession:
    def __init__(self, config):
        self.process = None
        self.output_queue = Queue()
        self.config = config
        self.telegram_bot = None
        self.start_session()
    
    def start_session(self):
        """Start persistent Kiro session"""
        print("[DEBUG] Starting Kiro session")
        env = os.environ.copy()
        env['NO_COLOR'] = '1'
        
        self.process = subprocess.Popen(
            ['kiro-cli', 'chat'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0,
            env=env,
            cwd='/home/mark/git/remote-kiro'
        )
        print(f"[DEBUG] Kiro process started with PID: {self.process.pid}")
        
        # Start output reader thread
        threading.Thread(target=self._read_output, daemon=True).start()
        
        # Load previous session
        self._send_command('/load telegram_session')
        time.sleep(1)
        
        # Trust all tools to avoid prompts
        self._send_command('/tools trust-all')
        time.sleep(1)
    
    def _read_output(self):
        """Read output from Kiro process"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
            except Exception as e:
                print(f"[DEBUG] Error reading output: {e}")
                break
    
    def _send_command(self, command):
        """Send command to Kiro"""
        if self.process and self.process.poll() is None:
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()
    
    def detect_input_prompt(self, line):
        """Detect if Kiro is waiting for user input"""
        patterns = [r'\[y/n/t\]', r'\(y/n\)', r'\[y/N\]', r'>\s*$']
        return any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns)
    
    def handle_auto_trust(self, line):
        """Automatically handle trust prompts if enabled"""
        if not self.config.getboolean('bot', 'auto_trust', fallback=False):
            return False
            
        if '[y/n/t]' in line:
            self._send_command('t')
            return True
        elif '(y/n)' in line or '[y/N]' in line:
            self._send_command('y')
            return True
        return False
    
    def _strip_ansi(self, text):
        """Remove ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    async def send_message(self, message, context=None):
        """Send message and get response"""
        # Clear output queue
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
        
        # Send message
        self._send_command(message)
        
        # Collect response
        response_lines = []
        start_time = time.time()
        
        while time.time() - start_time < 30:
            try:
                line = self.output_queue.get(timeout=1)
                clean_line = self._strip_ansi(line.strip())
                
                # Check for input prompts
                if self.detect_input_prompt(line):
                    if context:
                        await context.bot.send_message(
                            chat_id=context.effective_chat.id,
                            text=f"⏳ Waiting for input: {clean_line}"
                        )
                    
                    if self.handle_auto_trust(line):
                        continue
                
                # Skip empty lines and prompts
                if clean_line and not clean_line.endswith('>'):
                    response_lines.append(clean_line)
                
                # Check if response is complete
                if line.strip().endswith('>'):
                    break
                    
            except Empty:
                continue
        
        # Save session after each interaction
        self._send_command('/save telegram_session')
        
        return '\n'.join(response_lines) if response_lines else "No response received"

class TelegramBot:
    def __init__(self, token, authorized_user, config):
        self.token = token
        self.authorized_user = authorized_user
        self.config = config
        self.kiro = KiroSession(config)
        self.application = Application.builder().token(token).build()
        
        # Add message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        username = update.effective_user.username
        
        # Only respond to authorized user
        if username != self.authorized_user:
            return
        
        message_text = update.message.text
        print(f"Processing: {message_text}")
        
        # Get response from Kiro
        response = await self.kiro.send_message(message_text, context)
        
        # Smart truncation - show end instead of beginning
        if len(response) > 4000:
            response = "...(showing end)\n" + response[-3950:]
        
        # Send response
        await update.message.reply_text(response)
    
    def run(self):
        """Start the bot"""
        print("Telegram Kiro Bot started...")
        self.application.run_polling()

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('settings.ini')
    
    TOKEN = config.get('telegram', 'token')
    AUTHORIZED_USER = config.get('bot', 'authorized_user')
    
    bot = TelegramBot(TOKEN, AUTHORIZED_USER, config)
    bot.run()
