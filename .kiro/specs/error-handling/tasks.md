# Error Handling Improvements — Tasks

## Fix 1: Message Too Long Splitting

- [x] **Task 1.1**: Add `_split_html_message(text, max_length=4096)` method to `KiroSessionACP`
  - Split at `\n\n`, then `\n`, then hard limit
  - Track and repair open HTML tags (`<pre>`, `<code>`, `<b>`, `<i>`) across splits
  - Return list of strings, each ≤ max_length

- [x] **Task 1.2**: Update `_send_to_telegram_sync()` to call `_split_html_message()` and send each chunk sequentially

- [x] **Task 1.3**: Add unit tests for `_split_html_message()` — short message (no split), long plain text, split inside `<pre>` block, multiple paragraphs, message exactly at limit

## Fix 2: Configurable Prompt Timeout

- [x] **Task 2.1**: Add `prompt_timeout = 600` to `settings.ini.template` under `[bot]`

- [x] **Task 2.2**: Read `prompt_timeout` in `telegram_kiro_bot.py` `__init__` and pass to `KiroSessionACP`

- [x] **Task 2.3**: Add `prompt_timeout` attribute to `KiroSessionACP`, pass to `ACPClient` in `_handle_start_session()`

- [x] **Task 2.4**: Update `ACPClient._send_request()` to use `self.prompt_timeout` instead of hardcoded 600

- [x] **Task 2.5**: In `_handle_send_message()`, catch timeout and send user-friendly message: "⏱️ Request timed out after {N}s..."

## Fix 3: Prompt Already In Progress Guard

- [x] **Task 3.1**: Add `"prompt_in_flight": False` to agent data dict in `_handle_start_session()`

- [x] **Task 3.2**: In `_handle_send_message()`, check `prompt_in_flight` at start — if True, reply "⏳ Previous request still processing..." and return

- [x] **Task 3.3**: Set `prompt_in_flight = True` before `session.send_message()`, clear to `False` in `on_turn_end` callback and in the error handler

- [x] **Task 3.4**: Add unit test for prompt-in-flight guard — verify message is rejected when flag is set, and processed when flag is clear

## Fix 4: Monthly Usage Limit Handling

- [x] **Task 4.1**: Add `"usage_limit_reached": False` to agent data dict in `_handle_start_session()`

- [x] **Task 4.2**: In `_send_error()`, detect "monthly usage limit" in error string and set `usage_limit_reached = True` on the agent

- [x] **Task 4.3**: In `_handle_send_message()`, check `usage_limit_reached` at start — if True, reply with friendly message and return

- [x] **Task 4.4**: Clear `usage_limit_reached` in `_handle_cancel()` and `restart_with_agent()`

- [x] **Task 4.5**: Add unit test for usage limit lifecycle — flag set on error, messages rejected, flag cleared on cancel

## Fix 5: Transient Network Error Recovery

- [x] **Task 5.1**: Add retry loop (3 attempts, exponential backoff) around `future.result()` in `_send_to_telegram_sync()` — only retry on network-related errors

- [x] **Task 5.2**: Register global error handler via `application.add_error_handler()` in `TelegramBot.__init__()` that logs and suppresses `NetworkError`

- [x] **Task 5.3**: Add unit test for retry logic with mocked network failure then success
