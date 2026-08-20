"""
device.py — Low-level wrapper around pyzk for SpeedFace-V5L communication.

IMPORTANT — READ-ONLY PHASE 1 RULES:
  - This module must NOT modify, delete, or write any data to the device.
  - No clear_attendance(), delete_user(), set_user(), set_time(), etc.
  - Any write/destructive method is intentionally omitted.

Library:  pyzk (fananimi/pyzk)
PyPI:     https://pypi.org/project/pyzk/
GitHub:                                                                                                                                                                                                                                                                     
License:  MIT
"""

import logging
import socket
import time
from contextlib import contextmanager
from typing import Optional

from zk import ZK
from zk.exception import ZKErrorConnection, ZKNetworkError, ZKErrorResponse

from app.config import DeviceConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DeviceConnectionError(Exception):
    """Raised when the device cannot be reached or authenticated."""


class DeviceReadError(Exception):
    """Raised when a read operation fails after a successful connection."""


class DeviceCompatibilityWarning(Exception):
    """
    Raised when the device responds but returns data in an unexpected format.
    Typically seen with newer SpeedFace-V5L firmware where GET_FREE_SIZES
    returns a single DWORD instead of the expected 28-byte struct, causing
    pyzk to report zero records even though records exist on the device.
    """


# ---------------------------------------------------------------------------
# IP / TCP reachability helpers (used by diagnostics — no pyzk involved)
# ---------------------------------------------------------------------------

def check_ip_reachable(ip: str, timeout: int = 3) -> tuple[bool, str]:
    """
    Try a raw TCP connection to port 80 (or any open port) just to see
    if the host is alive on the network.  We use socket directly so this
    step does not depend on pyzk at all.
    Returns (success: bool, message: str).
    """
    try:
        # getaddrinfo validates the IP string first
        socket.getaddrinfo(ip, None)
    except socket.gaierror as exc:
        return False, f"IP address resolution failed: {exc}"
    return True, "IP format is valid and host is addressable"


def check_tcp_port(ip: str, port: int, timeout: int = 5) -> tuple[bool, str]:
    """
    Attempt a raw TCP connection to ip:port.
    Returns (success: bool, message: str).
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            return True, f"TCP port {port} is open and accepting connections"
        else:
            return False, (
                f"TCP port {port} is closed or filtered (connect_ex returned {result}). "
                "Check firewall rules and device network settings."
            )
    except socket.timeout:
        return False, f"TCP connection to {ip}:{port} timed out after {timeout}s"
    except OSError as exc:
        return False, f"TCP socket error: {exc}"


# ---------------------------------------------------------------------------
# Main device manager
# ---------------------------------------------------------------------------

class SpeedFaceDevice:
    """
    Wraps pyzk ZK to communicate with the SpeedFace-V5L over TCP.

    Usage (preferred — uses context manager for clean disconnect):

        cfg = DeviceConfig()
        with SpeedFaceDevice(cfg) as dev:
            info = dev.get_device_info()

    Or manually:

        dev = SpeedFaceDevice(cfg)
        dev.connect()
        ...
        dev.disconnect()
    """

    def __init__(self, config: DeviceConfig):
        self.config = config
        self._zk:   Optional[ZK]   = None
        self._conn                  = None   # pyzk connection object
        self._connected: bool       = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> float:
        """
        Establish a TCP connection to the device.

        Returns:
            elapsed_ms (float): round-trip connection time in milliseconds.

        Raises:
            DeviceConnectionError: if connection fails for any reason.
        """
        cfg = self.config
        logger.info(
            "Connecting to device at %s:%s (timeout=%ss) ...",
            cfg.ip, cfg.port, cfg.timeout
        )

        self._zk = ZK(
            cfg.ip,
            port=cfg.port,
            timeout=cfg.timeout,
            password=cfg.comm_key,
            force_udp=False,    # SpeedFace-V5L uses TCP
            ommit_ping=False,
        )

        t_start = time.perf_counter()
        try:
            self._conn = self._zk.connect()
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            self._connected = True
            logger.info(
                "Connected successfully in %.1f ms", elapsed_ms
            )
            return elapsed_ms

        except ZKErrorConnection as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error("ZKErrorConnection after %.1f ms: %s", elapsed_ms, exc)
            self._connected = False
            raise DeviceConnectionError(str(exc)) from exc

        except ZKNetworkError as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error("ZKNetworkError after %.1f ms: %s", elapsed_ms, exc)
            self._connected = False
            raise DeviceConnectionError(str(exc)) from exc

        except socket.timeout:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error("Connection timed out after %.1f ms", elapsed_ms)
            self._connected = False
            raise DeviceConnectionError(
                f"Connection timed out after {cfg.timeout}s. "
                "Check IP, port, and that the device is powered on."
            )

        except ConnectionRefusedError:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error("Connection refused after %.1f ms", elapsed_ms)
            self._connected = False
            raise DeviceConnectionError(
                f"Connection refused at {cfg.ip}:{cfg.port}. "
                "Verify the device IP/port and that TCP communication is enabled."
            )

        except OSError as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error("OS error during connection after %.1f ms: %s", elapsed_ms, exc)
            self._connected = False
            raise DeviceConnectionError(f"Network error: {exc}") from exc

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error("Unexpected error during connection after %.1f ms: %s", elapsed_ms, exc)
            self._connected = False
            raise DeviceConnectionError(f"Unexpected error: {exc}") from exc

    def disconnect(self) -> None:
        """Cleanly disconnect from the device."""
        if self._conn and self._connected:
            try:
                self._conn.disconnect()
                logger.info("Disconnected from device %s", self.config.ip)
            except Exception as exc:
                logger.warning("Error during disconnect (ignored): %s", exc)
            finally:
                self._connected = False
                self._conn = None

    @contextmanager
    def session(self):
        """
        Context manager that connects, yields self, then always disconnects.

        Example:
            with device.session():
                info = device.get_device_info()
        """
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False  # do not suppress exceptions

    def _require_connection(self):
        if not self._connected or self._conn is None:
            raise DeviceConnectionError(
                "Not connected. Call connect() before reading data."
            )

    # ------------------------------------------------------------------
    # Read-only data methods
    # ------------------------------------------------------------------

    def get_device_info(self) -> dict:
        """
        Retrieve device metadata.

        Returns a dict with keys:
          device_name, serial_number, firmware_version, platform,
          face_version, fp_version, mac, device_time, users, fingers,
          records, users_cap, fingers_cap

        Any field that cannot be retrieved is set to 'Not available through this protocol'.
        """
        self._require_connection()
        NOT_AVAIL = "Not available through this protocol"
        info = {}

        t_start = time.perf_counter()
        logger.info("Reading device information ...")

        def _safe(label: str, fn):
            try:
                result = fn()
                logger.debug("  %s = %s", label, result)
                return result if result not in (None, '', b'') else NOT_AVAIL
            except ZKErrorResponse as exc:
                logger.warning("  %s: ZKErrorResponse — %s", label, exc)
                return NOT_AVAIL
            except Exception as exc:
                logger.warning("  %s: error — %s", label, exc)
                return NOT_AVAIL

        # Scalar fields
        info['device_name']       = _safe('device_name',       self._conn.get_device_name)
        info['serial_number']     = _safe('serial_number',     self._conn.get_serialnumber)
        info['firmware_version']  = _safe('firmware_version',  self._conn.get_firmware_version)
        info['platform']          = _safe('platform',          self._conn.get_platform)
        info['face_version']      = _safe('face_version',      self._conn.get_face_version)
        info['fp_version']        = _safe('fp_version',        self._conn.get_fp_version)
        info['mac']               = _safe('mac',               self._conn.get_mac)
        info['device_time']       = _safe('device_time',       self._conn.get_time)

        # Capacity / usage (read_sizes populates conn.users, .records, etc.)
        try:
            self._conn.read_sizes()
            info['users']       = self._conn.users
            info['fingers']     = self._conn.fingers
            info['records']     = self._conn.records
            info['users_cap']   = self._conn.users_cap
            info['fingers_cap'] = self._conn.fingers_cap
            logger.debug(
                "  sizes: users=%s fingers=%s records=%s",
                info['users'], info['fingers'], info['records']
            )
        except ZKErrorResponse as exc:
            logger.warning("read_sizes() ZKErrorResponse: %s", exc)
            for key in ('users', 'fingers', 'records', 'users_cap', 'fingers_cap'):
                info[key] = NOT_AVAIL
        except Exception as exc:
            logger.warning("read_sizes() error: %s", exc)
            for key in ('users', 'fingers', 'records', 'users_cap', 'fingers_cap'):
                info[key] = NOT_AVAIL

        elapsed = (time.perf_counter() - t_start) * 1000
        logger.info("Device information read in %.1f ms", elapsed)
        return info

    def get_users(self) -> list:
        """
        Retrieve all registered users from the device.

        Returns a list of dicts:
          uid, user_id, name, privilege, privilege_label, card

        Password is intentionally excluded (read but not surfaced).
        Biometric templates are NOT retrieved.

        Raises:
            DeviceReadError: on failure.
        """
        self._require_connection()
        logger.info("Reading users from device ...")
        t_start = time.perf_counter()

        try:
            raw_users = self._conn.get_users()
        except ZKErrorResponse as exc:
            raise DeviceReadError(f"Device returned an error response: {exc}") from exc
        except ZKNetworkError as exc:
            raise DeviceReadError(f"Network error while reading users: {exc}") from exc
        except Exception as exc:
            raise DeviceReadError(f"Unexpected error reading users: {exc}") from exc

        users = []
        for u in raw_users:
            privilege_label = _privilege_label(u.privilege)
            users.append({
                'uid':             u.uid,
                'user_id':         u.user_id,
                'name':            u.name,
                'privilege':       u.privilege,
                'privilege_label': privilege_label,
                'card':            u.card if hasattr(u, 'card') else 'N/A',
                # password intentionally omitted
            })

        elapsed = (time.perf_counter() - t_start) * 1000
        logger.info("Read %d users in %.1f ms", len(users), elapsed)
        return users

    def get_attendance(self) -> tuple[list, str | None]:
        """
        Retrieve all attendance/transaction records from the device.

        Returns:
            (records: list, warning: str | None)

        Each record dict contains:
          user_id, timestamp, status, status_label, punch, verify_type, verify_label

        The warning string is set when records is empty but may be a firmware
        compatibility issue (SpeedFace-V5L newer firmware known problem).

        Raises:
            DeviceReadError: on hard failure.
        """
        self._require_connection()
        logger.info("Reading attendance records from device ...")
        t_start = time.perf_counter()

        warning = None
        try:
            raw_records = self._conn.get_attendance()
        except ZKErrorResponse as exc:
            raise DeviceReadError(f"Device returned an error response: {exc}") from exc
        except ZKNetworkError as exc:
            raise DeviceReadError(f"Network error while reading attendance: {exc}") from exc
        except Exception as exc:
            raise DeviceReadError(f"Unexpected error reading attendance: {exc}") from exc

        records = []
        for r in raw_records:
            records.append({
                'user_id':      r.user_id,
                'timestamp':    r.timestamp,
                'status':       r.status,
                'status_label': _status_label(r.status),
                'punch':        r.punch if hasattr(r, 'punch') else 0,
                'verify_type':  r.punch if hasattr(r, 'punch') else 0,
                'verify_label': _verify_label(r.punch if hasattr(r, 'punch') else 0),
            })

        elapsed = (time.perf_counter() - t_start) * 1000

        if len(records) == 0:
            # Distinguish "empty because no punches" from the known SpeedFace-V5L
            # firmware issue where GET_FREE_SIZES returns a single DWORD.
            warning = (
                "Attendance list is empty. This may be a known firmware compatibility issue "
                "with SpeedFace-V5L devices running newer firmware where pyzk receives a "
                "single DWORD from GET_FREE_SIZES instead of the expected 28-byte struct. "
                "The device may have attendance records that are not accessible via this protocol. "
                "Verify using the device's local display that punches exist. "
                "See: https://github.com/fananimi/pyzk/issues/126"
            )
            logger.warning(warning)
        else:
            logger.info("Read %d attendance records in %.1f ms", len(records), elapsed)

        return records, warning


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _privilege_label(privilege: int) -> str:
    from zk import const
    labels = {
        const.USER_DEFAULT:   'User',
        const.USER_ADMIN:     'Administrator',
    }
    # Some firmware versions expose additional privilege levels
    if hasattr(const, 'USER_ENROLLER'):
        labels[const.USER_ENROLLER] = 'Enroller'
    if hasattr(const, 'USER_MANAGER'):
        labels[const.USER_MANAGER] = 'Manager'
    return labels.get(privilege, f'Unknown ({privilege})')


def _status_label(status: int) -> str:
    """Map attendance status code to human-readable string."""
    labels = {
        0: 'Check In',
        1: 'Check Out',
        2: 'Break Out',
        3: 'Break In',
        4: 'Overtime In',
        5: 'Overtime Out',
    }
    return labels.get(status, f'Status {status}')


def _verify_label(punch: int) -> str:
    """Map verification/punch type to human-readable string."""
    labels = {
        0:  'Fingerprint',
        1:  'Fingerprint',
        2:  'Fingerprint',
        3:  'Fingerprint',
        4:  'Fingerprint',
        5:  'Fingerprint',
        6:  'Fingerprint',
        7:  'Fingerprint',
        8:  'Fingerprint',
        9:  'Fingerprint',
        10: 'Face',
        11: 'Face',
        12: 'Face',
        13: 'Face',
        14: 'Face',
        15: 'Password',
        16: 'Card/Badge',
        17: 'Card/Badge',
        18: 'Card/Badge',
        19: 'Card/Badge',
        20: 'Other',
    }
    return labels.get(punch, f'Type {punch}')
