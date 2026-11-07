# Dashboard screenshots - feature and popup index

Captured from the **production Pi** at `http://beer.chios.ch:8080` (real fermentation data,
4 iSpindels: MTB1, MTB3, MTB7, MTB9; 4 completed batches: *CoCo Jambo*, *Mango Maracuya Dream*,
*Honig Bier*, *Lemon Pale Lager*).

Use these on the D4 presentation slides (slide 10 "Live demo" backup, slide 5/13 beer data,
slide 7/8 diagrams can be photographed from the ebook). Each file maps to a feature and the
requirement it demonstrates.

| File | What it shows | Requirement |
| --- | --- | --- |
| `00_dashboard_overview.png` | the whole page: device cards, tabs, comparison chart, time controls | FR-05, FR-13, FR-14 |
| `01_overview_top.png` | the landing view, "Running (0)" tab (empty state) | FR-05 |
| `02_tab_completed.png` | the **Completed (4)** overview with name, iSpindel, start, status, #measurements, beer style, OG, yeast, responsible, end + row actions | FR-05 |
| `03_chart_comparison_2experiments.png` | two experiments overlaid in one chart (relative axis off) | FR-17 |
| `03b_chart_comparison_absolute.png` | same comparison on the absolute local-time axis | FR-16, FR-17 |
| `04_chart_relative_time_axis.png` | comparison with the axis switched to **hours since start** | FR-18 |
| `05_tab_devices_brokers.png` | the **Devices (4)** master data table + the inline broker list | FR-12, FR-15 |
| `06_device_card_expanded.png` | a device card expanded: gravity / temperature / attenuation dials, the per-device chart, tilt · RSSI · interval, the FR-19 silence warning | FR-13, FR-19 |
| `07_popup_setup_experiment.png` | **Set up experiment** dialog: required fields + the optional FR-06 fields | FR-01 |
| `08_popup_mqtt_brokers.png` | **MQTT brokers** dialog: own broker + Spanish PI + Thomas Ip with state | FR-15 |
| `09_popup_add_broker_form.png` | **Add MQTT broker** form inside the same dialog | FR-15 |
| `10_popup_edit_experiment.png` | **Edit experiment** dialog (prefilled) | FR-06 |
| `11_popup_delete_experiment_confirm.png` | **Delete experiment** confirmation | FR-12 (delete), safety |
| `12_popup_device_settings.png` | **Device settings** dialog: read-only MQTT name, display name, in-use flag | FR-12 |
| `13_popup_delete_ispindel_confirm.png` | **Delete iSpindel** confirmation (with its experiments + measurements) | FR-12 |
| `14_mobile_responsive.png` | the whole dashboard on a 390 px phone viewport | NFR-06 |

## Not captured (and why)

| Feature | Why | How to get it |
| --- | --- | --- |
| **End experiment** confirmation | no experiment is *running* on the Pi at capture time (3 of 4 are completed, fermentation is over) - the end dialog only appears on a running row | start a throwaway experiment, screenshot the end dialog, delete it again |
| **Toast notification** (experiment started / ended / export) | transient - it fades within a few seconds and fires only on an action | trigger a start/end/export and screenshot within the toast lifetime |
| **Export CSV** result | downloads a file, not a page state | export a batch and open the CSV in Excel (T-06) |

## Re-capturing

```bash
./presentation/capture_screenshots.sh http://beer.chios.ch:8080
```

The script does a `curl` reachability check and takes the static shots with **headless Chrome**.
The popup and tab-switching states need a click-through (the Dash callbacks only run in a real
browser), so those were captured through the chrome-devtools MCP browser; repeat by hand if the UI
changes.
