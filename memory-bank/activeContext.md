# Active Context

_Last updated: 27.10.2026 (eleventh session: **repository simplification** - dev-only tooling and
dotfiles removed, `compose.dev.yaml` merged into `compose.yaml`, comments/docstrings cut hard;
tenth session: **container migration** - the whole system is four compose
containers started by `./run.sh up` on any machine; `config.yml` carries no machine-specific value,
the rsync/sed/systemd double setup is gone, `deploy/systemd/` holds the Pi boot step + backup timer
and `scripts/publish.sh` exports the code-only tree; the two data/date-dependent self-test checks were
fixed and the card-content decision was closed, so the suite is ALL PASS again. Ninth session: the newest code is **deployed on the Pi again** - the
`dash-iconify` install that the Pi's `beer` env was missing, both services restarted, all three
browser-less checkers ALL PASS, and the README gained **2.7 "Start, stop and check the app on the
Pi"** - see below; the FR-16 narrowing check was fixed on the way. Eighth session: the device card's `className` carried a class name that
does not exist - an invented corner-shape token plus `ring-blue-900` instead of the documented
`ring-page` - it is fixed and the CSS rebuilt; the same card also lost its **beer-style line** and
the chip's **state label**, which `tools/check_requirements.py` reports and which is left open on
purpose - see below; seventh session: there is a **6-device simulated fleet** for demos
(`tools/simulate.py --demo`, 24 batches over the four weeks around today) - see below; the dials were
redesigned - one **value arc** in the
gradient's range colours plus a needle at the exact reading on a wider 0-30 °P / 0-50 °C scale - and
the chart's x axis spans the whole selected FR-16 time range, so the empty days before an
experiment's first measurement stay visible - see below; sixth
session: the chart's experiment selection and the CSV export moved
into the FR-05 row actions, the time axis / range moved under the figure; fifth session:
the FR-05 table lost its heading and its actions now follow the row state, the device-card accordion
animates; fourth session: Tailwind build-vs-dev-mode, the class-name rule and the corner-shape
plugin; third session: the requirement side was re-published as prose in `docs/spec/`; second
session: experiment auto-end fixed, toast notice, local development database, MQTT client-id
collision fixed)_

## Session: repository simplification and flat layout (27.10.2026, eleventh-thirteenth session)

The repository was cut back to a normal student-project shape (request: *"a lot of unnecessary
over-engineering, excessive comments, functions and config files and dotfiles - simplify so it
represents student work"*), then restructured into a **flat repository root** (request: *"one
single repo"* - no `app/` wrapper). **Removed** as dev-only tooling / over-engineering:
`.editorconfig`, `.gitattributes`, `scripts/publish.sh`, `compose.dev.yaml`, `environment.yml`,
`requirements-dev.txt`, and the tools `css_check.py`, `tailwind_class_check.py`, `load_test.py`,
`mqtt_watch.py`, `serial_monitor.py`, `run_broker.sh`, plus `deploy/powercycle_test.sh`; the
git-ignored legacy `data/` cluster was deleted. `.vscode/` and `.clinerules/` were restored on
request. Comments/docstrings were reduced sharply (`main.py` 1595 -> 1248 lines, `README.md`
348 -> 175); the short `FR-*`/`NFR-*` tags stay (rule 3). **Layout** - root: `main.py`, `db.py`,
`components/` (`ui.py`, `charts.py`), `mqtt_service.py`, `assets/`, `sql/`, `tools/`, `deploy/`
plus `run.sh`, `compose.yaml`, `Dockerfile`, `config.yml`, `requirements.txt`, `package*.json`,
`LICENSE`, `README.md` and the dotfiles. `ingest.py` was renamed `mqtt_service.py`; the components
moved back into `components/`.
**Verified:** `podman/docker compose config` clean, `./run.sh up` recreates the stack (image
rebuilt with `COPY . .`), `./run.sh test` = 134 PASS / 0 FAIL / 0 SKIP, dashboard/`_dash-layout`/
`tailwind.css` = 200, an MQTT publish gives a correct row (tilt 60 / 20 °C / 1.05), `./run.sh
backup` writes to `deploy/backups`, `npm run css` rebuilds unchanged.

## Current focus

**The container migration (27.10.2026, tenth session) is done in the repository**: the double setup
(a bare-metal "deploy to the Pi" flow with `rsync` + `sed` + systemd, and a separate laptop flow)
was replaced by **one compose stack that runs on any machine** - `./run.sh up` builds and starts
`db`, `broker`, `ingest`, `dashboard`; `config.yml` carries no machine-specific value any more;
`deploy/systemd/` provides the Pi's boot step (NFR-03) and its nightly backup (NFR-04). The stack was
built, started and self-tested locally; the production Pi was **deliberately not touched** (brew day
is 29.10.2026, two days after this session).

Still open: **commit the work** (one commit `82c5078 Init` holds everything), roll the stack out on
the Pi after a `pg_dump` of the running installation, and finish the last three Must items
(FR-15 other iSpindels, NFR-05 person test, NFR-08 third-person install from the new README).

## Recent changes (20.10.2026, second and third session)

| Change | Why |
| --- | --- |
| **The Pi runs the current code again + README 2.7** (`rsync` + `deploy/pi_update.sh`, `pip install "dash-iconify>=0.1"` in the Pi's `beer` env, `tools/check_requirements.py`, README section 2.7) | Request: *"help me start up app on pi and add to readme"*. The Pi still ran the build of 20.10. 11:29 (638 lines of `app/main.py` against 1593), so the first sync put the dashboard into a `ModuleNotFoundError: No module named 'dash_iconify'` restart loop - the Pi's `beer` env predates that `environment.yml` entry and a deploy never recreates it. The Pi's `config.yml` had drifted the same way (no `expected_attenuation`, no `target_temp_c`, no `mqtt.client_id`), so the repository copy was synced and `pi_update.sh`'s sed rules turned it back into a Pi config (backups: `~/ispindel-repo-bak-2026-10-21.tgz`, `~/ispindel/config.yml.bak-2026-10-21`). Verified on the live database: `check_requirements.py` **44 PASS + 1 data-dependent SKIP**, `ui_test.py` **54 PASS**, `fr19_test.py` ALL PASS, dashboard 200 in ~30 ms, served `tailwind.css` md5-identical to the committed build. The README now has **2.7 "Start, stop and check the app on the Pi (day-to-day)"** (systemctl start/stop/restart, journalctl, the six health checks, the deploy sequence with `config.yml`, the foreground run, and the `pip install` trap). One checker bug surfaced: FR-16's "range really narrows the chart" asserted `all - 24h == 1` (its own synthetic row) and failed on the production database, where the first experiment already has older real measurements - it now compares the difference with the DB count of rows outside the window. |
| **A 6-device simulated fleet for demos** (`tools/simulate.py --demo`, README 1.5, `check_requirements.py`) | Request: *"multiple experiments, 2-5 days each, within the last two weeks and the next two weeks, slightly different sines but some grouped and similar, split over 6 simulated devices"*. `seed_demo()` builds **6 iSpindels in 3 groups of two** (`SIM_A1`..`SIM_C2`) from a group curve (West Coast IPA 22 °C, Hefeweizen 19.5 °C, Bock 12.5 °C; og 13.4-16.2 °P, drop 6.8-9.8 °P) plus a deterministic jitter: the second device of a pair starts ~13 h later and ferments ~0.35 °P further at ~0.45 °C warmer, and every later batch drifts a little more - so a pair overlays almost exactly (FR-17/FR-18) while the groups are clearly different from each other. Every device runs **4 batches of 2-5 days** (durations clamped into that range) placed on the four weeks around today, so the fleet spans -14 d to +12 d: 24 experiments, ~9 500 rows at a 15 min interval. The **last** batch of each device is left open (`ended_at NULL`) - the schema allows only one open experiment per device and it covers `[start, infinity)`, so no batch may follow it, which is why the running batch is the future one. `--until-now` writes the fleet without the future (17 experiments, ~5 600 rows, the running batch clipped at now), because a card always shows the *newest* row of its device: with future rows the six SIM_ cards read a future "last measurement" and the FR-16 ranges (lower bound only) return them - the chart hides them behind the pinned time axis, the CSV export writes them out. Two bugs surfaced on the way: **`--delete` only matched experiments by name**, so an experiment started in the UI **on** a SIM_ device stopped the device delete with an FK error; and the checker's **FR-09 `GROUP BY recorded_at` was not device-aware** - it reported a conflict as soon as two iSpindels sat on the same 15 min grid, a false positive that would have hit the real multi-iSpindel case (FR-15) too. |
| **Dials redesigned: ONE value arc + a needle, wider scale** (`app/components/gauges.py`, `app/main.py`, `config.yml`, `tools/check_requirements.py`, README) | Two instructions in one go: *"do not use inner and outer layers, just one layer"* and *"bigger range + the exact point of the last measurement"*, then a correction - *"remove the outer gradient arc and depending on the range display the inner arc with different colours"*. **What was wrong:** the arc was drawn twice - a full-scale gradient arc (`steps`, 60 bands, 0.7 thick) with a thin value bar (`bar`, 0.25) lying on top of it - so nothing on the dial said *how much*, and the value bar could not mark a position (it always starts at 0). **Now:** `gauge()` draws **one arc, the value arc** - `gradient_steps(maximum, limit=value)` (`limit` is the new argument) drops every band behind the reading and clips the one the reading falls into, so the arc is filled 0..value and **which colours appear depends on the range** (a low gravity reaches only the green part, a high one runs into the red). A band's colour always comes from its position on the **full** scale, so the tip colour still matches `value_color(value, maximum)`, i.e. the number's colour. The **needle** is a `threshold` line at exactly `value` in `NEEDLE_COLOR` (`#0f172a`; value-coloured it would vanish into the arc under it) - it replaces the old optional `threshold` argument, which nothing called (Plotly allows only one threshold marker). The scale was widened to **0-30 °P / 0-50 °C** (`gauge_gravity_max` / `gauge_temp_max`), which also closes the old follow-up "the gauge saturates at the ~30 °P the uncalibrated device reports". New constants `NEEDLE_COLOR`, `NEEDLE_THICKNESS` (0.8 - the needle crosses the 0.75 arc) and `NEEDLE_WIDTH`; `BAR_THICKNESS` is gone. The grey `bgcolor` body stays (the unwritten part of the scale). Checks: *"the dial draws ONE arc layer - the value arc, no value bar"* (no `bar.color`, steps end at the value, fewer than 60 bands) and *"the value arc grows and re-colours with the reading"* (5 °P -> 15 bands tip `#0b7e7f`, 15 °P -> 45 bands tip `#6a3f71`, `limit=0` -> no arc). |
| **The chart's x axis spans the whole selected FR-16 range** (`app/main.py` `chart_window()`, `app/components/charts.py` `fermentation_figure(x_range=...)`, 3 new checks in `tools/check_requirements.py`, README) | Report: with *last 7 days* selected, an experiment that had only been running for three days showed just those three days. Plotly autoscales the x axis to the available points, so the four empty days in front of the first measurement were cropped away - and those empty days are the answer to "how long has this been running?". New helper `chart_window(range_key)`: for a fixed range it reads `now()` **from the database** (the same clock `RANGE_FILTER` compares against, so axis and data can never disagree about where the window begins and the newest point cannot fall off the right edge) and returns `(now - span, now)`; `None` for *entire experiment*. `fermentation_figure()` gained the **optional** `x_range` (backward compatible - the device cards and `load_test.py` call it without) and passes it to `update_xaxes(range=...)`, i.e. `range=None` (Plotly's autoscale) when there is no window. The FR-18 relative axis **ignores** the window on purpose: it counts hours since the start and has to begin at 0. Verified live: 3 days of hourly data -> `all` = autoscale, `7d` = 7.00 d axis vs 3.00 d data (4 empty days), `24h` = 1.00 d, `rel` = None. |
| **Devices tab (FR-12); the "hide the empty chart panel" idea was taken back** (`app/main.py`, `tools/check_requirements.py`, `tools/ui_test.py`, README) | Two requests. **(1) The comparison-chart panel was hidden while `chart-select` was empty** (a `chart-panel` wrapper + a clientside callback on `display`) - **taken back the same day**: it is always visible again, since the FR-16/FR-18 controls live in it and the empty chart reads "no measurements yet". `dcc.Download` stayed outside the card. **(2) New Devices table** (`DEVICE_HEADERS`, `device_rows/device_table/device_actions`, `device_values/update_device/device_form`, `dev-btn` pattern): one row per iSpindel with MQTT name, display name, in-use status, first seen, last measurement, **the interval the device itself reports** (FR-11), measurement count and a settings action. The settings dialog **reuses the experiment modal** (`experiment_action` gained the `dev-btn` Input plus `dev-name`/`dev-active` states and the `mode: "device"` branch) instead of a second modal, so `msg`/`reload` keep one owner. Editing is display name + the `device.is_active` flag; the MQTT name is read-only (it is the topic the device publishes with). Ignored devices keep recording (FR-10) but **leave the overview** - `ispindel_overview()` and the `newest` device in the checker now join `device ... WHERE is_active`, which is what makes the flag meaningful (FR-13). `update_dashboard` gained a seventh output (`exp-tab-devices`); the Devices table is the **third tab** of the experiment panel (FR-12), not a card of its own. |
| **Styled dials: a green -> blue -> red gradient arc, value-coloured bar + number and a 24 h trend arrow** (`app/components/gauges.py`, `app/main.py`, `tools/check_requirements.py`, README) | The two per-iSpindel dials were restyled. `gauge()` gained **optional** args - `steps` (the arc, painted with `gradient_steps()`), `threshold` (a marker line; kept from the reference example, unused by the app), `delta` (switches the mode to `gauge+number+delta`) and `number_color` (the value-coloured number) - plus, on top of the tick marks from the first pass, an arc outline (`borderwidth` / `bordercolor`) and a background track; the signature stays backward compatible (the test scripts call it with 4-5 args). New helpers `gradient_color(fraction)` (sRGB interpolation between stops), `value_color(value, maximum)` and `gradient_steps(maximum, bands=60)`; the stops are green `#16a34a` -> brand blue `#0057b7` -> red `#dc2626`. `device_card()` paints the gradient across the arc and passes `value_color(...)` as **both** the bar and the number colour, so a rising reading walks green -> blue -> red; the gravity dial keeps the ~24 h trend arrow (`change_over()`), the phone dial stays plain (NFR-06). An intermediate idea - semantic cold/ideal/warm `steps` + a config temperature band `gauge_temp_ideal_min/max` - was **dropped again** when the gradient replaced it, so those two config keys are gone. Two checks in `tools/check_requirements.py`. |
| **Oldschool PC pixel font as the dashboard default font** (`app/assets/fonts/*.woff` + `LICENSE-…`, `app/assets/input.pcss`, `app/components/charts.py`, `app/components/gauges.py`) | The UI switched to the classic **IBM XGA-AI** face from *The Ultimate Oldschool PC Font Pack v2.2* (VileR, int10h.org, CC BY-SA 4.0). Four faces (7x15, 12x20, 12x23, "12x20 Plus") were copied into `app/assets/fonts/` (served by Dash automatically) and declared with `@font-face` in `input.pcss`; `@theme { --font-sans: "IBM XGA-AI 12x20", … }` makes it the page default (Preflight's `--default-font-family` follows `--font-sans`). The pack's web fonts set 1em = the original pixel height (15/20/23px), so text is 1:1 crisp at those sizes; switching is a one-line change of the family name. Plotly draws its own SVG text and does **not** inherit the page font, so `charts.FONT_FAMILY` feeds the same family into the comparison chart and the gauges. **Trap found after the first try:** the font showed nowhere even though the CSS was right - dmc's `MantineProvider` injects `body, :host { font-family: var(--mantine-font-family) }`, and that *unlayered* rule beats Tailwind's layered `html` rule (Mantine's default is the system stack). Fixed by passing the same stack as `fontFamily` / `fontFamilyMonospace` / `headings.fontFamily` in `main.THEME`. A second bug: `charts.FONT_FAMILY` had the spaced family name unquoted, so CSS would read it as three separate families - now quoted. All four check scripts stay green; the font files reach the browser (test client: `/assets/fonts/…` -> 200). |
| **Brand colours: yellow page canvas + blue container outline** (`app/assets/input.pcss` `@theme`, `app/components/ui.py`, `app/main.py`, `tools/ui_test.py`) | The page background and every container got a fixed palette: `--color-page: #FFDD00` (the outer `min-h-screen` div of `ui.page()` uses `bg-page`) and `--color-brand: #0057B7` (the white `ui.card()` panels and the device cards use `border-brand` as their outline - an earlier full-blue card background was reverted to white). A **running** device card uses `border-2 border-brand ring-2 ring-page` so it still differs from an idle card (FR-04); `tools/ui_test.py` asserts the new classes. Both hex values live once in the `@theme` block of `input.pcss`; the CSS was rebuilt. Text is back to dark `text-slate-*` on white, so contrast is fine again. |
| **The chart selection + the CSV export moved into the FR-05 row actions; the time axis / range moved under the figure** (sixth session: `app/main.py`, rebuilt `tailwind.css`, `tools/check_requirements.py`, `tools/ui_test.py`, `tools/load_test.py`, `deploy/pi_update.sh`, README FR-05/FR-06/1.9) | A review of the chart card. **(1) The experiment multi-select dropdown is gone** (`exp-select`, `update_options`) - each FR-05 row now carries a `chart` action (`tabler:chart-line`) that toggles the experiment in the comparison chart via the new `chart-select` store; it is **blue** while shown, grey otherwise, so the row says what is overlaid. `update_dashboard()` takes `chart-select` as an extra `Input`, so the icon flips on the click, not only on the 15 s refresh (FR-17). **(2) The time axis moved to the bottom-left, the time range to the bottom-right** - both `ui.field` radios now sit **under** the `dcc.Graph` (`sm:flex-row sm:justify-between`); the chart panel carries **no heading line and no caption** any more (`ui.card(None, ...)`, like the FR-05 panel), the selection lives in the table. **(3) The `Download CSV` button is gone** - every row (running **and** completed) carries a `csv` action (`tabler:download`, FR-21) that exports that one experiment over the selected FR-16 range and reports in the same top-right toast as the other actions; `download_csv()` is no longer a callback but a plain function called by `experiment_action` (now 9 outputs, `download.data` added). **(4) A running row now also carries the FR-06 pencil** (`edit`): a running experiment can be corrected while it runs (the edit never touches the end time) - only **delete** stays completed-only. Both test scripts and the load test were updated; `tools/*check*` and `tools/ui_test.py` are all green. |
| **FR-05 table without a heading, actions per row state; the device-card accordion animates** (fifth session: `app/main.py`, `app/components/ui.py`, `app/assets/input.pcss` + rebuilt `tailwind.css`, `tools/check_requirements.py`, `tools/ui_test.py`, README 1.3 / 1.9 / FR-06) | Three UI changes from a review. **(1) The panel heading is gone:** `ui.card(None, ...)` renders a panel without its `H2` (documented in `ui.py`); the `Experiments (FR-05)` caption repeated only the requirement id - the tab labels `Running (n)` / `Completed (n)` already say what is shown. **(2) The `Actions` column follows the row:** a **running** row carries one red stop icon (`row_actions(exp_id, running=True)`) that opens the same FR-04 confirmation popup as the red button of the device card; completed rows keep the FR-06 pencil / trash pair. The icon id may not grow a `device` key (that would break the pattern match), so new `experiment_device(exp_id)` resolves the iSpindel, and the confirmation is now one nested `end_dialog(device)` used by the card button, the row icon and - via `exp-submit` with `mode: end` - the actual end. **(3) The accordion animates:** `--accordion-transition-duration: 0.5s` is declared on `details[data-card]` in `input.pcss` and consumed by `details[data-card]::details-content` (block-size + opacity + `content-visibility ... allow-discrete`), with `interpolate-size: allow-keywords` on `:root` so the height can animate to `auto`; `prefers-reduced-motion` switches it off and an engine without `::details-content` opens instantly. Both test scripts cover the new behaviour; a **pre-existing bug** in `tools/check_requirements.py` was fixed on the way (`card_json()` used `ensure_ascii=True`, so every `°` was escaped and the FR-13 value check failed on a healthy card). |
| **Tailwind: dev mode vs build, the class-name rule, precise class discovery + the corner-shape plugin** (fourth session: `app/**/*.py`, `app/assets/input.pcss`, `.vscode/*`, `package.json`, new `tools/tailwind_class_check.py`) | Four things at once. **(1) Build vs dev mode:** `npm run css` is the one-shot minified build, `npm run watch` is Tailwind's dev mode - it now also carries `--minify`, so both write the *same* file and switching back and forth (watch while editing, `css` before committing) needs no extra step. Before, a running watch left the artefact unminified, so `css_check.py` reported a stale CSS that was not stale (that is exactly what a watch process running since the previous session was doing). The three commands are now VS Code tasks in `.vscode/tasks.json`. **(2) The class-name rule:** every class is written out in full inside a `className`/`extra` argument - `TONES`, `tones`, `size`, `th`, `td`, `INPUT_CLASS`, `GRAVITY_TEXT`, `TEMP_TEXT` and the local `outline` variable are gone, the tone/size variants are parenthesised conditional expressions. The compiler *does* find a class in a variable (it scans the raw text - `min-h-8` proved it), but the **VS Code plugin** does not, so the editor could neither complete nor warn about it. New `tools/tailwind_class_check.py` fails when a compiled class comes from anywhere that is not a `className`, and when a `className` names a class the CSS does not have. The `.vscode/settings.json` `classRegex` was rewritten for the two shapes (multi-line implicit concatenation + parenthesised variants); a `)` inside a `className=(...)` truncates the editor's match, which is why no comment containing parentheses may sit inside such an expression. **(3) Precise class discovery:** `@import "tailwindcss" source(none)` + `@source "../**/*.py"`. Tailwind v4 otherwise scans the whole project (git-aware) and compiles every class name *mentioned in prose* into the shipped CSS - found in the wild: `.bg-black` and `.hover\:bg-amber-500` from the README's troubleshooting section, `ease-out` from the `@theme` line, and `table`/`visible`/`static`/`outline`/… from ordinary English in Python comments. **(4) New plugin:** `@plugin "@toolwind/corner-shape"` (v0.0.8-3, loaded v4-style from the CSS entry point) adds `corner-*` utilities for the CSS `corner-shape` property; every rounded surface (cards, device cards, buttons, stat boxes, alerts, form inputs) now uses `corner-squircle` next to its `rounded-*`, degrading gracefully where the property is unknown. `css_check.py`, `tailwind_class_check.py`, `fr19_test.py` and `ui_test.py` (31 checks) all pass, README 4 and `techContext.md`/`systemPatterns.md` updated. |
| **The running-device-card outline is blue** (`app/main.py:device_card`, `tools/ui_test.py`) | That outline had been changed *outside* this session from `border-amber-400 ring-1 ring-amber-300` to `border-blue-700 ring-1 ring-blue-100`, and the running branch carried `rounded-sm` while the idle branch has `rounded-xl` - a slip: the card would change its corner radius the moment an experiment starts. The radius is unified to `rounded-xl` (plus the new `corner-squircle`), the blue outline was kept and the FR-04 assertion in `tools/ui_test.py` updated to the blue classes. |
| **Stale Tailwind build + dropped context classes** (`app/main.py` device card, new `tools/css_check.py`) | A hand edit to the card's `className` (`bg-black`, `hover:bg-amber-500`) showed no effect: `app/assets/tailwind.css` is a **build artefact** served statically by Dash, so new classes stay dark until `npm run css` runs - the file had been built before the edit. The same edit had also dropped **`group`** (the three `group-open:` variants stop matching: chevron no longer rotates, the collapsed gravity/temperature values no longer hide) and `border` (without it `border-slate-200` is a colour with no width). Rebuild done; `group`, `border` and `rounded-xl` restored, animation intentionally left out. New `tools/css_check.py` rebuilds into a temp file and byte-compares with the committed CSS (`--fix` writes it), so this cannot happen silently again. |
| **VS Code / Positron workspace settings** (`.vscode/settings.json` + `extensions.json`) | Tailwind IntelliSense was dead in the whole repository: Tailwind is *CSS-first* here (v4, **no** `tailwind.config.js`) and `bradlc.vscode-tailwindcss` 0.16 only auto-detects `*.css` entry points, so `app/assets/input.pcss` was invisible to it. The file names the entry point (`tailwindCSS.experimental.configFile`), maps `python` onto the markup mode, describes the class-string shapes (`className="..."`, the `f"..."` and parenthesised variants, `extra="..."`) via `experimental.classRegex`, opens `*.pcss` in the extension's own language mode and enables string suggestions for Python/HTML. Verified by a script that parses the JSONC, checks the entry point/tailwind install and runs every regex against the real class strings (SQL does not match). |
| **FR-19 indication reworked** (`status_dot()` + `card_warnings()` in `app/main.py`, `FRESH_MINUTES` removed) | The header carried a grey/green freshness dot *and* a red "no data" badge, so the same problem had two indicators. Now there is **one** dot: green while healthy, red for **both** FR-19 conditions (no data for more than three intervals / never reported, battery below `battery_warn_v`). The reason is text and is therefore rendered only in the **expanded** card, one line per condition (`no data for 60 min (more than three intervals of 900 s)`, `battery low: 3.300 V is below the 3.50 V threshold`); the collapsed header stays one quiet line and the badge is gone. Tooltip on the red dot is deliberately neutral ("expand this card for the reason"). Tailwind rebuilt (`bg-red-500`, `text-red-600`); `tools/check_requirements.py` (24) and `tools/ui_test.py` (31) still all PASS. |
| **Agent-readable specification** (`docs/spec/`, prose, tables removed) | The requirement side had been copied into the memory bank and mixed with status/design notes, and wide requirement tables are hard to read reliably. `docs/spec/` is now a clean clone of the client's specification: README (terms, priorities), 01 assignment, 02 system context, 03 requirements (all 31 with priority + acceptance criterion), 04 milestones/acceptance tests, 05 deliverables. Verified automatically against `docs/iSpindel-project.md` - no requirement text lost, zero tables. Status/design knowledge stays in the memory bank. |
| **Experiment auto-end fixed** (`main.clicked()`, the missing guard on the red end button) | A grid rebuild re-renders the cards; Dash then fires the pattern-matching callback for the *added* "End experiment" button, and the callback ended the experiment seconds after it was created (0 measurements, nothing to select in the chart). Every experiment the user created on the Pi (`test2` - `test1000`) shows the 2-9 s life span. The existing code already guarded the **setup** button against this and the end button was simply missing it. |
| **Notices are toasts** (`ui.toast()`, `#msg` is `fixed right-0 top-0`, `toast-life` in `input.pcss`) | FR-01/FR-04 feedback should be visible from anywhere on the page and disappear by itself (10 s, CSS only - no clientside JS). |
| **Local development database** (PostgreSQL cluster in `data/pg` on **5433**, `config.yml` points at it) | The Mac's `localhost:5435` is an SSH tunnel to the **Pi's production database**: "local" tests were production tests and polluted the real data. The cluster is created with `initdb` (Docker is not installed on this Mac). |
| **`mqtt.client_id`** (laptop `ispindel-ingest-laptop`, Pi `ispindel-ingest`) | Both hosts subscribe to the **same** broker (the Pi is the broker). Two clients with the same id make mosquitto disconnect each other in a loop, so the laptop ingest stored nothing. |
| `deploy/pi_*.sh` sed rules updated (5433 -> 5432, `ispindel-ingest-laptop` -> `ispindel-ingest`) | Keeps the "repo copy = laptop config, deploy rewrites it" pattern working. |
| **Card footer times** (`times_text()` + the `device_times` store + one clientside callback) | The last-measurement info was an absolute timestamp hidden in the card header; it is now a live **`last: 12 s ago · upcoming: in 12 s`** line in the card **footer**, so it is readable at a glance and no longer occupies the collapsed header. |
| **Phone layout (NFR-06)**: `min-h-11` buttons with `w-full sm:w-auto`, stacked dialog/controls, `labelClassName` tap targets, and the **`viewport` store** | Plotly cannot read CSS media queries, so a clientside callback publishes the 768 px breakpoint and the charts drop the legend and shorten the axis titles on a phone ("no legends on mobile, just time"). |
| **The device cards stand alone** (the `ui.card(...)` wrapper around the overview is gone) | The container box around the cards was redundant - each card carries its own box, so the overview is now just the grid on the page background (the FR-13/FR-19 reference lives in the layout comment). |
| **Gauge numbers shrink on mobile** (`gauges.gauge(..., mobile=True)`) | The dial is only 112 px tall on a phone (`h-28`), where the 22 px number spilled out of the arc - it is 15 px there, with the tick labels and the dial label one step smaller. |
| **Compact experiment buttons** (`ui.button(..., compact=True)`) | The "Set up experiment" / "End experiment" buttons were `text-sm`/44 px next to a `text-xs` footer line; the compact variant uses `text-xs`, `min-h-8`, `px-2.5 py-1`, `rounded-md` so the footer stays one quiet line. |
| **Panels fade in** (Tailwind `@theme` animation `animate-fade-in` + `motion-reduce:animate-none`) | The `ui.card()` sections fade in when they appear. It plays **once**: dash-renderer keys a component by its `id` (`createContainer`), so a refresh reuses the DOM node - no flicker every 15 s. The **device cards do not animate** any more (20.10.2026: fading them on a grid rebuild looked buggy), so they carry neither `animate-fade-in` nor the per-`slot` `animationDelay`. |
| **Experiment table in two tabs** (`dmc.Tabs` in the *static* layout) | FR-05 in a `Running (n)` / `Completed (n)` view. Both panels share the same `v_experiment_overview` query. The Tabs shell is **not** inside the rebuilt table: a string id in callback-generated content cannot be a callback `Input` (Dash aborts at startup - that was the reported error), and a component that is never re-rendered keeps its own tab state, so no store is needed. |
| **`tools/simulate.py`** | Seeds a clearly simulated `SIM_01` + `SIM_7d_sine` (7 days, 15 min, 673 rows) from two sine functions, so the dashboard has a complete fermentation without hardware. `--delete` removes every `SIM_` row; the test scripts were made to delete only their own `zz_` rows so a simulation survives a test run. |
| **FR-06 edit + delete from the table** (pencil / trash icons, `dash_iconify`) | Both open the *same* dialog as "Set up experiment": `#exp-form` is rebuilt from `experiment_form(values)` and `exp-target` carries `{"mode", "id", "device"}`, so one dialog creates, edits and deletes. `update_experiment()` re-runs the FR-02/FR-03/CHECK validation; `delete_experiment()` removes the measurements first (no cascade) and the confirmation names the count. |
| **Markers only on short series** (`charts.fermentation_figure()`) | 673 markers of size 5 overlap into a fat band, so a 7-day simulation looked nothing like an 18-point chart. `mode="lines+markers"` is used up to 200 points, above that `"lines"` - the only remaining difference between two charts is then the data. |
| **"Time range" / "Time axis" now really work** (`ui.field()` renders a `<div>`, not a `<label>`) | The radios were inside a `<label>` while `dcc.RadioItems` renders a `<label>` per option; a label inside a label is invalid HTML, so the browser also clicked the *first* radio - the selection snapped back and the range never applied. The query was always correct (`check_requirements` proves `all` = `24h` + 1 point), the UI wiring was not. |
| **Figures are read-only** (`GRAPH_CONFIG = {"displayModeBar": False, ...}`) | The comparison chart had the full Plotly toolbar (zoom / pan / download / fullscreen); now every figure hides it, matching the device charts. |
| **One y axis per line plot** (`charts.fermentation_figure()`, no `secondary_y`) | Gravity and temperature now share a single left-hand scale instead of a gravity axis on the left and a temperature axis on the right; the temperature trace stays dotted/transparent and the axis title carries both units. |
| **Device card: a class name that does not exist, fixed and rebuilt** (`app/main.py` `device_card`, `app/assets/tailwind.css`) | The card's `className` had been hand-edited into `corner-es-superellipse.corner-superellipse/100` - two invented utilities glued by a **`.`** instead of a space, so the whole thing is one token that matches nothing (the corner-shape plugin knows `corner-{shape}` with `{shape}` ∈ round/scoop/bevel/notch/square/squircle, and `corner-superellipse/{value}` only *with* a value); the running branch also said `ring-blue-900` while the comment directly above it, README 4 and `tools/ui_test.py` all document the **yellow** `ring-2 ring-page`. Both branches now read `rounded-xl corner-squircle` + `ring-2 ring-page`, and `npm run css` rebuilt the artefact - before that rebuild the *stale* CSS still shipped `.ring-page` from an older build, which is why the card looked "buggy on grid rebuilds" while the source said something else. `tools/css_check.py`, `tools/tailwind_class_check.py` (both exit 1 before the fix), `tools/ui_test.py` (31 checks) and `tools/fr19_test.py` pass again; the rendered grid was verified against the live DB (7 cards, 108 class tokens, none of them missing from the compiled CSS). |
| **Open finding: the card lost the beer style and the chip label** (`app/main.py` `device_card` / `status_chip`, `tools/check_requirements.py`) | `check_requirements.py` still fails one FR-13/FR-20 check: the card is expected to name the batch's **`beer_style`** and the header chip to say **`active`**, and it now carries neither. The two style spans in the header are commented out (`app/main.py` 756-759 - `style` is still computed and used for the temperature window, so only the render is gone), and `status_chip()` renders `children=[status_dot(warn)]` alone although its docstring still promises the label ("active" / "idle"; "running" survives in the `title` only). Deliberately **not** changed with the class fix: this is a visible-content decision, not a styling bug - either the label/spans come back or the checker, the register and the docstring follow. |

**Not yet deployed:** the Pi still runs the old code, so experiments there are still ended
automatically. The fixes are local only; the Pi is copied over when development is finished.

## Open Must gaps (blocking acceptance)

| # | Requirement | Gap | Effort |
| --- | --- | --- | --- |
| 1 | **FR-15 / T-02** | only the own iSpindel (`dfp_os_01`) publishes to this broker; how the **other iSpindels in use** reach this system is unresolved (their broker? own broker? bridge?). Everything else about FR-15 is done and proven (`DEV_REPEAT = 1`, one card per device, comparison chart with 2 experiments). | medium (client decision) |
| 2 | **NFR-05** | a person who has never seen it must create, display and export an experiment without help. UI is English, every action answers with a message; the remaining UX risk is the free-text start field (`2026-11-12T16:30`). | small (a test person) |
| 3 | **NFR-08** | a *second* person should install from the README. The walk-through on 20.10.2026 fixed two real gaps (`dash-mantine-components` missing in the env, units not waiting for the clock). | small (a second person) |

Closed on 20.10.2026: **NFR-01 - NFR-04** (deployment, host-name access, two power cycles, no data
loss), **FR-14** (lag + refresh measured), **NFR-07** (1.31 s at fermentation-phase volume),
**FR-01**, **FR-12**, **FR-16**, **FR-21/FR-22**, and the fake `DEV_REPEAT` duplication.

## Should / Could gaps (after the Must items)

* **FR-06** (Should): the **edit half is done** (20.10.2026) - the pencil icon of an FR-05 row
  opens the dialog prefilled and `update_experiment()` saves it, the trash icon deletes the
  experiment with its measurements after a confirmation. Both icons sit on **completed** rows
  only; a running experiment's row carries just the FR-04 end action (fifth session). Still open:
  **timestamped events with markers in the chart** (`experiment_event` exists -> needs an insert
  form and `add_vline`/annotations in `charts.fermentation_figure()`).
* **NFR-06** (Should): a real smartphone test of the Must functions.
* **NFR-09** (Should): the DST change on **25.10.2026** - UTC storage and local display are verified,
  the observable "no gap, no overlap" test is still open (free test, five days away).
* **FR-20** (Could): derived values (apparent attenuation, estimated ABV, gravity drop per 24 h).
* Follow-ups from the code review: default interval when `interval_s` is NULL (FR-19 edge case) and a
  date/time picker instead of the free-text start field (NFR-05). The third one - the gravity gauge
  range - is **done** (20.10.2026, seventh session): `gauge_gravity_max` is 30 °P, so the ~30 °P of
  the uncalibrated device no longer saturates the dial.

## Next steps, in order

1. **Commit everything to git** (the repo still has zero commits) - protects D3; decide first whether
   `config.yml` (it contains the broker host) should be committed or replaced by an example file.
2. Record the small proofs a person has to do: NFR-05 walk-through, NFR-06 on a phone, T-06 CSV in
   Excel, NFR-09 around the DST change on 25.10.2026.
3. Decide the FR-15 question with the client (shared broker / bridge / second subscription) - the
   only Must that depends on a third party.
4. FR-06 (edit + events as markers), then FR-20 if time allows.
5. Polish D1 (1-2 pages, the two brewmaster questions) and prepare D4.


## Active decisions

* **PostgreSQL + Dash on a Raspberry Pi, bare metal with Miniconda + systemd** - chosen and
  justified in the README; the concept has to justify the technology against alternatives.
* **One measurement row per transmission, timestamped by the Pi** (the firmware sends no time) -
  the countdown and the whole live behaviour depend on this.
* **Invariants in the database** (unique experiment name, exclusion constraint on the device time
  range) instead of UI-only checks.
* **Raw values kept besides the normalised ones** (`gravity_raw`, `temp_raw`, `temp_unit`) for
  traceability if the °P/°C assumption is wrong.
* **Broker may run off the Pi** (NFR-01 explicitly allows it); currently the ZHAW lab Pi
  (`clt-lab-n-1298.zhaw.ch`) is used as the dev broker.

## Open questions for the client

* Which two brewmaster questions must the dashboard answer? (needed for the presentation)
* Which broker/network do the other iSpindels of the course use during the fermentation phase -
  can they all publish to one broker (whose)? How are the device names chosen (the naming
  convention for experiments is also a course-wide decision)?
* Group of one or two participants (affects "one system, two beers/iSpindels")?
* Is the lab Pi available for the whole fermentation phase, or must the broker run on the project Pi?

## Constraints and conventions to respect

* Priorities: Must first; Should/Could only add value on top of a working core system.
* Requirement IDs are referenced in code comments and in the traceability register - keep that
  convention when adding code.
* All settings in `config.yml`, never in the code (NFR-08).
* UI language is English; storage UTC, display Europe/Zurich.
* Never expose the dashboard/DB/broker to the internet; no authentication by design.

## Learnings / gotchas discovered so far

* The stock firmware publishes 7 separate topics per transmission and **no timestamp**; `tilt`
  first, `RSSI` last - that ordering makes an immediate single-row write possible.
* Waiting for `ingest.burst_seconds` (10 s) before writing made the countdown 10 s wrong; writing
  on the last topic fixes it.
* Dash remounts a `<details>` when its React key shifts -> cards kept closing until the stable
  `id` + `open_cards` store pattern was introduced.
* `gravity_unit` must match the device's **calibration polynomial** (stock polynomial = °P).
* mosquitto 2.x listens on localhost only until `listener 1883 0.0.0.0` is configured - a classic
  trap that `deploy/pi_setup.sh` checks explicitly.
* The PDF print from 20.10.2026 adds no requirement beyond `docs/iSpindel-project.md`; the raw
  extraction is kept in `docs/ispindel-project-moodle-print-2026-10-20.txt` for evidence.

**From the deployment on 21.10.2026 (the same two traps, a second time):**

* **A new dependency in `environment.yml` is a manual step on the Pi.** The env is created once and
  a deploy never rebuilds it, so `dash-iconify` (the FR-05 icons, added after the Pi's env was
  created) made the dashboard boot-loop with `ModuleNotFoundError: No module named 'dash_iconify'`.
  Symptom shape: `systemctl is-active` says `activating`, `curl` returns nothing, and
  `journalctl -u ispindel-dashboard` has the answer in one line. Fix:
  `~/miniconda3/envs/beer/bin/python -m pip install "dash-iconify>=0.1"` + restart.
* **A code deploy can require a `config.yml` change.** The newer code reads
  `dashboard.expected_attenuation` / `dashboard.target_temp_c` at import time; the Pi's older
  `config.yml` had neither (it still carried the two unused `gauge_*_max` keys instead), so the new
  code would have died on a `KeyError`. `pi_update.sh` only rewrites `dsn`, the broker host and the
  client id - the reliable path is to **copy the repository `config.yml` over** (keep a `.bak`
  first) and let the two sed rules turn it back into a Pi config.
* **`tools/check_requirements.py` had a fresh-database assumption**: FR-16's "range really narrows
  the chart" expected `all - 24h == 1`, i.e. only the synthetic row the script itself inserts.
  On the production database the first experiment already has older real measurements, so the check
  failed although the range worked. It now compares the difference with the DB count of rows
  outside the window - a check must never depend on the data being small.

**From the deployment on 20.10.2026 (all of these cost time once - do not repeat them):**

* The Pi's `beer` conda env was created before `dash-mantine-components` was added to
  `environment.yml`, so the dashboard died with `ModuleNotFoundError: dash_mantine_components`
  in a restart loop. `environment.yml` was right, the existing env had drifted.
* **The Pi has no RTC.** After a boot its clock sits at the fake-hwclock value of the last
  shutdown - chronyd reported "System clock wrong by 323465 s" (3.7 days). Anything that stamps
  data (`recorded_at`) before NTP has synced writes the wrong time, so both units now wait for
  `chrony-wait.service` (enabled) with `Wants=` (not `Requires=`), which can never block the
  ingest forever (`TimeoutStartSec=180` on that unit).
* A power cycle takes ~60 s before *all* services are up (Wi-Fi -> network-online.target ->
  chrony-wait -> Postgres/mosquitto -> the two iSpindel units). Checking 10 s after SSH answers
  shows `inactive` and looks like a failure - wait a minute (T-07 checklist updated).
* `pkill -f "gunicorn --chdir ..."` over SSH **kills your own session** (the pattern matches the
  remote shell's command line). Use `systemctl kill --signal=SIGKILL <unit>` instead.
* `rsync src -e "ssh ..." . host:dir/` with a stray `.` copies **the whole current directory**
  (including `node_modules`) into the target - it filled `~/ispindel/tools/` with 29 MB of a
  second repository copy. Copy files with `rsync -a file host:dir/`, or rsync the tree with
  excludes and a trailing slash on the source.
* In psycopg, `%` in SQL is a placeholder marker even when the params dict is empty
  (`params or {}`), so `LIKE 'zz_%'` must be written `'zz_%%'` or passed as a parameter.
* The lab Pi has a **publicly routable address**, the dashboard has no authentication and there
  was no firewall at all - nftables is now the only thing keeping 8080 off the internet.
* The Mac's `localhost:5435` is an SSH tunnel to the Pi's Postgres and the Mac's
  `localhost:8080` is the local dev server reading that database: "local" tests are production
  tests, and temporary rows have to be cleaned up (the check and load scripts do).
