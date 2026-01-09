# Telegram Kiro Bot Enhancement Proposal

## Issues to Address

### 1. Silent Input Waiting
When Kiro waits for user input (y/n prompts, confirmations), Telegram shows no indication. User doesn't know system is waiting.

### 2. Constant Confirmations  
Bot asks for y/n confirmations on all actions, creating friction.

### 3. Output Truncation
Long outputs get cut off at beginning, missing important end results.

## Solutions

### 1. Input Prompt Detection
Detect when Kiro is waiting and send immediate notification:
```python
def detect_input_prompt(self, line):
    patterns = [r'\(y/n\)', r'\[y/N\]', r'Trust this action\?', r'Continue\?']
    return any(re.search(p, line, re.IGNORECASE) for p in patterns)

# In send_message method:
if self.detect_input_prompt(line):
    self.send_telegram_message(chat_id, f"⏳ Waiting for input: {line.strip()}")
```

### 2. Auto-Trust Mode
Add config to auto-approve safe prompts:
```ini
[bot]
auto_trust = true
```

```python
def handle_auto_trust(self, line):
    if self.config.getboolean('bot', 'auto_trust', fallback=False):
        if re.search(r'Trust this action\? \(y/n\)', line):
            self._send_command('y')
            return True
    return False
```

### 3. Smart Truncation
Show last 4000 chars instead of first 4000:
```python
def send_message(self, chat_id, text):
    if len(text) > 4000:
        text = "...(showing end)\n" + text[-3950:]
    # send message
```

### 4. Timeout Updates
For long operations, show progress every 10 seconds:
```python
# Send partial updates during long waits
if time.time() - last_update > 10 and response_lines:
    partial = '\n'.join(response_lines[-10:])
    self.send_message(chat_id, f"🔄 Latest: {partial}")
```

## Implementation Order
1. Input prompt detection (critical)
2. Smart truncation (high impact)  
3. Auto-trust mode (convenience)
4. Progress updates (nice-to-have)

## Config Changes
```ini
[bot]
authorized_user = markretallack
auto_trust = true
progress_updates = true
```
