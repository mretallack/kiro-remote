# Agent Management Feature Tasks

## Implementation Plan

### Phase 1: Command Interception Infrastructure

#### Task 1.1: Add Command Interception Logic
- [x] **Description**: Implement message filtering to intercept `/agent` and `/chat` commands (with both "/" and "\" prefixes) before passing to kiro-cli
- **Expected Outcome**: Bot can identify and handle specific commands with either prefix without sending them to kiro-cli
- **Dependencies**: None
- **Files**: `telegram_kiro_bot.py`

#### Task 1.2: Add Process Management to Bot
- [x] **Description**: Extend bot to manage kiro-cli as subprocess with restart capability
- **Expected Outcome**: Bot can start/stop/restart kiro-cli process programmatically
- **Dependencies**: None
- **Files**: `telegram_kiro_bot.py`

#### Task 1.3: Add Agent State Tracking
- [x] **Description**: Track current active agent in bot memory and persist to file
- **Expected Outcome**: Bot knows which agent is currently active and can restore on restart
- **Dependencies**: Task 1.2
- **Files**: `telegram_kiro_bot.py`

#### Task 1.4: Add Conversation History Management
- [x] **Description**: Store conversation messages in bot memory for replay capability
- **Expected Outcome**: Bot maintains conversation history and can replay messages
- **Dependencies**: None
- **Files**: `telegram_kiro_bot.py`

### Phase 2: Agent Management Commands

#### Task 2.1: Implement `/agent create <name>` Interception
- [x] **Description**: Intercept `/agent create <name>` and `\agent create <name>` commands and handle agent creation with prompts
- **Expected Outcome**: Users can create agents via native kiro command with either prefix, bot handles the interaction
- **Dependencies**: Task 1.1, Task 1.2, Task 1.3
- **Files**: `telegram_kiro_bot.py`

#### Task 2.2: Implement `/agent list` Interception
- [x] **Description**: Intercept `/agent list` and `\agent list` commands and display available agents (built-in + custom)
- **Expected Outcome**: Users can list agents via native kiro command with either prefix, bot provides the response
- **Dependencies**: Task 1.1
- **Files**: `telegram_kiro_bot.py`

#### Task 2.3: Implement `/agent swap <name>` Interception
- [x] **Description**: Intercept `/agent swap <name>` and `\agent swap <name>` commands and switch agents with kiro-cli restart
- **Expected Outcome**: Users can switch agents via native kiro command with either prefix, bot handles the process
- **Dependencies**: Task 1.1, Task 1.2, Task 1.3
- **Files**: `telegram_kiro_bot.py`

#### Task 2.4: Implement `/agent delete <name>` Interception
- [x] **Description**: Intercept `/agent delete <name>` and `\agent delete <name>` commands and remove custom agents
- **Expected Outcome**: Users can delete custom agents via native kiro command with either prefix
- **Dependencies**: Task 1.1
- **Files**: `telegram_kiro_bot.py`

### Phase 3: Conversation Management Commands

#### Task 3.1: Implement `/chat save <name>` Interception
- [x] **Description**: Intercept `/chat save <name>` and `\chat save <name>` commands and save conversation state to file
- **Expected Outcome**: Users can save conversations via native kiro command with either prefix
- **Dependencies**: Task 1.1, Task 1.4
- **Files**: `telegram_kiro_bot.py`

#### Task 3.2: Implement `/chat load <name>` Interception
- [x] **Description**: Intercept `/chat load <name>` and `\chat load <name>` commands and restore saved conversation
- **Expected Outcome**: Users can restore conversations via native kiro command with either prefix
- **Dependencies**: Task 1.1, Task 1.2, Task 1.4, Task 3.1
- **Files**: `telegram_kiro_bot.py`

#### Task 3.3: Implement `/chat list` Interception
- [x] **Description**: Intercept `/chat list` and `\chat list` commands and display saved conversations
- **Expected Outcome**: Users can list saved conversations via native kiro command with either prefix
- **Dependencies**: Task 1.1, Task 3.1
- **Files**: `telegram_kiro_bot.py`

### Phase 4: Auto-Recovery Features

#### Task 4.1: Implement Auto-Save on Agent Switch
- [x] **Description**: Automatically save conversation state when switching agents
- **Expected Outcome**: Conversation context preserved across agent switches
- **Dependencies**: Task 2.3, Task 3.1
- **Files**: `telegram_kiro_bot.py`

#### Task 4.2: Implement Auto-Restore on Bot Startup
- [x] **Description**: Check for auto-save file on bot startup and restore previous state
- **Expected Outcome**: Bot resumes previous session after restart
- **Dependencies**: Task 1.3, Task 3.2
- **Files**: `telegram_kiro_bot.py`

#### Task 4.3: Add Error Handling and Recovery
- [x] **Description**: Handle process failures, corrupted files, and provide fallback options
- **Expected Outcome**: Robust error handling with graceful degradation
- **Dependencies**: All previous tasks
- **Files**: `telegram_kiro_bot.py`

### Phase 5: Testing and Documentation

#### Task 5.1: Create Agent JSON Template
- [x] **Description**: Define standard agent JSON structure and validation
- **Expected Outcome**: Consistent agent file format with proper validation
- **Dependencies**: Task 2.1
- **Files**: `telegram_kiro_bot.py`, documentation

#### Task 5.2: Add Logging and Monitoring
- [x] **Description**: Add comprehensive logging for debugging and monitoring
- **Expected Outcome**: Clear logs for troubleshooting agent and conversation management
- **Dependencies**: All implementation tasks
- **Files**: `telegram_kiro_bot.py`

#### Task 5.3: Update Documentation
- [ ] **Description**: Update README.md to reflect native kiro command usage with both "/" and "\" prefixes instead of custom bot commands
- **Expected Outcome**: Clear user documentation showing `/agent` and `/chat` commands work natively with either prefix
- **Dependencies**: All implementation tasks
- **Files**: `README.md`

## Implementation Notes

- **Command Interception**: Bot checks incoming messages for `/agent` and `/chat` patterns (with both "/" and "\" prefixes) before passing to kiro-cli
- **File Locations**: 
  - Agent files: `~/.kiro/agents/<name>.json`
  - Conversation saves: `~/.kiro/bot_conversations/<name>.json`
  - Auto-save: `~/.kiro/bot_conversations/__auto_save__.json`

- **Intercepted Commands**:
  - `/agent create <name>` or `\agent create <name>` - Bot handles agent creation
  - `/agent list` or `\agent list` - Bot lists available agents
  - `/agent swap <name>` or `\agent swap <name>` - Bot switches agents
  - `/agent delete <name>` or `\agent delete <name>` - Bot removes agents
  - `/chat save <name>` or `\chat save <name>` - Bot saves conversation
  - `/chat load <name>` or `\chat load <name>` - Bot loads conversation
  - `/chat list` or `\chat list` - Bot lists conversations

- **Agent JSON Structure**:
  ```json
  {
    "name": "agent-name",
    "description": "Agent description", 
    "instructions": "System instructions for the agent",
    "tools": ["tool1", "tool2"]
  }
  ```

- **Conversation State Structure**:
  ```json
  {
    "current_agent": "agent-name",
    "timestamp": "2026-01-11T18:00:00Z",
    "messages": [
      {"user": "message", "bot": "response"},
      ...
    ],
    "working_directory": "/path/to/dir"
  }
  ```

## Success Criteria

- [ ] Users can use native `/agent` and `/chat` commands seamlessly with either "/" or "\" prefixes
- [ ] Bot intercepts commands with both prefixes without passing them to kiro-cli
- [ ] Agent creation works without editor interaction
- [ ] Agent switching works without manual kiro-cli restarts
- [ ] Conversation context preserved across agent switches
- [ ] Bot can restart and resume previous session
- [ ] All commands work reliably in telegram bot environment with both prefixes
- [ ] Error handling provides clear feedback to users
- [ ] Telegram bot command conflicts resolved by supporting "\" alternative
