"""Tests for text_utils module."""

import pytest

from text_utils import strip_ansi, truncate_message


def test_strip_ansi_removes_color_codes():
    text = "\x1b[31mRed text\x1b[0m"
    assert strip_ansi(text) == "Red text"


def test_strip_ansi_removes_multiple_codes():
    text = "\x1b[1m\x1b[32mBold green\x1b[0m\x1b[0m"
    assert strip_ansi(text) == "Bold green"


def test_strip_ansi_handles_plain_text():
    text = "Plain text"
    assert strip_ansi(text) == "Plain text"


def test_truncate_message_under_limit():
    text = "Short message"
    assert truncate_message(text, 100) == "Short message"


def test_truncate_message_over_limit():
    text = "A" * 5000
    result = truncate_message(text, 4000)
    assert len(result) == 4000
    assert result.endswith("\n...")


def test_truncate_message_exact_limit():
    text = "A" * 4000
    assert truncate_message(text, 4000) == text
