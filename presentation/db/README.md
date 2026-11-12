# ER diagrams - and why the two views exist

The data model of the iSpindel monitor is five tables plus **two views**. The tables are the
stored truth ([`sql/schema.sql`](../../sql/schema.sql:1)); the views are the read models the
dashboard queries. This folder holds the diagrams and this file justifies every view.

| File | What it is |
| --- | --- |
| `er_diagram.dot` / `.svg` / `.png` | the simple 5-table diagram for the slide |
| `er_diagram_full.dot` / `.svg` / `.png` | all tables with every column, constraint and FR reference |
| **`er_diagram_views.dot` / `.svg` / `.png`** | **the full model *including* `v_device_latest` and `v_experiment_overview`** |
| `README.md` | this file - the justification of the two views |

The older `er_diagram_full.dot` only mentioned the views in a note box. `er_diagram_views.dot`
models them as real nodes with their output columns, so the diagram answers "what does the
dashboard actually read?" and not only "what is stored?".

## Rendering

```bash
cd presentation/db
dot -Tsvg er_diagram_views.dot -o er_diagram_views.svg
dot -Tpng -Gdpi=200 er_diagram_views.dot -o er_diagram_views.png
```

Graphviz only - no Python, no database. The `.dot` file is the source; the SVG/PNG are generated
and committed so the deck builds without Graphviz installed.

`er_diagram_views.dot` is laid out for **A4 landscape** (297 x 210 mm): the stored tables run left
to right in the top row, the two views sit side by side (parallel) in the bottom row. The `size`
attribute caps the drawing at 11.69 x 8.27 in, so the SVG/PNG print on one A4 sheet without
further scaling.

## How to read the diagram

* **Solid edge with a crow-foot** = a foreign key. That data is stored.
* **Dashed violet edge** = a view reads that table. A view stores nothing; every `SELECT`
  recomputes it.
* Blue nodes are process data (`measurement`), yellow nodes are master data (`device`,
  `experiment`), grey is the optional event log, violet dashed nodes are the views.

---

# Why views at all

Three reasons, and they are the same for both views:

1. **One definition of a read model.** "The newest measurement per device" and "the experiment
   list with its measurement count" are each needed in several places - the overview cards, the
   Devices tab, the experiment table, the CSV export, the self-tests. Without a view the same
   `DISTINCT ON` / `GROUP BY` would be copy-pasted into [`main.py`](../../main.py:1) and
   [`tools/check_requirements.py`](../../tools/check_requirements.py:1) and would drift apart.
2. **The dashboard never sees raw table shapes.** The UI needs `float8` for Plotly, a boolean
   `is_active`, a `broker_label` and a `measurements` count. Those are presentation concerns; the
   tables keep `numeric`, `ended_at` and no counters. The mapping lives in the database, not in
   every callback.
3. **No duplicated state.** A view cannot get out of sync with the tables, because it *is* a query.
   A denormalized `device.last_measurement` column or a `experiment.measurement_count` column
   would need a trigger on every insert and would be wrong the moment one is missed.

Both views are plain views, **not materialized views**: the ingest writes a row every few minutes
per device and the dashboard polls (`dashboard.refresh_ms`), so a matview would have to be
refreshed on every write to stay honest - and "last seen 3 minutes ago" is exactly the value that
must never be stale. The cost is bounded by the two indexes on `measurement`
([`sql/schema.sql`](../../sql/schema.sql:86)).

---

# `v_device_latest` - one row per iSpindel, newest measurement

Defined in [`sql/schema.sql`](../../sql/schema.sql:99), last re-created by
[`sql/migrations/2026-10-29_mqtt_brokers_fr15.sql`](../../sql/migrations/2026-10-29_mqtt_brokers_fr15.sql:43).

```sql
SELECT DISTINCT ON (d.id)
       d.id AS device_id, d.mqtt_name, m.recorded_at,
       m.tilt_deg::float8, m.temp_c::float8, m.gravity_plato::float8, m.battery_v::float8,
       m.interval_s, m.rssi_dbm,
       d.broker_id, b.label AS broker_label
FROM device d
LEFT JOIN mqtt_broker b ON b.id = d.broker_id
LEFT JOIN measurement m ON m.device_id = d.id
ORDER BY d.id, m.recorded_at DESC;
```

**What it is for.** The device card: name, last tilt / temperature / gravity / battery, the
countdown to the next transmission, the broker it publishes to. That is FR-13 (last measurement
time), FR-19 (battery warning), FR-15 (broker label) and the input for the FR-20 derived values
(FG, ABV, temperature window) - all of them need *the newest row of a device*, never the history.

**Why `DISTINCT ON` and not a window function or a correlated subquery.** `DISTINCT ON (d.id)`
with `ORDER BY d.id, m.recorded_at DESC` is served by `measurement_dev_time_idx
(device_id, recorded_at DESC)` as one index scan per device - no sort of the whole `measurement`
table, no subquery per row. `row_number() OVER (PARTITION BY device_id ...)` would sort every
measurement of every device on every dashboard refresh. The price is PostgreSQL-specific syntax,
which is acceptable: PostgreSQL 16 is a fixed part of the stack, not a swappable detail.

**Why `LEFT JOIN measurement` and not `JOIN`.** The ingest creates the `device` row on the first
MQTT message, and the row is written when `RSSI` arrives. A device can therefore exist for a few
milliseconds - or, after a broker was added but the iSpindel is silent, for days - **without any
measurement**. An inner join would make that device disappear from the dashboard, which is the
opposite of what the Devices tab must show ("connected, no data yet"). With the left join the
device is listed and `recorded_at` is `NULL`; the UI renders that as "no data yet".

**Why `LEFT JOIN mqtt_broker` and not `JOIN`.** `device.broker_id IS NULL` means "the broker from
`config.yml`" (NFR-08) - and that broker deliberately has **no row** in `mqtt_broker`. An inner
join would drop every device of the own broker, i.e. the normal case. The left join keeps them and
leaves `broker_label` `NULL`, which the UI shows as the configured broker.

**Why the `::float8` casts.** `measurement` stores `numeric` (exact, no binary rounding of a
gravity value). Plotly and the Dash JSON layer want floats. Casting in the view keeps the exact
value in the table and does the lossy conversion only on the way out - and it keeps the cast in
one place instead of in every callback.

**Why `broker_id` / `broker_label` are in a *device* view.** FR-15: two participants may use the
same iSpindel name on their own brokers, so a device is only identified by `(broker, name)`. The
Devices tab has to name the broker address next to every iSpindel, otherwise the two rows are
indistinguishable. The columns were **appended** in the FR-15 migration for exactly that reason
(see the migration rule below).

**Consumers.** [`main.py`](../../main.py:510) (countdown), [`main.py`](../../main.py:577) (device
cards), [`main.py`](../../main.py:1281) (Devices tab, left-joined so a device without a
measurement still appears), [`tools/check_requirements.py`](../../tools/check_requirements.py:67)
and [`tools/ui_test.py`](../../tools/ui_test.py:244) (self-tests).

**Caveat.** The `ORDER BY` in the view only exists to make `DISTINCT ON` deterministic. Do not
rely on the row order of a `SELECT * FROM v_device_latest` - order in the query that reads it.

---

# `v_experiment_overview` - one row per experiment, with its counters

Defined in [`sql/schema.sql`](../../sql/schema.sql:114), last re-created by
[`sql/migrations/2026-10-29_mqtt_brokers_fr15.sql`](../../sql/migrations/2026-10-29_mqtt_brokers_fr15.sql:57).

```sql
SELECT e.id, e.name, d.mqtt_name AS ispindel, e.started_at, e.ended_at,
       (e.ended_at IS NULL) AS is_active,
       count(m.id) AS measurements,
       max(m.recorded_at) AS last_seen_at,
       e.beer_style, e.og_plato, e.yeast, e.responsible, e.notes,
       d.broker_id, b.label AS broker_label
FROM experiment e
JOIN device d ON d.id = e.device_id
LEFT JOIN mqtt_broker b ON b.id = d.broker_id
LEFT JOIN measurement m ON m.experiment_id = e.id
GROUP BY e.id, d.mqtt_name, d.broker_id, b.label
ORDER BY e.started_at DESC;
```

**What it is for.** The experiment table and the comparison chart's selector: name, iSpindel,
start, end, active flag, number of measurements, last measurement, and the FR-01 metadata (beer
style, OG, yeast, responsible, notes). One row per experiment, already aggregated - the dashboard
never counts measurements itself.

**Why `count(m.id)` and not `count(*)`.** With the `LEFT JOIN`, an experiment without a single
measurement still produces one row, with all `m.*` columns `NULL`. `count(*)` would report **1**
for it; `count(m.id)` ignores `NULL` and reports **0**. The number in the table has to be the
number of measurements, not the number of joined rows.

**Why `is_active` is computed and not a column.** `ended_at IS NULL` is the single source of truth
for "still running" (FR-04). A separate `status` column would be a second state that can disagree
with the timestamps - and the `EXCLUDE USING gist` constraint on `experiment`
([`sql/schema.sql`](../../sql/schema.sql:59)) already guarantees at most one open experiment per
device (FR-03/FR-09). The boolean is derived, so it cannot drift.

**Why `LEFT JOIN measurement`.** An experiment is created *before* the first transmission (start
it, then pitch the yeast). It must appear in the list immediately, with `measurements = 0` and
`last_seen_at = NULL`. An inner join would hide a freshly started experiment - the one the user
just created.

**Why `LEFT JOIN mqtt_broker`.** Same reason as in `v_device_latest`: `NULL` is the broker from
`config.yml`, which has no row. The experiment table names the broker of its iSpindel (FR-15), so
the join has to keep the `NULL` case.

**Why `GROUP BY e.id, d.mqtt_name, d.broker_id, b.label`.** `e.id` is the primary key, so every
`e.*` column is functionally dependent on it and PostgreSQL allows selecting them without listing
them. The columns of the joined tables are not dependent on `e.id` and must be named - that is
exactly the four entries in the `GROUP BY`.

**Why the aggregates are not stored.** `measurements` and `last_seen_at` change with every ingest
row. Storing them would need a trigger on `measurement` and would still be wrong after a manual
delete (FR-12 deletes a device with its measurements). The aggregate is an index-only scan on
`measurement_exp_time_idx (experiment_id, recorded_at)` - cheap enough for a table of a few dozen
experiments. If a future dataset made it slow, the answer is a materialized view refreshed by the
ingest, **not** a counter column.

**Consumers.** [`main.py`](../../main.py:1002) (the experiment table),
[`tools/check_requirements.py`](../../tools/check_requirements.py:469) (self-test of the
comparison data).

**Caveat.** The `ORDER BY e.started_at DESC` is a convenience for `SELECT *`; the dashboard sorts
in the browser anyway (AG Grid). Do not build logic on the view's row order.

---

# The migration rule both views depend on

`CREATE OR REPLACE VIEW` can only replace a view if the existing columns keep their **name,
position and type**. New columns may only be **appended**. That is why:

* the FR-01 fields (`beer_style`, `og_plato`, `yeast`, `responsible`, `notes`) were appended in
  [`2026-10-20_view_experiment_overview_fr01.sql`](../../sql/migrations/2026-10-20_view_experiment_overview_fr01.sql:9), and
* `broker_id` / `broker_label` were appended in
  [`2026-10-29_mqtt_brokers_fr15.sql`](../../sql/migrations/2026-10-29_mqtt_brokers_fr15.sql:42).

A column inserted in the middle would make the migration fail on an existing database
(`cannot change name of view column`), while a fresh install from `sql/schema.sql` would work -
the classic "works on my machine" split. Any future column goes to the **end** of the `SELECT`
list, in `schema.sql` *and* in a migration.

# What the views deliberately do not do

* **No writes.** Both are read-only; the ingest writes `device` / `measurement` directly.
* **No business logic.** No attenuation, no ABV, no "fermentation finished" - those are FR-20
  calculations in the dashboard, because they depend on `config.yml` targets
  (`expected_attenuation`, `target_temp_c`) and must not be frozen into the database.
* **No history.** `v_device_latest` returns exactly one row per device; the charts read
  `measurement` directly with a time window.
* **No security layer.** The dashboard has no authentication and runs inside the LAN; the views
  are not a permission boundary.
