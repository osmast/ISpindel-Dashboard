# Project rules (iSpindel fermentation monitor)

A fermentation monitor: an iSpindel publishes gravity/temperature over MQTT, an ingest service
stores one row per transmission in PostgreSQL, and a Plotly Dash dashboard shows live and
historical data. The whole system runs as a Podman/Docker Compose stack (`./run.sh up`).

## Running and testing

* `./run.sh up | down | logs | ps | test | demo | backup | psql | shell` - the only entry point.
  It picks Podman when it is usable, Docker otherwise (`ISPINDEL_ENGINE=podman|docker` forces one).
* `./run.sh test` runs `tools/check_requirements.py`, `tools/ui_test.py` and
  `tools/fr19_test.py` *inside the container*, which is why they need no local Python
  environment.
* `npm run css` / `npm run watch` rebuild `assets/tailwind.css` (Node.js on the host) and must
  be run after a UI class change.

## Rules that are not negotiable

1. **`config.yml` is the only place for settings (NFR-08).** Never hard-code a host, port, DSN,
   threshold or time zone in the code. Environment variables (`ISPINDEL_DB_DSN`,
   `ISPINDEL_MQTT_HOST`, `ISPINDEL_MQTT_PORT`, `ISPINDEL_MQTT_CLIENT_ID`) may only *override* a
   single value so the same file works inside the container network and on a bare host - they are
   not a second configuration.
2. **`config.yml` contains no machine-specific value.** The stack is the same on every machine;
   there is no per-host config copy and no `sed` rewrite. A clone runs as it is.
3. **Reference the requirement in the comment next to the code** (`FR-11`, `NFR-09`, ...). The
   requirement IDs come from the assignment specification; the code is the traceability.
4. **Tailwind class strings are written out in full inside a `className`/`extra` argument** - no
   lookup table, no f-string, no `"bg-" + tone`. The compiler scans raw text, the editor plugin
   only understands the `classRegex` shapes in `.vscode/settings.json`, and a reader cannot see a
   composed name either.
5. **`assets/tailwind.css` is a build artefact**, never a source: after a class change run
   `npm run css` (or `npm run watch` while editing) and commit the rebuilt file. It is served
   statically - there is no Tailwind at runtime, and the container never runs Node.
6. **Schema changes go into `sql/schema.sql`** (fresh database) **and** a file in
   `sql/migrations/` (existing database). `CREATE OR REPLACE VIEW` may only append columns.
7. **Deployment is the compose stack, nothing else.** Do not add host-specific install steps,
   systemd units for a bare-metal install, or `rsync` deploy scripts: the Pi, a laptop and a
   colleague's machine run the same four containers, and the boot step is
   `deploy/systemd/ispindel.service`.
8. **This repository is the code.** Documents (concept, requirement register, meeting notes) are
   deliberately not part of it.
