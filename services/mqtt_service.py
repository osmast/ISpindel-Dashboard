"""iSpindel -> PostgreSQL ingest service, one listener per MQTT broker.

The stock firmware publishes one MQTT message per value (no JSON, no timestamp) under
ispindel/<name>/<field>: tilt, temperature, temp_units, battery, gravity, interval, RSSI.
The seven messages of one transmission arrive within milliseconds; `tilt` comes first and
`RSSI` last, so the row is written when `RSSI` arrives - one row per transmission (FR-11) with
`recorded_at` = time of receipt (the payload carries no time). The next `tilt` and
`burst_seconds` are only fallbacks for lost or late messages.

FR-15: during the fermentation phase the participants each run *their own* broker, so the service
listens on all of them at the same time: the broker from `config.yml` (NFR-08) plus every enabled
row of the `mqtt_broker` table, which the dashboard's "MQTT brokers" dialog fills at runtime. One
paho client per broker, each with its own client id - two clients sharing an id kick each other
off the broker - and its own burst buffer. A supervisor re-reads the table every
`ingest.broker_refresh_seconds`, so a broker added in the dialog starts delivering without a
restart; connection state and traffic are written back to that table for the dialog to show.

Run:  python -u services/mqtt_service.py
"""
import logging
import os
import threading
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
KEEPALIVE = MQTT_CFG.get("keepalive_seconds", 120)
# FR-15: how often the supervisor re-reads `mqtt_broker` (config.yml). 0 = only at startup.
BROKER_REFRESH = ING.get("broker_refresh_seconds", 10)

# The topics of one transmission, in the order the firmware sends them (RSSI last).
BURST_FIELDS = ("tilt", "temperature", "temp_units", "battery", "gravity", "interval", "RSSI")

log = logging.getLogger("ingest")
# One connection for the whole service. Several paho network threads write through it (one per
# broker), so every use goes through LOCK - including `get_conn()`'s lazy reconnect.
conn = None
LOCK = threading.RLock()

# FR-15: the device belongs to the broker it published to, so the same iSpindel name on two
# brokers stays two devices. The conflict target is the expression index from sql/schema.sql.
INSERT_SQL = """
WITH d AS (
    INSERT INTO device (broker_id, mqtt_name) VALUES (%(broker_id)s, %(name)s)
    ON CONFLICT ((COALESCE(broker_id, 0)), mqtt_name)
        DO UPDATE SET mqtt_name = EXCLUDED.mqtt_name
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


def build_row(link, name, fields, started):
    """One measurement row of `link`'s broker. `broker_id` None = the broker from config.yml."""
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
        "broker_id": link.id,
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


def spec_target(spec):
    """The part of a broker entry that needs a new connection when it changes."""
    return (spec["host"], int(spec["port"]), spec.get("username") or None,
            spec.get("password") or None, spec.get("topic_prefix") or "ispindel")


def _ok(reason_code):
    """True when a paho reason code means success (API-v2 object or plain int)."""
    return getattr(reason_code, "value", reason_code) == 0


class BrokerLink:
    """One MQTT connection: subscribes to <prefix>/+/+ and stores what arrives (FR-7 - FR-11).

    One instance per broker - the one from `config.yml` (`id is None`) plus every enabled
    `mqtt_broker` row (FR-15) - each with its own paho client, client id, topic prefix, burst
    buffer and last error. `messages` counts what arrived since the last supervisor pass, so the
    dashboard can see that a broker really delivers.
    """

    def __init__(self, spec):
        self.id = spec.get("id")                    # None = the broker from config.yml
        self.label = spec.get("label") or "own broker (config.yml)"
        self.target_key = spec_target(spec)
        self.host, self.port, self.username, self.password, self.prefix = self.target_key
        # the client id must differ per broker: two clients sharing one id kick each other off
        self.client_id = (f"{MQTT_CFG.get('client_id', 'ispindel-ingest')}"
                          + (f"-b{self.id}" if self.id else ""))
        self.buffer = {}        # device name -> {"started": float, "fields": {field: raw string}}
        self.messages = 0       # transmissions since the last supervisor pass
        self.stopping = False   # set by stop(): a deliberate close is not a connection loss
        self.last_error = None
        self.client = None

    def start(self):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id,
                             clean_session=False, userdata=self)
        if self.username:
            client.username_pw_set(self.username, self.password)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        # connect_async + loop_start: a broker that does not answer must never block the service
        client.connect_async(self.host, self.port, keepalive=KEEPALIVE)
        client.loop_start()
        self.client = client
        log.info("[%s] listening on %s/%s/%s (%s:%s) as %s", self.label, self.prefix, "+", "+",
                 self.host, self.port, self.client_id)

    def stop(self):
        if self.client is None:
            return
        self.stopping = True
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception as exc:            # a broker that never answered cannot be disconnected
            log.debug("[%s] disconnect: %s", self.label, exc)
        self.client = None


def on_connect(client, userdata, flags, reason_code, properties=None):
    link = userdata
    if _ok(reason_code):
        link.last_error = None
        log.info("[%s] MQTT connected (%s), subscribing to %s/+/+",
                 link.label, reason_code, link.prefix)
        client.subscribe(f"{link.prefix}/+/+")
    else:
        link.last_error = f"connect failed: {reason_code}"
        log.warning("[%s] %s - retrying", link.label, link.last_error)
    broker_status(link, connected=_ok(reason_code), error=link.last_error)


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    link = userdata
    if link.stopping:                       # we closed it: the broker was removed or changed
        log.info("[%s] connection closed (broker removed or changed)", link.label)
        return
    # paho reconnects by itself (loop_start) - log it so gaps are visible in the log
    if not _ok(reason_code):                # a deliberate stop (reason 0) is not an error
        link.last_error = f"disconnected: {reason_code}"
    log.warning("[%s] MQTT disconnected (%s) - reconnecting", link.label, reason_code)
    broker_status(link, error=link.last_error)


def get_conn():
    global conn
    if conn is None or conn.closed:
        conn = psycopg.connect(CFG["database"]["dsn"], autocommit=True)
    return conn


def db_query(sql, params=None):
    """Read helper for the service's own bookkeeping - the broker list (FR-15)."""
    with LOCK:
        with get_conn().cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def broker_status(link, connected=False, error=None, touched=False):
    """Report one broker's state back to `mqtt_broker`; the dashboard's dialog shows it (FR-15).

    Only brokers that exist as a row are written - the broker of config.yml has none - and a
    database hiccup is logged, never raised: it must not kill an MQTT callback.
    """
    if link.id is None:
        return
    with LOCK:
        try:
            with get_conn().cursor() as cur:
                cur.execute("""UPDATE mqtt_broker SET
                                   last_connected_at = CASE WHEN %(connected)s THEN now()
                                                            ELSE last_connected_at END,
                                   last_message_at   = CASE WHEN %(touched)s THEN now()
                                                            ELSE last_message_at END,
                                   last_error        = %(error)s
                               WHERE id = %(id)s""",
                            {"id": link.id, "connected": bool(connected),
                             "touched": bool(touched), "error": error})
        except psycopg.Error as exc:
            log.error("[%s] cannot store the broker state: %s", link.label, exc)


def store(link, name, burst):
    """Write exactly one measurement row for one transmission (FR-11).

    Called from the network thread of that broker and from `flush_stale()` in the main thread,
    so every database access goes through LOCK. `broker_id` travels in the row: the device is
    created for the broker it published to (FR-15).
    """
    global conn
    row = build_row(link, name, burst["fields"], burst["started"])
    with LOCK:
        try:
            with get_conn().cursor() as cur:
                cur.execute(INSERT_SQL, row)
                result = cur.fetchone()
        except psycopg.Error as exc:             # e.g. the Pi lost the database
            log.error("database error for %s: %s", name, exc)
            conn = None                          # reconnect on the next measurement
            return
    link.messages += 1
    log.info("stored %s%s: %.2f °P / %.2f °C -> %s", name,
             f" [{link.label}]" if link.id else "", row["plato"] or 0, row["temp_c"] or 0,
             f"experiment {result[0]}" if result else "duplicate, ignored")


def on_message(client, userdata, msg):
    link = userdata
    parts = msg.topic.split("/")
    if len(parts) != 3:
        return
    _, name, field = parts
    payload = msg.payload.decode(errors="replace").strip()
    if ING["log_messages"]:
        print(f"  [{link.label}] {msg.topic} = {payload}", flush=True)

    burst = link.buffer.get(name)
    # a new "tilt" ends the previous transmission (FR-11 holds for any interval)
    if field == "tilt" and burst and burst["fields"]:
        link.buffer.pop(name, None)
        store(link, name, burst)
        burst = None
    if burst is None:
        burst = link.buffer[name] = {"started": time.time(), "fields": {}}
    burst["fields"][field] = payload
    # complete as soon as RSSI arrived: write now so recorded_at stays within milliseconds
    if all(f in burst["fields"] for f in BURST_FIELDS):
        link.buffer.pop(name, None)
        store(link, name, burst)


def flush_stale(links):
    """Safety net: write a transmission whose remaining messages never arrived."""
    now = time.time()
    for link in links.values():
        for name, burst in list(link.buffer.items()):
            if now - burst["started"] >= ING["burst_seconds"] and link.buffer.pop(name, None):
                store(link, name, burst)


def broker_specs():
    """The brokers to listen on (FR-15).

    The broker of `config.yml` (NFR-08) plus every enabled `mqtt_broker` row - the ones the
    dashboard's dialog added. A database hiccup must not tear down the running listeners, so an
    unreadable list just returns what config.yml says.
    """
    specs = [{"id": None, "label": "own broker (config.yml)",
              "host": MQTT_CFG["host"], "port": MQTT_CFG["port"],
              "username": MQTT_CFG.get("username"), "password": MQTT_CFG.get("password"),
              "topic_prefix": MQTT_CFG.get("topic_prefix", "ispindel")}]
    try:
        specs += db_query("""SELECT id, label, host, port, username, password, topic_prefix
                             FROM mqtt_broker WHERE is_enabled ORDER BY id""")
    except psycopg.Error as exc:
        log.error("cannot read the broker list, keeping the current listeners: %s", exc)
    return specs


def sync_links(links):
    """Connect/disconnect so the running listeners match the broker list (FR-15).

    A broker that was added starts listening, one that was edited, disabled or deleted is closed.
    An unreachable broker stays in the list and paho keeps retrying in the background.
    """
    wanted = {spec["id"]: spec for spec in broker_specs()}
    for key, link in list(links.items()):
        spec = wanted.get(key)
        if spec is None or link.target_key != spec_target(spec):
            log.info("[%s] broker changed or removed - closing the connection", link.label)
            link.stop()
            links.pop(key)
    for key, spec in wanted.items():
        if key not in links:
            links[key] = BrokerLink(spec)
            links[key].start()
    return links


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    links = {}
    log.info("ingest starting - own broker %s:%s, broker list re-read every %s s (FR-15)",
             MQTT_CFG["host"], MQTT_CFG["port"], BROKER_REFRESH)
    try:
        next_pass = 0.0
        while True:
            if time.time() >= next_pass:
                links = sync_links(links)
                for link in links.values():      # tell the dashboard that data is flowing
                    broker_status(link, touched=link.messages)
                    link.messages = 0
                # broker_refresh_seconds = 0 means "read the list once, at startup"
                next_pass = time.time() + BROKER_REFRESH if BROKER_REFRESH > 0 else float("inf")
            time.sleep(1)
            flush_stale(links)
    except KeyboardInterrupt:
        log.info("stopped by user")
    finally:
        for link in links.values():
            link.stop()


if __name__ == "__main__":
    main()
