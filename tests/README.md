# Kiro CLI Tests

This directory contains pytest-based tests for validating the Kiro CLI interface.

## Purpose

These tests are designed to validate that new kiro-cli releases work correctly with the Telegram bot interface. They test:

- Basic CLI commands (help, usage)
- Agent commands (list, swap)
- Chat interface functionality
- Tools trust functionality

## Running Tests

From the project root:

```bash
# Run all tests
make test

# Run tests with verbose output
make test-setup
venv/bin/python -m pytest tests/ -v -s

# Run specific test file
venv/bin/python -m pytest tests/test_kiro_cli.py -v
```

## Test Categories

- **TestKiroCLI**: Tests basic CLI commands and agent functionality
- **TestKiroInterface**: Tests interactive chat interface through subprocess

## Adding New Tests

Add new test methods to the existing test classes or create new test files following the `test_*.py` naming convention.
