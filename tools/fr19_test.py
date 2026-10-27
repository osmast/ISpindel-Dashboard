"""Browser-less test of the FR-19 status indication (Should requirement): `device_card()` is
rendered for the four device states (healthy, stale, low battery, never reported) and the tree is
checked for the green/red dot and the explanation text in the expanded half only. No database.

Run:  python tools/fr19_test.py
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main                                                        # noqa: E402

WARN_V = main.BATTERY_WARN
NOW = datetime.now(timezone.utc)
BADGE_CLASSES = "px-2 py-0.5"        # the `ui.badge()` pill - must not appear in a card

ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"{'PASS' if condition else 'FAIL'}  {label}  {detail}")


def norm(obj):
    """Dash component -> plain dicts (`to_plotly_json()` keeps children as objects)."""
    if hasattr(obj, "to_plotly_json"):
        obj = obj.to_plotly_json()
    if isinstance(obj, dict):
        return {k: norm(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [norm(v) for v in obj]
    return obj


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def props(node):
    return node.get("props", {}) if isinstance(node, dict) else {}


def card(recorded_at, interval_s, battery_v):
    """`device_card()` for one synthetic measurement - the same call the overview makes."""
    latest = {"device_id": 1, "mqtt_name": "zz_fr19_dev", "recorded_at": recorded_at,
              "tilt_deg": 45.0, "temp_c": 20.0, "gravity_plato": 12.0,
              "battery_v": battery_v, "interval_s": interval_s, "rssi_dbm": -55}
    return norm(main.device_card(latest, [], 0))


def dots(tree):
    return [n for n in walk(tree)
            if isinstance(props(n).get("className"), str)
            and "h-2.5 w-2.5" in props(n)["className"]]


def summary_json(tree):
    for n in walk(tree):
        if n.get("type") == "Summary":
            return json.dumps(n)
    return ""


CASES = [
    ("healthy", NOW - timedelta(seconds=60), 900, 3.90, "bg-emerald-500", []),
    ("stale after 3 intervals", NOW - timedelta(hours=1), 900, 3.90, "bg-red-500",
     ["no data for 60 min", "more than three intervals of 900 s"]),
    ("battery below the threshold", NOW - timedelta(seconds=60), 900, WARN_V - 0.2, "bg-red-500",
     ["battery low", f"below the {WARN_V:.2f} V threshold"]),
    ("never reported", None, None, None, "bg-red-500", ["no data yet", "not reported"]),
]

for label, recorded, interval, volts, dot_class, expected in CASES:
    tree = card(recorded, interval, volts)
    blob = json.dumps(tree)
    found = dots(tree)
    summary = summary_json(tree)
    check(f"{label}: exactly one dot", len(found) == 1, f"{len(found)} dot(s)")
    check(f"{label}: the dot is {dot_class}",
          len(found) == 1 and dot_class in props(found[0])["className"])
    check(f"{label}: the dot is in the summary (collapsed + expanded)",
          bool(found) and props(found[0])["className"] in summary)
    check(f"{label}: no badge left", BADGE_CLASSES not in blob)
    check(f"{label}: no warning text in the collapsed header",
          not any(word in summary for word in ("no data", "battery low")))
    for word in expected or ["no warning text"]:
        if expected:
            check(f"{label}: text '{word}' is shown when expanded", word in blob)
        else:
            check(f"{label}: {word}", "battery low" not in blob and "no data" not in blob)

print(f"\nRESULT: {'ALL PASS' if ok else 'FAILURES'} ({len(CASES)} states x 6 checks)")
sys.exit(0 if ok else 1)
