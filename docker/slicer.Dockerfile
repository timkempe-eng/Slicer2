# Headless Bambu Studio CLI image (PRD §11.2 — slicing worker node).
#
# Bambu Studio ships as a Linux AppImage. We extract it and run the bundled
# binary under xvfb (the CLI still initialises a GL/Qt context on some builds).
# Pin BAMBU_VERSION to a known-good release for reproducible slices.
FROM ubuntu:22.04

ARG BAMBU_VERSION=v01.10.02.76
ARG BAMBU_APPIMAGE_URL=https://github.com/bambulab/BambuStudio/releases/download/${BAMBU_VERSION}/Bambu_Studio_ubuntu-24.04_PR-7286.AppImage

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xvfb \
        libgl1 libgtk-3-0 libwebkit2gtk-4.1-0 libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 libsoup-3.0-0 libosmesa6 \
        fonts-dejavu-core libfuse2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/bambu
# NOTE: download URL/asset name changes per release — verify before building.
RUN curl -fSL "${BAMBU_APPIMAGE_URL}" -o BambuStudio.AppImage \
    && chmod +x BambuStudio.AppImage \
    && ./BambuStudio.AppImage --appimage-extract \
    && rm BambuStudio.AppImage

# Wrapper so callers can just run `bambu-studio ...`.
RUN printf '#!/bin/sh\nexec xvfb-run -a /opt/bambu/squashfs-root/AppRun "$@"\n' \
        > /usr/local/bin/bambu-studio \
    && chmod +x /usr/local/bin/bambu-studio

ENTRYPOINT ["bambu-studio"]
