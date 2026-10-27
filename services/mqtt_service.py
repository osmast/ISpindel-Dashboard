"""Minimal iSpindel -> PostgreSQL ingest service.

The stock firmware publishes one MQTT message per value (no JSON, no timestamp) under
ispindel/<name>/<field>: tilt, temperature, temp_units, battery, gravity, interval, RSSI.
The seven messages of one transmission arrive within milliseconds; `tilt` comes first and
`RSSI` last, so the row is written when `RSSI` arrives - one row per transmission (FR-11) with
`recorded_at` = time of receipt (the payload carries no time). The next `tilt` and
`burst_seconds` are only fallbacks for lost or late messages.

Run:  python mqtt_service.py
"""
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import psycopg
import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load(Path(os.environ.get("ISPINDEL_CONFIG", ROOT / "config.yml")).read_text())
MQTT_CFG = CFG["mqtt"]
ING = CFG["ingest"]
# NFR-08: config.yml holds the settings; these variables only override single values (compose).
CFG["database"]["dsn"] = os.environ.get("ISPINDEL_DB_DSN", CFG["database"]["dsn"])
MQTT_CFG["host"] = os.environ.get("ISPINDEL_MQTT_HOST", MQTT_CFG["host"])
MQTT_CFG["port"] = int(os.environ.get("ISPINDEL_MQTT_PORT", MQTT_CFG["port"]))
MQTT_CFG["client_id"] = os.environ.get("ISPINDEL_MQTT_CLIENT_ID",
                                       MQTT_CFG.get("client_id", "ispindel-ingest"))
TOPIC = f"{MQTT_CFG['topic_prefix']}/+/+"
KEEPALIVE = MQTT_CFG.get("keepalive_seconds", 120)

# The topics of one transmission, in the order the firmware sends them (RSSI last).
BURST_FIELDS = ("tilt", "temperature", "temp_units", "battery", "gravity", "interval", "RSSI")

log = logging.getLogger("ingest")
buffer = {}          # device name -> {"started": float, "fields": {field: raw string}}
conn = None          # PostgreSQL connection, reopened on demand

INSERT_SQL = """
WITH d AS (
    INSERT INTO device (mqtt_name) VALUES (%(name)s)
    ON CONFLICT (mqtt_name) DO UPDATE SET mqtt_name = EXCLUDED.mqtt_name
    RETURNING id
)
INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                         gravity_plato, battery_v, interval_s, rssi_dbm,
                         gravity_raw, temp_raw, temp_unit)
SELECT d.id, e.id, %(recorded_at)s, %(tilt)s, %(temp_c)s,
       %(plato)s, %(battery)s, %(interval)s, %(rssi)s,
       %(gravity_raw)s, %(temp_raw)s, %(temp_unit)s
FROM d
LEFT JOIN experiment e
       ON e.device_id = d.id
      AND e.ended_at IS NULL
      AND e.started_at <= %(recorded_at)s
ON CONFLICT (device_id, recorded_at) DO NOTHING
RETURNING experiment_id
"""


def plato_from_sg(sg):
    """Specific gravity -> degrees Plato."""
    return 258.6 * (sg - 1) / (0.8795 * (sg - 1) + 1)


def to_celsius(value, unit):
    unit = (unit or "C").strip().upper()[:1]
    if unit == "F":
        return (value - 32) * 5 / 9
    if unit == "K":
        return value - 273.15
    return value


def build_row(name, fields, started):
    def num(key):
        try:
            return float(fields[key])
        except (KeyError, ValueError):
            return None

    temp_unit = fields.get("temp_units", "C")
    temp_raw = num("temperature")
    gravity_raw = num("gravity")
    plato = gravity_raw
    if gravity_raw is not None and str(ING["gravity_unit"]).upper().startswith("S"):
        plato = plato_from_sg(gravity_raw)
    interval = num("interval")
    rssi = num("RSSI")
    return {
        "name": name,
        "recorded_at": datetime.fromtimestamp(started, timezone.utc),
        "tilt": num("tilt"),
        "temp_c": None if temp_raw is None else to_celsius(temp_raw, temp_unit),
        "plato": plato,
        "battery": num("battery"),
        "interval": None if interval is None else int(interval),
        "rssi": None if rssi is None else int(rssi),
        "gravity_raw": gravity_raw,
        "temp_raw": temp_raw,
        "temp_unit": temp_unit,
    }


def on_connect(client, userdata, flags, reason_code, properties=None):
    log.info("MQTT connected (%s), subscribing to %s", reason_code, TOPIC)
    client.subscribe(TOPIC)


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    # paho reconnects by itself (loop_start) - log it so gaps are visible in the log
    log.warning("MQTT disconnected (%s) - reconnecting", reason_code)


def get_conn():
    global conn
    if conn is None or conn.closed:
        conn = psycopg.connect(CFG["database"]["dsn"], autocommit=True)
    return conn


def store(name, burst):
    """Write exactly one measurement row for one transmission (FR-11)."""
    global conn
    row = build_row(name, burst["fields"], burst["started"])
    try:
        with get_conn().cursor() as cur:
            cur.execute(INSERT_SQL, row)
            result = cur.fetchone()
        log.info("stored %s: %.2f °P / %.2f °C -> %s",
                 name, row["plato"] or 0, row["temp_c"] or 0,
                 f"experiment {result[0]}" if result else "duplicate, ignored")
    except psycopg.Error as exc:                 # e.g. the Pi lost the database
        log.error("database error for %s: %s", name, exc)
        conn = None                              # reconnect on the next measurement


def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if len(parts) != 3:
        return
    _, name, field = parts
    payload = msg.payload.decode(errors="replace").strip()
    if ING["log_messages"]:
        print(f"  {msg.topic} = {payload}", flush=True)

    burst = buffer.get(name)
    # a new "tilt" ends the previous transmission (FR-11 holds for any interval)
    if field == "tilt" and burst and burst["fields"]:
        store(name, buffer.pop(name))
        burst = None
    if burst is None:
        burst = buffer[name] = {"started": time.time(), "fields": {}}
    burst["fields"][field] = payload
    # complete as soon as RSSI arrived: write now so recorded_at stays within milliseconds
    if all(f in burst["fields"] for f in BURST_FIELDS):
        store(name, buffer.pop(name))


def flush_stale():
    """Safety net: write a transmission whose remaining messages never arrived."""
    now = time.time()
    for name, burst in list(buffer.items()):
        if now - burst["started"] >= ING["burst_seconds"]:
            store(name, buffer.pop(name))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # The client id must be unique per broker, or two clients kick each other off (config.yml).
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=MQTT_CFG.get("client_id", "ispindel-ingest"),
                         clean_session=False)
    if MQTT_CFG.get("username"):
        client.username_pw_set(MQTT_CFG["username"], MQTT_CFG.get("password"))
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(MQTT_CFG["host"], MQTT_CFG["port"], keepalive=KEEPALIVE)
    client.loop_start()
    log.info("ingest running, waiting for messages on %s", TOPIC)
    try:
        while True:
            time.sleep(1)
            flush_stale()
    except KeyboardInterrupt:
        log.info("stopped by user")
    finally:
        client.loop_stop()


if __name__ == "__main__":
    main()
