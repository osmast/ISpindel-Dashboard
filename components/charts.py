"""Plotly figure builders for the dashboard (the batch-card zones are built in main.py)."""
import plotly.graph_objects as go

PALETTE = ["#0ea5e9", "#f97316", "#22c55e", "#a855f7", "#ef4444", "#14b8a6"]

# Plotly draws its own SVG text and does not inherit the page font, so every figure names the
# family itself. Keep this stack in sync with `--font-sans` in assets/input.pcss.
FONT_FAMILY = '"IBM XGA-AI 12x20", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace'


def fermentation_figure(series, relative=False, height=460, legend=True, mobile=False,
                        x_range=None):
    """Gravity and temperature over time, on one y axis.

    series = [{"label": str, "points": [{"recorded_at", "gravity_plato", "temp_c"}]}].
    relative=True counts hours since the start of each experiment (FR-18). height=None autosizes
    to the container. `legend`/`mobile` hide the legend; mobile also shortens the axis titles
    (NFR-06). x_range = (start, end) pins the x axis to the selected time range (FR-16) so the
    empty time before an experiment's first measurement stays visible; ignored when `relative`.
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
        # markers turn a dense series into a fat band - draw them only while they stay readable
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
    # the spike marks the hovered point on the x axis; range=None means Plotly autoscale (FR-16)
    fig.update_xaxes(title_text=xaxis_title, automargin=True,
                     showspikes=True, spikemode="across", spikesnap="data",
                     spikethickness=1.5, spikecolor="#0f172a", spikedash="solid",
                     range=[x_range[0], x_range[1]] if (x_range and not relative) else None)
    # a single y axis: no secondary_y, so nothing is drawn on the right-hand side
    fig.update_yaxes(title_text=yaxis_title, automargin=True)
    return fig
