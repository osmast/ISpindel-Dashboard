"""iSpindel fermentation dashboard (Plotly Dash).

Run:  python main.py                              ->  http://localhost:8080
      gunicorn main:server -b 0.0.0.0:8080
"""
import os
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import dash
import dash_mantine_components as dmc
import psycopg
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify
from flask import request

from components import charts, ui
from services.db import CFG, LOCAL, execute, local, query, rows_to_csv

DASH = CFG["dashboard"]
REFRESH = DASH["refresh_ms"]
LIVE = DASH["live_ms"]
BATTERY_WARN = DASH["battery_warn_v"]
BATTERY_FULL = DASH["battery_full_v"]
BATTERY_EMPTY = DASH["battery_empty_v"]
# FR-20: target FG = og * (1 - attenuation/100), plus the target temperature window per beer style.
EXPECTED_ATTENUATION = DASH["expected_attenuation"]
TARGET_TEMP_C = DASH["target_temp_c"]

CHART_DAYS = DASH["device_chart_days"]

# FR-16/FR-22: the selectable time ranges (SQL interval, None = whole experiment).
RANGES = {"all": None, "7d": "7 days", "24h": "24 hours"}
RANGE_TEXT = {"all": "entire experiment", "7d": "last 7 days", "24h": "last 24 h"}
RANGE_FILTER = "AND (%(since)s::interval IS NULL OR m.recorded_at >= now() - %(since)s::interval)"

DEV_REPEAT = 1   # only > 1 for layout tests; FR-15 wants one card per real device

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}   # read-only charts, no modebar


def experiment_form(values=None, disabled=False):
    """The fields of the experiment dialog, filled from `values` (None = empty).

    One dialog serves create, edit (FR-06), delete and the end confirmation (FR-04, prefilled
    and disabled). The inputs always stay in the DOM - `experiment_action` reads them as State.
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
    """The fields of the device dialog (FR-12): read-only MQTT name, display name, "in use" flag."""
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



# Dash links every .css/.js under assets/ automatically. `assets_ignore` matches file names
# (skip the Tailwind source input.pcss); `assets_path_ignore` matches path levels (skip
# node_modules, the npm install that builds the CSS - it is full of package stylesheets).
app = dash.Dash(__name__, title="iSpindel Monitor", assets_ignore=r"\.pcss$",
                assets_path_ignore=[r"node_modules"])
server = app.server                                   # gunicorn entry point


def layout():
    return ui.page([
        # FR-01/FR-04: notices (experiment started / ended) are transient toasts. The
        # container is fixed to the top-right corner of the viewport (`top-0 right-0`) and
        # ignores pointer events, so it can never block the page behind it. The child
        # carries the fade-away animation (assets/input.pcss) - no JavaScript needed.
        html.Div(id="msg", className="pointer-events-none fixed right-0 top-0 z-50 flex "
                                     "w-full max-w-sm flex-col gap-2 p-4"),

        # FR-15: during the fermentation phase the participants run their own brokers - this small
        # button opens the dialog that adds them (and shows which of them really deliver).
        html.Div(className="flex items-center justify-end", children=[
            ui.button("broker-open", "MQTT brokers", tone="light", compact=True),
        ]),

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
                dcc.Graph(id="chart", config=GRAPH_CONFIG),
                # FR-16/FR-18: the time axis and the time range sit under the figure (NFR-06).
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


        # FR-01 - FR-04: the experiment dialog. It sits outside the device grid, which is rebuilt
        # on every refresh; `exp-target` holds the device whose dialog is open (None = closed).
        dcc.Store(id="exp-target", data=None),
        dmc.Modal(
            id="exp-modal", title="Set up experiment", opened=False, centered=True, size="lg",
            # Closed through the buttons only - a self-closing modal leaves Dash's `opened` at True.
            withCloseButton=False, closeOnClickOutside=False, closeOnEscape=False,
            children=[
                html.Div(id="modal-msg", className="mb-3"),
                # rebuilt with the values of an existing experiment for FR-06 edit / delete
                html.Div(id="exp-form", children=experiment_form()),
                # FR-12: the device fields, hidden until the Devices table opens the dialog
                html.Div(id="dev-form", style={"display": "none"}, children=device_form()),
                html.Div(className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end",
                         children=[
                    ui.button("exp-cancel", "Cancel", tone="light", extra="w-full sm:w-auto"),
                    ui.button("exp-submit", "Start experiment", extra="w-full sm:w-auto"),
                ]),
            ]),

        # FR-15: the broker dialog. Same shape as the experiment dialog - the static shell holds
        # the list and the form, the callback only opens it and writes through it.
        dcc.Store(id="broker-target", data=None),
        dcc.Store(id="broker-reload", data=0),
        dmc.Modal(
            id="broker-modal", title="MQTT brokers", opened=False, centered=True, size="lg",
            # closed through its buttons only - a self-closing modal leaves Dash's `opened` True
            withCloseButton=False, closeOnClickOutside=False, closeOnEscape=False,
            children=[
                html.Div(id="broker-msg", className="mb-3"),
                html.Div(id="broker-list", className="mb-3"),
                html.Div(id="broker-form", style={"display": "none"}),
                html.Div(className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end",
                         children=[
                    ui.button("broker-cancel", "Close", tone="light",
                              extra="w-full sm:w-auto"),
                    ui.button("broker-add", "Add broker", tone="grey",
                              extra="w-full sm:w-auto"),
                    ui.button("broker-submit", "Save broker", extra="w-full sm:w-auto"),
                ]),
            ]),

        dcc.Interval(id="tick", interval=REFRESH),
        dcc.Interval(id="tick1s", interval=LIVE),
        # device id -> {"last", "due"} epochs, written by update_device_times, rendered as
        # "last: 12 s ago · upcoming: in 12 s" by the clientside callback below (the id and not
        # the name: FR-15 - two brokers may carry an iSpindel with the same name)
        dcc.Store(id="device_times", data={}),
        # {"mobile": bool}, written by the viewport callback, used to drop the legend (NFR-06)
        dcc.Store(id="viewport", data={}),
        # which accordion cards are open - written by assets/card_state.js, read back on rebuild
        dcc.Store(id="open_cards", data={}),
        # FR-17: the experiment ids overlaid in the comparison chart (written by toggle_chart)
        dcc.Store(id="chart-select", data=[]),
        dcc.Store(id="reload", data=0),
    ])


# xxl at 96em (1536px) matches the container cap: two comfortable card columns on a laptop,
# three only on a very wide screen. `fontFamily` has to be set here - Mantine injects its own
# unlayered font-family rule that beats Tailwind's, so the CSS `--font-sans` alone is not enough.
THEME = {"fontFamily": charts.FONT_FAMILY,
         "fontFamilyMonospace": charts.FONT_FAMILY,
         "headings": {"fontFamily": charts.FONT_FAMILY},
         "breakpoints": {"xs": "36em", "sm": "48em", "md": "62em",
                         "lg": "75em", "xl": "88em", "xxl": "96em"}}

# dmc supplies the responsive grid; MantineProvider sets up its theme (CSS variables).
app.layout = dmc.MantineProvider(layout(), theme=THEME)

# The times line of every card ticks in the browser - one JS function for every card, no round trip.
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
        // FR-13: the time of the last measurement, "20.10. 14:35:12", from the browser clock.
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

# Plotly figures cannot react to CSS media queries, so the server needs the breakpoint:
# `{"mobile": true}` while the window is narrower than Tailwind's `md` (768 px, NFR-06).
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

# The empty state has to name the broker address an iSpindel publishes to. The server cannot read
# its own LAN address inside a container (`socket.gethostbyname`, the UDP egress trick and
# `hostname -I` all return the private bridge address, e.g. 172.x). What it can do:
#   * the browser reached the dashboard through the machine's LAN address (NFR-02) and sent it in
#     the HTTP `Host` header - a callback runs inside the request, so `request` is available;
#   * a run without containers can read the machine's own LAN address.
# Neither helps when the dashboard is opened on the machine itself via `localhost`: that address is
# useless to an iSpindel, so the hint then says so instead of printing it (see `mqtt_hint`).
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def client_host():
    """The host the browser used for this request (the HTTP `Host` header), without the dashboard
    port. Empty outside a request context (e.g. a test script)."""
    try:
        return urlsplit("//" + request.host).hostname or ""    # handles `host:port` and `[v6]:port`
    except RuntimeError:
        return ""


def own_lan_address():
    """This machine's own non-loopback IPv4 - the LAN address an iSpindel can publish to. Only a
    run without containers knows it: inside one it is the private bridge address, not usable."""
    if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
        return ""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))    # only picks the default route - nothing is sent
        return sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        sock.close()


def broker_host():
    """The address an iSpindel should point at: the one the browser used, unless that is a loopback
    address (`localhost` says nothing about the network the iSpindel floats in). Without containers
    the machine's own LAN address is the fallback; otherwise the hint explains the situation."""
    host = client_host()
    if host and host.lower() not in LOOPBACK_HOSTS:
        return host
    return own_lan_address()


# ---- callbacks ------------------------------------------------------------

@app.callback(Output("devices", "children"), Output("devices-table", "children"),
              Output("exp-running", "children"), Output("exp-completed", "children"),
              Output("exp-tab-running", "children"), Output("exp-tab-completed", "children"),
              Output("exp-tab-devices", "children"),
              Input("tick", "n_intervals"), Input("reload", "data"),
              Input("viewport", "data"), Input("chart-select", "data"),
              State("open_cards", "data"))
def update_dashboard(_, __, viewport, selected, open_cards):
    """The device cards, the three experiment-panel views (FR-05 running / completed + FR-12)
    and the tab labels with their counts. `chart-select` is an Input too, so toggling an
    experiment in the chart (FR-17) re-renders the table and the row icon turns blue at once."""
    rows = experiment_rows()
    running = [r for r in rows if r["is_active"]]
    completed = [r for r in rows if not r["is_active"]]
    devices = device_rows()
    host = broker_host()
    return (ispindel_overview(open_cards or {}, (viewport or {}).get("mobile", False), host),
            device_table(devices, host),
            experiment_table(running, selected, empty="no experiment is running"),
            experiment_table(completed, selected, empty="no experiment has been completed yet"),
            f"Running ({len(running)})", f"Completed ({len(completed)})",
            f"Devices ({len(devices)})")


@app.callback(Output("device_times", "data"), Input("tick1s", "n_intervals"))
def update_device_times(_):
    """Last measurement and next transmission per device, as absolute epochs - a tiny query that
    can run every `dashboard.live_ms`. The browser turns them into relative text. Keyed by the
    device id (FR-15: the iSpindel name is not unique across brokers)."""
    times = {}
    for row in query("SELECT device_id, recorded_at, interval_s FROM v_device_latest"):
        last, interval = row["recorded_at"], row["interval_s"]
        if last is None:
            times[row["device_id"]] = {"last": None, "due": None}
            continue
        times[row["device_id"]] = {
            "last": last.timestamp(),
            "due": (last + timedelta(seconds=interval)).timestamp() if interval else None,
        }
    return times


def mqtt_hint(host=""):
    """Shown while no iSpindel has reported yet (FR-13 overview / FR-12 device table): instead of
    only "no iSpindel has reported yet" it says where to point one. Port and topic prefix come from
    config.yml (NFR-08); `host` is the LAN address an iSpindel can publish to (`broker_host`). When
    that address is unknown (a container opened via `localhost`) the block does not print a useless
    `localhost` but says which address is meant."""
    port = CFG["mqtt"]["port"]
    prefix = CFG["mqtt"]["topic_prefix"]
    rows = [
        html.Li([html.Span("Server: ", className="text-slate-500"),
                 html.Span(host or "the LAN address of this machine")]),
        html.Li([html.Span("Port: ", className="text-slate-500"), html.Span(str(port))]),
        html.Li([html.Span("Topic: ", className="text-slate-500"),
                 html.Span(f"{prefix}/<name>/<field> (prefix {prefix})")]),
    ]
    note = [] if host else [
        html.P('An iSpindel cannot reach "localhost" - open this dashboard via the machine\'s LAN '
               "address instead and it will appear here.",
               className="mt-2 text-xs text-slate-400"),
    ]
    return html.Div(
        className="rounded-lg corner-squircle border border-dashed border-slate-300 bg-slate-50 "
                  "p-4 text-sm text-slate-600",
        children=[
            html.P("No iSpindel has reported yet.", className="font-medium text-slate-700"),
            html.P("Point an iSpindel at this monitor - its MQTT configuration:",
                   className="mt-1 text-slate-500"),
            html.Ul(className="mt-2 grid gap-1", children=rows),
            *note,
        ])


def ispindel_overview(open_cards=None, mobile=False, host=""):
    """One batch card per iSpindel. `open_cards` keeps the open state across a rebuild;
    `mobile` comes from the `viewport` store (NFR-06); `host` fills the empty-state hint."""
    open_cards = open_cards or {}
    rows = query("""SELECT l.device_id, l.mqtt_name, l.recorded_at, l.tilt_deg, l.temp_c,
                           l.gravity_plato, l.battery_v, l.interval_s, l.rssi_dbm, l.broker_label
                    FROM v_device_latest l JOIN device d ON d.id = l.device_id
                    WHERE d.is_active
                    ORDER BY l.broker_label NULLS FIRST, l.mqtt_name""")
    if not rows:
        return mqtt_hint(host)
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
    # FR-04/FR-13/FR-20: the experiment running on each iSpindel (name, style, OG). The
    # exclusion constraint guarantees at most one per device, so a plain dict is enough.
    active = {r["device_id"]: r
              for r in query("""SELECT device_id, name, beer_style, og_plato::float8 AS og_plato
                                FROM experiment WHERE ended_at IS NULL""")}
    if DEV_REPEAT > 1:                       # development only, see DEV_REPEAT
        rows = rows[:1] * DEV_REPEAT
    # `slot` only exists so the repeated cards get unique ids
    cards = [device_card(row, by_device.get(row["device_id"], []), slot,
                         open_cards.get(f"{row['device_id']}#{slot}", False),
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
    """A `dcc.Graph` that fills a wrapper div sized by a Tailwind height class."""
    return html.Div(className=className, children=[
        dcc.Graph(figure=figure, style={"height": "100%"}, config=GRAPH_CONFIG)
    ])


def header_stat(value, className, title=""):
    """One value in the card header, e.g. `27.1 °P`. `className` carries the text colour."""
    return html.Div(value, title=title or None,
                    className="text-right text-lg font-semibold tabular-nums " + className)


def status_dot(warn):
    """FR-19: green while the iSpindel is healthy, red for a stale device or low battery.
    The reason is text and lives in the expanded card (`card_warnings`)."""
    return html.Span(
        className=("inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-red-500" if warn else
                   "inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500"),
        title="warning - expand this card for the reason" if warn
              else "healthy: current data, battery above the warning threshold",
    )


def card_warnings(stale, age, interval_s, volts, low):
    """FR-19: the explanations of the red status dot, one line per condition (expanded card)."""
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
    """Li-Ion cell voltage -> charge in percent, clamped to 0..100 (FR-13). Limits are settings."""
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
    """Apparent attenuation in % - `(OG - FG) / OG`, both in °P, clamped at 0 (FR-20)."""
    if not og_plato or fg_plato is None:
        return None
    return max(0.0, (og_plato - fg_plato) / og_plato * 100)


def abv_percent(og_plato, fg_plato):
    """Estimated ABV in %: the `(OG - FG) * 131.25` rule of thumb on SG (FR-20)."""
    if og_plato is None or fg_plato is None:
        return None
    return max(0.0, (sg_from_plato(og_plato) - sg_from_plato(fg_plato)) * 131.25)


def target_fg(og_plato):
    """The expected final gravity: the configured apparent attenuation applied to the OG (FR-20)."""
    return None if og_plato is None else og_plato * (1 - EXPECTED_ATTENUATION / 100)


def target_temp_range(style):
    """The target temperature window for a beer style: first matching keyword, else `default`."""
    if style:
        for keyword, span in TARGET_TEMP_C.items():
            if keyword != "default" and keyword in style.lower():
                return span
    return TARGET_TEMP_C.get("default")


def temp_hint(temp, span):
    """`(text, state)` for the deviation from a target temperature window, else `None`.
    `state` is `"high"`, `"low"` or `"in"`; the caller turns it into a literal Tailwind class."""
    if temp is None or not span:
        return None
    low, high = span
    if temp > high:
        return f"\u25b2 {temp - high:.1f} °C High", "high"
    if temp < low:
        return f"\u25bc {low - temp:.1f} °C Low", "low"
    return "\u2713 in range", "in"


def gravity_rate(points, hours=24):
    """Gravity change per 24 h in °P, scaled by the real time between the two points (FR-20).
    `None` while the history is shorter than the window."""
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
    """FR-13/FR-19: the header pill carrying the single health dot (no text - the reason is in
    the expanded card). Not `ui.badge()` on purpose: `fr19_test.py` asserts a card has none."""
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
    """One iSpindel as a collapsible batch card (FR-13, FR-20). Collapsed: batch name, status
    chip, current gravity / temperature / battery. Opened: the three data zones, the device's own
    fermentation chart and the experiment controls. `batch` is the running experiment or None;
    `points` is the measurement history; `mobile` comes from the `viewport` store (NFR-06)."""
    age = None if latest["recorded_at"] is None else \
        (datetime.now(timezone.utc) - latest["recorded_at"]).total_seconds()
    # FR-19: silent for more than three intervals, or never reported at all
    stale = age is None or (bool(latest["interval_s"]) and age > 3 * latest["interval_s"])
    volts = latest["battery_v"]
    low = volts is not None and volts < BATTERY_WARN                                  # FR-19
    # FR-19: the two conditions as text for the expanded card
    warnings = card_warnings(stale, age, latest["interval_s"], volts, low)
    warnings_html = html.Div(
        className="mb-2 flex flex-col gap-1",
        children=[html.Div(line, className="text-xs font-medium text-red-600")
                  for line in warnings],
    ) if warnings else None
    pct = battery_percent(volts, BATTERY_EMPTY, BATTERY_FULL)
    # the footer times line counts from these two epochs (FR-13/FR-14)
    last_epoch = None if latest["recorded_at"] is None else latest["recorded_at"].timestamp()
    due = None if (last_epoch is None or not latest["interval_s"]) else \
        last_epoch + latest["interval_s"]
    name = latest["mqtt_name"]
    # FR-15: the identity in the DOM is the device id, not the name - two participants may use the
    # same iSpindel name on their own brokers, and the buttons have to resolve the right device.
    device_id = latest["device_id"]
    broker = latest.get("broker_label")   # None = the broker of config.yml, nothing to show
    # FR-04/FR-13: a running card wears the experiment name, the iSpindel name moves to the footer
    running = bool(batch)
    heading = batch["name"] if running else name
    style = (batch["beer_style"] or None) if running else None
    series = [{"label": name, "points": points}] if points else []
    # FR-20: the zone values; every helper returns None for a missing input (rendered as "-")
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
        # `id` gives React a stable key so a remount keeps `open` (restored from `open_cards`)
        id={"type": "card", "device": device_id, "slot": slot},
        open=is_open,
        **{"data-card": f"{device_id}#{slot}"},
        # `group` is needed by the `group-open:` variants inside; a running experiment gets the
        # thicker outline plus a ring (FR-04).
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
                            # FR-04: the experiment name while one runs (tooltip keeps the device)
                            html.H3(heading, title=f"iSpindel {name}" if running else None,
                                    className="min-w-0 truncate text-base font-semibold "
                                              "text-slate-800"),
                            # FR-13/FR-19: the batch state and the health dot in one pill
                            status_chip(running, bool(warnings)),
                        ]),
                    ]),
                    html.Div(className="flex shrink-0 items-center gap-3 sm:gap-4", children=[
                        # gravity/temperature hide once open (the zones show them then)
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
                # FR-19: why the dot next to the device name is red
                warnings_html,
                # FR-13/FR-20: the three data zones; a missing value renders as "-" (NFR-06)
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
                        html.Div(f"Target FG: ~{value_text(fg_target, ' °P' )}" if value_text else None,
                                 className="mt-1 text-xs text-slate-500"),
                        html.Div(className="text-xs text-slate-500", children=[
                            "Rate: ",
                            # falling gravity = running (green), rising = wrong (red), none if unknown
                            html.Span(value_text(rate, " °P/24h"), className=(
                                "font-medium text-emerald-600"
                                if rate is not None and rate < 0 else
                                "font-medium text-red-600" if rate is not None else "")),
                        ]),
                    ), span={"base": 12, "sm": 4}),
                    # TEMPERATURE: reading, target window of the style, deviation
                    dmc.GridCol(ui.zone(
                        "Temperature",
                        html.Div(className="flex items-baseline gap-1.5", children=[
                            html.Span(ui.num(temp, 1),
                                      className="text-2xl font-semibold tabular-nums "
                                                "text-purple-700"),
                            html.Span("°C", className="text-sm text-slate-500"),
                        ]),
                        html.Div(f"Target: {target_span[0]:.1f}\u2013{target_span[1]:.1f} °C"
                                 if target_span else None,
                                 className="mt-1 text-xs text-slate-500"),
                        html.Div(hint[0], className=(
                            "text-xs font-medium text-amber-600"
                            if hint and hint[1] == "high" else
                            "text-xs font-medium text-sky-700" if hint and hint[1] == "low" else
                            "text-xs font-medium text-emerald-600")) if hint else None,
                    ), span={"base": 12, "sm": 4}),
                    # ATTENUATION & ABV (FR-20)
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
                # FR-01 - FR-04: the experiment controls (end / set up) of this iSpindel
                html.Div(className="mt-3 flex flex-wrap items-center justify-between gap-2",
                         children=[
                    # FR-04/FR-15: the footer names the device (the header names the batch)
                    html.Div(className="flex items-center gap-2 text-xs", children=[
                        html.Span("iSpindel:", className="text-slate-400"),
                        html.Span(name, className="font-medium text-slate-700"),
                    ]) if running else
                    html.Span("no experiment yet", className="text-xs text-slate-400"),
                    # the id keys must match the callback pattern exactly, or the click does nothing
                    ui.button({"type": "end-btn", "device": device_id, "slot": slot},
                              "End experiment", tone="danger", compact=True) if running else
                    ui.button({"type": "setup-btn", "device": device_id, "slot": slot},
                              "Set up experiment", tone="grey", compact=True),
                ]),
                html.Div(className="mt-2 flex flex-wrap items-center justify-between "
                                   "gap-x-3 gap-y-1 text-xs text-slate-400", children=[
                    html.Span(f"tilt {ui.num(latest['tilt_deg'], 1)}° · "
                              f"RSSI {ui.num(latest['rssi_dbm'], 0)} dBm · "
                              f"interval {ui.num(latest['interval_s'], 0)} s"
                              # FR-15: which broker this iSpindel publishes to (empty for our own)
                              + (f" · {broker}" if broker else "")),
                    # FR-13/FR-14: time of the last measurement, its age, the next transmission
                    html.Span(id={"type": "times", "device": device_id, "slot": slot},
                              className="tabular-nums",
                              title="time of the last measurement, its age and the next "
                                    "transmission (FR-13 / FR-14, local time)",
                              children=times_text(last_epoch, due)),
                ]),
            ]),
        ],
    )


# FR-05: the columns of the experiment overview (FR-01 optional fields included).
TABLE_HEADERS = ["Name", "iSpindel", "Start Timestamp", "Status", "Measurements",
                 "Beer style", "OG °P", "Yeast", "Responsible", "End Timestamp", "Actions"]


def row_actions(exp_id, running=False, selected=False):
    """The action icons of one experiment row. Both states: `chart` (FR-17, blue while shown) and
    `csv` (FR-21); a running row adds `end` (FR-04), a completed one `delete` (FR-06); `edit`
    (FR-06) is on both. The ids are pattern ids that must match the callback exactly."""
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
    """One FR-05 table for the rows it is given (running or completed). `selected` holds the
    experiment ids shown in the comparison chart, so their chart icon is filled (FR-17)."""
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


# FR-12: the device master data. A new iSpindel appears automatically (created by the ingest).
DEVICE_HEADERS = ["Name (MQTT topic)", "Broker", "Display name", "Status", "First seen",
                  "Last measurement", "Interval", "Measurements", "Actions"]


def device_actions(device_id):
    """The one action of a device row (FR-12): open the settings dialog."""
    return dmc.Tooltip(
        label="device settings", position="top", withArrow=True, openDelay=300,
        children=dmc.ActionIcon(
            DashIconify(icon="tabler:settings", width=15),
            id={"type": "dev-btn", "device": device_id},
            variant="subtle", color="gray", size="sm", radius="md",
            **{"aria-label": "device settings"}))


def device_rows():
    """One row per device: the master data plus what its latest measurement reported.

    FR-15: the broker of every device is part of the row - the iSpindel name alone does not
    identify a device any more once several brokers are in play.
    """
    return query("""SELECT d.id, d.mqtt_name, d.display_name, d.is_active, d.first_seen_at,
                           l.recorded_at AS last_seen, l.interval_s, l.broker_label,
                           (SELECT count(*) FROM measurement m
                            WHERE m.device_id = d.id) AS measurements
                    FROM device d
                    LEFT JOIN v_device_latest l ON l.device_id = d.id
                    ORDER BY l.broker_label NULLS FIRST, d.mqtt_name""")


def device_table(rows, host=""):
    """The FR-12 device overview: every iSpindel the system knows, with its settings action.
    The empty state is the same "where to point an iSpindel" hint as the FR-13 overview."""
    body = [[html.Span(r["mqtt_name"]),
             r["broker_label"] or "config.yml",          # FR-15: NULL = the broker of config.yml
             r["display_name"] or "-",
             ui.badge("in use", "green") if r["is_active"] else ui.badge("ignored", "slate"),
             f"{local(r['first_seen_at']):%d. %b %y %H:%M}",
             f"{local(r['last_seen']):%d. %b %y %H:%M}" if r["last_seen"] else "-",
             f"{r['interval_s']} s" if r["interval_s"] else "-",
             str(r["measurements"]),
             device_actions(r["id"])] for r in rows]
    return ui.table(DEVICE_HEADERS, body, empty=mqtt_hint(host))


def device_values(device_id):
    """The dialog's values for one device, or None when the row is gone (FR-12)."""
    rows = query("SELECT mqtt_name, display_name, is_active FROM device WHERE id = %s", (device_id,))
    if not rows:
        return None
    row = rows[0]
    return {"mqtt_name": row["mqtt_name"], "display_name": row["display_name"],
            "active": row["is_active"]}


def update_device(device_id, display_name, active):
    """FR-12: save the device settings (display name + "in use" flag). Returns (alert, delta).
    The MQTT name is not editable - it is the identity the device publishes with."""
    values = device_values(device_id)
    if values is None:
        return ui.alert("that iSpindel no longer exists", "amber"), 0
    name = (display_name or "").strip() or None
    execute("UPDATE device SET display_name = %s, is_active = %s WHERE id = %s",
            (name, bool(active), device_id))
    state = "in use" if active else "ignored"
    return ui.alert(f"iSpindel '{values['mqtt_name']}' saved - {state} (FR-12)", "green"), 1


# FR-15: the brokers of the other iSpindels in use. The **own** broker is not stored anywhere -
# it stays in config.yml (NFR-08) - so the dialog renders it as the first, read-only row.
BROKER_HEADERS = ["Broker", "Address", "Topic prefix", "iSpindels", "State", "Actions"]


def broker_rows():
    """Every broker the ingest listens on (FR-15): config.yml first, then the added ones."""
    own = {"id": None, "label": "own broker (config.yml)", "is_config": True, "is_enabled": True,
           "host": CFG["mqtt"]["host"], "port": CFG["mqtt"]["port"],
           "topic_prefix": CFG["mqtt"]["topic_prefix"], "last_connected_at": None,
           "last_message_at": None, "last_error": None,
           "devices": query("SELECT count(*) AS n FROM device WHERE broker_id IS NULL")[0]["n"]}
    rows = query("""SELECT b.id, b.label, b.host, b.port, b.topic_prefix, b.is_enabled,
                           b.last_connected_at, b.last_message_at, b.last_error,
                           (SELECT count(*) FROM device d WHERE d.broker_id = b.id) AS devices
                    FROM mqtt_broker b ORDER BY b.label""")
    for row in rows:
        row["is_config"] = False
    return [own] + rows


def broker_state(row):
    """The state chip of one broker row: paused > error > delivering > silent (FR-15).

    The values come from the ingest, which writes connection state and traffic back into
    `mqtt_broker` - so the dialog shows whether the other participant's broker really delivers.
    """
    if not row["is_enabled"]:
        return ui.badge("paused", "slate")
    if row["last_error"]:
        return ui.badge(row["last_error"][:38], "red")
    last = row.get("last_message_at")
    if last is None:
        return ui.badge("no message yet", "amber")
    age = (datetime.now(timezone.utc) - last).total_seconds()
    if age < 300:
        return ui.badge(f"delivering ({age:.0f} s ago)", "green")
    return ui.badge(f"silent since {local(last):%d.%m. %H:%M}", "amber")


def broker_actions(row):
    """pause/resume, edit and delete of one broker row - the own broker has no row to change."""
    if row["is_config"]:
        return html.Span("config.yml", className="text-xs text-slate-400")

    def icon(kind, icon_name, label, colour):
        return dmc.Tooltip(
            label=label, position="top", withArrow=True, openDelay=300,
            children=dmc.ActionIcon(
                DashIconify(icon=icon_name, width=15),
                id={"type": "broker-btn", "broker": row["id"], "mode": kind},
                variant="subtle", color=colour, size="sm", radius="md",
                **{"aria-label": f"{label} broker"}))

    return html.Div(className="flex items-center gap-1", children=[
        icon("toggle", "tabler:player-pause" if row["is_enabled"] else "tabler:player-play",
             "pause" if row["is_enabled"] else "resume", "gray"),
        icon("edit", "tabler:pencil", "edit", "gray"),
        icon("delete", "tabler:trash", "delete", "red"),
    ])


def broker_table(rows):
    """The FR-15 list inside the dialog: one row per broker with its live state."""
    body = [[html.Span(r["label"]), f"{r['host']}:{r['port']}", r["topic_prefix"],
             str(r["devices"]), broker_state(r), broker_actions(r)] for r in rows]
    return ui.table(BROKER_HEADERS, body, empty="no broker configured")


def broker_form(values=None):
    """The fields of the broker dialog (FR-15): where the other iSpindels publish."""
    v = values or {}
    return html.Div(className="grid gap-4 md:grid-cols-2", children=[
        ui.field("Label (unique, shown in the dashboard)",
                 dcc.Input(id="broker-label", type="text", value=v.get("label"),
                           placeholder="Mueller Pi",
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("Host (name or IP address)",
                 dcc.Input(id="broker-host", type="text", value=v.get("host"),
                           placeholder="160.85.142.77",
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("Port",
                 dcc.Input(id="broker-port", type="number", value=v.get("port") or 1883,
                           placeholder="1883",
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("Topic prefix",
                 dcc.Input(id="broker-prefix", type="text",
                           value=v.get("topic_prefix") or "ispindel", placeholder="ispindel",
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("User (empty = anonymous)",
                 dcc.Input(id="broker-user", type="text", value=v.get("username"),
                           placeholder="ispindel",
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("Password",
                 dcc.Input(id="broker-password", type="password", value=v.get("password"),
                           className="w-full rounded-lg corner-squircle border border-slate-300 "
                                     "px-3 py-2")),
        ui.field("State - a paused broker records nothing",
                 dcc.Checklist(id="broker-enabled",
                               options=[{"label": " listen on this broker", "value": "on"}],
                               value=["on"] if v.get("is_enabled", True) else [],
                               className="flex flex-wrap gap-3 text-sm",
                               labelClassName="flex min-h-11 cursor-pointer items-center")),
    ])


def broker_values(broker_id):
    """The dialog's values of one broker, or None when the row is gone (FR-15)."""
    rows = query("""SELECT label, host, port, topic_prefix, username, password, is_enabled
                    FROM mqtt_broker WHERE id = %s""", (broker_id,))
    return rows[0] if rows else None


def save_broker(broker_id, label, host, port, prefix, username, password, enabled):
    """Insert (broker_id None) or update one broker. Returns (alert, reload_delta) - FR-15."""
    label, host = (label or "").strip(), (host or "").strip()
    if not label or not host:
        return ui.alert("a broker needs a label and a host (FR-15)", "amber"), 0
    try:
        port = int(port or 1883)
    except (TypeError, ValueError):
        return ui.alert("the port must be a number like 1883", "amber"), 0
    values = {"label": label, "host": host, "port": port,
              "topic_prefix": (prefix or "").strip() or "ispindel",
              "username": (username or "").strip() or None,
              "password": (password or "").strip() or None,
              "enabled": bool(enabled)}
    refresh = CFG["ingest"]["broker_refresh_seconds"]
    try:
        if broker_id is None:
            execute("""INSERT INTO mqtt_broker (label, host, port, topic_prefix, username,
                                                password, is_enabled)
                       VALUES (%(label)s, %(host)s, %(port)s, %(topic_prefix)s, %(username)s,
                               %(password)s, %(enabled)s)""", values)
            return ui.alert(f"broker '{label}' added - the ingest connects within {refresh} s "
                            f"(FR-15)", "green"), 1
        values["id"] = broker_id
        execute("""UPDATE mqtt_broker SET label = %(label)s, host = %(host)s, port = %(port)s,
                          topic_prefix = %(topic_prefix)s, username = %(username)s,
                          password = %(password)s, is_enabled = %(enabled)s,
                          last_error = NULL          -- the old failure does not belong to this
                      WHERE id = %(id)s""", values)
        return ui.alert(f"broker '{label}' saved - the ingest reconnects within {refresh} s "
                        f"(FR-15)", "green"), 1
    except psycopg.errors.UniqueViolation:
        return ui.alert(f"a broker named '{label}' exists already (FR-15)", "amber"), 0
    except psycopg.Error as exc:
        return ui.alert(f"database error: {exc}", "red"), 0


def delete_broker(broker_id):
    """Delete a broker together with everything it delivered. Returns (alert, reload_delta).

    `measurement` and `experiment` reference `device` without a cascade, so the rows of that
    broker's iSpindels go first - measurements, then experiments, then the devices (FR-15).
    """
    rows = query("""SELECT b.label,
                           (SELECT count(*) FROM device d WHERE d.broker_id = b.id) AS devices,
                           (SELECT count(*) FROM measurement m JOIN device d ON d.id = m.device_id
                             WHERE d.broker_id = b.id) AS measurements
                    FROM mqtt_broker b WHERE b.id = %s""", (broker_id,))
    if not rows:
        return ui.alert("that broker no longer exists", "amber"), 0
    row = rows[0]
    execute("""DELETE FROM measurement WHERE device_id IN
                 (SELECT id FROM device WHERE broker_id = %s)""", (broker_id,))
    execute("""DELETE FROM experiment WHERE device_id IN
                 (SELECT id FROM device WHERE broker_id = %s)""", (broker_id,))
    execute("DELETE FROM device WHERE broker_id = %s", (broker_id,))
    execute("DELETE FROM mqtt_broker WHERE id = %s", (broker_id,))
    return ui.alert(f"broker '{row['label']}' deleted, with its {row['devices']} iSpindels and "
                    f"{row['measurements']} measurements", "green"), 1


def toggle_broker(broker_id):
    """Pause / resume one broker (FR-15): the ingest stops or starts listening within one pass."""
    rows = query("SELECT label, is_enabled FROM mqtt_broker WHERE id = %s", (broker_id,))
    if not rows:
        return ui.alert("that broker no longer exists", "amber"), 0
    enabled = not rows[0]["is_enabled"]
    execute("UPDATE mqtt_broker SET is_enabled = %s, last_error = NULL WHERE id = %s",
            (enabled, broker_id))
    return ui.alert(f"broker '{rows[0]['label']}' "
                    f"{'resumed' if enabled else 'paused'} (FR-15)", "green"), 1







@app.callback(Output("chart-select", "data"),
              Input({"type": "row-btn", "exp": ALL, "mode": ALL}, "n_clicks"),
              State({"type": "row-btn", "exp": ALL, "mode": ALL}, "id"),
              State("chart-select", "data"),
              prevent_initial_call=True)
def toggle_chart(clicks, ids, selected):
    """FR-17: the `chart` row action adds / removes the experiment from the comparison chart."""
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
    """Normalise a pattern-matching click input (ALL -> list; a single component -> scalar)."""
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def clicked(triggered, ids, values):
    """True only if the triggering button was really clicked. Dash also fires a pattern-matching
    callback when the number of components changes (every rebuild) - which would end a freshly
    created experiment with `n_clicks = 0` (FR-04). `ids` and `values` are in the same order."""
    for component_id, value in zip(click_values(ids), click_values(values)):
        if component_id == triggered:
            return bool(value)
    return False


def resolve_device(value):
    """Accept a device id or an iSpindel name and return the numeric `device.id` (or None)."""
    if value is None:
        return None
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        rows = query("SELECT id FROM device WHERE id = %s", (int(value),))
    else:
        rows = query("SELECT id FROM device WHERE mqtt_name = %s", (value,))
    return rows[0]["id"] if rows else None


def create_experiment(name, device_id, start, beer_style, og, yeast, responsible, notes):
    """FR-01: create and start an experiment. Returns (alert, reload_delta)."""
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
    """FR-04: end the active experiment on a device (id or iSpindel name). Returns (alert, delta)."""
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
    """The dialog's field values from one experiment row (FR-01 - FR-06)."""
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
    """The experiment running on a device (id or name) as form values, or None (FR-04)."""
    device_id = resolve_device(device)
    if not device_id:
        return None
    rows = query("""SELECT name, started_at, beer_style, og_plato, yeast, responsible, notes
                    FROM experiment WHERE device_id = %s AND ended_at IS NULL LIMIT 1""",
                 (device_id,))
    return form_values(rows[0]) if rows else None


def experiment_device(exp_id):
    """The device id of an experiment - an FR-05 row ends it by device (FR-04). The id and not the
    name: two brokers may carry an iSpindel with the same name (FR-15)."""
    rows = query("""SELECT d.id FROM experiment e JOIN device d ON d.id = e.device_id
                    WHERE e.id = %s""", (exp_id,))
    return rows[0]["id"] if rows else None


def experiment_form_values(exp_id):
    """The dialog's field values for an existing experiment, or None if it is gone (FR-06)."""
    rows = query("""SELECT name, started_at, beer_style, og_plato, yeast, responsible, notes
                    FROM experiment WHERE id = %s""", (exp_id,))
    return form_values(rows[0]) if rows else None


def update_experiment(exp_id, name, start, beer_style, og, yeast, responsible, notes):
    """FR-06: save the edited fields of an existing experiment. Returns (alert, reload_delta).
    The end time is not touched here - that is what "End experiment" wrote (FR-04)."""
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
    """Delete an experiment and its measurements (`experiment_id` has no ON DELETE CASCADE)."""
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
              # both forms live in the static layout: Dash validates a callback's State ids
              # against the initial layout, so the (hidden) device fields must exist too.
              Output("exp-form", "children"), Output("exp-form", "style"),
              Output("dev-form", "children"), Output("dev-form", "style"),
              Output("msg", "children"), Output("modal-msg", "children"), Output("reload", "data"),
              # FR-21: the CSV row action writes the download here
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
              # the rendered ids of each button pattern, so `clicked()` can spot a real click
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
    """One callback for everything that writes `exp-modal.opened` (Dash allows one callback per
    output): open the dialog, create, edit, delete, cancel, end, plus the csv row action (FR-21;
    the chart action is swallowed here and handled by `toggle_chart`, FR-17). `exp-target` holds
    the current job: {"mode": create|end, "device": id} or {"mode": edit|delete|device, "id": id}.
    Validation errors go into the dialog (`modal-msg`), successes to a page toast."""
    reload_data = reload_data or 0
    triggered = ctx.triggered_id
    target = target or {}

    # the 12 outputs in order: exp-target, opened, title, submit label, exp-form children/style,
    # dev-form children/style, msg, modal-msg, reload, download.
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
        """FR-21/NFR-05: report the CSV row action as a toast and hand the file to `dcc.Download`."""
        return shape(message=ui.toast(alert), download=download)

    def end_dialog(device):
        """FR-04: open the end confirmation for the experiment running on `device` (id or name)."""
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
        # a rebuild adds this red button with n_clicks = 0 - only a real click may end (FR-04)
        if not clicked(triggered, end_ids, end_clicks):
            return nothing()
        # FR-04: the button opens the confirmation dialog (mode: end), it does not end directly
        return end_dialog(triggered.get("device"))
    if isinstance(triggered, dict) and triggered.get("type") == "setup-btn":
        # a rebuild can fire this with an empty click list - only a real click opens
        if not clicked(triggered, setup_ids, setup_clicks):
            return nothing()
        return opened({"mode": "create", "device": triggered.get("device")},
                      "Set up experiment", "Start experiment", experiment_form())
    if isinstance(triggered, dict) and triggered.get("type") == "row-btn":
        if not clicked(triggered, row_ids, row_clicks):
            return nothing()
        if triggered.get("mode") == "chart":
            # FR-17: `toggle_chart` writes `chart-select`; swallow the click (no dialog)
            return nothing()
        if triggered.get("mode") == "csv":
            # FR-21/FR-22: export this experiment over the selected time range
            data, alert = download_csv([triggered.get("exp")], range_key)
            return exported(alert, data)
        if triggered.get("mode") == "end":
            # FR-04: the same confirmation popup as the card's red button (device looked up here)
            return end_dialog(experiment_device(triggered.get("exp")))
        # FR-06: the pencil / trash icon opens the same dialog, prefilled
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
        # FR-12: the settings icon of a Devices-table row (guarded by `clicked()` like the rest)
        if not clicked(triggered, dev_ids, dev_clicks):
            return nothing()
        values = device_values(triggered.get("device"))
        if values is None:
            return closed(ui.toast(ui.alert("that iSpindel no longer exists", "amber")))
        return opened({"mode": "device", "id": triggered.get("device")},
                      "Device settings", "Save device", device_form(values), device=True)
    return nothing()


# FR-15: the broker dialog. One callback for everything that writes `broker-modal.opened` (Dash
# allows one callback per output): open, add, edit, delete, pause/resume, close. The list has a
# callback of its own below, so a refresh never resets the form the user is typing in.
@app.callback(Output("broker-target", "data"), Output("broker-modal", "opened"),
              Output("broker-modal", "title"), Output("broker-submit", "children"),
              Output("broker-form", "children"), Output("broker-form", "style"),
              Output("broker-msg", "children"), Output("broker-reload", "data"),
              Input("broker-open", "n_clicks"), Input("broker-add", "n_clicks"),
              Input("broker-cancel", "n_clicks"), Input("broker-submit", "n_clicks"),
              Input({"type": "broker-btn", "broker": ALL, "mode": ALL}, "n_clicks"),
              State("broker-target", "data"), State("broker-reload", "data"),
              State("broker-label", "value"), State("broker-host", "value"),
              State("broker-port", "value"), State("broker-prefix", "value"),
              State("broker-user", "value"), State("broker-password", "value"),
              State("broker-enabled", "value"),
              State({"type": "broker-btn", "broker": ALL, "mode": ALL}, "id"),
              prevent_initial_call=True)
def broker_action(open_clicks, add_clicks, _, submit_clicks, row_clicks, target, reload_data,
                  label, host, port, prefix, user, password, enabled, row_ids):
    """One callback for the whole FR-15 dialog: open it, add a broker, edit, delete, pause/resume.

    `broker-target` holds the open job ({"mode": create|edit|delete, "id": <broker id or None>}).
    Validation errors stay inside the dialog (`broker-msg`); a write returns to the list and bumps
    `broker-reload`, which re-renders it. The page toast (`msg`) belongs to the experiment dialog
    and is deliberately not written from here.
    """
    reload_data = reload_data or 0
    triggered = ctx.triggered_id
    target = target or {}
    hidden, shown = {"display": "none"}, {"display": "block"}

    def shape(target=dash.no_update, opened_=dash.no_update, title=dash.no_update,
              submit=dash.no_update, form=dash.no_update, style=dash.no_update,
              message=dash.no_update, delta=0):
        """The 8 outputs in order; `delta` reloads the list without touching the form."""
        return (target, opened_, title, submit, form, style, message, reload_data + delta)

    def listing(message="", delta=0):
        """Back to the list: form hidden, submit label reset, message above the table."""
        return shape(target=None, opened_=True, title="MQTT brokers", submit="Save broker",
                     style=hidden, message=message, delta=delta)

    def nothing():
        return shape()

    if triggered == "broker-open":
        return listing()
    if triggered == "broker-cancel":
        return shape(target=None, opened_=False, message="")
    if triggered == "broker-add":
        return shape(target={"mode": "create"}, opened_=True, title="Add MQTT broker",
                     submit="Save broker", form=broker_form(), style=shown, message="")
    if triggered == "broker-submit":
        mode, broker_id = target.get("mode"), target.get("id")
        if mode == "delete":
            alert, delta = delete_broker(broker_id)
        elif mode in ("create", "edit"):
            alert, delta = save_broker(broker_id if mode == "edit" else None, label, host, port,
                                       prefix, user, password, enabled)
        else:
            alert, delta = ui.alert("pick a broker to edit, or add one (FR-15)", "amber"), 0
        if delta:
            return listing(alert, delta)              # written -> list, the dialog stays open
        return shape(opened_=True, message=alert)     # keep the form with the reason inside
    if isinstance(triggered, dict) and triggered.get("type") == "broker-btn":
        # a rebuild adds these icons with n_clicks = 0 - only a real click may act
        if not clicked(triggered, row_ids, row_clicks):
            return nothing()
        mode, broker_id = triggered.get("mode"), triggered.get("broker")
        if mode == "toggle":
            alert, delta = toggle_broker(broker_id)
            return listing(alert, delta)
        values = broker_values(broker_id)
        if values is None:
            return listing(ui.alert("that broker no longer exists", "amber"), 1)
        if mode == "delete":
            counts = query("""SELECT (SELECT count(*) FROM device d
                                         WHERE d.broker_id = %(id)s) AS devices,
                                     (SELECT count(*) FROM measurement m
                                        JOIN device d ON d.id = m.device_id
                                       WHERE d.broker_id = %(id)s) AS measurements""",
                           {"id": broker_id})[0]
            return shape(target={"mode": "delete", "id": broker_id}, opened_=True,
                         title="Delete broker", submit="Delete broker", style=hidden,
                         message=ui.alert(
                             f"delete '{values['label']}' with its {counts['devices']} iSpindels "
                             f"and {counts['measurements']} measurements? Their cards and their "
                             f"experiments disappear from the dashboard. This cannot be undone.",
                             "red"))
        return shape(target={"mode": "edit", "id": broker_id}, opened_=True,
                     title="Edit MQTT broker", submit="Save broker", form=broker_form(values),
                     style=shown, message="")
    return nothing()


@app.callback(Output("broker-list", "children"),
              Input("tick", "n_intervals"), Input("broker-reload", "data"),
              Input("broker-modal", "opened"))
def update_broker_list(_, __, opened):
    """The FR-15 list inside the dialog. It re-reads while the dialog is open, so the state the
    ingest writes back (connected / delivering / error) follows without closing the dialog."""
    if not opened:
        return dash.no_update
    return broker_table(broker_rows())


def chart_window(range_key):
    """FR-16: the selected time range as the (start, end) the chart's x axis spans, or None for
    "entire experiment". The window comes from the database clock (the same `now()` as
    `RANGE_FILTER`), so the axis cannot disagree with the data. Pinning the axis keeps the empty
    days before an experiment's first measurement visible instead of cropping them away."""
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
    # FR-17: `ids` are the experiments toggled on in the FR-05 table (`chart-select`).
    mobile = (viewport or {}).get("mobile", False)   # FR-14/NFR-06: drop legend/titles on a phone
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
    # FR-16: `chart_window` pins the x axis to the whole range (FR-18 uses hours since start)
    return charts.fermentation_figure(series, relative=(axis == "rel"), mobile=mobile,
                                      x_range=chart_window(range_key))


def download_csv(ids, range_key):
    """FR-21/FR-22: CSV of the experiment(s) in `ids`, optionally over the selected time range.
    Returns `(download, alert)` - the `dcc.send_string` payload (or `no_update`) and a message.
    A plain function (called by `experiment_action`) so the test scripts can call it directly."""
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
    # Development server with hot reload. `use_debugger=False` keeps the interactive Werkzeug
    # console off - the dashboard binds to 0.0.0.0 and that console allows code execution.
    app.run(host=DASH["host"], port=DASH["port"], debug=True, use_debugger=False)
