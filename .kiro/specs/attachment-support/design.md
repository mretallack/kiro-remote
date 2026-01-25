# Design: Telegram Attachment Support

## Architecture Overview

The attachment support feature extends the existing Telegram Kiro Bot to handle file downloads and integrate them into the Kiro CLI conversation flow. The design maintains the bot's existing architecture while adding new handlers and utility functions.

## Component Design

### 1. Configuration Management

**Location:** `settings.ini`

**New Configuration:**
```ini
[bot]
authorized_user = markretallack
auto_trust = true
progress_updates = true
attachments_dir = ~/.kiro/bot_attachments  # New setting
```

**Implementation:**
- Add `attachments_dir` to the `[bot]` section
- Default value: `~/.kiro/bot_attachments/`
- Path expansion handled during initialization
- Directory creation on bot startup

### 2. File Download Handler

**Component:** `AttachmentHandler` class or module functions

**Responsibilities:**
- Download files from Telegram servers
- Generate unique filenames
- Save files to configured directory
- Return absolute file paths

**Key Methods:**

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE)
async def download_attachment(file_obj, user_id: int, original_name: str) -> str
def sanitize_filename(filename: str) -> str
def generate_attachment_path(user_id: int, filename: str) -> str
```

### 3. Message Formatter

**Component:** Message formatting utility

**Responsibilities:**
- Combine user caption with attachment path
- Format message for Kiro CLI consumption
- Handle cases with/without captions

**Format Logic:**
```
IF caption exists:
    message = f"{caption}\n\nThe attachment is {file_path}"
ELSE:
    message = f"The attachment is {file_path}"
```

### 4. Integration with Existing Bot

**Modified Components:**
- `KiroSession` class: No changes required
- Message handlers: Add new handlers for photos and documents
- Application setup: Register new handlers

**Handler Registration:**
```python
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
```

## Sequence Diagrams

### Photo Upload Flow

```
User                Telegram Bot           Telegram API         Filesystem         Kiro CLI
  |                      |                      |                    |                 |
  |--Send Photo+Caption->|                      |                    |                 |
  |                      |--Get File Info------>|                    |                 |
  |                      |<-File Object---------|                    |                 |
  |                      |--Download File------>|                    |                 |
  |                      |<-File Bytes----------|                    |                 |
  |                      |--Generate Path------>|                    |                 |
  |                      |--Write File--------->|                    |                 |
  |                      |<-Success-------------|                    |                 |
  |                      |--Format Message------|                    |                 |
  |                      |--Send to Kiro CLI----------------------------------->|
  |                      |                      |                    |                 |
  |<-Typing Indicator----|                      |                    |                 |
  |                      |<-Kiro Response--------------------------------------|
  |<-Bot Response--------|                      |                    |                 |
```

### Document Upload Flow

```
User                Telegram Bot           Telegram API         Filesystem         Kiro CLI
  |                      |                      |                    |                 |
  |--Send Doc+Caption--->|                      |                    |                 |
  |                      |--Verify Auth-------->|                    |                 |
  |                      |--Get File Info------>|                    |                 |
  |                      |<-File Object---------|                    |                 |
  |                      |--Check Size--------->|                    |                 |
  |                      |--Download File------>|                    |                 |
  |                      |<-File Bytes----------|                    |                 |
  |                      |--Sanitize Name-------|                    |                 |
  |                      |--Generate Path------>|                    |                 |
  |                      |--Write File--------->|                    |                 |
  |                      |<-Success-------------|                    |                 |
  |                      |--Format Message------|                    |                 |
  |                      |--Send to Kiro CLI----------------------------------->|
  |                      |                      |                    |                 |
  |<-Processing Msg------|                      |                    |                 |
  |                      |<-Kiro Response--------------------------------------|
  |<-Bot Response--------|                      |                    |                 |
```

### Error Handling Flow

```
User                Telegram Bot           Telegram API         Filesystem
  |                      |                      |                    |
  |--Send File---------->|                      |                    |
  |                      |--Download File------>|                    |
  |                      |<-Error: Timeout------|                    |
  |                      |--Log Error-----------|                    |
  |<-Error Message-------|                      |                    |
  |                      |                      |                    |
```

## Data Structures

### Attachment Metadata

```python
{
    'file_id': str,           # Telegram file ID
    'file_path': str,         # Local absolute path
    'original_name': str,     # Original filename
    'user_id': int,           # Telegram user ID
    'timestamp': float,       # Unix timestamp
    'file_size': int,         # Size in bytes
    'mime_type': str          # MIME type (if available)
}
```

### Configuration Structure

```python
config = {
    'telegram': {
        'token': str
    },
    'bot': {
        'authorized_user': str,
        'auto_trust': bool,
        'progress_updates': bool,
        'attachments_dir': str  # New field
    }
}
```

## Implementation Considerations

### 1. File Naming Strategy

**Pattern:** `{timestamp}_{user_id}_{sanitized_original_name}`

**Example:** `1737789050_123456789_screenshot.png`

**Sanitization Rules:**
- Replace spaces with underscores
- Remove: `/ \ : * ? " < > |`
- Preserve file extension
- Limit filename length to 255 characters
- Handle Unicode characters appropriately

### 2. Directory Structure

```
~/.kiro/bot_attachments/
├── 1737789050_123456789_image.png
├── 1737789051_123456789_document.pdf
├── 1737789052_123456789_code.py
└── ...
```

**Alternative (future enhancement):**
```
~/.kiro/bot_attachments/
├── 2026-01/
│   ├── 25/
│   │   ├── 1737789050_123456789_image.png
│   │   └── 1737789051_123456789_document.pdf
└── ...
```

### 3. Error Handling Strategy

**Download Errors:**
- Network timeout: Retry once, then fail with user message
- File too large: Immediate user notification
- Permission denied: Log error, notify user
- Disk space: Check available space, notify user

**Filesystem Errors:**
- Directory creation failure: Log and exit gracefully
- Write permission issues: Log and notify user
- Path traversal attempts: Reject and log security event

### 4. Security Considerations

**Path Validation:**
```python
def validate_path(base_dir: Path, file_path: Path) -> bool:
    """Ensure file_path is within base_dir"""
    return file_path.resolve().is_relative_to(base_dir.resolve())
```

**Filename Sanitization:**
```python
def sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from filename"""
    # Remove path separators and special chars
    safe_chars = re.sub(r'[/\\:*?"<>|]', '_', filename)
    # Limit length
    return safe_chars[:255]
```

**File Permissions:**
- Attachments directory: `0o755` (rwxr-xr-x)
- Downloaded files: `0o644` (rw-r--r--)

### 5. Integration Points

**Existing Code Modifications:**

1. **Configuration Loading** (`__init__` or startup):
   - Add `attachments_dir` parsing
   - Create directory if not exists
   - Store in instance variable

2. **Handler Registration** (main application setup):
   - Add photo handler
   - Add document handler
   - Maintain existing text handler priority

3. **Authorization Check** (reuse existing):
   - Apply same `authorized_user` check
   - Reject unauthorized file uploads

**No Changes Required:**
- `KiroSession` class
- Agent management logic
- Conversation persistence
- Response processing threads

### 6. Telegram API Considerations

**File Size Limits:**
- Photos: Up to 10 MB (automatically compressed by Telegram)
- Documents: Up to 20 MB for bots
- Larger files: Not supported, user notification required

**File Types Supported:**
- Photos (JPEG, PNG, WebP)
- Documents (any file type)
- Videos (future enhancement)
- Audio (future enhancement)
- Voice messages (future enhancement)

**API Methods Used:**
- `get_file()`: Get file metadata and download URL
- `download_to_drive()`: Download file to local filesystem

## Testing Strategy

### Unit Tests

1. **Filename Sanitization:**
   - Test special character removal
   - Test length limiting
   - Test Unicode handling

2. **Path Generation:**
   - Test timestamp formatting
   - Test user ID inclusion
   - Test path validation

3. **Message Formatting:**
   - Test with caption
   - Test without caption
   - Test with multiple attachments

### Integration Tests

1. **File Download:**
   - Mock Telegram API responses
   - Test successful download
   - Test network failures
   - Test file size limits

2. **End-to-End Flow:**
   - Send photo with caption
   - Verify file saved correctly
   - Verify message sent to Kiro CLI
   - Verify response received

### Manual Testing

1. Send various file types
2. Test with/without captions
3. Test unauthorized user rejection
4. Test disk space scenarios
5. Test concurrent uploads

## Performance Considerations

**Async Operations:**
- File downloads are async (non-blocking)
- Bot remains responsive during downloads
- Typing indicators shown during processing

**Resource Management:**
- No in-memory buffering of large files
- Stream downloads directly to disk
- Clean up partial downloads on failure

**Scalability:**
- Single user bot (no concurrency issues)
- File storage grows linearly with usage
- Future: Implement cleanup/retention policy

## Future Enhancements

1. **Automatic Cleanup:**
   - Configurable retention period
   - Scheduled cleanup task
   - Size-based limits

2. **File Type Handling:**
   - Video support
   - Audio/voice message support
   - Automatic transcription

3. **Advanced Features:**
   - Image compression options
   - Thumbnail generation
   - File metadata extraction
   - Duplicate detection

4. **Organization:**
   - Date-based subdirectories
   - User-based subdirectories
   - File type categorization

## Dependencies

**Existing:**
- `python-telegram-bot` (already installed)
- `pathlib` (standard library)
- `re` (standard library)
- `os` (standard library)

**No New Dependencies Required**

## Rollback Plan

If issues arise:
1. Remove handler registrations
2. Comment out attachment-related code
3. Bot continues functioning without attachment support
4. No data loss (existing conversations unaffected)

## Documentation Updates

**README.md additions:**
- Attachment support section
- Configuration example
- Usage examples
- File type limitations

**settings.ini.template update:**
- Add `attachments_dir` with default value
- Add comment explaining the setting
