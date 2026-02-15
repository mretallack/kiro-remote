# Steps to Reproduce: kiro-cli ValidationException After Image + Model Switch

## Prerequisites
- kiro-cli installed and configured
- Any image file (e.g., a screenshot or photo)

## Steps

1. **Start kiro-cli**
   ```bash
   kiro-cli chat
   ```

2. **Verify you're on auto model** (default)
   - Look at the bottom of the screen: `Model: auto`
   - If not, run `/model` and select `auto`

3. **Send an image prompt**
   ```
   look at /path/to/your/image.jpg
   ```
   - When prompted "Allow this action?", type `t` (trust)
   - Wait for kiro to analyze the image
   - Verify you get a successful response describing the image

4. **Switch to a text-only model**
   ```
   /model
   ```
   - Use arrow keys to select `deepseek-3.2`
   - Press Enter
   - Verify it says "Using deepseek-3.2"

5. **Send a simple text prompt**
   ```
   hi
   ```

## Expected Result
Kiro responds normally with a greeting.

## Actual Result
kiro-cli crashes with:
```
Kiro is having trouble responding right now: 
   0: Failed to send the request: An unknown error occurred: ValidationException
   1: An unknown error occurred: ValidationException
   2: unhandled error (ValidationException)
   3: service error
   4: unhandled error (ValidationException)
   5: Error { code: "ValidationException", message: "Improperly formed request.", 
      aws_request_id: "<some-id>" }

Location:
   crates/chat-cli/src/cli/chat/mod.rs:1460
```

## Notes
- The session becomes unusable after this error
- The issue occurs because deepseek-3.2 doesn't support images, but kiro-cli sends the conversation history (including the image) to it
- This also affects ACP mode with the same underlying cause
