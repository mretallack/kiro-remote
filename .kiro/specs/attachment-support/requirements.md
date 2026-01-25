# Requirements: Telegram Attachment Support

## Overview
Enable the Telegram Kiro Bot to receive images and file attachments from users, download them to a configurable directory, and pass the file paths to Kiro CLI for processing.

## User Stories

### US-1: Image Upload Support
As a bot user, I want to send images to Kiro so that I can ask questions about visual content or request image analysis.

**Acceptance Criteria:**
- WHEN a user sends an image (photo) to the bot, THE SYSTEM SHALL download the image to the attachments directory
- WHEN the image is downloaded, THE SYSTEM SHALL send a message to Kiro CLI containing the user's caption (if any) and the file path
- WHEN no caption is provided, THE SYSTEM SHALL send a default message indicating an attachment was received
- WHEN the download fails, THE SYSTEM SHALL notify the user with an error message

### US-2: Document/File Upload Support
As a bot user, I want to send documents and files to Kiro so that I can request code reviews, file analysis, or content processing.

**Acceptance Criteria:**
- WHEN a user sends a document/file to the bot, THE SYSTEM SHALL download the file to the attachments directory
- WHEN the file is downloaded, THE SYSTEM SHALL send a message to Kiro CLI containing the user's caption (if any) and the file path
- WHEN the file exceeds Telegram's size limit, THE SYSTEM SHALL notify the user that the file is too large
- WHEN the download fails, THE SYSTEM SHALL notify the user with an error message

### US-3: Configurable Attachments Directory
As a bot administrator, I want to configure where attachments are stored so that I can manage disk space and organize files appropriately.

**Acceptance Criteria:**
- WHEN the bot starts, THE SYSTEM SHALL read the attachments directory path from settings.ini
- WHEN the attachments directory does not exist, THE SYSTEM SHALL create it automatically
- WHEN the attachments directory path is not configured, THE SYSTEM SHALL use a default path (~/.kiro/bot_attachments/)
- WHEN the directory cannot be created or accessed, THE SYSTEM SHALL log an error and fail gracefully

### US-4: File Naming and Organization
As a bot administrator, I want attachments to be named systematically so that files are easily identifiable and don't overwrite each other.

**Acceptance Criteria:**
- WHEN a file is downloaded, THE SYSTEM SHALL name it using the pattern: `{timestamp}_{user_id}_{original_filename}`
- WHEN a filename contains special characters, THE SYSTEM SHALL sanitize them to prevent filesystem issues
- WHEN a file with the same name exists, THE SYSTEM SHALL append a unique identifier to prevent overwrites

### US-5: Message Format to Kiro CLI
As a developer, I want a consistent message format when attachments are sent to Kiro so that the AI can reliably process file references.

**Acceptance Criteria:**
- WHEN an attachment is received with a caption, THE SYSTEM SHALL format the message as: `{user_caption}\n\nThe attachment is {file_path}`
- WHEN an attachment is received without a caption, THE SYSTEM SHALL format the message as: `The attachment is {file_path}`
- WHEN multiple attachments are sent in a single message, THE SYSTEM SHALL list all file paths

### US-6: Attachment Cleanup
As a bot administrator, I want old attachments to be managed so that disk space doesn't grow indefinitely.

**Acceptance Criteria:**
- WHEN the bot processes attachments, THE SYSTEM SHALL maintain a record of downloaded files
- WHEN a configurable retention period expires, THE SYSTEM SHALL delete old attachments (optional feature for future enhancement)
- WHEN attachments are deleted, THE SYSTEM SHALL log the cleanup operation

## EARS Notation Requirements

### Functional Requirements

**FR-1: Image Download**
- WHEN a user sends a photo message to the bot
- THE SYSTEM SHALL download the highest resolution version available
- THE SYSTEM SHALL save it to the configured attachments directory
- THE SYSTEM SHALL return the absolute file path

**FR-2: Document Download**
- WHEN a user sends a document/file message to the bot
- THE SYSTEM SHALL download the file with its original filename
- THE SYSTEM SHALL save it to the configured attachments directory
- THE SYSTEM SHALL return the absolute file path

**FR-3: Configuration Loading**
- WHEN the bot initializes
- THE SYSTEM SHALL read the `attachments_dir` setting from the `[bot]` section of settings.ini
- THE SYSTEM SHALL expand user paths (e.g., ~/) to absolute paths
- THE SYSTEM SHALL create the directory if it doesn't exist

**FR-4: File Naming**
- WHEN saving an attachment
- THE SYSTEM SHALL generate a filename using: `{unix_timestamp}_{telegram_user_id}_{sanitized_original_name}`
- THE SYSTEM SHALL sanitize filenames by removing/replacing characters: `/ \ : * ? " < > |`
- THE SYSTEM SHALL preserve the original file extension

**FR-5: Message Formatting**
- WHEN an attachment is successfully downloaded
- THE SYSTEM SHALL construct a message for Kiro CLI
- THE SYSTEM SHALL include the user's caption text (if provided) followed by attachment information
- THE SYSTEM SHALL use the format: `The attachment is {absolute_file_path}`

**FR-6: Error Handling**
- WHEN a download fails due to network issues
- THE SYSTEM SHALL log the error with details
- THE SYSTEM SHALL send a user-friendly error message to Telegram
- THE SYSTEM SHALL not send anything to Kiro CLI

**FR-7: Authorization Check**
- WHEN an attachment is received
- THE SYSTEM SHALL verify the sender is the authorized user
- THE SYSTEM SHALL reject attachments from unauthorized users
- THE SYSTEM SHALL not download files from unauthorized users

### Non-Functional Requirements

**NFR-1: Performance**
- File downloads SHALL complete within 30 seconds for files up to 20MB
- The bot SHALL remain responsive during file downloads

**NFR-2: Security**
- File paths SHALL be validated to prevent directory traversal attacks
- Downloaded files SHALL inherit secure permissions (644 for files)
- The attachments directory SHALL be created with appropriate permissions (755)

**NFR-3: Reliability**
- Failed downloads SHALL not crash the bot
- Partial downloads SHALL be cleaned up
- The bot SHALL continue processing other messages during download failures

**NFR-4: Compatibility**
- The feature SHALL work with existing bot commands and functionality
- The feature SHALL not interfere with agent management or conversation persistence
- The feature SHALL support all Telegram file types (photos, documents, videos, audio)

## Out of Scope

- Automatic file type detection and specialized handling
- Image compression or format conversion
- Virus scanning or content filtering
- Attachment preview generation
- Multi-file batch uploads in a single operation
- Automatic cleanup/retention policies (future enhancement)
