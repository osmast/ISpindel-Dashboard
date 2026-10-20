"""Self-test of the requirements that need no hardware (part of the acceptance test).

Run from the repository root, inside the "beer" environment:

    python tools/check_requirements.py

It talks to the database from config.yml (and to nothing else), so an ingest or a dashboard
running in parallel is fine. Everything it creates is named ``zz_validation*`` and deleted
again before it exits - the script exits non-zero if any check fails.

Covered: FR-01 (optional fields, required-fields-only, invalid OG), FR-02 (duplicate name),
FR-03 (iSpindel already in use), FR-04 (end stops the assignment), FR-05 (table columns),
FR-10 (unassigned rows), FR-11 (no duplicate rows), FR-13 (latest values + time of the last
measurement on the card, the three data zones), FR-15 (one card per device), FR-16 (time range
filters chart and export), FR-20 (attenuation, ABV, target FG, 24 h rate, temperature target),
FR-21/FR-22 (CSV structure and selection), NFR-05 (export feedback), NFR-06 (zone layout),
NFR-09 (UTC storage / local display).

Not covered here (needs the Pi, the real device or a person): FR-06, FR-07 with real
iSpindels, the 1 min / 30 min interval test, NFR-01 - NFR-04, NFR-06 - NFR-08, FR-20.
See memory-bank/acceptance-tests.md for those.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import main                                                        # noqa: E402

ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"{'PASS' if condition else 'FAIL'}  {label}  {detail}")


def stable_count(fn, sql, params=()):
    """The live iSpindel keeps writing while this script runs, so a count taken once can be one
    row behind the export that happens between the two queries. Count before and after and accept
    anything in between - that is the honest invariant on a production database."""
    before = main.query(sql, params)[0]["n"]
    value = fn()
    after = main.query(sql, params)[0]["n"]
    return before, value, after


COUNT_EXP = """SELECT count(*) AS n FROM measurement m
               WHERE m.experiment_id = %(id)s AND m.gravity_plato IS NOT NULL"""
COUNT_EXP_24H = """SELECT count(*) AS n FROM measurement m
                   WHERE m.experiment_id = %(id)s AND m.gravity_plato IS NOT NULL
                     AND m.recorded_at >= now() - interval '24 hours'"""


# start from a clean slate so a re-run behaves like the first one. Only rows this script
# created are removed: a blunt "WHERE recorded_at < now() - interval '1 day'" would also wipe
# the long simulations seeded by tools/simulate.py. Measurements first - the FK has no cascade.
main.execute("""DELETE FROM measurement WHERE experiment_id IN
                  (SELECT id FROM experiment WHERE name LIKE %(pat)s)
                OR device_id IN (SELECT id FROM device WHERE mqtt_name LIKE %(pat)s)""",
             {"pat": "zz_validation%"})
main.execute("DELETE FROM experiment WHERE name LIKE %(pat)s", {"pat": "zz_validation%"})
main.execute("DELETE FROM device WHERE mqtt_name LIKE %(pat)s", {"pat": "zz_validation%"})


# ---- FR-12 / FR-13 / FR-15: the overview renders one card per active device ----
overview = main.ispindel_overview({})
cards = [c for c in overview.children if getattr(c, "children", None)]
# one card per **active** row of v_device_latest, no repeats - that is what FR-13/FR-15 ask for
# (the count is not hard-coded: a simulated device from tools/simulate.py is a device like any
# other, and one switched to "ignored" in the Devices table leaves the overview)
devices = main.query("""SELECT count(*) AS n FROM v_device_latest l
                        JOIN device d ON d.id = l.device_id
                        WHERE d.is_active""")[0]["n"]
check("FR-15 one card per active device (DEV_REPEAT=1)", len(cards) == devices,
      f"cards={len(cards)} active devices={devices}")

# FR-12: the Devices table lists the master data of every iSpindel plus the reported interval,
# with one settings action per row - a new iSpindel appears here without any code change
device_dump = json.dumps(main.device_table(main.device_rows()).to_plotly_json(), default=str)
known = main.query("SELECT count(*) AS n FROM device")[0]["n"]
check("FR-12 the Devices table lists every device with its interval + a settings action",
      main.DEVICE_HEADERS[0] == "Name (MQTT topic)" and "Interval" in main.DEVICE_HEADERS
      and device_dump.count("dev-btn") == known,
      f"{known} devices, {device_dump.count('dev-btn')} settings icons")


def plain(obj):
    """Dash component -> plain dicts.

    `to_plotly_json()` only converts the **top** component: its children stay component objects, and
    `json.dumps(..., default=str)` then serialises those with Python's `repr` (single quotes, nested
    props cut off). That made a zone's `span` and the status chip's text invisible to the string
    checks below, so everything is converted recursively first.
    """
    if hasattr(obj, "to_plotly_json"):
        obj = obj.to_plotly_json()
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    return obj


def card_json(name):
    """The JSON dump of the one card whose device is called `name` (empty if there is none).

    `ensure_ascii=False`: the card text contains ° (and the values are compared as written on
    screen), and `json.dumps` would otherwise escape it to \\u00b0 and every comparison with
    `27.1 °P` would fail.
    """
    for card in cards:
        dumped = json.dumps(plain(card), default=str, ensure_ascii=False)
        if name in dumped:
            return dumped
    return ""


# FR-13: the card shows the latest values **and the time of the last measurement** - a stamp in
# local time (NFR-09), not just how old the measurement is.
newest = main.query("""SELECT l.mqtt_name, l.recorded_at, l.tilt_deg, l.temp_c, l.gravity_plato
                       FROM v_device_latest l JOIN device d ON d.id = l.device_id
                       WHERE l.recorded_at IS NOT NULL AND d.is_active
                       ORDER BY l.recorded_at DESC LIMIT 1""")
if newest:
    row = newest[0]
    card = card_json(row["mqtt_name"])
    stamp = f"{main.local(row['recorded_at']):%d.%m. %H:%M:%S}"
    check("FR-13 the card shows the time of the last measurement (local time)",
          f"last: {stamp} (" in card, f"expected 'last: {stamp} (' on {row['mqtt_name']}")
    check("FR-13 the card shows the latest values (gravity, temperature, tilt, battery)",
          f"{main.ui.num(row['gravity_plato'], 1)} °P" in card
          and f"{main.ui.num(row['temp_c'], 1)} °C" in card
          and f"tilt {main.ui.num(row['tilt_deg'], 1)}°" in card and "%" in card,
          f"expected {main.ui.num(row['gravity_plato'], 1)} °P / "
          f"{main.ui.num(row['temp_c'], 1)} °C / tilt {main.ui.num(row['tilt_deg'], 1)}°")
else:
    print("SKIP  FR-13 card check - this database has no measurement yet")

# ---- FR-16: the time range really filters ------------------------------------
# The chart is checked on the first experiment in the database. The temporary row three days
# back hangs off the zz_validation *device*, so the cleanup can find it by device - a heuristic
# like "the newest row older than 2 days" would hit the simulation instead.
exp_id = main.query("SELECT id FROM experiment ORDER BY id LIMIT 1")[0]["id"]
main.execute("INSERT INTO device (mqtt_name) VALUES ('zz_validation') ON CONFLICT DO NOTHING")
dev1 = main.query("SELECT id FROM device WHERE mqtt_name = 'zz_validation'")[0]["id"]
# one temporary row three days back, so that "24h" must exclude it and "all" must include it
main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                        gravity_plato, battery_v, interval_s, rssi_dbm)
                VALUES (%s, %s, now() - interval '3 days', 62, 20, 14, 4.0, 30, -60)""",
             (dev1, exp_id))
fig_all = main.update_chart(0, [exp_id], "abs", "all", {})
fig_24h = main.update_chart(0, [exp_id], "abs", "24h", {})
db_all = stable_count(lambda: len(fig_all.data[0].y), COUNT_EXP, {"id": exp_id})
db_24h = stable_count(lambda: len(fig_24h.data[0].y), COUNT_EXP_24H, {"id": exp_id})
check("FR-16 range=all matches the database", db_all[0] <= db_all[1] <= db_all[2],
      f"{db_all[0]} <= chart {db_all[1]} <= {db_all[2]}")
check("FR-16 range=24h matches the database", db_24h[0] <= db_24h[1] <= db_24h[2],
      f"{db_24h[0]} <= chart {db_24h[1]} <= {db_24h[2]}")
check("FR-16 range really narrows the chart", len(fig_all.data[0].y) - len(fig_24h.data[0].y) == 1,
      f"all={len(fig_all.data[0].y)} 24h={len(fig_24h.data[0].y)} (the synthetic 3-day-old row)")

# FR-16: a selected range also pins the x axis to its **whole** window, so the empty time before
# an experiment's first measurement is drawn instead of cropped away. The case that asked for
# this: "last 7 days" with an experiment that has only been running for three days has to show
# four empty days. The whole-experiment default keeps Plotly's autoscale.
fig_7d = main.update_chart(0, [exp_id], "abs", "7d", {})
window_7d = fig_7d.layout.xaxis.range or (None, None)
check("FR-16 pins the x axis to the whole selected window",
      window_7d[0] is not None
      and abs((window_7d[1] - window_7d[0]).total_seconds() - 7 * 86400) < 5,
      f"range={fig_7d.layout.xaxis.range}")
check("FR-16 entire experiment keeps the axis on autoscale",
      fig_all.layout.xaxis.range is None, f"range={fig_all.layout.xaxis.range}")
# FR-18: the relative axis counts hours since the start of each experiment, so it must NOT be
# pinned to the wall clock - it starts at 0 for every range.
check("FR-18 relative axis ignores the selected range",
      main.update_chart(0, [exp_id], "rel", "7d", {}).layout.xaxis.range is None,
      "hours-since-start must start at 0")

# NFR-06: on a phone-sized viewport the chart drops the legend and shortens the axis titles,
# so the plot area is not eaten by a legend (the `viewport` store carries the breakpoint).
fig_mobile = main.update_chart(0, [exp_id], "abs", "all", {"mobile": True})
check("NFR-06 mobile chart has no legend and just the time axis",
      fig_mobile.layout.showlegend is False and fig_mobile.layout.xaxis.title.text == "time",
      f"legend={fig_mobile.layout.showlegend} title={fig_mobile.layout.xaxis.title.text!r}")
check("FR-17/FR-18 desktop chart keeps its legend",
      fig_all.layout.showlegend is True and fig_all.layout.xaxis.title.text == "time (local)",
      f"legend={fig_all.layout.showlegend} title={fig_all.layout.xaxis.title.text!r}")

# ---- NFR-06 / FR-20: the batch card's zones and its derived values -------------
# The card of the newest **running** batch is compared with the database and with the formulas,
# recomputed here independently (so a wrong formula cannot pass its own test). Everything the zones
# show comes from the experiment (OG, beer style) plus the device's own history.
batch_row = main.query("""
    SELECT l.device_id, l.mqtt_name, l.recorded_at, l.gravity_plato::float8 AS gravity_plato,
           l.temp_c::float8 AS temp_c, e.name AS batch, e.beer_style, e.og_plato::float8 AS og
    FROM v_device_latest l
    JOIN device d ON d.id = l.device_id AND d.is_active
    JOIN experiment e ON e.device_id = l.device_id AND e.ended_at IS NULL
    ORDER BY l.recorded_at DESC LIMIT 1""")
if batch_row:
    row = batch_row[0]
    history = main.query("""SELECT recorded_at, gravity_plato::float8 AS gravity_plato
                            FROM measurement WHERE device_id = %(id)s ORDER BY recorded_at""",
                         {"id": row["device_id"]})
    card_dump = card_json(row["mqtt_name"])
    og, fg = row["og"], row["gravity_plato"]

    def sg(plato):                              # the ingest's conversion, written out again
        return 1 + plato / (258.6 - 0.8795 * plato)

    att = max(0.0, (og - fg) / og * 100)                                   # FR-20: attenuation
    abv = max(0.0, (sg(og) - sg(fg)) * 131.25)                             # FR-20: ABV
    target = og * (1 - main.EXPECTED_ATTENUATION / 100)                    # FR-20: target FG
    est = max(0.0, (sg(og) - sg(target)) * 131.25)                         # FR-20: final ABV
    check("FR-13/FR-20 the card carries the three data zones",
          all(label in card_dump for label in ("Gravity", "Temperature", "Attenuation & ABV")),
          f"batch={row['batch']}")
    check("FR-13/FR-20 the card names the batch, its beer style and the batch state",
          row["batch"] in card_dump and row["beer_style"] in card_dump and "active" in card_dump,
          f"{row['batch']} / {row['beer_style']}")
    check("FR-20 the card shows the OG and the derived target FG",
          f"(OG {main.value_text(og, ' °P')})" in card_dump
          and f"Target FG: ~{main.value_text(target, ' °P')}" in card_dump,
          f"OG {og} -> target FG {target:.2f} °P")
    check("FR-20 the card shows the gravity drop per 24 h",
          main.value_text(main.gravity_rate(history), " °P/24h") in card_dump,
          f"{main.value_text(main.gravity_rate(history), ' °P/24h')} from "
          f"{len(history)} measurements")
    check("FR-20 attenuation, ABV and the estimated final ABV match the formulas",
          f"{att:.1f}%" in card_dump and f"{abv:.1f}%" in card_dump
          and f"Est. Final: {est:.1f}% ABV" in card_dump,
          f"atten {att:.1f} %, abv {abv:.1f} %, est {est:.1f} %")
    # FR-20: the target temperature window comes from `dashboard.target_temp_c` (per beer style)
    # and the card says how far the reading is off it.
    span = main.target_temp_range(row["beer_style"])
    check("FR-20 the card shows the target temperature window of the beer style",
          f"Target: {span[0]:.1f}\u2013{span[1]:.1f} °C" in card_dump,
          f"{row['beer_style']} -> {span}")
    check("FR-20 the temperature hint names the deviation",
          main.temp_hint(row["temp_c"], span)[0] in card_dump,
          f"{row['temp_c']} °C vs {span} -> {main.temp_hint(row['temp_c'], span)[0]}")
    # NFR-06: one zone per column from `sm`, stacked full width on a phone
    check("NFR-06 the three zones stack on a phone",
          card_dump.count('"span": {"base": 12, "sm": 4}') == 3,
          f"{card_dump.count(chr(34) + 'span' + chr(34))} span(s) in the card")
else:
    print("SKIP  FR-20 zone checks - no iSpindel runs an experiment in this database")

# the boundary states of the derivation (no OG / an interrupted history) must not raise - the
# zones then show "-" instead of a number
check("FR-20 the derived values survive missing inputs",
      main.attenuation_percent(None, 12.0) is None and main.abv_percent(12.0, None) is None
      and main.target_fg(None) is None and main.gravity_rate([]) is None
      and main.temp_hint(None, [18.0, 22.0]) is None
      and main.value_text(None, " °P") == "-",
      "None in -> None out (the card renders '-')")
check("FR-20 the derived values are clamped at 0",
      main.attenuation_percent(12.0, 15.0) == 0.0 and main.abv_percent(12.0, 15.0) == 0.0,
      "a gravity above the OG (uncalibrated device) yields 0, not a negative")
check("FR-20 the temperature hint has the three states",
      main.temp_hint(25.0, [18.0, 22.0])[1] == "high"
      and main.temp_hint(10.0, [18.0, 22.0])[1] == "low"
      and main.temp_hint(20.0, [18.0, 22.0])[1] == "in",
      "high / low / in range")
check("FR-20 the target temperature window falls back to `default`",
      main.target_temp_range("West Coast IPA") == main.TARGET_TEMP_C["ipa"]
      and main.target_temp_range("Bock (cold cellar)") == main.TARGET_TEMP_C["bock"]
      and main.target_temp_range("unknown style") == main.TARGET_TEMP_C["default"]
      and main.target_temp_range(None) == main.TARGET_TEMP_C["default"],
      "matched case-insensitively by keyword, else default")


# ---- FR-01: optional fields are stored and shown -----------------------------
main.execute("""INSERT INTO device (mqtt_name) VALUES ('zz_validation'), ('zz_validation2')
                ON CONFLICT DO NOTHING""")
dev1 = main.query("SELECT id FROM device WHERE mqtt_name = 'zz_validation'")[0]["id"]
dev2 = main.query("SELECT id FROM device WHERE mqtt_name = 'zz_validation2'")[0]["id"]
msg, _ = main.create_experiment("zz_validation_exp", dev1, "", "West Coast IPA", "14.5", "US-05",
                                "Validator", "dry hopped")
row = main.query("""SELECT beer_style, og_plato, yeast, responsible, notes
                    FROM experiment WHERE name = 'zz_validation_exp'""")
stored = row[0] if row else {}
check("FR-01 optional fields stored", row and stored["beer_style"] == "West Coast IPA"
      and float(stored["og_plato"]) == 14.5 and stored["yeast"] == "US-05"
      and stored["responsible"] == "Validator" and stored["notes"] == "dry hopped",
      str(stored))
check("FR-01 green confirmation", "started" in str(msg), str(msg)[:70])
msg2, _ = main.create_experiment("zz_validation_min", dev2, "", "", None, "", "", "")
row2 = main.query("""SELECT beer_style, og_plato, yeast, responsible, notes
                     FROM experiment WHERE name = 'zz_validation_min'""")
check("FR-01 start with required fields only",
      row2 and row2[0] == {"beer_style": None, "og_plato": None, "yeast": None,
                           "responsible": None, "notes": None}, str(row2))
msg3, _ = main.create_experiment("zz_validation_bad", dev2, "", "", "fourteen", "", "", "")
check("FR-01 invalid OG rejected",
      not main.query("SELECT 1 FROM experiment WHERE name = 'zz_validation_bad'")
      and "gravity" in str(msg3), str(msg3)[:60])

# ---- FR-03: an iSpindel that already runs an experiment is rejected -----------
msg_excl, _ = main.create_experiment("zz_validation_live", dev1, "", "", "", "", "", "")
check("FR-03 second active experiment on the same iSpindel rejected",
      "already runs" in str(msg_excl), str(msg_excl)[:70])

# ---- FR-04: ending an experiment stops the assignment ------------------------
msg_end, _ = main.end_experiment(dev2)
ended = main.query("""SELECT ended_at FROM experiment
                      WHERE name = 'zz_validation_min'""")[0]["ended_at"]
check("FR-04 end time stored", ended is not None, str(ended))
check("FR-04 green confirmation", "no longer assigned" in str(msg_end), str(msg_end)[:70])
# the exact predicate the ingest uses to pick the target experiment
assigned = main.query("""SELECT count(*) AS n FROM experiment
                         WHERE device_id = %s AND ended_at IS NULL AND started_at <= now()""",
                      (dev2,))[0]["n"]
check("FR-04 no experiment claims new measurements after the end", assigned == 0)
# FR-04 also for a device without an experiment
msg_none, _ = main.end_experiment(dev2)
check("FR-04 ending twice reports 'no running experiment'",
      "no running experiment" in str(msg_none), str(msg_none)[:60])

# ---- FR-02: duplicate name (now that dev2 has no active experiment) -----------
msg4, _ = main.create_experiment("zz_validation_exp", dev2, "", "", "", "", "", "")
check("FR-02 duplicate name rejected", "unique" in str(msg4), str(msg4)[:60])


# the table shows the new columns - both tabs of the FR-05 overview share the same header
def find_props(node, types):
    """Props of every component of the given types, walking the whole component tree.

    Needed because the FR-05 overview is a `dmc.Tabs` now: its tables and tab labels are nested
    a few levels deep, so `.children.children[...]` is no longer readable.
    """
    found = []

    def walk(n):
        if hasattr(n, "to_plotly_json"):
            n = n.to_plotly_json()
        if isinstance(n, dict):
            if n.get("type") in types:
                found.append(n.get("props", {}))
            for value in n.values():
                walk(value)
        elif isinstance(n, (list, tuple)):
            for value in n:
                walk(value)

    walk(node)
    return found


tabs = main.experiment_table(main.experiment_rows())
headers = [th.get("children") for th in find_props(tabs, {"Th"})]
# FR-04 / FR-06: the Actions column follows the row state - collected as {experiment id: modes}
actions = {}
for icon in find_props(tabs, {"ActionIcon"}):
    icon_id = icon.get("id", {})
    actions.setdefault(icon_id.get("exp"), set()).add(icon_id.get("mode"))
rows = main.experiment_rows()
# robust to the column order (the panel was reordered 20.10.2026: the end timestamp moved next to
# Actions and the stamps were renamed "… Timestamp"): assert the columns are present, not their index
required = ["Name", "iSpindel", "Start Timestamp", "Status", "Measurements", "End Timestamp"]
optional = ["Beer style", "OG °P", "Yeast", "Responsible"]
check("FR-05 table has the six required columns plus the FR-01 fields",
      all(h in headers for h in required) and all(h in headers for h in optional), str(headers))
check("FR-05 rows carry the FR-06 edit / delete icons plus the FR-17/FR-21 actions",
      headers[-1] == "Actions"
      and len(find_props(tabs, {"ActionIcon"})) == 4 * len(rows)
      and all(actions.get(r["id"]) == {"chart", "csv", "edit", "delete"}
              for r in rows if not r["is_active"]),
      f"headers={headers} icons={len(find_props(tabs, {'ActionIcon'}))}")
# FR-04 / FR-06 / FR-17 / FR-21: a **running** row carries chart + csv + edit + end. The pencil is
# there (a running experiment can still be corrected - the edit never touches the end time), the
# trash is not (deleting a batch that is still filling is not what the requirement wants).
check("FR-04 the running row offers end + edit + chart + csv, but no delete",
      all(actions.get(r["id"]) == {"chart", "csv", "edit", "end"}
          for r in rows if r["is_active"]),
      f"running rows: {[sorted(actions.get(r['id']) or []) for r in rows if r['is_active']]}")
# the views are a dmc.Tabs that belongs to the static layout (not to the rebuilt table): the two
# experiment views (FR-05) plus the device master data (FR-12) as the third tab
tab_values = [t.get("value") for t in find_props(main.app.layout, {"TabsTab"})]
check("FR-05/FR-12 running, completed and devices are separate tabs of one panel",
      tab_values == ["running", "completed", "devices"]
      and len(find_props(main.app.layout, {"TabsPanel"})) == 3, str(tab_values))
# the panel of the table has no heading line any more (the two tab labels say what is shown)
check("the FR-05 panel carries no repeated heading",
      "Experiments (FR-05)" not in json.dumps(main.app.layout.to_plotly_json(), default=str))

# ---- FR-21 / FR-22 / NFR-05: export ------------------------------------------
data, alert = main.download_csv([exp_id], "all")
csv_all = data["content"].splitlines()
data24, _ = main.download_csv([exp_id], "24h")
csv_24h = data24["content"].splitlines()
check("FR-21 CSV header correct",
      csv_all[0].startswith("experiment,ispindel,timestamp_utc,timestamp_local,tilt_deg,"
                            "temperature_c,gravity_plato,battery_v,interval_s,rssi_dbm"),
      csv_all[0])
exp_all = stable_count(lambda: len(csv_all) - 1, COUNT_EXP, {"id": exp_id})
exp_24h = stable_count(lambda: len(csv_24h) - 1, COUNT_EXP_24H, {"id": exp_id})
check("FR-21 one line per measurement", exp_all[0] <= exp_all[1] <= exp_all[2],
      f"{exp_all[0]} <= lines {exp_all[1]} <= {exp_all[2]}")
check("FR-22 time range in the export", exp_24h[0] <= exp_24h[1] <= exp_24h[2],
      f"{exp_24h[0]} <= lines {exp_24h[1]} <= {exp_24h[2]}")
check("NFR-05 export feedback", "exported" in str(alert), str(alert)[:70])
no_sel, alert2 = main.download_csv([], "all")
check("NFR-05 no silent no-op without a selection", "pick at least one" in str(alert2),
      str(alert2)[:60])
tz_row = main.query("""SELECT to_char(recorded_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI') AS utc,
                              to_char(recorded_at AT TIME ZONE 'Europe/Zurich', 'YYYY-MM-DD HH24:MI')
                                  AS loc
                       FROM measurement ORDER BY id LIMIT 1""")[0]
check("NFR-09 stored UTC, displayed Europe/Zurich (+2 h CEST)",
      abs(int(tz_row["loc"][-5:-3]) - int(tz_row["utc"][-5:-3])) == 2, str(tz_row))

# ---- FR-10 / FR-11 / FR-09 evidence on the live data -------------------------
stats = main.query("""SELECT
        (SELECT count(*) FROM measurement) AS rows,
        (SELECT count(*) FROM measurement WHERE experiment_id IS NULL) AS unassigned,
        (SELECT count(*) FROM (SELECT recorded_at FROM measurement
                               GROUP BY recorded_at, device_id
                               HAVING count(*) > 1) d) AS duplicates,
        (SELECT count(*) FROM (SELECT device_id, recorded_at FROM measurement
                               GROUP BY device_id, recorded_at
                               HAVING count(DISTINCT experiment_id) > 1) d) AS double_assigned,
        -- FR-03/FR-09: two experiments of the *same* device must never overlap. The schema's
        -- exclusion constraint should make this 0 - the check proves it is really installed.
        --
        -- Both groupings are **device-aware** on purpose: two iSpindels may transmit in the same
        -- second, so a global GROUP BY recorded_at reports a conflict that does not exist. It did,
        -- as soon as tools/simulate.py --demo put six devices on one 15 minute grid.
        (SELECT count(*) FROM experiment a JOIN experiment b
           ON a.device_id = b.device_id AND a.id < b.id
          AND tstzrange(a.started_at, COALESCE(a.ended_at, 'infinity')) &&
              tstzrange(b.started_at, COALESCE(b.ended_at, 'infinity'))) AS overlapping,
        -- only real transmissions: the synthetic 3-day-old row of this script is excluded
        (SELECT max(received_at - recorded_at) FROM measurement
         WHERE recorded_at > now() - interval '1 day') AS max_lag""")[0]
check("FR-10 unassigned measurements are kept", stats["unassigned"] > 0, str(stats["unassigned"]))
check("FR-11 no duplicate rows", stats["duplicates"] == 0)
check("FR-09 no measurement in two experiments", stats["double_assigned"] == 0)
check("FR-03/FR-09 no two experiments of one iSpindel overlap", stats["overlapping"] == 0,
      f"{stats['overlapping']} overlapping pairs")
print(f"      info: {stats['rows']} rows, max ingest lag {stats['max_lag']}")

# ---- cleanup -----------------------------------------------------------------
# the temporary 3-day-old row hangs off the zz_validation device, so it goes with it
main.execute("""DELETE FROM measurement WHERE experiment_id IN
                  (SELECT id FROM experiment WHERE name LIKE %(pat)s)
                OR device_id IN (SELECT id FROM device WHERE mqtt_name LIKE %(pat)s)""",
             {"pat": "zz_validation%"})
main.execute("DELETE FROM experiment WHERE name LIKE %(pat)s", {"pat": "zz_validation%"})
main.execute("DELETE FROM device WHERE mqtt_name LIKE %(pat)s", {"pat": "zz_validation%"})
left = main.query("SELECT count(*) AS n FROM experiment WHERE name LIKE %(pat)s",
                  {"pat": "zz_validation%"})[0]["n"]
dev_left = main.query("SELECT count(*) AS n FROM device WHERE mqtt_name LIKE %(pat)s",
                      {"pat": "zz_validation%"})[0]["n"]
print(f"      cleanup: {left} validation experiments and {dev_left} validation devices left")
print("\nRESULT:", "ALL PASS" if ok else "FAILURES - see above")
sys.exit(0 if ok else 1)
