# Tasks: Project Directory Per Agent

## Implementation Tasks

### Phase 1: Configuration Infrastructure
- [ ] Create `load_agent_config()` function to read `~/.kiro/bot_agent_config.json`
  - Expected: Function returns dict with agent configs and default_directory
  - Resources: Use json module, os.path.expanduser for tilde expansion

- [ ] Create `get_agent_working_directory(agent_name)` function
  - Expected: Returns working directory for agent, or default if not configured
  - Resources: Uses loaded config, validates path exists with os.path.isdir()

- [ ] Create `create_default_agent_config()` function
  - Expected: Creates config file with default structure if missing
  - Resources: Creates ~/.kiro/bot_agent_config.json with default_directory set

- [ ] Add config loading to bot initialization
  - Expected: Config loaded on startup, stored in instance variable
  - Resources: Call load_agent_config() in __init__ or main()

### Phase 2: Kiro Process Management
- [ ] Modify `start_kiro_process()` to accept `working_dir` parameter
  - Expected: subprocess.Popen uses cwd=working_dir
  - Resources: Update function signature and Popen call

- [ ] Update all calls to `start_kiro_process()` to pass working directory
  - Expected: All process starts use appropriate working directory
  - Resources: Find all start_kiro_process() calls, add working_dir argument

### Phase 3: Agent Commands Integration
- [ ] Update `handle_agent_swap()` to use configured working directory
  - Expected: Agent swap starts Kiro in agent's configured directory
  - Resources: Call get_agent_working_directory(), pass to start_kiro_process()

- [ ] Update `handle_agent_list()` to display working directories
  - Expected: Agent list shows directory path for each agent
  - Resources: Look up directory for each agent, format with 📁 emoji

- [ ] Add working directory to agent swap confirmation message
  - Expected: Message shows "Switched to 'agent' in /path/to/dir"
  - Resources: Include directory path in success message

### Phase 4: State Persistence
- [ ] Update conversation state save to include working_directory
  - Expected: Saved state JSON includes current working directory
  - Resources: Add working_directory field to state dict

- [ ] Update conversation state load to restore working_directory
  - Expected: Loaded state restores Kiro session in saved directory
  - Resources: Extract working_directory from state, pass to start_kiro_process()

- [ ] Add backward compatibility for states without working_directory
  - Expected: Old states load successfully with default directory
  - Resources: Use .get('working_directory', default) when loading

### Phase 5: Error Handling & Validation
- [ ] Add directory validation in `get_agent_working_directory()`
  - Expected: Invalid paths log warning and return default directory
  - Resources: Use os.path.isdir(), logging.warning()

- [ ] Add error handling for missing config file
  - Expected: Missing config creates default, logs info message
  - Resources: Try/except around config load, call create_default_agent_config()

- [ ] Add error handling for malformed JSON config
  - Expected: Invalid JSON logs error and uses defaults
  - Resources: Try/except json.JSONDecodeError

### Phase 6: Testing & Documentation
- [ ] Test agent switching with configured directories
  - Expected: Agent starts in correct directory, can access project files
  - Resources: Manual testing with different agents and directories

- [ ] Test backward compatibility with existing conversation states
  - Expected: Old states load without errors
  - Resources: Test with existing saved conversations

- [ ] Update README.md with agent configuration documentation
  - Expected: README explains bot_agent_config.json structure and usage
  - Resources: Add section under "Agent Management" or "Configuration"

## Dependencies
- Phase 2 depends on Phase 1 (config infrastructure must exist)
- Phase 3 depends on Phase 2 (process management must support working_dir)
- Phase 4 depends on Phase 2 (state persistence needs working_dir support)
- Phase 5 can be done in parallel with Phase 3-4
- Phase 6 depends on all previous phases

## Estimated Effort
- Phase 1: ~30 minutes
- Phase 2: ~15 minutes
- Phase 3: ~20 minutes
- Phase 4: ~20 minutes
- Phase 5: ~15 minutes
- Phase 6: ~30 minutes
- **Total: ~2 hours**
