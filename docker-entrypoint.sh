#!/bin/sh
# Entrypoint for the Bazarr fork's production image.
#
# Honors the same PUID / PGID / TZ environment variables as the
# lscr.io/linuxserver/bazarr image so the user's existing compose env block
# works unchanged. Runs Bazarr as that unprivileged user via su-exec.
#
# Explicit design decisions:
#   * Only chown /config — NEVER /mnt/media. The media mount is shared with
#     Sonarr/Radarr/Plex; ownership there is managed by the NAS, not us.
#   * `exec su-exec` so SIGTERM from Docker reaches Python directly (clean
#     shutdown inside the default 10s stop grace).
#   * `"$@"` passes the CMD through untouched, so `docker run image sh` and
#     similar one-off invocations still work.

set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Validate that PUID / PGID are positive integers. A non-numeric value here
# would blow up later inside addgroup/adduser with a cryptic error.
case "$PUID" in
    ''|*[!0-9]*) echo "docker-entrypoint: PUID must be a non-negative integer, got '$PUID'" >&2; exit 1 ;;
esac
case "$PGID" in
    ''|*[!0-9]*) echo "docker-entrypoint: PGID must be a non-negative integer, got '$PGID'" >&2; exit 1 ;;
esac

# Create (or reuse) the bazarr group at the requested GID. If a group already
# exists at that GID — e.g. one of alpine's reserved groups — use its name
# instead of failing.
if ! getent group bazarr >/dev/null 2>&1; then
    if getent group "$PGID" >/dev/null 2>&1; then
        BAZARR_GROUP="$(getent group "$PGID" | cut -d: -f1)"
    else
        addgroup -g "$PGID" bazarr
        BAZARR_GROUP="bazarr"
    fi
else
    BAZARR_GROUP="bazarr"
fi

# Same logic for the user. Reuse an existing UID match rather than failing.
if ! getent passwd bazarr >/dev/null 2>&1; then
    if getent passwd "$PUID" >/dev/null 2>&1; then
        BAZARR_USER="$(getent passwd "$PUID" | cut -d: -f1)"
    else
        adduser -D -H -u "$PUID" -G "$BAZARR_GROUP" -s /sbin/nologin bazarr
        BAZARR_USER="bazarr"
    fi
else
    BAZARR_USER="bazarr"
fi

# Make sure Bazarr can write to /config. If the dir doesn't exist yet (bind
# mount missing) we still try to create it so first-run doesn't explode
# inside Python with a less-friendly error.
if [ ! -d /config ]; then
    mkdir -p /config
fi
chown -R "$PUID:$PGID" /config 2>/dev/null || \
    echo "docker-entrypoint: warning - could not chown /config; continuing" >&2

exec su-exec "$PUID:$PGID" "$@"
