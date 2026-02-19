# Requirements: Telegram Bot Output Buffering & Typing Indicators

## Problem Statement

The Telegram bot currently buffers all text chunks until the final `on_turn_end` callback, causing poor user experience:

1. **Delayed Output**: Tool execution messages appear immediately, but Kiro's explanatory text (e.g., "You're right. Let me remove...") only appears at the very end
2. **No Activity Indicator**: Users don't know if Kiro is still thinking/working during long operations
3. **Confusing Message Order**: Tool notifications appear first, followed by all buffered text at once, making the conversation flow unnatural

### Current Behavior Example

```
🔧 write
🔧 Editing requirements.md
Remove CSV format changes from requirements

🔧 write
🔧 Editing requirements.md
Remove CSV field names requirement

[Long pause with no feedback]

You're right. Let me remove the CSV-related sections...
Now let me also update the requirements document...
Perfect! I've removed all CSV-related sections...
```

### Desired Behavior

```
You're right. Let me remove the CSV-related sections from the design document.

🔧 write
🔧 Editing requirements.md
Remove CSV format changes from requirements

Now let me also update the requirements document to remove CSV references.

🔧 write
🔧 Editing requirements.md
Remove CSV field names requirement

Perfect! I've removed all CSV-related sections from both documents.
```

## User Stories

### US-1: Timely Text Output
**WHEN** Kiro generates text chunks during a response  
**THE SYSTEM SHALL** send accumulated text to Telegram after a timeout period (e.g., 2 seconds of no new chunks)

**Acceptance Criteria:**
- Text chunks are buffered for up to 2 seconds
- If no new chunks arrive within timeout, buffered text is sent
- Timer resets when new chunks arrive
- Final text is sent immediately on `on_turn_end`

### US-2: Persistent Typing Indicator
**WHEN** Kiro is processing a user message  
**THE SYSTEM SHALL** display a typing indicator continuously until the response is complete

**Acceptance Criteria:**
- Typing indicator appears when message processing starts
- Indicator is refreshed every 4-5 seconds (Telegram's typing indicator expires after 5 seconds)
- Indicator stops when `on_turn_end` is received
- Indicator stops if an error occurs

### US-3: Interleaved Output
**WHEN** Kiro sends both text chunks and tool notifications  
**THE SYSTEM SHALL** display them in chronological order

**Acceptance Criteria:**
- Text chunks sent via timeout appear before subsequent tool calls
- Tool notifications don't interrupt buffered text
- Message order matches Kiro's actual execution flow

### US-4: Clean Message Boundaries
**WHEN** Multiple text chunks are buffered  
**THE SYSTEM SHALL** combine them into a single Telegram message

**Acceptance Criteria:**
- Chunks within the timeout window are concatenated
- No empty messages are sent
- Whitespace is preserved between chunks

## Non-Functional Requirements

### NFR-1: Performance
**THE SYSTEM SHALL** not introduce noticeable latency in message delivery

### NFR-2: Thread Safety
**THE SYSTEM SHALL** handle concurrent chunk buffering and timeout events safely

### NFR-3: Resource Efficiency
**THE SYSTEM SHALL** cancel typing indicator thread when response completes

## Out of Scope

- Streaming individual words/tokens (chunks are already sentence-level)
- Progress bars or percentage indicators
- Editing previous messages (Telegram bot uses append-only messaging)
