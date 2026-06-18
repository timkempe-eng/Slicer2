# Slicer2 worker image: headless OrcaSlicer CLI + the FastAPI app code, so an
# RQ worker can pull jobs off Redis and run real slices.
#
# Slicer2 standardises on OrcaSlicer (a Bambu Studio fork with the same CLI that
# *bundles* the A1 profiles), extracted from its Linux AppImage and run under
# xvfb (the CLI still initialises a GL/Qt context on some builds). Profiles are
# flattened into backend/profiles/a1/ at build time so the binary version and
# the profiles always match.
#
# This same image runs both the slicing worker (`rq worker slicing`) and, if you
# want a single image, the API (`uvicorn app.main:app`).
FROM ubuntu:24.04

# Pin a known-good OrcaSlicer release for reproducible slices. Override at build
# time; verify the asset name resolves (it changes per release):
#   docker build --build-arg ORCA_APPIMAGE_URL=https://github.com/SoftFever/OrcaSlicer/releases/download/<tag>/<asset>.AppImage ...
ARG ORCA_TAG=V2.2.0
ARG ORCA_APPIMAGE_URL=https://github.com/SoftFever/OrcaSlicer/releases/download/${ORCA_TAG}/OrcaSlicer_Linux_AppImage_Ubuntu2404_${ORCA_TAG}.AppImage

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SLICER2_SLICER_BIN=orca-slicer SLICER2_DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xvfb \
        python3 python3-pip python3-venv \
        libgl1 libgtk-3-0 libwebkit2gtk-4.1-0 libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 libsoup-3.0-0 libosmesa6 \
        fonts-dejavu-core libfuse2 \
    && rm -rf /var/lib/apt/lists/*

# ---- slicer ----
WORKDIR /opt/orca
RUN curl -fSL "${ORCA_APPIMAGE_URL}" -o orca.AppImage \
    && chmod +x orca.AppImage \
    && ./orca.AppImage --appimage-extract >/dev/null \
    && rm orca.AppImage
# Wrapper so callers can just run `orca-slicer ...` (matches SLICER2_SLICER_BIN).
RUN printf '#!/bin/sh\nexec xvfb-run -a /opt/orca/squashfs-root/AppRun "$@"\n' \
        > /usr/local/bin/orca-slicer \
    && chmod +x /usr/local/bin/orca-slicer

# ---- python deps ----
WORKDIR /app
COPY backend/requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/venv/bin:${PATH}"

# ---- app + profiles ----
COPY backend/app ./app
COPY backend/profiles ./profiles
COPY scripts ./scripts
COPY backend/tests/_stl.py ./tests/_stl.py
# Bake the A1 profiles by flattening OrcaSlicer's bundled presets (mirrors
# scripts/setup_slicer.sh step 3) so a real slice works out of the box.
RUN python3 scripts/flatten_profiles.py \
        --resources /opt/orca/squashfs-root/resources/profiles \
        --printer a1_mini --out ./profiles/a1 \
    && ls -1 ./profiles/a1

# Default to the slicing worker; the compose file overrides the command per role.
CMD ["rq", "worker", "slicing", "--url", "redis://redis:6379/0"]
