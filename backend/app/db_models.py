"""Persistent job row. Mirrors the ``Job`` dataclass in ``models.py``.

``options`` and ``result`` are stored as JSON (JSONB on Postgres) so adding a
slicing knob never needs a migration. ``input_key`` / ``output_key`` are object
keys in Spaces (or relative paths under DATA_DIR when storage is local).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Enum as SAEnum, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import JobStatus

# JSONB on Postgres, plain JSON elsewhere (e.g. sqlite in dev/test).
_JSON = JSON().with_variant(JSONB, "postgresql")


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False, length=16), default=JobStatus.QUEUED
    )
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)
    options: Mapped[dict] = mapped_column(_JSON)
    result: Mapped[Optional[dict]] = mapped_column(_JSON, nullable=True)
    input_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    output_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
