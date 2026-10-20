"""Plotly figure builders for the dashboard (the batch-card zones are built in main.py)."""
import plotly.graph_objects as go

PALETTE = ["#0ea5e9", "#f97316", "#22c55e", "#a855f7", "#ef4444", "#14b8a6"]

# The dashboard's font, registered as a @font-face in app/assets/input.pcss and set as the page
# default there (`--font-sans`, which Preflight applies to <html>). Plotly draws its own SVG text,
# so it does **not** inherit the page font - every figure has to name the family itself
# (main.py feeds the same name to the Mantine theme as well, because
# Mantine's own `body, :host { font-family: var(--mantine-font-family) }` wins over the page rule.
# The names with spaces are quoted so the CSS parser reads one family, not three identifiers.
# Keep this stack in sync with `--font-sans` in app/assets/input.pcss.
FONT_FAMILY = '"IBM XGA-AI 12x20", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace'


def fermentation_figure(series, relative=False, height=460, legend=True, mobile=False,
                        x_range=None):
    """Gravity and temperature over time, on ONE y axis.

    series = [{"label": str,
               "points": [{"recorded_at": datetime, "gravity_plato": float, "temp_c": float}]}]
    relative=True switches the x axis to hours since the start of each experiment (FR-18).
    height=None autosizes the figure to its container (the compact per-device chart does
    that, so the card can set the height with CSS). legend=False hides the legend - the
    per-device card already names the device in its title, so it is just wasted space.
    mobile=True (a phone-sized viewport, see the `viewport` store in main.py) also drops the
    legend and shortens the axis titles to "time" / "hours" (NFR-06).
    x_range = (start, end) datetimes (FR-16): pins the x axis to the selected time range instead
    of letting Plotly autoscale to the data. An experiment that started inside the window then
    keeps the empty time in front of its first measurement visible - with "last 7 days" and an
    experiment that has been running for three days, the four days before it stay drawn. The
    range comes from `main.chart_window()` (the database clock, i.e. the same `now()` the
    time-range query compares against). It is ignored while `relative` is True: that axis counts
    hours since the start and therefore has to begin at 0.

    There is deliberately **no second y axis**: gravity and temperature share one scale, so
    the ticks and labels sit on the left only and the whole right-hand side stays plot area.
    The temperature trace is dotted and slightly transparent to keep the two lines apart, and
    the axis title carries both units.
    """
    if mobile:
        legend = False
    if relative:
        xaxis_title = "hours" if mobile else "hours since start"
    else:
        xaxis_title = "time" if mobile else "time (local)"
    yaxis_title = "°P · °C" if mobile else "gravity (°P) · temperature (°C)"

    fig = go.Figure()
    for i, s in enumerate(series):
        points = s["points"]
        color = PALETTE[i % len(PALETTE)]
        if relative and points:
            t0 = points[0]["recorded_at"]
            x = [(p["recorded_at"] - t0).total_seconds() / 3600 for p in points]
        else:
            x = [p["recorded_at"] for p in points]
        # A long series (the 7-day simulation at 15 min = 673 points) would draw 673 overlapping
        # markers and turn the line into a fat band, so a dense chart looks nothing like a short
        # one. Markers are only drawn while they stay readable; the line is always there.
        markers = len(points) <= 200
        fig.add_trace(go.Scatter(
            x=x, y=[p["gravity_plato"] for p in points], name=f"{s['label']} (°P)",
            mode="lines+markers" if markers else "lines", line=dict(color=color),
            marker=dict(size=5, color=color, line=dict(width=1, color="white"))))
        fig.add_trace(go.Scatter(
            x=x, y=[p["temp_c"] for p in points], name=f"{s['label']} (°C)",
            mode="lines", line=dict(color=color, dash="dot"), opacity=0.6))

    if not series:
        fig.add_annotation(text="no measurements yet", showarrow=False,
                           font=dict(color="#94a3b8"))

    fig.update_layout(
        height=height,
        autosize=height is None,
        # automargin on the axes grows these only as far as the tick labels and titles
        # need - that keeps the plot area as large as possible on a phone
        margin=dict(l=2 if mobile else 6, r=2 if mobile else 6,
                    t=28 if legend else 4, b=6),
        showlegend=legend,
        font=dict(family=FONT_FAMILY, size=10 if mobile else 12),
        hovermode="x unified",
        # opaque dark box - the default unified hover box is a translucent light grey
        hoverlabel=dict(bgcolor="#0f172a", bordercolor="#0f172a", namelength=-1,
                        font=dict(color="#f8fafc", size=11)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        # transparent so the card's background (and its hover colour) shows through
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    # the spike snaps to the data point, so the hovered measurement is marked on the x axis.
    # FR-16: no x_range (the "entire experiment" default) means `range=None`, which is Plotly's
    # autoscale - the axis then spans exactly the experiment's own run time.
    fig.update_xaxes(title_text=xaxis_title, automargin=True,
                     showspikes=True, spikemode="across", spikesnap="data",
                     spikethickness=1.5, spikecolor="#0f172a", spikedash="solid",
                     range=[x_range[0], x_range[1]] if (x_range and not relative) else None)
    # a single y axis: no secondary_y, so nothing is drawn on the right-hand side
    fig.update_yaxes(title_text=yaxis_title, automargin=True)
    return fig
