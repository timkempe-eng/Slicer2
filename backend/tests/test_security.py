"""Security-behavior tests: no job enumeration, print gated off, safe filenames."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app import config
from app.main import _safe_filename, app

client = TestClient(app)


def test_no_global_job_list_endpoint():
    # The enumeration endpoint must not exist (would expose all jobs/filenames).
    assert client.get("/api/jobs").status_code == 404


def test_health_does_not_leak_internals():
    body = client.get("/api/health").json()
    assert body == {"ok": True}  # no slicer_bin / paths


def test_print_disabled_by_default():
    assert config.ENABLE_PRINT is False
    r = client.post("/api/jobs/whatever/print", json={"transport": "lan", "host": "10.0.0.1"})
    assert r.status_code == 404  # gated off, no SSRF


def test_docs_disabled_in_default_config():
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


def test_filename_sanitization_strips_markup():
    assert _safe_filename("<img src=x onerror=alert(1)>.stl") == "_img src_x onerror_alert_1_.stl"
    assert "<" not in _safe_filename("<script>.stl") and ">" not in _safe_filename("<script>.stl")
    assert _safe_filename("../../etc/passwd") == "passwd"
    assert _safe_filename(None) == "model"
    assert _safe_filename("   ") == "model"


def test_upload_still_works_and_rejects_bad_type():
    # Rate limiting is a no-op without Redis (dev), so a normal upload proceeds.
    r = client.post("/api/slice", files={"file": ("m.gif", io.BytesIO(b"x"), "image/gif")})
    assert r.status_code == 400 and "Unsupported file type" in r.json()["detail"]
