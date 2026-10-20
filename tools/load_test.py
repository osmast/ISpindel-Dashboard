"""NFR-07 load test: build a fermentation-like volume, time a full dashboard refresh, check that a
brand-new measurement is already in the chart (FR-14), then remove everything again.

    python tools/load_test.py         # on the Pi (or on the Mac through the 5435 SSH tunnel)

It creates 2 experiments x 960 measurements (10 days at a 15 minute interval, i.e. what the
fermentation phase will look like) on temporary devices named ``zz_load*`` and deletes them at the
end - the real measurements are never touched. Measured 20.10.2026 on the Raspberry Pi:
device cards 642 ms, experiment table 50 ms, comparison chart 203 ms (relative axis 272 ms),
CSV export 142 ms -> 1310 ms for a full refresh, against the NFR-07 limit of 5000 ms.
"""
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))
import main  # noqa: E402

NAMES = ("zz_load_a", "zz_load_b")
# ---- build the load: 2 experiments x 960 rows = 10 days at a 15 minute interval ----
main.execute("DELETE FROM measurement WHERE experiment_id IN "
             "(SELECT id FROM experiment WHERE name LIKE 'zz_load%%')")
main.execute("DELETE FROM experiment WHERE name LIKE 'zz_load%%'")
main.execute("DELETE FROM device WHERE mqtt_name LIKE 'zz_load%%'")

ids, dev_ids = [], []
for name in NAMES:
    main.execute("INSERT INTO device (mqtt_name) VALUES (%s)", (name,))
    dev = main.query("SELECT id FROM device WHERE mqtt_name = %s", (name,))[0]["id"]
    dev_ids.append(dev)
    main.execute("""INSERT INTO experiment (name, device_id, started_at, ended_at, beer_style, og_plato)
                    VALUES (%s, %s, now() - interval '11 days', now() - interval '1 day', 'IPA', 14.5)""",
                 (name, dev))
    eid = main.query("SELECT id FROM experiment WHERE name = %s", (name,))[0]["id"]
    ids.append(eid)
    main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                             gravity_plato, battery_v, interval_s, rssi_dbm)
                    SELECT %s, %s, now() - interval '10 days' + (n || ' minutes')::interval * 15,
                           60 - n / 40.0, 20 + (n %% 7) / 3.0, 14.5 * (0.995 ^ n), 3.9, 900, -60
                    FROM generate_series(1, 960) n""", (dev, eid))

rows = main.query("SELECT count(*) n FROM measurement WHERE experiment_id = ANY(%s)", (ids,))[0]["n"]
print(f"synthetic load: {rows} measurements in {len(ids)} experiments "
      f"(10 days, 15 min interval, 2 iSpindels)")

# ---- NFR-07: the work one dashboard refresh performs ----
total = 0.0
for label, fn in [("device cards (ispindel_overview)", lambda: main.ispindel_overview({})),
                  ("experiment table (FR-05)",
                   lambda: main.experiment_table(main.experiment_rows())),
                  ("chart: 2 experiments, entire duration (FR-16/17)",
                   lambda: main.update_chart(0, ids, "abs", "all", {})),
                  # FR-16 with a fixed range: this path also reads the window bounds
                  # (`chart_window()` -> one `SELECT now()`) before it builds the figure
                  ("chart: 2 experiments, last 7 days (FR-16)",
                   lambda: main.update_chart(0, ids, "abs", "7d", {})),
                  ("chart: relative axis (FR-18)", lambda: main.update_chart(0, ids, "rel", "all", {})),
                  ("chart: mobile viewport (NFR-06)",
                   lambda: main.update_chart(0, ids, "abs", "all", {"mobile": True})),
                  ("CSV export (FR-21)", lambda: main.download_csv(ids, "all"))]:
    t = time.perf_counter()
    fn()
    ms = (time.perf_counter() - t) * 1000
    total += ms
    print(f"  {label}: {ms:.0f} ms")
print(f"  TOTAL full refresh: {total:.0f} ms   (NFR-07 limit 5000 ms)")

# ---- FR-14: is a measurement that was just stored already in the chart? ----
main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                         gravity_plato, battery_v)
                VALUES (%s, %s, now(), 61.5, 20.4, 3.4, 3.85)""", (dev_ids[0], ids[0]))
newest = main.query("SELECT max(recorded_at) m FROM measurement WHERE experiment_id = %s",
                    (ids[0],))[0]["m"]
fig = main.update_chart(0, [ids[0]], "abs", "all", {})
print(f"FR-14 newest row: {newest:%H:%M:%S}   last chart point: {fig.data[0].x[-1]:%H:%M:%S}   "
      f"-> {'the chart shows the newest measurement' if fig.data[0].x[-1] == newest else 'MISSING'}")

# ---- cleanup ----
main.execute("DELETE FROM measurement WHERE experiment_id = ANY(%s)", (ids,))
main.execute("DELETE FROM experiment WHERE name LIKE 'zz_load%%'")
main.execute("DELETE FROM device WHERE mqtt_name LIKE 'zz_load%%'")
left = main.query("""SELECT (SELECT count(*) FROM measurement WHERE experiment_id = ANY(%s)) m,
                            (SELECT count(*) FROM device WHERE mqtt_name LIKE 'zz_load%%') d,
                            (SELECT count(*) FROM measurement) total""", (ids,))[0]
print(f"cleanup: {left['m']} synthetic measurements, {left['d']} synthetic devices left; "
      f"real measurements still in the database: {left['total']}")
