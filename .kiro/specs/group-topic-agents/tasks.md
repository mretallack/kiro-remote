# Group Topic Agents - Implementation Tasks

## Phase 1: Core Infrastructure

- [x] **Task 1: Add thread_id support to KiroSessionACP response routing**
  - Add `thread_id` field to agent data dict in `self.agents[name]`
  - Modify `_send_to_telegram_sync()` to accept and pass `message_thread_id`
  - Modify the async `send_to_telegram` callback to include `message_thread_id`
  - Ensure typing indicator sends include `message_thread_id`

- [x] **Task 2: Add `send_message_to_agent()` method to KiroSessionACP**
  - New method that puts a prompt on the queue with explicit `agent_name` and `thread_id`
  - Modify `_handle_prompt()` in worker loop to use `msg.get("agent_name")` or fall back to `self.active_agent`
  - Set `agent_data["thread_id"]` before prompting so responses route correctly

- [x] **Task 3: Add `start_agent_background()` method to KiroSessionACP**
  - New method to start a named agent without changing `self.active_agent`
  - Reuse existing session start logic with `background=True` flag
  - `_handle_start_session` conditionally skips `self.active_agent` assignment

## Phase 2: Telegram Group Handling

- [x] **Task 4: Add topic name resolution and caching**
  - Add `_topic_agent_cache: Dict[int, str]` to TelegramBot
  - Add persistent cache file (`~/.kiro/topic_agent_map.json`) load/save
  - Implement `_resolve_topic_agent()` — check cache, then try to get topic name from update
  - Implement `_match_agent_name()` — case-insensitive match with space-to-underscore normalization
  - Add `\topic register <agent>` command as fallback for unresolvable topics

- [x] **Task 5: Add `handle_group_message()` to TelegramBot**
  - New handler for messages in group forum topics
  - Extract `message_thread_id` from update
  - Call `_resolve_topic_agent()` to get agent name
  - Start agent session if not running (background)
  - Call `kiro.send_message_to_agent()` with agent_name, message, chat_id, thread_id

- [x] **Task 6: Modify `handle_message()` to detect and route group messages**
  - Add check at top: if chat type is group/supergroup and message is a topic message, delegate to `handle_group_message()`
  - Existing 1-to-1 logic remains unchanged below the check

- [x] **Task 7: Make bot commands topic-aware in groups**
  - Modify `handle_intercepted_commands_group()` to pass thread_id context
  - `\cancel` in a topic cancels that topic's agent only
  - `\context` / `\compact` scoped to topic's agent
  - `\model list` / `\model <id>` scoped to topic's agent
  - `\agent list` works the same in any topic
  - Reply to commands with `message_thread_id` so responses stay in-topic

## Phase 3: Attachments & Events

- [x] **Task 8: Make attachment handlers topic-aware**
  - Modify `handle_photo()` and `handle_document()` to detect group topic context
  - Route attachments to the correct agent via `send_message_to_agent()`
  - Use `start_agent_background()` for agents started from topics
  - Include `message_thread_id` in error replies

- [x] **Task 9: Handle topic lifecycle events and auto-creation**
  - Add handler for `forum_topic_created` events — auto-populate cache
  - Add handler for `forum_topic_edited` events — update/invalidate cache
  - Implement `\topic sync` command — creates a forum topic for each known agent that doesn't have one
  - Requires `can_manage_topics` bot admin permission
  - Register handlers via `filters.StatusUpdate.FORUM_TOPIC_CREATED/EDITED`

## Phase 4: Configuration & Polish

- [x] **Task 10: Add group configuration to settings.ini**
  - Add `[group]` section with optional `group_id` and `topic_cache` path
  - Read config on startup
  - If `group_id` is set, only respond in that group

- [x] **Task 11: Update README.md with group topic documentation**
  - Add "Group Topics" section to README.md explaining the feature
  - Document setup steps (create group, enable topics, bot permissions, `\topic sync`)
  - Document topic naming convention (topic name = agent name)
  - Document `\topic register` fallback command
  - Document `\topic sync` command
  - Document `[group]` configuration options in settings.ini
  - Add group-specific commands to the Bot Commands section

## Phase 5: Testing

- [x] **Task 12: Add unit tests for topic resolution and routing**
  - Test `_resolve_topic_agent()` with matching/non-matching names
  - Test `_match_agent_name()` case-insensitivity and space normalization
  - Test cache persistence (load/save)
  - Test that 1-to-1 messages still route correctly (regression)

- [x] **Task 13: Add integration test for group message flow**
  - Test group message routes to correct agent
  - Verify `start_agent_background` called for new agents
  - Verify commands in topics are scoped correctly
  - Test forum topic lifecycle handlers (created/edited)

## Dependencies

- Task 2 depends on Task 1 (thread_id routing must exist before sending messages)
- Task 5 depends on Tasks 2, 3, 4 (needs all infrastructure)
- Task 6 depends on Task 5
- Task 7 depends on Task 5
- Task 8 depends on Task 5
- Tasks 12-13 depend on all implementation tasks
