"""
Queue-based ACP session manager.

Uses a dedicated worker thread to handle Kiro communication,
with a queue for async-to-sync communication.
"""

import asyncio
import json
import logging
import queue
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from acp_client import ACPClient
from acp_session import ACPSession
from context_tracker import ContextTracker

logger = logging.getLogger(__name__)


class KiroSessionACP:
    """Manages Kiro ACP sessions with queue-based async/sync bridge."""

    def __init__(self):
        self.agents = {}
        self.active_agent = None

        # Queue for messages from async layer to worker thread
        self.message_queue = queue.Queue()

        # Callback for sending messages back to Telegram
        self.send_to_telegram = None
        self.current_chat_id = None

        # Store application and event loop reference for typing indicator
        self.application = None
        self.event_loop = None

        # Configuration
        self.chunk_timeout = 2.0
        self.typing_refresh_interval = 4.0
        self.prompt_timeout = 600

        # Worker thread
        self.worker_thread = None
        self.running = False

        # Context tracking
        self.context_tracker = ContextTracker()

        # Output suppression: when True, output is queued instead of sent
        self.suppress_output = False

    def get_available_models(self):
        """Get list of available models for active agent."""
        if not self.active_agent or self.active_agent not in self.agents:
            return None
        return self.agents[self.active_agent].get("models", {})

    def get_available_modes(self):
        """Get list of available modes for active agent."""
        if not self.active_agent or self.active_agent not in self.agents:
            return None
        return self.agents[self.active_agent].get("modes", {})

    def set_model(self, model_id: str, chat_id: int):
        """Set the model for the active agent (async-safe)."""
        self.message_queue.put(
            {"type": "set_model", "model_id": model_id, "chat_id": chat_id}
        )

    def set_mode(self, mode_id: str):
        """Set the mode for the active agent (async-safe)."""
        self.message_queue.put({"type": "set_mode", "mode_id": mode_id})

    def start_worker(self):
        """Start the worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Worker thread started")

    def _worker_loop(self):
        """Worker thread main loop - processes messages from queue."""
        while self.running:
            try:
                # Get message from queue (blocking with timeout)
                try:
                    msg = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue

                msg_type = msg.get("type")

                if msg_type == "send_message":
                    self._handle_send_message(msg)
                elif msg_type == "start_session":
                    self._handle_start_session(msg)
                elif msg_type == "set_model":
                    self._handle_set_model(msg)
                elif msg_type == "set_mode":
                    self._handle_set_mode(msg)
                elif msg_type == "cancel":
                    self._handle_cancel(msg)
                elif msg_type == "close":
                    break

            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                import traceback

                traceback.print_exc()

        logger.info("Worker thread stopped")

    def _handle_send_message(self, msg: Dict[str, Any]):
        """Handle send_message request in worker thread."""
        text = msg["text"]
        chat_id = msg["chat_id"]

        logger.info(f"Worker: Sending message: {text[:50]}")

        if not self.active_agent or self.active_agent not in self.agents:
            self._send_error(chat_id, "No active agent")
            return

        current_agent_name = self.active_agent
        agent_data = self.agents[current_agent_name]
        session = agent_data["session"]
        agent_data["chat_id"] = chat_id
        agent_data["chunks"] = []  # Reset chunks for new message

        # Fix 4: Check usage limit
        if agent_data.get("usage_limit_reached"):
            self._send_to_telegram_sync(
                chat_id,
                "❌ Monthly usage limit reached. Try again next month or check your plan. Use \\cancel to reset.",
                agent_name=current_agent_name,
            )
            return

        # Fix 3: Check prompt in flight
        if agent_data.get("prompt_in_flight"):
            self._send_to_telegram_sync(
                chat_id,
                "⏳ Previous request still processing. Use \\cancel to abort it.",
                agent_name=current_agent_name,
            )
            return

        # Handle /compact specially - it goes through send_prompt but kiro-cli
        # doesn't return a prompt response for it, leaving the session locked.
        # Send the prompt with a short timeout and cancel to free the session.
        if text.strip().lower() == "/compact":
            agent_data["typing_stop_event"].clear()
            agent_data["typing_thread"] = threading.Thread(
                target=self._typing_indicator_loop,
                args=(chat_id, agent_data["typing_stop_event"]),
                daemon=True,
            )
            agent_data["typing_thread"].start()

            client = agent_data["client"]
            session_id = agent_data["session_id"]
            content = [{"type": "text", "text": text}]
            params = {"sessionId": session_id, "prompt": content}

            # Send the prompt request
            request_id = client.next_id
            client.next_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "session/prompt",
                "params": params,
            }
            response_queue = __import__("queue").Queue()
            client.pending_requests[request_id] = response_queue

            import json as _json

            client.process.stdin.write(_json.dumps(request) + "\n")
            client.process.stdin.flush()

            # Wait briefly then cancel - compaction callback handles the rest
            try:
                response_queue.get(timeout=5)
            except Exception:
                pass
            client.pending_requests.pop(request_id, None)
            client.cancel(session_id)

            logger.info("Worker: Sent /compact and released session")
            # Typing will be stopped by on_compaction_status callback
            return

        # Start typing indicator thread
        agent_data["typing_stop_event"].clear()
        agent_data["typing_thread"] = threading.Thread(
            target=self._typing_indicator_loop,
            args=(chat_id, agent_data["typing_stop_event"]),
            daemon=True,
        )
        agent_data["typing_thread"].start()
        logger.info(f"Worker: Started typing indicator thread")

        # Set up callbacks that reference agent_data
        def on_chunk(content):
            logger.debug(f"Worker: Received chunk: {content[:50]}")
            with agent_data["chunk_lock"]:
                agent_data["chunks"].append(content)

                # Cancel existing timer if active
                if agent_data["chunk_timer"]:
                    agent_data["chunk_timer"].cancel()

                # Create new timer to flush chunks after timeout
                agent_data["chunk_timer"] = threading.Timer(
                    self.chunk_timeout, lambda: self._flush_chunks(agent_data)
                )
                agent_data["chunk_timer"].start()

        def on_tool_call(tool):
            tool_name = tool.get("title", "unknown")
            logger.info(f"Worker: Tool call: {tool_name}")
            # Don't send tool start notifications to Telegram
            # Users will see tool outputs when they complete

        def on_tool_update(update):
            """Handle tool completion and send stdout/stderr."""
            status = update.get("status")
            if status != "completed":
                return

            raw_output = update.get("rawOutput", {})
            items = raw_output.get("items", [])

            if not items:
                return

            # Extract output from first item
            first_item = items[0]

            # Handle bash command output (Json format with stdout/stderr)
            if "Json" in first_item:
                output_data = first_item.get("Json", {})
                stdout = output_data.get("stdout", "").strip()
                stderr = output_data.get("stderr", "").strip()

                if not stdout and not stderr:
                    return

                # Truncate if too long (first 1000 + last 1000 bytes)
                def truncate_output(text, max_bytes=1000):
                    if len(text) <= max_bytes * 2:
                        return text
                    return f"{text[:max_bytes]}\n\n... (truncated {len(text) - max_bytes * 2} bytes) ...\n\n{text[-max_bytes:]}"

                output_parts = []
                if stdout:
                    output_parts.append(
                        f"**Output:**\n```\n{truncate_output(stdout)}\n```"
                    )
                if stderr:
                    output_parts.append(
                        f"**stderr:**\n```\n{truncate_output(stderr)}\n```"
                    )

                if output_parts:
                    message = "\n".join(output_parts)
                    self._send_to_telegram_sync(
                        agent_data["chat_id"], message, agent_name=current_agent_name
                    )

            # Handle file read output (Text format)
            elif "Text" in first_item:
                text_content = first_item.get("Text", "").strip()

                if not text_content:
                    return

                # Truncate if too long
                max_chars = 2000
                if len(text_content) > max_chars:
                    text_content = f"{text_content[:max_chars]}\n\n... (truncated {len(text_content) - max_chars} chars) ..."

                message = f"**File Content:**\n```\n{text_content}\n```"
                self._send_to_telegram_sync(
                    agent_data["chat_id"], message, agent_name=current_agent_name
                )

        def on_turn_end():
            logger.info(f"Worker: on_turn_end called")

            # Clear prompt-in-flight flag
            agent_data["prompt_in_flight"] = False

            # Cancel chunk timer if active
            if agent_data["chunk_timer"]:
                agent_data["chunk_timer"].cancel()
                agent_data["chunk_timer"] = None

            # Flush any remaining chunks
            self._flush_chunks(agent_data)

            # Stop typing indicator
            agent_data["typing_stop_event"].set()
            if agent_data["typing_thread"]:
                agent_data["typing_thread"].join(timeout=1.0)
                agent_data["typing_thread"] = None

            logger.info(f"Worker: Turn end complete")

        # Clear old callbacks and register new ones
        session.chunk_callbacks = []
        session.tool_call_callbacks = []
        session.tool_update_callbacks = []
        session.turn_end_callbacks = []

        session.on_chunk(on_chunk)
        session.on_tool_call(on_tool_call)
        session.on_tool_update(on_tool_update)
        session.on_turn_end(on_turn_end)

        # Send message (blocks until response)
        agent_data["prompt_in_flight"] = True
        try:
            session.send_message(text)
            logger.info("Worker: Message sent successfully")
        except Exception as e:
            logger.error(f"Worker: Error sending message: {e}")
            import traceback

            traceback.print_exc()

            # Clear prompt-in-flight flag on error
            agent_data["prompt_in_flight"] = False

            # Stop typing indicator on error
            agent_data["typing_stop_event"].set()
            if agent_data["typing_thread"]:
                agent_data["typing_thread"].join(timeout=1.0)
                agent_data["typing_thread"] = None

            # Fix 2 Task 2.5: User-friendly timeout message
            error_str = str(e)
            if "Timeout waiting for response" in error_str:
                self._send_to_telegram_sync(
                    chat_id,
                    f"⏱️ Request timed out after {self.prompt_timeout}s. The operation may still be running — use \\cancel to abort.",
                    agent_name=current_agent_name,
                )
            else:
                self._send_error(chat_id, error_str, agent_name=current_agent_name)

    def _handle_start_session(self, msg: Dict[str, Any]):
        """Handle start_session request in worker thread."""
        agent_name = msg.get("agent_name", "kiro_default")
        working_dir = msg.get("working_dir", "/home/mark/git/remote-kiro")

        logger.info(f"Worker: Starting session for {agent_name}")

        try:
            client = ACPClient(working_dir, prompt_timeout=self.prompt_timeout)
            client.start()
            client.initialize()

            # Get full session response to capture models info
            session_result = client._send_request(
                "session/new", {"cwd": working_dir, "mcpServers": []}
            )
            session_id = session_result["sessionId"]
            session = ACPSession(session_id, client)

            # Register metadata callback for context tracking
            def on_metadata(params):
                context_usage = params.get("contextUsagePercentage")
                if context_usage is not None:
                    logger.debug(f"Worker: Context usage: {context_usage}%")
                    self.context_tracker.update_usage(session_id, context_usage)

                    # Get agent data for chat_id
                    agent_data = self.agents.get(agent_name, {})
                    current_chat_id = agent_data.get("chat_id")

                    # Check for warnings
                    if self.context_tracker.should_alert(session_id):
                        logger.info(f"Worker: Context usage alert at {context_usage}%")
                        if current_chat_id:
                            self._send_to_telegram_sync(
                                current_chat_id,
                                f"🚨 Context usage: {context_usage:.1f}%. Recommend using \\compact now",
                                agent_name=agent_name,
                            )
                    elif self.context_tracker.should_warn(session_id):
                        logger.info(
                            f"Worker: Context usage warning at {context_usage}%"
                        )
                        if current_chat_id:
                            self._send_to_telegram_sync(
                                current_chat_id,
                                f"⚠️ Context usage: {context_usage:.1f}%. Consider using \\compact",
                                agent_name=agent_name,
                            )

            session.on_metadata(on_metadata)

            # Register compaction status callback
            def on_compaction_status(params):
                status = params.get("status", {})
                status_type = status.get("type")
                logger.info(f"Worker: Compaction status: {status}")

                # Get chat_id from agent data
                agent_data = self.agents.get(agent_name, {})
                current_chat_id = agent_data.get("chat_id")

                if current_chat_id:
                    if status_type == "started":
                        self._send_to_telegram_sync(
                            current_chat_id,
                            "🔄 Compacting conversation...",
                            agent_name=agent_name,
                        )
                    elif status_type == "completed":
                        self._send_to_telegram_sync(
                            current_chat_id,
                            "✅ Compaction complete",
                            agent_name=agent_name,
                        )
                        # Stop typing indicator - compaction doesn't produce a
                        # normal prompt response so on_turn_end won't fire
                        agent_data.get("typing_stop_event", threading.Event()).set()
                    elif status_type == "failed":
                        error = status.get("error", "Unknown error")
                        self._send_to_telegram_sync(
                            current_chat_id,
                            f"❌ Compaction failed: {error}",
                            agent_name=agent_name,
                        )
                        agent_data.get("typing_stop_event", threading.Event()).set()

            session.on_compaction_status(on_compaction_status)

            # Register subagent update callback
            def on_subagent_update(params):
                # Handle tool_call title updates for subagents
                if params.get("_tool_call_update"):
                    agent_data = self.agents.get(agent_name, {})
                    sid = params.get("sessionId", "")
                    title = params.get("title", "")
                    if sid in agent_data.get("subagents", {}) and title:
                        agent_data["subagents"][sid]["last_tool"] = title[:80]
                    return

                subagents_list = params.get("subagents", [])
                agent_data = self.agents.get(agent_name, {})
                current_chat_id = agent_data.get("chat_id")
                prev = agent_data.get("subagents", {})

                # Build new state
                current = {}
                for sa in subagents_list:
                    sid = sa.get("sessionId", "")
                    current[sid] = {
                        "name": sa.get("sessionName", "unknown"),
                        "agent": sa.get("agentName", ""),
                        "query": sa.get("initialQuery", "")[:100],
                        "status": sa.get("status", "running"),
                    }

                # Detect new subagents
                for sid, info in current.items():
                    if sid not in prev:
                        query_preview = info["query"][:60]
                        if current_chat_id:
                            self._send_to_telegram_sync(
                                current_chat_id,
                                f"🔀 Subagent <code>{info['name']}</code> started: {query_preview}...",
                                agent_name=agent_name,
                            )

                # Detect finished subagents
                for sid, info in prev.items():
                    if sid not in current:
                        if current_chat_id:
                            self._send_to_telegram_sync(
                                current_chat_id,
                                f"✅ Subagent <code>{info['name']}</code> finished",
                                agent_name=agent_name,
                            )

                agent_data["subagents"] = current

            session.on_subagent_update(on_subagent_update)

            # Store for this agent
            self.agents[agent_name] = {
                "client": client,
                "session": session,
                "session_id": session_id,
                "working_dir": working_dir,
                "agent_name": agent_name,
                "chunks": [],  # Store chunks per agent
                "chat_id": None,  # Store chat_id per agent
                "models": session_result.get("models", {}),  # Store models info
                "modes": session_result.get("modes", {}),  # Store modes info
                "chunk_timer": None,  # Timer for chunk buffering
                "chunk_lock": threading.Lock(),  # Thread safety for chunks
                "typing_thread": None,  # Thread for typing indicator
                "typing_stop_event": threading.Event(),  # Signal to stop typing
                "pending_output": [],  # Queued output when agent is not active
                "prompt_in_flight": False,  # Guard against concurrent prompts
                "usage_limit_reached": False,  # Monthly usage limit flag
                "subagents": {},  # Active subagents {sessionId: info}
            }

            self.active_agent = agent_name
            logger.info(f"Worker: Session started for {agent_name}")

        except Exception as e:
            logger.error(f"Worker: Error starting session: {e}")
            import traceback

            traceback.print_exc()

    def _handle_set_model(self, msg: Dict[str, Any]):
        """Handle set_model request in worker thread."""
        model_id = msg["model_id"]
        chat_id = msg["chat_id"]

        if not self.active_agent or self.active_agent not in self.agents:
            self._send_error(chat_id, "No active agent")
            return

        try:
            agent_data = self.agents[self.active_agent]
            session = agent_data["session"]
            session.client.set_model(session.session_id, model_id)

            # Update stored model info
            agent_data["models"]["currentModelId"] = model_id

            self._send_to_telegram_sync(chat_id, f"✓ Model set to: {model_id}")
            logger.info(f"Worker: Set model to {model_id}")
        except Exception as e:
            logger.error(f"Worker: Error setting model: {e}")
            import traceback

            traceback.print_exc()
            self._send_error(chat_id, f"Failed to set model: {str(e)}")

    def _handle_set_mode(self, msg: Dict[str, Any]):
        """Handle set_mode request in worker thread."""
        mode_id = msg["mode_id"]

        if not self.active_agent or self.active_agent not in self.agents:
            logger.warning(f"Cannot set mode: no active agent")
            return

        try:
            agent_data = self.agents[self.active_agent]
            session = agent_data["session"]
            session.set_mode(mode_id)

            # Update stored mode info
            if "modes" in agent_data:
                agent_data["modes"]["currentModeId"] = mode_id

            logger.info(f"Worker: Set mode to {mode_id} for agent {self.active_agent}")
        except Exception as e:
            logger.error(f"Worker: Error setting mode: {e}")
            import traceback

            traceback.print_exc()

    def _handle_cancel(self, msg: Dict[str, Any]):
        """Handle cancel request in worker thread."""
        if self.active_agent and self.active_agent in self.agents:
            agent_data = self.agents[self.active_agent]
            session = agent_data["session"]
            session.cancel()
            agent_data["prompt_in_flight"] = False
            agent_data["usage_limit_reached"] = False
            logger.info("Worker: Cancelled operation")

    def _flush_chunks(self, agent_data: Dict[str, Any]):
        """Flush buffered chunks to Telegram."""
        with agent_data["chunk_lock"]:
            chunks = agent_data["chunks"]
            if chunks:
                message = "".join(chunks)
                logger.info(
                    f"Worker: Flushing {len(chunks)} chunks ({len(message)} chars)"
                )
                try:
                    self._send_to_telegram_sync(
                        agent_data["chat_id"],
                        message,
                        agent_name=agent_data.get("agent_name"),
                    )
                except Exception as e:
                    logger.error(f"Error flushing chunks: {e}")
                chunks.clear()

    def _typing_indicator_loop(self, chat_id: int, stop_event: threading.Event):
        """Background thread that refreshes typing indicator."""
        logger.info(f"Worker: Typing indicator thread started for chat {chat_id}")
        while not stop_event.is_set():
            try:
                # Send typing action via async bridge
                if self.application and self.event_loop:
                    from telegram.constants import ChatAction

                    asyncio.run_coroutine_threadsafe(
                        self.application.bot.send_chat_action(
                            chat_id=chat_id, action=ChatAction.TYPING
                        ),
                        self.event_loop,
                    )
            except Exception as e:
                logger.error(f"Typing indicator error: {e}")

            # Wait for interval or until stop signal
            stop_event.wait(self.typing_refresh_interval)

        logger.info(f"Worker: Typing indicator thread stopped for chat {chat_id}")

    def _split_html_message(self, text: str, max_length: int = 4096) -> list:
        """Split a message into chunks that fit within Telegram's limit.

        Splits at paragraph breaks, then newlines, then hard limit.
        Tracks and repairs open HTML tags across splits.
        """
        if len(text) <= max_length:
            return [text]

        # Tags we need to track
        tag_names = ["pre", "code", "b", "i"]
        tag_pattern = re.compile(
            r"<(/?)(" + "|".join(tag_names) + r")(?:\s[^>]*)?>", re.IGNORECASE
        )

        def get_open_tags(chunk: str) -> list:
            """Return list of tags that are opened but not closed in chunk."""
            stack = []
            for match in tag_pattern.finditer(chunk):
                is_closing = match.group(1) == "/"
                tag = match.group(2).lower()
                if is_closing:
                    if stack and stack[-1] == tag:
                        stack.pop()
                else:
                    stack.append(tag)
            return stack

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break

            # Find best split point
            split_at = None
            # Try paragraph break
            idx = remaining.rfind("\n\n", 0, max_length)
            if idx > 0:
                split_at = idx + 2
            else:
                # Try newline
                idx = remaining.rfind("\n", 0, max_length)
                if idx > 0:
                    split_at = idx + 1
                else:
                    # Hard split
                    split_at = max_length

            chunk = remaining[:split_at]
            remaining = remaining[split_at:]

            # Repair open tags
            open_tags = get_open_tags(chunk)
            if open_tags:
                # Close open tags at end of chunk (reverse order)
                for tag in reversed(open_tags):
                    chunk += f"</{tag}>"
                # Re-open tags at start of next chunk
                prefix = "".join(f"<{tag}>" for tag in open_tags)
                remaining = prefix + remaining

            chunks.append(chunk)

        return chunks

    def _send_to_telegram_sync(self, chat_id: int, text: str, agent_name: str = None):
        """Send message to Telegram from worker thread.

        If agent_name is provided, output is queued when that agent is not
        active or when output is globally suppressed.
        """
        # Gate: queue output if agent is not active or output is suppressed
        if agent_name and (agent_name != self.active_agent or self.suppress_output):
            agent_data = self.agents.get(agent_name)
            if agent_data is not None:
                agent_data["pending_output"].append((chat_id, text))
                logger.info(
                    f"Worker: Queued output for inactive/suppressed agent {agent_name} ({len(text)} chars)"
                )
            return

        logger.info(
            f"Worker: _send_to_telegram_sync called with text length: {len(text)}"
        )
        if self.send_to_telegram:
            # Convert markdown to HTML
            html_text = self._markdown_to_html(text)
            # Split if too long for Telegram
            parts = self._split_html_message(html_text)
            for part in parts:
                try:
                    logger.debug(f"Worker: Scheduling async call to Telegram")
                    future = asyncio.run_coroutine_threadsafe(
                        self.send_to_telegram(chat_id, part),
                        self.send_to_telegram.loop,
                    )
                    # Wait for the message to actually be sent (with timeout)
                    future.result(timeout=10.0)
                    logger.debug(f"Worker: Message sent to Telegram successfully")
                except (OSError, ConnectionError) as e:
                    # Retry on transient network errors (Fix 5)
                    import time

                    for attempt in range(1, 3):
                        wait = 2**attempt
                        logger.warning(
                            f"Network error sending message (attempt {attempt + 1}/3), retrying in {wait}s: {e}"
                        )
                        time.sleep(wait)
                        try:
                            future = asyncio.run_coroutine_threadsafe(
                                self.send_to_telegram(chat_id, part),
                                self.send_to_telegram.loop,
                            )
                            future.result(timeout=10.0)
                            break
                        except (OSError, ConnectionError) as e2:
                            e = e2
                    else:
                        logger.error(
                            f"Failed to send telegram message after 3 attempts: {e}"
                        )
                except Exception as e:
                    logger.error(f"Error sending telegram message: {e}")
                    import traceback

                    traceback.print_exc()
        else:
            logger.warning(f"No send_to_telegram callback set")

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown formatting to HTML for Telegram."""
        import html

        # Extract code blocks first to protect them
        code_blocks = []

        def save_code_block(match):
            code_blocks.append(match.group(1))
            return f"\x00CODEBLOCK{len(code_blocks)-1}\x00"

        text = re.sub(r"```(.+?)```", save_code_block, text, flags=re.DOTALL)

        # Extract inline code to protect it
        inline_codes = []

        def save_inline_code(match):
            inline_codes.append(match.group(1))
            return f"\x00INLINECODE{len(inline_codes)-1}\x00"

        text = re.sub(r"`(.+?)`", save_inline_code, text)

        # Escape HTML in remaining text
        text = html.escape(text)

        # Bold: **text** or __text__ -> <b>text</b>
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

        # Italic: *text* or _text_ -> <i>text</i>
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)

        # Restore inline code with HTML escaping
        for i, code in enumerate(inline_codes):
            text = text.replace(
                f"\x00INLINECODE{i}\x00", f"<code>{html.escape(code)}</code>"
            )

        # Restore code blocks with HTML escaping
        for i, code in enumerate(code_blocks):
            text = text.replace(
                f"\x00CODEBLOCK{i}\x00", f"<pre>{html.escape(code)}</pre>"
            )

        return text

    def _send_error(self, chat_id: int, error: str, agent_name: str = None):
        """Send error message to Telegram."""
        # Try to extract meaningful error from JSON-RPC error
        if "monthly usage limit has been reached" in error.lower():
            user_message = "❌ Monthly usage limit reached. Try again next month or check your plan."
            # Fix 4: Set usage limit flag
            if agent_name and agent_name in self.agents:
                self.agents[agent_name]["usage_limit_reached"] = True
        elif "JSON-RPC error" in error:
            # Extract the actual error message
            import re

            match = re.search(r"'data': '([^']+)'", error)
            if match:
                user_message = f"❌ Error: {match.group(1)}"
            else:
                user_message = f"❌ Error: {error}"
        else:
            user_message = f"❌ Error: {error}"

        self._send_to_telegram_sync(chat_id, user_message, agent_name=agent_name)

    # Public API (called from async layer)

    def _load_agent_config(self):
        """Load agent configuration from ~/.kiro/bot_agent_config.json"""
        import os

        config_path = os.path.expanduser("~/.kiro/bot_agent_config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load agent config: {e}")

        return {"agents": {}, "default_directory": "/home/mark/git/remote-kiro"}

    def start_session(self, agent_name: str = "kiro_default", working_dir: str = None):
        """Start a session (async-safe)."""
        if not self.running:
            self.start_worker()

        if working_dir is None:
            # Load agent config to get working directory
            config = self._load_agent_config()
            working_dir = (
                config.get("agents", {}).get(agent_name, {}).get("working_directory")
            )

            if not working_dir:
                working_dir = config.get(
                    "default_directory", "/home/mark/git/remote-kiro"
                )

        logger.info(
            f"Starting session for agent '{agent_name}' in directory: {working_dir}"
        )

        self.message_queue.put(
            {
                "type": "start_session",
                "agent_name": agent_name,
                "working_dir": working_dir,
            }
        )

    def send_message(self, text: str, chat_id: int):
        """Send message to Kiro (async-safe)."""
        self.message_queue.put(
            {"type": "send_message", "text": text, "chat_id": chat_id}
        )

    def cancel_operation(self):
        """Cancel current operation (async-safe).

        Sends cancel directly to kiro-cli, bypassing the worker queue
        which may be blocked waiting for a prompt response.
        """
        if self.active_agent and self.active_agent in self.agents:
            agent_data = self.agents[self.active_agent]
            try:
                agent_data["session"].cancel()
                agent_data["prompt_in_flight"] = False
                logger.info("Cancel sent directly to kiro-cli")
            except Exception as e:
                logger.error(f"Error sending direct cancel: {e}")
        # Also queue so worker cleans up when it unblocks
        self.message_queue.put({"type": "cancel"})

    def get_subagents(self) -> dict:
        """Get active subagents for the current agent."""
        if self.active_agent and self.active_agent in self.agents:
            return self.agents[self.active_agent].get("subagents", {})
        return {}

    def terminate_subagent(self, name: str) -> str:
        """Terminate a subagent by name. Returns status message."""
        subagents = self.get_subagents()
        for sid, info in subagents.items():
            if info["name"] == name:
                if self.active_agent and self.active_agent in self.agents:
                    client = self.agents[self.active_agent]["client"]
                    client.terminate_session(sid)
                    return f"🛑 Terminated subagent `{name}`"
        return f"❌ No active subagent named `{name}`"

    def close(self):
        """Close all sessions and stop worker."""
        self.running = False
        self.message_queue.put({"type": "close"})

        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        for agent_name, agent_data in list(self.agents.items()):
            try:
                agent_data["client"].close()
            except:
                pass

        logger.info("Closed all sessions")

    # Compatibility methods

    def send_to_kiro(self, message: str):
        """Compatibility method."""
        if self.current_chat_id:
            self.send_message(message, self.current_chat_id)

    def set_chat_id(self, chat_id: int):
        """Set current chat ID."""
        self.current_chat_id = chat_id

    def list_agents(self):
        """List available agents."""
        return list(self.agents.keys())

    def save_state(self) -> bool:
        """Save current session state (placeholder for compatibility)."""
        # The queue-based implementation doesn't need explicit save_state
        # Sessions are automatically persisted by kiro-cli
        logger.info("save_state called (no-op in queue-based implementation)")
        return True

    def restart_with_agent(self, agent_name: str) -> bool:
        """Switch to a different agent."""
        try:
            logger.info(f"Switching to agent: {agent_name}")

            # Start session for the new agent if not already started
            if agent_name not in self.agents:
                self.start_session(agent_name=agent_name)
                # Give it a moment to start
                import time

                time.sleep(1)

            # Switch active agent
            self.active_agent = agent_name

            # Clear error flags for the new agent
            if agent_name in self.agents:
                self.agents[agent_name]["usage_limit_reached"] = False

            # Flush any pending output from this agent
            self.flush_pending_output(agent_name)

            # Try to set the mode to match the agent name
            # This will silently fail if the mode doesn't exist
            self.set_mode(agent_name)

            logger.info(f"Switched to agent: {agent_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch agent: {e}")
            return False

    def flush_pending_output(self, agent_name: str):
        """Send all queued output for an agent to Telegram."""
        agent_data = self.agents.get(agent_name)
        if not agent_data:
            return
        pending = agent_data["pending_output"]
        if not pending:
            return
        logger.info(f"Flushing {len(pending)} pending messages for agent {agent_name}")
        for chat_id, text in pending:
            self._send_to_telegram_sync(chat_id, text)
        pending.clear()

    def agents_with_pending_output(self) -> list:
        """Return list of agent names that have queued output."""
        return [
            name for name, data in self.agents.items() if data.get("pending_output")
        ]
