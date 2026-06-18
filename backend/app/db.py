"""SQLAlchemy engine, session factory, and declarative Base.

The URL comes from ``config.DATABASE_URL`` — a managed Postgres in production, a
local sqlite file in dev/test. ``ensure_schema()`` creates tables if they are
missing (idempotent, ``checkfirst=True``), so dev/test work without running
Alembic; production still uses Alembic migrations, with which ``create_all``
coexists harmlessly.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

# sqlite needs check_same_thread off so the API and background slicing (which
# may run in a different thread) can share the connection pool.
_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(config.DATABASE_URL, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


_schema_ready = False


def ensure_schema() -> None:
    """Create tables if absent. Safe to call repeatedly and alongside Alembic."""
    global _schema_ready
    if _schema_ready:
        return
    # Import models so they register on Base.metadata before create_all.
    from . import db_models  # noqa: F401

    Base.metadata.create_all(engine, checkfirst=True)
    _schema_ready = True
