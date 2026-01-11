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
from telegram.constants import ChatAction

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
        env['EDITOR'] = 'cat'  # Prevent vim from opening
        env['VISUAL'] = 'cat'  # Prevent vim from opening
        env['TERM'] = 'dumb'   # Indicate non-interactive terminal
        
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
        
        # Start output reader thread
        threading.Thread(target=self._read_output, daemon=True).start()
        
        # Trust all tools to avoid prompts
        self._send_command('/tools trust-all')
        time.sleep(1)
    
    def _read_output(self):
        """Read output from Kiro process"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    print(f"[DEBUG] RAW FROM KIRO: {repr(line.strip())}")
                    self.output_queue.put(line)
            except Exception as e:
                print(f"[DEBUG] Error reading output: {e}")
                break
    
    def _send_command(self, command):
        """Send command to Kiro"""
        if self.process and self.process.poll() is None:
            print(f"[DEBUG] SENDING TO KIRO: {repr(command)}")
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()
    
    def detect_input_prompt(self, line):
        """Detect if Kiro is waiting for user input"""
        patterns = [r'\[y/n/t\]', r'\(y/n\)', r'\[y/N\]', r'>\s*$', r'!>!>', r'!>']
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
        elif '!>!>' in line or '!>' in line:
            # Send Enter to continue past prompts
            self._send_command('')
            return True
        return False
    
    def _strip_ansi(self, text):
        """Remove ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    async def send_message(self, message, update=None, context=None):
        """Send message and get response"""
        # Clear output queue
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
        
        # Send message
        print(f"[DEBUG] USER MESSAGE: {repr(message)}")
        self._send_command(message)
        
        # Commands that don't produce responses - return immediately
        if message.strip().startswith('/agent swap'):
            time.sleep(0.5)  # Brief pause for command to process
            return "Agent swapped successfully"
        
        # Collect response
        response_lines = []
        start_time = time.time()
        last_typing = 0
        last_output_time = time.time()
        
        while time.time() - start_time < 30:
            # Send typing indicator every 4 seconds
            current_time = time.time()
            if update and context and current_time - last_typing > 4:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action=ChatAction.TYPING
                )
                last_typing = current_time
            
            try:
                line = self.output_queue.get(timeout=1)
                clean_line = self._strip_ansi(line.strip())
                print(f"[DEBUG] PROCESSED LINE: {repr(clean_line)}")
                last_output_time = time.time()
                
                # Check for input prompts
                if self.detect_input_prompt(line):
                    if update and context:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"⏳ Waiting for input: {clean_line}"
                        )
                    
                    if self.handle_auto_trust(line):
                        continue
                
                # Extract actual response content from lines with embedded prompts
                if '> ' in clean_line and not clean_line.strip().endswith('> '):
                    # Extract content after the prompt marker
                    parts = clean_line.split('> ', 1)
                    if len(parts) > 1 and parts[1].strip():
                        response_lines.append(parts[1].strip())
                elif clean_line and not (
                    re.match(r'^. Thinking\.\.\.$', clean_line) or 
                    clean_line.strip() == '>' or 
                    clean_line.strip().endswith('> ') or
                    clean_line.startswith('▸ Credits:')):
                    response_lines.append(clean_line)
                
                # Check if response is complete (Kiro prompt returned or credits line)
                if (clean_line.strip() == '>' or 
                    (len(clean_line.strip()) <= 3 and clean_line.strip().endswith('>')) or
                    clean_line.startswith('▸ Credits:')):
                    break
                    
            except Empty:
                # Only break on timeout if we haven't seen any content yet
                if time.time() - start_time > 25 and not response_lines:
                    break
                continue
        
        final_response = '\n'.join(response_lines) if response_lines else "No response received"
        print(f"[DEBUG] FINAL RESPONSE: {repr(final_response)}")
        return final_response

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
        
        # Map backslash to forward slash for Kiro commands
        if message_text.startswith('\\'):
            message_text = '/' + message_text[1:]
        
        print(f"Processing: {message_text}")
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action=ChatAction.TYPING
        )
        
        # Get response from Kiro
        response = await self.kiro.send_message(message_text, update, context)
        
        # Smart truncation - show beginning and end
        if len(response) > 4000:
            beginning = response[:1500]
            end = response[-1500:]
            response = f"{beginning}\n\n...(truncated middle)...\n\n{end}"
        
        # Send response
        await update.message.reply_text(response)
    
    def run(self):
        """Start the bot with error recovery"""
        print("Telegram Kiro Bot started...")
        while True:
            try:
                self.application.run_polling()
            except Exception as e:
                print(f"Bot crashed with error: {e}")
                print("Restarting in 5 seconds...")
                time.sleep(5)

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('settings.ini')
    
    TOKEN = config.get('telegram', 'token')
    AUTHORIZED_USER = config.get('bot', 'authorized_user')
    
    bot = TelegramBot(TOKEN, AUTHORIZED_USER, config)
    bot.run()
