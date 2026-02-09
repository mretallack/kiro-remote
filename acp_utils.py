"""
ACP detection and utilities.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def supports_acp() -> bool:
    """Check if kiro-cli supports ACP."""
    try:
        result = subprocess.run(
            ["kiro-cli", "acp", "--help"],
            capture_output=True,
            timeout=5
        )
        supported = result.returncode == 0
        logger.info(f"ACP support: {supported}")
        return supported
    except Exception as e:
        logger.error(f"Error checking ACP support: {e}")
        return False
