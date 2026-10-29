# iSpindel Fermentation Monitor

A fermentation monitoring system for a small brewery: an **iSpindel** floats in the fermenter and
publishes tilt, temperature, gravity and battery over **MQTT**. This system stores every
transmission in **PostgreSQL** and shows the live and historical course in a **Plotly Dash**
dashboard in the local network - start and end experiments, follow the fermentation, compare
batches, export the data as CSV.

The whole system is **four containers** in one `compose.yaml` and runs on a Windows PC, a Mac, a
Linux box or a Raspberry Pi:

```
 iSpindel --Wi-Fi/MQTT--> mosquitto :1883 --subscribe--> ingest --INSERT--> PostgreSQL
 (one transmission =                                         |            (one row per
  7 MQTT messages)                                           |             transmission)
                                                             |
                        browser <-- Dash/gunicorn :8080 <-- SELECT ----------+
```

Everything on this page is a copy-paste command. `<engine>` is `podman` or `docker` - pick the
one you installed; `compose.yaml` and `Dockerfile` are identical for both.

## 1 - Install a container engine

Prerequisite: a container engine with Compose. Nothing else - there is no Node.js, no Python, no
PostgreSQL and no mosquitto on the host, everything runs in the containers.

| Machine | Install |
| --- | --- |
| **Raspberry Pi / Debian / Ubuntu** | `sudo apt update && sudo apt install podman podman-compose` |
| **macOS** | `brew install podman && podman machine init && podman machine start` (or Docker Desktop) |
| **Windows** | `winget install Docker.DockerDesktop` (or Podman Desktop) with the **WSL 2** backend |
| check | `<engine> compose version` |

## 2 - Start the system

### macOS, Linux, Raspberry Pi (bash)

```bash
git clone <this repository> ispindel-monitor
cd ispindel-monitor
podman compose up -d --build        # Docker instead: docker compose up -d --build
```

### Windows (PowerShell)

```powershell
git clone <this repository> ispindel-monitor
cd ispindel-monitor
docker compose up -d --build        # Podman Desktop instead: podman compose up -d --build
```

The first run builds the image (a minute or two) and starts four containers. Check them with

```bash
<engine> compose ps
```

Now point the iSpindel at this machine - MQTT server = the LAN address, port `1883`:

| OS | The LAN address |
| --- | --- |
| macOS | `ipconfig getifaddr en0` |
| Linux / Raspberry Pi | `hostname -I` |
| Windows | `ipconfig` (IPv4 of the active adapter) |

Open <http://localhost:8080> - the dashboard. PostgreSQL creates the schema on the first start, so
an iSpindel that publishes to port 1883 is stored and shown immediately.

### Something to look at first

The dashboard starts **empty**. To see it with data instead, start the stack with the `demo`
profile - it adds a one-shot container that seeds six simulated iSpindels (17 batches: cards,
comparison chart, CSV export) and then exits:

```bash
<engine> compose --profile demo up -d --build
```

On a stack that is already running, the same data comes from

```bash
<engine> compose exec -T dashboard python tools/simulate.py --demo --until-now
```

Everything seeded this way carries the `SIM_` prefix. Remove it again with
`<engine> compose exec -T dashboard python tools/simulate.py --delete`.

## 3 - The four containers

| Service | Image / build | What it does | Reachable at |
| --- | --- | --- | --- |
| `db` | `postgres:16-alpine` | storage; applies `sql/schema.sql` on the first start | `127.0.0.1:5433` - **loopback only** |
| `broker` | `eclipse-mosquitto:2` | receives the iSpindel (`deploy/mosquitto.conf`) | `<host>:1883` - LAN |
| `ingest` | this repository (`Dockerfile`) | assembles the 7 messages of one transmission into one row | - |
| `dashboard` | this repository (`Dockerfile`) | Plotly Dash behind gunicorn | `<host>:8080` - LAN |
| `seed` | this repository (`Dockerfile`) | **only with `--profile demo`**: one-shot, seeds the simulated fleet and exits | - |

The three official images are multi-arch, so the same `compose.yaml` runs on x86-64 and on the
Raspberry Pi (arm64). `ingest` and `dashboard` are the **same image** and differ only in their
`command`. The dashboard has **no authentication** - keep it inside the local network.

## 4 - Configuration

All settings live in **`config.yml`** - never in the code (NFR-08). The file is committed and
contains **no machine-specific value**, so nothing has to be rewritten on another machine.

| Setting | Meaning |
| --- | --- |
| `database.dsn` | PostgreSQL connection string (only used by a run **without** containers) |
| `mqtt.host` / `mqtt.port` / `mqtt.client_id` / `mqtt.topic_prefix` | broker address, unique client id, `ispindel` topic prefix |
| `ingest.burst_seconds` / `gravity_unit` / `log_messages` | burst fallback, device gravity unit (`P`/`SG`), verbose logging |
| `dashboard.refresh_ms` / `live_ms` | chart refresh (FR-14), countdown tick |
| `dashboard.battery_*_v` | battery gauge limits and the FR-19 warning threshold |
| `dashboard.expected_attenuation` / `target_temp_c` | FR-20 targets (FG, ABV estimate, temperature window per style) |
| `dashboard.timezone` | display time zone (NFR-09; stored in UTC) |

Inside the container network `compose.yaml` overrides only the addresses
(`ISPINDEL_DB_DSN`, `ISPINDEL_MQTT_HOST`, `ISPINDEL_MQTT_CLIENT_ID`). Two host ports can be moved
without editing anything:

```bash
ISPINDEL_HTTP_PORT=8090 ISPINDEL_PG_PORT=5434 podman compose up -d
```

```powershell
$env:ISPINDEL_HTTP_PORT=8090; $env:ISPINDEL_PG_PORT=5434; docker compose up -d
```

`ISPINDEL_CONFIG=/path/to/other.yml` points any component at a completely different file.

## 5 - Everyday commands

`<engine>` = `podman` or `docker`. Run them in the cloned directory.

| What | Command |
| --- | --- |
| start / update after a code change | `<engine> compose up -d --build` |
| stop (the `pgdata` volume - the data - survives) | `<engine> compose down` |
| follow the logs (Ctrl-C leaves them running) | `<engine> compose logs -f --tail 50` |
| what runs | `<engine> compose ps` |
| is the database ready? | `<engine> compose exec -T db pg_isready -U ispindel -d ispindel` |
| the three self-tests | `<engine> compose exec -T dashboard python tools/check_requirements.py` etc. |
| start (or update) with mock data | `<engine> compose --profile demo up -d --build` |
| seed the demo fleet on a running stack | `<engine> compose exec -T dashboard python tools/simulate.py --demo --until-now` |
| remove the mock data again | `<engine> compose exec -T dashboard python tools/simulate.py --delete` |
| a psql prompt on the database | `<engine> compose exec db psql -U ispindel -d ispindel` |
| a shell inside the dashboard container | `<engine> compose exec dashboard bash` |
| development (Dash hot reload, writes to the source tree) | `ISPINDEL_DASHBOARD_CMD="python main.py" <engine> compose up -d --build` |

On Windows the last one is `$env:ISPINDEL_DASHBOARD_CMD="python main.py"; docker compose up -d --build`.

## 6 - Raspberry Pi: start on boot and nightly backup

Two systemd units in `deploy/systemd/` make the Pi a set-and-forget box (NFR-03 / NFR-04).
Put the clone in `/srv/ispindel` (the units use that path):

```bash
sudo mkdir -p /srv && sudo git clone <this repository> /srv/ispindel
cd /srv/ispindel && sudo podman compose up -d --build

sudo cp deploy/systemd/ispindel.service deploy/systemd/ispindel-backup.service deploy/systemd/ispindel-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ispindel ispindel-backup.timer
```

* `ispindel.service` runs `podman compose up -d` at boot. With Podman there is no daemon that
  could restore the containers, so this unit **is** the boot mechanism. (Docker restores them by
  itself - the unit is harmless there, `systemctl enable ispindel` is simply optional.)
* `ispindel-backup.timer` runs `deploy/backup.sh` nightly at 03:30 into `/var/backups/ispindel`,
  keeps 14 days and verifies the dump is not empty.
* The Pi has **no real-time clock**: both units wait for `time-sync.target`, otherwise
  `recorded_at` would be stamped wrong (FR-08 / NFR-09).

A manual backup (also fine on the Mac or on Windows):

```bash
bash deploy/backup.sh                                        # Linux, macOS, Raspberry Pi
```

```powershell
# `cmd /c` keeps the bytes intact (PowerShell's `>` would write UTF-16 and corrupt the dump)
cmd /c "mkdir deploy\backups 2>nul & docker compose exec -T db pg_dump -U ispindel -Fc -d ispindel > deploy\backups\ispindel.dump"
```

## 7 - Tests

The checks run **inside the dashboard container** - same code, same config, the database of the
stack - so no local Python is needed:

```bash
<engine> compose exec -T dashboard python tools/check_requirements.py
<engine> compose exec -T dashboard python tools/ui_test.py
<engine> compose exec -T dashboard python tools/fr19_test.py
```

| Script | Checks |
| --- | --- |
| `tools/check_requirements.py` | the functional requirements that need no hardware |
| `tools/ui_test.py` | the experiment dialog and the table row actions |
| `tools/fr19_test.py` | the status indication (healthy / stale / low battery) |

They create only `zz_*` rows and clean up after themselves. `tools/fake_spindel.py` simulates an
iSpindel (7 MQTT topics) without hardware.

## 8 - Development (host-side only)

```bash
cd assets && npm ci && npm run css              # Tailwind build -> assets/tailwind.css
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # only to run tools/ on the host
```

The UI is styled with **Tailwind v4**; `assets/input.pcss` is the source and
`assets/tailwind.css` is the committed build artefact served statically - **a class added to the
Python code does nothing until `cd assets && npm run css` is run**. Every class string is written
out in full inside a `className`/`extra` argument (Tailwind compiles from the raw file text).

## 9 - Troubleshooting

| Symptom | Check |
| --- | --- |
| dashboard not reachable | `<engine> compose ps`, then `<engine> compose logs dashboard` |
| no measurements arrive | `<engine> compose logs ingest` (prints every topic when `ingest.log_messages` is on), `<engine> compose logs broker` |
| ingest stores nothing | is the database up? `<engine> compose exec -T db pg_isready -U ispindel -d ispindel` |
| stale UI after a class change | the CSS is baked into the image - run `cd assets && npm run css`, then `<engine> compose up -d --build` |
| changed `compose.yaml`, weird behaviour | `<engine> compose down && <engine> compose up -d` (a changed port/volume needs a recreate) |
| port already in use | move it: `ISPINDEL_HTTP_PORT=8090` (see section 4) |
| "no container with ID or name" (Podman) | never remove containers by hand - always `compose down` |

## 10 - Repository layout

```
compose.yaml              the four services
Dockerfile                the image of the ingest service and the dashboard (one build, two commands)
config.yml                all settings (NFR-08), no machine-specific value in it
requirements.txt          runtime dependencies - what the image installs

main.py                   Plotly Dash dashboard (the only Python file in the root)
components/ui.py          reusable Tailwind layout components
components/charts.py      Plotly fermentation charts
services/db.py            tiny PostgreSQL helper
services/mqtt_service.py  MQTT -> PostgreSQL: assembles the 7 messages into one row
assets/                   Dash-served: tailwind.css, card_state.js, fonts/; package.json builds the CSS
sql/schema.sql            schema, keys, views; applied automatically on the first start
sql/migrations/           view/constraint migrations for a database that already exists
tools/                    self-tests and simulators
deploy/mosquitto.conf     broker configuration (mounted into the broker container)
deploy/backup.sh          pg_dump with 14 days retention (NFR-04)
deploy/systemd/           boot step + nightly backup timer for the Raspberry Pi
```

## 11 - Requirements and licence

The comments in the code name the requirement they implement (`FR-01` ... `FR-22`, `NFR-01` ...
`NFR-09`), which come from the assignment specification. Code: **MIT** (see `LICENSE`). The
bundled IBM XGA-AI fonts are **CC BY-SA 4.0** by VileR, full licence text in
`assets/fonts/LICENSE-oldschool-pc-font-pack.txt`.
