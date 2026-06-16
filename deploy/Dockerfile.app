# Combined production image: the headless Bambu-compatible slicer + the FastAPI
# app in one container, so in-process slicing works without a separate queue
# (MVP). Split the slicer into its own worker image once Celery/Redis is wired.
#
# Stage 1 obtains the slicer; stage 2 adds Python and the app.

# ---- stage 1: extract the slicer AppImage ----
FROM ubuntu:24.04 AS slicer
ARG BAMBU_VERSION=v01.10.02.76
ARG BAMBU_APPIMAGE_URL=https://github.com/bambulab/BambuStudio/releases/download/${BAMBU_VERSION}/Bambu_Studio_ubuntu-24.04_PR-7286.AppImage
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl libfuse2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/bambu
# NOTE: verify the release asset name before building — it changes per release.
RUN curl -fSL "${BAMBU_APPIMAGE_URL}" -o BambuStudio.AppImage \
    && chmod +x BambuStudio.AppImage \
    && ./BambuStudio.AppImage --appimage-extract \
    && rm BambuStudio.AppImage

# ---- stage 2: runtime app ----
FROM ubuntu:24.04
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SLICER2_SLICER_BIN=bambu-studio SLICER2_DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv xvfb \
        libgl1 libgtk-3-0 libwebkit2gtk-4.1-0 libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 libsoup-3.0-0 libosmesa6 \
        fonts-dejavu-core libfuse2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=slicer /opt/bambu/squashfs-root /opt/bambu/squashfs-root
RUN printf '#!/bin/sh\nexec xvfb-run -a /opt/bambu/squashfs-root/AppRun "$@"\n' \
        > /usr/local/bin/bambu-studio && chmod +x /usr/local/bin/bambu-studio

WORKDIR /app
COPY backend/requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/venv/bin:${PATH}"
COPY backend/app ./app
COPY backend/profiles ./profiles

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
