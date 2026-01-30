# Requirements: Project Directory Per Agent

## Overview
Enable each Kiro agent to start in a specific project directory, allowing different agents to work on different projects without manual directory changes.

## User Stories

### Agent Configuration
WHEN an administrator configures an agent
THE SYSTEM SHALL allow specifying a working directory for that agent

WHEN an administrator does not specify a working directory for an agent
THE SYSTEM SHALL use the default bot working directory

### Agent Switching
WHEN a user switches to an agent with a configured project directory
THE SYSTEM SHALL start the Kiro CLI session in that agent's project directory

WHEN a user switches to an agent without a configured project directory
THE SYSTEM SHALL start the Kiro CLI session in the default directory

### Agent Listing
WHEN a user lists available agents
THE SYSTEM SHALL display each agent's configured project directory (if set)

### Configuration Management
WHEN the bot starts
THE SYSTEM SHALL load agent-to-directory mappings from a configuration file

WHEN an agent configuration file is missing or invalid
THE SYSTEM SHALL log a warning and continue with default behavior

### Conversation State
WHEN a conversation state is saved
THE SYSTEM SHALL include the current agent's working directory

WHEN a conversation state is restored
THE SYSTEM SHALL restore the Kiro CLI session in the saved working directory

## Acceptance Criteria

- Agent configuration includes optional `working_directory` field
- Bot reads agent configurations from a central config file
- Agent switching respects configured working directories
- Agent listing shows working directory information
- Conversation state preserves working directory context
- Invalid or missing directories are handled gracefully with fallback to default
- Existing agent functionality remains unchanged
