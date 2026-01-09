#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch, MagicMock
import subprocess
import sys
import os

# Add current directory to path to import the bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_kiro_bot import KiroSession, TelegramBot

class TestKiroSession(unittest.TestCase):
    
    @patch('subprocess.Popen')
    def test_ansi_stripping(self, mock_popen):
        """Test ANSI escape sequence removal"""
        session = KiroSession()
        
        # Test various ANSI sequences
        test_cases = [
            ("\x1b[31mRed text\x1b[0m", "Red text"),
            ("\x1b[1;32mBold green\x1b[0m", "Bold green"),
            ("Normal \x1b[33mYellow\x1b[0m text", "Normal Yellow text"),
            ("No ANSI codes", "No ANSI codes")
        ]
        
        for input_text, expected in test_cases:
            result = session._strip_ansi(input_text)
            self.assertEqual(result, expected)

class TestTelegramBot(unittest.TestCase):
    
    def setUp(self):
        self.bot = TelegramBot("test_token")
    
    @patch('subprocess.run')
    def test_get_updates(self, mock_run):
        """Test Telegram API updates parsing"""
        # Mock successful API response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": [{"update_id": 1, "message": {"text": "test"}}]}'
        mock_run.return_value = mock_result
        
        updates = self.bot.get_updates()
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["update_id"], 1)
    
    @patch('subprocess.run')
    def test_get_updates_error(self, mock_run):
        """Test error handling in get_updates"""
        # Mock failed API response
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        updates = self.bot.get_updates()
        self.assertEqual(updates, [])

if __name__ == '__main__':
    unittest.main()
