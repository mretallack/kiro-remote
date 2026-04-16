# Error Handling Improvements — Requirements

## Overview

The Telegram Kiro Bot has five production error handling issues identified from journal logs (Apr 11–12). These cause silent failures, lost responses, and poor user experience. This spec addresses all five.

## User Stories

### US-1: Message Too Long Splitting

**As a** bot user  
**I want** long Kiro responses to be delivered in full  
**So that** I don't miss any content when Kiro generates lengthy output

**Evidence**: `telegram.error.BadRequest: Message is too long` in journal logs (Apr 12 18:20). Telegram has a 4096 character limit per message.

#### Acceptance Criteria
- WHEN Kiro returns a response exceeding 4096 characters THE SYSTEM SHALL split it into multiple sequential messages
- WHEN splitting a message THE SYSTEM SHALL preserve HTML formatting across chunks (no broken tags)
- WHEN splitting a message THE SYSTEM SHALL prefer splitting at paragraph boundaries (`\n\n`), then line boundaries (`\n`), then at the character limit
- WHEN a `<pre>` or `<code>` block spans a split boundary THE SYSTEM SHALL close the tag before the split and reopen it after
- WHEN sending multiple chunks THE SYSTEM SHALL send them in order with no chunks dropped

### US-2: Configurable Prompt Timeout

**As a** bot user  
**I want** to be notified when a Kiro request times out  
**So that** I know what happened instead of getting silence

**Evidence**: `Exception: Timeout waiting for response to session/prompt` — ~20 occurrences across Apr 11–12, the most frequent error in the logs. Current hardcoded timeout is 600s in `acp_client.py`.

#### Acceptance Criteria
- WHEN a prompt exceeds the configured timeout THE SYSTEM SHALL send the user a message: "⏱️ Request timed out after {N}s. The operation may still be running — use `\cancel` to stop it."
- THE SYSTEM SHALL support a `prompt_timeout` setting in `settings.ini` under `[bot]` (default: 600)
- WHEN the timeout is configured THE SYSTEM SHALL pass it through to `ACPClient._send_request`

### US-3: Prompt Already In Progress Guard

**As a** bot user  
**I want** my retry messages to be queued when a previous request is still running  
**So that** I don't get "Prompt already in progress" errors

**Evidence**: `Exception: JSON-RPC error: {'code': -32603, 'message': 'Internal error', 'data': 'Prompt already in progress'}` — ~10 occurrences, always following a timeout.

#### Acceptance Criteria
- WHEN a user sends a message while a prompt is in-flight THE SYSTEM SHALL reply: "⏳ Previous request still processing. Please wait or use `\cancel` to stop it."
- WHEN a user sends a message while a prompt is in-flight THE SYSTEM SHALL NOT forward the message to Kiro
- WHEN the in-flight prompt completes or is cancelled THE SYSTEM SHALL process the next queued message automatically
- THE SYSTEM SHALL track prompt state per agent using a boolean flag (`prompt_in_flight`)

### US-4: Monthly Usage Limit Handling

**As a** bot user  
**I want** a clear message when the monthly usage limit is reached  
**So that** I stop retrying and know what to do

**Evidence**: `Exception: JSON-RPC error: ... 'The monthly usage limit has been reached'` — 4 occurrences in quick succession (Apr 12 17:44–17:49).

#### Acceptance Criteria
- WHEN Kiro returns a "monthly usage limit" error THE SYSTEM SHALL send the user: "❌ Monthly usage limit reached. Check your Kiro account or try again next month."
- WHEN the usage limit error has been detected THE SYSTEM SHALL set a `usage_limit_reached` flag per agent
- WHEN `usage_limit_reached` is set THE SYSTEM SHALL reject new messages with the same friendly message without sending to Kiro
- WHEN the user runs `\cancel` or restarts the agent THE SYSTEM SHALL clear the `usage_limit_reached` flag

### US-5: Transient Network Error Recovery

**As a** bot operator  
**I want** Telegram API network errors to be retried automatically  
**So that** temporary connectivity issues don't cause lost messages

**Evidence**: `telegram.error.NetworkError: httpx.ReadError:` (5 occurrences) and `telegram.error.NetworkError: Bad Gateway` (1 occurrence, Apr 12 02:10).

#### Acceptance Criteria
- WHEN a Telegram API call fails with a `NetworkError` THE SYSTEM SHALL retry up to 3 times with exponential backoff (1s, 2s, 4s)
- WHEN all retries are exhausted THE SYSTEM SHALL log the error and continue (not crash)
- THE SYSTEM SHALL register a global error handler via `application.add_error_handler()` to catch unhandled Telegram errors
- THE SYSTEM SHALL log all network errors with sufficient context for debugging
