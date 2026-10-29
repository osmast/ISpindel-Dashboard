# iSpindel Fermentation Monitor

A fermentation monitoring system for a small brewery: an **iSpindel** floats in the fermenter and
publishes tilt, temperature, gravity and battery over **MQTT**. This system stores every
transmission in **PostgreSQL** and shows the live and historical course in a **Plotly Dash**
dashboard in the local network - start and end experiments, follow the fermentation, compare
batches, export the data as CSV.

The whole system is **three containers** in one `compose.yaml` - database, broker and dashboard -
plus an **optional fourth** container (`ingest`) that records a real iSpindel. It runs on a
Windows PC, a Mac, a Linux box or a Raspberry Pi:

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

The first run builds the image (a minute or two) and starts three containers. Check them with

```bash
<engine> compose ps
```

Open <http://localhost:8080> - the dashboard. PostgreSQL creates the schema on the first start.

### Recording a real iSpindel (optional ingest)

`up` starts the database, the broker and the dashboard. The **ingest** - the container that turns
the iSpindel's seven messages into one table row - is **not** part of that; start it as the extra
step when a real iSpindel should be recorded:

```bash
<engine> compose --profile ingest up -d ingest      # `up -d ingest` alone works too
```

The profile has to be repeated for **every** command that addresses that service (`ps`, `logs`,
`restart`, `exec`, `down`) - without it the provider does not see the service at all
(`missing services [ingest]` / `no such service: ingest`).

Now point the iSpindel at this machine - MQTT server = the LAN address, port `1883`:

| OS | The LAN address |
| --- | --- |
| macOS | `ipconfig getifaddr en0` |
| Linux / Raspberry Pi | `hostname -I` |
| Windows | `ipconfig` (IPv4 of the active adapter) |

From then on every transmission of that iSpindel is stored and shown live. The same container in
the foreground is the one-off variant (Ctrl-C stops it), and stopping the stack **with** the
profile stops the ingest as well - a plain `<engine> compose down` leaves it running:

```bash
<engine> compose --profile ingest run --rm ingest
<engine> compose --profile ingest down
```

### Other iSpindels in use: their own brokers (FR-15)

Each participant runs **their own** broker, so one broker is rarely enough. The **MQTT brokers**
button at the bottom left of the *Devices* tab opens a dialog that adds one (label, host, port,
topic prefix, optional user/password). For every broker the list shows how many iSpindels it
delivered and what it does right now - *delivering*, *connected, no data yet*, *silent since ...*
or the connection error. A running ingest picks a broker up within `ingest.broker_refresh_seconds`
(10 s) without a restart; pausing, editing or deleting it takes effect the same way. The Devices
tab itself names the **broker address** of every iSpindel (for the own broker the LAN address an
iSpindel has to publish to, plus the label underneath).

* The broker of `config.yml` is the first row and is **not** editable there - it stays in the file
  (NFR-08). Everything else is data: the added brokers live in the `mqtt_broker` table.
* The Devices tab shows the same list **inline** (below the devices, read-only) - so a broker that
  is configured but not yet delivering is visible without opening the dialog.
* Each device row also carries a **trash icon**: it deletes that iSpindel with its experiments and
  measurements (a confirmation first, FR-12). A device that is still publishing is created again by
  the next transmission - that is the honest behaviour, not a bug.
* A broker that wants a login answers `Not authorized`; the row then shows
  **not connected: connect failed: Not authorized** - put the user and password into the form
  (mosquitto's `allow_anonymous false`). A host that is down or in another network shows
  **not connected after 60 s - is the broker reachable?**, because a TCP-level failure never reaches
  the MQTT layer. Both texts are the full line in a tooltip; the chip shows the reason only.
* Before trusting that, test the credentials (and what a broker carries) from the Pi - the broker
  container brings the client tools along:

  ```bash
  podman exec ispindel_broker_1 mosquitto_sub -h 160.85.124.31 -p 1883 \
      -u '<user>' -P '<pass>' -t 'ispindel/#' -v -W 15
  ```
* The host field also accepts a whole address (`160.85.124.31:1883`) - the port is taken from it.
* Two participants may use the same iSpindel name on their own brokers - the name is unique **per
  broker**, so the two stay two devices (the Devices tab names the broker **address** of every
  iSpindel, with its label underneath).
* An iSpindel should publish to **one** of the configured brokers. One that publishes to two of
  them is recorded twice, once per broker, because those are two independent sources.
* The *delivering* state is derived from the newest **stored** measurement of that broker's
  iSpindels - so it works for the own broker too, which has no row of its own. The connect/message
  times shown next to it come from the ingest, and they only move while it runs.

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

## 3 - The containers

| Service | Image / build | What it does | Reachable at |
| --- | --- | --- | --- |
| `db` | `docker.io/library/postgres:16-alpine` | storage; applies `sql/schema.sql` on the first start | `127.0.0.1:5433` - **loopback only** |
| `broker` | `docker.io/library/eclipse-mosquitto:2` | receives the iSpindel (`deploy/mosquitto.conf`) | `<host>:1883` - LAN |
| `ingest` | this repository (`Dockerfile`) | **only with `--profile ingest`**: assembles the 7 messages of one transmission into one row (section 2) | - |
| `dashboard` | this repository (`Dockerfile`) | Plotly Dash behind gunicorn | `<host>:8080` - LAN |
| `seed` | this repository (`Dockerfile`) | **only with `--profile demo`**: one-shot, seeds the simulated fleet and exits | - |

The three official images are multi-arch, so the same `compose.yaml` runs on x86-64 and on the
Raspberry Pi (arm64). Their names are **fully qualified** (`docker.io/library/...`), so Podman
never has to guess a registry: a bare `postgres:16-alpine` needs a short-name alias in the host's
`/etc/containers/registries.conf` and fails on a fresh Raspberry Pi. The `ingest` and the
`dashboard` are the **same image** and differ only in their `command`, which is why an ingest that
is started on demand needs no second build. The dashboard has **no authentication** - keep it
inside the local network.

## 4 - Configuration

All settings live in **`config.yml`** - never in the code (NFR-08). The file is committed and
contains **no machine-specific value**, so nothing has to be rewritten on another machine.

| Setting | Meaning |
| --- | --- |
| `database.dsn` | PostgreSQL connection string (only used by a run **without** containers) |
| `mqtt.host` / `mqtt.port` / `mqtt.client_id` / `mqtt.topic_prefix` | broker address, unique client id, `ispindel` topic prefix |
| `ingest.burst_seconds` / `gravity_unit` / `log_messages` | burst fallback, device gravity unit (`P`/`SG`), verbose logging |
| `ingest.broker_refresh_seconds` | FR-15: how often the running ingest re-reads the broker list (0 = only at startup) |
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
| what runs (three containers; the ingest appears only once started) | `<engine> compose ps` |
| start the ingest - records a real iSpindel | `<engine> compose --profile ingest up -d ingest` |
| the ingest as a one-off in the foreground (Ctrl-C stops it) | `<engine> compose --profile ingest run --rm ingest` |
| stop the stack incl. the ingest (plain `down` leaves the ingest container behind) | `<engine> compose --profile ingest down` |
| the ingest's log | `<engine> compose --profile ingest logs -f ingest` |
| add / pause / delete another MQTT broker (FR-15) | the **MQTT brokers** button at the bottom left of the *Devices* tab - no command |
| delete an iSpindel with its measurements and experiments (FR-12) | the **trash icon** of its row in the *Devices* tab (asks first) - a device that still publishes is created again by the next transmission |
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

* `ispindel.service` runs `podman compose --profile ingest up -d` at boot. The `--profile ingest`
  is deliberate: the ingest is optional in `compose.yaml`, but after a power cycle the Pi has to
  keep recording without anyone logging in (NFR-03), and the unit's matching `down` removes the
  ingest container as well. With Podman there is no daemon that could restore the containers, so
  this unit **is** the boot mechanism. (Docker restores them by itself - the unit is harmless
  there, `systemctl enable ispindel` is simply optional.)
* `ispindel-backup.timer` runs `deploy/backup.sh` nightly at 03:30 into `/var/backups/ispindel`,
  keeps 14 days and verifies the dump is not empty.
* The Pi has **no real-time clock**: both units wait for `time-sync.target`, otherwise
  `recorded_at` would be stamped wrong (FR-08 / NFR-09).

### Coming from the old bare-metal installation

The first installation used apt `mosquitto` and `postgresql`, a conda env and the two systemd units
`ispindel-ingest` / `ispindel-dashboard`. Those units hold **`1883`** and **`8080`**, so the
containers cannot bind their ports and stop with:

```
Error: rootlessport listen tcp 0.0.0.0:1883: bind: address already in use
Error: rootlessport listen tcp 0.0.0.0:8080: bind: address already in use
```

Stop and disable them once - the stack brings its own broker and dashboard:

```bash
sudo ss -ltnp | grep -E ':(1883|8080)\b'                          # who holds the two ports
sudo systemctl disable --now ispindel-ingest ispindel-dashboard mosquitto
sudo ss -ltn  | grep -E ':(1883|8080)\b' || echo '1883 and 8080 are free'
```

Then clear what a failed attempt left behind and start the stack again:

```bash
cd /srv/ispindel && podman compose --profile ingest down && podman compose up -d --build
```

`postgresql.service` **stays**: it holds the measurements of the fermentation phase on `5432`,
while the database of the stack starts empty (`127.0.0.1:5433` on the host). Copy the rows into
the container database - data only, because `sql/schema.sql` already created the tables there:

```bash
PGPASSWORD=ispindel pg_dump -h 127.0.0.1 -p 5432 -U ispindel --data-only --inserts ispindel > /tmp/old-data.sql
podman compose exec -T db psql -U ispindel -d ispindel < /tmp/old-data.sql
podman compose exec -T db psql -U ispindel -d ispindel -c 'SELECT count(*) FROM measurement'
```

Finally point the iSpindel at the broker of the stack: server = the Pi's LAN address, port `1883`
(the topics do not change: `<prefix>/<device name>/<field>`).


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
| no rows in the dashboard | is the ingest running? `<engine> compose ps` shows three containers - start it with `<engine> compose --profile ingest up -d ingest` (section 2) |
| a broker stays at *no data yet* | it is configured but nothing was stored from it: `<engine> compose --profile ingest up -d ingest` must run (the ingest closes listeners when it is not), then look at the row's state - *not connected: Not authorized* means the broker wants a user/password |
| `missing services [ingest]` / `no such service: ingest` | the ingest sits behind a profile: give **that** command the profile too (`ps`, `logs`, `restart`, `exec`, `down`). `restart` also needs an existing container - after a plain `up`, run `<engine> compose --profile ingest up -d ingest` instead |
| no measurements arrive | `<engine> compose --profile ingest logs ingest` (prints every topic when `ingest.log_messages` is on), `<engine> compose logs broker` |
| ingest stores nothing | is the database up? `<engine> compose exec -T db pg_isready -U ispindel -d ispindel` |
| stale UI after a class change | the CSS is baked into the image - run `cd assets && npm run css`, then `<engine> compose up -d --build` |
| changed `compose.yaml`, weird behaviour | `<engine> compose down && <engine> compose up -d` (a changed port/volume needs a recreate) |
| `bind: address already in use` for `1883`/`8080` | something else already listens there - an old bare-metal installation or a second stack (section 6); the dashboard port alone moves with `ISPINDEL_HTTP_PORT=8090` (section 4) |
| `short-name "postgres:16-alpine" did not resolve to an alias` (Podman) | the clone predates the fully qualified image names - `git pull`; `compose.yaml` names every image as `docker.io/library/...` |
| "no container with ID or name" (Podman) | never remove containers by hand - always `compose down` |

## 10 - Repository layout

```
compose.yaml              the stack (db, broker, dashboard) + the optional ingest/seed profiles
Dockerfile                the image of the ingest service and the dashboard (one build, two commands)
config.yml                all settings (NFR-08), no machine-specific value in it
requirements.txt          runtime dependencies - what the image installs

main.py                   Plotly Dash dashboard (the only Python file in the root)
components/ui.py          reusable Tailwind layout components
components/charts.py      Plotly fermentation charts
services/db.py            tiny PostgreSQL helper
services/mqtt_service.py  MQTT -> PostgreSQL: assembles the 7 messages into one row
assets/                   Dash-served: tailwind.css, card_state.js, fonts/; package.json builds the CSS
sql/schema.sql            schema, keys, views (incl. `mqtt_broker` for the FR-15 brokers); on first start
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
