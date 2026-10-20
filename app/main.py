"""iSpindel fermentation dashboard (Plotly Dash).

Run:  python app/main.py                              ->  http://localhost:8080
      gunicorn --chdir app main:server -b 0.0.0.0:8080
"""
from datetime import datetime, timedelta, timezone

import dash
import dash_mantine_components as dmc
import psycopg
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

from components import charts, ui
from db import CFG, LOCAL, execute, local, query, rows_to_csv

DASH = CFG["dashboard"]
REFRESH = DASH["refresh_ms"]
LIVE = DASH["live_ms"]
BATTERY_WARN = DASH["battery_warn_v"]
BATTERY_FULL = DASH["battery_full_v"]
BATTERY_EMPTY = DASH["battery_empty_v"]
# FR-20: the reference values of the batch card. `EXPECTED_ATTENUATION` turns an experiment's OG
# into its "Target FG" (fg = og * (1 - att/100)) and - with the same rule of thumb - into the
# estimate for the final ABV; `TARGET_TEMP_C` holds the target temperature window per beer style
# (matched case-insensitively inside `beer_style`, else the "default" entry), from which the card
# derives the "a High / v Low" hint. Both are settings (NFR-08); the formulas are written out in
# docs/concept.md.
EXPECTED_ATTENUATION = DASH["expected_attenuation"]
TARGET_TEMP_C = DASH["target_temp_c"]
# Gravity and temperature are shown as text, in the text-safe reference colours
# (`text-yellow-600` / `text-purple-700`) - one colour per quantity, like the old dial pair. The
# class strings live at the `header_stat` and `ui.zone` calls in device_card(), where Tailwind and
# the editor both see the literal names (no module-level class constants).

CHART_DAYS = DASH["device_chart_days"]

# FR-16/FR-22: the selectable time ranges - the value is an SQL interval, None = "entire
# experiment". One dict for the chart query, the export and the chart's x axis window
# (`chart_window()`), so all three always agree.
RANGES = {"all": None, "7d": "7 days", "24h": "24 hours"}
# the labels of the FR-16 selector (also used in the export message, so both cannot drift apart)
RANGE_TEXT = {"all": "entire experiment", "7d": "last 7 days", "24h": "last 24 h"}
# Restrict a query to the selected range: with since = None the first condition is TRUE and
# every measurement of the selected experiments stays in the result.
RANGE_FILTER = "AND (%(since)s::interval IS NULL OR m.recorded_at >= now() - %(since)s::interval)"

# FR-19: the status dot next to the device name is green while the iSpindel is healthy and
# turns red for both conditions the requirement names - no data for more than three intervals,
# or a battery voltage below `dashboard.battery_warn_v`. The reason itself is text and is
# therefore shown only in the expanded card (see `card_warnings()`), never in the header.

# The other iSpindels of the course publish to their own broker until the brew-day setup is
# agreed, so during development the first device could be repeated to judge the grid with
# several cards. That fake duplication is off: FR-15 requires that every card is a real
# device. ispindel_overview() still honours a value > 1 for pure layout tests (README 1.9).
DEV_REPEAT = 1

# The class string of every text/number input is written out at the field itself (see
# experiment_form) instead of living in a constant: a constant is invisible to the VS Code
# Tailwind plugin, which only reads the `className="..."` / `extra="..."` shapes listed in
# .vscode/settings.json. `tools/tailwind_class_check.py` guards that rule.

# Every figure on the page is read-only: no Plotly modebar. That removes the zoom / pan /
# autoscale / "download as png" / fullscreen buttons and the Plotly logo - noise for a
# non-programmer and a phone user (NFR-05); the charts are meant to be read, not edited.
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def experiment_form(values=None, disabled=False):
    """The fields of the experiment dialog, filled from `values` (None = empty).

    The dialog is rebuilt from this whenever it opens, so one dialog serves all four jobs:
    **create** (empty), **edit** (FR-06, prefilled), **delete** (prefilled, plus a warning) and
    the **end confirmation** (FR-04: prefilled and `disabled=True` - nothing is edited there, the
    fields only show *what* is being ended). Because the callback answers `no_update` for
    `#exp-form` on every other action, whatever the user typed survives while the dialog is open.

    The inputs stay in the DOM even while they are disabled: `experiment_action` reads them as
    `State`, and Dash refuses a callback whose `State` id does not exist in the layout.
    """
    v = values or {}

    def val(key):
        return v.get(key)

    return [
        html.Div(className="grid gap-4 md:grid-cols-2", children=[
            ui.field("Name (unique)",
                     dcc.Input(id="new-name", type="text", value=val("name"), disabled=disabled,
                               placeholder="2026_IPA_Mueller",
                               className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
            ui.field("Start (empty = now, else 2026-11-12T16:30)",
                     dcc.Input(id="new-start", type="text", value=val("start"), disabled=disabled,
                               placeholder="2026-11-12T16:30",
                               className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
        ]),
        # FR-01: the iSpindel is not a field anymore - the dialog is opened from the device card
        # (or from the experiment's row), so it is clear which iSpindel it belongs to (FR-03).
        html.P(className="mt-3 text-xs text-slate-400",
               children=["These fields may stay empty and can be completed later (FR-06):"]),
        html.Div(className="mt-2 grid gap-4 md:grid-cols-2", children=[
            ui.field("Beer style", dcc.Input(id="new-style", type="text", value=val("style"),
                                             disabled=disabled, placeholder="West Coast IPA",
                                             className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
            ui.field("Original gravity °P",
                     dcc.Input(id="new-og", type="number", value=val("og"), disabled=disabled,
                               placeholder="14.5",
                               className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
            ui.field("Yeast", dcc.Input(id="new-yeast", type="text", value=val("yeast"),
                                        disabled=disabled, placeholder="US-05",
                                        className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
            ui.field("Responsible",
                     dcc.Input(id="new-responsible", type="text", value=val("responsible"),
                               disabled=disabled, placeholder="O. Steiner",
                               className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
            ui.field("Notes", dcc.Input(id="new-notes", type="text", value=val("notes"),
                                        disabled=disabled, placeholder="dry hopped 03.11.",
                                        className="w-full rounded-lg corner-squircle border border-slate-300 px-3 py-2")),
        ]),
    ]


def device_form(values=None, disabled=False):
    """The fields of the device dialog (FR-12): the read-only MQTT name, a display name and the
    "in use" flag that decides whether the iSpindel shows up in the overview (FR-13).

    Every class string is written out at its control (no shared constant) - the class-name rule of
    the project, see the comment at the top of `experiment_form`. It is defined up here, next to
    `experiment_form()`, because `layout()` renders it at import time (the dialog keeps both forms
    in the DOM so Dash finds their ids - see the callback outputs below).
    """
    values = values or {}
    return html.Div(className="grid gap-3", children=[
        ui.field("iSpindel name (from the MQTT topic, read-only)",
                 dcc.Input(value=values.get("mqtt_name"),
                           disabled=True,
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("Display name (optional - shown instead of the MQTT name)",
                 dcc.Input(id="dev-name", value=values.get("display_name") or "",
                           disabled=disabled,
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("Usage - an ignored iSpindel keeps recording, it is only hidden from the overview",
                 dcc.Checklist(id="dev-active",
                               options=[{"label": " in use", "value": "on"}],
                               value=["on"] if values.get("active", True) else [],
                               className="flex flex-wrap gap-3 text-sm",
                               labelClassName="flex min-h-11 cursor-pointer items-center")),
    ])



# assets_ignore: the Tailwind *source* (app/assets/input.pcss) must not be linked as a
# stylesheet - Dash would serve it with a non-CSS MIME type and the browser logs an error.
app = dash.Dash(__name__, title="iSpindel Monitor", assets_ignore=r"\.pcss$")
server = app.server                                   # gunicorn entry point


def layout():
    return ui.page([
        # FR-01/FR-04: notices (experiment started / ended) are transient toasts. The
        # container is fixed to the top-right corner of the viewport (`top-0 right-0`) and
        # ignores pointer events, so it can never block the page behind it. The child
        # carries the fade-away animation (app/assets/input.pcss) - no JavaScript needed.
        html.Div(id="msg", className="pointer-events-none fixed right-0 top-0 z-50 flex "
                                     "w-full max-w-sm flex-col gap-2 p-4"),

        # FR-13 / FR-19: the iSpindel overview. It has no container box - the cards stand alone
        # on the page background (update_dashboard() replaces the children with a dmc.Grid).
        html.Div(id="devices"),

        # FR-05: the two views of the experiment table. The dmc.Tabs shell sits in this static
        # layout on purpose: a string id inside callback-generated content cannot be a callback
        # Input (Dash validates the ids at startup), and a Tabs that is never re-rendered keeps
        # the tab the user picked - so the view needs no store to survive the 15 s refresh.
        # The panel has **no heading line** (20.10.2026): the two tab labels "Running (n)" /
        # "Completed (n)" already name what is shown, so an "Experiments (FR-05)" caption above
        # them only repeated the requirement id.
        ui.card(None, dmc.Tabs(id="exp-tabs", value="running", children=[
            dmc.TabsList([
                # the labels carry the counts, so update_dashboard() fills them
                dmc.TabsTab(children="", value="running", id="exp-tab-running"),
                dmc.TabsTab(children="", value="completed", id="exp-tab-completed"),
                # FR-12: the device master data is the **third view of the same panel** - the
                # ingest creates a device row on the first message, so a new iSpindel appears here
                # without any code change; display name and the "in use" flag are managed from it.
                dmc.TabsTab(children="", value="devices", id="exp-tab-devices"),
            ]),
            dmc.TabsPanel(html.Div(id="exp-running"), value="running", pt="md"),
            dmc.TabsPanel(html.Div(id="exp-completed"), value="completed", pt="md"),
            dmc.TabsPanel(html.Div(id="devices-table"), value="devices", pt="md"),
        ])),

        # FR-14 - FR-18: the comparison chart. It carries **no heading and no controls above it**
        # (20.10.2026): the experiments are picked with the `chart` action of the FR-05 rows above
        # (FR-17), and the FR-16/FR-18 axis controls sit below the figure. `ui.card(None, ...)`
        # renders the panel without its H2, like the FR-05 table panel.
        #
        # The panel is **always visible**: hiding it while nothing was selected was tried on
        # 20.10.2026 and taken back the same day - an empty chart shows "no measurements yet" and
        # the panel is where the FR-16/FR-18 controls live, so it should be there from the start.
        ui.card(None,
                # read-only figure: GRAPH_CONFIG switches the Plotly modebar (and with it the
                # fullscreen / screenshot buttons) off
                dcc.Graph(id="chart", config=GRAPH_CONFIG),
                # FR-16/FR-18: the two controls sit **under** the figure - the time axis on the
                # bottom left, the time range on the bottom right; they stack on a phone (NFR-06)
                # and the radios keep their 44 px tap target.
                html.Div(className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start "
                                   "sm:justify-between sm:gap-4", children=[
                    ui.field("Time axis",
                             dcc.RadioItems(id="relative", value="abs",
                                            options=[{"label": " absolute", "value": "abs"},
                                                     {"label": " hours since start", "value": "rel"}],
                                            className="flex flex-wrap gap-3 text-sm",
                                            labelClassName="flex min-h-11 cursor-pointer "
                                                           "items-center")),
                    ui.field("Time range",
                             dcc.RadioItems(id="range", value="all",
                                            options=[{"label": f" {label}", "value": key}
                                                     for key, label in RANGE_TEXT.items()],
                                            className="flex flex-wrap gap-3 text-sm sm:justify-end",
                                            labelClassName="flex min-h-11 cursor-pointer "
                                                           "items-center")),
                ])),
        # FR-21: the download target of the FR-05 row export (an invisible component).
        dcc.Download(id="download"),


        # FR-01 - FR-04: the experiment dialog of a device card. It sits outside the device grid
        # on purpose - the grid is rebuilt every refresh, so a form inside a card would lose what
        # the user has typed. `exp-target` holds the device whose dialog is open (None = closed).
        dcc.Store(id="exp-target", data=None),
        dmc.Modal(
            id="exp-modal", title="Set up experiment", opened=False, centered=True, size="lg",
            # The dialog is closed through the buttons only: a modal that closes itself (X,
            # click outside, Esc) would leave Dash's `opened` state at True, and the next click
            # on "Set up experiment" would then not reopen it.
            withCloseButton=False, closeOnClickOutside=False, closeOnEscape=False,
            children=[
                html.Div(id="modal-msg", className="mb-3"),
                # The fields live in their own container so the callback can rebuild them with
                # the values of an existing experiment (FR-06 edit / delete) - the same dialog
                # serves "new", "edit" and "delete".
                html.Div(id="exp-form", children=experiment_form()),
                # FR-12: the device fields, hidden until the Devices table opens the dialog. It
                # sits in the static layout on purpose - see the comment at the callback's outputs.
                html.Div(id="dev-form", style={"display": "none"}, children=device_form()),
                # full-width buttons on a phone (NFR-06), right-aligned on a laptop
                html.Div(className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end",
                         children=[
                    ui.button("exp-cancel", "Cancel", tone="light", extra="w-full sm:w-auto"),
                    ui.button("exp-submit", "Start experiment", extra="w-full sm:w-auto"),
                ]),
            ]),

        dcc.Interval(id="tick", interval=REFRESH),
        dcc.Interval(id="tick1s", interval=LIVE),
        # device name -> {"last": epoch of the last measurement, "due": epoch of the next
        # transmission} - written by update_device_times, turned into the card's footer line
        # ("last: 12 s ago · upcoming: in 12 s") by the clientside callback below
        dcc.Store(id="device_times", data={}),
        # {"mobile": bool} - written by the viewport clientside callback below, read by the
        # chart and the device cards to drop the legend on a phone (NFR-06)
        dcc.Store(id="viewport", data={}),
        # which accordion cards are open - written by app/assets/card_state.js on every
        # toggle, read back here so a rebuild cannot close them
        dcc.Store(id="open_cards", data={}),
        # FR-17: the experiment ids overlaid in the comparison chart. Written by the `chart`
        # action of an FR-05 table row (toggle_chart), read by update_chart and by
        # update_dashboard (so the row icon shows which experiments are selected). A list,
        # because several experiments can be shown side by side to compare them.
        dcc.Store(id="chart-select", data=[]),
        dcc.Store(id="reload", data=0),
    ])


# Mantine's default xl is 88em (1408px), which already switches to three columns on a
# 1440px laptop and squeezes the cards. xxl at 96em (1536px) matches the container cap,
# so a laptop keeps two comfortable columns and only a very wide screen gets three.
#
# `fontFamily` is as important as the breakpoints: Mantine injects its own
# `body, :host { font-family: var(--mantine-font-family) }` (unlayered, so it beats Tailwind's
# layered `html` rule) with a system-font default - setting it here is what actually makes the
# oldschool font show up in the app. The CSS `--font-sans` alone is not enough.
THEME = {"fontFamily": charts.FONT_FAMILY,
         "fontFamilyMonospace": charts.FONT_FAMILY,
         "headings": {"fontFamily": charts.FONT_FAMILY},
         "breakpoints": {"xs": "36em", "sm": "48em", "md": "62em",
                         "lg": "75em", "xl": "88em", "xxl": "96em"}}

# dmc supplies the responsive grid; MantineProvider sets up its theme (CSS variables).
app.layout = dmc.MantineProvider(layout(), theme=THEME)

# The times line of every card ticks in the browser: `device_times` carries the absolute epoch
# of the last measurement and of the next transmission per device (written by
# update_device_times), so this callback only has to subtract the browser clock - one JS
# function for every card, no server round trip.
app.clientside_callback(
    """
    function (n, times, ids) {
        // with a single device card the id list can arrive as a scalar (DEV_REPEAT = 1)
        const list = Array.isArray(ids) ? ids : (ids ? [ids] : []);
        const now = Date.now() / 1000;
        function span(sec) {              // 42 -> "42 s", 155 -> "2:35"
            return sec > 60 ? Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0")
                            : sec + " s";
        }
        // FR-13: the absolute time of the last measurement, "20.10. 14:35:12" - the same shape
        // as measured_at() on the server, but from the browser's own clock and time zone (the
        // epoch in `device_times` carries no zone, so this is also what NFR-09 wants on a
        // correctly set browser).
        function measuredAt(sec) {
            const d = new Date(sec * 1000);
            function p(v) { return String(v).padStart(2, "0"); }
            return p(d.getDate()) + "." + p(d.getMonth() + 1) + ". " +
                   p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
        }
        return list.map(function (id) {
            const t = times ? times[id.device] : null;
            const last = (t && t.last !== null && t.last !== undefined)
                ? "last: " + measuredAt(t.last) + " (" +
                  span(Math.max(0, Math.round(now - t.last))) + " ago)"
                : "last: -";
            let upcoming = "upcoming: -";
            if (t && t.due !== null && t.due !== undefined) {
                const left = Math.round(t.due - now);
                upcoming = left > 0 ? "upcoming: in " + span(left) : "upcoming: overdue";
            }
            return last + " · " + upcoming;
        });
    }
    """,
    Output({"type": "times", "device": ALL, "slot": ALL}, "children"),
    Input("tick1s", "n_intervals"),
    State("device_times", "data"),
    State({"type": "times", "device": ALL, "slot": ALL}, "id"),
)

# Plotly figures cannot react to CSS media queries, so the server has to know the breakpoint:
# this writes `{"mobile": true}` into the `viewport` store while the window is narrower than
# Tailwind's `md` (768 px) - and only when the breakpoint actually changes, so a dragged window
# does not spam the callbacks. `update_chart` and `update_dashboard` read the store to drop the
# chart legend and shorten the axis titles on a phone (NFR-06).
app.clientside_callback(
    """
    function (n) {
        const mobile = window.innerWidth < 768;
        if (window.__ispindelMobile === mobile) { return window.dash_clientside.no_update; }
        window.__ispindelMobile = mobile;
        return {mobile: mobile};
    }
    """,
    Output("viewport", "data"),
    Input("tick1s", "n_intervals"),
)

# ---- callbacks ------------------------------------------------------------

@app.callback(Output("devices", "children"), Output("devices-table", "children"),
              Output("exp-running", "children"), Output("exp-completed", "children"),
              Output("exp-tab-running", "children"), Output("exp-tab-completed", "children"),
              Output("exp-tab-devices", "children"),
              Input("tick", "n_intervals"), Input("reload", "data"),
              Input("viewport", "data"), Input("chart-select", "data"),
              State("open_cards", "data"))
def update_dashboard(_, __, viewport, selected, open_cards):
    """Everything that changes over time: the device cards, the three views of the experiment panel
    (FR-05 running / completed + the FR-12 Devices table) and the tab labels with their counts.

    `chart-select` is an Input as well, so toggling an experiment in the chart (FR-17) re-renders
    the tables and the chosen row's chart icon turns blue immediately.
    """
    rows = experiment_rows()
    running = [r for r in rows if r["is_active"]]
    completed = [r for r in rows if not r["is_active"]]
    devices = device_rows()
    return (ispindel_overview(open_cards or {}, (viewport or {}).get("mobile", False)),
            device_table(devices),
            experiment_table(running, selected, empty="no experiment is running"),
            experiment_table(completed, selected, empty="no experiment has been completed yet"),
            f"Running ({len(running)})", f"Completed ({len(completed)})",
            f"Devices ({len(devices)})")


@app.callback(Output("device_times", "data"), Input("tick1s", "n_intervals"))
def update_device_times(_):
    """The last measurement and the next transmission per device, as absolute epochs - a tiny
    query, so it can run every `dashboard.live_ms`. The card footer turns them into relative
    text ("last: 12 s ago · upcoming: in 12 s") in the browser, so the age stays correct
    between the slow dashboard refreshes and the countdown does not keep pointing at a
    transmission that already arrived."""
    times = {}
    for row in query("SELECT mqtt_name, recorded_at, interval_s FROM v_device_latest"):
        last, interval = row["recorded_at"], row["interval_s"]
        if last is None:
            times[row["mqtt_name"]] = {"last": None, "due": None}
            continue
        times[row["mqtt_name"]] = {
            "last": last.timestamp(),
            "due": (last + timedelta(seconds=interval)).timestamp() if interval else None,
        }
    return times


def ispindel_overview(open_cards=None, mobile=False):
    """One **batch card** per iSpindel: the three data zones plus the device's own
    fermentation chart ("Gärdiagramm"). Rebuilt on every refresh.

    `open_cards` maps "device#slot" to whether that card is open - it comes from the
    `open_cards` store so a rebuild does not close what the user opened (README 1.9).
    `mobile` comes from the `viewport` store and is passed to every card so the charts can
    drop their legend on a phone (NFR-06).
    """
    open_cards = open_cards or {}
    rows = query("""SELECT l.device_id, l.mqtt_name, l.recorded_at, l.tilt_deg, l.temp_c,
                           l.gravity_plato, l.battery_v, l.interval_s, l.rssi_dbm
                    FROM v_device_latest l JOIN device d ON d.id = l.device_id
                    WHERE d.is_active
                    ORDER BY l.mqtt_name""")
    if not rows:
        return html.P("no iSpindel has reported yet", className="text-sm text-slate-400")
    history = query("""SELECT device_id, recorded_at,
                              gravity_plato::float8 AS gravity_plato,
                              temp_c::float8 AS temp_c
                       FROM measurement
                       WHERE recorded_at >= now() - make_interval(days => %(days)s)
                       ORDER BY device_id, recorded_at""",
                    {"days": CHART_DAYS})
    by_device = {}
    for row in history:
        by_device.setdefault(row["device_id"], []).append(row)
    # FR-04/FR-13/FR-20: which experiment currently runs on which iSpindel. The card needs more
    # than the name now - its `beer_style` (the target temperature window) and its OG (attenuation,
    # target FG, ABV) come from the same row. The exclusion constraint guarantees at most one
    # running experiment per device, so a plain dict is enough.
    active = {r["device_id"]: r
              for r in query("""SELECT device_id, name, beer_style, og_plato::float8 AS og_plato
                                FROM experiment WHERE ended_at IS NULL""")}
    if DEV_REPEAT > 1:                       # development only, see DEV_REPEAT
        rows = rows[:1] * DEV_REPEAT
    # `slot` only exists so the repeated cards get unique ids
    cards = [device_card(row, by_device.get(row["device_id"], []), slot,
                         open_cards.get(f"{row['mqtt_name']}#{slot}", False),
                         active.get(row["device_id"]), mobile)
             for slot, row in enumerate(rows)]
    # 12 columns: one card per row on a phone, two from md, three only from xxl (1536px)
    return dmc.Grid(gutter=16, children=[
        dmc.GridCol(card, span={"base": 12, "md": 6, "xxl": 4}) for card in cards
    ])


def measured_at(epoch):
    """The absolute time of a measurement in local time, e.g. ``20.10. 14:35:12``.

    FR-13 asks for the **time of the last measurement**, not only for how old it is - so the
    card shows both: this stamp and, in brackets, the age that ticks in the browser. Formatted
    like the FR-05 table (local time, day.month - NFR-09); the 1 s clientside callback rebuilds
    exactly this string from the epoch, with the browser clock and the browser time zone.
    """
    if epoch is None:
        return "-"
    return f"{local(datetime.fromtimestamp(epoch, timezone.utc)):%d.%m. %H:%M:%S}"


def times_text(last, due):
    """The footer times line of a device card:
    "last: 20.10. 14:35:12 (12 s ago) · upcoming: in 12 s".

    Same wording as the 1 s clientside callback - this is only the first paint, the callback
    rewrites it on the next tick.
    """
    def span(seconds):
        return f"{seconds // 60}:{seconds % 60:02d}" if seconds > 60 else f"{seconds} s"

    now = datetime.now(timezone.utc).timestamp()
    ago = "last: -" if last is None else \
        f"last: {measured_at(last)} ({span(max(0, int(round(now - last))))} ago)"
    if due is None:
        return f"{ago} · upcoming: -"
    left = int(round(due - now))
    return f"{ago} · upcoming: in {span(left)}" if left > 0 else f"{ago} · upcoming: overdue"


def plot(figure, className=""):
    """A `dcc.Graph` that fills a wrapper div.

    The wrapper carries a Tailwind height class, so the chart can be sized per breakpoint;
    `height: 100%` on the graph needs that definite height on the parent, and the figures are
    built with `height=None`/`autosize` to follow the container.
    """
    return html.Div(className=className, children=[
        dcc.Graph(figure=figure, style={"height": "100%"}, config=GRAPH_CONFIG)
    ])


def header_stat(value, className, title=""):
    """One value in the card header: the number with its unit in the same row, e.g. `27.1 °P`.

    `className` carries the text colour - and `group-open:hidden` for the two values the zones
    take over once the card is open. It is written out at the call site (device_card), so both
    Tailwind and the editor see the literal class names.
    """
    return html.Div(value, title=title or None,
                    className="text-right text-lg font-semibold tabular-nums " + className)


def status_dot(warn):
    """FR-19: the round dot next to the device name - green while the iSpindel is healthy.

    It turns **red** as soon as one of the two FR-19 conditions holds: the device has not sent
    data for more than three intervals (or never reported at all), or its battery voltage is
    below `dashboard.battery_warn_v`. Both conditions use the same dot, so the header stays a
    single quiet line. The dot lives in the `<summary>`, which is why it is visible while the
    card is collapsed *and* while it is expanded - the **reason** is text and is therefore only
    written in the expanded half of the card (`card_warnings`), never in the collapsed header
    (not even as a tooltip).
    """
    return html.Span(
        className=("inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-red-500" if warn else
                   "inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500"),
        title="warning - expand this card for the reason" if warn
              else "healthy: current data, battery above the warning threshold",
    )


def card_warnings(stale, age, interval_s, volts, low):
    """FR-19: the explanations of the red status dot, one line per condition (expanded card).

    `stale` means "no measurement for more than three intervals" and covers the device that
    has never reported; `low` is the battery below the configured threshold.
    """
    lines = []
    if stale:
        if age is None:
            lines.append("no data yet - this iSpindel has not reported")
        else:
            lines.append(f"no data for {int(age // 60)} min "
                         f"(more than three intervals of {ui.num(interval_s, 0)} s)")
    if low:
        lines.append(f"battery low: {volts:.3f} V is below the {BATTERY_WARN:.2f} V threshold")
    return lines


def battery_percent(volts, empty_v, full_v):
    """Li-Ion cell voltage -> charge in percent, clamped to 0..100 (the card header, FR-13).

    The iSpindel reports volts, the reference dashboard shows percent; the limits are settings
    (`dashboard.battery_empty_v` / `battery_full_v`, NFR-08).
    """
    if volts is None:
        return 0.0
    return max(0.0, min(100.0, (volts - empty_v) / (full_v - empty_v) * 100))


def value_text(value, unit="", digits=1):
    """`15.9 °P` / `94%` - and a plain `-` while the value is unknown (never `- °P`)."""
    return "-" if value is None else f"{value:.{digits}f}{unit}"


def sg_from_plato(plato):
    """°P -> specific gravity, the inverse of the ingest's `plato_from_sg()` (FR-08/FR-20)."""
    return 1 + plato / (258.6 - 0.8795 * plato)


def attenuation_percent(og_plato, fg_plato):
    """Apparent attenuation in % - `(OG - FG) / OG`, both in °P (FR-20).

    `None` while the OG or the gravity to compare with is unknown, which is what the card shows as
    `-`. Clamped at 0: a fermentation cannot have *gained* extract, and an uncalibrated device can
    report more °P than its own OG (the `dfp_os_01` ~30 °P case documented in the concept).
    """
    if not og_plato or fg_plato is None:
        return None
    return max(0.0, (og_plato - fg_plato) / og_plato * 100)


def abv_percent(og_plato, fg_plato):
    """Estimated alcohol by volume in %: the common `(OG - FG) * 131.25` rule of thumb on SG (FR-20).

    Same guards and the same clamp at 0 as `attenuation_percent`.
    """
    if og_plato is None or fg_plato is None:
        return None
    return max(0.0, (sg_from_plato(og_plato) - sg_from_plato(fg_plato)) * 131.25)


def target_fg(og_plato):
    """The expected final gravity: the configured apparent attenuation applied to the OG (FR-20)."""
    return None if og_plato is None else og_plato * (1 - EXPECTED_ATTENUATION / 100)


def target_temp_range(style):
    """`dashboard.target_temp_c` for a beer style: first keyword contained in it, else `default`.

    Matching case-insensitively and by substring keeps the config short and readable (`"ipa"`
    matches "West Coast IPA", `"bock"` matches "Bock (cold cellar)"); an unknown style falls back
    to the `default` window.
    """
    if style:
        for keyword, span in TARGET_TEMP_C.items():
            if keyword != "default" and keyword in style.lower():
                return span
    return TARGET_TEMP_C.get("default")


def temp_hint(temp, span):
    """`(text, state)` for the deviation from a target temperature window, else `None`.

    `state` is `"high"`, `"low"` or `"in"`; the **caller** turns it into the Tailwind class, because
    a class name has to be written out literally inside the `className` argument (see ui.py) and a
    function can never satisfy that rule.
    """
    if temp is None or not span:
        return None
    low, high = span
    if temp > high:
        return f"\u25b2 {temp - high:.1f} °C High", "high"
    if temp < low:
        return f"\u25bc {low - temp:.1f} °C Low", "low"
    return "\u2713 in range", "in"


def gravity_rate(points, hours=24):
    """Gravity change per 24 h in °P (FR-20) - negative while the fermentation is running.

    Takes the newest point and the newest point at least `hours` back, and scales the difference by
    the time actually between them, so a longer gap (a missed transmission, a 30 min test interval)
    does not distort the rate. `None` while the history is shorter than the window - the card then
    shows `Rate: -` instead of a made-up number.
    """
    if len(points) < 2:
        return None
    newest = points[-1]
    cutoff = newest["recorded_at"] - timedelta(hours=hours)
    older = [p for p in points if p["recorded_at"] <= cutoff]
    if not older or newest["gravity_plato"] is None or older[-1]["gravity_plato"] is None:
        return None
    before = older[-1]
    spent = (newest["recorded_at"] - before["recorded_at"]).total_seconds() / 3600
    return None if not spent else (newest["gravity_plato"] - before["gravity_plato"]) / spent * 24


def status_chip(running, warn):
    """FR-13/FR-19: the pill in the batch-card header - the batch state plus the single health dot.

    The dot is `status_dot()`, so the header keeps exactly one indicator: green while the iSpindel
    is healthy, red as soon as one of the two FR-19 conditions holds. The **label** is the batch
    state ("active" while an experiment runs, "idle" without one) and never a warning text - the
    reason is written in the expanded half of the card only (`card_warnings`).
    Deliberately **not** `ui.badge()`: that is the notification pill of FR-05/FR-19, and
    `tools/fr19_test.py` asserts that a card carries none of them.
    """
    return html.Span(
        className="inline-flex shrink-0 items-center gap-1.5 "
                  "bg-white px-1.5 py-0.5 text-[10px] font-semibold "
                  "uppercase tracking-wide text-slate-500",
        title="healthy and running" if running and not warn else
              "healthy, no experiment running" if not warn else
              "expand this card for the reason",
        children=[status_dot(warn)],
    )


def device_card(latest, points, slot=0, is_open=False, batch=None, mobile=False):
    """One iSpindel as a collapsible **batch card** (FR-13, FR-20).

    Collapsed it shows the batch name plus the beer style, the status chip, the three current
    values (gravity, temperature, battery) and the health dot; opened it reveals three **data
    zones** - gravity (with the OG, the target FG and the 24 h rate), temperature (with its target
    window and the deviation) and the derived attenuation / ABV - followed by the device's own
    fermentation chart, the experiment controls and the footer line.

    `batch` is the experiment running on this device (`{"name", "beer_style", "og_plato"}`, built by
    `ispindel_overview`) or None when there is none - the card then wears the device name and shows
    `-` wherever an OG-based value would be. `points` is the device's measurement history (the 24 h
    rate needs it) and `mobile` comes from the `viewport` store (NFR-06).
    """
    age = None if latest["recorded_at"] is None else \
        (datetime.now(timezone.utc) - latest["recorded_at"]).total_seconds()
    # FR-19: silent for more than three intervals, or never reported at all
    stale = age is None or (bool(latest["interval_s"]) and age > 3 * latest["interval_s"])
    volts = latest["battery_v"]
    low = volts is not None and volts < BATTERY_WARN                                  # FR-19
    # FR-19: the two conditions as text for the expanded card. The header dot only carries the
    # colour, so a collapsed card stays one line per device.
    warnings = card_warnings(stale, age, latest["interval_s"], volts, low)
    warnings_html = html.Div(
        className="mb-2 flex flex-col gap-1",
        children=[html.Div(line, className="text-xs font-medium text-red-600")
                  for line in warnings],
    ) if warnings else None
    pct = battery_percent(volts, BATTERY_EMPTY, BATTERY_FULL)
    # the footer times line counts from these two epochs (FR-13/FR-14); the clientside callback
    # turns them into "last: 12 s ago" / "upcoming: in 12 s"
    last_epoch = None if latest["recorded_at"] is None else latest["recorded_at"].timestamp()
    due = None if (last_epoch is None or not latest["interval_s"]) else \
        last_epoch + latest["interval_s"]
    name = latest["mqtt_name"]
    # FR-04/FR-13: while an experiment runs the card wears the **experiment name** - the iSpindel
    # name moves to the footer, so the card still says which device it is (FR-15 wants the
    # iSpindels distinguishable by name); a running batch also gets the stronger outline.
    running = bool(batch)
    heading = batch["name"] if running else name
    style = (batch["beer_style"] or None) if running else None
    series = [{"label": name, "points": points}] if points else []
    # FR-20: the zone values, derived once from the experiment (OG, beer style) and the device's own
    # history. Every helper returns None for a missing input, which the zones render as "-".
    gravity, temp = latest["gravity_plato"], latest["temp_c"]
    og = batch["og_plato"] if running else None
    fg_target = target_fg(og)
    attenuation = attenuation_percent(og, gravity)
    abv = abv_percent(og, gravity)
    est_abv = abv_percent(og, fg_target)
    rate = gravity_rate(points)
    target_span = target_temp_range(style) if running else None
    hint = temp_hint(temp, target_span)
    return html.Details(
        # `id` gives React a stable key - Dash otherwise falls back to the index path, and a
        # remount drops the `open` attribute. `open` is restored from the `open_cards` store,
        # which app/assets/card_state.js keeps up to date on every toggle, so neither a
        # remount nor a refresh can close a card the user opened.
        id={"type": "card", "device": name, "slot": slot},
        open=is_open,
        **{"data-card": f"{name}#{slot}"},
        # The card itself is the clickable surface. `group` has to stay - the three
        # `group-open:` variants inside (chevron rotation, hiding the collapsed
        # gravity/temperature values) only match while an ancestor carries it - and `border`
        # is what gives the border colour a width at all. Every container is white with the brand
        # blue (#0057B7) as its outline (`border-brand`, token in input.pcss); a **running**
        # experiment gets the thicker outline plus a yellow (page-colour) ring so it still stands
        # out against the identical idle outline (FR-04).
        # Deliberately without `animate-fade-in` (removed 20.10.2026: it looked buggy on grid
        # rebuilds). The outline of a running experiment is written out below, not built up.
        className=("group rounded-xl corner-squircle border-2 border-brand bg-white transition-colors "
                   "ring-2 ring-page" if running else
                   "group rounded-xl corner-squircle border border-brand bg-white transition-colors"),
        children=[
            html.Summary(
                className="flex cursor-pointer list-none items-center justify-between gap-3 "
                          "p-3 [&::-webkit-details-marker]:hidden sm:p-4",
                children=[
                    html.Div(className="min-w-0", children=[
                        html.Div(className="flex min-w-0 items-center gap-2", children=[
                            # FR-04: while an experiment runs this is the **experiment** name -
                            # the iSpindel name moves to the footer, and the tooltip keeps the
                            # device reachable without extra space in a one-line header.
                            html.H3(heading, title=f"iSpindel {name}" if running else None,
                                    className="min-w-0 truncate text-base font-semibold "
                                              "text-slate-800"),
                            # FR-20/FR-13: which beer this batch is - the experiment's `beer_style`
                            # is also what picks the target temperature window of zone 2. Hidden on
                            # a phone, where the header has room for the name only.
                            # html.Span("\u2022", className="hidden text-slate-300 sm:inline")
                            # if style else None,
                            # html.Span(style, className="hidden truncate text-xs text-slate-500 "
                            #                            "sm:inline") if style else None,
                            # FR-13/FR-19: the batch state and the single health dot in one pill.
                            # It sits in the <summary>, so it is visible while the card is
                            # collapsed *and* expanded; the **reason** is text and is rendered in
                            # the expanded half only.
                            status_chip(running, bool(warnings)),
                        ]),
                        # The last measurement and the next transmission live in the card footer
                        # (they tick there) - the header stays a single quiet line per device.
                    ]),
                    html.Div(className="flex shrink-0 items-center gap-3 sm:gap-4", children=[
                        # gravity and temperature matter only while collapsed - the zones
                        # show them as soon as the card is open, so they hide there
                        header_stat(f"{ui.num(gravity, 1)} °P",
                                    className="text-yellow-600 group-open:hidden"),
                        header_stat(f"{ui.num(temp, 1)} °C",
                                    className="text-purple-700 group-open:hidden"),
                        header_stat(f"Bat: {pct:.0f} %",
                                    className=("text-amber-600" if low else "text-emerald-600")),
                        # chevron: a corner rotated 45 deg points down, 225 deg points up
                        html.Span(className="ml-1 h-2 w-2 rotate-45 border-b-2 border-r-2 "
                                             "border-slate-400 transition-transform duration-200 "
                                             "group-open:rotate-[225deg]"),
                    ]),
                ],
            ),
            html.Div(className="px-3 pb-3 sm:px-4 sm:pb-4", children=[
                # FR-19: why the dot next to the device name is red - one line per condition,
                # text only, because the circle in the header already warns while collapsed.
                warnings_html,
                # FR-13/FR-20: the three **data zones** - how much sugar is left, is it warm
                # enough, how far has the batch come. Three across from `sm`, stacked on a phone
                # (NFR-06); they replaced the two Plotly dials on 20.10.2026. Every value that is
                # not there yet renders as "-" instead of a made-up number.
                dmc.Grid(gutter=8, children=[
                    # GRAVITY: the reading, the batch's OG, the target FG and the 24 h rate
                    dmc.GridCol(ui.zone(
                        "Gravity",
                        html.Div(className="flex items-baseline gap-1.5", children=[
                            html.Span(ui.num(gravity, 1),
                                      className="text-2xl font-semibold tabular-nums "
                                                "text-yellow-600"),
                            html.Span("°P", className="text-sm text-slate-500"),
                            html.Span(f"(OG {value_text(og, ' °P')})",
                                      className="text-xs text-slate-400"),
                        ]),
                        html.Div(f"Target FG: ~{value_text(fg_target, ' °P')}",
                                 className="mt-1 text-xs text-slate-500"),
                        html.Div(className="text-xs text-slate-500", children=[
                            "Rate: ",
                            # a *falling* gravity is the fermentation working (green), a rising
                            # one is wrong (red) - no colour while the history is too short
                            html.Span(value_text(rate, " °P/24h"), className=(
                                "font-medium text-emerald-600"
                                if rate is not None and rate < 0 else
                                "font-medium text-red-600" if rate is not None else "")),
                        ]),
                    ), span={"base": 12, "sm": 4}),
                    # TEMPERATURE: the reading, the target window of the beer style and how far
                    # the reading is off it
                    dmc.GridCol(ui.zone(
                        "Temperature",
                        html.Div(className="flex items-baseline gap-1.5", children=[
                            html.Span(ui.num(temp, 1),
                                      className="text-2xl font-semibold tabular-nums "
                                                "text-purple-700"),
                            html.Span("°C", className="text-sm text-slate-500"),
                        ]),
                        html.Div(f"Target: {target_span[0]:.1f}\u2013{target_span[1]:.1f} °C"
                                 if target_span else "Target: -",
                                 className="mt-1 text-xs text-slate-500"),
                        html.Div(hint[0], className=(
                            "text-xs font-medium text-amber-600"
                            if hint and hint[1] == "high" else
                            "text-xs font-medium text-sky-700" if hint and hint[1] == "low" else
                            "text-xs font-medium text-emerald-600")) if hint else None,
                    ), span={"base": 12, "sm": 4}),
                    # ATTENUATION & ABV (FR-20): how much of the extract is gone, how much alcohol
                    # is in there now and where the batch is heading
                    dmc.GridCol(ui.zone(
                        "Attenuation & ABV",
                        html.Div(className="flex items-baseline gap-2", children=[
                            html.Span(value_text(attenuation, "%"),
                                      className="text-2xl font-semibold tabular-nums "
                                                "text-slate-800"),
                            html.Span("Atten", className="text-xs text-slate-500"),
                            html.Span("|", className="text-slate-300"),
                            html.Span(value_text(abv, "%"),
                                      className="text-2xl font-semibold tabular-nums "
                                                "text-slate-800"),
                            html.Span("ABV", className="text-xs text-slate-500"),
                        ]),
                        html.Div(f"Est. Final: {value_text(est_abv, '% ABV')}",
                                 className="mt-1 text-xs text-slate-500"),
                    ), span={"base": 12, "sm": 4}),
                ]),
                plot(charts.fermentation_figure(series, height=None, legend=False,
                                                mobile=mobile),
                     className="h-40 sm:h-52"),
                # FR-01 - FR-04: the experiment controls of this iSpindel, lower left. A running
                # experiment is shown with a red end button; otherwise the grey button opens the
                # dialog. The iSpindel comes from the card, so it is never picked twice.
                html.Div(className="mt-3 flex flex-wrap items-center justify-between gap-2",
                         children=[
                    # FR-04/FR-15: the header carries the experiment name while one runs, so
                    # the footer names the **device** - together the card always says both.
                    html.Div(className="flex items-center gap-2 text-xs", children=[
                        html.Span("iSpindel:", className="text-slate-400"),
                        html.Span(name, className="font-medium text-slate-700"),
                    ]) if running else
                    html.Span("no experiment yet", className="text-xs text-slate-400"),
                    # The id keys must be EXACTLY the keys of the callback pattern
                    # ({"type", "device", "slot"}): dash-renderer looks the callback up by the
                    # sorted key names of the clicked id, so an extra key (e.g. "device_id")
                    # makes the click silently do nothing. The device is resolved from the name.
                    ui.button({"type": "end-btn", "device": name, "slot": slot},
                              "End experiment", tone="danger", compact=True) if running else
                    ui.button({"type": "setup-btn", "device": name, "slot": slot},
                              "Set up experiment", tone="grey", compact=True),
                ]),
                html.Div(className="mt-2 flex flex-wrap items-center justify-between "
                                   "gap-x-3 gap-y-1 text-xs text-slate-400", children=[
                    html.Span(f"tilt {ui.num(latest['tilt_deg'], 1)}° · "
                              f"RSSI {ui.num(latest['rssi_dbm'], 0)} dBm · "
                              f"interval {ui.num(latest['interval_s'], 0)} s"),
                    # FR-13/FR-14: the **time** of the last measurement (local time), how old it
                    # is and when the next transmission is due. The clientside callback rewrites
                    # this every second from `device_times`.
                    html.Span(id={"type": "times", "device": name, "slot": slot},
                              className="tabular-nums",
                              title="time of the last measurement, its age and the next "
                                    "transmission (FR-13 / FR-14, local time)",
                              children=times_text(last_epoch, due)),
                ]),
            ]),
        ],
    )


# FR-05: the columns of the experiment overview. Both tabs use the same header, so the FR-01
# optional fields are visible whether an experiment is running or finished.
TABLE_HEADERS = ["Name", "iSpindel", "Start Timestamp", "Status", "Measurements",
                 "Beer style", "OG °P", "Yeast", "Responsible", "End Timestamp", "Actions"]


def row_actions(exp_id, running=False, selected=False):
    """The action icons of one experiment row (FR-04 / FR-06 / FR-17 / FR-21).

    **Both** row states carry the two analysis actions:

    * `chart` (FR-17) toggles the experiment in the comparison chart - blue while it is shown,
      grey otherwise, so the row itself says what is overlaid;
    * `csv` (FR-21) exports **this** experiment as a CSV over the selected FR-16 time range.

    Then the state-specific actions:

    * `edit` (FR-06) is on **both** states - a running experiment can be corrected while it runs
      (the edit form never touches the end time, that is written by ending it, FR-04);
    * a **running** experiment adds `end` (FR-04) - there is nothing to delete about a batch that
      is still filling, so deleting stays a completed-only action;
    * a **completed** experiment adds `delete` (FR-06).

    Clicking any of them goes through `experiment_action` (the chart toggle also writes the
    `chart-select` store via `toggle_chart`); the ids are pattern ids, and the key set must match
    the callback exactly - an extra key makes the click silently do nothing.
    """
    def icon(kind, icon_name, label, colour):
        return dmc.Tooltip(
            label=label, position="top", withArrow=True, openDelay=300,
            children=dmc.ActionIcon(
                DashIconify(icon=icon_name, width=15),
                id={"type": "row-btn", "exp": exp_id, "mode": kind},
                variant="subtle", color=colour, size="sm", radius="md",
                **{"aria-label": f"{label} experiment"}))

    state_actions = [icon("edit", "tabler:pencil", "edit", "gray")]              # FR-06, both
    state_actions += ([icon("end", "tabler:circle-stop", "end", "red")] if running else
                      [icon("delete", "tabler:trash", "delete", "red")])         # FR-04 / FR-06
    return html.Div(className="flex items-center gap-1", children=[
        # FR-17: blue while the experiment is overlaid in the comparison chart, grey otherwise
        icon("chart", "tabler:chart-line",
             "remove from chart" if selected else "add to chart",
             "blue" if selected else "gray"),
        *state_actions,
        icon("csv", "tabler:download", "export as CSV", "gray"),    # FR-21
    ])


def experiment_rows():
    """The FR-05 rows, extended by the FR-01 optional fields (the notes become the tooltip)."""
    return query("""SELECT id, name, ispindel, started_at, ended_at, is_active, measurements,
                           beer_style, og_plato, yeast, responsible, notes
                    FROM v_experiment_overview""")


def experiment_table(rows, selected=(), empty="no data yet"):
    """One FR-05 table for the rows it is given - the caller decides running or completed.

    The `Actions` column follows the **row**: both states carry the FR-17 chart toggle, the FR-06
    edit icon and the FR-21 CSV export; a running row adds the FR-04 end button, a completed one
    the FR-06 delete icon (see `row_actions`). `selected` holds the experiment ids currently shown
    in the comparison chart, so the chart icon of those rows is filled (FR-17).
    """
    selected = set(selected or [])
    body = [[html.Span(r["name"], title=r["notes"] or None), r["ispindel"],
             f"{local(r['started_at']):%d. %b %y %H:%M}",
             ui.badge("active", "green") if r["is_active"] else ui.badge("completed", "slate"),
             str(r["measurements"]),
             r["beer_style"] or "-",
             ui.num(r["og_plato"], 1),
             r["yeast"] or "-",
             r["responsible"] or "-",
             f"{local(r['ended_at']):%d. %b %y %H:%M}" if r["ended_at"] else "-",
             row_actions(r["id"], running=r["is_active"], selected=r["id"] in selected)]
            for r in rows]
    return ui.table(TABLE_HEADERS, body, empty=empty)


# FR-12: the device master data (the `device` table). A new iSpindel appears here automatically -
# the ingest creates the row on the first message - and the table is where its settings are
# managed. FR-11 wants the transmission interval visible: every burst reports it (`interval_s`).
DEVICE_HEADERS = ["Name (MQTT topic)", "Display name", "Status", "First seen", "Last measurement",
                  "Interval", "Measurements", "Actions"]


def device_actions(device_id):
    """The one action of a device row (FR-12): open the settings dialog.

    The id is a pattern id and must keep exactly the callback's key set - the MQTT name is looked
    up from the id in `device_values()`, so it does not have to be part of the id.
    """
    return dmc.Tooltip(
        label="device settings", position="top", withArrow=True, openDelay=300,
        children=dmc.ActionIcon(
            DashIconify(icon="tabler:settings", width=15),
            id={"type": "dev-btn", "device": device_id},
            variant="subtle", color="gray", size="sm", radius="md",
            **{"aria-label": "device settings"}))


def device_rows():
    """One row per device: the master data plus what its latest measurement reported."""
    return query("""SELECT d.id, d.mqtt_name, d.display_name, d.is_active, d.first_seen_at,
                           l.recorded_at AS last_seen, l.interval_s,
                           (SELECT count(*) FROM measurement m
                            WHERE m.device_id = d.id) AS measurements
                    FROM device d
                    LEFT JOIN v_device_latest l ON l.device_id = d.id
                    ORDER BY d.mqtt_name""")


def device_table(rows, empty="no iSpindel has reported yet"):
    """The FR-12 device overview: every iSpindel the system knows, with its settings action."""
    body = [[html.Span(r["mqtt_name"]),
             r["display_name"] or "-",
             ui.badge("in use", "green") if r["is_active"] else ui.badge("ignored", "slate"),
             f"{local(r['first_seen_at']):%d. %b %y %H:%M}",
             f"{local(r['last_seen']):%d. %b %y %H:%M}" if r["last_seen"] else "-",
             f"{r['interval_s']} s" if r["interval_s"] else "-",
             str(r["measurements"]),
             device_actions(r["id"])] for r in rows]
    return ui.table(DEVICE_HEADERS, body, empty=empty)


def device_values(device_id):
    """The dialog's values for one device, or None when the row is gone (FR-12)."""
    rows = query("SELECT mqtt_name, display_name, is_active FROM device WHERE id = %s", (device_id,))
    if not rows:
        return None
    row = rows[0]
    return {"mqtt_name": row["mqtt_name"], "display_name": row["display_name"],
            "active": row["is_active"]}


def update_device(device_id, display_name, active):
    """FR-12: save the device settings (display name + the "in use" flag). Returns (alert, delta).

    The **MQTT name is deliberately not editable**: it is the `<name>` in
    `ispindel/<name>/<field>`, i.e. the identity the device publishes with - renaming it here
    would silently detach the device from everything it has already sent.
    """
    values = device_values(device_id)
    if values is None:
        return ui.alert("that iSpindel no longer exists", "amber"), 0
    name = (display_name or "").strip() or None
    execute("UPDATE device SET display_name = %s, is_active = %s WHERE id = %s",
            (name, bool(active), device_id))
    state = "in use" if active else "ignored"
    return ui.alert(f"iSpindel '{values['mqtt_name']}' saved - {state} (FR-12)", "green"), 1







@app.callback(Output("chart-select", "data"),
              Input({"type": "row-btn", "exp": ALL, "mode": ALL}, "n_clicks"),
              State({"type": "row-btn", "exp": ALL, "mode": ALL}, "id"),
              State("chart-select", "data"),
              prevent_initial_call=True)
def toggle_chart(clicks, ids, selected):
    """FR-17: the `chart` action of a table row adds / removes that experiment from the chart.

    The selection used to be a multi-select dropdown above the chart; since 20.10.2026 it lives
    in the `chart-select` store, written from the FR-05 table (the row action replaced the
    dropdown). A rebuild re-renders the rows, so the callback is guarded by `clicked()` like the
    card buttons - only `n_clicks > 0` on the chart icon itself toggles.
    """
    triggered = ctx.triggered_id
    if not (isinstance(triggered, dict) and triggered.get("type") == "row-btn"
            and triggered.get("mode") == "chart" and clicked(triggered, ids, clicks)):
        return dash.no_update
    selected = list(selected or [])
    exp_id = triggered.get("exp")
    if exp_id in selected:
        selected.remove(exp_id)
    else:
        selected.append(exp_id)
    return selected


def click_values(value):
    """Normalise a pattern-matching click input.

    With `ALL` the browser sends one value per matching component, but with a single card (the
    normal case, `DEV_REPEAT = 1`) the value can arrive as a scalar - iterating that would raise.
    """
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def clicked(triggered, ids, values):
    """True only if the button that fired this callback was really clicked.

    Dash also fires a pattern-matching callback when the number of matching components
    changes. Every dashboard rebuild re-renders the device cards, so the red "End experiment"
    button appears with `n_clicks = 0` - and acting on that ended an experiment the moment it
    was created (FR-04: it then had no measurements and nothing to show in the chart). Only
    `n_clicks > 0` on the triggering button itself counts. `ids` comes from a
    `State(..., "id")` and is in the same order as `values`, which is what makes the mapping
    from `ctx.triggered_id` to its own click count possible.
    """
    for component_id, value in zip(click_values(ids), click_values(values)):
        if component_id == triggered:
            return bool(value)
    return False


def resolve_device(value):
    """Accept a device id or an iSpindel name and return the numeric `device.id`.

    The card buttons carry both, but a name is also accepted so a mistake can never turn into a
    database error (500) - the user gets an amber message instead.
    """
    if value is None:
        return None
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        rows = query("SELECT id FROM device WHERE id = %s", (int(value),))
    else:
        rows = query("SELECT id FROM device WHERE mqtt_name = %s", (value,))
    return rows[0]["id"] if rows else None


def create_experiment(name, device_id, start, beer_style, og, yeast, responsible, notes):
    """FR-01: create and start an experiment. Returns (alert, reload_delta).

    The device comes from the card the dialog was opened on, so no second choice is needed -
    the database still guarantees one active experiment per iSpindel (FR-03).
    """
    device_id = resolve_device(device_id)
    if not name or not device_id:
        return ui.alert("a name is required (FR-01)", "amber"), 0
    if start:                                                       # local time in, UTC stored
        try:
            started = datetime.fromisoformat(str(start).strip()).astimezone()
        except ValueError:
            return ui.alert("start must look like 2026-11-12T16:30, or stay empty for 'now'",
                            "amber"), 0
    else:
        started = datetime.now().astimezone()

    # the optional fields: an empty input arrives as "" (text) or None (number) -> store NULL
    def text(value):
        return value.strip() or None if isinstance(value, str) else None

    if og in ("", None):
        og_plato = None
    else:
        try:
            og_plato = float(og)
        except (TypeError, ValueError):
            return ui.alert("original gravity must be a number like 14.5, or stay empty",
                            "amber"), 0
    try:
        execute("""INSERT INTO experiment
                       (name, device_id, started_at, beer_style, og_plato, yeast, responsible, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (name.strip(), device_id, started, text(beer_style), og_plato, text(yeast),
                 text(responsible), text(notes)))
    except psycopg.errors.UniqueViolation:                              # FR-02
        return ui.alert(f"'{name}' already exists - names must be unique (FR-02)", "red"), 0
    except psycopg.errors.ExclusionViolation:                           # FR-03
        return ui.alert("this iSpindel already runs an experiment - end it first (FR-03)",
                        "red"), 0
    return ui.alert(f"experiment '{name}' started (FR-01)", "green"), 1


def end_experiment(device):
    """FR-04: end the experiment that is active on a device (id or iSpindel name).

    Returns (alert, reload_delta).
    """
    device_id = resolve_device(device)
    if not device_id:
        return ui.alert("unknown iSpindel", "amber"), 0
    row = query("""SELECT id, name FROM experiment
                   WHERE device_id = %s AND ended_at IS NULL LIMIT 1""", (device_id,))
    if not row:
        return ui.alert("this iSpindel has no running experiment", "amber"), 0
    execute("UPDATE experiment SET ended_at = now() WHERE id = %s", (row[0]["id"],))
    return ui.alert(f"experiment '{row[0]['name']}' ended - new measurements are no longer "
                    f"assigned to it (FR-04)", "green"), 1


def form_values(row):
    """The dialog's field values from one experiment row (FR-01 - FR-06).

    One shape for every mode of the dialog: ``create`` builds it from empty, ``edit``/``delete``
    from the table's row, the FR-04 **end confirmation** from the running experiment.
    """
    return {
        "name": row["name"],
        # the start field is free text (NFR-05) - hand it exactly the shape it accepts
        "start": f"{local(row['started_at']):%Y-%m-%dT%H:%M}",
        "style": row["beer_style"],
        "og": float(row["og_plato"]) if row["og_plato"] is not None else None,
        "yeast": row["yeast"],
        "responsible": row["responsible"],
        "notes": row["notes"],
    }


def active_experiment(device):
    """The experiment that is running on a device (id or iSpindel name), as form values - or None.

    FR-04: the end confirmation shows what it is about to end, so it needs the same field values
    the edit dialog uses. The name is accepted as well as the id so a wrong value can never turn
    into a database error (see `resolve_device`).
    """
    device_id = resolve_device(device)
    if not device_id:
        return None
    rows = query("""SELECT name, started_at, beer_style, og_plato, yeast, responsible, notes
                    FROM experiment WHERE device_id = %s AND ended_at IS NULL LIMIT 1""",
                 (device_id,))
    return form_values(rows[0]) if rows else None


def experiment_device(exp_id):
    """The iSpindel name of an experiment (id) - the running FR-05 row ends it *by device* (FR-04).

    The row's icon carries the experiment id only: the callback pattern for the table is
    `{"type": "row-btn", "exp": ..., "mode": ...}`, and an extra key would make the click stop
    matching (see `row_actions`). The device is therefore looked up here, and the confirmation
    dialog is built exactly like the one of the card's red button.
    """
    rows = query("""SELECT d.mqtt_name FROM experiment e JOIN device d ON d.id = e.device_id
                    WHERE e.id = %s""", (exp_id,))
    return rows[0]["mqtt_name"] if rows else None


def experiment_form_values(exp_id):
    """The dialog's field values for an existing experiment (FR-06: edit it afterwards).

    Returns None when the row is gone (someone else deleted it in the meantime).
    """
    rows = query("""SELECT name, started_at, beer_style, og_plato, yeast, responsible, notes
                    FROM experiment WHERE id = %s""", (exp_id,))
    return form_values(rows[0]) if rows else None


def update_experiment(exp_id, name, start, beer_style, og, yeast, responsible, notes):
    """FR-06: save the edited fields of an existing experiment.

    Returns (alert, reload_delta) like create_experiment, so the dialog treats both the same.
    The end time is not touched here - that stays what "End experiment" wrote (FR-04).
    """
    if not name or not name.strip():
        return ui.alert("a name is required (FR-01)", "red"), 0
    if start and start.strip():
        try:
            started = datetime.fromisoformat(start).astimezone()
        except ValueError:
            return ui.alert("the start must look like 2026-11-12T16:30 (FR-01)", "amber"), 0
    else:
        started = None                                    # keep the stored start

    if og in ("", None):
        og_plato = None
    else:
        try:
            og_plato = float(og)
        except (TypeError, ValueError):
            return ui.alert("original gravity must be a number like 14.5, or stay empty",
                            "amber"), 0

    def text(value):
        return value.strip() or None if isinstance(value, str) else None

    try:
        execute("""UPDATE experiment SET name = %s, started_at = COALESCE(%s, started_at),
                          beer_style = %s, og_plato = %s, yeast = %s, responsible = %s, notes = %s
                   WHERE id = %s""",
                (name.strip(), started, text(beer_style), og_plato, text(yeast),
                 text(responsible), text(notes), exp_id))
    except psycopg.errors.UniqueViolation:                              # FR-02
        return ui.alert(f"'{name}' already exists - names must be unique (FR-02)", "red"), 0
    except psycopg.errors.ExclusionViolation:                           # FR-03
        return ui.alert("that start would overlap another experiment on this iSpindel (FR-03)",
                        "red"), 0
    except psycopg.errors.CheckViolation:
        return ui.alert("the start must stay before the end of the experiment", "red"), 0
    return ui.alert(f"experiment '{name.strip()}' updated (FR-06)", "green"), 1


def delete_experiment(exp_id):
    """Delete an experiment **and its measurements**.

    `measurement.experiment_id` has no ON DELETE CASCADE, so the rows have to go first - the
    dialog shows the count before this runs, so nothing disappears unseen.
    """
    rows = query("""SELECT e.name, count(m.id) AS measurements FROM experiment e
                    LEFT JOIN measurement m ON m.experiment_id = e.id
                    WHERE e.id = %s GROUP BY e.id, e.name""", (exp_id,))
    if not rows:
        return ui.alert("that experiment no longer exists", "amber"), 0
    name, measurements = rows[0]["name"], rows[0]["measurements"]
    execute("DELETE FROM measurement WHERE experiment_id = %s", (exp_id,))
    execute("DELETE FROM experiment WHERE id = %s", (exp_id,))
    return ui.alert(f"experiment '{name}' deleted, including its {measurements} measurements",
                    "green"), 1


@app.callback(Output("exp-target", "data"), Output("exp-modal", "opened"),
              Output("exp-modal", "title"), Output("exp-submit", "children"),
              # the two forms of the dialog: the experiment fields, and (hidden until needed) the
              # device fields of FR-12. **Both belong to the static layout** - Dash validates the
              # ids of a callback's State against the initial layout, so the device fields must
              # exist even while the experiment form is showing. That is what keeps the usual
              # `suppress_callback_exceptions` out of this app.
              Output("exp-form", "children"), Output("exp-form", "style"),
              Output("dev-form", "children"), Output("dev-form", "style"),
              Output("msg", "children"), Output("modal-msg", "children"), Output("reload", "data"),
              # FR-21: the CSV row action writes the download here (the export button moved from
              # the chart card onto the FR-05 rows)
              Output("download", "data"),
              Input({"type": "setup-btn", "device": ALL, "slot": ALL}, "n_clicks"),
              Input({"type": "end-btn", "device": ALL, "slot": ALL}, "n_clicks"),
              Input({"type": "row-btn", "exp": ALL, "mode": ALL}, "n_clicks"),
              # FR-12: the settings icon of a row in the Devices table
              Input({"type": "dev-btn", "device": ALL}, "n_clicks"),
              Input("exp-cancel", "n_clicks"), Input("exp-submit", "n_clicks"),
              State("exp-target", "data"),
              State("new-name", "value"), State("new-start", "value"), State("new-style", "value"),
              State("new-og", "value"), State("new-yeast", "value"),
              State("new-responsible", "value"), State("new-notes", "value"),
              State("reload", "data"),
              # the rendered ids of every button pattern - with the values they let `clicked()`
              # tell a real click from the spurious trigger a rebuild causes (see `clicked`)
              State({"type": "setup-btn", "device": ALL, "slot": ALL}, "id"),
              State({"type": "end-btn", "device": ALL, "slot": ALL}, "id"),
              State({"type": "row-btn", "exp": ALL, "mode": ALL}, "id"),
              State("range", "value"),                       # FR-22: the export time range
              # FR-12: the fields of the device dialog (the same modal, a different form)
              State("dev-name", "value"), State("dev-active", "value"),
              State({"type": "dev-btn", "device": ALL}, "id"),
              prevent_initial_call=True)
def experiment_action(setup_clicks, end_clicks, row_clicks, dev_clicks, _, __, target, name, start,
                      style, og, yeast, responsible, notes, reload_data, setup_ids, end_ids,
                      row_ids, range_key, dev_name, dev_active, dev_ids):
    """Everything around an experiment: open the dialog, create, edit, delete, cancel, end, and the
    two row actions of the FR-05 table - chart (FR-17, handled by `toggle_chart`) and csv (FR-21).

    One callback because all of it writes `exp-modal.opened` - Dash allows only a single callback
    per output. `exp-target` holds what the dialog is working on:
        None                                       -> closed
        {"mode": "create", "device": <name>}       -> a new experiment on that iSpindel
        {"mode": "end", "device": <name>}          -> end the running one (FR-04, confirmation)
        {"mode": "edit"|"delete", "id": <id>}      -> an existing experiment (FR-06)
        {"mode": "device", "id": <device id>}      -> the settings of an iSpindel (FR-12)
    The "end" mode is reached from the red button of a device card (`end-btn`, FR-04) and from the
    end icon of a running FR-05 row (`row-btn` with `mode: end`); the "edit" mode from the pencil
    of **any** row (running or completed, FR-06) and "delete" only from a completed row (FR-06).
    The `chart` icon of a row (FR-17) is handled by `toggle_chart` and only has to be swallowed
    here; the `csv` icon of a row (FR-21) exports that experiment over the selected FR-16 range;
    the settings icon of a **Devices** row (`dev-btn`, FR-12) opens the device dialog (read-only
    MQTT name, display name, "in use" flag).
    Validation errors go into the dialog (`modal-msg`), where the user still is; successes go to
    the page (`msg`) as a toast.
    """
    reload_data = reload_data or 0
    triggered = ctx.triggered_id
    target = target or {}

    # the response shape of the callback (12 outputs) - `shape` keeps it readable. The order is
    # exp-target, opened, title, submit label, exp-form children, exp-form style, dev-form
    # children, dev-form style, msg, modal-msg, reload, download.
    hidden, shown = {"display": "none"}, {"display": "block"}

    def shape(*, target=dash.no_update, opened_=dash.no_update, title=dash.no_update,
              label=dash.no_update, exp_form=dash.no_update, exp_style=dash.no_update,
              dev_form=dash.no_update, dev_style=dash.no_update, message=dash.no_update,
              dialog=dash.no_update, reload_value=None, download=dash.no_update):
        return (target, opened_, title, label, exp_form, exp_style, dev_form, dev_style, message,
                dialog, reload_data if reload_value is None else reload_value, download)

    def opened(state, title, label, form, message="", device=False):
        """Open the dialog - on the experiment form by default, on the device form for FR-12."""
        if device:
            return shape(target=state, opened_=True, title=title, label=label, dev_form=form,
                         dev_style=shown, exp_style=hidden, dialog=message)
        return shape(target=state, opened_=True, title=title, label=label, exp_form=form,
                     exp_style=shown, dev_style=hidden, dialog=message)

    def closed(message="", delta=0):
        return shape(target=None, opened_=False, message=message, dialog="",
                     reload_value=reload_data + delta)

    def nothing():
        return shape()

    def exported(alert, download):
        """FR-21/NFR-05: the CSV row action reports in the same top-right toast as the other
        actions (the row icon has no room for an inline message) and hands the file to
        `dcc.Download`."""
        return shape(message=ui.toast(alert), download=download)

    def end_dialog(device):
        """FR-04: open the end confirmation for the experiment running on `device`.

        `device` is an iSpindel name (or id) - the card button knows it, the table row looks it
        up with `experiment_device()`. A `None` (or an experiment that was ended in the
        meantime) reads as "nothing to end", never as a database error.
        """
        values = active_experiment(device) if device else None
        if values is None:                    # already ended by someone else
            return closed(ui.toast(ui.alert("this iSpindel has no running experiment", "amber")))
        return opened({"mode": "end", "device": device},
                      "End experiment", "End experiment", experiment_form(values, disabled=True),
                      ui.alert(f"end the running experiment '{values['name']}' on this iSpindel? "
                               f"The end time is stored as now and new measurements are no "
                               f"longer assigned to it (FR-04).", "amber"))

    if triggered == "exp-cancel":
        return closed()
    if triggered == "exp-submit":
        mode = target.get("mode")
        if mode == "edit":
            alert, delta = update_experiment(target.get("id"), name, start, style, og, yeast,
                                             responsible, notes)
        elif mode == "delete":
            alert, delta = delete_experiment(target.get("id"))
        elif mode == "end":                            # FR-04: confirmed in the same dialog
            alert, delta = end_experiment(target.get("device"))
        elif mode == "device":                         # FR-12: the device settings dialog
            alert, delta = update_device(target.get("id"), dev_name, dev_active)
        else:
            alert, delta = create_experiment(name, target.get("device"), start, style, og, yeast,
                                             responsible, notes)
        if delta:                       # stored -> close, report on the page as a toast
            return closed(ui.toast(alert), delta)
        return shape(opened_=True, dialog=alert)   # keep the dialog open with the message inside
    if isinstance(triggered, dict) and triggered.get("type") == "end-btn":
        # A rebuild of the grid adds this red button with n_clicks = 0; acting on that ended
        # the experiment right after it was created (FR-04) - only a real click may end it.
        if not clicked(triggered, end_ids, end_clicks):
            return nothing()
        # FR-04 (20.10.2026): ending an experiment is **not** undone by a single click any
        # more - the red button opens the *same* dialog as "Set up experiment", read-only
        # (disabled fields show what is about to end) and with the end button in it. The
        # confirm path is `exp-submit` with `mode: end` above.
        return end_dialog(triggered.get("device"))
    if isinstance(triggered, dict) and triggered.get("type") == "setup-btn":
        # a rebuild of the grid can fire this with an empty click list - only a real click opens
        if not clicked(triggered, setup_ids, setup_clicks):
            return nothing()
        return opened({"mode": "create", "device": triggered.get("device")},
                      "Set up experiment", "Start experiment", experiment_form())
    if isinstance(triggered, dict) and triggered.get("type") == "row-btn":
        if not clicked(triggered, row_ids, row_clicks):
            return nothing()
        if triggered.get("mode") == "chart":
            # FR-17: the toggle itself is written to `chart-select` by `toggle_chart` (its own
            # output). Here the click only has to be swallowed so it does not open a dialog.
            return nothing()
        if triggered.get("mode") == "csv":
            # FR-21/FR-22: export this one experiment over the selected FR-16 time range; the
            # feedback goes to the top-right toast, the file to `dcc.Download`.
            data, alert = download_csv([triggered.get("exp")], range_key)
            return exported(alert, data)
        if triggered.get("mode") == "end":
            # FR-04 (20.10.2026): a running row carries this action **only** - it opens the same
            # confirmation popup as the red button of the device card. The device is not part of
            # the icon id (that would break the pattern match), so it is looked up here; `None`
            # (the experiment was deleted meanwhile) ends in the "nothing to end" toast.
            return end_dialog(experiment_device(triggered.get("exp")))
        # FR-06: the pencil / trash icon of a **completed** experiment's row opens the same
        # dialog, prefilled
        values = experiment_form_values(triggered.get("exp"))
        if values is None:
            return closed(ui.toast(ui.alert("that experiment no longer exists", "amber")))
        if triggered.get("mode") == "delete":
            measurements = query("SELECT count(*) AS n FROM measurement WHERE experiment_id = %s",
                                 (triggered.get("exp"),))[0]["n"]
            return opened({"mode": "delete", "id": triggered.get("exp")},
                          "Delete experiment", "Delete experiment", experiment_form(values),
                          ui.alert(f"delete '{values['name']}' and its {measurements} "
                                   f"measurements? This cannot be undone.", "red"))
        return opened({"mode": "edit", "id": triggered.get("exp")},
                      "Edit experiment", "Save changes", experiment_form(values))
    if isinstance(triggered, dict) and triggered.get("type") == "dev-btn":
        # FR-12: the settings icon of a Devices-table row. A rebuild re-renders the icons, so the
        # click is guarded with `clicked()` like every other table button.
        if not clicked(triggered, dev_ids, dev_clicks):
            return nothing()
        values = device_values(triggered.get("device"))
        if values is None:
            return closed(ui.toast(ui.alert("that iSpindel no longer exists", "amber")))
        return opened({"mode": "device", "id": triggered.get("device")},
                      "Device settings", "Save device", device_form(values), device=True)
    return nothing()


def chart_window(range_key):
    """FR-16: the selected time range as the (start, end) datetimes the chart's x axis spans.

    `None` for "entire experiment" - the axis then autoscales to the experiment's own run time.
    For a fixed range the window is taken from the **database** clock: it is the same `now()`
    that `RANGE_FILTER` compares against, so the axis can never disagree with the data about
    where the range begins (and a measurement from the newest transmission cannot fall off the
    right-hand edge).

    Why the axis is pinned at all: without it Plotly cuts the axis to the available points, so
    "last 7 days" showed only the three days an experiment had been running. The empty days in
    front of the first measurement are the answer to "how long has this been running?", so they
    have to stay visible.
    """
    interval = RANGES.get(range_key)
    if interval is None:
        return None
    row = query("SELECT now() - %(span)s::interval AS start_ts, now() AS end_ts",
                {"span": interval})[0]
    return row["start_ts"], row["end_ts"]


@app.callback(Output("chart", "figure"),
              Input("tick", "n_intervals"), Input("chart-select", "data"),
              Input("relative", "value"), Input("range", "value"), Input("viewport", "data"))
def update_chart(_, ids, axis, range_key, viewport):
    # FR-17: `ids` are the experiments toggled on in the FR-05 table (the `chart-select` store).
    # FR-14/NFR-06: on a phone the legend is dropped and the axis titles are shortened
    mobile = (viewport or {}).get("mobile", False)
    if not ids:
        return charts.fermentation_figure([], mobile=mobile)
    rows = query("""SELECT e.id, e.name, m.recorded_at,
                           m.gravity_plato::float8 AS gravity_plato,
                           m.temp_c::float8 AS temp_c
                    FROM experiment e
                    JOIN measurement m ON m.experiment_id = e.id
                    WHERE e.id = ANY(%(ids)s)
                    """ + RANGE_FILTER + """
                    ORDER BY e.id, m.recorded_at""",
                 {"ids": list(ids), "since": RANGES.get(range_key)})
    series, by_id = [], {}
    for row in rows:
        entry = by_id.get(row["id"])
        if entry is None:
            entry = {"label": row["name"], "points": []}
            by_id[row["id"]] = entry
            series.append(entry)
        entry["points"].append(row)
    # FR-16: `chart_window` pins the x axis to the whole selected range, so the time before the
    # experiment's first measurement is drawn as empty plot area instead of being cropped away
    # (the FR-18 relative axis ignores the window - it counts hours since the start).
    return charts.fermentation_figure(series, relative=(axis == "rel"), mobile=mobile,
                                      x_range=chart_window(range_key))


def download_csv(ids, range_key):
    """FR-21: CSV of the experiment(s) in `ids`; FR-22: several experiments and/or a time range.
    The structure of the file is documented in README section 1.9.

    Returns `(download, alert)`: `download` is the `dcc.send_string` payload for `dcc.Download`
    (or `dash.no_update` when there is nothing to export), `alert` is the message for the user.
    It is **no** callback of its own any more - it is called by `experiment_action`, because the
    FR-21 export action now sits on the FR-05 table rows (it used to be a button in the chart
    card). Keeping it a plain function also lets the test scripts call it directly.
    """
    if not ids:
        return dash.no_update, ui.alert(
            "pick at least one experiment, then export it again (FR-21)", "amber")
    rows = query("""SELECT e.name AS experiment, d.mqtt_name AS ispindel,
                           to_char(m.recorded_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') || 'Z'
                               AS timestamp_utc,
                           to_char(m.recorded_at AT TIME ZONE %(tz)s, 'YYYY-MM-DD HH24:MI:SS')
                               AS timestamp_local,
                           m.tilt_deg::float8 AS tilt_deg,
                           m.temp_c::float8 AS temperature_c,
                           m.gravity_plato::float8 AS gravity_plato,
                           m.battery_v::float8 AS battery_v,
                           m.interval_s, m.rssi_dbm
                    FROM measurement m
                    JOIN experiment e ON e.id = m.experiment_id
                    JOIN device d ON d.id = m.device_id
                    WHERE m.experiment_id = ANY(%(ids)s)
                    """ + RANGE_FILTER + """
                    ORDER BY e.name, m.recorded_at""",
                 {"tz": str(LOCAL), "ids": list(ids), "since": RANGES.get(range_key)})
    if not rows:
        return dash.no_update, ui.alert("no measurements in the selected range", "amber")
    filename = f"{rows[0]['experiment']}.csv" if len(ids) == 1 else "experiments.csv"
    return (dcc.send_string(rows_to_csv(rows), filename),
            ui.alert(f"exported {len(rows)} measurements ({RANGE_TEXT.get(range_key)}), "
                     f"file: {filename}", "green"))


if __name__ == "__main__":
    # Development server. `debug=True` turns on Dash's hot reload (the browser refreshes by
    # itself when a file changes) and the Werkzeug reloader (the process restarts), so you
    # never have to stop and start it by hand. `use_debugger=False` keeps the interactive
    # Werkzeug console switched off: the dashboard binds to 0.0.0.0, and that console allows
    # arbitrary code execution from the browser. gunicorn on the Pi never runs this block.
    app.run(host=DASH["host"], port=DASH["port"], debug=True, use_debugger=False)
