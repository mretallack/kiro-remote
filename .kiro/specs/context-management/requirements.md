# Context Management via ACP - Requirements

## Overview

Enable Telegram bot users to monitor and manage Kiro CLI context usage through bot commands that leverage the ACP protocol.

## User Stories

### Context Monitoring

**US-1: View Context Usage**
- WHEN a user sends `\context` command
- THE SYSTEM SHALL display current context usage percentage
- THE SYSTEM SHALL show context usage in a readable format (e.g., "Context: 64.7%")

**US-2: Receive Context Warnings**
- WHEN context usage exceeds 80%
- THE SYSTEM SHALL send a warning message to the user
- THE SYSTEM SHALL suggest using `\compact` to free up space

**US-3: Receive Context Alerts**
- WHEN context usage exceeds 90%
- THE SYSTEM SHALL send an urgent alert to the user
- THE SYSTEM SHALL recommend immediate compaction

### Context Management

**US-4: Trigger Manual Compaction**
- WHEN a user sends `\compact` command
- THE SYSTEM SHALL execute the `/compact` slash command via ACP
- THE SYSTEM SHALL notify the user when compaction starts
- THE SYSTEM SHALL notify the user when compaction completes

**US-5: View Compaction Status**
- WHEN compaction is in progress
- THE SYSTEM SHALL show a status indicator to the user
- THE SYSTEM SHALL display progress updates if available

**US-6: Handle Compaction Errors**
- WHEN compaction fails
- THE SYSTEM SHALL notify the user of the failure
- THE SYSTEM SHALL provide error details if available

### Context Information

**US-7: View Detailed Context Info**
- WHEN a user sends `\context show` command
- THE SYSTEM SHALL execute the `/context show` slash command via ACP
- THE SYSTEM SHALL display the output to the user

**US-8: Clear Context Rules**
- WHEN a user sends `\context clear` command
- THE SYSTEM SHALL execute the `/context clear` slash command via ACP
- THE SYSTEM SHALL confirm the action to the user

## Acceptance Criteria

### AC-1: Context Usage Tracking
- Bot tracks context usage percentage from ACP metadata notifications
- Context usage is stored per session
- Context usage is updated on every turn

### AC-2: Command Execution
- Bot can execute arbitrary slash commands via `_kiro.dev/commands/execute`
- Command responses are properly formatted for Telegram
- Command errors are handled gracefully

### AC-3: User Experience
- Commands respond within 2 seconds
- Status messages are clear and actionable
- Error messages are user-friendly

### AC-4: Backward Compatibility
- Existing bot commands continue to work
- New commands follow existing `\` prefix convention
- No breaking changes to current functionality

## Non-Functional Requirements

### NFR-1: Performance
- Context usage updates should not impact message latency
- Command execution should be asynchronous

### NFR-2: Reliability
- Failed commands should not crash the bot
- Context tracking should handle missing metadata gracefully

### NFR-3: Usability
- Commands should be intuitive and consistent with Kiro CLI
- Help text should be available for new commands

## Out of Scope

- Automatic compaction triggers (future enhancement)
- Context usage history/graphs (future enhancement)
- Per-agent context limits (future enhancement)
- Context usage predictions (future enhancement)
