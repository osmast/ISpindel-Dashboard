"""Reusable layout primitives. All styling is Tailwind utility classes.

Every class string is written out in full inside a `className` argument (no lookup table, no
f-string, no `"bg-" + tone`), because Tailwind compiles from the raw file text.
"""
from dash import html


def num(value, digits=2, dash="-"):
    """None-safe number formatting."""
    return dash if value is None else f"{value:.{digits}f}"


def page(children):
    return html.Div(
        className="min-h-screen bg-page text-slate-800",
        children=[
            # html.Header(
            #     className="bg-slate-900 text-white px-4 py-4 md:px-8",
            #     children=[
            #         html.H1("iSpindel Fermentation Monitor",
            #                 className="text-lg font-semibold tracking-tight md:text-xl"),
            #         html.P("live and historical fermentation data",
            #                className="text-xs text-slate-400 md:text-sm"),
            #     ],
            # ),
            html.Main(
                # Full width on a laptop, capped on very large screens (1536px = Tailwind 2xl).
                className="mx-auto flex w-full max-w-[1536px] flex-col gap-4 p-4 md:gap-6 md:p-6",
                children=children,
            ),
        ],
    )


def card(title, *children):
    """A panel of the page. A falsy `title` renders the panel **without** its heading line.

    The FR-05 experiment table passes `None`: its two tab labels ("Running (n)" / "Completed (n)")
    already say what is shown, so a heading above them only repeated the requirement id.
    """
    heading = [
        html.H2(title, className="mb-4 text-xs font-semibold uppercase tracking-wider "
                                 "text-slate-500")
    ] if title else []
    return html.Section(
        # animate-fade-in: the panel fades in when the page renders (see assets/input.pcss)
        className="animate-fade-in motion-reduce:animate-none rounded-xl corner-squircle border "
                  "border-brand bg-white p-4 shadow-sm md:p-5",
        children=[*heading, *children],
    )


def stat(label, value, unit="", hint=""):
    return html.Div(
        className="rounded-lg corner-squircle border border-slate-200 p-3",
        children=[
            html.Div(label, className="text-xs uppercase tracking-wide text-slate-500"),
            html.Div(
                className="leading-tight",
                children=[
                    html.Span(value, className="text-2xl font-semibold tabular-nums"),
                    html.Span(f" {unit}", className="text-sm text-slate-500"),
                ],
            ),
            html.Div(hint, className="mt-1 text-xs text-slate-400"),
        ],
    )


def zone(label, *children):
    """One data zone of the FR-13 batch card: an uppercase caption over the zone's lines."""
    return html.Div(
        className="rounded-lg corner-squircle border border-slate-200 bg-slate-50 p-3",
        children=[html.Div(label, className="mb-1 text-xs font-semibold uppercase tracking-wide "
                                            "text-slate-500"),
                  *children],
    )


def badge(text, tone="slate"):
    """A small status pill (FR-05). `tone` picks one of the fixed colour sets."""
    return html.Span(text, className=(
        "inline-block rounded-full border px-2 py-0.5 text-xs font-medium "
        "bg-slate-100 text-slate-700 border-slate-200" if tone == "slate" else
        "inline-block rounded-full border px-2 py-0.5 text-xs font-medium "
        "bg-emerald-50 text-emerald-700 border-emerald-200" if tone == "green" else
        "inline-block rounded-full border px-2 py-0.5 text-xs font-medium "
        "bg-amber-50 text-amber-700 border-amber-200" if tone == "amber" else
        "inline-block rounded-full border px-2 py-0.5 text-xs font-medium "
        "bg-red-50 text-red-700 border-red-200" if tone == "red" else
        "inline-block rounded-full border px-2 py-0.5 text-xs font-medium "
        "bg-sky-50 text-sky-700 border-sky-200"))


def alert(text, tone="slate"):
    """A one-line message. `tone` uses the same colour sets as `badge`."""
    return html.Div(text, className=(
        "rounded-lg corner-squircle border px-3 py-2 text-sm "
        "bg-slate-100 text-slate-700 border-slate-200" if tone == "slate" else
        "rounded-lg corner-squircle border px-3 py-2 text-sm "
        "bg-emerald-50 text-emerald-700 border-emerald-200" if tone == "green" else
        "rounded-lg corner-squircle border px-3 py-2 text-sm "
        "bg-amber-50 text-amber-700 border-amber-200" if tone == "amber" else
        "rounded-lg corner-squircle border px-3 py-2 text-sm "
        "bg-red-50 text-red-700 border-red-200" if tone == "red" else
        "rounded-lg corner-squircle border px-3 py-2 text-sm "
        "bg-sky-50 text-sky-700 border-sky-200"))


def toast(content, tone="slate"):
    """A transient notice for the fixed top-right corner (FR-01 / FR-04), faded out by CSS."""
    if not hasattr(content, "to_plotly_json"):        # a plain string -> wrap it in an alert
        content = alert(content, tone)
    return html.Div(content, className="toast-life w-full shadow-lg")


def button(id, label, tone="dark", extra="", compact=False, **kwargs):
    """A button. `extra` appends static Tailwind classes; `compact=True` is the footer variant."""
    return html.Button(
        label,
        id=id,
        # size x tone: min-h-11 = 44 px touch target (NFR-06), compact = min-h-8 for card footers.
        className=(
            "min-h-8 rounded-md corner-squircle px-2.5 py-1 text-xs font-medium transition-colors "
            "bg-slate-900 text-white hover:bg-slate-700 " if compact and tone == "dark" else
            "min-h-8 rounded-md corner-squircle px-2.5 py-1 text-xs font-medium transition-colors "
            "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 "
            if compact and tone == "light" else
            "min-h-8 rounded-md corner-squircle px-2.5 py-1 text-xs font-medium transition-colors "
            "border border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200 "
            "hover:border-slate-300 " if compact and tone == "grey" else
            "min-h-8 rounded-md corner-squircle px-2.5 py-1 text-xs font-medium transition-colors "
            "bg-red-600 text-white hover:bg-red-500 " if compact and tone == "danger" else
            "min-h-11 rounded-lg corner-squircle px-4 py-2 text-sm font-medium transition-colors "
            "bg-slate-900 text-white hover:bg-slate-700 " if tone == "dark" else
            "min-h-11 rounded-lg corner-squircle px-4 py-2 text-sm font-medium transition-colors "
            "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 "
            if tone == "light" else
            "min-h-11 rounded-lg corner-squircle px-4 py-2 text-sm font-medium transition-colors "
            "border border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200 "
            "hover:border-slate-300 " if tone == "grey" else
            "min-h-11 rounded-lg corner-squircle px-4 py-2 text-sm font-medium transition-colors "
            "bg-red-600 text-white hover:bg-red-500 ") + extra,
        **kwargs,
    )


def field(label, control):
    """A labelled control: caption + control, in a `<div>` not a `<label>` (a nested label makes
    dcc.RadioItems snap back to its first option)."""
    return html.Div(
        className="grid gap-1 text-sm",
        children=[html.Span(label, className="text-slate-600"), control],
    )


def table(headers, rows, empty="no data yet"):
    """`empty` is either the plain-text placeholder or a ready-made component (e.g. the
    "where to point an iSpindel" hint of the FR-12 device table)."""
    if not rows:
        if hasattr(empty, "to_plotly_json"):
            return empty
        return html.P(empty, className="text-sm text-slate-400")
    return html.Div(
        className="overflow-x-auto",
        children=html.Table(
            className="w-full text-left text-sm",
            children=[
                html.Thead(html.Tr([
                    html.Th(h, className="border-b border-slate-200 px-2 py-2 text-xs "
                                         "uppercase tracking-wide text-slate-500")
                    for h in headers])),
                html.Tbody([
                    html.Tr([html.Td(c, className="border-b border-slate-100 px-2 py-2 align-top")
                             for c in row]) for row in rows]),
            ],
        ),
    )
