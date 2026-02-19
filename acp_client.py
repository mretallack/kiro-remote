"""
Agent Client Protocol (ACP) client for kiro-cli.

Implements JSON-RPC 2.0 communication over stdio with kiro-cli acp subprocess.

Example:
    client = ACPClient("/path/to/project")
    client.start()
    client.initialize()
    session_id = client.create_session("/path/to/project")
    client.send_prompt(session_id, [{"type": "text", "text": "Hello"}])
    client.close()
"""

import json
import logging
import queue
import subprocess
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ACPClient:
    """Manages JSON-RPC communication with kiro-cli acp subprocess."""

    def __init__(self, working_directory: str):
        self.working_directory = working_directory
        self.process: Optional[subprocess.Popen] = None
        self.next_id = 1
        self.pending_requests: Dict[int, queue.Queue] = {}
        self.notification_handlers: List[Callable] = []
        self.running = False
        self.reader_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start kiro-cli acp subprocess and reader thread."""
        self.process = subprocess.Popen(
            ["kiro-cli", "acp", "--verbose"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            cwd=self.working_directory,
        )

        self.running = True
        self.reader_thread = threading.Thread(target=self._read_messages, daemon=True)
        self.reader_thread.start()

        # Start stderr reader
        self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_thread.start()

        logger.info("Started kiro-cli acp subprocess")

    def _read_messages(self) -> None:
        """Read newline-delimited JSON messages from stdout."""
        while self.running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break

                # Log full message for permission requests
                message = json.loads(line)

                # Debug: Log ALL session/update messages fully
                if message.get("method") == "session/update":
                    logger.info(
                        f"ACPClient: SESSION UPDATE: {json.dumps(message, indent=2)}"
                    )
                elif message.get("method") == "session/request_permission":
                    logger.info(
                        f"ACPClient: FULL permission request: {json.dumps(message, indent=2)}"
                    )
                else:
                    logger.info(
                        f"ACPClient: Received from kiro-cli: {line.strip()[:200]}"
                    )

                self._route_message(message)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}, line: {line}")
            except Exception as e:
                logger.error(f"Error reading message: {e}")

    def _read_stderr(self) -> None:
        """Read stderr output from kiro-cli."""
        while self.running and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                logger.info(f"kiro-cli stderr: {line.strip()}")
            except Exception as e:
                logger.error(f"Error reading stderr: {e}")

    def _route_message(self, message: Dict[str, Any]) -> None:
        """Route message to pending request or notification handler."""
        has_id = "id" in message
        has_method = "method" in message
        msg_id = message.get("id")
        method = message.get("method")

        logger.debug(
            f"Routing message: has_id={has_id}, has_method={has_method}, id={msg_id}, method={method}"
        )

        if has_id and not has_method:
            # Response to a request (has id but no method)
            if msg_id in self.pending_requests:
                logger.debug(f"Routing to pending request: {msg_id}")
                self.pending_requests[msg_id].put(message)
            else:
                logger.debug(
                    f"Received response for request {msg_id} that is no longer pending (likely already completed)"
                )
        elif has_method:
            # Could be a notification or a request from server
            if has_id:
                # This is a request from the server that expects a response
                logger.info(
                    f"ACPClient: Received request from server: {method} id={msg_id}"
                )
                # Handle it in notification handlers, they can respond if needed
                for handler in self.notification_handlers:
                    try:
                        handler(message)
                    except Exception as e:
                        logger.error(f"Error in notification handler: {e}")
                        import traceback

                        traceback.print_exc()
            else:
                # Regular notification
                logger.debug(
                    f"ACPClient: Routing notification method={method} to {len(self.notification_handlers)} handlers"
                )
                for handler in self.notification_handlers:
                    try:
                        handler(message)
                    except Exception as e:
                        logger.error(f"Error in notification handler: {e}")
                        import traceback

                        traceback.print_exc()
        else:
            logger.warning(f"Received message with no id or method: {message}")

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request and wait for response."""
        request_id = self.next_id
        self.next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        response_queue: queue.Queue = queue.Queue()
        self.pending_requests[request_id] = response_queue

        try:
            message = json.dumps(request) + "\n"
            logger.debug(f"Sending request: {message.strip()}")
            self.process.stdin.write(message)
            self.process.stdin.flush()

            response = response_queue.get(
                timeout=300
            )  # Increased timeout for long-running prompts

            if "error" in response:
                raise Exception(f"JSON-RPC error: {response['error']}")

            return response.get("result", {})

        except queue.Empty:
            raise Exception(
                f"Timeout waiting for response to {method} (request_id={request_id})"
            )
        finally:
            del self.pending_requests[request_id]

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send JSON-RPC notification (no response expected)."""
        notification = {"jsonrpc": "2.0", "method": method, "params": params}

        message = json.dumps(notification) + "\n"
        self.process.stdin.write(message)
        self.process.stdin.flush()

    def initialize(self) -> Dict[str, Any]:
        """Initialize connection and exchange capabilities."""
        params = {
            "protocolVersion": 1,
            "clientCapabilities": {},
            "clientInfo": {"name": "telegram-kiro-bot", "version": "1.0.0"},
        }

        result = self._send_request("initialize", params)
        logger.info(f"Initialized ACP connection: {result}")
        return result

    def create_session(self, cwd: str, mcp_servers: List = None) -> str:
        """Create a new chat session."""
        params = {
            "cwd": cwd,
            "mcpServers": mcp_servers if mcp_servers is not None else [],
        }

        logger.debug(f"Creating session with params: {params}")
        result = self._send_request("session/new", params)
        session_id = result["sessionId"]
        logger.info(f"Created session: {session_id}")
        return session_id

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """Load an existing session by ID."""
        params = {"sessionId": session_id}
        result = self._send_request("session/load", params)
        logger.info(f"Loaded session: {session_id}")
        return result

    def send_prompt(
        self, session_id: str, content: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send a prompt to the agent and return the result with stopReason."""
        params = {
            "sessionId": session_id,
            "prompt": content,  # kiro-cli expects 'prompt' not 'content'
        }

        try:
            result = self._send_request("session/prompt", params)
            return result
        except Exception as e:
            logger.error(f"Failed to send prompt: {e}")
            # Check if process is still alive
            if self.process and self.process.poll() is not None:
                logger.error(
                    f"kiro-cli process has exited with code: {self.process.poll()}"
                )
            raise

    def cancel(self, session_id: str) -> None:
        """Cancel the current operation."""
        params = {"sessionId": session_id}
        self._send_notification("session/cancel", params)
        logger.info(f"Sent cancel for session: {session_id}")

    def respond_to_permission(
        self, request_id, session_id: str, tool_call_id: str, option_id: str
    ) -> None:
        """Respond to a permission request from the server."""
        # request_id can be either int or string (UUID)
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"outcome": {"outcome": "selected", "optionId": option_id}},
        }
        message = json.dumps(response) + "\n"
        logger.info(
            f"Responding to permission request id={request_id}: optionId={option_id}"
        )
        logger.info(f"Permission response JSON: {message.strip()}")
        self.process.stdin.write(message)
        self.process.stdin.flush()
        logger.info(f"Permission response sent and flushed")

    def set_mode(self, session_id: str, mode: str) -> None:
        """Switch agent mode."""
        params = {"sessionId": session_id, "modeId": mode}
        self._send_request("session/set_mode", params)
        logger.info(f"Set mode to: {mode}")

    def set_model(self, session_id: str, model: str) -> None:
        """Change the model for the session."""
        params = {"sessionId": session_id, "modelId": model}
        self._send_request("session/set_model", params)
        logger.info(f"Set model to: {model}")

    def execute_command(self, session_id: str, command: str) -> Dict[str, Any]:
        """Execute a slash command (Kiro extension)."""
        params = {"sessionId": session_id, "command": command}
        result = self._send_request("_kiro.dev/commands/execute", params)
        return result

    def on_notification(self, callback: Callable) -> None:
        """Register a notification handler."""
        self.notification_handlers.append(callback)

    def close(self) -> None:
        """Close the connection and terminate subprocess."""
        self.running = False

        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)

        if self.reader_thread:
            self.reader_thread.join(timeout=5)

        logger.info("Closed ACP connection")
