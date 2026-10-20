# Requirements Traceability / Design Requirements Register

Purpose: **one line per requirement, with evidence, current status and the concrete gap** - so that
nothing the client demands (Must) or expects (Should) or offers as an option (Could) gets lost.
Requirement text: `requirements.md` (verbatim) / `docs/iSpindel-project.md`.

## How to read it

| Status | Meaning |
| --- | --- |
| **MET** | acceptance criterion demonstrably fulfilled (verified in code and/or with the fake iSpindel) |
| **PARTIAL** | implemented but not yet fully covering the requirement/acceptance criterion |
| **PENDING-VERIFY** | implemented/documented, but the acceptance criterion needs a test that has not run yet (Pi, real device, third person, smartphone) |
| **OPEN** | not implemented |
| **N/A** | not applicable to this system |

Legend for the "evidence" column: `main.py:155` = `app/main.py` line 155, `ingest:132` =
`ingest/mqtt_ingest.py` line 132, `schema:39` = `sql/schema.sql` line 39.

## Scoreboard (20.10.2026, after the deployment on the Raspberry Pi)

| Group | Must | Should | Could | Must MET | Must PARTIAL / PENDING-VERIFY | Should / Could OPEN |
| --- | --- | --- | --- | --- | --- | --- |
| 3.1 Experiment management (FR-01 - FR-06) | 5 | 1 | - | **5** (01-05) | 0 | FR-06 (events half) |
| 3.2 Data acquisition (FR-07 - FR-12) | 5 | 1 | - | **5** (07, 08, 09, 11, 12) | 0 | - |
| 3.3 Dashboard (FR-13 - FR-20) | 5 | 2 | 1 | 4 (13, 14, 16, 17) | 1 (FR-15 other iSpindels) | - (FR-20 done 20.10.2026) |
| 3.4 Export (FR-21 - FR-22) | 1 | 1 | - | **1** (21) | 0 | - |
| 3.5 Non-functional (NFR-01 - NFR-09) | 6 | 3 | - | 4 (01, 02, 03, 04) | 2 (NFR-05 person test, NFR-08 third-person install) | - |
| **Total (31 requirements)** | **22** | **8** | **1** | **19** | **3** | **1 (FR-06)** |

Verified on the deployed Raspberry Pi on 20.10.2026 (see "Deployment record" below): the updated
build runs under systemd, the real iSpindel `dfp_os_01` feeds it, a power cycle loses no data,
the dashboard is reachable by host name and closed to the internet, a full refresh with
fermentation-phase volume takes 1.3 s and every check of `tools/check_requirements.py` passes.

Remaining: **FR-15** (the other iSpindels of the course must reach this broker - a client
decision), **NFR-05** (a person who has never seen the dashboard), **NFR-08** (a second person
installs from the README), plus the Should items FR-06, NFR-06 and NFR-09 (DST). **FR-20** (the
Could) was closed on 20.10.2026 with the batch zones - the formulas are in `docs/concept.md`.

## 3.1 Experiment Management

| ID | Prio | Requirement (short) | Evidence | Status | Gap / next action | Verify |
| --- | --- | --- | --- | --- | --- | --- |
| FR-01 | Must | create + start an experiment via dashboard; required: name, start date/time, iSpindel; optional in the form: beer style, original gravity (°P), yeast, responsible, notes | **dialog on the device card** (lower left, grey "Set up experiment" button) with name + start + the 5 optional fields; the iSpindel comes from the card (`device_id` in the button id); `create_experiment()` validates and inserts, `schema:23-27` columns | **MET** | verified live and by `tools/ui_test.py` (23 checks): fields stored, `NULL` when empty, invalid OG rejected inside the dialog, start with required fields only | T-01 + `tools/ui_test.py` |
| FR-02 | Must | unique experiment name, clear error message | `schema:19` UNIQUE, `create_experiment()` UniqueViolation -> red alert | **MET** | verified live (duplicate name -> message, no row) | T-01 + checker |
| FR-03 | Must | one iSpindel per experiment, at most one active experiment per iSpindel | `schema:31-34` EXCLUDE USING gist, ExclusionViolation -> red alert; **the UI cannot even attempt it**: a card with a running experiment shows the red end button instead of the setup button | **MET** | rejection proven at the data layer (`tools/check_requirements.py`) and by design in the UI; the exclusion constraint fired for real once (a load-test helper) | T-01 + checker |
| FR-04 | Must | end an active experiment via dashboard, store end time, no further assignment | red **End experiment** button on the card of the running experiment (`end_experiment()`, `UPDATE ... SET ended_at = now()`), `ingest:61-64` `e.ended_at IS NULL` in the assignment join; **an action of a running FR-05 row** too (red stop icon -> same confirmation popup, `row_actions(mode="end")` + `experiment_device()`), alongside `chart`/`csv`/`edit` | **MET** | verified live and by `tools/ui_test.py`: only the running experiment's card offers the button, `ended_at` set, the ingest predicate matches no experiment afterwards; ending twice says "no running experiment" | T-01 + `tools/ui_test.py` |
| FR-05 | Must | overview of all experiments: name, iSpindel, start, end, status, number of measurements | `schema:81-93` v_experiment_overview (the six FR-05 columns plus the FR-01 optional fields), `experiment_table()` - split into the `Running (n)` / `Completed (n)` tabs, `Actions` column per row state, panel without a heading line | **MET** | all six required columns intact, extended as a subset - verified live; the action column is covered by `tools/check_requirements.py` and `tools/ui_test.py` | T-01 + checker |
| FR-06 | Should | complete/edit experiment fields afterwards; timestamped events shown as markers in the chart | **edit half done**: `update_experiment()` + the pencil icon of the FR-05 table (`row_actions(mode="edit")` on **every** row - running and completed, since a running experiment can be corrected while it runs), the dialog rebuilt from `experiment_form(values)` with a mode-dependent title/button; **events**: `schema:59-65` experiment_event table only | **PARTIAL** | the events half is still open: event insert + `add_vline`/annotations in `charts.fermentation_figure()` | `tools/ui_test.py` (edit incl. a running row, duplicate name refused, delete) |

## 3.2 Data Acquisition and Storage

| ID | Prio | Requirement (short) | Evidence | Status | Gap / next action | Verify |
| --- | --- | --- | --- | --- | --- | --- |
| FR-07 | Must | receive all iSpindels in use via MQTT automatically | `ingest:37` topic `ispindel/+/+`, `ingest:116` subscribe, `ingest:181-201` loop, `ingest:119-121` auto reconnect | **MET (own device) / PARTIAL (others)** | live: real `dfp_os_01` writes 2 rows/min at a 30 s interval; the *other* iSpindels of the course do not reach this broker yet | T-02 |
| FR-08 | Must | store every measurement with at least the listed fields and units | `ingest:48-67` INSERT, `ingest:70-81` SG->°P + °C normalisation, `schema:39-55` all fields + raw values, `ingest` unit from `config.yml:26` | **MET** | verify the unit matches the device's calibration polynomial | T-02 |
| FR-09 | Must | automatic assignment to the experiment active at the time of receipt, never to two | `ingest:61-64` LEFT JOIN on `device_id` + `ended_at IS NULL` + `started_at <= recorded_at`, `schema:31-34` prevents overlap | **MET** | - | T-02 |
| FR-10 | Should | measurements without an active experiment are stored unassigned | `schema:42` nullable `experiment_id`, `ingest:61-64` LEFT JOIN keeps the row | **MET** | - | SQL query |
| FR-11 | Must | no fixed interval assumed, exactly one record per transmission, no duplicates | `ingest:42` BURST_FIELDS, `ingest:147-170` burst assembly + write on last topic, `ingest:173-178` flush_stale, `schema:54` UNIQUE(device_id, recorded_at), `ingest:65` ON CONFLICT DO NOTHING | **MET** | live data: 190+ rows, 0 duplicate `(device_id, recorded_at)`, exactly 2 rows per minute at a 30 s interval | T-03 + checker |
| FR-12 | Must | separated entities (tables + keys), new iSpindels/experiments without schema or code change; data model diagram in the concept | `schema:9-65` device/experiment/measurement/experiment_event + FKs, `ingest:49-53` device auto-created, **`docs/concept.md` section 2** (Mermaid ER diagram); **the Devices table** (`device_rows/device_table`, FR-12) now also *shows* the master data (MQTT name, display name, in-use flag, first seen, last measurement, reported interval, measurement count) and **manages** it via the settings dialog (`device_form`, `update_device`) | **MET** | - | D1 review + `tools/check_requirements.py` (Devices table) + `tools/ui_test.py` (settings dialog) |

## 3.3 Dashboard and Visualisation

| ID | Prio | Requirement (short) | Evidence | Status | Gap / next action | Verify |
| --- | --- | --- | --- | --- | --- | --- |
| FR-13 | Must | per active iSpindel: latest gravity, temperature, tilt, battery + time of the last measurement | `main.py` `ispindel_overview()` + `device_card()` (batch name + `beer_style`, status chip, header gravity/temp/`Bat: x %`, the three **data zones**, `tilt / RSSI / interval` line, "last measurement" line), `schema:69-79` v_device_latest | **MET** | live check: DB `3.801 V -> 56 %`, `tilt 96.58°`, `RSSI -77`, `interval 30 s` are exactly what the card shows; the card of the newest running batch carries all three zones | T-04 |
| FR-14 | Must | gravity + temperature chart over time, auto-update without reload, <= 60 s after receipt | `main.py:89` dcc.Interval(tick, REFRESH=15000 ms from `config.yml:34`), `main.py:472-486` chart callback, `main.py:130-136` grid/table rebuild | **MET** | measured on the Pi: ingest lag avg **57 ms** / max 102 ms over 113 rows, refresh 15 s -> worst case ~15.1 s; a measurement stored at 11:16:33 was the last chart point in the very next callback | T-04 |
| FR-15 | Must | all iSpindels in use at the same time, clearly distinguishable | `main.py:155-186` one card per device, `charts.py:5` PALETTE, `main.py:101` multi-select comparison chart; `DEV_REPEAT = 1` | **PARTIAL** | only `dfp_os_01` publishes to this broker so far - the other course iSpindels must be pointed here (or bridged); the comparison chart itself is proven with 2 experiments (1920 synthetic rows) | T-02 |
| FR-16 | Must | any experiment incl. completed ones, over its entire duration; **selectable time range** (24 h / 7 d / entire) | `main.py:107-112` range RadioItems, `main.py:33-36` RANGES + RANGE_FILTER, `main.py:486` filter in the chart query, `main.py` `chart_window()` + `charts.py` `fermentation_figure(x_range=...)` pin the x axis to the whole selected window (seventh session) | **MET** | verified live: with a synthetic 3-day-old row `entire experiment` = 84 points vs `last 24 h` = 83, both equal to SQL; and the axis keeps the empty days: 3 days of data -> `7d` axis 7.00 d vs data 3.00 d, `all` autoscaled, FR-18 `rel` never pinned | T-05 + checker |
| FR-17 | Must | at least two experiments overlaid in one chart | the `chart` action of an FR-05 row (`row_actions(mode="chart")` -> `toggle_chart` -> the `chart-select` store; blue icon while shown), `update_chart` reads the store, series per experiment; **the multi-select dropdown was replaced by these row actions on 20.10.2026** | **MET** | - | T-05 |
| FR-18 | Should | switch the time axis to relative time (hours since the start) for comparisons | `main.py:79-82` RadioItems absolute/relative, `charts.py:19-28` x = hours since the first point | **MET** | - | T-05 |
| FR-19 | Should | indicate no data for more than three intervals, and battery below a configurable threshold | `main.py` `device_card()` `stale = age is None or age > 3 * interval_s`, `low = volts < BATTERY_WARN` (`config.yml`), `card_warnings()` -> one text line per condition, `status_dot(bool(warnings))` -> **one** dot in the header: green healthy / red for either condition, visible collapsed *and* expanded; the "no data" badge is gone | **MET (logic) / PENDING-VERIFY** | switch the iSpindel off, or raise `battery_warn_v`, during the test | T-04 area |
| FR-20 | Could | derived values (apparent attenuation, ABV, gravity drop / 24 h) | `main.py` `target_fg()`, `attenuation_percent()`, `abv_percent()`, `gravity_rate()`, `target_temp_range()`, `temp_hint()` + the three `ui.zone()` blocks of `device_card()`; settings `dashboard.expected_attenuation` / `target_temp_c` | **MET** | formulas written out in `docs/concept.md` section 4; live check on the `SIM_B2` batch: OG 13.35 °P -> target FG 2.67 °P, attenuation 54.7 %, ABV 4.0 %, est. final 5.7 %, rate -2.0 °P/24h, `Hefeweizen` -> 18.0-22.0 °C with `✓ in range` - every number recomputed independently by `tools/check_requirements.py` | T-04 + checker |

## 3.4 Data Access and Export

| ID | Prio | Requirement (short) | Evidence | Status | Gap / next action | Verify |
| --- | --- | --- | --- | --- | --- | --- |
| FR-21 | Must | CSV download of a selected experiment; experiment + iSpindel name in data or file name; opens correctly in Excel | the `csv` action of an FR-05 row -> `download_csv([id], range)` (plain function, called by `experiment_action`), `db.py:40-45` csv.DictWriter, filename = `<experiment>.csv`; feedback in the top-right toast; **column table documented in README section 1.9** (required by chapter 3.4) | **MET** | verified live: header + one line per measurement matching the SQL count; `tools/ui_test.py` exports a running row | T-06 + checker |
| FR-22 | Should | several experiments and/or a selected time range in one file | the same `RANGE_FILTER` in `download_csv()` -> every row export honours the selected FR-16 range; `download_csv()` still accepts a list of ids and writes `experiments.csv` for several | **PARTIAL** | the time-range half is MET (live: `entire experiment` = all lines vs `last 24 h` = fewer, exactly the selection); **since 20.10.2026 the export is a per-row action, so "several experiments in one file" is no longer reachable from the UI** - the function still supports it, a multi-select export trigger would restore it | T-06 + checker |

## 3.5 Non-functional Requirements

| ID | Prio | Requirement (short) | Evidence | Status | Gap / next action | Verify |
| --- | --- | --- | --- | --- | --- | --- |
| NFR-01 | Must | application + database + web server on the Pi, all data stored there (broker may be elsewhere) | deployed 20.10.2026: `ispindel-dashboard` (gunicorn `main:server -b 0.0.0.0:8080`) and `ispindel-ingest` as systemd services, PostgreSQL 17 local on `127.0.0.1:5432`, mosquitto local; repository at `/home/admin/ispindel`, conda env `beer` | **MET** | everything except the broker could even run off the Pi; no external hosting or external database in use | `systemctl status`, DB on the Pi |
| NFR-02 | Must | dashboard reachable in the LAN via http://hostname:port, not published to the internet | `config.yml:32-33` host 0.0.0.0 / port 8080; `http://clt-lab-n-1298.zhaw.ch:8080` (200 in 28 ms) and `http://clt-lab-n-1298:8080` (200) from the laptop; **nftables** (`/etc/nftables.conf`, enabled) limits 8080 to `160.85.0.0/16`, keeps 22/1883 open, INPUT policy accept | **MET** | the lab Pi has a publicly routable address (160.85.142.209) and the dashboard has no authentication - the host firewall (README 2.6) is what keeps it off the internet; access from outside the campus goes through `ssh -L 8080:localhost:8080` | T-08 |
| NFR-03 | Must | after restart/power failure all services start automatically, acquisition resumes, history visible | systemd units with `Restart=always` + `After=network-online.target chrony-wait.service postgresql.service mosquitto.service`; **two power cycles executed on 20.10.2026**: SSH back after 24 s, all seven services (`ssh mosquitto postgresql ispindel-ingest ispindel-dashboard nftables chrony`) active after ~60 s; `systemctl kill -s SIGKILL ispindel-dashboard` -> systemd restarted it (`NRestarts=2`) and the dashboard answered 200 again | **MET** | the ~60 s boot (Wi-Fi + NTP + chained services) is worth knowing when judging "runs again" | T-07 |
| NFR-04 | Must | no measurement lost on restart; backup procedure in the README | power cycle: **209 rows before = 209 after**; the ingest reconnected at 11:15:06 and kept writing; `pg_dump -Fc` executed on the Pi -> `~/backups/ispindel-2026-10-20.dump` (README 2.4 documents cron + restore) | **MET** | the transmissions during the ~1 min boot are lost (QoS 0, assumption A4) - not a data loss of stored rows | T-07 |
| NFR-05 | Must | operable by a non-programmer after a short introduction, UI in English | `app/components/ui.py` + `app/main.py` all labels English, `ui.alert` feedback for every action, export now reports what it wrote, `docs/concept.md` explanations; no code/DB access needed | **PENDING-VERIFY** | have a test person create/display/export an experiment unaided; the remaining UX risk is the free-text start field (`2026-11-12T16:30`) | manual |
| NFR-06 | Should | usable on a smartphone browser | Tailwind responsive classes + `dmc.Grid` spans (`main.py:182-185`, `main.py:309-318`), `config.yml`-driven sizes; README 1.9 documents the layout | **PENDING-VERIFY** | walk through all Must functions on a phone (dropdowns are the risk) | manual |
| NFR-07 | Should | a complete experiment renders in < 5 s, also with several iSpindels | load test on the Pi 20.10.2026 with 1920 synthetic measurements (2 experiments x 10 days at a 15 min interval): device cards 642 ms, experiment table 50 ms, comparison chart (entire duration) 203 ms, relative axis 272 ms, CSV export 142 ms -> **full refresh 1310 ms** (limit 5000 ms); chart query `Execution Time 0.274 ms` with the index on `(experiment_id, recorded_at)` | **MET** | measured at fermentation-phase volume; downsampling (`date_bin`) is still the answer if a multi-year dataset ever gets slow | load test (see below) |
| NFR-08 | Must | README installs a fresh Raspberry Pi OS to a running system; settings in a config file, not in code | README sections 1-4 + `deploy/pi_setup.sh` + the systemd units were **followed on the real Pi on 20.10.2026**; two gaps found and fixed: `dash-mantine-components` was missing in the conda env (added, `environment.yml` already listed it) and the units did not wait for the clock (`chrony-wait.service` added, README 2.3 updated); firewall documented in README 2.6 | **PARTIAL** | a *second* person should still walk through it (the acceptance criterion); the README now matches the deployed state | third-person install |
| NFR-09 | Should | timestamps stored in UTC, displayed in Europe/Zurich, correct across the DST change | `schema:43` timestamptz, `db.py:14/35-37` ZoneInfo + `local()`, `main.py:509-512` `AT TIME ZONE` in the export, `config.yml:42` timezone | **PARTIAL (verified UTC/local live)** | live check: stored `07:24 UTC` shows as `09:24` local (+2 h CEST) in chart, table and CSV; the **DST change on 25.10.2026** is still to be observed; the Pi has no RTC, so the units now wait for `chrony-wait` before stamping data | manual on 25.10.2026 |

## Acceptance test coverage

| Test | Requirements | Ready? | What is missing before the test passes |
| --- | --- | --- | --- |
| T-01 | FR-01 - FR-05 | **yes** | nothing - `tools/ui_test.py` drives the card button, the dialog, cancel and end through real Dash requests; `tools/check_requirements.py` covers FR-02/FR-03 at the data layer. Note: FR-03's "assign an iSpindel already in use" can no longer be triggered from the UI (the card of a running experiment shows the end button instead) - the rejection is demonstrated via the checker/DB, the UI prevents it by design |
| T-02 | FR-07 - FR-09, FR-15 | no | the other iSpindels in use must actually reach this system (broker decision); the own device already reports |
| T-03 | FR-11 | mostly | run the real device at 60 s and 1800 s; the 30 s case is verified live |
| T-04 | FR-13, FR-14 | almost | only the stopwatch proof for the 60 s limit |
| T-05 | FR-16, FR-17 | almost | the time range is done; needs two experiments (one completed) to compare |
| T-06 | FR-21 | **yes** | open the CSV in Excel once and compare the columns with the README table |
| T-07 | NFR-03, NFR-04 | no | deploy + systemd units on the Pi, then the power-cycle test |
| T-08 | NFR-02 | no | deploy + host name access from a second device |

## Deliverable readiness (D1 - D4)

| ID | Status | Missing |
| --- | --- | --- |
| D1 Concept | **draft exists** (`docs/concept.md`: architecture + automation-pyramid table, Mermaid ER data model, technology choice with alternatives, assumptions A1-A8, open client questions) | review/shorten to the 1-2 pages the client asked for; the two brewmaster questions are still open |
| D2 Running system | partially | runs locally with real device data; **Pi deployment** + fermentation-phase data missing |
| D3 Source code | exists (README, config, code, deploy scripts, `tools/check_requirements.py`) | **git commits** (repo has none), remove the leftover Moodle HTML from the repository root, strip the `config.yml` question (broker host committed) |
| D4 Presentation | not started | 15 min structure along concept / live system / interpretation / outlook, live demo rehearsal, the two brewmaster questions |

## Additional findings from the code review

Status of the findings from the first pass (20.10.2026):

| # | Finding | Status |
| --- | --- | --- |
| 1 | **FR-19 edge case**: `stale = age is None or (bool(interval_s) and age > 3 * interval_s)` (`main.py` `device_card()`) - a device that reports with `interval_s = NULL` (a burst whose `interval` topic was lost and was written by `flush_stale`) can never get the red FR-19 dot. | **open** - fall back to a configured default interval when `interval_s` is NULL (Should-level) |
| 2 | **FR-21 / NFR-05 feedback**: "Download CSV" without a selection returned `dash.no_update` - no hint for the user. | **fixed** (`csv-msg` alert, verified) |
| 3 | **FR-01 / NFR-05 UX risk**: the start time is a free text field (`2026-11-12T16:30`). | **open** - a `dmc.DateTimePicker` or a "now" checkbox would remove the typing risk; the format is validated and explained in the label |
| 4 | **FR-15 cosmetics**: `DEV_REPEAT` repeated one device for layout tests. | **fixed** (`DEV_REPEAT = 1`) |
| 5 | **Time authority**: `recorded_at` is the time of the **first** message of the burst (`tilt`), not of the last (`ingest:101`). | by design - keep it; the countdown targets `recorded_at + interval_s` |
| 6 | **FR-08 traceability**: a later change of `ingest.gravity_unit` re-interprets only new rows. | documented as assumption A2 in `docs/concept.md` |
| 7 | **NFR-08 assumption**: the systemd units assume user `admin` and `/home/admin/ispindel`. | **documented** in README 2.3 (still has to be checked on the real Pi) |

New observations from the live data (20.10.2026):

* The device `dfp_os_01` reports **~30 °P** (tilt ~96°): the stock polynomial on an **uncalibrated**
  device. Not a code problem (the raw value and the unit are stored), but it must be explained in
  the presentation. Since 20.10.2026 the batch card shows it as `0.0% Atten` / `0.0% ABV` (the
  derived values are clamped at 0 because a batch cannot gain extract) - the *reading* itself stays
  visible in the gravity zone, which is where the explanation belongs.
* `max(received_at - recorded_at)` is a few milliseconds for complete bursts; single rows show
  ~10 s - the `flush_stale` path (a burst whose last topic never arrived). `recorded_at` stays the
  burst start, so the countdown is unaffected.
* The dev dashboard shows the Plotly/Dash debug toolbar because `app/main.py` runs with
  `debug=True`; gunicorn on the Pi does not.

## Deployment record (20.10.2026) - the system as it runs on the Pi

| Item | Value |
| --- | --- |
| Host | `clt-lab-n-1298` (ZHAW lab Raspberry Pi, Raspberry Pi OS, aarch64), reachable as `160.85.142.209` (campus IP) and `clt-lab-n-1298.zhaw.ch` |
| Repository | `/home/admin/ispindel` (updated with `rsync` from the Mac; previously an 16.10. snapshot) |
| Python | Miniconda env `beer` (`~/miniconda3/envs/beer`), Python 3.12.15, dash 4.4.1, plotly 7.1.0, **dash-mantine-components 2.8.0** (had to be installed on 20.10.2026) |
| Database | PostgreSQL 17, cluster `main` on `127.0.0.1:5432`, role/database `ispindel` |
| Broker | mosquitto on `0.0.0.0:1883`, anonymous, no bridge; the iSpindel `dfp_os_01` publishes 7 topics per transmission |
| Services | `ispindel-ingest`, `ispindel-dashboard` (gunicorn `main:server -b 0.0.0.0:8080`), both `enabled` + `Restart=always`, ordered after `network-online.target` and `chrony-wait.service` |
| Time | chrony (NTP) + `chrony-wait.service` enabled: the Pi has no RTC, so without it the clock is days behind after a boot and `recorded_at` would be wrong |
| Firewall | nftables (`/etc/nftables.conf`, service enabled): 8080 only from `160.85.0.0/16`, 22 + 1883 open, INPUT policy accept |
| Access | `http://clt-lab-n-1298.zhaw.ch:8080` (campus network); from outside via `ssh -L 8080:localhost:8080` |
| Backup before the update | `~/ispindel-pre-deploy/ispindel-repo-2026-10-20_1110.tgz` and `~/backups/ispindel-2026-10-20.dump` (pg_dump -Fc) |

Steps performed: rsync the current repository -> adapt `config.yml` (DSN port 5432, `mqtt.host`
localhost) -> apply `sql/migrations/2026-10-20_view_experiment_overview_fr01.sql` -> restart both
services -> `tools/check_requirements.py` (all PASS on live data) -> load test -> power cycle.

Measured on the Pi that day:

* `tools/check_requirements.py`: **ALL PASS** (24 checks) against the production database
* full dashboard refresh with 1920 synthetic measurements: **1310 ms** (NFR-07 limit 5000 ms)
* ingest lag over one hour: average **57 ms**, maximum **102 ms** (single bursts that lost their
  last topic go through `flush_stale` and add up to 10 s, `recorded_at` stays the burst start)
* power cycle: 213 rows before -> **all rows kept**, services active ~60 s after the boot,
  `systemctl kill -s SIGKILL ispindel-dashboard` -> restarted automatically (NRestarts=2)
* data gap during the reboot: the transmissions between 11:14:05 and 11:15:06 are missing
  (QoS 0 without retain, assumption A4) - about one minute of a ~15 min interval

Note for the working setup on the Mac: `localhost:5435` is an **SSH tunnel into the Pi's
PostgreSQL** (`ssh -L 5435:127.0.0.1:5432`) and `localhost:8080` is the **Mac's own dev server**
reading that database. Both work against the production data, so a `zz_validation*` or load-test
record created locally also lands on the Pi - `tools/check_requirements.py` and
`tools/load_test.py` clean up after themselves.

## Prioritised action list (Must first)

1. **git init + first commit** of the current state (protects D3 immediately) - still open, and the
   only remaining action that needs no hardware at all.
2. **Pi session** (NFR-01 - NFR-04, the last six unproven Must items): `deploy/pi_setup.sh`,
   systemd units, Tailwind build, then T-03 at 60 s and 1800 s, T-04 stopwatch, T-07 power cycle,
   T-08 LAN access, NFR-05 walk-through by a second person, NFR-06 on a phone.
3. **FR-15 / T-02**: settle how the other iSpindels reach the broker (one shared broker, a
   mosquitto bridge, or a second subscription in the ingest) - the only Must that depends on a
   third party.
4. **FR-06** (Should): edit/complete experiment fields + events rendered as markers.
5. **NFR-07 / FR-19 edge / NFR-05 picker** (Should / follow-ups): `date_bin` downsampling, default
   interval for a `NULL` `interval_s`, and the date/time picker.
6. ~~**FR-20** (Could): attenuation / ABV / gravity drop per 24 h, formula explained in the
   concept.~~ **done 20.10.2026** - the batch zones show all of them, `docs/concept.md` section 4
   holds the formulas, `tools/check_requirements.py` recomputes them.
7. **D1** polish (shorten to 1-2 pages, add the two brewmaster questions), **D4** preparation,
   and the leftover `iSpindel Project _ Moodle ZHAW.html` in the repository root.
