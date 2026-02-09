"""
ACP Session wrapper for high-level session management.

Provides a simplified interface for interacting with ACP sessions,
handling message accumulation, event callbacks, and session operations.

Example:
    session = ACPSession(session_id, client)
    session.on_chunk(lambda c: print(c, end=""))
    session.on_turn_end(lambda: print("\\nDone"))
    session.send_message("Hello Kiro")
"""

from typing import Callable, Optional, Dict, Any
import logging
import os
import json

from acp_client import ACPClient

logger = logging.getLogger(__name__)


class ACPSession:
    """High-level interface for an ACP session."""
    
    def __init__(self, session_id: str, client: ACPClient):
        self.session_id = session_id
        self.client = client
        self.message_chunks = []
        self.chunk_callbacks = []
        self.tool_call_callbacks = []
        self.tool_update_callbacks = []
        self.turn_end_callbacks = []
        self.commands_available_callbacks = []
        self.compaction_status_callbacks = []
        self.mcp_event_callbacks = []
        
        # Register notification handler
        self.client.on_notification(self._handle_notification)
        
    def _handle_notification(self, message: Dict[str, Any]) -> None:
        """Handle notifications from kiro."""
        method = message.get("method")
        params = message.get("params", {})
        request_id = message.get("id")  # Server requests have an id
        
        logger.debug(f"ACPSession: Received notification method={method}, sessionId={params.get('sessionId')}, my_session={self.session_id}, request_id={request_id}")
        
        # Only process notifications for this session
        if params.get("sessionId") != self.session_id:
            logger.debug(f"ACPSession: Ignoring notification for different session")
            return
        
        # Handle permission requests immediately
        if method == "session/request_permission":
            logger.info(f"ACPSession: Auto-approving permission request")
            
            # Extract options from the request
            options = params.get("options", [])
            
            # Find the allow_once option (preferred) or allow_always as fallback
            selected_option = None
            for opt in options:
                if opt.get("kind") == "allow_once":
                    selected_option = opt.get("optionId")
                    break
            
            # Fallback to allow_always if allow_once not available
            if not selected_option:
                for opt in options:
                    if opt.get("kind") == "allow_always":
                        selected_option = opt.get("optionId")
                        break
            
            # If still no option found, use the first allow option
            if not selected_option:
                for opt in options:
                    if "allow" in opt.get("kind", ""):
                        selected_option = opt.get("optionId")
                        break
            
            if selected_option:
                tool_call_id = params.get("toolCall", {}).get("toolCallId")
                self.client.respond_to_permission(
                    request_id,
                    self.session_id,
                    tool_call_id,
                    selected_option
                )
            else:
                logger.error(f"No allow option found in permission request")
            return
            
        if method == "session/update":
            self._handle_session_update(params.get("update", {}))
        elif method == "_kiro.dev/commands/available":
            self._handle_commands_available(params)
        elif method == "_kiro.dev/compaction/status":
            self._handle_compaction_status(params)
        elif method in ["_kiro.dev/mcp/oauth_request", "_kiro.dev/mcp/server_initialized"]:
            self._handle_mcp_event(method, params)
        elif method == "_kiro.dev/metadata":
            # Metadata notifications (like contextUsagePercentage) - just log at debug level
            logger.debug(f"ACPSession: Metadata: {params}")
        else:
            # Log unhandled notification methods
            logger.warning(f"ACPSession: UNHANDLED notification method: {method}")
            logger.warning(f"ACPSession: Full message: {json.dumps(message, indent=2)}")
            
    def _handle_session_update(self, update: Dict[str, Any]) -> None:
        """Handle session/update notification."""
        # kiro-cli uses 'sessionUpdate' field, not 'type'
        update_type = update.get("sessionUpdate") or update.get("type")
        logger.debug(f"ACPSession: Received session update type: {update_type}")
        
        if update_type == "agent_message_chunk":
            # Extract text from content
            content_obj = update.get("content", {})
            if isinstance(content_obj, dict):
                content = content_obj.get("text", "")
            else:
                content = str(content_obj)
            
            logger.debug(f"ACPSession: Chunk content: {content[:50]}")
            self.message_chunks.append(content)
            logger.debug(f"ACPSession: Calling {len(self.chunk_callbacks)} chunk callbacks")
            for callback in self.chunk_callbacks:
                callback(content)
                
        elif update_type in ["tool_call", "ToolCall"]:
            logger.debug(f"ACPSession: Tool call, calling {len(self.tool_call_callbacks)} callbacks")
            for callback in self.tool_call_callbacks:
                callback(update)
                
        elif update_type in ["tool_call_update", "ToolCallUpdate"]:
            logger.debug(f"ACPSession: Tool update, calling {len(self.tool_update_callbacks)} callbacks")
            for callback in self.tool_update_callbacks:
                callback(update)
        
        else:
            # Log unhandled update types to help with ACP spec evolution
            logger.warning(f"ACPSession: UNHANDLED session update type: {update_type}")
            logger.warning(f"ACPSession: Full update: {json.dumps(update, indent=2)}")
            
    def _handle_commands_available(self, params: Dict[str, Any]) -> None:
        """Handle available commands notification."""
        for callback in self.commands_available_callbacks:
            callback(params.get("commands", []))
            
    def _handle_compaction_status(self, params: Dict[str, Any]) -> None:
        """Handle compaction status notification."""
        for callback in self.compaction_status_callbacks:
            callback(params)
            
    def _handle_mcp_event(self, method: str, params: Dict[str, Any]) -> None:
        """Handle MCP server events."""
        for callback in self.mcp_event_callbacks:
            callback(method, params)
            
    def send_message(self, text: str) -> None:
        """Send a text message."""
        logger.debug(f"ACPSession.send_message called with: {text[:50]}")
        content = [{"type": "text", "text": text}]
        logger.debug(f"Calling client.send_prompt...")
        result = self.client.send_prompt(self.session_id, content)
        logger.debug(f"client.send_prompt returned: {result}")
        
        # Trigger turn_end when we get the response
        if result and result.get("stopReason"):
            logger.debug(f"Triggering {len(self.turn_end_callbacks)} turn_end callbacks")
            for callback in self.turn_end_callbacks:
                callback()
        else:
            logger.warning(f"No stopReason in result: {result}")
        
    def send_image(self, path: str, caption: str = "") -> None:
        """Send an image with optional caption."""
        content = []
        
        if caption:
            content.append({"type": "text", "text": caption})
            
        content.append({
            "type": "image",
            "source": {
                "type": "file",
                "path": os.path.abspath(path)
            }
        })
        
        result = self.client.send_prompt(self.session_id, content)
        
        # Trigger turn_end when we get the response
        if result and result.get("stopReason"):
            for callback in self.turn_end_callbacks:
                callback()
        
    def on_chunk(self, callback: Callable[[str], None]) -> None:
        """Register callback for message chunks."""
        self.chunk_callbacks.append(callback)
        
    def on_tool_call(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback for tool calls."""
        self.tool_call_callbacks.append(callback)
        
    def on_tool_update(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback for tool updates."""
        self.tool_update_callbacks.append(callback)
        
    def on_turn_end(self, callback: Callable[[], None]) -> None:
        """Register callback for turn end."""
        self.turn_end_callbacks.append(callback)
        
    def on_commands_available(self, callback: Callable[[list], None]) -> None:
        """Register callback for available commands."""
        self.commands_available_callbacks.append(callback)
        
    def on_compaction_status(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback for compaction status."""
        self.compaction_status_callbacks.append(callback)
        
    def on_mcp_event(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register callback for MCP events."""
        self.mcp_event_callbacks.append(callback)
        
    def cancel(self) -> None:
        """Cancel the current operation."""
        self.client.cancel(self.session_id)
        
    def set_mode(self, mode: str) -> None:
        """Switch agent mode."""
        self.client.set_mode(self.session_id, mode)
        
    def set_model(self, model: str) -> None:
        """Change the model."""
        self.client.set_model(self.session_id, model)
        
    def get_accumulated_message(self) -> str:
        """Get accumulated message chunks."""
        return "".join(self.message_chunks)
