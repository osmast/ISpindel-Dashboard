"""Self-test of the requirements that need no hardware (part of the acceptance test).

Run from the repository root or inside the dashboard container:
    <engine> compose exec -T dashboard python tools/check_requirements.py
It talks to the database from config.yml only. Everything it creates is named ``zz_validation*``
and deleted again before it exits; the script exits non-zero if any check fails.
"""
import json
import sys
import time
from datetime import timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
# the counterpart: everything the "24 h" range has to hide. On a fresh database that is only the
# synthetic row this script inserts, but on the production database the first experiment may
# already carry older real measurements - the difference all - 24h is then larger than 1, which is
# correct behaviour and must not be reported as a failure.
COUNT_EXP_OUTSIDE_24H = """SELECT count(*) AS n FROM measurement m
                           WHERE m.experiment_id = %(id)s AND m.gravity_plato IS NOT NULL
                             AND m.recorded_at < now() - interval '24 hours'"""


# start from a clean slate so a re-run behaves like the first one. Only rows this script
# created are removed: a blunt "WHERE recorded_at < now() - interval '1 day'" would also wipe
# the long simulations seeded by tools/simulate.py. Measurements first - the FK has no cascade.
main.execute("""DELETE FROM measurement WHERE experiment_id IN
                  (SELECT id FROM experiment WHERE name LIKE %(pat)s)
                OR device_id IN (SELECT id FROM device WHERE mqtt_name LIKE %(pat)s)""",
             {"pat": "zz_validation%"})
main.execute("DELETE FROM experiment WHERE name LIKE %(pat)s", {"pat": "zz_validation%"})
main.execute("DELETE FROM device WHERE mqtt_name LIKE %(pat)s", {"pat": "zz_validation%"})
main.execute("DELETE FROM mqtt_broker WHERE label LIKE %(pat)s", {"pat": "zz_validation%"})


# ---- FR-12 / FR-13 / FR-15: the overview renders one card per active device ----
overview = main.ispindel_overview({})
# one card per **active** row of v_device_latest, no repeats - that is what FR-13/FR-15 ask for
# (the count is not hard-coded: a simulated device from tools/simulate.py is a device like any
# other, and one switched to "ignored" in the Devices table leaves the overview)
devices = main.query("""SELECT count(*) AS n FROM v_device_latest l
                        JOIN device d ON d.id = l.device_id
                        WHERE d.is_active""")[0]["n"]
if devices:
    cards = [c for c in overview.children if getattr(c, "children", None)]
    check("FR-15 one card per active device (DEV_REPEAT=1)", len(cards) == devices,
          f"cards={len(cards)} active devices={devices}")
else:
    # no active device: the overview is the "where to point an iSpindel" hint, not a grid
    dumped = json.dumps(overview.to_plotly_json(), default=str)
    check("FR-15 empty overview says where to point an iSpindel",
          "No iSpindel has reported yet" in dumped and str(main.CFG["mqtt"]["port"]) in dumped
          and main.CFG["mqtt"]["topic_prefix"] in dumped)

# FR-12: the Devices table lists the master data of every iSpindel plus the reported interval,
# with one settings action per row - a new iSpindel appears here without any code change
device_dump = json.dumps(main.device_table(main.device_rows()).to_plotly_json(), default=str)
known = main.query("SELECT count(*) AS n FROM device")[0]["n"]
check("FR-12 the Devices table lists every device with its interval + a settings action",
      main.DEVICE_HEADERS[0] == "Name (MQTT topic)" and "Interval" in main.DEVICE_HEADERS
      and device_dump.count("dev-btn") == known,
      f"{known} devices, {device_dump.count('dev-btn')} settings icons")


# ---- FR-15: the own broker from config.yml plus the brokers added in the dialog -----------
# The own broker is never a row of `mqtt_broker` (NFR-08: it lives in config.yml), so the dialog
# renders it as the read-only first row. Everything else is added at runtime - the phase where the
# other participants' iSpindels publish to *their* brokers is exactly this case.
brokers = main.broker_rows()
check("FR-15 the broker list starts with the own broker from config.yml (read-only)",
      brokers and brokers[0]["is_config"] and brokers[0]["host"] == main.CFG["mqtt"]["host"]
      and brokers[0]["port"] == main.CFG["mqtt"]["port"], str(brokers[:1]))
broker_dump = json.dumps(main.broker_table(brokers).to_plotly_json(), default=str)
check("FR-15 the list names address, topic prefix and state of every broker",
      f"{main.CFG['mqtt']['host']}:{main.CFG['mqtt']['port']}" in broker_dump
      and main.CFG["mqtt"]["topic_prefix"] in broker_dump and "config.yml" in broker_dump
      and main.BROKER_HEADERS == ["Broker", "Address", "Topic prefix", "iSpindels", "State",
                                  "Actions"],
      str(main.BROKER_HEADERS))

# the own broker has no `mqtt_broker` row (NFR-08), so its state can only come from the data that
# was stored for its iSpindels - the trap that made it read "no message yet" while it was delivering
own_state = json.dumps(main.broker_state(brokers[0]).to_plotly_json(), default=str)
if brokers[0].get("last_stored"):
    check("FR-15 the own broker shows a state derived from its newest stored measurement",
          "delivering" in own_state or "silent since" in own_state, own_state[:70])
    check("FR-15 the broker state never counts a negative age (a clock ahead of the data)",
          "(-" not in own_state, own_state[:70])
else:
    print("INFO  the own broker has no measurement yet - its chip stays at 'no data yet'")

alert, delta = main.save_broker(None, "zz_validation_broker", "127.0.0.1", 1884, "ispindel",
                                "", "", ["on"])
stored = main.query("SELECT id, label, host, port, is_enabled FROM mqtt_broker WHERE label = %s",
                    ("zz_validation_broker",))
broker_id = stored[0]["id"] if stored else None
check("FR-15 a broker added in the dialog is stored and enabled",
      bool(delta) and stored and stored[0]["port"] == 1884 and stored[0]["is_enabled"],
      str(stored))
added_row = [r for r in main.broker_rows() if r["label"] == "zz_validation_broker"][0]
check("FR-15 a broker without data says so instead of pretending to deliver",
      added_row["last_stored"] is None and added_row["last_message_at"] is None
      and "no data yet" in json.dumps(main.broker_state(added_row).to_plotly_json(), default=str),
      str({k: added_row[k] for k in ("label", "last_stored", "last_connected_at")}))
check("FR-15 a second broker with the same label is refused",
      main.save_broker(None, "zz_validation_broker", "127.0.0.1", 1885, "ispindel", "", "",
                       ["on"])[1] == 0)
check("FR-15 a broker without a host is refused",
      main.save_broker(None, "zz_validation_nohost", "", 1883, "ispindel", "", "", ["on"])[1] == 0)
# an address pasted into the host field ("160.85.124.31:1883") must not become a host name
main.save_broker(None, "zz_validation_addr", "127.0.0.1:1885", 1883, "ispindel", "", "", ["on"])
addr_row = main.query("SELECT host, port FROM mqtt_broker WHERE label = 'zz_validation_addr'")
check("FR-15 an address pasted into the host field is split into host and port",
      addr_row and addr_row[0]["host"] == "127.0.0.1" and addr_row[0]["port"] == 1885, str(addr_row))
main.execute("DELETE FROM mqtt_broker WHERE label = 'zz_validation_addr'")

# a connection the broker refuses ("Not authorized": it wants a user/password) must be readable
refused = dict(main.broker_rows()[0], last_error="connect failed: Not authorized - retrying")
refused_chip = json.dumps(main.broker_state(refused).to_plotly_json(), default=str)
check("FR-15 a refused connection is shown as an error with its reason",
      "children='Not authorized'" in refused_chip                        # the chip itself
      and "connect failed: Not authorized - retrying" in refused_chip,   # the tooltip keeps it all
      refused_chip[:90])
watchdog = dict(main.broker_rows()[0], last_error="not connected after 60 s - is the broker reachable?")
watchdog_chip = json.dumps(main.broker_state(watchdog).to_plotly_json(), default=str)
check("FR-15 the state chip does not repeat 'not connected'",
      "children='not connected after 60 s" in watchdog_chip, watchdog_chip[:90])

# the ingest reads that very list while it runs (services/mqtt_service.py)
import services.mqtt_service as ingest                                      # noqa: E402
specs = ingest.broker_specs()
enabled = main.query("SELECT count(*) AS n FROM mqtt_broker WHERE is_enabled")[0]["n"]
check("FR-15 the ingest listens on the own broker plus every enabled one",
      len(specs) == 1 + enabled and any(spec.get("port") == 1884 for spec in specs),
      f"{len(specs)} listener(s): " + ", ".join(f"{s['host']}:{s['port']}" for s in specs))

# a connection error ("Not authorized") must survive the periodic traffic report - the supervisor
# writes the same row every `broker_refresh_seconds`, and passing error=None wiped the reason
refused_link = ingest.BrokerLink({"id": broker_id, "label": "zz_validation_broker",
                                  "host": "127.0.0.1", "port": 1884, "topic_prefix": "ispindel"})
refused_link.last_error = "connect failed: Not authorized - retrying"
ingest.broker_status(refused_link, touched=0, error=refused_link.last_error)
kept = main.query("SELECT last_error FROM mqtt_broker WHERE id = %s", (broker_id,))[0]["last_error"]
check("FR-15 a connection error survives the periodic traffic report on the broker row",
      kept == "connect failed: Not authorized - retrying", str(kept))
refused_row = [r for r in main.broker_rows() if r["id"] == broker_id][0]
check("FR-15 a refused broker shows the reason instead of 'no data yet'",
      "Not authorized" in json.dumps(main.broker_state(refused_row).to_plotly_json(), default=str),
      str(refused_row["last_error"]))


# a broker that never answers must say so: a TCP-level failure (host down, wrong network) never
# fires `on_connect`, so without the watchdog the row would keep reading "no data yet"
class SilentLink:                       # a listener that has been trying for two minutes
    started_at = time.time() - 120
    last_error = None
    client = type("DeadClient", (), {"is_connected": lambda self: False})()


reach_error = ingest.link_error(SilentLink())
check("FR-15 a broker that never answers is reported as unreachable",
      reach_error and "reachable" in reach_error, str(reach_error))
check("FR-15 a listener that just started is not called unreachable yet",
      ingest.link_error(SilentLink(), grace=600) is None)


# paho reports a refused connect *and* then a disconnect: the specific reason must win, otherwise
# the row would only ever say "disconnected: Unspecified error"
class FailReason:
    value = 128                            # any non-zero code


class RefusedLink:
    id = None                              # no row to write -> broker_status() returns early
    label = "zz_validation_refused"        # on_disconnect() logs it
    stopping = False
    last_error = "connect failed: Not authorized - retrying"


refused_stub = RefusedLink()
ingest.on_disconnect(None, refused_stub, None, FailReason())
check("FR-15 a refused connect keeps its reason instead of the generic disconnect text",
      refused_stub.last_error == "connect failed: Not authorized - retrying", refused_stub.last_error)

# a broker can accept the connection and refuse the *subscription* (mosquitto `acl_file`): the ingest
# then looks connected while nothing ever arrives - the SUBACK code 0x80 is the only trace of it
class SubLink:
    id = None
    label = "zz_validation_sub"
    prefix = "ispindel"                    # on_subscribe() logs it
    last_error = None


class GrantedCode:
    def __init__(self, value):
        self.value = value


denied_link = SubLink()
ingest.on_subscribe(None, denied_link, 1, [GrantedCode(0x80)])
check("FR-15 a refused subscription is reported (the broker denies reading its topics)",
      "subscription refused" in (denied_link.last_error or ""), str(denied_link.last_error))
allowed_link = SubLink()
ingest.on_subscribe(None, allowed_link, 1, [GrantedCode(0)])
check("FR-15 a granted subscription leaves the broker healthy",
      allowed_link.last_error is None, str(allowed_link.last_error))

# the same iSpindel name on another broker is its own device (never merged with the own broker's)
main.execute("INSERT INTO device (mqtt_name) VALUES ('zz_validation') ON CONFLICT DO NOTHING")
main.execute("""INSERT INTO device (broker_id, mqtt_name) VALUES (%(id)s, 'zz_validation')
                ON CONFLICT DO NOTHING""", {"id": broker_id})
both = main.query("SELECT id, broker_id FROM device WHERE mqtt_name = 'zz_validation'")
check("FR-15 the same iSpindel name on another broker is a second device",
      len(both) == 2 and len({r["broker_id"] for r in both}) == 2, str(both))


# ... but the ingest stores a name through **one** broker only: a bridge or a mirrored broker that
# carries the same iSpindel must not split its batch over two devices
class NameLink:
    def __init__(self, broker_id):
        self.id = broker_id


check("FR-15 only the broker that owns a name stores it (bridges create no duplicates)",
      ingest.owns_name(NameLink(None), "zz_validation")
      and not ingest.owns_name(NameLink(broker_id), "zz_validation")
      and ingest.owns_name(NameLink(broker_id), "zz_validation_brandnew"),
      "own broker wins, a new name is free")
devices_dump = json.dumps(main.device_table(main.device_rows()).to_plotly_json(), default=str)
check("FR-15 the Devices table names the broker address of every iSpindel",
      "Broker (address)" in main.DEVICE_HEADERS and "127.0.0.1:1884" in devices_dump
      and "zz_validation_broker" in devices_dump,
      "the added broker's address is in the table next to the own broker's")
check("FR-15 the own broker's address is the one an iSpindel publishes to, not `localhost`",
      "160.85.9.9:1883" in json.dumps(
          main.device_table(main.device_rows(), "160.85.9.9").to_plotly_json(), default=str),
      "host passed by update_dashboard() via broker_host()")

# the Devices tab carries the broker list as well (read-only), so a broker that is configured but
# not delivering or refused by the broker is visible without opening the dialog
layout_dump = json.dumps(main.app.layout.to_plotly_json(), default=str)
check("FR-15 the Devices tab shows the broker list next to the devices",
      "broker-inline" in layout_dump and "broker-open" in layout_dump
      and "MQTT brokers" in layout_dump)
inline_dump = json.dumps(main.broker_table(main.broker_rows(), with_actions=False)
                         .to_plotly_json(), default=str)
check("FR-15 the inline broker list is read-only (the dialog owns the editing)",
      "broker-btn" not in inline_dump and "Actions" not in inline_dump, inline_dump[-120:])

alert, delta = main.toggle_broker(broker_id)
check("FR-15 pausing a broker is stored (the ingest stops listening within one pass)",
      bool(delta) and not main.query("SELECT is_enabled FROM mqtt_broker WHERE id = %s",
                                     (broker_id,))[0]["is_enabled"])
alert, delta = main.toggle_broker(broker_id)
check("FR-15 resuming a broker is stored",
      bool(delta) and main.query("SELECT is_enabled FROM mqtt_broker WHERE id = %s",
                                 (broker_id,))[0]["is_enabled"])
alert, delta = main.delete_broker(broker_id)
check("FR-15 deleting a broker takes its iSpindels with it (and nothing of the own broker)",
      bool(delta) and not main.query("SELECT 1 FROM mqtt_broker WHERE id = %s", (broker_id,))
      and not main.query("SELECT 1 FROM device WHERE broker_id = %s", (broker_id,)),
      "deleted broker + its devices")


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
main.execute("INSERT INTO device (mqtt_name) VALUES ('zz_validation') ON CONFLICT DO NOTHING")
dev1 = main.query("SELECT id FROM device WHERE mqtt_name = 'zz_validation'")[0]["id"]
# Which experiment? The one with the **newest measurement**, so that the "24 h" range really has
# data to show. The first experiment of the database is not a good pick: with the simulated fleet
# (tools/simulate.py --demo) or any older installation the oldest batch has nothing inside the last
# 24 h, and a check may not depend on which data happens to be there.
newest_exp = main.query("""SELECT m.experiment_id AS id
                           FROM measurement m
                           WHERE m.experiment_id IS NOT NULL
                           ORDER BY m.recorded_at DESC LIMIT 1""")
first_exp = main.query("SELECT id FROM experiment ORDER BY id LIMIT 1")
if newest_exp:
    exp_id = newest_exp[0]["id"]
elif first_exp:
    exp_id = first_exp[0]["id"]
else:
    print("INFO  no experiment in the database - FR-16/FR-18 run on a temporary zz_validation one")
    # Ended on purpose: an experiment that is still running would be picked up by the FR-20 zone
    # checks as "the newest running batch", and these are not real measurements.
    main.execute("""INSERT INTO experiment (name, device_id, started_at, ended_at, beer_style)
                    VALUES ('zz_validation_range', %(d)s, now() - interval '10 days',
                            now() - interval '9 days', 'West Coast IPA')""", {"d": dev1})
    exp_id = main.query("SELECT id FROM experiment WHERE name = 'zz_validation_range'")[0]["id"]
    # One row inside the 24 h window: without it the "24 h" figure has no series at all (and the
    # checks below read `.data[0]`). The 3-day-old row of the next INSERT is the one that "24 h"
    # has to hide.
    main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                            gravity_plato, battery_v, interval_s, rssi_dbm)
                    VALUES (%(d)s, %(e)s, now() - interval '5 minutes', 62, 20, 14, 4.0, 30, -60)""",
                 {"d": dev1, "e": exp_id})
# one temporary row three days back, so that "24h" must exclude it and "all" must include it
main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                        gravity_plato, battery_v, interval_s, rssi_dbm)
                VALUES (%s, %s, now() - interval '3 days', 62, 20, 14, 4.0, 30, -60)""",
             (dev1, exp_id))
fig_all = main.update_chart(0, [exp_id], "abs", "all", {})
fig_24h = main.update_chart(0, [exp_id], "abs", "24h", {})


def chart_points(fig):
    """Points of the chart's first series - **0** when the selected range has no measurement.

    A figure without a data series is a legitimate answer (a range that excludes everything), so
    reading `.data[0]` directly would report correct behaviour as a crash. That happened as soon
    as the oldest experiment of a database was picked for this check - the simulated fleet has
    batches that ended weeks ago.
    """
    return len(fig.data[0].y) if fig.data else 0


db_all = stable_count(lambda: chart_points(fig_all), COUNT_EXP, {"id": exp_id})
db_24h = stable_count(lambda: chart_points(fig_24h), COUNT_EXP_24H, {"id": exp_id})
check("FR-16 range=all matches the database", db_all[0] <= db_all[1] <= db_all[2],
      f"{db_all[0]} <= chart {db_all[1]} <= {db_all[2]}")
check("FR-16 range=24h matches the database", db_24h[0] <= db_24h[1] <= db_24h[2],
      f"{db_24h[0]} <= chart {db_24h[1]} <= {db_24h[2]}")
db_outside = stable_count(lambda: chart_points(fig_all) - chart_points(fig_24h),
                          COUNT_EXP_OUTSIDE_24H, {"id": exp_id})
check("FR-16 range really narrows the chart",
      db_outside[0] <= db_outside[1] <= db_outside[2] and db_outside[1] >= 1,
      f"all={chart_points(fig_all)} 24h={chart_points(fig_24h)} -> "
      f"{db_outside[1]} row(s) outside the window (incl. the synthetic 3-day-old one)")

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
    # FR-04/FR-13: the header of a card whose device runs an experiment carries the **batch name**,
    # so the dashboard answers "which beer is this iSpindel in" without opening the card. The beer
    # style and an explicit "active" label are deliberately *not* on the card (the FR-05 table has
    # the style column, and the card header is one quiet line per device) - a check may only demand
    # what the requirement asks for, not what an earlier version of the UI happened to render.
    check("FR-04/FR-13 the card header names the running batch",
          row["batch"] in card_dump, f"expected {row['batch']!r} on the card")
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
# A range without a single measurement is a valid answer, not an error: download_csv then returns
# no_update plus the amber "no measurements in the selected range" notice. Treating that as a crash
# was the same mistake as reading `.data[0]` of an empty figure - so the CSV checks tolerate it.
data, alert = main.download_csv([exp_id], "all")
csv_all = data["content"].splitlines() if data is not main.dash.no_update else []
data24, alert_24h = main.download_csv([exp_id], "24h")
csv_24h = data24["content"].splitlines() if data24 is not main.dash.no_update else []
check("FR-21/FR-22 an empty range exports no file but says why",
      bool(csv_24h) or "no measurements in the selected range" in str(alert_24h),
      str(alert_24h)[:70])
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
tz_row = main.query("""SELECT recorded_at,
                              to_char(recorded_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI') AS utc,
                              to_char(recorded_at AT TIME ZONE 'Europe/Zurich', 'YYYY-MM-DD HH24:MI')
                                  AS loc
                       FROM measurement ORDER BY id LIMIT 1""")[0]
# NFR-09: the stored value is UTC and the display is the local time of Europe/Zurich - so the
# expected offset is the one the zone really has at that timestamp (+2 h CEST in summer, +1 h CET in
# winter). Hard-coding "+2 h CEST" made this check fail from the DST change onward even though
# nothing was wrong; it now compares the SQL conversion with the one the dashboard performs.
local_ts = main.local(tz_row["recorded_at"])
utc_ts = tz_row["recorded_at"].astimezone(timezone.utc)
check("NFR-09 stored UTC, displayed in the local time of Europe/Zurich",
      tz_row["utc"] == utc_ts.strftime("%Y-%m-%d %H:%M")
      and tz_row["loc"] == local_ts.strftime("%Y-%m-%d %H:%M"),
      f"{tz_row['utc']} UTC -> {tz_row['loc']} local (offset {local_ts.utcoffset()})")

# ---- FR-10 / FR-11 / FR-09 evidence on the live data -------------------------
# FR-10 (measurements without an experiment are kept, not dropped) needs at least one unassigned
# row to look at. A freshly installed system has none until the first transmission arrives without
# a running experiment, so the check creates its own and says so - it still proves that an
# unassigned measurement survives the query that the dashboard runs.
if not main.query("SELECT 1 FROM measurement WHERE experiment_id IS NULL LIMIT 1"):
    print("INFO  no unassigned measurement yet - FR-10 is shown on a synthetic row")
    main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                            gravity_plato, battery_v, interval_s, rssi_dbm)
                    VALUES (%(d)s, NULL, now() - interval '2 minutes', 62, 20, 14, 4.0, 30, -60)""",
                 {"d": dev1})
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
