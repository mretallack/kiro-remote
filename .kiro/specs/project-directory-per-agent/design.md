# Design: Project Directory Per Agent

## Architecture Overview

This feature extends the existing agent management system to support per-agent working directories. The bot will maintain a configuration file mapping agents to their project directories and use this information when starting Kiro CLI sessions.

## Component Design

### 1. Agent Configuration File
**Location**: `~/.kiro/bot_agent_config.json`

**Structure**:
```json
{
  "agents": {
    "agent_name": {
      "working_directory": "/home/mark/git/project-name",
      "description": "Optional description override"
    },
    "another_agent": {
      "working_directory": "/home/mark/git/another-project"
    }
  },
  "default_directory": "/home/mark/git/remote-kiro"
}
```

### 2. Configuration Loading
- Load on bot startup
- Validate directory paths exist
- Fall back to default if path invalid
- Log warnings for missing/invalid paths

### 3. Kiro CLI Session Management
**Current Flow**:
```
start_kiro_process() → subprocess.Popen(['kiro-cli', 'chat', ...])
```

**Updated Flow**:
```
start_kiro_process(agent_name, working_dir) → 
  subprocess.Popen(['kiro-cli', 'chat', ...], cwd=working_dir)
```

### 4. Agent Switching Integration
**Sequence Diagram**:
```
User → Bot: \agent swap project_agent
Bot → Config: Get working_directory for project_agent
Config → Bot: /home/mark/git/facebook
Bot → Kiro: Stop current session
Bot → Kiro: Start new session with cwd=/home/mark/git/facebook
Bot → User: ✅ Switched to 'project_agent' in /home/mark/git/facebook
```

### 5. Agent Listing Enhancement
**Current Output**:
```
📋 Available Agents:
• default - Default Kiro agent
• my_helper - A helpful coding assistant
```

**Enhanced Output**:
```
📋 Available Agents:
• default - Default Kiro agent
  📁 /home/mark/git/remote-kiro
• my_helper - A helpful coding assistant
  📁 /home/mark/git/facebook
```

## Implementation Considerations

### Configuration Management
- Use JSON for easy editing and validation
- Create config file with defaults if missing
- Support both absolute and tilde-expanded paths
- Validate directories exist before using

### Error Handling
- Invalid directory → log warning, use default
- Missing config file → create with defaults
- Permission errors → log error, use default
- Agent not in config → use default directory

### Backward Compatibility
- Existing agents without config entries work normally
- Conversation states without working_directory field handled gracefully
- No breaking changes to existing commands

### State Persistence
- Save working_directory in conversation state
- Restore working_directory when loading conversation
- Update conversation state structure to include working_directory

## Data Flow

```
Bot Startup:
  1. Load bot_agent_config.json
  2. Validate directory paths
  3. Store in memory

Agent Switch:
  1. Look up agent in config
  2. Get working_directory (or use default)
  3. Stop current Kiro process
  4. Start new Kiro process with cwd=working_directory
  5. Send confirmation with directory info

Agent List:
  1. Get all agents (built-in + custom)
  2. For each agent, look up working_directory in config
  3. Format output with directory info
```

## Files to Modify

1. `telegram_kiro_bot_threaded.py`:
   - Add config loading function
   - Modify `start_kiro_process()` to accept working_dir parameter
   - Update `handle_agent_swap()` to use configured directory
   - Update `handle_agent_list()` to show directories
   - Update conversation state save/load

2. `~/.kiro/bot_agent_config.json` (new file):
   - Created automatically if missing
   - User-editable configuration

## Testing Approach

- Test with valid directory paths
- Test with invalid/missing directories
- Test agent switching with different directories
- Test conversation save/restore with directories
- Test backward compatibility with existing states
