# Proposal: File/Artifact Sending from Kiro to Telegram

## Problem
Currently, when Kiro builds artifacts (APKs, executables, etc.), there's no way to automatically send them back through the Telegram interface. Users must manually retrieve files from the system.

## Solution Options

### Option 1: MCP Server Integration (Recommended)
Use an MCP server like `simple-telegram-mcp` to give Kiro direct Telegram sending capabilities.

**Implementation:**
1. Install MCP server: `pip install simple-telegram-mcp`
2. Configure MCP in Kiro CLI to include Telegram tools
3. Kiro can then use `/send_file` or similar commands to push files directly

**Pros:**
- Clean separation of concerns
- Kiro handles the logic, MCP handles delivery
- Extensible to other platforms
- No modification to existing bot code

**Cons:**
- Additional dependency
- Requires MCP configuration

### Option 2: Enhanced Bot Wrapper
Modify the existing `telegram_kiro_bot.py` to detect file requests and handle uploads.

**Implementation:**
1. Add file detection in bot's response parsing
2. Implement Telegram file upload API calls
3. Add commands like `/get_last_build` or `/send <filepath>`

**Pros:**
- Self-contained solution
- Direct control over file handling
- Can implement custom logic

**Cons:**
- Couples file handling with bot logic
- Requires bot code changes
- Less flexible for other use cases

### Option 3: Hybrid Approach
Combine both: use MCP for Kiro-side sending, enhance bot for user-initiated retrieval.

**Implementation:**
1. MCP server for Kiro to push files automatically
2. Bot commands for manual file requests
3. Shared file staging area

## Recommended Implementation

**Phase 1: MCP Integration**
```bash
# Add to Kiro MCP configuration
{
  "telegram": {
    "server": "simple-telegram-mcp",
    "config": {
      "bot_token": "...",
      "chat_id": "..."
    }
  }
}
```

**Phase 2: Usage Pattern**
```
User: "Build the Android APK"
Kiro: "Building... Done. APK created at /path/to/app.apk"
Kiro: [automatically sends file via MCP]
```

## Benefits
- Seamless workflow from request to delivery
- No manual file retrieval needed
- Maintains conversation context
- Extensible to other file types and platforms

## Next Steps
1. Test `simple-telegram-mcp` compatibility with Kiro CLI
2. Configure MCP server with bot credentials
3. Define file sending triggers and patterns
4. Implement fallback mechanisms for large files
