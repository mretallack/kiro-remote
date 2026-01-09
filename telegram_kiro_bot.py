#!/usr/bin/env python3
import subprocess
import threading
import time
import re
import os
import configparser
from queue import Queue, Empty

class KiroSession:
    def __init__(self, config):
        self.process = None
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.config = config
        self.telegram_bot = None
        self.start_session()
    
    def start_session(self):
        """Start persistent Kiro session"""
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
        
        # Start output reader thread
        threading.Thread(target=self._read_output, daemon=True).start()
        
        # Load previous session
        self._send_command('/load telegram_session')
        time.sleep(1)  # Wait for load to complete
    
    def _read_output(self):
        """Read output from Kiro process"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
            except:
                break
    
    def _send_command(self, command):
        """Send command to Kiro"""
        if self.process and self.process.poll() is None:
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()
    
    def detect_input_prompt(self, line):
        """Detect if Kiro is waiting for user input"""
        patterns = [
            r'\(y/n\)',
            r'\[y/N\]', 
            r'Trust this action\?',
            r'Continue\?',
            r'Press Enter to continue',
            r'>\s*$'
        ]
        return any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns)
    
    def handle_auto_trust(self, line):
        """Automatically handle trust prompts if enabled"""
        if not self.config.getboolean('bot', 'auto_trust', fallback=False):
            return False
            
        trust_patterns = [
            r'Trust this action\? \(y/n\)',
            r'Continue\? \[y/N\]',
            r'Proceed\? \(y/n\)'
        ]
        
        for pattern in trust_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self._send_command('y')
                return True
        return False
    
    def _strip_ansi(self, text):
        """Remove ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def send_message(self, message, chat_id=None):
        """Send message and get response with enhanced features"""
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
        last_update = start_time
        
        while time.time() - start_time < 30:
            try:
                line = self.output_queue.get(timeout=1)
                clean_line = self._strip_ansi(line.strip())
                
                # Check for input prompts
                if self.detect_input_prompt(line):
                    if self.telegram_bot and chat_id:
                        self.telegram_bot.send_message(chat_id, f"⏳ Waiting for input: {clean_line}")
                    
                    # Try auto-trust
                    if self.handle_auto_trust(line):
                        continue
                
                # Skip empty lines and prompts
                if clean_line and not clean_line.endswith('>'):
                    response_lines.append(clean_line)
                
                # Progress updates for long operations
                if (self.config.getboolean('bot', 'progress_updates', fallback=False) and 
                    time.time() - last_update > 10 and response_lines and 
                    self.telegram_bot and chat_id):
                    partial = '\n'.join(response_lines[-10:])
                    self.telegram_bot.send_message(chat_id, f"🔄 Latest: {partial}")
                    last_update = time.time()
                
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
        self.kiro.telegram_bot = self  # Set reference for callbacks
        self.offset = 0
    
    def get_updates(self):
        """Get updates from Telegram"""
        try:
            result = subprocess.run([
                'curl', '-s', f'https://api.telegram.org/bot{self.token}/getUpdates',
                '-d', f'offset={self.offset}&timeout=10'
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return data.get('result', [])
        except:
            pass
        return []
    
    def send_message(self, chat_id, text):
        """Send message to Telegram with smart truncation"""
        # Smart truncation - show end instead of beginning
        if len(text) > 4000:
            text = "...(showing end)\n" + text[-3950:]
        
        subprocess.run([
            'curl', '-s', f'https://api.telegram.org/bot{self.token}/sendMessage',
            '-d', f'chat_id={chat_id}',
            '-d', f'text={text}'
        ], capture_output=True)
    
    def run(self):
        """Main bot loop"""
        print("Telegram Kiro Bot started...")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.offset = update['update_id'] + 1
                    
                    if 'message' in update and 'text' in update['message']:
                        chat_id = update['message']['chat']['id']
                        username = update['message']['from'].get('username', 'unknown')
                        text = update['message']['text']
                        
                        # Only respond to authorized user
                        if username != self.authorized_user:
                            continue
                        
                        print(f"Processing: {text}")
                        
                        # Get response from Kiro
                        response = self.kiro.send_message(text, chat_id)
                        
                        # Send response
                        self.send_message(chat_id, response)
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('settings.ini')
    
    TOKEN = config.get('telegram', 'token')
    AUTHORIZED_USER = config.get('bot', 'authorized_user')
    
    bot = TelegramBot(TOKEN, AUTHORIZED_USER, config)
    bot.run()
