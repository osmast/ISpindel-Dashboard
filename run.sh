#!/usr/bin/env bash
# The single entry point. Works on every machine and with either engine (Podman preferred,
# Docker works too). ISPINDEL_ENGINE=podman|docker forces one.
#
#   ./run.sh up       build and start everything, then print the dashboard URL
#   ./run.sh dev      same stack, but the app runs from the source tree (hot reload)
#   ./run.sh down     stop and remove the containers (the pgdata volume - the data - stays)
#   ./run.sh logs     follow the logs of all four services (Ctrl-C leaves them running)
#   ./run.sh ps       what runs, and the health of database and broker
#   ./run.sh test     the browser-less requirement checks, inside the running container
#   ./run.sh demo     seed the simulated 6-device fleet (demo data)
#   ./run.sh backup   NFR-04: pg_dump into deploy/backups, keeps the last 14 days
#   ./run.sh psql     interactive psql on the database
#   ./run.sh shell    a shell inside the dashboard container
# ---------------------------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

# The usage text is the comment block at the top of this file - one source, so it cannot drift.
usage() { awk '/^# ---/ {exit} /^#/ && !/^#!/ {sub(/^# ?/, ""); print}' "$0"; }

detect_engine() {
  case "${ISPINDEL_ENGINE:-auto}" in
    podman|docker) printf '%s\n' "$ISPINDEL_ENGINE"; return 0;;
  esac
  # `info` also tells whether the engine is actually usable (Podman: the machine/VM is running).
  if command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then printf 'podman\n'
  elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then printf 'docker\n'
  else printf '\n'; fi
}

ENGINE="$(detect_engine)"
if [ -z "$ENGINE" ]; then
  cat >&2 <<'MSG'
no usable container engine found.

  Podman (preferred)   macOS: brew install podman && podman machine init && podman machine start
                       Debian/Raspberry Pi OS: sudo apt install podman podman-compose
  Docker (alternative) Docker Desktop on macOS / docker.io + docker-compose-plugin on Linux

Then run ./run.sh up again. See README section 2.
MSG
  exit 1
fi

compose() {
  case "$ENGINE" in
    podman) if podman compose version >/dev/null 2>&1; then podman compose "$@"
            else podman-compose "$@"; fi;;
    docker) docker compose "$@";;
  esac
}

case "${1:-}" in
  up)
    compose up -d --build
    # LAN address for the iSpindel: macOS has no `hostname -I`, Linux has no `ipconfig`.
    LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')" \
      || LAN_IP=""
    echo
    echo "engine:    $ENGINE"
    echo "dashboard: http://localhost:8080"
    echo "broker:    ${LAN_IP:-<this host>}:1883   <- point the iSpindel here"
    echo "logs:      ./run.sh logs"
    ;;
  dev)
    # Same stack, but the app runs from the source tree (Dash hot reload) - compose.yaml.
    ISPINDEL_DASHBOARD_CMD="python main.py" compose up -d --build
    echo
    echo "dev stack on http://localhost:8080   (edit main.py / components/*.py - the browser reloads by itself)"
    ;;
  down)   compose down ;;
  logs)   compose logs -f --tail 50 ;;
  ps)     compose ps
          echo
          compose exec -T db pg_isready -U ispindel -d ispindel ;;
  test)   # Inside the container: same code, same config, the database of the stack.
          compose exec -T dashboard python tools/check_requirements.py
          compose exec -T dashboard python tools/ui_test.py
          compose exec -T dashboard python tools/fr19_test.py ;;
  demo)   compose exec -T dashboard python tools/simulate.py --demo --until-now ;;
  backup) exec bash deploy/backup.sh ;;
  psql)   compose exec db psql -U ispindel -d ispindel ;;
  shell)  compose exec dashboard bash ;;
  ""|-h|--help|help) usage ;;
  *) echo "unknown command: $1" >&2; echo >&2; usage; exit 1 ;;
esac
