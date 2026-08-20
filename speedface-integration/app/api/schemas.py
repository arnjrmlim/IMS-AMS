"""
app/api/schemas.py — Pydantic response models for the Phase 3 REST API.

These models define what the API returns to the future Laravel application.
The Laravel system never sees ZKTeco internals, pyzk objects, or raw device
protocol details — only these clean, validated structures.

All models are read-only representations of already-synchronized data.
No model enables writing back to the SpeedFace device.
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Standard envelope ─────────────────────────────────────────────────────────

class Meta(BaseModel):
    page:     int
    per_page: int
    total:    int
    pages:    int = Field(default=0)

    def model_post_init(self, __context: Any) -> None:
        import math
        object.__setattr__(
            self, 'pages',
            math.ceil(self.total / self.per_page) if self.per_page > 0 else 0
        )


class ErrorDetail(BaseModel):
    code:    str
    message: str


class ErrorResponse(BaseModel):
    success: bool  = False
    error:   ErrorDetail


class SuccessResponse(BaseModel):
    success: bool = True
    data:    Any  = None
    meta:    Optional[Meta] = None


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:  str = 'ok'
    version: str = '3.0.0'
    service: str = 'speedface-integration'


# ── Device ────────────────────────────────────────────────────────────────────

class DeviceSchema(BaseModel):
    id:               int
    name:             Optional[str]
    ip_address:       str
    port:             int
    serial_number:    Optional[str]
    model:            Optional[str]
    firmware_version: Optional[str]
    platform:         Optional[str]
    face_version:     Optional[str]
    fp_version:       Optional[str]
    mac_address:      Optional[str]
    user_count:       Optional[int]
    attendance_count: Optional[int]
    last_connected_at: Optional[str]
    last_sync_at:     Optional[str]
    created_at:       str
    updated_at:       str


# ── Sync status ───────────────────────────────────────────────────────────────

class SyncRunSchema(BaseModel):
    id:               int
    device_id:        int
    started_at:       str
    completed_at:     Optional[str]
    status:           str
    records_read:     int
    records_inserted: int
    records_skipped:  int
    records_failed:   int
    error_message:    Optional[str]
    dry_run:          bool


class SyncStatusSchema(BaseModel):
    device_found:            bool
    device_ip:               str
    device_port:             int
    device_name:             Optional[str]         = None
    serial_number:           Optional[str]         = None
    firmware:                Optional[str]         = None
    platform:                Optional[str]         = None
    local_record_count:      int                   = 0
    last_sync_at:            Optional[str]         = None
    last_sync_status:        Optional[str]         = None
    last_record_datetime:    Optional[str]         = None
    total_sync_runs:         int                   = 0
    sync_in_progress:        bool                  = False
    last_run:                Optional[SyncRunSchema] = None


# ── Attendance ────────────────────────────────────────────────────────────────

class AttendanceRecordSchema(BaseModel):
    id:                int
    device_id:         int
    device_user_id:    str
    punch_datetime:    str
    punch_state:       int
    punch_state_label: str
    verification_type:       int
    verification_type_label: str
    raw_data:          Optional[str]
    created_at:        str

    @classmethod
    def from_db_row(cls, row) -> 'AttendanceRecordSchema':
        from app.device_models import PUNCH_STATE_MAP, PUNCH_STATE_LABELS, VERIFY_TYPE_MAP, VERIFY_TYPE_LABELS
        state_key  = PUNCH_STATE_MAP.get(row['punch_state'], f'unknown_{row["punch_state"]}')
        verify_key = VERIFY_TYPE_MAP.get(row['verification_type'], 'other')
        return cls(
            id                      = row['id'],
            device_id               = row['device_id'],
            device_user_id          = row['device_user_id'],
            punch_datetime          = row['punch_datetime'],
            punch_state             = row['punch_state'],
            punch_state_label       = PUNCH_STATE_LABELS.get(state_key, state_key),
            verification_type       = row['verification_type'],
            verification_type_label = VERIFY_TYPE_LABELS.get(verify_key, verify_key),
            raw_data                = row['raw_data'],
            created_at              = row['created_at'],
        )


# ── Device users ──────────────────────────────────────────────────────────────

class DeviceUserSchema(BaseModel):
    id:             int
    device_id:      int
    device_uid:     Optional[int]
    device_user_id: str
    name:           Optional[str]
    privilege:      int
    card_number:    Optional[str]
    created_at:     str
    updated_at:     str

    @classmethod
    def from_db_row(cls, row) -> 'DeviceUserSchema':
        return cls(
            id             = row['id'],
            device_id      = row['device_id'],
            device_uid     = row['device_uid'],
            device_user_id = row['device_user_id'],
            name           = row['name'],
            privilege      = row['privilege'],
            card_number    = row['card_number'],
            created_at     = row['created_at'],
            updated_at     = row['updated_at'],
        )


# ── Sync trigger response ─────────────────────────────────────────────────────

class SyncTriggerResponse(BaseModel):
    success:  bool
    message:  str
    job_id:   Optional[str] = None


# ── Employee mapping ──────────────────────────────────────────────────────────

class MappingSchema(BaseModel):
    id:             int
    device_id:      int
    device_user_id: str
    employee_id:    Optional[str]
    mapping_status: str
    notes:          Optional[str]
    created_at:     str
    updated_at:     str
