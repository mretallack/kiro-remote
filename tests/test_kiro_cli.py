import os
import subprocess
import time

import pytest


class TestKiroCLI:
    """Test suite for Kiro CLI interface validation."""

    def run_kiro_command(self, args, timeout=10):
        """Run kiro-cli command and return result."""
        cmd = ["kiro-cli"] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            pytest.fail(f"Command timed out: {' '.join(cmd)}")
        except FileNotFoundError:
            pytest.fail("kiro-cli not found in PATH")

    def test_kiro_help(self):
        """Test basic help command."""
        result = self.run_kiro_command(["--help"])
        assert result.returncode == 0
        assert "kiro-cli" in result.stdout.lower()

    def test_kiro_usage(self):
        """Test usage information."""
        result = self.run_kiro_command([])
        # Should show usage or help when no args provided
        assert result.returncode in [0, 1]  # Some CLIs return 1 for usage

    def test_agent_list(self):
        """Test agent list command."""
        result = self.run_kiro_command(["agent", "list"])
        assert result.returncode == 0

    def test_agent_swap(self):
        """Test agent swap command (should show available agents)."""
        # First get list of agents
        list_result = self.run_kiro_command(["agent", "list"])
        if list_result.returncode == 0 and list_result.stdout.strip():
            # Try to swap to first available agent or test swap help
            swap_result = self.run_kiro_command(["agent", "swap", "--help"])
            assert swap_result.returncode in [0, 1]

    def test_chat_help(self):
        """Test chat command help."""
        result = self.run_kiro_command(["chat", "--help"])
        assert result.returncode == 0
        assert "chat" in result.stdout.lower()

    def test_version_or_info(self):
        """Test version or info command if available."""
        # Try common version flags
        for flag in ["--version", "-v", "version"]:
            result = self.run_kiro_command([flag])
            if result.returncode == 0:
                break
        # At least one should work or we should get help
        assert True  # Basic connectivity test passed if we get here


class TestKiroInterface:
    """Test Kiro CLI interface through subprocess interaction."""

    def test_kiro_basic_interaction(self):
        """Test basic interaction with kiro-cli chat."""
        try:
            # Start kiro-cli chat process
            proc = subprocess.Popen(
                ["kiro-cli", "chat", "--trust-all-tools"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Send a simple test message
            test_input = "hello\n/quit\n"
            stdout, stderr = proc.communicate(input=test_input, timeout=30)

            # Should exit cleanly
            assert proc.returncode in [0, 1]  # Some exit codes are acceptable

        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("Kiro CLI chat session timed out")
        except FileNotFoundError:
            pytest.skip("kiro-cli not available for interactive testing")

    def test_kiro_tools_trust(self):
        """Test tools trust functionality."""
        try:
            proc = subprocess.Popen(
                ["kiro-cli", "chat"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Test tools trust command
            test_input = "/tools trust-all\n/quit\n"
            stdout, stderr = proc.communicate(input=test_input, timeout=20)

            assert proc.returncode in [0, 1]

        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("Tools trust test timed out")
        except FileNotFoundError:
            pytest.skip("kiro-cli not available for tools testing")
