# Agent Management Feature Requirements

## Overview
Enable creation and management of global agents without requiring editor interaction or CLI restarts, with support for conversation persistence across bot restarts.

## User Stories

### Agent Creation
WHEN a user wants to create a new global agent
THE SYSTEM SHALL provide a command-line interface to specify agent properties without opening an editor

WHEN a user creates a new global agent
THE SYSTEM SHALL store the agent configuration in ~/.kiro/agents/ directory

WHEN a user creates a new global agent
THE SYSTEM SHALL make the agent immediately available without requiring kiro-cli restart

### Agent Management
WHEN a user lists available agents
THE SYSTEM SHALL display both project-local and global agents with clear distinction

WHEN a user wants to switch to a newly created agent
THE SYSTEM SHALL allow switching without losing current conversation context

### Conversation Persistence
WHEN a user saves the current conversation
THE SYSTEM SHALL store conversation state with a user-specified name using "/chat save <name>"

WHEN the bot restarts
THE SYSTEM SHALL provide capability to reload a saved conversation state

WHEN a conversation is reloaded
THE SYSTEM SHALL restore the previous context, agent selection, and conversation history

### Bot Integration
WHEN the bot needs to restart kiro-cli
THE SYSTEM SHALL automatically save current conversation state before restart

WHEN the bot restarts kiro-cli
THE SYSTEM SHALL automatically reload the previous conversation state after restart

WHEN the bot encounters agent-related changes
THE SYSTEM SHALL handle agent reloading without manual intervention

## Acceptance Criteria

- Agent creation works without editor dependency
- Global agents stored in ~/.kiro/agents/ are immediately usable
- Conversation save/load functionality preserves full context
- Bot can restart kiro-cli seamlessly with state preservation
- No manual kiro-cli restarts required for agent management
- Clear distinction between global and project agents in listings

## Constraints

- Must work with telegram bot environment (no interactive editors)
- Must preserve conversation context across restarts
- Must support global agent storage in home directory
- Must integrate with existing kiro-cli command structure
