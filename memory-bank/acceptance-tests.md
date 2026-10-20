# Acceptance Test Checklist (T-01 to T-08 + the non-functional proofs)

Copy-paste recipes for proving each acceptance criterion. Run them on the Raspberry Pi with the
real iSpindel shortly before brew day (29.10.2026) - the assignment says the system must already
fulfil the Must requirements of chapters 3.1 and 3.2 on that day, and fermentation data from the
beginning can never be recorded later.

## Preparation (once)

```bash
export DSN="postgresql://ispindel:ispindel@localhost:5435/ispindel"   # on the Pi: port 5432
conda activate beer
psql "$DSN" -f sql/schema.sql        # only on an empty database
python ingest/mqtt_ingest.py         # terminal 1
python app/main.py                   # terminal 2 -> http://localhost:8080
python tools/fake_spindel.py --interval 5 --count 20   # terminal 3, optional rehearsal
```

**Automated first pass:** `python tools/check_requirements.py` already covers the parts of T-01
(FR-01 - FR-05), T-03/T-04 evidence (FR-09 - FR-11, FR-13), T-05/T-06 (FR-15, FR-16, FR-21, FR-22)
and the NFR-05/NFR-09 evidence that need no hardware - it creates temporary `zz_validation*`
records and deletes them again. Everything below is what *it cannot* check: the Pi, the other
iSpindels, long intervals and a human being.

Handy queries while testing:

```sql
-- one row per transmission, no duplicates: the newest rows with the wire latency
SELECT id, device_id, experiment_id, recorded_at, received_at - recorded_at AS lag,
       tilt_deg, temp_c, gravity_plato, battery_v, interval_s, rssi_dbm
FROM measurement ORDER BY id DESC LIMIT 10;

-- FR-11: rows per minute must equal transmissions per minute (no duplicates, nothing merged)
SELECT date_trunc('minute', recorded_at) AS minute, count(*)
FROM measurement WHERE device_id = (SELECT id FROM device WHERE mqtt_name = '<name>')
GROUP BY 1 ORDER BY 1 DESC LIMIT 20;

-- FR-10: unassigned measurements exist and are identifiable
SELECT count(*) FROM measurement WHERE experiment_id IS NULL;

-- FR-05: the overview figures must match the database
SELECT e.name, count(m.id) FROM experiment e LEFT JOIN measurement m ON m.experiment_id = e.id
GROUP BY e.name ORDER BY e.name;
```

## T-01 - Experiment management (FR-01 to FR-05) - **new UI (20.10.2026)**

The card of an iSpindel without an experiment has a grey **Set up experiment** button (lower
left); a card whose iSpindel runs an experiment shows `running experiment: <name>` and a red
**End experiment** button. Automated equivalent: `python tools/ui_test.py` (23 checks, drives the
real callbacks).

| Step | Action in the dashboard | Expected |
| --- | --- | --- |
| 1 | On a card without an experiment: **Set up experiment**, fill in only the name, press **Start experiment** | dialog closes, green message, the row appears in the experiment table and the card switches to `running experiment: <name>` + red button |
| 2 | Fill in name + beer style, OG, yeast, responsible, notes | stored; visible in the table (notes as the tooltip of the name) |
| 3 | Try a name that already exists | red message **inside the dialog**, the dialog stays open, the table does not grow (FR-02) |
| 4 | Leave the name empty, or type `fourteen` as the original gravity | amber message inside the dialog, nothing is stored |
| 5 | Press **End experiment** on the card | green message, the card goes back to the grey setup button, the experiment table says `completed`, `ended_at` is set; new measurements do not appear in it |
| 6 | Compare the table figures with the SQL above | identical counts, start/end/status correct |
| 7 | *(FR-03)* Try to give one iSpindel a second experiment | **the UI does not offer it** (the card shows the end button, not the setup button) - the database constraint was proven separately: `tools/check_requirements.py` shows the red "already runs an experiment" message |

## T-02 - All iSpindels in use (FR-07 to FR-09, FR-15)

1. Put every iSpindel of the group/course into operation, each in its **own experiment**
   (`ispindel/<name>/...` topics, distinct names).
2. `python tools/mqtt_watch.py --raw` shows the incoming topics of all devices.
3. Check: every device has a card **and** appears in its experiment (count > 0 in the table).
4. No measurement assigned twice:
   `SELECT recorded_at, count(DISTINCT experiment_id) FROM measurement GROUP BY 1 HAVING count(DISTINCT experiment_id) > 1;`
   -> must return no rows.
5. `DEV_REPEAT` in `app/main.py` must be `1` for this test.

## T-03 - Interval independence (FR-11) - partly proven

**Proven on the Pi 20.10.2026** at a 30 s interval: `SELECT date_trunc('minute', recorded_at),
count(*)` showed exactly 2 rows per minute, `UNIQUE (device_id, recorded_at)` plus
`ON CONFLICT DO NOTHING` make duplicates impossible, and a full check found 0 duplicate rows.

1. Set the iSpindel interval to **60 s**, wait ~10 minutes, then to **1800 s**, wait for two
   transmissions (the 1800 s case is still outstanding).
2. Count rows per transmission interval; exactly **one** row per transmission, no duplicates,
   no merged or split records.
3. `received_at - recorded_at` stays in the low milliseconds range (measured average 57 ms, max
   102 ms over one hour; single bursts that lose their last topic go through the 10 s
   `flush_stale` path - `recorded_at` stays the burst start, so the countdown is unaffected).


## T-04 - Liveness (FR-13, FR-14) and the FR-19 indications - **FR-13/FR-14 proven**

Automated equivalent of the FR-19 part: `python tools/fr19_test.py` (4 device states x 6 checks,
browser-less - it renders `device_card()` and inspects the tree).

**Measured on the Pi 20.10.2026:** ingest lag over one hour: average **57 ms**, maximum 102 ms;
dashboard refresh `dashboard.refresh_ms = 15000`; a measurement stored at 11:16:33 was the last
chart point in the very next callback (`tools/load_test.py` checks exactly that) -> a new
measurement is visible within ~15 s of its receipt, against the 60 s limit. The values shown in
the card were compared with the newest row (`3.801 V -> 56 %`, `tilt 96.58°`, `RSSI -77`,
`interval 30 s`) - FR-13.

1. Keep the dashboard open, note the latest values, wait for the next transmission.
2. Within **15 s** the card values, the time of the last measurement and the chart show the new
   point.
3. Compare the displayed values with `SELECT ... ORDER BY recorded_at DESC LIMIT 1` (FR-13).
4. Switch the iSpindel off; after `3 x interval` the status dot next to the device name turns
   **red**, and the expanded card shows the reason as text (FR-19).
5. Set `dashboard.battery_warn_v` above the current voltage in `config.yml`, restart the dashboard
   -> the same dot turns red and the expanded card adds the `battery low: ... V is below the ... V
   threshold` line (FR-19). Both conditions together still use one dot and show one line each.

## T-05 - Historical view and comparison (FR-16, FR-17)

1. Select a completed experiment: the complete course from start to end is visible.
2. Select a second (running) experiment: both are overlaid, distinguishable by colour + legend.
3. Switch the time axis to "hours since start" (FR-18): both curves start at the same point.
4. *(after the FR-16 fix)* switch the range to last 24 h / last 7 days / entire experiment and check
   that the chart changes accordingly.

## T-06 - Export (FR-21, FR-22)

1. Select one experiment, press "Download CSV", open the file in Excel.
2. Check: one column per field, dot decimals, readable timestamps (`timestamp_utc` ISO 8601,
   `timestamp_local` Europe/Zurich), experiment + iSpindel name present.
3. Compare the columns with the README table (must be documented there).
4. *(after the FR-22 fix)* select two experiments and/or a time range, the file contains exactly
   that selection.

## T-07 - Power cycle (NFR-03, NFR-04) - **proven 20.10.2026**

Automated from the laptop (the remote equivalent of pulling the plug):

```bash
./deploy/pi_powercycle_test.sh        # reboots, waits for SSH, waits 60 s, then verifies
                                      # -> log: /tmp/pi_reboot.log
```

Manual version:

```bash
ssh ispindel-pi 'psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" -tAc "select count(*) from measurement"'
ssh ispindel-pi 'printf "admin\n" | sudo -S -p "" sh -c "sleep 2; systemctl reboot"'
# wait ~60 s: SSH is back after ~25 s, but the services need Wi-Fi + NTP + Postgres + mosquitto
ssh ispindel-pi 'systemctl is-active ssh mosquitto postgresql ispindel-ingest ispindel-dashboard nftables chrony-wait'
ssh ispindel-pi 'psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" -c "select count(*) from measurement"'
```

Measured: 213 rows before -> 214/215 after (nothing lost, the iSpindel kept writing), all seven
services active ~60 s after the boot, `Restart=always` proven separately with
`systemctl kill --signal=SIGKILL ispindel-dashboard` (service back, HTTP 200, `NRestarts=2`).

> **Two traps:** (1) checking `systemctl is-active` 10 s after SSH answers shows `inactive` and is
> *not* a failure - wait the full minute; (2) never use `pkill -f "...gunicorn..."` over SSH, the
> pattern matches your own remote shell and kills the session - use `systemctl kill`.
> The transmissions during the ~1 min boot are lost (QoS 0 without retain).

## T-08 - LAN access (NFR-01, NFR-02) - **proven 20.10.2026**

Measured from the laptop (campus network):

```
http://clt-lab-n-1298.zhaw.ch:8080/   -> http 200 in 0.028 s
http://clt-lab-n-1298:8080/           -> http 200 in 0.041 s
http://160.85.142.209:8080/           -> http 200
```

All data comes from the Pi's own PostgreSQL, ingest and dashboard run on the Pi (NFR-01). The
dashboard is additionally kept off the internet by nftables (8080 only from `160.85.0.0/16`), and
access from outside the campus network goes through `ssh -L 8080:localhost:8080 ispindel-pi`.

Repeat check:

```bash
for u in http://clt-lab-n-1298.zhaw.ch:8080/ http://clt-lab-n-1298:8080/; do
  printf '%-40s ' "$u"; curl -s -m 10 -o /dev/null -w 'http:%{http_code} in %{time_total}s\n' "$u"
done
ssh ispindel-pi 'printf "admin\n" | sudo -S -p "" nft list chain inet filter input'
```

## NFR-05, NFR-06, NFR-07, NFR-09 - proofs that need a person or a stopwatch

| NFR | Proof | State |
| --- | --- | --- |
| NFR-05 | A person who has never seen the dashboard creates, displays (chart) and exports an experiment without help, in English - note the time needed for the introduction | open (needs a test person) |
| NFR-06 | Repeat the Must walk-through on a smartphone browser (dropdowns and the chart are the risk) | open (needs a phone) |
| NFR-07 | **measured 20.10.2026**: `python tools/load_test.py` with 1920 measurements (2 experiments x 10 days at a 15 min interval): device cards 642 ms, table 50 ms, comparison chart 203 ms, relative axis 272 ms, CSV 142 ms -> **1310 ms total** (limit 5000 ms) | **MET** |
| NFR-09 | Around the DST change on **25.10.2026** (03:00 local): points before and after must appear without gap or overlap in the chart, and the CSV must show the correct local times (`timestamp_utc` vs. `timestamp_local`); UTC storage and the +2 h display are already verified | open (25.10.2026) |

## Recording the result

Note the outcome of every test (pass/fail + screenshot) - the presentation and the acceptance depend
on being able to demonstrate the criteria. After a passing test, move the requirement to **MET** in
`requirements-traceability.md`.
