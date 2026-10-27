# System Patterns (architecture and design decisions)

## End-to-end data path

```
  fermenter                                      any machine (Podman/Docker Compose - laptop or Pi)
  ----------                                     -------------------------------------------------
  iSpindel ──Wi-Fi/MQTT (QoS 0)──► MQTT broker          container `broker`  (eclipse-mosquitto:2)
                                    │ (may run off this host - NFR-01)
                                    ▼
                    ingest/mqtt_ingest.py  ──INSERT──►  PostgreSQL 16
                    (container `ingest`)                    container `db`, volume `pgdata`
                                                            │  tables: device, experiment,
                                                            │  measurement, experiment_event
                                                            │  views: v_device_latest,
                                                            │  v_experiment_overview
                                                            ▼
                    Plotly Dash + gunicorn  (container `dashboard`, 0.0.0.0:8080)
                                    │
                    browser in the local network (laptop / smartphone)
```

**One compose file** (27.10.2026, eleventh session): `compose.dev.yaml` was merged into
`compose.yaml`. The dashboard `command` is `${ISPINDEL_DASHBOARD_CMD:-gunicorn ...}`, so
`./run.sh dev` sets `ISPINDEL_DASHBOARD_CMD="python app/main.py"` for the hot-reload server.
Since the thirteenth session the repository is **flat** (no `app/` wrapper): `main.py`, `db.py`,
`components/`, `mqtt_service.py`, `assets/`, `sql/`, `tools/`, `deploy/` sit at the root.
The dashboard mounts `main.py`, `db.py`, `components/`, `assets/` and `tools/` from the working
tree, the ingest mounts `mqtt_service.py`; `config.yml`, `sql/schema.sql` and
`deploy/mosquitto.conf` are mounted too. Commands: `python -u mqtt_service.py` (ingest),
`gunicorn main:server` (dashboard, `PYTHONPATH=/repo`).

The four services live in `compose.yaml`; `ingest` and `dashboard` are the **same image** built from
the repository (`Dockerfile`) and differ only in their `command`. There is **no wrapper script**
(removed 27.10.2026): the entry points are the plain compose commands from the README
(`podman compose up -d --build` / `docker compose ...`), because they work identically in bash and
in PowerShell. Ports: 8080 published to the LAN, 1883 published to the LAN (the
iSpindel), 5433 bound to 127.0.0.1 only. `ISPINDEL_HTTP_PORT` / `ISPINDEL_PG_PORT` move the host
ports; the settings inside the container network are always the same, because compose passes
`ISPINDEL_DB_DSN=…@db:5432` and `ISPINDEL_MQTT_HOST=broker` into the app - a run on the host reads
the same `config.yml` with `localhost`. That is the whole "no per-machine configuration" trick.

Automation-pyramid assignment (needed for D1): iSpindel = field level, Raspberry Pi ingest =
control level (data acquisition only, no actuators), PostgreSQL + experiment assignment =
supervisory level / simplified MES precursor, ERP = out of scope.

## The central hardware pattern: one transmission = 7 MQTT messages

The stock firmware does **not** send JSON and **no timestamp**:

| Topic | Example payload |
| --- | --- |
| `ispindel/<name>/tilt` | `62.00` |
| `ispindel/<name>/temperature` | `20.00` |
| `ispindel/<name>/temp_units` | `C` |
| `ispindel/<name>/battery` | `4.050` |
| `ispindel/<name>/gravity` | `1.0568` |
| `ispindel/<name>/interval` | `900` |
| `ispindel/<name>/RSSI` | `-55` |

Patterns derived from that:

* **Burst assembly** (`buffer` dict keyed by device name): collect the 7 values of one
  transmission and write **one** database row (FR-11). The row is written as soon as the last
  topic (`RSSI`) arrives, so `recorded_at` stays within milliseconds of the real transmission -
  the dashboard countdown depends on it.
* **Fallbacks**: a new `tilt` also closes the previous burst (firmware always sends `tilt`
  first), and `flush_stale()` writes a burst whose remaining messages never arrived after
  `ingest.burst_seconds` (10 s). This keeps FR-11 true for **any** interval (1 min / 30 min).
* **The Raspberry Pi is the time authority**: `recorded_at` = time of receipt, ISO 8601 / UTC
  (`timestamptz`). Consequence: the Pi clock must be correct (NTP/chrony); the firmware cannot
  supply a time.
* **QoS 0, not retained**: if the broker or the Pi is down, that transmission is lost forever.
  Nothing can be recovered afterwards -> "keep the broker running" is an operational rule.
* **Unit normalisation at ingest**: `gravity_unit` (`P` or `SG`) decides whether the device
  value is already °P or must be converted (`plato_from_sg`); `temp_units` (`C`/`F`/`K`) is
  normalised to °C. The raw values plus their unit are **kept as well** (`gravity_raw`,
  `temp_raw`, `temp_unit`) for traceability (FR-08).
* **Idempotency**: `UNIQUE (device_id, recorded_at)` plus `INSERT ... ON CONFLICT DO NOTHING`
  makes a duplicated burst harmless.

## Data model (as-built, `sql/schema.sql`)

```
device (id PK, mqtt_name UNIQUE, display_name, is_active, first_seen_at)
experiment (id PK, name UNIQUE, device_id FK->device, started_at, ended_at NULL=active,
            beer_style, og_plato, yeast, responsible, notes, created_at,
            CHECK ended_at > started_at,
            EXCLUDE USING gist (device_id =, tstzrange(started_at, coalesce(ended_at,'infinity')) &&))
measurement (id PK, device_id FK, experiment_id FK NULL=unassigned, recorded_at,
             tilt_deg, temp_c, gravity_plato, battery_v, interval_s, rssi_dbm,
             gravity_raw, temp_raw, temp_unit, received_at,
             UNIQUE (device_id, recorded_at))
experiment_event (id PK, experiment_id FK ON DELETE CASCADE, occurred_at, kind, note)
views: v_device_latest (latest row per device), v_experiment_overview (experiment + ispindel +
       is_active + measurement count + last_seen_at)
```

Design decisions worth defending in the concept (D1):

* **Three linked entities** instead of one wide table (FR-12): new devices and new experiments
  need **no schema or code change**; a device row is even created automatically on first
  message (`INSERT ... ON CONFLICT`).
* **Invariants live in the database, not in the UI** - `UNIQUE(name)` = FR-02,
  `EXCLUDE USING gist` on the overlapping time range = FR-03/FR-09 (an iSpindel can never be in
  two experiments at once). The UI merely translates the resulting `UniqueViolation` /
  `ExclusionViolation` into a readable message.
* **`experiment_id IS NULL` is a meaningful state** (FR-10): measurements of a device without an
  active experiment are stored, not discarded.
* **`*_raw` columns + `temp_unit`** keep the transmitted value and allow a later re-interpretation
  if the calibration or the unit assumption was wrong.
* **Indexes match the dominant query** (`measurement(experiment_id, recorded_at)` for
  "all measurements of experiments A and B ordered by time", `measurement(device_id, recorded_at
  DESC)` for the per-device card and the latest-value view).
* **`experiment_event`** exists in the schema for FR-06 (event markers); the UI part is open.


## Dashboard patterns (`app/`)

* **Dash + Tailwind utility classes**, no extra JS framework. Layout primitives live in
  `app/components/ui.py` (card, badge, alert, button, field, table, stat, zone), figures in
  `components/charts.py` (gravity + temperature on one y axis). The batch card's three data zones
  are plain HTML built in `main.py` - no figure involved.
* **Server-side rendering per refresh**: `update_dashboard()` rebuilds the whole device grid
  (and the experiment table) from `v_device_latest` + the last `dashboard.device_chart_days`
  days of measurements. One card per iSpindel, each with its own compact chart.
* **Two speeds of refresh**: `dashboard.refresh_ms` (15 s, FR-14 << 60 s) for the grid/chart,
  `dashboard.live_ms` (1 s) for a tiny `update_nextdue` query plus a **clientside callback** that
  only subtracts the browser clock -> the countdown ticks without HTTP traffic.
* **Accordion without callbacks**: cards are native `<details>` elements, the collapsed/expanded
  differences are pure Tailwind `group-open:` variants. Opening/closing is animated in
  `app/assets/input.pcss` over the custom property `--accordion-transition-duration` (0.5 s,
  declared on `details[data-card]`): `::details-content` transitions `block-size` (to `auto`, which
  needs `interpolate-size: allow-keywords` on `:root`), `opacity` and `content-visibility` with
  `allow-discrete`. The `<summary>` stays outside that box, so the header never moves;
  `prefers-reduced-motion` disables it and an engine without `::details-content` opens instantly.
* **The row actions of the FR-05 table** (since the sixth session): every row carries the two
  analysis actions `chart` (FR-17) and `csv` (FR-21) plus `edit` (FR-06); a running row adds `end`
  (FR-04, one red stop icon that opens the FR-04 confirmation popup), a completed one adds `delete`
  (FR-06 - a batch that is still filling is not deletable). A pattern id must keep exactly the
  callback's key set, so no icon carries a device; `experiment_device()` looks the iSpindel up and
  `end_dialog(device)` builds the same popup as the card's red button.
* **The comparison-chart selection lives in a store, written by a row action** (since the sixth
  session): the experiment multi-select dropdown was removed from the chart card. The `chart` icon
  toggles the experiment id in the `chart-select` store (`toggle_chart`, guarded by `clicked()` like
  every table button), `update_chart` reads it and `update_dashboard` takes it as an `Input` so the
  icon turns blue on the click (FR-17). `update_dashboard` takes `chart-select` as an extra `Input`
  (its five outputs - the device grid, the two table bodies and the two tab labels - are unchanged).
* **The CSV export is a row action, not a button**: `csv` on a row calls the plain function
  `download_csv([id], range)` (FR-21/FR-22) from `experiment_action` and writes the file to
  `dcc.Download`; the feedback is the top-right toast, like the other row actions (no inline
  `csv-msg` div any more).
* **Experiment controls live in the device card** (since 20.10.2026): no separate start/end card.
  Lower left of a card is either a **grey** "Set up experiment" button (tone `grey`,
  `bg-slate-100` -> `hover:bg-slate-200`) or, while an experiment runs, `running experiment:
  <name>` with a **red** "End experiment" button. The card carries the numeric `device_id` in the
  button id, so the iSpindel is never picked twice (FR-03 by construction);
  `resolve_device()` still accepts a name so a bad value yields a message, not a 500.
* **The dialog is a `dmc.Modal` at page level**, outside the rebuilt device grid - a form inside a
  card would lose what the user typed every 15 s. It is closed only through its own buttons
  (`withCloseButton/closeOnClickOutside/closeOnEscape = False`), otherwise a browser-side close
  would leave Dash's `opened` at `True` and the next click would not reopen it.
* **One callback per output**: `experiment_action` handles setup/cancel/submit/end because all of
  them write `exp-modal.opened`; validation errors go to `modal-msg` (inside the dialog),
  successes to `msg` (page, as a toast). `click_values()` normalises pattern-matching clicks
  (scalar when only one card exists) - the countdown clientside callback does the same for its
  id list.
* **Never trust a pattern-matching click without checking it** (`main.clicked()`): dash-renderer
  fires a wildcard callback when the *number of matching components changes* - a rebuilt grid adds
  or removes the red end button - and that arrives with `n_clicks = 0`/`None`. The end action ran
  on that and ended an experiment the moment it was created. `clicked(triggered, ids, values)`
  maps `ctx.triggered_id` to its own click count via a `State(..., "id")` and only acts when that
  count is > 0. Both buttons (setup and end) use it.
* **Transient notices are toasts**: `#msg` is a `fixed right-0 top-0 z-50 pointer-events-none`
  container and `ui.toast()` wraps the alert with the `toast-life` animation
  (`app/assets/input.pcss`): fade in, hold, fade out after 10 s with `forwards`. Pure CSS - the
  container ignores pointer events, so the invisible leftover node cannot swallow a click, and the
  next notice replaces the children.
* **The server is told the viewport** (`viewport` store + a clientside callback on the 1 s tick):
  Plotly figures cannot react to CSS media queries, so the browser publishes
  `{"mobile": window.innerWidth < 768}` - only when the breakpoint changes, so a dragged window
  does not spam the callbacks. `update_chart` and `update_dashboard` read the store (as an Input
  for both, so a rotation re-renders the figures) and pass `mobile=True` to
  `charts.fermentation_figure()`, which drops the legend and shortens the axis
  titles to `time` / `hours` (NFR-06).
* **The times line of a card ticks in the browser**: `update_device_times` publishes the absolute
  epochs of the last measurement and the next transmission per device (a tiny query, every
  `dashboard.live_ms`) into the `device_times` store, and one clientside callback formats
  `last: 12 s ago · upcoming: in 12 s` from the browser clock - no server round trip per second.
  `times_text()` produces the same wording for the first paint.
* **Never nest a `<label>`** (`ui.field()`): `dcc.RadioItems` / `dcc.Checklist` render a
  `<label>` per option. A `<label>` inside a `<label>` is invalid HTML and the browser then
  treats the *first* radio as the outer label's control, clicking it whenever anything inside
  the label is clicked - the selection snapped back to the first option and the FR-16 time
  range never applied. `ui.field()` therefore renders a `<div>`/`<span>`.
* **One dialog, three modes** (`experiment_action`): the fields are the children of `#exp-form`,
  so the callback rebuilds them from `experiment_form(values)` whenever the dialog opens -
  `None` for a new experiment, the row's values for edit/delete. `exp-target` carries
  `{"mode": "create"|"edit"|"delete", "id": ..., "device": ...}` and decides what `exp-submit`
  does; the modal title and the primary button label are outputs, so one button serves all three.
  Everything else answers `no_update` for the form, which is what keeps what the user typed.
* **A `dmc.Tabs` shell belongs in the static layout**: a component that is *rebuilt* by a callback
  cannot be the `Input` of another callback - Dash validates every string id against the initial
  layout at startup and aborts with *"no components with that id exist in the layout"* (that is
  what `exp-tabs` did; the fix is not `suppress_callback_exceptions` but moving the shell into
  `layout()`). A Tabs that is never re-rendered also keeps the tab the user picked by itself, so
  the view needs no store - `update_dashboard()` writes the two table bodies and the two tab
  labels instead. Pattern-matching ids (dicts) are exempt from that validation.
* **Markers only while they are readable** (`charts.fermentation_figure()`): `lines+markers` up to
  200 points, `lines` above that. A 7-day simulation at 15 min would otherwise draw 673 markers of
  size 5 on top of each other and look like a different kind of chart than an 18-point one.
* **Figures are read-only** (`GRAPH_CONFIG`): `displayModeBar: False` on every `dcc.Graph`, so
  no zoom / pan / download / fullscreen toolbar - one less thing to mis-click on a phone.
* **One y axis per line plot**: `charts.fermentation_figure()` deliberately has no
  `secondary_y`. Gravity (°P) and temperature (°C) share the single left-hand scale, so no ticks
  are drawn on the right and the full width stays plot area; the temperature trace is dotted and
  slightly transparent to keep the two lines apart and the axis title carries both units.
* **Animations are CSS, and they play once**: the panels fade in through a Tailwind theme
  animation (`@theme { --animate-fade-in: ... }` + `@keyframes` in `app/assets/input.pcss`,
  used as `animate-fade-in motion-reduce:animate-none`). dash-renderer keys a component by its
  `id` (`createContainer`), so a rebuilt grid reuses the DOM node and the animation does not
  replay on every refresh - only a genuinely new element animates. Device cards add a per-`slot`
  `animationDelay` so several cards appear staggered.
* **Persisting UI state across rebuilds**: Dash keys components by `id`, otherwise by index path,
  and a remount drops `<details open>`. Fix: stable `id` per card **plus** an `open_cards` store
  (`app/assets/card_state.js` writes it via `dash_clientside.set_props`) that `update_dashboard`
  reads as a **State** (so toggling costs no round trip).
* **Config over code** (NFR-08): every setting (DSN, broker host/port/topic prefix, refresh
  times, battery thresholds, gauge ranges, history window, time zone) is read from `config.yml`;
  `ISPINDEL_CONFIG` points a component at another file.
* **Time display**: storage always UTC, display via `ZoneInfo(config.dashboard.timezone)` -
  `local()` in `app/db.py` for Python, `AT TIME ZONE` in SQL for the CSV export (NFR-09).
* **Export**: `dcc.send_string(rows_to_csv(...))` with `experiment`, `ispindel`,
  `timestamp_utc`, `timestamp_local` and the eight measurement columns (FR-21).
* **FR-19 detection** happens in `device_card()`: `stale` = never reported, or
  `age > 3 * interval_s`; `low` = `battery_v < dashboard.battery_warn_v`. `card_warnings()`
  turns each condition into one text line, `status_dot(bool(warnings))` renders **one** dot in
  the header - green while healthy, red for either condition (collapsed *and* expanded, because
  the dot is inside the `<summary>`). The reason is text and is therefore rendered only in the
  expanded half of the card; the old red "no data" badge was removed (20.10.2026).

## The "other iSpindels in use" pattern - still unresolved

FR-15 and T-02 require **all iSpindels in use during the fermentation phase** in one dashboard.
The stock firmware hard-codes the topic prefix `ispindel/<name>/...`, and the course devices may
publish to **different brokers**. Open options:

1. everyone points their iSpindel at the same broker (e.g. the lab Pi / the own Pi) - the client
   provides the details on brew day,
2. run an **MQTT bridge** on the Pi (`mosquitto` bridge to the other brokers/hosts),
3. subscribe the ingest to several brokers (one client per broker -> needs a code change).

Current state: `app/main.py` contains `DEV_REPEAT = 6` - a **development-only** block that repeats
the first device card six times so the grid can be judged. It must be set back to `1` before the
acceptance test.

## Operational patterns (README chapter 2)

* `deploy/pi_setup.sh`: idempotent one-shot setup - apt packages (mosquitto, postgresql, chrony),
  broker config with `listener 1883 0.0.0.0` + a verification of the listener, PostgreSQL role /
  database, schema, `config.yml` patched to local host + port 5432.
* `deploy/pi_update.sh`: update an existing installation - adapt `config.yml`, apply the view
  migration, restart both services, verify them (used for the 20.10.2026 deployment).
* `deploy/pi_powercycle_test.sh`: T-07 from the laptop - reboot, wait for SSH, wait 60 s, then check
  services, row count, boot order and firewall (writes `/tmp/pi_reboot.log`).
* `deploy/mosquitto.conf`: minimal LAN broker config for testing.
* systemd unit `ispindel.service` (repository `deploy/systemd/`) = `podman compose up -d`, enabled
  in `multi-user.target` with `Wants=/After=network-online.target time-sync.target` -> NFR-03. It is
  the boot step because **rootless Podman has no daemon** that could restore `restart:` policies
  (Docker does that by itself; `podman-restart.service` is the rootful alternative). `time-sync.target`
  replaces the old `chrony-wait.service`: the Pi has no RTC, so the clock is days behind at boot and
  `recorded_at` would be stamped wrong (FR-08/NFR-09).
* `deploy/systemd/ispindel-backup.{service,timer}`: nightly `pg_dump` via `deploy/backup.sh` into
  `/var/backups/ispindel`, 14 days retention (NFR-04); the script verifies the dump is not empty
  before it keeps it.
* The old nftables ruleset (8080 only from `160.85.0.0/16`) belonged to the bare-metal Pi and is not
  part of the repository - README says plainly that the dashboard has no authentication and must stay
  inside the local network.
* Tailwind: `app/assets/input.pcss` -> `app/assets/tailwind.css` (committed, served by Dash) via
  Tailwind CLI v4.3.3; `.pcss` is kept off Dash's stylesheet list with `assets_ignore=r"\.pcss$"`.
  The source switches automatic source detection off (`@import "tailwindcss" source(none)`) and
  scans only `@source "../**/*.py"`, so the CSS holds exactly the classes the UI uses - not every
  class name that happens to be *mentioned* in `README.md`, `docs/` or a comment. The built file
  is an **artefact**, not a source: a class added to the Python code does nothing until the CSS is
  rebuilt (`npm run css`; dev mode `npm run watch` writes the same minified file) -
  `python tools/css_check.py [--fix]` compares a fresh build with the committed one, so a stale
  build is detected instead of showing up as "my class does nothing".
* **Tailwind class-name rule:** every class string is written out in full inside a
  `className`/`extra` argument - no lookup table, no f-string, no `"bg-" + tone`. The compiler
  reads raw file text and would find a class in a variable; the VS Code plugin would not, and a
  reader cannot either. `python tools/tailwind_class_check.py` fails if a compiled class comes
  from anywhere else, or if a `className` names a class the compiled CSS does not have. Variant
  classes also depend on their context (`group-open:*` needs an ancestor `group`,
  `border-slate-200` needs `border`), and the plugin `@plugin "@toolwind/corner-shape"` (loaded
  from the CSS entry point, v4 style) adds the `corner-*` utilities - every rounded surface uses
  `corner-squircle` next to its `rounded-*`.
* **Schema changes**: `sql/schema.sql` is for a fresh database; an existing one gets a file in
  `sql/migrations/` (`CREATE OR REPLACE VIEW` may only append columns - see the FR-01 migration).
* **Deployment = the compose stack, on every machine** (27.10.2026): `git clone` + `./run.sh up`
  builds the image and starts `db`, `broker`, `ingest`, `dashboard`; `./run.sh down` stops them and
  keeps the `pgdata` volume. There is no rsync, no `sed` rewriting of `config.yml`, no host package
  installation and no second configuration file any more - the old flow (rsync excluding
  `config.yml` + `pi_update.sh` converting the laptop config into a Pi config) is exactly what the
  container migration removed. `scripts/publish.sh` exports the code-only tree for a public
  repository (allowlist + deny check: `docs/`, `memory-bank/`, `data/`, `node_modules/` must not be
  in it).
