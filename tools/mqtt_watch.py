"""Read-only MQTT watcher - shows whether the iSpindel really publishes.

It subscribes to <prefix>/# and prints every message, plus one compact summary
line per transmission (the 7 single-value messages that belong together).
Nothing is stored in the database - it is the "is anything coming?" tool.

    python tools/mqtt_watch.py                       # defaults from config.yml
    python tools/mqtt_watch.py --host 192.168.0.92    # a different broker
    python tools/mqtt_watch.py --host 10.0.0.5 --port 1883 --username iot --password secret
    python tools/mqtt_watch.py --count 1              # stop after 1 transmission
    python tools/mqtt_watch.py --raw                  # only raw topic = payload lines

Auth: if the broker needs a login (e.g. a public/VPS broker) pass
--username/--password, or set mqtt.username / mqtt.password in config.yml.
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load(Path(os.environ.get("ISPINDEL_CONFIG", ROOT / "config.yml")).read_text())

# which topics make up one transmission, in the order the firmware sends them
SUMMARY_FIELDS = ["tilt", "temperature", "temp_units", "battery", "gravity", "interval", "RSSI"]


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"connected to broker ({reason_code}), subscribing to {userdata['topic']}\n", flush=True)
    client.subscribe(userdata["topic"])


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    print(f"!! disconnected from broker ({reason_code}) - retrying", flush=True)


def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="replace").strip()
    stamp = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
    print(f"{stamp}  {msg.topic} = {payload}", flush=True)

    if userdata["raw"]:
        return
    parts = msg.topic.split("/")
    if len(parts) != 3:
        return
    _, name, field = parts
    burst = userdata["buffer"].setdefault(name, {"started": time.time(), "fields": {}})
    # a new transmission starts with "tilt" -> summarise the previous one
    if field == "tilt" and burst["fields"]:
        summarise(name, userdata["buffer"].pop(name), userdata)
        burst = userdata["buffer"][name] = {"started": time.time(), "fields": {}}
    burst["fields"][field] = payload


def summarise(name, burst, userdata):
    """One line per transmission - the same 7 fields the ingest turns into a row."""
    fields = burst["fields"]
    ordered = [fields[f] for f in SUMMARY_FIELDS if f in fields]
    missing = [f for f in SUMMARY_FIELDS if f not in fields]
    line = " ".join(f"{f}={fields[f]}" for f in SUMMARY_FIELDS if f in fields)
    note = f"   (missing: {', '.join(missing)})" if missing else ""
    print(f"    -> transmission from {name!r} ({len(ordered)}/7 fields): {line}{note}", flush=True)
    userdata["done"] += 1


def flush_stale(buffer, burst_seconds, userdata):
    """Transmissions whose remaining messages never arrived."""
    now = time.time()
    for name, burst in list(buffer.items()):
        if now - burst["started"] >= burst_seconds:
            summarise(name, buffer.pop(name), userdata)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=CFG["mqtt"]["host"], help="broker host/IP")
    parser.add_argument("--port", type=int, default=CFG["mqtt"]["port"], help="broker port")
    parser.add_argument("--topic", default=f"{CFG['mqtt']['topic_prefix']}/#",
                        help="topic filter to subscribe to")
    parser.add_argument("--username", default=CFG["mqtt"].get("username"))
    parser.add_argument("--password", default=CFG["mqtt"].get("password"))
    parser.add_argument("--count", type=int, default=0,
                        help="stop after N transmissions (0 = run until Ctrl-C)")
    parser.add_argument("--raw", action="store_true",
                        help="print only raw topic = payload lines (no summaries)")
    args = parser.parse_args()

    burst_seconds = float(CFG["ingest"]["burst_seconds"])
    userdata = {"topic": args.topic, "raw": args.raw, "buffer": {}, "done": 0}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ispindel-watch")
    if args.username:
        client.username_pw_set(args.username, args.password or None)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.user_data_set(userdata)

    print(f"broker {args.host}:{args.port}   topic {args.topic}\n", flush=True)
    client.connect_async(args.host, args.port, keepalive=CFG["mqtt"].get("keepalive_seconds", 120))
    client.loop_start()
    try:
        while True:
            time.sleep(1)
            if not args.raw:
                flush_stale(userdata["buffer"], burst_seconds, userdata)
            if args.count and userdata["done"] >= args.count:
                client.loop_stop()
                client.disconnect()
                return 0
    except KeyboardInterrupt:
        print("\nstopped by user")
        client.loop_stop()
        client.disconnect()
        return 0


if __name__ == "__main__":
    sys.exit(main())
