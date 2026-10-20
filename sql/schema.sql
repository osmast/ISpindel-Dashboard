-- iSpindel fermentation monitor - PostgreSQL schema (tested on PostgreSQL 16).
-- Apply once on an empty database:
--   psql "postgresql://ispindel:ispindel@localhost:5435/ispindel" -f sql/schema.sql

CREATE EXTENSION IF NOT EXISTS btree_gist;   -- required by the exclusion constraint below

-- ---------- master data ----------------------------------------------------

CREATE TABLE device (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mqtt_name     text NOT NULL UNIQUE,      -- the <name> in ispindel/<name>/<field>
    display_name  text,
    is_active     boolean NOT NULL DEFAULT true,
    first_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE experiment (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL UNIQUE,                        -- FR-02
    device_id   bigint NOT NULL REFERENCES device(id),
    started_at  timestamptz NOT NULL,
    ended_at    timestamptz,                                 -- NULL = active (FR-04)
    beer_style  text,
    og_plato    numeric(5,2),
    yeast       text,
    responsible text,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR ended_at > started_at),
    -- FR-03 + FR-09: a device can never be in two experiments at the same time
    EXCLUDE USING gist (
        device_id WITH =,
        tstzrange(started_at, COALESCE(ended_at, 'infinity')) WITH &&
    )
);

-- ---------- process data ---------------------------------------------------

CREATE TABLE measurement (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     bigint NOT NULL REFERENCES device(id),
    experiment_id bigint REFERENCES experiment(id),          -- NULL = unassigned (FR-10)
    recorded_at   timestamptz NOT NULL,                      -- UTC, set by the Pi (FR-08)
    tilt_deg      numeric(5,2),
    temp_c        numeric(5,2),
    gravity_plato numeric(5,2),
    battery_v     numeric(4,3),
    interval_s    integer,
    rssi_dbm      smallint,
    gravity_raw   numeric(6,4),                              -- exactly as transmitted
    temp_raw      numeric(6,3),
    temp_unit     text,
    received_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (device_id, recorded_at)                          -- FR-11: no duplicate rows
);
CREATE INDEX measurement_exp_time_idx ON measurement (experiment_id, recorded_at);
CREATE INDEX measurement_dev_time_idx ON measurement (device_id, recorded_at DESC);

CREATE TABLE experiment_event (                              -- FR-06 (schema ready, UI later)
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    experiment_id bigint NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    occurred_at   timestamptz NOT NULL,
    kind          text NOT NULL,
    note          text
);

-- ---------- views used by the dashboard ------------------------------------

CREATE VIEW v_device_latest AS
SELECT DISTINCT ON (d.id)
       d.id AS device_id, d.mqtt_name, m.recorded_at,
       m.tilt_deg::float8      AS tilt_deg,
       m.temp_c::float8        AS temp_c,
       m.gravity_plato::float8 AS gravity_plato,
       m.battery_v::float8     AS battery_v,
       m.interval_s, m.rssi_dbm
FROM device d
LEFT JOIN measurement m ON m.device_id = d.id
ORDER BY d.id, m.recorded_at DESC;

CREATE VIEW v_experiment_overview AS
SELECT e.id, e.name, d.mqtt_name AS ispindel, e.started_at, e.ended_at,
       (e.ended_at IS NULL) AS is_active,
       count(m.id) AS measurements,
       max(m.recorded_at) AS last_seen_at,
       -- FR-01/FR-05: the optional experiment fields (appended, so that an existing database
       -- can be updated with CREATE OR REPLACE VIEW - see the migration note below)
       e.beer_style, e.og_plato, e.yeast, e.responsible, e.notes
FROM experiment e
JOIN device d ON d.id = e.device_id
LEFT JOIN measurement m ON m.experiment_id = e.id
GROUP BY e.id, d.mqtt_name
ORDER BY e.started_at DESC;

-- Migration for a database that already exists (a view can replace itself as long as the
-- existing columns keep their names and positions - new columns must be appended):
--   CREATE OR REPLACE VIEW v_experiment_overview AS <the definition above>;

