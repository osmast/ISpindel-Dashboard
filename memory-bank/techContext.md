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
| CSS | Tailwind CSS CLI v4.3.3 (`@tailwindcss/cli`) + plugin `@toolwind/corner-shape` 0.0.8-3, source `app/assets/input.pcss` -> committed `tailwind.css` | `package.json`, `app/assets/input.pcss` |
| Fonts | IBM XGA-AI (7x15 / 12x20 / 12x23 / "12x20 Plus") from *The Ultimate Oldschool PC Font Pack v2.2* (VileR, CC BY-SA 4.0); `.woff`, page default via `@theme --font-sans`, Plotly figures via `charts.FONT_FAMILY` | `app/assets/fonts/`, `app/assets/input.pcss`, `app/components/charts.py` |
| Serial debugging | pyserial >= 3.5 | `tools/serial_monitor.py` |
| Runtime env | Miniconda environment `beer`, Python 3.12, conda-forge only | `environment.yml` |
| Host | Raspberry Pi, bare metal Raspberry Pi OS 64-bit, user `admin`, repo at `/home/admin/ispindel` | README 2.x |

## Environment setup (local, macOS)

```bash
conda env create -f environment.yml && conda activate beer
# local development database: a cluster in data/pg on port 5433 (Docker is not installed here)
initdb -D data/pg -U ispindel --auth=trust --encoding=UTF8
pg_ctl -D data/pg -o "-p 5433 -k /tmp" -l data/pg.log start
createdb -h localhost -p 5433 -U ispindel ispindel
psql postgresql://ispindel:ispindel@localhost:5433/ispindel -f sql/schema.sql
npm ci && npm run css          # only after changing Tailwind class names
python ingest/mqtt_ingest.py   # terminal 1 - subscribes to the Pi's broker, writes locally
python app/main.py             # terminal 2 -> http://localhost:8080
python tools/fake_spindel.py --interval 5 --count 10   # terminal 3, only with a local broker
```

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

## Deployment facts that matter

* **The system is deployed** (20.10.2026) on the ZHAW lab Raspberry Pi `clt-lab-n-1298`:
  `160.85.142.209` (public campus address) / `clt-lab-n-1298.zhaw.ch`, repo `/home/admin/ispindel`,
  conda env `beer`, PostgreSQL 17 local, mosquitto local, gunicorn on `0.0.0.0:8080`; both units
  `enabled` with `Restart=always`. Full details in `requirements-traceability.md` -> "Deployment
  record".
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
  a stale CSS that was not stale. Two context traps that look like the same symptom:
  `group-open:*` needs an ancestor `group`, and `border-slate-200` needs `border` to have a
  width at all.

## Repository state (checked 20.10.2026)

* git repository exists but has **no commits yet** - every file is untracked. Nothing is
  versioned, so the D3 deliverable is at risk.
* Leftover file in the repository root: `iSpindel Project _ Moodle ZHAW.html` (Moodle export,
  belongs in `docs/` or should be deleted).
* `node_modules/`, `data/`, `__pycache__/`, `tailwindcss` are git-ignored.
