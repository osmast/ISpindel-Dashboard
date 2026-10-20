"""Simulates an iSpindel: publishes exactly the same 7 topics as the real firmware.

Use it to test ingest + dashboard without hardware:
    python tools/fake_spindel.py --interval 5 --count 10
"""
import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load(Path(os.environ.get("ISPINDEL_CONFIG", ROOT / "config.yml")).read_text())


def sg_from_plato(plato):
    """Degrees Plato -> specific gravity (the iSpindel polynomial usually outputs SG)."""
    return 1 + plato / (258.6 - 0.8795 * plato)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="iSpindel_test", help="device name (MQTT topic)")
    parser.add_argument("--interval", type=float, default=5, help="seconds between transmissions")
    parser.add_argument("--count", type=int, default=0, help="number of transmissions, 0 = forever")
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fake-spindel")
    client.connect(CFG["mqtt"]["host"], CFG["mqtt"]["port"])
    client.loop_start()

    i = 0
    while args.count == 0 or i < args.count:
        plato = 14.0 * (0.97 ** i)                     # falling extract
        values = {
            "tilt": f"{62 - 3.0 * i:.2f}",             # the spindle tilts as it ferments
            "temperature": f"{20.0 + 0.3 * (i % 3):.2f}",
            "temp_units": "C",
            "battery": f"{4.05 - 0.005 * i:.3f}",
            "gravity": f"{sg_from_plato(plato):.4f}",
            "interval": str(int(args.interval)),
            "RSSI": str(-55 - (i % 10)),
        }
        for field, value in values.items():
            client.publish(f"{CFG['mqtt']['topic_prefix']}/{args.name}/{field}", value)
        print(f"{datetime.now(timezone.utc):%H:%M:%S} sent {values}", flush=True)
        i += 1
        time.sleep(args.interval)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
