"""
app/device_models.py — Normalized data models for Phase 3.

These dataclasses form the application-independent layer between:
  - Raw device data (pyzk dicts)
  - The REST API / future Laravel system

The future Laravel application never needs to know about:
  - ZKTeco protocol details
  - Port 4370
  - Device-specific punch codes
  - pyzk library internals

It only sees these normalized structures.

READ-ONLY GUARANTEE
-------------------
These models represent data READ FROM the device.
They are never used to write back to the device.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Punch state mapping ───────────────────────────────────────────────────────

PUNCH_STATE_MAP = {
    0: 'check_in',
    1: 'check_out',
    2: 'break_out',
    3: 'break_in',
    4: 'overtime_in',
    5: 'overtime_out',
}

PUNCH_STATE_LABELS = {
    'check_in':     'Check In',
    'check_out':    'Check Out',
    'break_out':    'Break Out',
    'break_in':     'Break In',
    'overtime_in':  'Overtime In',
    'overtime_out': 'Overtime Out',
}

# ── Verification type mapping ─────────────────────────────────────────────────

VERIFY_TYPE_MAP = {
    **{i: 'fingerprint' for i in range(0, 10)},
    **{i: 'face'        for i in range(10, 15)},
    15: 'password',
    **{i: 'card'        for i in range(16, 20)},
    20: 'other',
}

VERIFY_TYPE_LABELS = {
    'fingerprint': 'Fingerprint',
    'face':        'Face',
    'password':    'Password',
    'card':        'Card/Badge',
    'other':       'Other',
}


def normalize_punch_state(code: int) -> str:
    return PUNCH_STATE_MAP.get(code, f'unknown_{code}')


def normalize_verify_type(punch: int) -> str:
    return VERIFY_TYPE_MAP.get(punch, 'other')


# ── Normalized models ─────────────────────────────────────────────────────────

@dataclass
class NormalizedAttendanceRecord:
    """
    Application-independent attendance record.

    device_id       : local DB device row id
    device_user_id  : user identifier from the SpeedFace (string)
    punch_datetime  : normalized datetime string 'YYYY-MM-DD HH:MM:SS'
    punch_state     : normalized string e.g. 'check_in', 'check_out'
    punch_state_raw : original integer code from device
    verification_type      : normalized string e.g. 'face', 'fingerprint'
    verification_type_raw  : original integer code from device
    raw_data        : original device record serialized as JSON string
    """
    device_id:              int
    device_user_id:         str
    punch_datetime:         str
    punch_state:            str
    punch_state_raw:        int
    verification_type:      str
    verification_type_raw:  int
    raw_data:               str = ''

    @classmethod
    def from_device_dict(cls, device_id: int, record: dict) -> 'NormalizedAttendanceRecord':
        """
        Build from a dict returned by SpeedFaceDevice.get_attendance().

        record keys: user_id, timestamp, status, punch / verify_type
        """
        ts = record.get('timestamp')
        if isinstance(ts, datetime):
            punch_dt = ts.strftime('%Y-%m-%d %H:%M:%S')
        else:
            punch_dt = str(ts) if ts else '1970-01-01 00:00:00'

        state_raw  = int(record.get('status', 0))
        verify_raw = int(record.get('verify_type', record.get('punch', 0)))
        user_id    = str(record.get('user_id', ''))

        import json
        raw = json.dumps({
            'user_id':     user_id,
            'datetime':    punch_dt,
            'state_code':  state_raw,
            'verify_code': verify_raw,
        }, ensure_ascii=False)

        return cls(
            device_id             = device_id,
            device_user_id        = user_id,
            punch_datetime        = punch_dt,
            punch_state           = normalize_punch_state(state_raw),
            punch_state_raw       = state_raw,
            verification_type     = normalize_verify_type(verify_raw),
            verification_type_raw = verify_raw,
            raw_data              = raw,
        )


@dataclass
class NormalizedUser:
    """
    Application-independent user record from the SpeedFace device.
    Biometric templates are never included.
    """
    device_id:       int
    device_uid:      int
    device_user_id:  str
    name:            str
    privilege:       int
    privilege_label: str
    card_number:     Optional[str] = None

    @classmethod
    def from_device_dict(cls, device_id: int, user: dict) -> 'NormalizedUser':
        card = str(user['card']) if user.get('card') not in (0, None, 'N/A', '') else None
        return cls(
            device_id       = device_id,
            device_uid      = int(user.get('uid', 0)),
            device_user_id  = str(user.get('user_id', '')),
            name            = str(user.get('name', '')),
            privilege       = int(user.get('privilege', 0)),
            privilege_label = str(user.get('privilege_label', 'User')),
            card_number     = card,
        )


@dataclass
class NormalizedDeviceInfo:
    """
    Application-independent device metadata snapshot.
    """
    device_id:        int
    name:             Optional[str]
    serial_number:    Optional[str]
    firmware_version: Optional[str]
    platform:         Optional[str]
    face_version:     Optional[str]
    fp_version:       Optional[str]
    mac_address:      Optional[str]
    device_time:      Optional[str]
    user_count:       Optional[int]
    attendance_count: Optional[int]
    ip_address:       str
    port:             int

    @classmethod
    def from_device_dict(
        cls, device_id: int, ip: str, port: int, info: dict
    ) -> 'NormalizedDeviceInfo':
        NOT_AVAIL = 'Not available through this protocol'

        def _str_or_none(v):
            return str(v) if v and v != NOT_AVAIL else None

        def _int_or_none(v):
            return int(v) if isinstance(v, int) else None

        dt = info.get('device_time')
        if isinstance(dt, datetime):
            dt = dt.strftime('%Y-%m-%d %H:%M:%S')
        elif dt == NOT_AVAIL:
            dt = None

        return cls(
            device_id        = device_id,
            name             = _str_or_none(info.get('device_name')),
            serial_number    = _str_or_none(info.get('serial_number')),
            firmware_version = _str_or_none(info.get('firmware_version')),
            platform         = _str_or_none(info.get('platform')),
            face_version     = _str_or_none(info.get('face_version')),
            fp_version       = _str_or_none(info.get('fp_version')),
            mac_address      = _str_or_none(info.get('mac')),
            device_time      = dt,
            user_count       = _int_or_none(info.get('users')),
            attendance_count = _int_or_none(info.get('records')),
            ip_address       = ip,
            port             = port,
        )
