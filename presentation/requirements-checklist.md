# Requirement checklist (D4) - fill-in sheet for the presentation

This is the checklist the client uses to accept the system (assignment chapters 3 and 4).
It is the same list the deck shows on slides 14-18, with a column to tick off live.

Requirement text (verbatim): `memory-bank/requirements.md`.
Per-requirement evidence and status: `memory-bank/requirements-traceability.md`.

Priority code: **M** = Must (mandatory for acceptance), **S** = Should (needs a
justification if omitted), **C** = Could (optional).

Status code to fill in: **MET** / **PARTIAL** / **OPEN** / **N/A**,
and a **Proof** (which slide / which demo step / which screenshot shows it).

## 3.1 Experiment management (FR-01 - FR-06)

| ID | Prio | Requirement (short) | Status | Proof (slide / demo step) |
| --- | --- | --- | --- | --- |
| FR-01 | M | Create + start an experiment via the dashboard (name, start, iSpindel required; beer style, OG, yeast, responsible, notes optional) | MET | slide 10 |
| FR-02 | M | Experiment name is unique, duplicate is rejected with a clear message | MET | slide 10 |
| FR-03 | M | Exactly one iSpindel per experiment; at most one active experiment per iSpindel | MET | slide 10 |
| FR-04 | M | An active experiment can be ended; later measurements are no longer assigned | MET | slide 10 |
| FR-05 | M | Overview of all experiments (name, iSpindel, start, end, status, #measurements) | MET | slide 10 |
| FR-06 | S | Fields can be edited afterwards; events with a timestamp can be recorded and shown in the chart |  |  |

## 3.2 Data acquisition and storage (FR-07 - FR-12)

| ID | Prio | Requirement (short) | Status | Proof |
| --- | --- | --- | --- | --- |
| FR-07 | M | All iSpindels in use are received via MQTT, automatically | MET | slide 16 / T-02 |
| FR-08 | M | Every measurement is stored with all minimum fields (experiment, name, timestamp, tilt, temperature, gravity, battery, interval, RSSI) | MET | slide 8 / 16 |
| FR-09 | M | A measurement is auto-assigned to the experiment active for its iSpindel at receipt | MET | slide 16 |
| FR-10 | S | Measurements without an active experiment are kept, not lost |  |  |
| FR-11 | M | No fixed interval assumed; exactly one record per transmission, no duplicates | MET | slide 16 / T-03 |
| FR-12 | M | Data model separates experiments, iSpindels and measurements as linked entities; new iSpindels/experiments need no schema or code change | MET | slide 8 |

## 3.3 Dashboard and visualisation (FR-13 - FR-20)

| ID | Prio | Requirement (short) | Status | Proof |
| --- | --- | --- | --- | --- |
| FR-13 | M | For each active iSpindel the latest values (gravity, temperature, tilt, battery) and the time of the last measurement | MET | slide 10 / 16 |
| FR-14 | M | Chart shows gravity + temperature over time, auto-updates within 60 s, no reload | MET | slide 16 / T-04 |
| FR-15 | M | All iSpindels in use shown at once and clearly distinguishable | MET | slide 16 / T-02 |
| FR-16 | M | Any experiment including completed ones, over its entire duration, selectable time range | MET | slide 16 |
| FR-17 | M | At least two experiments overlaid in one chart for comparison | MET | slide 10 / 16 |
| FR-18 | S | Time axis switchable to relative time (hours since start) for comparison |  |  |
| FR-19 | S | Warning if an iSpindel is silent for > 3 intervals or battery < configurable threshold |  |  |
| FR-20 | C | Derived values shown (apparent attenuation, estimated ABV, gravity drop per 24 h) |  |  |

## 3.4 Data access and export (FR-21 - FR-22)

| ID | Prio | Requirement (short) | Status | Proof |
| --- | --- | --- | --- | --- |
| FR-21 | M | Measurements of a selected experiment downloadable as CSV; name + iSpindel included; opens in Excel | MET | slide 10 / T-06 |
| FR-22 | S | Several experiments and/or a selected time range in one export file |  |  |

## 3.5 Non-functional requirements (NFR-01 - NFR-09)

| ID | Prio | Requirement (short) | Status | Proof |
| --- | --- | --- | --- | --- |
| NFR-01 | M | App, database and web server run on the Raspberry Pi; only the broker may run elsewhere | MET | slide 16 |
| NFR-02 | M | Dashboard reachable in the LAN via http://hostname:port, not published to the internet | MET | slide 16 / T-08 |
| NFR-03 | M | After a restart/power failure all services start automatically, acquisition resumes | MET | slide 16 / T-07 |
| NFR-04 | M | Measurements are not lost on restart; a backup procedure is described | MET | slide 16 / T-07 |
| NFR-05 | M | Operable by a person without programming knowledge; UI in English | MET | slide 16 |
| NFR-06 | S | Usable on a smartphone browser |  |  |
| NFR-07 | S | Displaying a complete experiment takes < 5 s, also with several iSpindels |  |  |
| NFR-08 | M | A README describes installation from a fresh Pi OS; settings in a config file, not in code | MET | slide 9 / 16 |
| NFR-09 | S | Timestamps stored in UTC, displayed in Europe/Zurich, correct across DST |  |  |

## 4.1 Acceptance test (T-01 - T-08)

| Test | Requirements | What to demonstrate | Status | Proof |
| --- | --- | --- | --- | --- |
| T-01 | FR-01 - FR-05 | start with required fields only, duplicate name, iSpindel already in use, end |  |  |
| T-02 | FR-07 - FR-09, FR-15 | all iSpindels in use recorded and shown at the same time |  |  |
| T-03 | FR-11 | set the interval to 1 min, then 30 min, no duplicates |  |  |
| T-04 | FR-13, FR-14 | a new measurement appears within 60 s while the dashboard is open |  |  |
| T-05 | FR-16, FR-17 | a completed experiment + a running one, compared in one chart |  |  |
| T-06 | FR-21 | export an experiment and open it in Excel |  |  |
| T-07 | NFR-03, NFR-04 | pull the power, reconnect, no data lost, history visible |  |  |
| T-08 | NFR-02 | open the dashboard from another device via the host name |  |  |

## Scoreboard (from the assignment)

| Group | Must | Should | Could |
| --- | --- | --- | --- |
| 3.1 Experiment management | 5 | 1 | - |
| 3.2 Data acquisition | 5 | 1 | - |
| 3.3 Dashboard | 5 | 2 | 1 |
| 3.4 Export | 1 | 1 | - |
| 3.5 Non-functional | 6 | 3 | - |
| **Total** | **22** | **8** | **1** |

