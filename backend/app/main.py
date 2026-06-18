"""Slicer2 FastAPI application: upload -> slice -> download / print."""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config, jobs, storage
from .models import JobView, PrinterModel, PrintRequest, SliceOptions
from .printer import LanPrinterClient, PrinterError

app = FastAPI(title="Slicer2", version="0.1.0", description="Better slicing as a service.")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "slicer_bin": config.SLICER_BIN}


@app.post("/api/slice", response_model=JobView)
async def create_slice(
    file: UploadFile = File(...),
    printer: PrinterModel = Form(PrinterModel.A1),
    layer_height_mm: float = Form(0.20),
    infill_density: int = Form(15),
    filament: str = Form("pla"),
    supports: bool = Form(False),
) -> JobView:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: "
            f"{', '.join(sorted(config.ALLOWED_EXTENSIONS))}",
        )

    options = SliceOptions(
        printer=printer,
        layer_height_mm=layer_height_mm,
        infill_density=infill_density,
        filament=filament,
        supports=supports,
    )

    # Stream the upload to a temp file, enforcing the size cap, then hand it to
    # object storage (Spaces in prod, local disk in dev). The object key is
    # independent of the job id, so concurrent uploads never collide.
    safe_name = Path(file.filename or "model").name
    input_key = f"uploads/{uuid.uuid4().hex}/{safe_name}"
    size = 0
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > config.MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File too large.")
            tmp.write(chunk)
        tmp.flush()
        storage.upload_file(input_key, Path(tmp.name))

    job = jobs.create_job(filename=safe_name, input_key=input_key, options=options)
    jobs.enqueue_slice(job.id)
    return job.to_view()


@app.get("/api/jobs", response_model=list[JobView])
def list_all_jobs() -> list[JobView]:
    return [j.to_view() for j in jobs.list_jobs()]


@app.get("/api/jobs/{job_id}", response_model=JobView)
def get_one_job(job_id: str) -> JobView:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_view()


@app.get("/api/jobs/{job_id}/download")
def download_output(job_id: str):
    job = jobs.get_job(job_id)
    if job is None or not job.output_path:
        raise HTTPException(status_code=404, detail="No sliced output for this job.")
    name = f"{Path(job.filename).stem}.gcode.3mf"
    # Remote storage: redirect to a short-lived presigned URL (bytes never touch
    # the app). Local storage: stream the file directly.
    url = storage.presigned_get_url(job.output_path, filename=name)
    if url:
        return RedirectResponse(url)
    return FileResponse(
        storage.local_path(job.output_path), filename=name, media_type="application/octet-stream"
    )


@app.post("/api/jobs/{job_id}/print", response_model=JobView)
def print_job(job_id: str, req: PrintRequest) -> JobView:
    """Push a finished job to a printer over the local network.

    Auto-push is outside the MVP (a hosted service can't reach a printer behind
    a home NAT, and Bambu's cloud blocks third-party print-start). This LAN path
    works only when Slicer2 runs on the same network as the printer — the future
    on-network "local bridge". Cloud push is intentionally unimplemented.
    """
    job = jobs.get_job(job_id)
    if job is None or not job.output_path:
        raise HTTPException(status_code=404, detail="No sliced output for this job.")

    if req.transport == "lan":
        client = LanPrinterClient(req.host or "", req.serial or "", req.access_code or "")
    elif req.transport == "cloud":
        raise HTTPException(
            status_code=501,
            detail="Bambu Cloud printing is not supported: Bambu's Authorization "
            "Control System blocks third-party cloud print-start. Download the "
            ".gcode.3mf and print it from the printer's screen via microSD.",
        )
    else:
        raise HTTPException(status_code=400, detail="transport must be 'lan' or 'cloud'.")

    with tempfile.TemporaryDirectory() as tmp:
        local_out = storage.download_to(job.output_path, Path(tmp) / "job.gcode.3mf")
        try:
            client.print_file(local_out, job_name=job.filename)
        except PrinterError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        finally:
            client.close()

    return job.to_view()


# Serve the mobile web UI at the root. Mounted last so /api routes win.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
