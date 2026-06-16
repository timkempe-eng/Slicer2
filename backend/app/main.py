"""Slicer2 FastAPI application: upload -> slice -> download / print."""
from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, jobs
from .models import JobView, PrinterModel, PrintRequest, SliceOptions
from .printer import CloudPrinterClient, LanPrinterClient, PrinterError

app = FastAPI(title="Slicer2", version="0.1.0", description="Better slicing as a service.")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "slicer_bin": config.SLICER_BIN}


@app.post("/api/slice", response_model=JobView)
async def create_slice(
    background: BackgroundTasks,
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

    # Stream the upload to disk, enforcing the size cap as we go.
    job_dir = config.UPLOAD_DIR / "pending"
    job_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "model").name
    dest = job_dir / safe_name
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > config.MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large.")
            out.write(chunk)

    job = jobs.create_job(filename=safe_name, input_path=dest, options=options)
    # Move the upload under the job id so concurrent uploads don't collide.
    final = config.UPLOAD_DIR / job.id / safe_name
    final.parent.mkdir(parents=True, exist_ok=True)
    dest.replace(final)
    job.input_path = str(final)

    background.add_task(jobs.run_slice, job.id)
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
def download_output(job_id: str) -> FileResponse:
    job = jobs.get_job(job_id)
    if job is None or not job.output_path:
        raise HTTPException(status_code=404, detail="No sliced output for this job.")
    name = f"{Path(job.filename).stem}.gcode.3mf"
    return FileResponse(job.output_path, filename=name, media_type="application/octet-stream")


@app.post("/api/jobs/{job_id}/print", response_model=JobView)
def print_job(job_id: str, req: PrintRequest) -> JobView:
    job = jobs.get_job(job_id)
    if job is None or not job.output_path:
        raise HTTPException(status_code=404, detail="No sliced output for this job.")

    if req.transport == "lan":
        client = LanPrinterClient(req.host or "", req.serial or "", req.access_code or "")
    elif req.transport == "cloud":
        # Phase 2: requires a logged-in cloud session. Surfaces a clear 501.
        raise HTTPException(
            status_code=501,
            detail="Bambu Cloud printing is not implemented yet (Phase 2). "
            "Use transport='lan' for now.",
        )
    else:
        raise HTTPException(status_code=400, detail="transport must be 'lan' or 'cloud'.")

    try:
        client.print_file(Path(job.output_path), job_name=job.filename)
    except PrinterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()

    return job.to_view()


# Serve the mobile web UI at the root. Mounted last so /api routes win.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
