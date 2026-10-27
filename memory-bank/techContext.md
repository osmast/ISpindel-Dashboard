# Tech Context

## Stack (all confirmed in the repository)

| Layer | Technology | Version / source |
| --- | --- | --- |
| Sensor | iSpindel, stock firmware (universam 7.3.3 in `~/Downloads`) | MQTT publisher, QoS 0, 7 topics per transmission |
| Broker | mosquitto (Pi) / Homebrew mosquitto / `amqtt` (local test broker) | `deploy/mosquitto.conf`, `tools/run_broker.sh` |
| Ingest | Python `paho-mqtt` >= 2.1 (CallbackAPIVersion.VERSION2) + `psycopg[binary]` >= 3.2 | `ingest/mqtt_ingest.py` |
| Database | PostgreSQL 16 (`timestamptz`, `btree_gist`, exclusion constraint) | `sql/schema.sql` |
| Dashboard | Plotly Dash >= 3.0 + dash-mantine-components >= 2.8 (`dmc.Grid`) + Plotly >= 6.0 | `app/main.py` |
| Production server | gunicorn >= 22.0 (`main:server`, `-b 0.0.0.0:8080`) | `app/main.py`, README 2.3 |
| Config | PyYAML, `config.yml`, override via `ISPINDEL_CONFIG` | `config.yml` |
| CSS | Tailwind CSS CLI v4.3.3 (`@tailwindcss/cli`) + plugin `@toolwind/corner-shape` 0.0.8-3, source `assets/input.pcss` -> committed `assets/tailwind.css` | `package.json`, `assets/input.pcss` |
| Fonts | IBM XGA-AI (7x15 / 12x20 / 12x23 / "12x20 Plus") from *The Ultimate Oldschool PC Font Pack v2.2* (VileR, CC BY-SA 4.0); `.woff`, page default via `@theme --font-sans`, Plotly figures via `charts.FONT_FAMILY` | `assets/fonts/`, `assets/input.pcss`, `components/charts.py` |
| Serial debugging | (removed with `tools/serial_monitor.py`, 27.10.2026) | - |
| Runtime | **Podman/Docker Compose** - four containers (`db`, `broker`, `ingest`, `dashboard`); the image is `python:3.12-slim` + `requirements.txt`, started with `podman compose up -d --build` (or `docker compose ...`) - the commands are the README, there is no wrapper script | `compose.yaml`, `Dockerfile` |
| Host | **any machine**: Windows PC, macOS laptop, Linux workstation, Raspberry Pi 4/5 (Raspberry Pi OS 64-bit). On the Pi the stack lives in `/srv/ispindel`, runs rootful and autostarts through `deploy/systemd/ispindel.service` | README |
| Host-side tools | `venv` + `requirements.txt` (or npm for Tailwind) - only to run `tools/` on the host or to rebuild the CSS; no conda, no `requirements-dev.txt` | `requirements.txt`, `package.json` |

## Repository layout (27.10.2026, eleventh-thirteenth session)

Dev-only extras removed: `.editorconfig`, `.gitattributes`, `scripts/publish.sh`,
`compose.dev.yaml` (merged into `compose.yaml`), `environment.yml`, `requirements-dev.txt`, and
the tools `css_check.py`, `tailwind_class_check.py`, `load_test.py`, `mqtt_watch.py`,
`serial_monitor.py`, `run_broker.sh` plus `deploy/powercycle_test.sh`. `.vscode/` and
`.clinerules/` were restored on request (their stale paths were fixed). The self-tests
(`check_requirements.py`, `ui_test.py`, `fr19_test.py`) and the simulators (`fake_spindel.py`,
`simulate.py`) stay. The Tailwind build (`npm run css`) is checked by eye/README only.

**Flat repository root** (thirteenth session). There is no `app/` wrapper any more - all code sits
at the repository root next to the entry point:

| Path | What |
| --- | --- |
| `main.py` | the Plotly Dash dashboard |
| `db.py` | PostgreSQL helper |
| `components/ui.py`, `components/charts.py` | layout components and figures |
| `mqtt_service.py` | the MQTT ingest service (was `ingest/mqtt_ingest.py`, then `app/ingest.py`) |
| `assets/` | Dash-served: `tailwind.css`, `input.pcss`, `card_state.js`, `fonts/` |
| `sql/` | `schema.sql` + `migrations/` |
| `tools/` | self-tests and simulators |
| `deploy/` | `mosquitto.conf`, `backup.sh`, `systemd/` |

`main.py` imports `from components import charts, ui`; `gunicorn main:server` (no `--chdir`),
`PYTHONPATH=/repo`, `python -u mqtt_service.py` for the ingest; the Tailwind `@source` lines are
`../main.py` and `../components/*.py`. The left-over pre-container PostgreSQL cluster `data/`
(74 MB, git-ignored) was deleted.

## Environment setup (27.10.2026 - container first, no host services)

```bash
# the whole system, one command; Podman is preferred, Docker is identical
podman machine start 2>/dev/null || true   # macOS: Podman runs in a VM
podman compose up -d --build               # db/broker/ingest/dashboard -> http://localhost:8080
podman compose exec -T dashboard python tools/simulate.py --demo --until-now   # demo data
podman compose exec -T dashboard python tools/check_requirements.py            # self-test
ISPINDEL_DASHBOARD_CMD="python main.py" podman compose up -d --build           # hot reload

# host-side tools only:
python -m venv .venv && .venv/bin/pip install -r requirements.txt
npm ci && npm run css       # only after changing Tailwind class names
```

There is no PostgreSQL cluster, no docker-compose file for the database and no conda requirement
any more: `compose.yaml` provides PostgreSQL 16 (applies `sql/schema.sql` on the first start) and
mosquitto. The old local cluster in `data/pg` (port 5433) is dead weight and can be deleted.
The database of the stack is published on `127.0.0.1:5433` (`ISPINDEL_PG_PORT` to move it) so a
`psql` on the host can look into it; `podman compose exec db psql -U ispindel -d ispindel` needs
no port at all.


## Key commands / tools in the repo

| Command | Purpose |
| --- | --- |
| `python tools/fake_spindel.py --interval 5 --count 10` | simulates an iSpindel (7 topics, SG payload) - test ingest + dashboard without hardware |
| `python tools/simulate.py [--running\|--delete]` | seeds a clearly simulated 7-day experiment (two sine functions) straight into the database |
| `python tools/simulate.py --demo [--until-now]` | seeds the 6-device demo fleet: 3 groups of two, 24 batches of 2-5 days over the four weeks around now (~9 500 rows); `--until-now` leaves the future out |
| `python tools/mqtt_watch.py [--raw] [--count 1]` | read-only MQTT watcher: "is anything arriving?" |
| `bash tools/run_broker.sh` | throwaway local `amqtt` broker on 0.0.0.0:1883 |
| `python tools/serial_monitor.py` | USB serial console for the iSpindel |
| `bash deploy/pi_setup.sh` | on the Pi: apt packages, broker config, DB, schema, config.yml |
| `npm run css` | the Tailwind **build** - one-shot, minified, writes `app/assets/tailwind.css` (what is committed/deployed) |
| `npm run watch` | Tailwind **dev mode** - `--watch --minify`, rebuilds on every change, Ctrl-C stops it (same output as `css`) |
| `python tools/css_check.py [--fix]` | is the committed `tailwind.css` still in sync with the sources? (`--fix` rebuilds it) |
| `python tools/tailwind_class_check.py` | is every class in the CSS written inside a `className`/`extra`, and nothing missing? (the class-name rule) |
| `ssh ispindel-pi 'cd ~/ispindel && bash deploy/pi_update.sh'` | deploy step 2 on the Pi: config.yml, view migration, restart both services, verify |
| `ssh ispindel-pi 'sudo systemctl restart ispindel-ingest ispindel-dashboard'` | start / stop / restart the app by hand (`start`, `stop`, `status` take the same names) |
| `ssh ispindel-pi 'journalctl -u ispindel-dashboard -n 30 --no-pager'` | why a service is down (first thing to look at) |

## Deployment facts that matter

* **The system is deployed** (20.10.2026) on the ZHAW lab Raspberry Pi `clt-lab-n-1298`:
  `160.85.142.209` (public campus address) / `clt-lab-n-1298.zhaw.ch`, repo `/home/admin/ispindel`,
  conda env `beer`, PostgreSQL 17 local, mosquitto local, gunicorn on `0.0.0.0:8080`; both units
  `enabled` with `Restart=always`. Full details in `requirements-traceability.md` -> "Deployment
  record". **Redeployed 21.10.2026** with the newest code (the Pi had still run the 20.10. 11:29
  build) - see the second deployment record; the Pi now needs `pip install` for every new
  `environment.yml` entry (that deploy failed on the missing `dash-iconify`), and the day-to-day
  start/stop commands are README section 2.7.
* **Access:** `http://clt-lab-n-1298.zhaw.ch:8080` in the campus network. From outside use the
  tunnel `ssh -L 8080:localhost:8080 admin@160.85.142.209` (NFR-02 forbids publishing it).
  A local `~/.ssh/config` alias `ispindel-pi` exists for `ssh`/`scp`/`rsync` (key-only, no
  password: `~/.ssh/rpi_1298_ed25519`).
* **SSH keys:** the Pi's `authorized_keys` holds `rpi_1298_ed25519`. The Mac's default
  `~/.ssh/id_ed25519` is passphrase-protected and is **not** installed on the Pi - always use the
  `ispindel-pi` alias or `-i ~/.ssh/rpi_1298_ed25519`.
* **Firewall:** nftables limits 8080 to `160.85.0.0/16` (22 and 1883 stay open, INPUT policy
  accept). Ruleset in README 2.6, revert with `sudo nft flush ruleset`.
* **Time:** chrony + `chrony-wait.service` (enabled) - without it the Pi's clock is days behind
  after a boot and `recorded_at` would be wrong; a reboot needs ~60 s until everything is up.
* **Database:** local development = a PostgreSQL cluster in `data/pg` on **port 5433**
  (`postgresql://ispindel:ispindel@localhost:5433/ispindel`, started with `pg_ctl -D data/pg
  -o "-p 5433 -k /tmp" -l data/pg.log start`); on the Pi the DSN uses `localhost:5432`
  (`deploy/pi_setup.sh` and `deploy/pi_update.sh` rewrite it). The Mac's `localhost:5435` is an
  **SSH tunnel to the Pi's** 5432 - it is the *production* database, so point a separate config
  (`ISPINDEL_CONFIG`) at it instead of the default one.
* **MQTT client id:** `mqtt.client_id` (laptop `ispindel-ingest-laptop`, Pi `ispindel-ingest`).
  Both hosts subscribe to the **same** broker, and mosquitto disconnects the existing client when
  a second one connects with the same id - sharing an id makes the two ingests kick each other off
  in a loop and nothing is stored.
* **Networks:** iSpindel on `iot-ZHAW`, laptop on `ZHAW` - the Pi is reachable from both
  (README 1.8); a public broker (broker.hivemq.com) is documented as the fastest cross-network test.
* **Time zone:** storage UTC, display `Europe/Zurich`. The DST change on **25.10.2026** falls
  between now and brew day - a free NFR-09 test.
* **Tailwind class discovery:** `input.pcss` does `@import "tailwindcss" source(none)` and then
  names the only source, `@source "../**/*.py"` (`app/`). Without `source(none)`, Tailwind v4
  scans the whole project (git-aware) and **every class name mentioned in prose** - `README.md`,
  `docs/`, a comment - is compiled into the shipped CSS (that is how an unused background
  utility ended up in `tailwind.css`). Class strings must be **static** (no f-strings/variables)
  for the **VS Code plugin**: the compiler reads raw text and does find a class in a variable,
  but the plugin only reads the `classRegex` shapes, so the rule is "every class string is
  written out in full inside a `className`/`extra` argument" -
  `tools/tailwind_class_check.py` enforces it. Do not name classes in comments or docstrings
  inside `app/**` or in `input.pcss` either.
* **Tailwind plugin:** `@plugin "@toolwind/corner-shape"` in `input.pcss` - v4 loads plugins from
  the CSS entry point (no `tailwind.config.js` here). It adds `corner-*` utilities for the (still
  experimental) CSS `corner-shape` property; every rounded surface uses `corner-squircle` next to
  its `rounded-*` radius, and a browser without support just ignores the property. Never put a
  `)` inside a `className=(...)` expression: the plugin's `classRegex` for that shape stops at
  the first `)` and silently loses every class behind it.
* **Dash assets:** everything in `app/assets/` is linked automatically; `input.pcss` is excluded
  via `assets_ignore=r"\.pcss$"`.
* **Security posture:** dashboard/DB/broker are campus-only, no authentication (out of scope);
  `app.run(..., use_debugger=False)` keeps the Werkzeug console off while binding to 0.0.0.0.
  `config.yml` contains the broker host - the file has a TODO to be git-ignored before moving the
  broker to a public VPS.

## Tool usage patterns (how to work in this repo)

* Never hard-code settings - add them to `config.yml` and document them in the README table.
* Change the schema only in `sql/schema.sql` (idempotent setup assumes one-shot apply) and note
  that an existing database must be migrated by hand.
* Reference the requirement ID in comments next to the implementing code (FR-xx / NFR-xx) - the
  existing code does this consistently and it feeds directly into the traceability register.
* After UI changes: `npm run css` (or the standalone Tailwind CLI on the Pi) before taking a
  screenshot / demoing.
* **Editor support** lives in `.vscode/settings.json` (committed): Tailwind is CSS-first here
  (no `tailwind.config.js`), so the extension only works when `tailwindCSS.experimental.configFile`
  names `app/assets/input.pcss` - it auto-detects `*.css` entry points only - and when
  `tailwindCSS.includeLanguages` (`python` -> html) plus `experimental.classRegex` describe the
  class strings, which sit in Python literals. Two shapes are covered (20.10.2026): a plain or
  multi-line string after `className=`/`extra=`/`labelClassName=` and a parenthesised variant
  expression. A new way of writing a class string needs a new regex there, otherwise the editor
  silently stops completing that one; `tools/tailwind_class_check.py` checks the patterns and
  the compiled CSS agree. `files.associations` opens `*.pcss` in the extension's "Tailwind CSS"
  mode, and build/watch/check are VS Code tasks in `.vscode/tasks.json`.
* **The compiled CSS is an artefact, never a source**: `app/assets/tailwind.css` is produced by
  `npm run css` and then served statically, so a class added to a `.py` file does **nothing**
  until the rebuild - check with `python tools/css_check.py [--fix]`, and the class-name rule
  with `python tools/tailwind_class_check.py`. `watch` writes the same minified file as `css`
  since 20.10.2026; before that a watch left the artefact unminified and `css_check.py` reported
  a stale CSS that was not stale. There is a third trap of the same symptom: a class name that
  **is not a class** - the device card carried `corner-es-superellipse.corner-superellipse/100`
  (two invented utilities glued by a `.` instead of a space) and `ring-blue-900` while the
  documented colour was `ring-2 ring-page`; the rebuild replaced `.ring-page` from the older
  build with nothing, so the card silently lost both (fixed 20.10.2026, activeContext). Two
  context traps that look like the same symptom:
  `group-open:*` needs an ancestor `group`, and `border-slate-200` needs `border` to have a
  width at all.

## Repository state (checked 27.10.2026, after the container migration)

* git repository, branch `main`, remote `https://github.com/osmast/ISpindel-Dashboard.git` (private,
  returns 404 unauthenticated). Still **one** commit (`82c5078 Init`, 20.10.2026); the whole
  container migration plus the previously uncommitted work sits in the working tree - commit it.
* The repository root after the simplification and flat layout (27.10.2026): `main.py`, `db.py`,
  `components/`, `mqtt_service.py`, `assets/`, `sql/`, `tools/`, `deploy/` plus `run.sh`,
  `compose.yaml`, `Dockerfile`, `config.yml`, `requirements.txt`, `package*.json`, `LICENSE`,
  `README.md`, `.dockerignore`, `.gitignore`, `.vscode/`, `.clinerules/`, `docs/`, `memory-bank/`.
  Removed: `.editorconfig`, `.gitattributes`, `scripts/`, `compose.dev.yaml`, `environment.yml`,
  `requirements-dev.txt`, the legacy `data/` cluster and the `app/` wrapper.
* `iSpindel Project _ Moodle ZHAW.html` moved to `docs/ispindel-project-moodle-export.html`;
  `deploy/pi_setup.sh`, `pi_update.sh` and `pi_powercycle_test.sh` are deleted (rsync + sed + systemd
  install are gone - `deploy/powercycle_test.sh` + `deploy/systemd/ispindel.service` replace them).
* The old 1312-line README became `docs/runbook-pre-container-setup.md`; the new `README.md` is the
  code-only run guide (quick start, containers, config, run.sh, Pi, development, troubleshooting,
  layout) and is meant to be published.
* `node_modules/`, `data/`, `deploy/backups/`, `__pycache__/`, `tailwindcss`, `config.local.yml`
  are git-ignored. There is no publish script any more (removed 27.10.2026) - if a public
  code-only release is wanted again, the allowlist has to be recreated.
* **The production Pi still runs the old bare-metal installation** (systemd `ispindel-ingest` /
  `ispindel-dashboard`, conda, apt postgres/mosquitto, `/home/admin/ispindel`, data of the
  fermentation phase). Brew day is **29.10.2026**, two days after this session, so the container
  stack was deliberately **not** rolled out there - the migration recipe is in README ("Coming from
  an older installation") and keeps `systemctl enable --now` as the rollback.
