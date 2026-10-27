# iSpindel Fermentation Monitor

A fermentation monitoring system for a small brewery: an **iSpindel** floats in the fermenter and
publishes tilt, temperature, gravity and battery over **MQTT**. This system stores every
transmission in **PostgreSQL** and shows the live and historical course in a **Plotly Dash**
dashboard in the local network - start and end experiments, follow the fermentation, compare
batches, export the data as CSV.

The whole system is **four containers** and starts with one command on any machine - a laptop, a
colleague's computer or a Raspberry Pi:

```
 iSpindel --Wi-Fi/MQTT--> mosquitto :1883 --subscribe--> ingest --INSERT--> PostgreSQL
 (one transmission =                                         |            (one row per
  7 MQTT messages)                                           |             transmission)
                                                             |
                        browser <-- Dash/gunicorn :8080 <-- SELECT ----------+
```

## Quick start

Prerequisite: a container engine with Compose - nothing else. Podman is preferred, Docker works
identically (`compose.yaml` and `Dockerfile` are engine-neutral).

```bash
# 1. Podman (macOS: Docker Desktop also works, skip this step)
brew install podman && podman machine init && podman machine start      # macOS
sudo apt install podman podman-compose                                  # Debian / Raspberry Pi OS

# 2. the system
git clone <this repository> ispindel-monitor && cd ispindel-monitor
./run.sh up
```

`./run.sh up` builds the image, starts database, broker, ingest and dashboard and prints

```
engine:    podman
dashboard: http://localhost:8080
broker:    192.168.0.24:1883   <- point the iSpindel here
```

That is the running system: the dashboard is on <http://localhost:8080>, the schema is created by
PostgreSQL itself on the first start, and an iSpindel that publishes to this machine's port 1883
is stored and shown immediately.

Want something to look at first? `./run.sh demo` seeds six simulated iSpindels with 17 batches
(batch cards, comparison chart, CSV export); `./run.sh test` runs the automatic self-tests.

## The four containers

| Service | Image / build | What it does | Reachable at |
| --- | --- | --- | --- |
| `db` | `postgres:16-alpine` | storage; applies `sql/schema.sql` on the first start | `127.0.0.1:5433` (loopback only) |
| `broker` | `eclipse-mosquitto:2` | receives the iSpindel (`deploy/mosquitto.conf`) | `<host>:1883` (LAN) |
| `ingest` | this repository (`Dockerfile`) | assembles the 7 messages of one transmission into one row | - |
| `dashboard` | this repository (`Dockerfile`) | Plotly Dash behind gunicorn | `<host>:8080` (LAN) |

`compose.yaml` is the only place where the system is wired together; `./run.sh` is a thin wrapper
around it that also picks the engine. Both the ingest service and the dashboard run from the
**same image** and differ only in their `command`.

Ports can be moved without editing anything: `ISPINDEL_HTTP_PORT=8090 ISPINDEL_PG_PORT=5434
./run.sh up` (the ports *inside* the container network never change).

## Configuration

All settings live in **`config.yml`** - never in the code (NFR-08). The file is committed and
contains **no machine-specific value**: it describes the setup the containers implement, so
nothing has to be rewritten when the system moves to another machine.

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
(`ISPINDEL_DB_DSN`, `ISPINDEL_MQTT_HOST`, `ISPINDEL_MQTT_PORT`, `ISPINDEL_MQTT_CLIENT_ID`).
`ISPINDEL_CONFIG=/path/to/other.yml` points any component at a different file.

## `./run.sh` commands

| Command | Effect |
| --- | --- |
| `up` | build and start all four containers |
| `dev` | same stack, but the app runs from the source tree with Dash hot reload |
| `down` | stop and remove the containers (the `pgdata` volume - the data - survives) |
| `logs` | follow the logs of all services |
| `ps` | what runs, plus the health of database and broker |
| `test` | the three self-tests, inside the container |
| `demo` | seed the simulated 6-device fleet |
| `backup` | `pg_dump` into `deploy/backups` (14 days retention, NFR-04) |
| `psql` | interactive psql on the database |
| `shell` | a shell inside the dashboard container |

## Raspberry Pi

The stack is the same as on a laptop. On the Pi it lives in `/srv/ispindel` and needs a **boot
step** (NFR-03) and a **nightly backup** (NFR-04), both shipped in `deploy/systemd/`:

```bash
sudo cp deploy/systemd/ispindel.service /etc/systemd/system/
sudo cp deploy/systemd/ispindel-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ispindel ispindel-backup.timer
```

The Pi has no real-time clock, so both units wait for `time-sync.target` - without a correct
clock `recorded_at` would be stamped wrong (FR-08 / NFR-09).

## Tests

`./run.sh test` runs the browser-less checks **inside the dashboard container** (same code, same
config, the database of the stack):

| Script | Checks |
| --- | --- |
| `tools/check_requirements.py` | the functional requirements that need no hardware |
| `tools/ui_test.py` | the experiment dialog and the table row actions |
| `tools/fr19_test.py` | the status indication (healthy / stale / low battery) |

They create only `zz_*` rows and clean up after themselves. `tools/fake_spindel.py` (simulated
iSpindel) and `tools/simulate.py` (demo data) need no hardware either.

## Development (host-side only)

```bash
npm ci && npm run css                           # Tailwind build (after a class change)
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # only to run tools/ on the host
```

The UI is styled with **Tailwind v4**; `assets/input.pcss` is the source and
`assets/tailwind.css` is the committed build artefact served statically - **a class added to
the Python code does nothing until `npm run css` is run**. Every class string is written out in
full inside a `className`/`extra` argument (Tailwind compiles from the raw file text).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| dashboard not reachable | `./run.sh ps`, then `./run.sh logs dashboard` |
| no measurements arrive | `./run.sh logs ingest` (prints every topic when `ingest.log_messages` is on), `./run.sh logs broker` |
| ingest stores nothing | database reachable? `./run.sh ps` runs `pg_isready` |
| stale UI after a class change | the CSS is baked into the image - run `npm run css`, then `./run.sh up` |
| changed `compose.yaml`, weird behaviour | `./run.sh down && ./run.sh up` (a changed port/volume needs a recreate) |

## Repository layout

```
run.sh                    entry point: up / dev / down / logs / ps / test / demo / backup / psql / shell
compose.yaml              the four services
Dockerfile                the image of the ingest service and the dashboard (one build, two commands)
config.yml                all settings (NFR-08), no machine-specific value in it
requirements.txt          runtime dependencies - what the image installs
package.json              Tailwind CLI build step for assets/tailwind.css

main.py                   Plotly Dash dashboard (cards, tables, callbacks, export)
db.py                     tiny PostgreSQL helper
components/ui.py          reusable Tailwind layout components
components/charts.py      Plotly fermentation charts
mqtt_service.py           MQTT -> PostgreSQL: assembles the 7 messages into one row
assets/                   served by Dash: input.pcss -> tailwind.css (committed), card_state.js, fonts/
sql/schema.sql            schema, keys, views; applied automatically on the first start
sql/migrations/           view/constraint migrations for a database that already exists
tools/                    self-tests and simulators (run via ./run.sh)
deploy/mosquitto.conf     broker configuration (mounted into the broker container)
deploy/backup.sh          pg_dump with 14 days retention (NFR-04)
deploy/systemd/           boot step + nightly backup timer for the Raspberry Pi
```

## Requirements and licence

The comments in the code name the requirement they implement (`FR-01` ... `FR-22`, `NFR-01` ...
`NFR-09`), which come from the assignment specification. Code: **MIT** (see `LICENSE`). The
bundled IBM XGA-AI fonts are **CC BY-SA 4.0** by VileR, full licence text in
`assets/fonts/LICENSE-oldschool-pc-font-pack.txt`.
