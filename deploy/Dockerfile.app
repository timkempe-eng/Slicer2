# Slicer2 API image: the FastAPI app only. Slicing now runs in a separate RQ
# worker (built from docker/slicer.Dockerfile), so this image stays small and
# does NOT carry the slicer binary — it just accepts uploads, enqueues jobs to
# Redis, persists to Postgres, and streams results from Spaces.
FROM ubuntu:24.04
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SLICER2_DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/venv/bin:${PATH}"
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic

EXPOSE 8000
# Apply DB migrations, then serve. (Migrations are idempotent.)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
