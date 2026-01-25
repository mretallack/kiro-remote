# Tasks: Telegram Attachment Support

## Implementation Tasks

### Configuration & Setup

- [x] **Task 1: Update settings.ini.template**
  - Add `attachments_dir` setting to `[bot]` section with default value
  - Add explanatory comment
  - **Expected outcome:** Template file includes new configuration option

- [x] **Task 2: Add configuration loading**
  - Read `attachments_dir` from config in bot initialization
  - Expand user paths (~/) to absolute paths
  - Set default to `~/.kiro/bot_attachments/` if not specified
  - **Expected outcome:** Bot loads and stores attachments directory path

- [x] **Task 3: Create attachments directory**
  - Check if directory exists on startup
  - Create directory with proper permissions (755) if missing
  - Log creation or use existing directory
  - **Expected outcome:** Attachments directory exists and is accessible

### Core Functionality

- [x] **Task 4: Implement filename sanitization**
  - Create `sanitize_filename()` function
  - Remove/replace dangerous characters: `/ \ : * ? " < > |`
  - Replace spaces with underscores
  - Preserve file extension
  - Limit to 255 characters
  - **Expected outcome:** Function returns safe filenames

- [x] **Task 5: Implement path generation**
  - Create `generate_attachment_path()` function
  - Use pattern: `{timestamp}_{user_id}_{sanitized_filename}`
  - Return absolute path in attachments directory
  - **Expected outcome:** Function generates unique, safe file paths

- [x] **Task 6: Implement message formatter**
  - Create `format_attachment_message()` function
  - Handle caption + attachment path
  - Handle no caption case
  - Format: `{caption}\n\nThe attachment is {file_path}` or `The attachment is {file_path}`
  - **Expected outcome:** Function returns properly formatted messages

### Handler Implementation

- [x] **Task 7: Implement photo handler**
  - Create `handle_photo()` async function
  - Check user authorization
  - Get highest resolution photo
  - Download file using Telegram API
  - Save to attachments directory
  - Format message with caption and path
  - Send to Kiro CLI via existing message handling
  - Handle errors gracefully
  - **Expected outcome:** Photos are downloaded and processed

- [x] **Task 8: Implement document handler**
  - Create `handle_document()` async function
  - Check user authorization
  - Get document file object
  - Download file using Telegram API
  - Save to attachments directory with original filename
  - Format message with caption and path
  - Send to Kiro CLI via existing message handling
  - Handle errors gracefully
  - **Expected outcome:** Documents are downloaded and processed

- [x] **Task 9: Register handlers**
  - Add photo handler to application
  - Add document handler to application
  - Ensure proper filter usage (filters.PHOTO, filters.Document.ALL)
  - **Expected outcome:** Handlers are registered and respond to file uploads

### Error Handling & Polish

- [x] **Task 10: Add error handling**
  - Handle download failures (network timeout, etc.)
  - Handle filesystem errors (permissions, disk space)
  - Send user-friendly error messages to Telegram
  - Log errors appropriately
  - **Expected outcome:** Errors are caught and reported gracefully

- [x] **Task 11: Update documentation**
  - Add attachment support section to README.md
  - Document configuration option
  - Provide usage examples
  - Note file size limitations
  - **Expected outcome:** README includes attachment feature documentation

### Testing

- [ ] **Task 12: Manual testing**
  - Test photo upload with caption
  - Test photo upload without caption
  - Test document upload with caption
  - Test document upload without caption
  - Test unauthorized user rejection
  - Test various file types
  - Verify files saved correctly
  - Verify Kiro CLI receives proper messages
  - **Expected outcome:** All scenarios work as expected

## Dependencies

- Existing: `python-telegram-bot`, `pathlib`, `re`, `os`, `time`
- No new dependencies required

## Notes

- Maintain existing bot architecture
- Reuse authorization checks
- No changes to KiroSession or agent management
- Keep implementation minimal and focused
