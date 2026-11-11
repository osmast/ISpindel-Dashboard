#!/usr/bin/env python3
"""Plot the real fermentation data of all four batches.

Run:  python presentation/plot_fermentation.py
In:   presentation/data/*.csv   (FR-21 exports from the live dashboard)
Out:  presentation/plots/mango_fermentation.png   (all four batches)
      presentation/plots/mango_duration.png       (Mango: UI end vs. real end)

The top panel overlays the gravity of all four batches, the bottom panel their
temperature. Mango Maracuya Dream is highlighted because it is the beer the
presentation interprets in detail; the other three are the comparison batches.

A final tilt of ~89 deg means the iSpindel was taken out of the fermenter. Those
points are drawn as X markers, not connected to the fermentation curve.
"""

import csv
import datetime as dt
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT_DIR = os.path.join(HERE, "plots")
os.makedirs(OUT_DIR, exist_ok=True)

# The UI end time shown in the experiment table (05. Nov 26 19:32, local).
UI_END = dt.datetime(2026, 11, 5, 19, 32)

INK = "#111827"
MUTED = "#64748B"
AMBER = "#D97706"
BRAND = "#0057B7"
GREEN = "#15803D"
PURPLE = "#7C3AED"
RED = "#B91C1C"

# name, file, colour, highlighted
SERIES = [
    ("Mango Maracuya Dream", "mango_maracuya.csv", AMBER, True),
    ("CoCo Jambo", "coco_jambo.csv", BRAND, False),
    ("Honig Bier", "honig_bier.csv", GREEN, False),
    ("Lemon Pale Lager", "lemon_pale_lager.csv", PURPLE, False),
]

TILT_OUT = 80.0   # above this the iSpindel is out of the fermenter


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_series(filename):
    rows = list(csv.DictReader(open(os.path.join(DATA, filename))))
    times, gravity, temp, tilt = [], [], [], []
    for r in rows:
        times.append(dt.datetime.fromisoformat(r["timestamp_local"]))
        gravity.append(_float(r.get("gravity_plato")))
        temp.append(_float(r.get("temperature_c")))
        tilt.append(_float(r.get("tilt_deg")))
    return times, gravity, temp, tilt


def split_real_end(times):
    """The real end is the last point before the largest gap in the series.

    For Mango the iSpindel stopped on 31.10.; the single 05.11. point is the
    device lying outside the fermenter (tilt ~90 deg), so it is an artifact.
    """
    gaps = [(times[i + 1] - times[i], i) for i in range(len(times) - 1)]
    gap, idx = max(gaps)
    return idx, gap


def plot_curve():
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 7), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )
    fig.patch.set_facecolor("white")

    mango_times = mango_gravity = None
    for name, filename, color, highlight in SERIES:
        times, gravity, temp, tilt = load_series(filename)
        real = [(t, g, tp) for t, g, tp, ti in zip(times, gravity, temp, tilt)
                if ti is None or ti <= TILT_OUT]
        art = [(t, g) for t, g, ti in zip(times, gravity, tilt)
               if ti is not None and ti > TILT_OUT]
        rt = [x[0] for x in real]
        rg = [x[1] for x in real]
        rtp = [x[2] for x in real]
        lw = 2.4 if highlight else 1.4
        alpha = 1.0 if highlight else 0.8
        ax1.plot(rt, rg, color=color, lw=lw, alpha=alpha, label=name)
        ax2.plot(rt, rtp, color=color, lw=lw, alpha=alpha,
                 ls="-" if highlight else "--")
        if art:
            ax1.scatter([x[0] for x in art], [x[1] for x in art],
                        color=color, marker="X", s=70, zorder=5)
        if highlight:
            mango_times, mango_gravity = times, gravity

    # Mango: the real fermentation window and the UI end
    real_idx, gap = split_real_end(mango_times)
    real_end = mango_times[real_idx]
    ax1.axvspan(mango_times[0], real_end, color="#FEF3C7", alpha=0.45)
    ax1.axvline(real_end, color=RED, ls="--", lw=1.6)
    ax1.axvline(UI_END, color=MUTED, ls=":", lw=1.2)
    ax1.annotate(
        f"Mango real end\n{real_end:%d.%m. %H:%M}",
        xy=(real_end, mango_gravity[real_idx]), xytext=(-10, 28),
        textcoords="offset points", ha="right", color=RED, fontsize=9,
        fontweight="bold",
    )

    ax1.set_ylabel("gravity (°P)", color=INK)
    ax1.set_title(
        "All four batches - gravity and temperature (real iSpindel data)",
        fontsize=15, fontweight="bold", color=INK, loc="left",
    )
    ax1.legend(loc="upper left", frameon=False, fontsize=8, ncol=1)
    ax1.grid(alpha=0.25)

    ax2.set_ylabel("temperature (°C)", color=INK)
    ax2.set_xlabel("time (Europe/Zurich)", color=INK)
    ax2.text(0.01, 0.95, "dashed = temperature;  X = device out of the fermenter",
             transform=ax2.transAxes, fontsize=8, color=MUTED, va="top")
    ax2.grid(alpha=0.25)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.\n%H:%M"))
    ax2.xaxis.set_major_locator(mdates.DayLocator())
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "mango_fermentation.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)
    return real_end, gap


def plot_duration(real_end):
    times, _, _, _ = load_series("mango_maracuya.csv")
    first = times[0]
    last_meas = times[-1]
    ends = [
        ("UI end (button pressed)", UI_END, MUTED),
        ("last measurement (device out)", last_meas, AMBER),
        ("real fermentation end", real_end, RED),
    ]

    fig, ax = plt.subplots(figsize=(12, 3.6))
    fig.patch.set_facecolor("white")
    for i, (label, end, color) in enumerate(ends):
        days = (end - first).total_seconds() / 86400
        ax.barh(i, days, color=color, height=0.55, alpha=0.9)
        ax.text(days + 0.08, i,
                f"{end:%d.%m. %H:%M}   ({days:.1f} days)",
                va="center", fontsize=9.5, color=INK, fontweight="bold")
    ax.set_yticks(range(len(ends)))
    ax.set_yticklabels([e[0] for e in ends], fontsize=10, color=INK)
    ax.set_xlabel(f"days since the first measurement ({first:%d.%m. %H:%M})",
                  color=INK)
    ax.set_xlim(0, max((e[1] - first).total_seconds() / 86400 for e in ends) + 2.8)
    ax.set_title(
        "Mango Maracuya Dream - experiment length: UI end vs. real end",
        fontsize=14, fontweight="bold", color=INK, loc="left",
    )
    ax.grid(axis="x", alpha=0.25)
    ax.invert_yaxis()
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "mango_duration.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


def main():
    real_end, gap = plot_curve()
    plot_duration(real_end)
    print(f"Mango real end : {real_end:%d.%m. %H:%M}  (gap after: {gap})")
    print(f"Mango UI end   : {UI_END:%d.%m. %H:%M}")


if __name__ == "__main__":
    main()
