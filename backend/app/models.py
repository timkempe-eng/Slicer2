"""Domain models and API schemas."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    SLICING = "slicing"
    DONE = "done"
    FAILED = "failed"


class PrinterModel(str, Enum):
    A1 = "a1"
    A1_MINI = "a1_mini"


class SliceOptions(BaseModel):
    """User-facing slicing parameters. Mapped onto Bambu Studio presets."""

    printer: PrinterModel = PrinterModel.A1
    # Common, friendly knobs. Extend as profiles grow.
    layer_height_mm: float = Field(0.20, ge=0.08, le=0.32)
    infill_density: int = Field(15, ge=0, le=100, description="percent")
    filament: str = Field("pla", description="Filament preset key, e.g. 'pla', 'petg'.")
    supports: bool = False


class SliceResult(BaseModel):
    estimated_print_seconds: Optional[int] = None
    filament_grams: Optional[float] = None
    filament_meters: Optional[float] = None


class JobView(BaseModel):
    """Serializable view of a Job returned by the API."""

    id: str
    status: JobStatus
    filename: str
    options: SliceOptions
    created_at: float
    updated_at: float
    error: Optional[str] = None
    result: Optional[SliceResult] = None
    has_output: bool = False


@dataclass
class Job:
    id: str
    filename: str
    input_path: str
    options: SliceOptions
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    output_path: Optional[str] = None
    error: Optional[str] = None
    result: Optional[SliceResult] = None

    def touch(self, status: Optional[JobStatus] = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = time.time()

    def to_view(self) -> JobView:
        return JobView(
            id=self.id,
            status=self.status,
            filename=self.filename,
            options=self.options,
            created_at=self.created_at,
            updated_at=self.updated_at,
            error=self.error,
            result=self.result,
            has_output=bool(self.output_path),
        )


class PrintRequest(BaseModel):
    """Request body for pushing a finished job to a printer."""

    transport: str = Field("lan", description="'lan' or 'cloud'.")
    # LAN
    host: Optional[str] = None
    serial: Optional[str] = None
    access_code: Optional[str] = None
    # Cloud
    region: str = "us"
