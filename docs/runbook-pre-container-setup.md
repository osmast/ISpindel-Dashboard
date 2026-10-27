# iSpindel Fermentation Monitor

Minimal fermentation monitoring system: the iSpindel publishes to MQTT, a small Python
service stores one row per transmission in PostgreSQL, and a Plotly Dash dashboard shows
live and historical data. Everything runs on a Raspberry Pi (bare metal, Miniconda).

```
iSpindel --Wi-Fi--> MQTT broker --subscribe--> ingest/mqtt_ingest.py --INSERT--> PostgreSQL
                                                                                   |
                                        browser <-- Plotly Dash  <-- SELECT --------+
```

## How the iSpindel data arrives (important)

The stock iSpindel firmware sends **one MQTT message per value** on its own topic - there is
no JSON and **no timestamp** in the payload:

| Topic | Example payload |
| --- | --- |
| `ispindel/<name>/tilt` | `62.00` |
| `ispindel/<name>/temperature` | `20.00` |
| `ispindel/<name>/temp_units` | `C` |
| `ispindel/<name>/battery` | `4.050` |
| `ispindel/<name>/gravity` | `1.0568` |
| `ispindel/<name>/interval` | `900` |
| `ispindel/<name>/RSSI` | `-55` |

Consequences that shape the whole design:

* One transmission = **7 messages in a few milliseconds**. The ingest service collects them
  and writes **exactly one measurement row** per transmission (FR-11). The firmware always
  publishes `tilt` first and `RSSI` last, so the row is written as soon as `RSSI` arrives -
  `recorded_at` is then within milliseconds of the real transmission, which the dashboard
  countdown depends on. The next `tilt` and `ingest.burst_seconds` are only fallbacks if
  messages are lost.
* **The Raspberry Pi creates the timestamp** (ISO 8601 UTC). The Pi must have a correct
  clock (NTP) - otherwise every stored time is wrong.
* `gravity` is whatever the device's calibration polynomial produces: **°P or SG**. The
  ingest converts to °P using `ingest.gravity_unit` and keeps the raw value as well.
* `temp_units` can be `C`, `F` or `K`; the ingest normalises to °C.
* Publishing uses QoS 0, not retained: if the broker or the Pi is down, that transmission is
  lost forever. Keep the broker running, and note that nothing can be recovered afterwards.

## Files

```
config.yml               all settings (NFR-08) - no settings in the code
environment.yml          Miniconda environment
sql/schema.sql           database schema (tables, keys, views)
ingest/mqtt_ingest.py    MQTT -> PostgreSQL ingest service (systemd service)
tools/fake_spindel.py    simulates an iSpindel - lets you test without hardware
tools/check_requirements.py  self-test of the requirements that need no hardware (FR-01 - FR-06, FR-10/11/15/16/21/22, NFR-05/09)
tools/ui_test.py         browser-less test of the device-card dialog and the FR-05 row actions (FR-01 - FR-04, FR-06)
tools/fr19_test.py       browser-less test of the FR-19 indication (dot green/red + texts)
tools/css_check.py       is the committed tailwind.css up to date with the sources? (`--fix` rebuilds)
tools/tailwind_class_check.py  is every class in the CSS inside a className, and nothing missing?
tools/load_test.py       NFR-07: fermentation-phase volume (2 experiments x 960 rows) and timings
tools/simulate.py        seeds clearly simulated data for demos: one experiment, or a 6-device fleet
tools/mqtt_watch.py      read-only MQTT watcher ("is anything arriving?")
tools/run_broker.sh      throwaway amqtt broker on this machine (0.0.0.0:1883)
tools/serial_monitor.py  USB serial console for the iSpindel
app/main.py              Plotly Dash dashboard
app/db.py                tiny PostgreSQL helper
app/components/ui.py     reusable Tailwind layout components (card, badge, zone, table)
app/components/charts.py Plotly fermentation charts
app/assets/input.pcss    Tailwind source   ->  build  ->  app/assets/tailwind.css
app/assets/card_state.js remembers which accordion cards are open
deploy/mosquitto.conf    minimal broker config for local testing
deploy/pi_setup.sh       one-shot Pi setup (broker + DB + schema + config.yml)
deploy/pi_update.sh      update an existing Pi installation (config, view migration, restart, verify)
deploy/pi_powercycle_test.sh  T-07/NFR-03/NFR-04: reboot the Pi and verify it comes back
sql/migrations/          view/constraint migrations for a database that already exists
package.json             Tailwind CLI v4.3 build step + the corner-shape plugin (`npm ci`, `npm run css`)
app/assets/tailwind.css  compiled CSS (committed - served by Dash)
```

## 1. Local test (macOS)

### 1.1 Database

Development stores into a **local** PostgreSQL cluster, so nothing the laptop does ever
touches the Pi's production data. The cluster lives in `data/pg` (git-ignored):

```bash
initdb -D data/pg -U ispindel --auth=trust --encoding=UTF8
pg_ctl -D data/pg -o "-p 5433 -k /tmp" -l data/pg.log start
createdb -h localhost -p 5433 -U ispindel ispindel
psql "postgresql://ispindel:ispindel@localhost:5433/ispindel" -f sql/schema.sql
```

`config.yml` already points at `localhost:5433`. `pg_ctl -D data/pg stop` stops the
cluster again (start it once per development session).

*Alternative:* the same works with a throwaway Docker container
(`docker run -d --name ispindel-pg -e POSTGRES_USER=ispindel -e POSTGRES_PASSWORD=ispindel
-e POSTGRES_DB=ispindel -p 5435:5432 postgres:16-alpine`) - then set `database.dsn` to
port 5435.

### 1.2 MQTT broker

The broker runs **on the Raspberry Pi** and the iSpindel publishes to it (section 2.1).
A laptop alone cannot receive the iSpindel data, so `config.yml` points `mqtt.host` at the
Pi (`clt-lab-n-1298.zhaw.ch`) and the laptop subscribes to the same broker. Each side
stores into its **own** database, so running the ingest on the laptop is safe and gives
live data locally.

Because both the laptop and the Pi subscribe to the same broker, their MQTT **client ids
must differ** (`mqtt.client_id`). Connecting with an id that is already in use makes
mosquitto disconnect the other client, so two ingests sharing an id kick each other off in
a loop and neither stores anything. `config.yml` carries the laptop id
(`ispindel-ingest-laptop`); the deploy scripts rewrite it to `ispindel-ingest` on the Pi.

Only for hardware-free tests (section 1.5) run a throwaway broker on the laptop and use a
separate config for it:

```bash
bash tools/run_broker.sh -d                 # amqtt on 0.0.0.0:1883
printf 'mqtt:\n  host: localhost\n' > /tmp/local.yml   # then run the tests with
ISPINDEL_CONFIG=/tmp/local.yml python ingest/mqtt_ingest.py
```

> Never run `tools/fake_spindel.py` while `mqtt.host` points at the Pi: it publishes to the
> same broker and the fake values would end up in the Pi's database.

Note: mosquitto 2.x only listens on localhost until a `listener` line is configured - see 2.1.

### 1.3 Python environment

```bash
conda env create -f environment.yml
conda activate beer
```

`environment.yml` also installs **`dash-iconify`**, which renders the icons of the FR-05 table
(pencil = edit, trash = delete, stop = end). It fetches the SVG from `api.iconify.design`
**in the browser** the first time and the browser caches it afterwards, so those icons need
internet on the first page load - the rest of the dashboard works without it.

### 1.4 Start the ingest and the dashboard

```bash
python ingest/mqtt_ingest.py     # terminal 1: prints every message it receives
python app/main.py               # terminal 2: http://localhost:8080
```

`app/main.py` runs in **debug mode**: Dash's hot reload refreshes the browser by itself when
a Python file changes and the Werkzeug reloader restarts the process, so you never have to
stop and start it by hand. The interactive Werkzeug console is switched off
(`use_debugger=False`) - the dashboard binds to `0.0.0.0` and that console would allow
arbitrary code execution from the browser. gunicorn on the Pi never runs that block.

### 1.5 Test the whole chain without hardware

```bash
python tools/fake_spindel.py --name iSpindel_test --interval 2 --count 3
```

You should see the 7 topics printed by the ingest, then `stored iSpindel_test: ... °P`,
and one row per transmission in the dashboard.

#### Simulated data for demos and layout work (`tools/simulate.py`)

`fake_spindel.py` needs a broker and produces a few rows; for **complete fermentations** in the
dashboard there is `tools/simulate.py`, which writes straight into the database:

```bash
python tools/simulate.py                    # one experiment: 7 days, 15 min interval, finished
python tools/simulate.py --running          # leave it open -> shows in the "Running" tab
python tools/simulate.py --days 3 --interval 5 --name SIM_demo
python tools/simulate.py --demo             # the 6-device fleet over four weeks (table below)
python tools/simulate.py --demo --until-now # ... with nothing dated after now
python tools/simulate.py --delete           # remove every SIM_ experiment and device
```

The single-experiment form creates the iSpindel `SIM_01` and the experiment `SIM_7d_sine`
(**673 measurements**) whose values are **two sine functions and nothing else**:

```
gravity(t) = og - drop * (1 - cos(pi*t/duration)) / 2      # HALF a period -> falling S-curve
temp(t)    = temp_mid + temp_amp * sin(2*pi*t/24h)         # one cycle per day
```

(The gravity uses **half** a cosine period: with a full one it fell *and rose back to the OG*,
which the batch card's `Rate` exposed as a positive °P/24h on a finished batch - fixed 20.10.2026.)

`tilt_deg`, `battery_v`, `interval_s` and `rssi_dbm` get plausible values, and `gravity_raw`
(SG) plus `temp_raw`/`temp_unit` keep a raw transmission like the ingest does (FR-08);
`received_at` equals `recorded_at` so the row is indistinguishable from a real one. Everything
carries the `SIM_` prefix, so it is obvious in the UI and `--delete` removes it in one go - and
the test scripts only ever delete their own `zz_` rows, so a simulation survives a test run. The
extra device is a bonus: it makes FR-15 (one card per iSpindel) and FR-17 (two experiments in
one chart) demonstrable without second hardware.

**`--demo` seeds a whole fleet instead**: 6 iSpindels in 3 groups of two, so the FR-15 overview, the
FR-05 table and the comparison chart have a realistic amount of material to work with.

| Group | iSpindels | Beer style (`beer_style`) | Curve |
| --- | --- | --- | --- |
| A | `SIM_A1`, `SIM_A2` | West Coast IPA | 22.0 °C, og 15.6 °P, drop 9.8 °P |
| B | `SIM_B1`, `SIM_B2` | Hefeweizen | 19.5 °C, og 13.4 °P, drop 8.2 °P |
| C | `SIM_C1`, `SIM_C2` | Bock (cold cellar) | 12.5 °C, og 16.2 °P, drop 6.8 °P |

Every device runs **four batches of 2-5 days** (24 experiments, ~9 500 rows at a 15 min interval)
placed on the four weeks around today: two in the past, one that is running today and one that
starts in the coming days. The **two devices of a group are almost identical** (~13 h apart, a few
tenths of a °P and a few tenths of a °C), which is the pair to overlay in the FR-17 chart and to
compare on the FR-18 relative axis, while the groups differ by several °P and °C. The last batch of
every device is left **open** (`ended_at NULL`), so all six cards show a running fermentation and the
Running tab is not empty - the schema allows only one open experiment per device and an open one
covers `[start, infinity)`, which is why it has to be the device's last batch.

> **The demo fleet contains future timestamps.** The last batches lie in the next two weeks, and a
> card always shows the *newest* row of its device, so the six SIM_ cards read a future "last
> measurement". The FR-16 ranges only have a *lower* bound, so they return those rows as well: the
> chart does not show them (the time axis is pinned to the selected window), but the CSV export does.
> Use `--demo --until-now` for a fleet that leaves the future out completely: no row is dated after
> now, the batches that have not started are not created, and the currently running batch stays open
> with a real age - 17 experiments, ~5 600 rows.

### 1.6 Test with the real iSpindel

The iSpindel has no AP while it runs normally: it wakes for ~3 s, publishes and deep-sleeps
(default interval 15 min). To get the configuration portal you must **press the reset button
twice within 1 second** (`DRD_TIMEOUT`) - the LED then blinks once per second and the AP stays
open for **5 minutes** (`PORTALTIMEOUT`). A low battery (< 3.3 V) makes it sleep for at least
an hour per cycle, which looks like a dead device.

1. Power the iSpindel over USB (a DATA cable lets you read the serial console with
   `python tools/serial_monitor.py` - it shows the firmware version, tilt, temperature,
   battery, the IP address and every publish).
2. Press reset twice quickly, then connect to the `iSpindel_...` Wi-Fi network.
3. In `http://192.168.4.1` set:
   * **Name**: a unique, permanent name, e.g. `dfp_os_01` (this becomes the topic - do not rename later)
   * **Service/API**: MQTT, **Server**: the LAN IP or host name of the broker
     (`ipconfig getifaddr en0` on the Mac, or `clt-lab-n-1298.local` on the Pi), **Port**: 1883
   * **Interval**: 60 s or more for tests (the firmware requires > 10 s)
   * **Gravity conversion**: the stock polynomial `-0.00031*tilt^2+0.557*tilt-14.054` returns
     **degrees Plato** -> set `ingest.gravity_unit: "P"`. Only use `"SG"` if you calibrated
     against specific gravity values.
4. Save. Watch the ingest output: as soon as the iSpindel wakes up, all 7 topics appear.
   If nothing arrives, check the topic prefix, the broker IP and whether the PC firewall
   allows port 1883. Sanity check for the gravity unit: dip a hydrometer/spindle in the same
   wort and compare with the value in the dashboard.

### 1.7 "Is anything arriving?" - watch MQTT without the database

`tools/mqtt_watch.py` subscribes to `ispindel/#` and prints every message plus one
summary line per transmission - the ingest and PostgreSQL are not needed:

```bash
# watch whatever broker config.yml points at
python tools/mqtt_watch.py

# watch another broker, e.g. the Pi or a ZHAW/AWS broker
python tools/mqtt_watch.py --host 192.168.0.92
python tools/mqtt_watch.py --host 10.0.0.5 --port 1883 --username iot --password secret

# stop after the first transmission (handy when you just want a yes/no answer)
python tools/mqtt_watch.py --count 1
```

If the iSpindel and the laptop are on the **same** Wi-Fi (for example both on the
ZHAW `iot-ZHAW` network, passkey from the Moodle page), the easiest reliable test is
to run the broker on the laptop, point the iSpindel at the laptop's IP and watch:

```bash
./tools/run_broker.sh -d                 # amqtt broker on 0.0.0.0:1883, logs to /tmp/ispindel-broker.log
ipconfig getifaddr en0                   # the IP to enter in the iSpindel portal
python tools/mqtt_watch.py               # watch the local broker
```

In the iSpindel portal (`http://192.168.4.1`, reachable after pressing reset twice)
set **Service/API = MQTT**, **Server = that IP**, **Port = 1883**. The firmware always
publishes under the hard-coded prefix `ispindel`, so the topics appear as
`ispindel/<name>/tilt`, ... within a few seconds of a transmission.

#### Fastest cross-network check (public broker)

The laptop and the iSpindel often sit on **different** Wi-Fi networks (campus
`ZHAW`/`edu-wlan` vs. `iot-ZHAW`), and campus networks usually isolate clients, so a
broker on the laptop is unreachable for the iSpindel. Use a public broker instead -
both sides only need internet (outbound port 1883 is allowed from the ZHAW networks):

```bash
# 1) keep <name> unique - the prefix "ispindel" is hard-coded and the broker is public
python tools/mqtt_watch.py --host broker.hivemq.com --topic 'ispindel/<name>/#'

# 2) in the iSpindel portal: SSID iot-ZHAW + passkey, Service/API MQTT,
#    Server: broker.hivemq.com   Port: 1883   Name: <name>   Interval: 60
```

`test.mosquitto.org` and `broker.emqx.io` work the same way. Map it back to the Pi
later (section 2.5); for a first yes/no this needs no network changes at all.

Troubleshooting the config portal:

* The portal AP stays open for **5 minutes** only - press **reset twice within ~1 s**
  to reopen it (LED blinks once per second).
* macOS keeps jumping back to a known network. Turn off auto-join (or "forget")
  the campus network while testing, otherwise the `iSpindel_XXXX` AP drops again.
* The `/i` page of the portal shows `Station IP` - `(IP unset)` means the device did
  not associate with the Wi-Fi. A charge-only USB cable never shows up as `/dev/cu.*`;
  `tools/serial_monitor.py` (data cable) shows the Wi-Fi join result and every publish.

### 1.8 Connect to the real iSpindel at ZHAW (laptop on `ZHAW`, iSpindel on `iot-ZHAW`)

The ZHAW lab Raspberry Pi (`clt-lab-n-1298` / `160.85.142.209`) is already associated with the
**iot-ZHAW** Wi-Fi, so it shares the network with the iSpindel and the whole chain runs there -
mosquitto, ingest, PostgreSQL and the dashboard. Nothing has to be started on the laptop:

```
iSpindel (iot-ZHAW) --> mosquitto on the Pi :1883 --> ingest --> PostgreSQL :5432 --> dashboard :8080
```

Check it with the read-only watcher (prints one summary line per transmission):

```bash
python tools/mqtt_watch.py --host clt-lab-n-1298.zhaw.ch --count 1
```

Open the Pi's dashboard - no installation needed:

    http://clt-lab-n-1298.zhaw.ch:8080

Run the dashboard on the laptop against the **local** database (section 1.1) - that is the
normal development setup, and it also shows the live iSpindel data because the laptop
subscribes to the Pi's broker. To look at the Pi's database directly instead, forward its
PostgreSQL and point a second config at the tunnel port:

```bash
ssh -N -L 5435:127.0.0.1:5432 admin@clt-lab-n-1298.zhaw.ch   # keep this terminal open
printf 'database:\n  dsn: "postgresql://ispindel:ispindel@localhost:5435/ispindel"\n' > /tmp/pi.yml
ISPINDEL_CONFIG=/tmp/pi.yml python app/main.py               # http://localhost:8080
```

> The ingest may run on the laptop **and** on the Pi at the same time as long as both use
> their own database (laptop = local cluster, Pi = localhost:5432) - each stores its own
> copy. Pointing a second ingest at the *same* database would store every transmission
> twice (`recorded_at` differs by milliseconds, so `UNIQUE (device_id, recorded_at)` does
> not catch it).

If the iSpindel ever needs re-configuring, put it in config mode (reset twice within ~1 s) and
set **Server** to the Pi's stable ZHAW name `clt-lab-n-1298.zhaw.ch`, **Port** `1883` - the DNS
name survives DHCP lease changes (see 2.1).

### 1.9 Dashboard layout

The dashboard opens with an **iSpindel overview**: one card per **active** device, covering the
capabilities of the Node-RED reference dashboard in the lab (`clt-lab-n-1279:1880`). Only devices
whose "in use" flag is set get a card (FR-13) - the **Devices** tab switches an iSpindel to
*ignored* when it should not show up.

| Node-RED widget | Dashboard equivalent |
| --- | --- |
| Aktueller Extrakt | **Gravity** zone: the reading in °P, the batch's OG, the derived `Target FG` and the 24 h rate |
| Aktuelle Temperatur | **Temperature** zone: the reading in °C, the target window of the beer style and the deviation from it |
| - | **Attenuation & ABV** zone (FR-20): apparent attenuation, the current ABV and the estimated final ABV |
| Batterieladung | battery charge in %, top right of the header (`Bat: 94 %`) |
| Gärdiagramm | the device's own fermentation chart (last `dashboard.device_chart_days` days) |
| - | card footer: how long ago the last measurement arrived and when the next one is due |

Each card is a collapsible **`<details>` accordion**:

* **collapsed** it shows the **batch** - the name of the running experiment, or the iSpindel name
  when none runs - plus its `beer_style` (`SIM_A1_4 • West Coast IPA`), the **status chip** and the
  three current values: gravity, temperature and battery, each as number + unit in the same row
  (`27.1 °P`, `22.8 °C`, `Bat: 56 %`). The chip carries the **FR-19 dot**: **green** while the
  iSpindel is healthy, **red** as soon as one of the two conditions of the requirement holds - no
  measurement for more than three intervals (or none at all yet), or a battery voltage below
  `dashboard.battery_warn_v`. Its label is the **batch state** (`ACTIVE` / `IDLE`), never a
  warning text. Battery: volts -> % via `dashboard.battery_empty_v` / `battery_full_v`, amber
  below `dashboard.battery_warn_v`; gravity and temperature use one fixed reference colour each
  (`text-yellow-600` / `text-purple-700`),
* **open** it reveals the three **data zones** - they replaced the two Plotly dials on 20.10.2026.
  **Gravity**: the reading, the OG of the batch (`(OG 15.9 °P)`), the derived `Target FG: ~3.2 °P`
  and `Rate: -1.9 °P/24h` (green while the gravity falls - the fermentation is working -, red while
  it rises, no colour while the history is too short). **Temperature**: the reading, the
  `Target: 19.0–21.0 °C` window of the beer style and how far the reading is off it
  (`▲ 1.1 °C High` / `▼ 1.1 °C Low` / `✓ in range`). **Attenuation & ABV**: `54.7% Atten`,
  `4.0% ABV` and `Est. Final: 5.7% ABV`. Every derived number is explained in `docs/concept.md`
  (FR-20), and a value whose input is missing is rendered as `-`. Then the
  device's own **fermentation chart**, the experiment controls and a footer line: the
  tilt / RSSI / interval summary on the left and, on the right,
  **`last: 12 s ago · upcoming: in 12 s`** - how old the last measurement is and when the next
  transmission is due (FR-13 / FR-14). A red dot is explained here as text, **one line per
  condition** (FR-19), e.g. `no data for 60 min (more than three intervals of 900 s)` and
  `battery low: 3.300 V is below the 3.50 V threshold`; the collapsed header stays one quiet
  line per device and carries no text for the warning,
* the **chevron** on the far right is a bordered square rotated 45 deg (points down) that
  turns to 225 deg (points up) when the card opens, with `transition-transform duration-200`,
* opening and closing is **animated over `--accordion-transition-duration: 0.5s`** - the custom
  property is declared on `details[data-card]` in `app/assets/input.pcss` and consumed by the
  card's content box (`::details-content`), which grows to its natural height and fades in. The
  height can only animate to `auto` because the same stylesheet turns
  `interpolate-size: allow-keywords` on, and the content stays visible while it closes because
  `content-visibility` is transitioned with `allow-discrete`; a browser without that support
  simply opens the card instantly. The header (`<summary>`) sits outside that box, so the
  collapsed values never move, and `prefers-reduced-motion` turns the animation off.

The footer times count from `recorded_at` and `recorded_at + interval`, so they follow the
device whatever interval it uses and resync within a second when a transmission arrives early
or late; `upcoming: overdue` means the device is late. Two callbacks drive them:
`update_device_times` re-reads the latest timestamps every `dashboard.live_ms` (a tiny query -
the slow dashboard refresh would leave the age up to 15 s behind) and a `clientside_callback`
on `dcc.Interval(id="tick1s")` only subtracts the browser clock, so the once-per-second tick
costs no requests.

Nothing of the collapsing needs a callback: Tailwind's `group-open:` compiles to
`:is(:where(.group):is([open], :popover-open, :open) *)`, so the browser's own `<details>`
state drives both the hidden values and the chevron. `dmc.Accordion` would have needed an
extra callback to re-render the header on every toggle (dmc is still used for the grids).

#### Keeping a card open across a refresh

Dash gives every component a React key: the component's `id` if it has one, otherwise its
**index path** (`createContainer` in the dash renderer). A `<details>` whose key shifts is
unmounted and mounted again, and a remount throws the `open` attribute away - that is what
kept closing the cards every time `update_dashboard()` rebuilt the tree. Two things together
fix it:

* the `<details>` carries an `id`, so its key is stable whatever changes around it, and
* its `open` comes from the `open_cards` store, so even a remount restores the state.

`app/assets/card_state.js` keeps that store current: `<details>` fires a `toggle` event
(which does not bubble, hence the capture-phase listener) and the script pushes the whole
open set into the store with `dash_clientside.set_props("open_cards", {data: ...})`.

`update_dashboard()` reads it as a **`State`, not an `Input`**, so toggling a card costs no
callback round trip - the browser opens it instantly and the next refresh simply renders it
the same way.

The same stable key is what makes the **fade-in** of the `ui.card()` panels work: they carry
`animate-fade-in motion-reduce:animate-none`, and because a refresh reuses the DOM node the
animation plays **once** - on the first render - instead of replaying every 15 s. The animation
is a Tailwind theme entry (`@theme { --animate-fade-in: fade-in 0.45s ease-out both; @keyframes
fade-in {...} }` in `app/assets/input.pcss`). The **device cards do not animate** on purpose
(20.10.2026: fading the cards on a grid rebuild looked buggy), so they carry no
`animate-fade-in` and no per-`slot` delay.

**Brand colours** live in the same `@theme` block (20.10.2026): `--color-page: #FFDD00` - the
yellow page canvas, `bg-page` on the outer `min-h-screen` div of `ui.page()` - and
`--color-brand: #0057B7` - the **outline** of every container: the white `ui.card()` panels and the
device cards use `border-brand`. A **running** device card gets the thicker `border-2` plus a
`ring-2 ring-page` (the yellow), so it still stands out against the otherwise identical idle
outline (FR-04). One token instead of a raw hex in each `className`, so the palette changes in a
single place.

**Fonts** (20.10.2026): the UI uses the classic IBM XGA-AI pixel font from *The Ultimate Oldschool
PC Font Pack v2.2* by VileR (int10h.org), licensed CC BY-SA 4.0 - the license text is kept at
`app/assets/fonts/LICENSE-oldschool-pc-font-pack.txt`. Four `.woff` faces (7x15, 12x20, 12x23 and
the "12x20 Plus" with the expanded charset) are copied into `app/assets/fonts/` (Dash serves that
folder automatically) and declared with `@font-face` in `input.pcss`; `--font-sans` in the same
`@theme` block sets **`IBM XGA-AI 12x20`** as the page default, which Preflight applies through
`--default-font-family`. These web fonts are built so that one `em` equals the original pixel
height (7x15 -> 15px, 12x20 -> 20px, 12x23 -> 23px), so a `font-size`/`line-height` at one of
those values renders 1:1 crisp (whole multiples stay crisp too); change the family name in
`--font-sans` to switch. The **Plotly figures do not inherit the page font** - they draw their own
SVG text - so `charts.FONT_FAMILY` names the same family for the comparison chart and the
per-device chart, and `main.py` passes it to the Mantine theme (see the note below).

> **Mantine overrides the page font by default.** dmc's `MantineProvider` injects
> `body, :host { font-family: var(--mantine-font-family) }` into the page - and because that rule is
> *unlayered* it beats Tailwind's `@layer base` rule on `<html>`, whose default
> `--mantine-font-family` is the system stack. Setting `--font-sans` alone therefore changes
> nothing in the browser; the same stack has to be passed to the provider as `fontFamily` (plus
> `fontFamilyMonospace` and `headings.fontFamily`) in the `THEME` dict of `main.py`, which is what
> actually makes the font show up.

A device that never reported shows `0` in the zones - like the reference dashboard - and the red
FR-19 dot; the reason (`no data yet - this iSpindel has not reported`) is the first line of the
expanded card. Below the overview follow the experiment features:
start/end an experiment with the optional FR-01 fields, the experiment table (FR-05, including
the optional fields and the per-row actions), the comparison chart (FR-14 - FR-18, its FR-16 /
FR-18 controls below the figure) and the CSV export (FR-21 / FR-22, a row action with a toast).
All charts are Plotly - `dcc.Graph`, no extra plotting library; the batch zones are plain HTML with
Tailwind classes, which is what makes them so much lighter than the two dial figures they replaced.

> The times line can only be as accurate as `recorded_at`. While the ingest still waited for
> `ingest.burst_seconds` (10 s) before writing the row, the footer showed 20 s instead
> of 30 s and sat on `overdue` for 10 s per cycle. Check with
> `SELECT received_at - recorded_at FROM measurement ORDER BY id DESC LIMIT 5` - it should be
> milliseconds, not seconds.

The overview loops over every row of `v_device_latest`, so **every iSpindel that publishes
to the broker appears automatically** - no per-device configuration. The reference
dashboard shows ten iSpindels (`MTB1` - `MTB10`) because they publish to its broker; the
Pi's broker currently only sees `dfp_os_01` (check with `tools/mqtt_watch.py`).

#### Grid and page width

The cards sit in a **`dmc.Grid`** (dash-mantine-components) with
`span={"base": 12, "md": 6, "xl": 4}`: one card per row on a phone, two from Mantine's
`md` (992px, laptop) and three from `xl` (1408px). The three zones inside a card use the
same grid with `span={"base": 12, "sm": 4}`, so they stack on a phone and stand **side by
side from `sm`** (768px). The page container uses the **full width on a laptop** and is capped at
1536px on very large screens, so the layout does not stretch across a 27" monitor.

The device chart is sized by **CSS, not by the figure**: `plot()` wraps the `dcc.Graph` in a div
carrying a Tailwind height class (`h-40 sm:h-52`) and the figure is built with
`height=None`/`autosize`, so it follows the container. The graph itself
needs `height: 100%` **and** a parent with a definite height; without that Plotly falls
back to its own default height and overflows the card.

The compact per-device chart drops the legend (the card title already names the device) and
sets `automargin` on its axes, so they only take the space the tick labels and titles need
and the plot area stays as large as possible on a narrow screen. Hovering shows an **opaque
dark box** (`layout.hoverlabel`) plus a **vertical spike that snaps to the data point**
(`spikesnap="data"`), so it is obvious which measurement the values belong to; the markers
carry a white outline so they stand out against the card. The experiment comparison chart
keeps its legend and a fixed 460px height.

The zones are **text, not figures**: three `ui.zone()` boxes (an uppercase caption over two or
three lines), which is why a card renders in a fraction of the time the two `go.Indicator` dials
needed - and why the numbers are readable on a phone without shrinking fonts (NFR-06).

> **Development only:** the other iSpindels of the course still publish to their own broker,
> so `DEV_REPEAT` in `app/main.py` can repeat the first device to judge the grid with several
> cards for a **layout test only** - it is set to `1` (every card is a real device, FR-15).
> If you raise it, note that the repeated cards get a `slot` key in their times id so the
> ids stay unique; Dash matches pattern ids on the **exact set of keys**, so a selector that
> omits `slot` would silently stop updating the footer times.

#### Phone layout (NFR-06)

The dashboard is used on a smartphone in the cellar, so the elements that suffer most on a
narrow screen are adapted:

* the **device cards stand alone**: the overview has **no container box** at all (no
  background, no outline, no rounding), so the cards themselves are the only boxes on the
  page background;
* **buttons** get `min-h-11` (**44 px** - the smallest comfortable touch target) and
  `w-full sm:w-auto`, so on a phone they fill the row and on a laptop they stay compact. The
  experiment dialog stacks its Cancel / Start buttons in a column on a phone. The two
  **experiment buttons on a device card are the compact variant** (`ui.button(..., compact=True)`:
  `text-xs` like the rest of the card footer, `min-h-8`, `px-2.5 py-1`, `rounded-md`), so they
  do not dominate the footer line;
* the **radio labels** of the chart controls are `min-h-11` flex rows, and the control row is
  `flex-col` on a phone and a single wrapping row from `sm`;
* the **three zones** of a batch card stack (`span={"base": 12, "sm": 4}`), so a phone gets one
  zone per row instead of three squeezed columns, and the header hides the `beer_style` next to
  the batch name (`hidden sm:inline`) where there is no room for it;
* the **charts drop their legend on a phone** and shorten the axis titles to `time` / `hours`
  ("no legends on mobile, just time"). Plotly cannot read CSS media queries, so the browser
  writes the breakpoint into the **`viewport` store**: a `clientside_callback` on the 1 s tick
  returns `{"mobile": window.innerWidth < 768}` - and only when the breakpoint actually
  changes, so a dragged window does not spam the callbacks. `update_chart` and
  `update_dashboard` read the store and pass `mobile=True` to
  `charts.fermentation_figure()`, which turns the legend off, uses the short axis titles and
  tightens the margins and the fonts.

#### One y axis per chart

Every line plot (`charts.fermentation_figure()`, used by the device cards and the comparison
chart) has a **single y axis** - no `secondary_y`. Gravity (°P) and temperature (°C) share the
scale, so the ticks and labels are on the left only and the whole right-hand side stays plot
area. The temperature trace is drawn **dotted and slightly transparent** (`dash="dot"`,
`opacity=0.6`) so the two quantities stay apart, and the axis title carries both units
(`gravity (°P) · temperature (°C)`, shortened to `°P · °C` on a phone). The x axis carries the
**time** (`time (local)`, or `hours since start` for the FR-18 relative view).

Markers are drawn only while they stay readable: `mode="lines+markers"` up to **200 points** and
`"lines"` above that, so the 7-day simulation (673 points at 15 min) looks like the same kind of
chart as an 18-point one instead of turning into a fat band of 673 overlapping dots. Trace
colours come from one palette by series order, so a chart differs from another only in its data.

#### Experiment dialog on the device card (FR-01 - FR-04)

There is no separate start/end card anymore. The experiment belongs to one iSpindel, so its
controls live **in that iSpindel's card, lower left**:

| Card state | Lower left of the card |
| --- | --- |
| no experiment yet | grey **Set up experiment** button (`bg-slate-100` -> `hover:bg-slate-200`, `ui.button(..., tone="grey")`) which opens the dialog |
| experiment running | `running experiment: <name>` plus a red **End experiment** button (`bg-red-600` -> `hover:bg-red-500`) |

Because the card knows its device, the iSpindel is **not a field of the form** any more - it cannot
be picked wrong, and the dialog carries the numeric `device_id` (`resolve_device()` also accepts an
iSpindel name so a wrong value can never become a database error). The dialog itself contains the
name, the start time (empty = now) and the five optional FR-01 fields. Validation errors appear
**inside the dialog** (`modal-msg`), successes on the page (`msg`).

Design decisions worth keeping:

* the dialog sits **outside** the device grid: the grid is rebuilt every `dashboard.refresh_ms`, so
  a form inside a card would lose what the user has typed;
* the dialog is closed **only** through its Cancel / Start buttons (`withCloseButton=False`,
  `closeOnClickOutside=False`, `closeOnEscape=False`): a modal the browser closes on its own would
  leave Dash's `opened` state at `True`, and the next click on "Set up experiment" would not
  reopen it;
* the click handlers are **one** callback (`experiment_action`) because Dash allows only one
  callback per output, and open/submit/cancel/end all write `exp-modal.opened`;
* a pattern-matching click arrives as a scalar when only one card exists - `click_values()`
  normalises it, and the times clientside callback does the same for its id list;
* a grid rebuild fires the callback with empty click lists; that must never reopen the dialog
  (guarded and covered by `tools/ui_test.py`).

#### Experiment actions in the table (FR-04 / FR-06 / FR-17 / FR-21)

The `Actions` column of the FR-05 table follows the **row state**
(`row_actions(exp_id, running, selected)`); every icon is a `dmc.ActionIcon` + `dash_iconify` with
a `dmc.Tooltip`:

| Row | Action | What a click does |
| --- | --- | --- |
| both | **chart-line** (`chart`) | FR-17: adds / removes this experiment from the comparison chart - blue while it is shown, grey otherwise, so the row itself says what is overlaid |
| both | **pencil** (`edit`) | FR-06: opens the dialog prefilled with that experiment (also while it is running) |
| running (`Running (n)`) | red **stop** (`end`) | opens the *same* confirmation dialog as the red **End experiment** button of the device card (FR-04) - read-only fields, the end time is written when it is confirmed |
| completed (`Completed (n)`) | **trash** (`delete`) | FR-06: the same dialog with the values plus the delete warning |
| both | **download** (`csv`) | FR-21: exports **this** experiment over the selected FR-16 time range; the feedback is a top-right toast (NFR-05) |

A **running** experiment therefore carries edit + end (+ chart + csv) but **no delete**: the end
time is not part of the edit form (it is what "End experiment" writes), so the pencil is safe,
while a batch that is still collecting data should not be deletable by a single misplaced click
(NFR-05). Ending stays a two-step confirmation - the row icon and the card button only *open* the
dialog, `exp-submit` with `mode: end` does the work.

* the **pencil** opens the *same* dialog prefilled with that experiment's name, start and FR-01
  fields. The fields are the children of `#exp-form`, which the callback rebuilds from
  `experiment_form(values)` - one dialog serves "new", "edit" and "delete", and because the
  callback answers `no_update` for the form on every other action, typing is never lost;
* the **trash** opens the same dialog with the values plus a red warning
  (`delete '<name>' and its N measurements? This cannot be undone.`);
* the dialog **title and primary button follow the mode**: `Set up experiment` /
  `Start experiment`, `Edit experiment` / `Save changes`, `Delete experiment` /
  `Delete experiment`. `exp-target` carries `{"mode": ..., "id": ..., "device": ...}` so the
  submit knows whether to create, update or delete;
* the ids are pattern ids
  (`{"type": "row-btn", "exp": <id>, "mode": "end"|"edit"|"delete"|"chart"|"csv"}`) and the callback
  guards them with `clicked()` exactly like the card buttons - a rebuilt table fires the callback
  with `n_clicks = 0` as well. The **end** icon cannot carry the iSpindel name (an extra key in the
  id would make the click stop matching the callback pattern), so `experiment_device()` looks it up
  and the confirmation is built exactly like the card's. The `chart` mode is handled by
  `toggle_chart` (its own `chart-select` output) and `experiment_action` only swallows that click,
  so it never opens a dialog; the `csv` mode runs `download_csv()` for the one experiment and shows
  the result as a toast;
* **the two analysis actions are on every row**: `chart` (FR-17) toggles the experiment in the
  comparison chart (the multi-select dropdown of the chart card was replaced by this row action),
  `csv` (FR-21) exports that one experiment over the selected FR-16 time range;
* **editing runs the same validation as creating**: a duplicate name (FR-02), an overlapping
  start (FR-03) and a start after the end (the table's `CHECK`) are refused with a message in
  the dialog. The **end time is not part of the edit form** - it stays what "End experiment"
  wrote (FR-04);
* **deleting removes the experiment and its measurements** (`measurement.experiment_id` has no
  `ON DELETE CASCADE`, so the rows go first) - which is why the confirmation names the count.
  The timestamped events with chart markers of FR-06 are still open (only the edit half is done).

The **experiment table** shows those fields as well (the notes as the tooltip of the name
cell), so a started experiment can be checked without touching the database. All six columns
required by FR-05 stay in place, followed by the `Actions` column described above. The panel
carries **no heading line of its own** - the tab labels already say what is shown.

The panel is split into **three tabs** (`dmc.Tabs`): `Running (n)`, `Completed (n)` and
`Devices (n)` (FR-12, see below). The two experiment panels come from the same
`v_experiment_overview` query and differ only in the status filter, so the FR-01 fields are visible
in both views and a long list of finished batches no longer buries the experiment that is running.

The **Tabs shell lives in the static layout**, not in the rebuilt table, for two reasons:
a string id inside callback-generated content cannot be used as a callback `Input` (Dash
validates every id at startup and aborts otherwise), and a component that is never re-rendered
keeps its own state - so the tab the user picked simply survives the 15 s refresh and no store
is needed. `update_dashboard()` therefore has seven outputs: the device grid, the three tab bodies
(FR-05 running / FR-05 completed / the FR-12 Devices table) and the three tab labels with their
counts.

#### Devices tab (FR-12)

The **Devices** tab of the same panel shows the master data the ingest maintains on its
own: the first message of a new iSpindel creates its row, so a new device appears here without any
code change. One row per device:

| Column | Source | Notes |
| --- | --- | --- |
| Name (MQTT topic) | `device.mqtt_name` | the `<name>` in `ispindel/<name>/<field>`; **not editable** - it is the identity the device publishes with, renaming it would detach the device from its data |
| Display name | `device.display_name` | free text, set in the settings dialog |
| Status | `device.is_active` | `in use` (green) or `ignored` (grey) |
| First seen | `device.first_seen_at` | when the ingest first saw the device |
| Last measurement | `v_device_latest.recorded_at` | local time (NFR-09) |
| Interval | `v_device_latest.interval_s` | the transmission interval the iSpindel itself reports (FR-11) |
| Measurements | count | how many rows this device contributed |
| Actions | – | the settings icon opens the dialog |

The **settings dialog** is the experiment modal again with a different form (read-only MQTT name, a
display name, the "in use" flag) - one modal, one callback (`experiment_action`, `mode: "device"`),
so no second dialog machinery. An **ignored** iSpindel keeps recording (FR-10) but leaves the
overview, because the cards are rendered for active devices only (FR-13) - that is what gives the
flag its meaning.

#### Chart controls and export (FR-16 - FR-22)

The comparison chart no longer has controls **above** it (20.10.2026): the experiment selection
moved into the FR-05 table's row actions (the `chart` icon, FR-17 - see the actions table above),
so the card carries only the figure and the two axis controls **below** it (the panel has no
heading line either, like the FR-05 table). The panel is **always visible** and shows
"no measurements yet" while nothing is selected - hiding it was tried on 20.10.2026 and taken back
the same day, because the FR-16/FR-18 controls live in it and it should be there from the start:

| Control | Position | Requirement | Effect |
| --- | --- | --- | --- |
| Time axis: absolute / hours since start | bottom **left** | FR-18 | switches the x axis to the hours since the first measurement of each experiment |
| Time range: entire experiment / last 7 days / last 24 h | bottom **right** | FR-16 | limits the query to `recorded_at >= now() - interval` - the whole experiment is the default |

The x axis follows the selected range instead of being cut to the available points: `chart_window()`
asks the **database** for `now()` - the same clock `RANGE_FILTER` compares against - and the figure
(`charts.fermentation_figure(x_range=...)`) draws exactly that window. The days in front of an
experiment's first measurement therefore stay visible as empty plot area (select *last 7 days* while
an experiment has been running for three days and the four empty days before it are shown - they
answer "how long has this been running?"). With *entire experiment* (the default) the axis keeps
Plotly's autoscale and spans the experiment's own run time. The FR-18 relative axis ignores the
window on purpose: it counts hours since the start and has to begin at 0.

The two selected experiments are overlaid in one chart (FR-17): each row's `chart` icon toggles
that experiment into / out of the chart, the `chart-select` store holds the ids and the icon turns
**blue** while the experiment is shown (the table is an `Input` of `update_dashboard`, so the icon
updates on the click, not only on the 15 s refresh). The default is an empty chart with a hint
pointing at the table - no experiment is auto-selected any more.

All figures on the page are **read-only**: `GRAPH_CONFIG` sets `displayModeBar: False`, which
takes the Plotly toolbar (zoom / pan / autoscale / download-as-image / fullscreen buttons) off
the comparison chart and the device charts. It is noise for a non-programmer and it covers the
plot on a phone (NFR-05).

> The controls are wrapped by `ui.field()`, which renders a `<div>`/`<span>` and **not** a
> `<label>`: `dcc.RadioItems` renders a `<label>` per option and a `<label>` inside a `<label>`
> is invalid HTML - the browser then also clicks the *first* radio whenever any option is
> clicked, which made the Time range / Time axis selectors snap back to their first option.
> The same reason keeps the query correct: the range really is applied (proven by
> `tools/check_requirements.py`: `range=all` shows one more point than `range=24h`).

The **export is a row action** now too (`csv` icon, FR-21): it exports that one experiment over
the selected time range (FR-22) and answers with a top-right **toast** - an export with no data
used to do nothing at all, which looks like a broken button to a non-programmer (NFR-05). The
export function `download_csv()` is no callback of its own any more; `experiment_action` calls it
and writes the file to `dcc.Download`.

**Structure of the export file** (the specification asks for this in the README):

| Column | Unit / format | Example |
| --- | --- | --- |
| `experiment` | experiment name as stored | `2026_IPA_Mueller` |
| `ispindel` | iSpindel name from the MQTT topic | `dfp_os_01` |
| `timestamp_utc` | ISO-8601-like `YYYY-MM-DD HH24:MI:SS` + `Z`, UTC | `2026-10-20 09:24:30Z` |
| `timestamp_local` | same instant in `dashboard.timezone` | `2026-10-20 11:24:30` |
| `tilt_deg` | ° (tilt angle of the iSpindel) | `62.00` |
| `temperature_c` | °C, normalised from `temp_units` | `23.10` |
| `gravity_plato` | °P, converted with the polynomial rule if the device sends SG | `30.00` |
| `battery_v` | V | `4.050` |
| `interval_s` | s (device transmission interval) | `30` |
| `rssi_dbm` | dBm (Wi-Fi signal strength) | `-81` |

The file is comma separated with a header line, `.` as the decimal separator, one row per
measurement ordered by experiment and time, and named `<experiment>.csv` (or
`experiments.csv` for several experiments). `UTF-8`, `\n` line endings - Excel opens it
directly, no import wizard needed.

## 2. Deploy on the Raspberry Pi (bare metal)

No Docker - everything runs directly on Raspberry Pi OS. Replace
`admin@clt-lab-n-1298.local` with your own user and host name.

### 2.1 System packages and database

```bash
ssh admin@clt-lab-n-1298.local
sudo apt update
sudo apt install -y mosquitto mosquitto-clients postgresql chrony
sudo systemctl enable --now mosquitto postgresql chrony

sudo -u postgres psql -c "CREATE USER ispindel WITH PASSWORD 'ispindel';"
sudo -u postgres psql -c "CREATE DATABASE ispindel OWNER ispindel;"
```

#### Broker configuration (mosquitto 2.x listens on localhost by default)

```bash
sudo cp deploy/mosquitto.conf /etc/mosquitto/conf.d/ispindel.conf
sudo systemctl restart mosquitto
ss -ltn | grep 1883          # must show 0.0.0.0:1883 - not 127.0.0.1:1883

mosquitto_pub -h 127.0.0.1 -t ispindel/_selftest/tilt -m 45.6   # smoke test
```

The iSpindel then points at the Pi: **Server Address = the Pi's IP** (`hostname -I`) or, better,
the stable ZHAW DNS name (`hostname -f`, e.g. `clt-lab-n-1298.zhaw.ch`), **Server Port = 1883**.
The DNS name resolves on the ZHAW network and survives DHCP lease changes, so the iSpindel keeps
working after the Pi reconnects. `deploy/mosquitto.conf` sets `allow_anonymous true`, which is fine
inside the local network (NFR-02) - do not expose port 1883 to the internet; section 2.5 shows
the username/password variant for that case.

### 2.2 Copy the project and create the environment

```bash
# from the laptop - note the exclusion of config.yml: the repository copy points at the SSH
# tunnel (5435) and the lab broker, the Pi needs localhost/5432 (deploy/pi_update.sh fixes it,
# but excluding it keeps the running configuration intact)
rsync -a --exclude node_modules --exclude __pycache__ --exclude '*.pyc' --exclude .git \
  --exclude config.yml --exclude 'iSpindel Project _ Moodle ZHAW.html' \
  ./ admin@clt-lab-n-1298.local:~/ispindel/

# on the Pi - Miniconda, then the "beer" env
cd ~/ispindel
curl -fsSLO https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh -b

# Miniconda ships Anaconda's "defaults" channel, which now stops non-interactive
# installs with "CondaToSNonInteractiveError". environment.yml is conda-forge only,
# so point conda at conda-forge and drop the Anaconda channel - no ToS click needed:
printf 'channels:\n  - conda-forge\nchannel_priority: strict\ndefault_channels: []\n' \
  > ~/miniconda3/.condarc
~/miniconda3/bin/conda env create -f environment.yml

# broker config + PostgreSQL role/database + schema + config.yml in one shot
# (idempotent; does the cp/sudo -u postgres/sed/psql steps of 2.1 and the edits below):
bash deploy/pi_setup.sh
```

**Updating an existing installation** (what was done on 20.10.2026):

```bash
rsync -a --exclude node_modules --exclude __pycache__ --exclude '*.pyc' --exclude .git \
  --exclude config.yml --exclude 'iSpindel Project _ Moodle ZHAW.html' \
  ./ ispindel-pi:/home/admin/ispindel/          # ispindel-pi = key-only ssh alias
ssh ispindel-pi 'cd ~/ispindel && bash deploy/pi_update.sh'   # config, migration, restart, verify
ssh ispindel-pi 'cd ~/ispindel && ~/miniconda3/envs/beer/bin/python tools/check_requirements.py'
```

> **Why `config.yml` is excluded:** it is the only file that must differ between the laptop and the
> Pi (DSN port and broker host). Without the exclusion an `rsync` silently points the Pi's ingest
> and dashboard at `localhost:5435` - running services keep working, but the next restart fails.
> The flip side: **every other setting changed here has to be applied to the Pi's copy by hand**,
> because `pi_update.sh` only rewrites the DSN / broker host / client id (and then prints the
> effective values). The wider gauge scale of 20.10.2026, for example:
>
> ```bash
> ssh ispindel-pi "cd ~/ispindel && sed -i \
>   -e 's/^  expected_attenuation: .*/  expected_attenuation: 80/' config.yml && \
>   grep -n expected_attenuation config.yml"
> ```
>
> (A nested block such as `dashboard.target_temp_c` is easier to add with an editor than with
> `sed` - or copy the block over from this repository's `config.yml`.)

### 2.3 Start automatically after a reboot (NFR-03)

```bash
sudo tee /etc/systemd/system/ispindel-ingest.service > /dev/null <<'EOF'
[Unit]
Description=iSpindel MQTT ingest
# network-online: wait for an address; chrony-wait: the Pi has no RTC, so the clock is days
# behind until NTP answers - without this the ingest would stamp measurements with the
# fake-hwclock time of the last shutdown (FR-08/NFR-09).
After=network-online.target chrony-wait.service postgresql.service mosquitto.service
Wants=network-online.target chrony-wait.service

[Service]
User=admin
WorkingDirectory=/home/admin/ispindel
ExecStart=/home/admin/miniconda3/envs/beer/bin/python ingest/mqtt_ingest.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/ispindel-dashboard.service > /dev/null <<'EOF'
[Unit]
Description=iSpindel dashboard
After=network-online.target chrony-wait.service postgresql.service
Wants=network-online.target chrony-wait.service

[Service]
User=admin
WorkingDirectory=/home/admin/ispindel/app
ExecStart=/home/admin/miniconda3/envs/beer/bin/gunicorn --chdir /home/admin/ispindel/app main:server -b 0.0.0.0:8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable chrony-wait                      # the units wait for this one
sudo systemctl enable --now ispindel-ingest ispindel-dashboard
systemctl status ispindel-ingest --no-pager
```

> **Assumption:** the units use `User=admin` and the repository at `/home/admin/ispindel`
> (the account created by the Raspberry Pi Imager). If you imaged the Pi with a different
> user, change those two lines in both unit files - the paths appear in `User`,
> `WorkingDirectory` and `ExecStart`.

**After a power cycle** the Pi needs roughly a minute: Wi-Fi associates, `network-online.target`
and `chrony-wait.service` (clock) are reached, then Postgres, mosquitto and the two services.
`systemctl is-active` right after SSH answers can still say `inactive` - check again after
~60 s (measured 20.10.2026: SSH back after 24 s, everything active after ~60 s).

The dashboard is then reachable in the local network at
`http://clt-lab-n-1298.local:8080` (NFR-02: nothing is published to the internet).

### 2.4 Backup (NFR-04)

```bash
sudo tee /etc/cron.daily/ispindel-backup > /dev/null <<'EOF'
#!/bin/sh
mkdir -p /home/admin/backups
pg_dump -Fc "postgresql://ispindel:ispindel@localhost:5432/ispindel" \
  > /home/admin/backups/ispindel-$(date +%F).dump
find /home/admin/backups -name 'ispindel-*.dump' -mtime +14 -delete
EOF
sudo chmod +x /etc/cron.daily/ispindel-backup
```

Restore:

```bash
pg_restore -d "postgresql://ispindel:ispindel@localhost:5432/ispindel" backups/ispindel-YYYY-MM-DD.dump
```

### 2.5 Where should the broker run?

The iSpindel must be able to reach the broker over the network:

* **Same Wi-Fi as the Pi** (normal case on brew day): the broker on the Pi is enough. Set the
  iSpindel server to the Pi's IP or host name.
* **Different network**: run mosquitto on a small VPS (or a public broker) and set
  `mqtt.host` accordingly. NFR-01 explicitly allows the broker to run off the Pi.

Two things to remember with a public broker: there is no authentication, so anyone can
publish values for your device name, and the firmware hard-codes the topic as
`ispindel/<name>/...` (the prefix is not configurable on the device). Keep an eye on the
real device names during the fermentation phase.

### 2.6 Firewall: the dashboard stays in the network (NFR-02)

The lab Pi has a **publicly routable address** (`160.85.142.209`), the dashboard has **no
authentication**, and the requirement says it must not be published to the internet. So port
8080 is limited to the campus network at the host itself:

```bash
sudo tee /etc/nftables.conf > /dev/null <<'EOF'
#!/usr/sbin/nft -f
# NFR-02: the dashboard must not be reachable from the internet. This Raspberry Pi has a
# publicly routable address and the dashboard has no authentication, so 8080 is limited to the
# campus network; 1883 stays open for the iSpindel and 22 for SSH. The input policy stays
# "accept", i.e. this file can never lock anybody out - it only drops 8080 from outside
# 160.85.0.0/16.
flush ruleset

table inet filter {
    chain input {
        type filter hook input priority filter; policy accept;

        iif lo accept
        ct state established,related accept

        tcp dport { 22, 1883 } accept                    # SSH + MQTT (the iSpindel connects here)
        ip saddr 160.85.0.0/16 tcp dport 8080 accept     # dashboard: campus network only
        tcp dport 8080 drop                              # everything else is dropped
    }
}
EOF

sudo nft -c -f /etc/nftables.conf      # syntax check first
sudo nft -f /etc/nftables.conf         # apply
sudo systemctl enable --now nftables   # and load it again after every boot
sudo nft list ruleset                  # verify
```

Revert with `sudo nft flush ruleset`. Add another subnet (e.g. a home network or the
`iot-ZHAW` range if the iSpindel must reach 8080) as another `ip saddr ... tcp dport 8080
accept` line **before** the `drop`.

**Access from outside the campus network** goes through an SSH tunnel instead of opening the
port - the same path the local development setup uses:

```bash
ssh -L 8080:localhost:8080 admin@160.85.142.209    # then http://localhost:8080
ssh -L 5435:localhost:5432 admin@160.85.142.209    # psql on localhost:5435
```

### 2.7 Start, stop and check the app on the Pi (day-to-day)

Section 2.3 installs the two units and **enables** them, so after a power cycle the app comes back
by itself (~60 s). Everything below is for working on the running Pi in between.

```bash
ssh ispindel-pi                 # key-only alias from ~/.ssh/config; 2.6 has the tunnel variant

systemctl status ispindel-ingest ispindel-dashboard --no-pager
sudo systemctl start   ispindel-ingest ispindel-dashboard   # start both services
sudo systemctl stop    ispindel-ingest ispindel-dashboard   # stop both (e.g. before a manual run)
sudo systemctl restart ispindel-ingest ispindel-dashboard   # after a code or config change
```

The dashboard is then reachable in the campus network at **`http://clt-lab-n-1298.zhaw.ch:8080`**
(`http://clt-lab-n-1298.local:8080` works as well); from outside the campus network use the SSH
tunnel of 2.6, `ssh -L 8080:localhost:8080 ispindel-pi`.

| Question | Command |
| --- | --- |
| does the dashboard answer? | `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/` -> `200` |
| is anything being stored? | `psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" -c "SELECT count(*) AS rows, max(recorded_at) AS newest FROM measurement"` |
| what did the ingest just receive? | `journalctl -u ispindel-ingest -n 10 --no-pager` |
| why is the dashboard down? | `journalctl -u ispindel-dashboard -n 30 --no-pager` |
| is the broker listening for the iSpindel? | `ss -ltn \| grep 1883` -> must show `0.0.0.0:1883` |
| is the iSpindel publishing at all? | `mosquitto_sub -h 127.0.0.1 -t 'ispindel/#' -v` |

**Deploying a code or configuration change** - the order matters, because a service that is
already running keeps the old code *and* the old `config.yml` in memory:

```bash
# 1. from the laptop: copy the tree over (config.yml included - step 2 rewrites it to the Pi's values)
rsync -ai --exclude node_modules --exclude __pycache__ --exclude '*.pyc' --exclude .git \
  --exclude data --exclude 'iSpindel Project _ Moodle ZHAW.html' \
  ./ ispindel-pi:/home/admin/ispindel/

# 2. on the Pi: config.yml (dsn / broker host / client id), the view migration, restart, verify
ssh ispindel-pi 'cd ~/ispindel && bash deploy/pi_update.sh'

# 3. the self-test of everything that needs no hardware (exits 0 when every line says PASS)
ssh ispindel-pi 'cd ~/ispindel && ~/miniconda3/envs/beer/bin/python tools/check_requirements.py'
```

Before overwriting the Pi's `config.yml` that way, keep a copy
(`ssh ispindel-pi 'cp ~/ispindel/config.yml ~/ispindel/config.yml.bak'`) - it is the only file
whose content differs from the repository, and 2.2 explains what the `sed` rules of
`pi_update.sh` change.

> **A dependency added to `environment.yml` has to be installed on the Pi by hand** - the `beer`
> env is created once and never rebuilt by a deploy. On 21.10.2026 the dashboard sat in a restart
> loop with `ModuleNotFoundError: No module named 'dash_iconify'` (the FR-05 icons), because the
> Pi's env predates that entry; the fix was
> `~/miniconda3/envs/beer/bin/python -m pip install "dash-iconify>=0.1"` and a restart. A new
> `import` in the code behaves the same way - check `journalctl -u ispindel-dashboard` first when
> the dashboard is `activating` and `curl` answers nothing.

For a one-off look at the dashboard in the foreground (no gunicorn, hot reload) stop the service
first, otherwise the port is taken:

```bash
sudo systemctl stop ispindel-dashboard
cd ~/ispindel && ~/miniconda3/envs/beer/bin/python app/main.py    # Ctrl-C to leave, then start it again
```

## 3. Configuration (`config.yml`)

| Setting | Meaning |
| --- | --- |
| `database.dsn` | PostgreSQL connection string (local development: port 5433, Pi: 5432) |
| `mqtt.host` / `mqtt.port` | broker address |
| `mqtt.client_id` | MQTT client id - must be unique per broker (laptop vs Pi) |
| `mqtt.topic_prefix` | must be `ispindel` for a real iSpindel (the firmware hard-codes it) |
| `mqtt.username` / `password` | `null` = anonymous |
| `ingest.burst_seconds` | fallback wait for the remaining messages of one transmission (must stay below the iSpindel interval) |
| `ingest.gravity_unit` | `SG` or `P` - the unit produced by the device's calibration polynomial |
| `ingest.log_messages` | print every received MQTT message (useful while testing hardware) |
| `dashboard.port` | dashboard port (8080) |
| `dashboard.refresh_ms` | chart refresh interval, must stay below 60000 (FR-14) |
| `dashboard.live_ms` | countdown: how often the next transmission time is re-read (1000) |
| `dashboard.battery_warn_v` | battery warning threshold (FR-19) |
| `dashboard.battery_full_v` / `battery_empty_v` | 100 % / 0 % limits of the battery charge (default 4.2 V / 3.3 V) |
| `dashboard.expected_attenuation` | FR-20: assumed apparent attenuation in % - gives `Target FG = OG * (1 - x/100)` and the estimated final ABV (default 80) |
| `dashboard.target_temp_c` | FR-20: target temperature window per beer style (`default` + keywords such as `ipa`, `lager`, `bock`), matched case-insensitively inside `beer_style` |
| `dashboard.device_chart_days` | history window of the per-iSpindel chart |
| `dashboard.timezone` | display time zone, storage is always UTC (NFR-09) |

`ISPINDEL_CONFIG=/path/to/other.yml` runs any component with a different config file
(handy for testing against another broker/database without editing the repository copy).

## 4. Tailwind CSS (Tailwind CLI v4.3)

The UI is styled with Tailwind utility classes. Tailwind compiles `app/assets/input.pcss`
into `app/assets/tailwind.css`, which Dash serves automatically from `app/assets/`
(`<link rel="stylesheet" href="/assets/tailwind.css">`).

The compiled file is committed, so the dashboard looks right straight after cloning.

### Dev mode or build?

There is **no Tailwind at runtime**. Tailwind runs once, writes `app/assets/tailwind.css`, and
Dash then serves that finished file statically - a class added to a `.py` file does **nothing**
in the browser until the CSS is rebuilt, and only that one class is affected while everything
around it still looks styled, so the element just looks half broken.

| Command | What it is | When |
| --- | --- | --- |
| `npm run watch` | **dev mode** - `--watch --minify`, rebuilds on every save, Ctrl-C stops it | while editing the UI |
| `npm run css` | **the build** - one-shot, minified | before committing / deploying |

Both write the **same** minified file, so switching back and forth needs no extra step: run
`watch` while editing, stop it, run `css` before committing. (`watch` carries `--minify` for
exactly that reason: an unminified watch output used to differ from a fresh build, which made
`css_check.py` report a stale CSS that was not stale.) The same commands are wired as VS Code
tasks - **Terminal → Run Task**: `Tailwind: build` (also `Cmd/Ctrl+Shift+B`),
`Tailwind: watch`, `Tailwind: check`.

`python tools/css_check.py` is the guard for the committed artefact: it rebuilds into a temp
file and compares byte for byte (`--fix` writes it in place):

```
python tools/css_check.py          # rebuilds into a temp file and compares with the committed one
  NOT IN THE CSS YET  .bg-black
  NOT IN THE CSS YET  .hover\:bg-amber-500
  the compiled CSS is stale ->  python tools/css_check.py --fix   (or: npm run css)
python tools/css_check.py --fix    # write app/assets/tailwind.css
```

Traps that look the same but are not:

* **A class name must be written out in full inside a `className`/`extra` argument.** No lookup
  table, no f-string, no `"bg-" + tone`. Tailwind reads the raw *text* of a file and would find
  a class sitting in a variable just as well - but the **editor** cannot (see "Editor setup"),
  and neither can the next reader. `python tools/tailwind_class_check.py` fails when a class
  reaches the CSS from anywhere that is not a `className`, and when a `className` names a class
  the compiled CSS does not have (a typo, or a stale build).
* **Do not name classes in the prose of a comment or a docstring** - neither in `app/**/*.py`
  nor in `input.pcss`, which are the scanned files. An ordinary English word that also happens
  to be a utility (`table`, `visible`, `static`, `outline`) creates an unused rule; a
  hyphenated one (`bg-black` in a troubleshooting sentence) adds a rule nobody uses.
  `tailwind_class_check.py` lists both.
* **Variants need their parent class.** `group-open:hidden` and `group-open:rotate-[225deg]`
  only match while an ancestor carries `group`; drop `group` from a card's `className` and the
  chevron stops rotating and the collapsed header values stop hiding - silently, with no error.
* **Colour classes need the property class.** `border-slate-200` is only a colour: without
  `border` there is no border width, so nothing is visible. The same applies to
  `text-*`/`bg-*` on an element whose own text colour or background wins.
* **A `)` inside a `className=(...)` expression truncates the editor's match.** The
  parenthesised shape of `classRegex` stops at the first `)`, so the inner conditions have to
  stay free of parentheses - a comment like `(e.g. …)` inside the expression is enough to hide
  every class behind it from the editor.

### Option A - Tailwind CLI via npm (needs Node.js)

```bash
npm ci            # tailwindcss + @tailwindcss/cli + @toolwind/corner-shape, from package-lock.json
npm run css       # the build: app/assets/tailwind.css, minified
npm run watch     # dev mode: --watch --minify, rebuilds on every change (Ctrl-C stops it)
```

### Option B - standalone CLI, no Node.js (recommended on the Pi)

The same CLI is shipped as a single executable (v4.3.3):

```bash
# macOS (Apple Silicon)
curl -fL -o tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-macos-arm64
shasum -a 256 tailwindcss    # expect cdf646702987a743464dff4d9c60fd4480d1c1e73dd819a9a67f1078815dce9d
chmod +x tailwindcss

# Raspberry Pi (64-bit Raspberry Pi OS)
curl -fL -o tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-linux-arm64
shasum -a 256 tailwindcss    # expect 55fd0b241214eff3de1e8ee4f22796662f2d2e7a49bcfca7477cfd0bac398195
chmod +x tailwindcss

./tailwindcss -i app/assets/input.pcss -o app/assets/tailwind.css --minify
```

Notes:

* Check the download size: ~80 MB (macOS arm64) / ~110 MB (linux arm64). A truncated file
  fails with `main executable failed strict validation` - download it again.
* `app/assets/input.pcss` deliberately uses the `.pcss` extension, and `assets_ignore` in
  `app/main.py` keeps Dash from linking it: Dash links *every* file in `app/assets/`, and
  the Tailwind source must never be served as CSS (the browser would reject the MIME type
  and log an error).
* `input.pcss` switches Tailwind's automatic source detection **off**
  (`@import "tailwindcss" source(none)`) and names the one place where class names live:
  `@source "../**/*.py"`, i.e. `app/`. Without `source(none)`, Tailwind v4 scans the whole
  project (git-aware) - `README.md`, `docs/`, every comment - and every class name *mentioned in
  prose* is compiled into the shipped CSS. With it, `tailwind.css` holds exactly the classes the
  UI uses. Add another `@source` line if a class string ever moves into another file type.
* The same file loads the plugin `@plugin "@toolwind/corner-shape"` - that is how a Tailwind v4
  plugin is wired, from the CSS entry point, because there is no `tailwind.config.js` here. It
  adds `corner-*` utilities for the CSS `corner-shape` property, and every rounded surface in
  the dashboard uses `corner-squircle` next to its `rounded-*` radius. A browser that does not
  know the property ignores it, so radius and layout are unaffected there. To drop the plugin
  again: remove the `@plugin` line, the `corner-squircle` classes and the dependency.
* Tailwind's preflight resets some browser defaults. If a Plotly or Dash element starts
  looking off, load `tailwind.css` before other styles or disable preflight.
* `node_modules/` is git-ignored; `package.json` and `package-lock.json` are committed.

### Editor setup: Tailwind completions inside the Python files (IntelliSense)

The build never needs an editor (`npm run css`), but while editing the UI it is worth having real
completions. The workspace settings for that ship in **`.vscode/settings.json`**, because Tailwind
v4 needs two non-obvious hints in this project:

* **The entry point has to be named.** This project is CSS-first (Tailwind v4): there is **no
  `tailwind.config.js`**, the configuration is `app/assets/input.pcss`. The extension
  (`bradlc.vscode-tailwindcss`) auto-detects only `*.css` entry points, so it finds nothing here
  and stays silent in the whole repository - `tailwindCSS.experimental.configFile` points it at
  `app/assets/input.pcss` explicitly.
* **Python has to be declared.** Class names live in Python string literals
  (`className="grid gap-4"`, `ui.button(..., extra="w-full")`), so the settings map `python` onto
  the markup mode (`tailwindCSS.includeLanguages`) and describe the string shapes with
  `tailwindCSS.experimental.classRegex`. This repository writes them in two shapes and both are
  covered: a plain or multi-line string after `className=`/`extra=`/`labelClassName=`
  (`className="flex cursor-pointer items-center gap-3 " "p-3 sm:p-4"`, which is why the pattern
  spans a newline) and a parenthesised expression for the tone/size variants
  (`className=("min-h-8 …" if compact and tone == "dark" else "min-h-11 …")`). **Add a pattern
  there if a new way of writing class strings is introduced**, otherwise the editor silently
  stops completing that one; `python tools/tailwind_class_check.py` checks that the patterns and
  the compiled CSS agree.
* `files.associations` opens `*.pcss` in the extension's own "Tailwind CSS" language mode, so
  `@import "tailwindcss"`, `@source` and `@theme` are highlighted and validated instead of being
  flagged as unknown at-rules.
* `editor.quickSuggestions` is switched on for **strings** in Python and HTML only: VS Code does
  not suggest inside string content by default, and that is exactly where the class names are.

Checking it:

* Open `app/components/ui.py`, put the cursor inside `className="..."` and type - a list of
  Tailwind utilities appears (or press `Ctrl+Space`); hovering a class name shows the CSS it
  generates. Both only work when the extension found the entry point.
* If nothing happens, run **"Tailwind CSS: Show Output"** from the command palette - the language
  server log says what it could not find.
* `.vscode/extensions.json` recommends the extension; `.vscode/settings.json` is committed on
  purpose (without it the extension does not activate for this repository at all).


## 5. Status and next steps

Deployed and verified on the ZHAW lab Raspberry Pi (`clt-lab-n-1298`, reachable as
`http://clt-lab-n-1298.zhaw.ch:8080`) on 20.10.2026 - see "Verified on the Pi" below. The
hardware-independent checks also run locally against the same database.

Verified with a real MQTT broker, the fake iSpindel, a real iSpindel and PostgreSQL:

* 7 subtopic messages per transmission are assembled into exactly one row (FR-11); on the live
  data (30 s interval) `SELECT date_trunc('minute', recorded_at), count(*)` shows exactly one
  measurement per transmission
* SG -> °P conversion, °C normalisation, raw values kept for traceability (FR-08)
* measurements without an active experiment are stored with `experiment_id = NULL` (FR-10) -
  unassigned rows are present and identifiable
* experiment name uniqueness (FR-02) and "one iSpindel, one active experiment" (FR-03) are
  enforced by the database (unique constraint + exclusion constraint); ending an experiment
  keeps new measurements out of it (FR-04)
* the FR-01 optional fields are part of the form and are stored (`NULL`, not empty strings)
* the FR-16 time range filters the chart and the export; the export reports what it wrote
  (FR-21 / FR-22), and the chart's x axis spans the **whole** selected range - the empty days
  before an experiment's first measurement stay visible
* timestamps are stored in UTC and displayed in `dashboard.timezone` (NFR-09)

**Verified on the Pi (20.10.2026):**

* `tools/check_requirements.py`: **all checks PASS** against the production database
* NFR-01/NFR-02: ingest, dashboard and PostgreSQL run on the Pi, reachable by host name
  (`http://clt-lab-n-1298.zhaw.ch:8080`, 200 in ~28 ms); 8080 is firewalled to the campus
  network (README 2.6)
* NFR-03/NFR-04: two power cycles - all services active ~60 s after the boot, 213 of 213
  measurements kept, `systemctl kill -s SIGKILL ispindel-dashboard` restarted automatically;
  a ~1 minute gap of transmissions during the boot (QoS 0, see the MQTT notes above)
* FR-14: ingest lag average 57 ms / max 102 ms over an hour, dashboard refresh 15 s -> a new
  measurement is visible within ~15 s of its receipt
* NFR-07: full refresh with 1920 measurements (2 experiments x 10 days at a 15 min interval):
  **1310 ms** (`tools/load_test.py`)

**Verified again on the Pi (21.10.2026)** - the repository was synced once more (the Pi had still
been running the build of 20.10.2026 11:29), the `dash-iconify` entry that was missing from the
Pi's `beer` env was installed (2.7), both services restarted and everything re-checked:

* `tools/check_requirements.py`, `tools/ui_test.py` and `tools/fr19_test.py`: **ALL PASS** against
  the production database, while the live `dfp_os_01` kept writing (30 s interval)
* `app/assets/tailwind.css` on the Pi is byte-identical to the committed build (same md5);
  `/_dash-layout`, `/assets/tailwind.css` and the fonts all answer 200, the dashboard renders the
  newest UI (time range, optional experiment fields, chart row selection)
* the FR-16 "range really narrows the chart" check now compares the narrowing with the database
  count of rows outside the window: on a production database the first experiment already carries
  older real measurements, and the old assertion (`all - 24h == 1`, i.e. only its own synthetic
  row) reported that correct behaviour as a failure
* FR-20 zone checks **SKIP**: `dfp_os_01` runs no experiment at the moment, so the batch card has
  no OG / target values to compare - start one from the card (or seed `tools/simulate.py`)
* `tools/css_check.py` **SKIPs on the Pi** (no Tailwind CLI there) - the CSS is built on the Mac
  and deployed (section 4)

`tools/check_requirements.py` re-runs the checks that do not need hardware (it renders the
overview, filters the chart, creates/ends a temporary experiment, exports the CSV and cleans
up after itself):

```bash
python tools/check_requirements.py      # exits 0 when every line says PASS
python tools/ui_test.py                 # FR-01 - FR-04 dialog, browser-less
python tools/fr19_test.py               # FR-19 dot + warning texts, browser-less
python tools/css_check.py               # no stale Tailwind build (--fix rebuilds it)
python tools/load_test.py               # NFR-07 with fermentation-phase volume
./deploy/pi_powercycle_test.sh          # T-07/NFR-03/NFR-04 from the laptop
```

Still missing / next steps:

* the **other iSpindels** of the course do not reach this system yet (FR-15 / T-02) - the
  broker question has to be settled on brew day; `DEV_REPEAT` is `1`
* event markers in the chart (FR-06), derived values such as attenuation and ABV (FR-20)
* a non-programmer should walk through start / display / export once (NFR-05), the dashboard
  should be tested on a smartphone (NFR-06), and a second person should install from this
  README (NFR-08)
* the DST change on 25.10.2026 is the natural NFR-09 test
* `date_bin` downsampling only if a multi-year dataset ever gets slow (NFR-07 currently has a
  factor of ~4 headroom)
* authentication-free LAN access is fine, but the broker needs a stable, reachable place

> **Requirement tracking:** `docs/spec/` is the specification itself, written as prose (no tables):
> README, assignment, system context, all 31 requirements with their acceptance criteria,
> milestones/acceptance tests and deliverables. `memory-bank/requirements-traceability.md` lists
> every requirement (22 Must, 8 Should, 1 Could) with its evidence in the code, its current status
> and the open gap; `memory-bank/requirements.md` holds the verbatim specification,
> `memory-bank/acceptance-tests.md` the recipes for T-01 - T-08, `docs/concept.md` the concept (D1)
> with the data model diagram. Update the status there whenever a requirement is finished.

