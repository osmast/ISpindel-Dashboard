#!/usr/bin/env bash
# NFR-04: a logical pg_dump in the custom format (consistent while PostgreSQL keeps running).
#   ./run.sh backup                              or:  bash deploy/backup.sh
#   ISPINDEL_BACKUP_DIR=/mnt/usb/pg bash deploy/backup.sh
# Retention: 14 days. Restore: podman compose exec -T db pg_restore -U ispindel -d ispindel --clean
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${ISPINDEL_BACKUP_DIR:-deploy/backups}"
KEEP_DAYS="${ISPINDEL_BACKUP_KEEP_DAYS:-14}"

# engine + compose provider (same rule as run.sh, kept separate so this script stands alone)
if [ -n "${ISPINDEL_ENGINE:-}" ]; then ENGINE="$ISPINDEL_ENGINE"
elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then ENGINE=podman
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then ENGINE=docker
else echo "no usable container engine found - see README section 2" >&2; exit 1; fi

compose() {
  case "$ENGINE" in
    podman) if podman compose version >/dev/null 2>&1; then podman compose "$@"
            else podman-compose "$@"; fi;;
    docker) docker compose "$@";;
  esac
}

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$BACKUP_DIR/ispindel-$STAMP.dump"

echo "engine $ENGINE -> $FILE"
compose exec -T db pg_dump -U ispindel -Fc -d ispindel > "$FILE"

# A dump that is empty or truncated is worse than no dump, because it looks like a backup.
if [ ! -s "$FILE" ]; then echo "backup FAILED: $FILE is empty" >&2; rm -f "$FILE"; exit 1; fi
echo "ok: $(du -h "$FILE" | cut -f1)"

# 14-day retention - only this script's own files are touched.
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'ispindel-*.dump' -mtime "+$KEEP_DAYS" -print -delete
echo "kept:"; ls -1t "$BACKUP_DIR"/ispindel-*.dump | head -5
