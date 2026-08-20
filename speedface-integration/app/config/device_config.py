"""
app/config/device_config.py — Device configuration loaded from environment variables.

Moved here from app/config.py when app/config/ became a package in Phase 3.
All existing imports `from app.config import DeviceConfig` continue to work
via app/config/__init__.py which re-exports DeviceConfig from this module.

All sensitive settings (IP, comm key) must be provided via a .env file
or real environment variables. Nothing is hard-coded here.
"""

import os
import re
import logging
from dotenv import load_dotenv

# Load .env from the project root (two levels above this file: app/config/ -> app/ -> root)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

logger = logging.getLogger(__name__)


def _validate_ip(ip: str) -> str:
    """Basic IPv4 validation."""
    pattern = re.compile(
        r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    )
    match = pattern.match(ip.strip())
    if not match:
        raise ValueError(f"Invalid IP address format: '{ip}'")
    for octet in match.groups():
        if int(octet) > 255:
            raise ValueError(f"Invalid IP address: '{ip}' (octet out of range)")
    return ip.strip()


def _validate_port(port_str: str) -> int:
    """Validate TCP port number."""
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid port value: '{port_str}' (must be an integer)")
    if not (1 <= port <= 65535):
        raise ValueError(f"Port {port} is out of valid range (1–65535)")
    return port


def _validate_timeout(timeout_str: str) -> int:
    """Validate connection timeout in seconds."""
    try:
        timeout = int(timeout_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid timeout value: '{timeout_str}' (must be an integer)")
    if timeout < 1:
        raise ValueError(f"Timeout must be at least 1 second, got {timeout}")
    if timeout > 120:
        logger.warning("Timeout is set to %s seconds — this is unusually high.", timeout)
    return timeout


class DeviceConfig:
    """Holds validated device connection parameters."""

    def __init__(self):
        raw_ip      = os.getenv('DEVICE_IP', '').strip()
        raw_port    = os.getenv('DEVICE_PORT', '4370').strip()
        raw_key     = os.getenv('DEVICE_COMM_KEY', '0').strip()
        raw_timeout = os.getenv('DEVICE_TIMEOUT', '10').strip()

        if not raw_ip:
            raise ValueError(
                "DEVICE_IP is not set. "
                "Copy .env.example to .env and fill in the device IP address."
            )

        self.ip      = _validate_ip(raw_ip)
        self.port    = _validate_port(raw_port)
        self.timeout = _validate_timeout(raw_timeout)

        # Comm key: must be a non-negative integer (0 = no password)
        try:
            comm_key_int = int(raw_key)
        except (ValueError, TypeError):
            raise ValueError(
                f"DEVICE_COMM_KEY must be an integer (0 for no password), got '{raw_key}'"
            )
        if comm_key_int < 0:
            raise ValueError("DEVICE_COMM_KEY must be >= 0")
        self._comm_key = comm_key_int  # stored privately; never logged

    @property
    def comm_key(self) -> int:
        return self._comm_key

    def display(self) -> dict:
        """Return a safe dict for display — comm key is never included."""
        return {
            'ip':      self.ip,
            'port':    self.port,
            'timeout': self.timeout,
            'comm_key_set': self._comm_key != 0,
        }

    def __repr__(self):
        return (
            f"DeviceConfig(ip={self.ip!r}, port={self.port}, "
            f"timeout={self.timeout}s, comm_key_set={self._comm_key != 0})"
        )
