# Group Topic Agents - Design

## Architecture Overview

The design extends the existing `TelegramBot` and `KiroSessionACP` classes to support group forum topics. The key insight is that `KiroSessionACP` already supports multiple concurrent agents via `self.agents` dict — currently only one is "active" at a time for the 1-to-1 chat. In group mode, we remove the single-active-agent constraint and route by `message_thread_id` instead.

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Group                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Topic:   │  │ Topic:   │  │ Topic:   │              │
│  │ thingino │  │ facebook │  │ dicio    │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
└───────┼──────────────┼──────────────┼───────────────────┘
        │              │              │
        ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                   TelegramBot                            │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │           TopicRouter (new)                      │    │
│  │                                                  │    │
│  │  topic_name → agent_name mapping                 │    │
│  │  message_thread_id → agent_name cache            │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                               │
│  ┌──────────────────────▼──────────────────────────┐    │
│  │           KiroSessionACP (modified)              │    │
│  │                                                  │    │
│  │  agents["thingino"] ─── kiro-cli process         │    │
│  │  agents["facebook"] ─── kiro-cli process         │    │
│  │  agents["dicio"]    ─── kiro-cli process         │    │
│  │                                                  │    │
│  │  send_to_kiro(msg, agent_name, chat_id, thread)  │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Topic Name = Agent Name (case-insensitive)

No configuration file mapping topics to agents. The topic name IS the agent name. This keeps it simple — create a topic called "thingino" and it routes to the thingino agent.

### 2. No Active Agent in Group Mode

In 1-to-1 mode, `self.active_agent` tracks which agent receives messages. In group mode, the agent is determined per-message from the topic. The `active_agent` field is only used for 1-to-1 chat.

### 3. Concurrent Sessions via Existing Infrastructure

`KiroSessionACP.agents` dict already holds multiple agent sessions. Currently `restart_with_agent()` tears down and rebuilds. For group mode, we use `start_agent_session(agent_name)` to lazily start agents without stopping others.

### 4. Thread-ID Routing for Responses

When sending responses back to Telegram, include `message_thread_id` so replies land in the correct topic. This requires passing thread_id through the callback chain.

## Sequence Diagram - Message in Topic

```
User                Telegram           TelegramBot         KiroSessionACP
 │                    │                    │                    │
 │─── msg in topic ──▶│                    │                    │
 │                    │── update ──────────▶│                    │
 │                    │                    │                    │
 │                    │                    │── is_group_forum? ─▶│
 │                    │                    │   yes               │
 │                    │                    │                    │
 │                    │                    │── get thread_id ───▶│
 │                    │                    │── get topic_name ──▶│
 │                    │                    │── resolve agent ───▶│
 │                    │                    │                    │
 │                    │                    │── agent started? ──▶│
 │                    │                    │   no → start it     │
 │                    │                    │                    │
 │                    │                    │── send_message ────▶│
 │                    │                    │   (agent, chat_id,  │
 │                    │                    │    thread_id)        │
 │                    │                    │                    │
 │                    │                    │◀── response ────────│
 │                    │                    │   (with thread_id)  │
 │                    │◀── reply in topic ─│                    │
 │◀───────────────────│                    │                    │
```

## Implementation Details

### TelegramBot Changes

#### New: `handle_group_message()`

```python
async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle message in a group forum topic."""
    # Extract thread_id (topic identifier)
    thread_id = update.message.message_thread_id
    if thread_id is None:
        return  # General topic or non-forum group, ignore

    # Resolve topic name to agent name
    agent_name = await self._resolve_topic_agent(update, context, thread_id)
    if not agent_name:
        return  # Error already sent

    # Ensure agent session is running
    if agent_name not in self.kiro.agents:
        await update.message.reply_text(
            f"🔄 Starting agent '{agent_name}'...",
            message_thread_id=thread_id
        )
        self.kiro.start_agent_session(agent_name)

    # Route message to agent
    self.kiro.send_message_to_agent(
        agent_name=agent_name,
        message=update.message.text,
        chat_id=update.effective_chat.id,
        thread_id=thread_id
    )
```

#### Modified: `handle_message()`

Add a check at the top:

```python
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing auth check ...

    # Route group forum messages differently
    if update.effective_chat.type in ("group", "supergroup"):
        if update.message.is_topic_message:
            await self.handle_group_message(update, context)
            return

    # ... existing 1-to-1 logic unchanged ...
```

#### New: `_resolve_topic_agent()`

```python
async def _resolve_topic_agent(self, update, context, thread_id) -> Optional[str]:
    """Resolve a topic's thread_id to an agent name."""
    # Get topic name from the forum_topic_created field or cache
    # Telegram doesn't always include topic name in messages,
    # so we maintain a thread_id -> agent_name cache

    if thread_id in self._topic_agent_cache:
        return self._topic_agent_cache[thread_id]

    # Try to get forum topic info via Bot API
    # Fall back: use getForumTopicInfo or cache from topic creation events
    topic_name = await self._get_topic_name(update, context, thread_id)
    if not topic_name:
        await update.message.reply_text(
            "❌ Could not determine topic name",
            message_thread_id=thread_id
        )
        return None

    # Case-insensitive match against available agents
    agent_name = self._match_agent_name(topic_name)
    if not agent_name:
        agents = self._get_available_agent_names()
        await update.message.reply_text(
            f"❌ No agent matches topic '{topic_name}'\n\n"
            f"Available agents:\n" + "\n".join(f"• `{a}`" for a in agents),
            message_thread_id=thread_id,
            parse_mode="Markdown"
        )
        return None

    self._topic_agent_cache[thread_id] = agent_name
    return agent_name
```

### KiroSessionACP Changes

#### New: `send_message_to_agent()`

```python
def send_message_to_agent(self, agent_name: str, message: str, chat_id: int, thread_id: int):
    """Send a message to a specific agent (for group topic routing)."""
    self.message_queue.put({
        "type": "prompt",
        "agent_name": agent_name,
        "message": message,
        "chat_id": chat_id,
        "thread_id": thread_id,
    })
```

#### New: `start_agent_session()`

```python
def start_agent_session(self, agent_name: str):
    """Start a specific agent session without changing active_agent."""
    self.message_queue.put({
        "type": "start_agent",
        "agent_name": agent_name,
    })
```

#### Modified: `_send_to_telegram_sync()`

Add `thread_id` parameter:

```python
def _send_to_telegram_sync(self, chat_id, text, thread_id=None, **kwargs):
    """Send message to Telegram, optionally in a specific thread."""
    # Include message_thread_id in the send_message call
    ...
```

#### Modified: Worker loop prompt handling

The worker currently uses `self.active_agent` to determine which session to prompt. For group messages, the `agent_name` is explicit in the queue message:

```python
def _handle_prompt(self, msg):
    agent_name = msg.get("agent_name") or self.active_agent
    thread_id = msg.get("thread_id")
    # Use agent_name to look up session, pass thread_id for response routing
```

### Response Routing

The callback chain for sending responses back needs `thread_id`:

1. `ACPSession` emits chunks → `KiroSessionACP` buffers them
2. On flush, `_send_to_telegram_sync(chat_id, text, thread_id=thread_id)`
3. The async callback includes `message_thread_id=thread_id` in `bot.send_message()`

Each agent's entry in `self.agents[name]` already has a `chat_id` field. We add a `thread_id` field:

```python
self.agents[agent_name] = {
    ...
    "thread_id": None,  # Set per-prompt for group routing
}
```

### Topic Name Resolution

Telegram's Bot API doesn't include the topic name in every message update. Strategies:

1. **`getForumTopicInfo`** — not available in python-telegram-bot yet
2. **Listen for `forum_topic_created` / `forum_topic_edited` events** — build cache
3. **Use `get_chat` with topic info** — may work for supergroups
4. **Manual cache via bot command** — `\topic map <agent>` in a topic to register it

**Chosen approach**: Hybrid. Listen for topic lifecycle events to build cache. For topics that already exist when bot joins, provide a `\topic register` command or attempt to use `getForumTopicIconCustomEmojiId` heuristics. In practice, the simplest path is:

- On first message in an unknown thread_id, use the Telegram Bot API `get_forum_topic_icon_sticker` or parse the `message.reply_to_message.forum_topic_created.name` if available.
- Maintain a persistent JSON cache file (`~/.kiro/topic_agent_map.json`) mapping `{group_id}_{thread_id}` → `agent_name`.
- Provide `\topic register <agent>` as fallback for topics the bot can't auto-detect.

### Configuration (settings.ini)

```ini
[group]
# Optional: restrict to specific group ID
group_id = -1001234567890
# Optional: path to topic-agent cache
topic_cache = ~/.kiro/topic_agent_map.json
```

### Topic Auto-Creation (`\topic sync`)

The bot can create forum topics for all known agents automatically:

```python
async def sync_topics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create forum topics for all agents that don't already have one."""
    chat_id = update.effective_chat.id
    existing_topics = set(self._topic_agent_cache.values())
    agents = self._get_available_agent_names()

    created = []
    for agent in agents:
        if agent not in existing_topics:
            result = await context.bot.create_forum_topic(
                chat_id=chat_id, name=agent
            )
            self._topic_agent_cache[result.message_thread_id] = agent
            created.append(agent)

    self._save_topic_cache()
    await update.message.reply_text(
        f"✅ Created {len(created)} topics: {', '.join(created)}" if created
        else "✅ All agents already have topics"
    )
```

Requires bot admin permission: `can_manage_topics`.

### Auto-Sync on Startup

When `group_id` is configured in `settings.ini`, the bot auto-syncs topics on startup:

```python
async def _auto_sync_topics(self):
    """On startup, create topics for agents not already in cache."""
    if not self.group_id:
        return

    self._load_topic_cache()
    cached_agents = set(self._topic_agent_cache.values())
    agents = self._get_available_agent_names()

    for agent in agents:
        if agent not in cached_agents:
            try:
                result = await self.application.bot.create_forum_topic(
                    chat_id=self.group_id, name=agent
                )
                self._topic_agent_cache[result.message_thread_id] = agent
            except Exception as e:
                logger.warning(f"Failed to create topic for '{agent}': {e}")

    self._save_topic_cache()
```

Flow:
1. Bot starts → loads `topic_agent_map.json` cache
2. If `group_id` configured → for each agent not in cache, call `createForumTopic`
3. Cache updated and saved

### Limitations of Topic Auto-Creation

- **No Bot API to list existing topics**: The Telegram Bot API does not provide a `getForumTopics` method. Only the full MTProto client API (`channels.getForumTopics`) supports this. The bot cannot discover pre-existing topics.
- **Duplicate topic names possible**: If topics were manually created before the bot ran (empty cache), the bot will create duplicates since Telegram allows multiple topics with the same name.
- **First-run with existing topics**: Use `\topic register <agent>` in each pre-existing topic to populate the cache, OR delete the manual topics and let the bot recreate them.
- **Cache is the source of truth**: If the cache file is deleted, the bot will create new topics on next startup (resulting in duplicates of any existing ones).

### Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Topic name doesn't match any agent | Reply with error + available agents list |
| Agent session fails to start | Reply with error in topic |
| Prompt timeout for an agent | Reply with timeout message in that topic |
| Usage limit reached | Reply in topic, don't affect other topics |
| Topic renamed | Cache invalidated on next message; re-resolves |

### Typing Indicators

Currently typing indicators use `chat_id`. For groups with topics, we also need `message_thread_id`:

```python
await context.bot.send_chat_action(
    chat_id=chat_id,
    action=ChatAction.TYPING,
    message_thread_id=thread_id
)
```

## Files to Modify

| File | Changes |
|------|---------|
| `telegram_kiro_bot.py` | Add group message handling, topic resolution, thread-aware responses |
| `kiro_session_acp.py` | Add `send_message_to_agent()`, `start_agent_session()`, thread_id in response routing |
| `settings.ini.template` | Add `[group]` section |
| `README.md` | Document group topic feature |

## Telegram Group Setup (Prerequisites)

### 1. Create the group

Create a new Telegram group and add the bot as a member.

### 2. Enable forum topics

Group settings → Edit → Enable **Topics** (auto-converts to supergroup).

### 3. Bot admin permissions

Promote the bot to admin with at minimum:
- ✅ Read messages
- ✅ Send messages

### 4. Disable bot privacy mode

In BotFather: `/mybots` → your bot → Bot Settings → Group Privacy → **Turn OFF**

Without this, the bot won't receive messages in group topics.

### 5. Create topics (automatic)

The bot can auto-create topics for all known agents using `\topic sync` in the group. This requires the additional admin permission:
- ✅ Manage Topics (`can_manage_topics`)

Alternatively, create topics manually — each topic name must match an agent name (case-insensitive).

### 6. Get the group ID

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates" | python3 -m json.tool | grep -A5 chat
```

The `chat.id` will be a negative number like `-1001234567890`. Optionally configure in `settings.ini`:

```ini
[group]
group_id = -1001234567890
```

## Out of Scope

- Multiple authorized users per group
- Per-topic agent configuration file (topic name = agent name is sufficient)
- Creating agents from within topics
- Cross-topic agent communication
