# Group Topic Agents - Implementation Tasks

## Phase 1: Core Infrastructure

- [ ] **Task 1: Add thread_id support to KiroSessionACP response routing**
  - Add `thread_id` field to agent data dict in `self.agents[name]`
  - Modify `_send_to_telegram_sync()` to accept and pass `message_thread_id`
  - Modify the async `send_to_telegram` callback to include `message_thread_id`
  - Ensure typing indicator sends include `message_thread_id`

- [ ] **Task 2: Add `send_message_to_agent()` method to KiroSessionACP**
  - New method that puts a prompt on the queue with explicit `agent_name` and `thread_id`
  - Modify `_handle_prompt()` in worker loop to use `msg.get("agent_name")` or fall back to `self.active_agent`
  - Set `agent_data["thread_id"]` before prompting so responses route correctly

- [ ] **Task 3: Add `start_agent_session()` method to KiroSessionACP**
  - New method to start a named agent without changing `self.active_agent`
  - Reuse existing session start logic but skip the `self.active_agent = agent_name` assignment
  - Queue-based: put `{"type": "start_agent", "agent_name": ...}` and handle in worker

## Phase 2: Telegram Group Handling

- [ ] **Task 4: Add topic name resolution and caching**
  - Add `_topic_agent_cache: Dict[int, str]` to TelegramBot
  - Add persistent cache file (`~/.kiro/topic_agent_map.json`) load/save
  - Implement `_resolve_topic_agent()` — check cache, then try to get topic name from update
  - Implement `_match_agent_name()` — case-insensitive match against available agents
  - Add `\topic register <agent>` command as fallback for unresolvable topics

- [ ] **Task 5: Add `handle_group_message()` to TelegramBot**
  - New handler for messages in group forum topics
  - Extract `message_thread_id` from update
  - Call `_resolve_topic_agent()` to get agent name
  - Start agent session if not running
  - Call `kiro.send_message_to_agent()` with agent_name, message, chat_id, thread_id

- [ ] **Task 6: Modify `handle_message()` to detect and route group messages**
  - Add check at top: if chat type is group/supergroup and message is a topic message, delegate to `handle_group_message()`
  - Existing 1-to-1 logic remains unchanged below the check

- [ ] **Task 7: Make bot commands topic-aware in groups**
  - Modify `handle_intercepted_commands()` to pass thread_id context
  - `\cancel` in a topic cancels that topic's agent only
  - `\context` / `\compact` / `\model` commands scoped to topic's agent
  - `\agent list` works the same in any topic
  - Reply to commands with `message_thread_id` so responses stay in-topic

## Phase 3: Attachments & Events

- [ ] **Task 8: Make attachment handlers topic-aware**
  - Modify `handle_photo()` and `handle_document()` to detect group topic context
  - Route attachments to the correct agent via `send_message_to_agent()`
  - Include `message_thread_id` in error replies

- [ ] **Task 9: Handle topic lifecycle events**
  - Add handler for `forum_topic_created` events — populate cache
  - Add handler for `forum_topic_edited` events — invalidate/update cache
  - Add handler for `forum_topic_closed` / `forum_topic_reopened` if needed

## Phase 4: Configuration & Polish

- [ ] **Task 10: Add group configuration to settings.ini**
  - Add `[group]` section with optional `group_id` and `topic_cache` path
  - Read config on startup
  - If `group_id` is set, only respond in that group

- [ ] **Task 11: Update README.md with group topic documentation**
  - Document how to set up the bot in a group
  - Document topic naming convention
  - Document `\topic register` fallback command
  - Document configuration options

## Phase 5: Testing

- [ ] **Task 12: Add unit tests for topic resolution and routing**
  - Test `_resolve_topic_agent()` with matching/non-matching names
  - Test `_match_agent_name()` case-insensitivity
  - Test cache persistence (load/save)
  - Test that 1-to-1 messages still route correctly (regression)

- [ ] **Task 13: Add integration test for group message flow**
  - Mock a group forum message update with `message_thread_id`
  - Verify correct agent is started and receives the message
  - Verify response includes correct `message_thread_id`
  - Verify commands in topics are scoped correctly

## Dependencies

- Task 2 depends on Task 1 (thread_id routing must exist before sending messages)
- Task 5 depends on Tasks 2, 3, 4 (needs all infrastructure)
- Task 6 depends on Task 5
- Task 7 depends on Task 5
- Task 8 depends on Task 5
- Tasks 12-13 depend on all implementation tasks
