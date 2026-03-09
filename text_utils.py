"""Text utilities for formatting command output for Telegram."""

import re


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def truncate_message(text: str, max_length: int = 4000) -> str:
    """Truncate message to fit Telegram limits."""
    if len(text) <= max_length:
        return text

    return text[: max_length - 4] + "\n..."
