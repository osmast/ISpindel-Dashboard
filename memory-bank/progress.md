# Progress

_Status checked on 20.10.2026 against the requirement specification (see
`requirements-traceability.md` for the per-requirement evidence)._

## Summary

| Area | Status |
| --- | --- |
| Data acquisition (FR-07 - FR-12) | **all 5 Must MET** - live data from the real `dfp_os_01` on the deployed Pi, one row per transmission, no duplicates |
| Experiment management (FR-01 - FR-05) | **all 5 Must MET** - optional fields added and verified live |
| Dashboard (FR-13 - FR-20) | 4 of 5 Must MET (FR-13/14/16/17); FR-15 waits for the other iSpindels |
| Export (FR-21) | **MET** + the column structure is documented; FR-22 MET as well |
| Non-functional (NFR-01 - NFR-09) | **NFR-01 - NFR-04 MET on the Pi** (deployment, host name, power cycles, no data loss); NFR-07 measured (1.31 s); NFR-09 verified for UTC/local, DST still open |
| Should: FR-06 (edit half done, events open), NFR-06 | open; FR-10, FR-18, FR-19, FR-22, NFR-07 met |
| Could: FR-20 | **MET** (20.10.2026, eighth session): the batch zones show attenuation, ABV, the target FG, the 24 h rate and the temperature target |
| Deliverables | D1 draft (`docs/concept.md`), **D2 running on the Pi with real data**, D3 complete but uncommitted, D4 to prepare |

Count: **31 requirements - 22 Must (19 proven, 3 left: FR-15, NFR-05, NFR-08), 8 Should (5 met,
1 open, 2 pending), 1 Could (met).** See `requirements-traceability.md` for the line-by-line
scoreboard and the "Deployment record" section for the state of the Pi.

## What works (verified)

* **Whole MQTT chain without hardware**: `tools/fake_spindel.py` publishes the 7 topics, the
  ingest assembles them and writes exactly one row per transmission (FR-11).
* **Unit handling**: SG -> °P conversion and °C normalisation with the raw values kept
  (`gravity_raw`, `temp_raw`, `temp_unit`).
* **Assignment**: measurements are attached to the experiment that is active for the device at
  `recorded_at`; without an active experiment `experiment_id` stays NULL instead of dropping the
  value (FR-09, FR-10).
* **DB-enforced invariants**: duplicate experiment name -> clean error message (FR-02);
  iSpindel already in an active experiment -> rejection by the exclusion constraint, translated
  into a message (FR-03); ending an experiment stops the assignment (FR-04).
* **Dashboard**: iSpindel overview (one collapsible **batch card** per device with the three data
  zones - gravity, temperature, attenuation & ABV -, battery %, own fermentation chart, last
  measurement + countdown + status dot), experiment
  table with status, measurement count and per-row actions (chart / edit / end|delete / csv),
  start/end forms, comparison chart (experiments selected per row, two axes, optional relative time
  axis, FR-16 time range), CSV export as a row action - all styled with Tailwind, config-driven, and
  refreshable without manual reload (15 s).
* **Dials** (20.10.2026, seventh session): each dial draws **one arc - the value arc** - the fixed
  green -> blue -> red gradient filled from 0 up to the reading, so **which colours appear depends on
  the range**, plus a dark **needle** at the exact value and a number in the colour of the arc's tip.
  The old two-layer look (a full-scale gradient arc with a thin value bar on top of it) is gone and
  the scale is wider: 0-30 °P / 0-50 °C (`dashboard.gauge_gravity_max` / `gauge_temp_max`).
* **FR-19 logic** is in place (reworked 20.10.2026): the status dot next to the device name is
  green while healthy and **red** for both conditions - no data for more than three intervals
  (or never reported) *and* battery below the configured threshold. The dotted reason is text
  and therefore only shown in the expanded card, one line per condition; the collapsed header
  carries no warning text. The red "no data" badge is gone (`card_warnings()` + `status_dot()`).
* **FR-16 / FR-22** (20.10.2026): the time range selector filters chart **and** export; the export
  reports what it wrote instead of silently doing nothing. Since the seventh session the selected
  range also **pins the chart's x axis** to its whole window (`chart_window()` + the `x_range`
  argument of `charts.fermentation_figure()`), so the empty days before an experiment's first
  measurement stay visible instead of being autoscaled away; *entire experiment* keeps Plotly's
  autoscale and the FR-18 relative axis is never pinned (it counts hours since the start).
* **FR-01** (20.10.2026): beer style, original gravity, yeast, responsible and notes live in the
  **experiment dialog of the device card** (grey "Set up experiment" button, lower left); while an
  experiment runs the card shows `running experiment: <name>` and a red end button. No separate
  start/end card, and the iSpindel is never picked twice.
* **FR-05 table** (20.10.2026, fifth session): the panel has **no heading line** any more
  (`ui.card(None, ...)` - the tab labels `Running (n)` / `Completed (n)` say what is shown), and
  its `Actions` column follows the **row state**: a **running** row carries one red stop icon that
  opens the same FR-04 confirmation popup as the card's red button (no edit / delete while an
  experiment runs), a **completed** row keeps pencil + trash (FR-06). Covered by
  `tools/check_requirements.py` and `tools/ui_test.py`.
* **The device-card accordion animates** (20.10.2026, fifth session): opening/closing runs over
  `--accordion-transition-duration: 0.5s` (declared on `details[data-card]` in
  `app/assets/input.pcss`, consumed by `::details-content` with `interpolate-size` +
  `content-visibility ... allow-discrete`) - still without a callback; `prefers-reduced-motion`
  switches it off.
* **`tools/ui_test.py`** (20.10.2026): browser-less test of that dialog - it drives the real Dash
  callbacks (open, validation, create, end, cancel, grid rebuild) with the button ids as the card
  renders them, plus the FR-06 row actions and the FR-04 end icon of a running row (fifth session).
  46 checks, all PASS. `tools/check_requirements.py` (33 checks, all PASS) covers the FR-05 table
  columns **and** the action icons per row state.
* **Experiment auto-end fixed** (20.10.2026, second session): dash-renderer fires the
  pattern-matching callback when a rebuilt grid adds or removes the red end button, and acting on
  that ended an experiment seconds after it was created (0 measurements, nothing to select in the
  chart). The guard the setup button already had now also covers the end button (`main.clicked()`,
  proven by `ui_test.py`). **Only local so far - the Pi still runs the old code.**
* **Notices are toasts** (20.10.2026): experiment start/end feedback is a fixed top-right toast
  (`ui.toast()`, `#msg` is `fixed right-0 top-0`, `toast-life` in `input.pcss`) that fades away
  after 10 s - CSS only, no clientside JS.
* **Local development database** (20.10.2026): the laptop stores into its own PostgreSQL cluster
  (`data/pg`, port 5433) instead of the SSH tunnel to the Pi's production database, and the ingest
  subscribes to the Pi's broker to get the live iSpindel data.
* **MQTT client-id collision fixed** (20.10.2026): `mqtt.client_id` is configurable (laptop
  `ispindel-ingest-laptop`, Pi `ispindel-ingest`). Sharing an id made the two ingests disconnect
  each other in a loop, so the laptop stored nothing. Verified: both databases receive the same
  transmissions at the same time with no disconnects.
* **Card footer times** (20.10.2026): the last measurement and the next transmission moved from
  the card header to the footer as a live relative line - `last: 12 s ago · upcoming: in 12 s`
  (`times_text()` for the first paint, the `device_times` store plus one clientside callback for
  the once-per-second tick).
* **Phone layout (NFR-06)** (20.10.2026): buttons are 44 px tall (`min-h-11`) and fill the row
  (`w-full sm:w-auto`), the dialog and the chart controls stack on a phone, the radio labels got
  tap-target heights, and the charts drop the legend and shorten the axis titles below 768 px
  (the `viewport` store + a clientside callback; `update_chart`/`update_dashboard` read it).
* **Batch cards instead of dials** (20.10.2026, eighth session): the two Plotly gauges at the top of
  every device card were replaced by three text **data zones** (**gravity** with the OG, the derived
  target FG and the 24 h rate; **temperature** with the target window of the beer style and the
  deviation; **attenuation & ABV** with the estimated final ABV - FR-20). The header now wears the
  batch name, its `beer_style`, a **status chip** (`● ACTIVE` / `● IDLE`, the FR-19 dot inside) and
  `Bat: x %`. `app/components/gauges.py` was deleted, `battery_percent()` moved into `main.py`, and
  the two `dashboard.gauge_*_max` settings were replaced by `expected_attenuation` and
  `target_temp_c`. The zones are cheap HTML instead of two `go.Indicator` figures.
* **The device cards stand alone** (20.10.2026): the container box around the iSpindel overview
  was removed entirely; on a phone the three zones stack (`span={"base": 12, "sm": 4}`) and the
  header hides the `beer_style`.
* **Compact experiment buttons + panel fade-in** (20.10.2026): the setup/end buttons use the
  `compact=True` variant (`text-xs`, `min-h-8`) to match the card footer, and every panel
  (iSpindel card + `ui.card()` section) fades in via the Tailwind theme animation
  `animate-fade-in` (with `motion-reduce:animate-none`). The stable React key (`id`) means the
  animation plays once instead of on every refresh; device cards are staggered by `slot`.
* **FR-05 in two tabs** (20.10.2026): the experiment table is a `dmc.Tabs` with `Running (n)`
  and `Completed (n)`, both from the same `v_experiment_overview` query. The Tabs shell lives in
  the static layout, which also fixes the `exp-tabs` callback error and keeps the open tab
  without any store.
* **`tools/simulate.py`** (20.10.2026): seeds `SIM_01` + `SIM_7d_sine` (7 days, 15 min, 673 rows)
  from two sine functions - a complete fermentation for demos and layout work without hardware.
  `--delete` removes all `SIM_` rows, and `check_requirements.py` no longer deletes arbitrary old
  measurements (it only touches its own `zz_validation` rows), so a simulation survives the tests.
* **`tools/simulate.py --demo`** (20.10.2026, seventh session): the same two sine functions, but as a
  **fleet** - 6 iSpindels in 3 groups of two (`SIM_A1`..`SIM_C2`), each running **4 batches of 2-5
  days** placed on the four weeks around today (24 experiments, ~9 500 rows), so FR-15, the FR-05
  table and the comparison chart have realistic material. A group's two devices differ by ~13 h and a
  few tenths of a °P/°C (the "similar pair" for FR-17/FR-18), the groups differ by several °P/°C.
  The **last** batch of every device stays open - the schema allows only one open experiment per
  device and it covers `[start, infinity)`, so no batch may follow it. `--until-now` writes the fleet
  without the future (17 experiments): a card always shows the *newest* row of its device, so a
  future-dated batch would make the card read a future "last measurement" and would also appear in
  the FR-16 ranges (they only have a lower bound). `--delete` also had to be fixed: it removed
  experiments by *name*, so an experiment created in the UI **on** a SIM_ device blocked the device
  delete with an FK error. Two checks in `check_requirements.py` had to become **device-aware**
  (FR-09's `GROUP BY recorded_at` reported a conflict for two iSpindels transmitting in the same
  second; the FR-09 check now also proves that no two experiments of one device overlap).
* **Markers only on short series** (20.10.2026): `mode="lines+markers"` up to 200 points, else
  `"lines"` - a dense 7-day chart no longer draws 673 overlapping markers.
* **FR-06 edit + delete** (20.10.2026): every FR-05 row has a pencil and a trash icon
  (`dmc.ActionIcon` + `dash_iconify`, added to `environment.yml`). Both open the same dialog,
  rebuilt from `experiment_form(values)`; the mode in `exp-target` decides whether `exp-submit`
  creates, updates (`update_experiment()`) or deletes (`delete_experiment()`, measurements
  first). `tools/ui_test.py` covers prefill, a refused duplicate name, the update and the delete.
* **"Time range" / "Time axis" fixed** (20.10.2026): `ui.field()` now renders a `<div>` instead
  of a `<label>`. Nested labels (`dcc.RadioItems` renders one per option) made the browser also
  click the first radio, so the selector snapped back to "entire experiment" and the range never
  applied. Covered by the new FR-05 tab checks and the existing FR-16 range checks.
* **Read-only figures** (20.10.2026): `GRAPH_CONFIG` turns the Plotly modebar (zoom / pan /
  download / fullscreen) off for the comparison chart too, matching the device charts.
* **One y axis per line plot** (20.10.2026): `charts.fermentation_figure()` dropped
  `secondary_y` - gravity (°P) and temperature (°C) share a single left-hand scale, the ticks
  are on the left only, the temperature trace stays dotted/transparent and the axis title
  carries both units (`gravity (°P) · temperature (°C)`, `°P · °C` on a phone).
* **`tools/check_requirements.py`** (20.10.2026): 24 machine checks against the live database - all
  PASS; verifies FR-01, FR-02, FR-03, FR-04, FR-05, FR-09, FR-10, FR-11, FR-15, FR-16, FR-21,
  FR-22, NFR-05 and NFR-09 without hardware and cleans up after itself.
* **Operations documentation**: `deploy/pi_setup.sh`, mosquitto config, systemd units, backup cron,
  Tailwind build (npm + standalone CLI), full local test instructions (README sections 1-4), plus the
  D1 concept draft in `docs/concept.md` (architecture diagram, automation pyramid, ER diagram,
  technology choice, assumptions).

## What is missing

### Must

| Requirement | Missing part |
| --- | --- |
| FR-15 / T-02 | importing the *other* iSpindels in use is unresolved (only `dfp_os_01` publishes to this broker) |
| NFR-05 | a person who has never seen the dashboard creates, displays and exports an experiment without help |
| NFR-08 | a *second* person installs from the README (the walk-through on 20.10.2026 found and fixed two gaps) |

*(Closed on 20.10.2026: FR-01, FR-12, FR-14, FR-16 and the non-functional NFR-01 - NFR-04 on the
deployed Pi; NFR-07 measured at 1.31 s for fermentation-phase volume.)*

### Should / Could

FR-06 (edit experiment + events with chart markers), FR-22 (time range in the export),
NFR-06 (smartphone proof), NFR-07 (5 s proof,
downsampling), NFR-09 (DST proof), plus the explicitly required documentation of the CSV columns
in the README. (FR-20 - attenuation / ABV / gravity drop per 24 h - was closed on 20.10.2026 with
the batch zones.)

### Deliverables

| ID | Status |
| --- | --- |
| D1 Concept | **missing** (1-2 pages: architecture + automation pyramid, data model, technology justification, assumptions) |
| D2 Running system with fermentation-phase data | not yet - system not deployed, no real data |
| D3 Source code + README + config file | exists, but **nothing is committed to git** and the Moodle HTML export still sits in the repository root |
| D4 Presentation (15 min + live demo) | to prepare |

## Known issues / risks

1. **Brew day is 29.10.2026** - 9 days from this status. Every Must gap above must be closed and
   proven before then; lost fermentation data cannot be recovered (QoS 0, no timestamps in the
   payload).
2. **No git commits** - a single bad edit or a lost file endangers the whole deliverable.
3. **Broker placement**: the dev config points at the ZHAW lab Pi; a public broker has no
   authentication and the device topic prefix cannot be changed on the device. Whoever publishes
   as `ispindel/<name>/...` can inject values.
4. **How other iSpindels reach the dashboard** is the biggest unresolved design question.
5. **Pi clock**: no NTP -> wrong `recorded_at` everywhere (chrony is part of `pi_setup.sh`).
6. **`DEV_REPEAT = 6`** must not survive into the acceptance test.
7. **Tailwind**: new class names require a rebuild of `app/assets/tailwind.css` - `npm run css`
   (build) or `npm run watch` (dev mode, same minified output), then `python tools/css_check.py`
   to be sure; on the Pi the standalone CLI has to be downloaded once. Every class string must be
   written out in full inside a `className`/`extra` argument (no lookup table, no f-string) -
   `python tools/tailwind_class_check.py` proves it, and the VS Code tasks run both checks.
8. **NFR-07** is unmeasured; long experiments at a 1-minute test interval (T-03) or several
   devices at once could make the single-shot chart query slow.
9. **`config.yml` is committed** and contains the broker host plus a TODO to exclude it once the
   broker moves to a VPS - decide what the submitted state should be.
10. **The Pi still runs the code from the second 20.10.2026 session** - every local change since
    then (auto-end guard, toast, card footer times, blue running outline, class-name rule, the
    FR-05 panel/row-action and accordion changes of the fifth session, the chart-selection /
    row-export and the time axis / range move of the sixth session) is **not deployed**.
    Experiments started there are still ended automatically a few seconds later, and the Pi's
    `app/assets/tailwind.css` is the older build. Deploy the local fixes (`rsync` +
    `deploy/pi_update.sh`) before the next test; the Pi's `config.yml` needs no change (the deploy
    sed keeps it at `localhost:5432`).

## Evolution of decisions

* Starting point: read the iSpindel via its HTTP push, ingest into a database, show a dashboard.
* Field reality (7 MQTT topics, no JSON, no timestamp, QoS 0) reshaped the ingest into a burst
  assembler with the Pi as time authority.
* The reference Node-RED dashboard in the lab (dials for extract, temperature, battery charge,
  "Gärdiagramm") set the visual target for the device cards; the cards became native `<details>`
  accordions to avoid extra callbacks.
* Write-on-last-topic replaced "wait for `burst_seconds`" once the countdown was observed to lag
  by 10 s.
* Database-level constraints (unique name, exclusion constraint) replaced UI-only validation, so
  the behavioural requirements hold whatever the caller is.

