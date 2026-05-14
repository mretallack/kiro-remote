# Group Topic Agents - Requirements

## Overview

Enable the bot to operate in a Telegram group where each forum topic maps to a specific Kiro agent. Instead of using `\agent swap` in a 1-to-1 chat, users add the bot to a group with topics enabled, and each topic automatically routes messages to its corresponding agent.

## User Stories

### Group Setup

WHEN the bot is added to a Telegram group with forum topics enabled
THE SYSTEM SHALL accept messages from the authorized user in any topic

WHEN the bot receives a message in a group without forum topics enabled
THE SYSTEM SHALL ignore the message (existing 1-to-1 behaviour unchanged)

WHEN the bot is in a group
THE SYSTEM SHALL only respond to messages from the authorized user (same as current behaviour)

### Topic-to-Agent Mapping

WHEN a message is received in a topic whose name matches a known agent name
THE SYSTEM SHALL route the message to that agent's Kiro session

WHEN a message is received in a topic whose name does NOT match any known agent
THE SYSTEM SHALL reply with an error indicating no matching agent was found and list available agents

WHEN a new topic is created in the group with a name matching a known agent
THE SYSTEM SHALL automatically begin routing messages in that topic to the matching agent

WHEN an agent session does not yet exist for a matched topic
THE SYSTEM SHALL lazily start the agent session on first message (same as current agent swap behaviour)

### Message Routing

WHEN a message arrives in a topic mapped to an agent
THE SYSTEM SHALL send the message to that agent's Kiro session without requiring `\agent swap`

WHEN a response is received from a Kiro agent session
THE SYSTEM SHALL reply in the same topic (message_thread_id) that originated the request

WHEN a tool execution notification is generated
THE SYSTEM SHALL send it to the correct topic thread

WHEN a typing indicator is needed
THE SYSTEM SHALL show it in the correct topic thread

### Concurrent Agent Sessions

WHEN messages arrive in different topics simultaneously
THE SYSTEM SHALL handle them independently (each topic has its own agent session)

WHEN an agent in one topic is processing a request
THE SYSTEM SHALL allow messages to be sent to agents in other topics without blocking

WHEN a prompt is already in flight for a specific agent/topic
THE SYSTEM SHALL queue or reject additional messages for that topic (existing guard behaviour)

### Bot Commands in Groups

WHEN a user sends `\agent list` in any topic
THE SYSTEM SHALL list available agents (same as current behaviour)

WHEN a user sends `\cancel` in a topic
THE SYSTEM SHALL cancel the operation for that topic's agent only

WHEN a user sends `\context` in a topic
THE SYSTEM SHALL show context usage for that topic's agent

WHEN a user sends `\compact` in a topic
THE SYSTEM SHALL compact the session for that topic's agent

WHEN a user sends `\model` commands in a topic
THE SYSTEM SHALL apply model changes to that topic's agent only

### Topic Auto-Creation

WHEN a user sends `\topic sync` in the group
THE SYSTEM SHALL create a forum topic for each known agent that does not already have a topic

WHEN creating topics automatically
THE SYSTEM SHALL name each topic after the agent name and cache the mapping

WHEN the bot lacks `can_manage_topics` permission
THE SYSTEM SHALL reply with an error explaining the missing permission

### Backward Compatibility

WHEN the bot receives a direct message (1-to-1 chat)
THE SYSTEM SHALL continue to operate exactly as before (single active agent with `\agent swap`)

WHEN the bot is in both a group and a 1-to-1 chat
THE SYSTEM SHALL maintain independent sessions for each context

### Attachments in Groups

WHEN a photo or document is sent in a topic
THE SYSTEM SHALL route the attachment to that topic's agent (same as current attachment handling)

### Configuration

WHEN the bot starts
THE SYSTEM SHALL read an optional `group_id` setting from settings.ini to restrict which group it operates in

WHEN no `group_id` is configured
THE SYSTEM SHALL operate in any group it is added to (with authorized_user check still enforced)

## Acceptance Criteria

- Bot operates in a Telegram group with forum topics enabled
- Each topic name maps to a Kiro agent by name (case-insensitive match)
- Messages in a topic are routed to the correct agent without manual swap
- Responses are sent back to the originating topic thread
- Multiple agents can be active concurrently (one per topic)
- Existing 1-to-1 chat behaviour is completely unchanged
- Bot commands (`\cancel`, `\context`, `\compact`, `\model`) are scoped to the topic's agent
- Typing indicators and tool notifications appear in the correct topic
- Attachments (photos, documents) work in topics
- Unauthorized users in the group are ignored
- Agent sessions are lazily started on first message to a topic

## Constraints

- Must not break existing 1-to-1 chat functionality
- Must use the same KiroSessionACP infrastructure (no new session manager)
- Topic names must match agent names (as listed by `\agent list`)
- Only the configured authorized_user can interact with the bot in the group
- The bot must handle the case where a topic is renamed (re-maps to new agent or shows error)
