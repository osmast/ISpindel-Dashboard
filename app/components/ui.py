"""Reusable layout primitives. All styling is Tailwind utility classes.

**Every class string is written out in full inside a `className` argument** - no lookup table,
no f-string, no `"bg-" + tone`. Two readers have to find the names:

* the Tailwind compiler (`@source "../**/*.py"` in app/assets/input.pcss), which scans the raw
  text of this file, and
* the VS Code Tailwind plugin, which only looks at the shapes named in
  `tailwindCSS.experimental.classRegex` in .vscode/settings.json.

A class name that is assembled from a variable is invisible to the plugin (and to a reader);
the failure is silent - the class is simply missing from app/assets/tailwind.css and the
element renders unstyled. `python tools/tailwind_class_check.py` guards that rule.
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
        # animate-fade-in: the panel fades in when the page renders (see app/assets/input.pcss)
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
    """One data zone of the FR-13 batch card: an uppercase caption over the zone's lines.

    The device card carries three of them (gravity / temperature / attenuation & ABV) in a grid
    that stacks on a phone. They replaced the two Plotly dials on 20.10.2026 - the same numbers,
    but with the OG, the targets, the 24 h rate and the derived values next to them.
    """
    return html.Div(
        className="rounded-lg corner-squircle border border-slate-200 bg-slate-50 p-3",
        children=[html.Div(label, className="mb-1 text-xs font-semibold uppercase tracking-wide "
                                            "text-slate-500"),
                  *children],
    )


def badge(text, tone="slate"):
    """A small status pill (FR-05). `tone` picks one of the fixed colour sets, written out
    in full per branch so Tailwind and the editor both see every literal class name."""
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
    """A transient notice for the fixed top-right corner (FR-01 / FR-04).

    `content` is either a plain string (wrapped in an `alert`) or an existing alert
    component. The whole life cycle is CSS: the `toast-life` animation in
    app/assets/input.pcss fades the notice in, holds it for 10 s and fades it out
    (`forwards`, so it stays invisible afterwards). No JavaScript is involved - the
    container in main.py ignores pointer events and the faded node cannot capture a click,
    and the next notice simply replaces the children.
    """
    if not hasattr(content, "to_plotly_json"):        # a plain string -> wrap it in an alert
        content = alert(content, tone)
    return html.Div(content, className="toast-life w-full shadow-lg")


def button(id, label, tone="dark", extra="", compact=False, **kwargs):
    """A button. `extra` appends static Tailwind classes (e.g. `w-full sm:w-auto`, so a button
    fills the row on a phone); that is the one place where classes come from outside this file,
    and the call site is where the literal is written. `compact=True` renders the small variant
    for a card footer: `text-xs` like the surrounding footer line, less padding and a smaller
    radius. Every size/tone combination is written out in full (see the module docstring), so
    no class name is ever assembled at runtime.
    """
    return html.Button(
        label,
        id=id,
        # size x tone. The default size is min-h-11 = 44 px, the smallest comfortable touch
        # target (NFR-06); compact is min-h-8 for the card footers. `grey` is the quiet
        # default action, e.g. the "set up experiment" button of a device card.
        # NB: no parenthesis may appear inside this className expression - the VS Code
        # classRegex for the parenthesised shape stops at the first `)`.
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
    """A labelled control: caption + control in a grid.

    Deliberately a `<div>`/`<span>` and **not** a `<label>`: `dcc.RadioItems` /
    `dcc.Checklist` render a `<label>` per option, and a `<label>` inside a `<label>` is
    invalid HTML. The browser then treats the *first* radio as the outer label's control and
    clicks it whenever anything inside the label is clicked - which made the "Time range" and
    "Time axis" selectors snap back to their first option, so the range never applied.
    """
    return html.Div(
        className="grid gap-1 text-sm",
        children=[html.Span(label, className="text-slate-600"), control],
    )


def table(headers, rows, empty="no data yet"):
    if not rows:
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
