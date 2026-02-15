# Tests

## Running Tests

```bash
# Run all tests
python3.12 -m pytest tests/ -v

# Run with output visible
python3.12 -m pytest tests/ -v -s

# Run specific test
python3.12 -m pytest tests/test_complete_flow.py -v
```

## Test Files

### ACP Tests (New)
- `test_complete_flow.py` - Complete end-to-end test simulating bot behavior with async event loop
  - Tests simple messages
  - Tests tool calls
  - Tests Telegram message delivery
  - **Status**: ✅ PASSING

### Legacy Tests
- `test_kiro_cli.py` - Old tests using `kiro-cli chat` (text-based interface)
  - **Status**: ⚠️ May be outdated, uses old text-based protocol

## Test Coverage

The ACP integration is tested through:
1. **Message Flow**: Sending messages and receiving responses
2. **Tool Calls**: Detection and display of tool execution
3. **Turn Completion**: Proper handling of turn_end signals
4. **Telegram Integration**: Mock bot receives messages correctly

## Notes

- Tests use Python 3.12 for async/await support
- The complete flow test simulates the actual bot with mocked Telegram API
- All tests pass successfully with the ACP implementation
