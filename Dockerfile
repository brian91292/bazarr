# syntax=docker/dockerfile:1.7
#
# Production image for the Bazarr fork. Designed to be built directly from a
# git URL by Docker Compose:
#
#   services:
#     bazarr:
#       build: https://github.com/<user>/bazarr.git#master
#
# Result is a drop-in replacement for lscr.io/linuxserver/bazarr:latest — same
# /config path, same PUID/PGID env semantics, same port 6767.
#
# Two stages:
#   1. frontend-builder  — compiles the React/Vite frontend to /build/build
#   2. runtime           — alpine + python + ffmpeg + mediainfo, carries the
#                          backend source and the prebuilt frontend.

# -----------------------------------------------------------------------------
# Stage 1: build the frontend
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy only the lockfiles first so npm ci stays cached when source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy the rest of the frontend and build. Output dir is ./build per
# frontend/vite.config.ts.
COPY frontend/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------------
FROM alpine:3.22 AS runtime

# Install runtime + build deps in a single layer so the build deps can be
# wiped before the layer is committed (smaller final image).
#
# Runtime deps:
#   - ffmpeg, mediainfo : media probing
#   - python3, py3-pip  : Bazarr runtime
#   - libxml2, libxslt  : lxml runtime
#   - p7zip             : archive handling
#   - bash              : entrypoint shell
#   - tzdata            : TZ env var resolution
#   - su-exec           : drop-privilege shim (alpine-native)
#   - netcat-openbsd    : healthcheck only
#
# Build deps (removed at end of RUN):
#   - build-base, cargo, libffi-dev, libpq-dev, libxml2-dev, libxslt-dev,
#     python3-dev : compiling any wheel that isn't in the linuxserver index.
RUN apk add --no-cache \
        ffmpeg \
        mediainfo \
        python3 \
        py3-pip \
        libxml2 \
        libxslt \
        p7zip \
        bash \
        tzdata \
        su-exec \
        netcat-openbsd \
 && apk add --no-cache --virtual=.build-deps \
        build-base \
        cargo \
        libffi-dev \
        libpq-dev \
        libxml2-dev \
        libxslt-dev \
        python3-dev \
 && mkdir -p /app/bazarr/bin /config

WORKDIR /app/bazarr/bin

# Install Python deps first — changes in these files are rare, so this layer
# gets reused across most rebuilds. --find-links points at the LinuxServer
# wheel mirror which carries prebuilt wheels for numpy/lxml/Pillow on alpine,
# saving ~15 min of compile on armv7/aarch64 hosts.
COPY requirements.txt postgres-requirements.txt ./
RUN pip install \
        --break-system-packages \
        --no-cache-dir \
        --find-links https://wheel-index.linuxserver.io/alpine-3.22/ \
        -r requirements.txt \
        -r postgres-requirements.txt \
 && apk del .build-deps

# Application source. Ordered least-churn-first so small code changes don't
# bust earlier cache layers.
COPY bazarr.py ./
COPY migrations ./migrations
COPY libs ./libs
COPY custom_libs ./custom_libs
COPY bazarr ./bazarr

# Prebuilt frontend — bazarr/app/ui.py serves static assets from
# <repo>/frontend/build, which maps to /app/bazarr/bin/frontend/build here.
COPY --from=frontend-builder /build/build ./frontend/build

# Entrypoint (PUID/PGID handling).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# PYTHONPATH order matters: custom_libs first so it can shadow libs/.
ENV PYTHONPATH="/app/bazarr/bin/custom_libs:/app/bazarr/bin/libs:/app/bazarr/bin/bazarr:/app/bazarr/bin" \
    BAZARR_VERSION="fork" \
    SZ_USER_AGENT="bazarr-fork"

EXPOSE 6767

# Bazarr accepting TCP ≠ fully ready, but this matches the loose bar the
# LinuxServer image sets (no healthcheck at all) while at least detecting
# a hung Python process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD nc -z localhost 6767 || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python3", "bazarr.py", "--no-update", "--config", "/config"]
