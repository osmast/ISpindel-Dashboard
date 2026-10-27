"""Seed clearly simulated data - one experiment, or a whole simulated fleet (``--demo``).

Everything carries the ``SIM_`` prefix (device and experiment names), so it is obvious in the UI
and easy to remove again:

    python tools/simulate.py --demo --until-now    # the 6-device fleet over four weeks
    python tools/simulate.py                       # one 7-day experiment
    python tools/simulate.py --delete              # remove every SIM_ experiment and device

The data is two sine functions (a falling S-curve for gravity, one cycle per day for the
temperature), not a model of a real fermentation.
"""
import argparse
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db                                                          # noqa: E402

PREFIX = "SIM_"
# LIKE pattern for the prefix: \_ is a literal underscore, so SIMX... is not matched
PATTERN = PREFIX.replace("_", r"\_") + "%"

INSERT = """INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                    gravity_plato, battery_v, interval_s, rssi_dbm,
                                    gravity_raw, temp_raw, temp_unit, received_at)
            VALUES (%(device)s, %(experiment)s, %(recorded_at)s, %(tilt)s, %(temp_c)s,
                    %(gravity_plato)s, %(battery_v)s, %(interval_s)s, %(rssi)s,
                    %(gravity_raw)s, %(temp_c)s, 'C', %(recorded_at)s)"""


def sg_from_plato(plato):
    """Degrees Plato -> specific gravity (the inverse of the ingest's conversion)."""
    return 1 + plato / (258.6 - 0.8795 * plato)


def delete_simulations():
    """Remove every SIM_ row: measurements first, then the experiments and devices.

    An experiment that runs **on** a SIM_ device is removed as well, even if it was named
    differently in the dashboard - otherwise the foreign key stops the device from being deleted
    (the dashboard happily starts an experiment on a simulated iSpindel).
    """
    measurements = db.execute("""DELETE FROM measurement
                                 WHERE device_id IN
                                         (SELECT id FROM device WHERE mqtt_name LIKE %(pat)s)
                                    OR experiment_id IN
                                         (SELECT id FROM experiment WHERE name LIKE %(pat)s)""",
                              {"pat": PATTERN})
    experiments = db.execute("""DELETE FROM experiment WHERE name LIKE %(pat)s
                                  OR device_id IN
                                       (SELECT id FROM device WHERE mqtt_name LIKE %(pat)s)""",
                             {"pat": PATTERN})
    devices = db.execute("DELETE FROM device WHERE mqtt_name LIKE %(pat)s", {"pat": PATTERN})
    return measurements, experiments, devices


def rows_for(start, days, interval_min, og, drop, temp_mid, temp_amp, device_id, experiment_id,
             until=None):
    """The `INSERT` parameters of one batch - two sine functions, one row per interval.

    `gravity` falls over exactly one cosine period (an S-curve), the temperature swings with the
    day, and tilt/battery/interval/RSSI get plausible values so the device card looks complete.
    `until` stops the batch at that instant (used by `--until-now`); `progress` is computed from the
    full duration either way, so a stopped batch is a cut-off fermentation, not a different curve.
    """
    duration = days * 86400
    step = interval_min * 60
    rows, elapsed = [], 0.0
    while elapsed <= duration:
        recorded_at = start + timedelta(seconds=elapsed)
        if until is not None and recorded_at > until:
            break
        # HALF a cosine period: 0 -> 1 and no way back, i.e. the falling S-curve of a fermentation.
        # With the full period the gravity returned to the OG at the end of the batch (the batch
        # card's "Rate" exposed it on 20.10.2026: a finished fermentation must not rise again).
        progress = 0.5 * (1 - math.cos(math.pi * elapsed / duration))
        gravity = og - drop * progress
        temperature = temp_mid + temp_amp * math.sin(2 * math.pi * elapsed / 86400)
        rows.append({
            "device": device_id, "experiment": experiment_id, "recorded_at": recorded_at,
            "tilt": round(30 + 35 * progress, 2),                # the spindle tilts over
            "temp_c": round(temperature, 2),
            "gravity_plato": round(gravity, 2),
            "battery_v": round(4.15 - 0.25 * progress, 3),
            "interval_s": int(interval_min * 60),
            "rssi": -60 - len(rows) % 7,
            "gravity_raw": round(sg_from_plato(gravity), 4),
        })
        elapsed += step
    return rows


def create_device(mqtt_name, display_name):
    """The device row of a simulated iSpindel (re-used if it already exists)."""
    return db.query("""INSERT INTO device (mqtt_name, display_name)
                       VALUES (%s, %s)
                       ON CONFLICT (mqtt_name) DO UPDATE
                           SET mqtt_name = EXCLUDED.mqtt_name
                       RETURNING id""", (mqtt_name, display_name))[0]["id"]


def create_experiment(name, device_id, started_at, ended_at, style, og, notes):
    """Insert one experiment and return its id. `ended_at=None` leaves it running (FR-04)."""
    return db.query("""INSERT INTO experiment (name, device_id, started_at, ended_at, beer_style,
                                               og_plato, yeast, responsible, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (name, device_id, started_at, ended_at, style, og, "SIM yeast",
                     "tools/simulate.py", notes))[0]["id"]


# ---- the demo fleet (`--demo`): 6 devices in 3 groups of two ------------------
# (group, beer style, (og, drop, temp_mid, temp_amp), ((start in days from now, duration), ...))
# The two devices of a group run almost the same fermentation - the "similar pair" for the FR-17
# comparison chart and the FR-18 relative axis - while the groups differ clearly from each other.
# Every device runs four batches of 2-5 days, placed so that the four weeks around today are covered.
DEMO_GROUPS = (
    ("A", "West Coast IPA", (15.6, 9.8, 22.0, 1.8),
     ((-13.5, 4.0), (-7.5, 3.5), (-1.5, 4.0), (6.5, 4.0))),
    ("B", "Hefeweizen", (13.4, 8.2, 19.5, 2.4),
     ((-12.5, 3.5), (-6.0, 4.5), (-0.5, 4.0), (8.0, 3.0))),
    ("C", "Bock (cold cellar)", (16.2, 6.8, 12.5, 1.2),
     ((-14.0, 5.0), (-8.5, 5.0), (-3.0, 5.0), (5.0, 5.0))),
)
# The second device of a group starts ~13 h later and ferments a little further and warmer; every
# later batch of a device drifts by a few more hours. Both stay inside their group, so a pair is
# similar but never identical - and the clamp keeps every batch within the 2-5 days.
JITTER_DEVICE = {"start": 0.55, "days": 0.35, "og": -0.35, "drop": -0.45, "temp_mid": 0.45}
JITTER_BATCH = {"start": 0.20, "days": -0.15, "og": 0.10, "drop": -0.15, "temp_mid": 0.20}
MIN_DAYS, MAX_DAYS = 2.0, 5.0


def seed_demo(interval_min, until_now=False):
    """Seed the 6-device demo fleet. Returns `(devices, experiments, measurements)`."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    devices = experiments = measurements = 0
    for group, style, curve, batches in DEMO_GROUPS:
        og, drop, temp_mid, temp_amp = curve
        for i in range(2):                                    # the two devices of the group
            device = f"{PREFIX}{group}{i + 1}"
            device_id = create_device(device, f"simulated ({device}, group {group})")
            devices += 1
            planned = [{"n": n,
                        "start": now + timedelta(days=start_day + i * JITTER_DEVICE["start"]
                                                 + n * JITTER_BATCH["start"]),
                        "days": min(MAX_DAYS, max(MIN_DAYS, days + i * JITTER_DEVICE["days"]
                                                  + n * JITTER_BATCH["days"])),
                        "og": og + i * JITTER_DEVICE["og"] + n * JITTER_BATCH["og"],
                        "drop": drop + i * JITTER_DEVICE["drop"] + n * JITTER_BATCH["drop"],
                        "temp_mid": temp_mid + i * JITTER_DEVICE["temp_mid"]
                                    + n * JITTER_BATCH["temp_mid"]}
                       for n, (start_day, days) in enumerate(batches)]
            if until_now:
                planned = [b for b in planned if b["start"] <= now]
            # The **last** batch of the device stays open (ended_at NULL, FR-04) so the card shows
            # a running fermentation and the Running tab is not empty. It has to be the last one:
            # an open experiment covers `[start, infinity)`, so the schema's exclusion constraint
            # (one experiment per device at a time) would reject any batch after it.
            open_batch = planned[-1] if planned else None
            for batch in planned:
                name = f"{device}_{batch['n'] + 1}"
                end = batch["start"] + timedelta(days=batch["days"])
                experiment_id = create_experiment(
                    name, device_id, batch["start"], None if batch is open_batch else end, style,
                    round(batch["og"], 2),
                    f"generated: group {group}, {style}, sine curves - see tools/simulate.py")
                rows = rows_for(batch["start"], batch["days"], interval_min, batch["og"],
                                batch["drop"], batch["temp_mid"], temp_amp, device_id,
                                experiment_id, until=now if until_now else None)
                with db.connect() as conn, conn.cursor() as cur:
                    cur.executemany(INSERT, rows)
                experiments += 1
                measurements += len(rows)
                print(f"  {name:10} {batch['start']:%d.%m. %H:%M} - {end:%d.%m. %H:%M} UTC  "
                      f"{batch['days']:.2f} d  {len(rows):4} rows  og {batch['og']:.2f} °P  "
                      f"{'OPEN (running)' if batch is open_batch else ''}")
    return devices, experiments, measurements


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default=f"{PREFIX}7d_sine", help="experiment name")
    parser.add_argument("--device", default=f"{PREFIX}01", help="iSpindel (MQTT) name")
    parser.add_argument("--days", type=float, default=7, help="length of the experiment in days")
    parser.add_argument("--interval", type=float, default=15, help="minutes between transmissions")
    parser.add_argument("--end", default=None, help="last transmission, ISO 8601 (default: now)")
    parser.add_argument("--og", type=float, default=14.5, help="original gravity in °P")
    parser.add_argument("--drop", type=float, default=11.0, help="gravity drop over the run in °P")
    parser.add_argument("--temp-mid", type=float, default=20.5, help="mean temperature in °C")
    parser.add_argument("--temp-amp", type=float, default=2.0, help="temperature swing in °C")
    parser.add_argument("--running", action="store_true",
                        help="leave the experiment open (it then shows in the Running tab)")
    parser.add_argument("--delete", action="store_true", help="remove every SIM_ row and exit")
    parser.add_argument("--demo", action="store_true",
                        help="seed the whole 6-device demo fleet instead of one experiment")
    parser.add_argument("--until-now", action="store_true",
                        help="with --demo: write nothing dated after now and skip the batches "
                             "that have not started (every SIM_ card then shows a real age)")
    args = parser.parse_args()

    if args.delete:
        measurements, experiments, devices = delete_simulations()
        print(f"removed {measurements} measurements, {experiments} experiments and "
              f"{devices} devices with the {PREFIX} prefix")
        return

    if args.demo:
        # a re-run replaces the fleet instead of stacking a second one on top of it
        delete_simulations()
        print(f"seeding the demo fleet: 6 devices in 3 groups, batches of 2-5 days every "
              f"{args.interval:g} min"
              f"{', nothing dated after now' if args.until_now else ''}")
        devices, experiments, measurements = seed_demo(args.interval, args.until_now)
        print(f"done: {devices} devices, {experiments} experiments, {measurements} measurements")
        print("remove it again with: python tools/simulate.py --delete")
        return

    end = datetime.fromisoformat(args.end) if args.end else datetime.now(timezone.utc)
    end = end.astimezone(timezone.utc)
    start = end - timedelta(days=args.days)

    # re-running must not stack up: drop a previous run of this experiment first
    db.execute("""DELETE FROM measurement WHERE experiment_id IN
                    (SELECT id FROM experiment WHERE name = %s)""", (args.name,))
    db.execute("DELETE FROM experiment WHERE name = %s", (args.name,))
    device_id = db.query("""INSERT INTO device (mqtt_name, display_name)
                            VALUES (%s, %s)
                            ON CONFLICT (mqtt_name) DO UPDATE
                                SET mqtt_name = EXCLUDED.mqtt_name
                            RETURNING id""",
                         (args.device, f"simulated ({args.device})"))[0]["id"]
    experiment_id = db.query("""INSERT INTO experiment
                                    (name, device_id, started_at, ended_at, beer_style, og_plato,
                                     yeast, responsible, notes)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id""",
                             (args.name, device_id, start, None if args.running else end,
                              "simulated ale", args.og, "SIM yeast", "tools/simulate.py",
                              "generated: two sine functions, see tools/simulate.py"))[0]["id"]

    rows = rows_for(start, args.days, args.interval, args.og, args.drop, args.temp_mid,
                    args.temp_amp, device_id, experiment_id)

    with db.connect() as conn, conn.cursor() as cur:
        cur.executemany(INSERT, rows)
    print(f"{args.name} on {args.device}: {len(rows)} measurements, "
          f"{start:%d.%m.%Y %H:%M} - {end:%d.%m.%Y %H:%M} UTC, every {args.interval:g} min")
    print(f"status: {'running (no end time)' if args.running else 'completed'}")
    print("remove it again with: python tools/simulate.py --delete")


if __name__ == "__main__":
    main()
