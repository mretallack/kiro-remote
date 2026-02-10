"""
Queue-based ACP session manager.

Uses a dedicated worker thread to handle Kiro communication,
with a queue for async-to-sync communication.
"""

import logging
import queue
import threading
import asyncio
import json
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from acp_client import ACPClient
from acp_session import ACPSession

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
        
        # Worker thread
        self.worker_thread = None
        self.running = False
        
    def get_available_models(self):
        """Get list of available models for active agent."""
        if not self.active_agent or self.active_agent not in self.agents:
            return None
        return self.agents[self.active_agent].get('models', {})
    
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
                    
                msg_type = msg.get('type')
                
                if msg_type == 'send_message':
                    self._handle_send_message(msg)
                elif msg_type == 'start_session':
                    self._handle_start_session(msg)
                elif msg_type == 'cancel':
                    self._handle_cancel(msg)
                elif msg_type == 'close':
                    break
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                import traceback
                traceback.print_exc()
                
        logger.info("Worker thread stopped")
        
    def _handle_send_message(self, msg: Dict[str, Any]):
        """Handle send_message request in worker thread."""
        text = msg['text']
        chat_id = msg['chat_id']
        
        logger.info(f"Worker: Sending message: {text[:50]}")
        
        if not self.active_agent or self.active_agent not in self.agents:
            self._send_error(chat_id, "No active agent")
            return
            
        agent_data = self.agents[self.active_agent]
        session = agent_data['session']
        agent_data['chat_id'] = chat_id
        agent_data['chunks'] = []  # Reset chunks for new message
        
        # Set up callbacks that reference agent_data
        def on_chunk(content):
            logger.debug(f"Worker: Received chunk: {content[:50]}")
            agent_data['chunks'].append(content)
            
        def on_tool_call(tool):
            tool_name = tool.get('title', 'unknown')
            logger.info(f"Worker: Tool call: {tool_name}")
            
            # Extract command and purpose for better display
            raw_input = tool.get('rawInput', {})
            command = raw_input.get('command', '')
            purpose = raw_input.get('__tool_use_purpose', '')
            
            # Format message with command details
            message_parts = [f"🔧 {tool_name}"]
            if purpose:
                message_parts.append(f"\n_{purpose}_")
            if command and command not in tool_name:
                message_parts.append(f"\n`{command}`")
            
            self._send_to_telegram_sync(agent_data['chat_id'], "\n".join(message_parts))
        
        def on_tool_update(update):
            """Handle tool completion and send stdout/stderr."""
            status = update.get('status')
            if status != 'completed':
                return
            
            raw_output = update.get('rawOutput', {})
            items = raw_output.get('items', [])
            
            if not items:
                return
            
            # Extract stdout/stderr from first item
            output_data = items[0].get('Json', {})
            stdout = output_data.get('stdout', '').strip()
            stderr = output_data.get('stderr', '').strip()
            exit_status = output_data.get('exit_status', '')
            
            if not stdout and not stderr:
                return
            
            # Truncate if too long (first 1000 + last 1000 bytes)
            def truncate_output(text, max_bytes=1000):
                if len(text) <= max_bytes * 2:
                    return text
                return f"{text[:max_bytes]}\n\n... (truncated {len(text) - max_bytes * 2} bytes) ...\n\n{text[-max_bytes:]}"
            
            output_parts = []
            if stdout:
                output_parts.append(f"**Output:**\n```\n{truncate_output(stdout)}\n```")
            if stderr:
                output_parts.append(f"**stderr:**\n```\n{truncate_output(stderr)}\n```")
            
            if output_parts:
                message = "\n".join(output_parts)
                self._send_to_telegram_sync(agent_data['chat_id'], message)
            
        def on_turn_end():
            logger.info(f"Worker: on_turn_end called")
            logger.info(f"Worker: agent_data keys: {agent_data.keys()}")
            logger.info(f"Worker: chunks type: {type(agent_data.get('chunks'))}")
            logger.info(f"Worker: chunks length: {len(agent_data.get('chunks', []))}")
            chunks = agent_data['chunks']
            logger.info(f"Worker: Turn end - {len(chunks)} chunks accumulated")
            logger.info(f"Worker: chunks bool: {bool(chunks)}")
            if chunks:
                message = "".join(chunks)
                logger.info(f"Worker: Sending final message (length: {len(message)})")
                self._send_to_telegram_sync(agent_data['chat_id'], message)
            else:
                logger.warning(f"Worker: Turn end but no chunks!")
        
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
        try:
            session.send_message(text)
            logger.info("Worker: Message sent successfully")
        except Exception as e:
            logger.error(f"Worker: Error sending message: {e}")
            import traceback
            traceback.print_exc()
            self._send_error(chat_id, str(e))
            
    def _handle_start_session(self, msg: Dict[str, Any]):
        """Handle start_session request in worker thread."""
        agent_name = msg.get('agent_name', 'kiro_default')
        working_dir = msg.get('working_dir', '/home/mark/git/remote-kiro')
        
        logger.info(f"Worker: Starting session for {agent_name}")
        
        try:
            client = ACPClient(working_dir)
            client.start()
            client.initialize()
            
            # Get full session response to capture models info
            session_result = client._send_request("session/new", {
                "cwd": working_dir,
                "mcpServers": []
            })
            session_id = session_result["sessionId"]
            session = ACPSession(session_id, client)
            
            # Store for this agent
            self.agents[agent_name] = {
                'client': client,
                'session': session,
                'session_id': session_id,
                'working_dir': working_dir,
                'chunks': [],  # Store chunks per agent
                'chat_id': None,  # Store chat_id per agent
                'models': session_result.get('models', {})  # Store models info
            }
            
            self.active_agent = agent_name
            logger.info(f"Worker: Session started for {agent_name}")
            
        except Exception as e:
            logger.error(f"Worker: Error starting session: {e}")
            import traceback
            traceback.print_exc()
            
    def _handle_cancel(self, msg: Dict[str, Any]):
        """Handle cancel request in worker thread."""
        if self.active_agent and self.active_agent in self.agents:
            session = self.agents[self.active_agent]['session']
            session.cancel()
            logger.info("Worker: Cancelled operation")
            
    def _send_to_telegram_sync(self, chat_id: int, text: str):
        """Send message to Telegram from worker thread."""
        logger.info(f"Worker: _send_to_telegram_sync called with text length: {len(text)}")
        if self.send_to_telegram:
            # Schedule the async call
            try:
                logger.debug(f"Worker: Scheduling async call to Telegram")
                asyncio.run_coroutine_threadsafe(
                    self.send_to_telegram(chat_id, text),
                    self.send_to_telegram.loop
                )
                logger.debug(f"Worker: Async call scheduled successfully")
            except Exception as e:
                logger.error(f"Error scheduling telegram message: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.warning(f"No send_to_telegram callback set")
            
    def _send_error(self, chat_id: int, error: str):
        """Send error message to Telegram."""
        self._send_to_telegram_sync(chat_id, f"❌ Error: {error}")
        
    # Public API (called from async layer)
    
    def _load_agent_config(self):
        """Load agent configuration from ~/.kiro/bot_agent_config.json"""
        import os
        config_path = os.path.expanduser('~/.kiro/bot_agent_config.json')
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load agent config: {e}")
        
        return {
            "agents": {},
            "default_directory": "/home/mark/git/remote-kiro"
        }
    
    def start_session(self, agent_name: str = 'kiro_default', working_dir: str = None):
        """Start a session (async-safe)."""
        if not self.running:
            self.start_worker()
            
        if working_dir is None:
            # Load agent config to get working directory
            config = self._load_agent_config()
            working_dir = config.get("agents", {}).get(agent_name, {}).get("working_directory")
            
            if not working_dir:
                working_dir = config.get("default_directory", "/home/mark/git/remote-kiro")
            
        logger.info(f"Starting session for agent '{agent_name}' in directory: {working_dir}")
            
        self.message_queue.put({
            'type': 'start_session',
            'agent_name': agent_name,
            'working_dir': working_dir
        })
        
    def send_message(self, text: str, chat_id: int):
        """Send message to Kiro (async-safe)."""
        self.message_queue.put({
            'type': 'send_message',
            'text': text,
            'chat_id': chat_id
        })
        
    def cancel_operation(self):
        """Cancel current operation (async-safe)."""
        self.message_queue.put({'type': 'cancel'})
        
    def close(self):
        """Close all sessions and stop worker."""
        self.running = False
        self.message_queue.put({'type': 'close'})
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            
        for agent_name, agent_data in self.agents.items():
            try:
                agent_data['client'].close()
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
            logger.info(f"Switched to agent: {agent_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch agent: {e}")
            return False
