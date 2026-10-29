-- iSpindel fermentation monitor - PostgreSQL schema (PostgreSQL 16). Applied automatically by
-- the db container on the first start; for an existing database use sql/migrations/.

CREATE EXTENSION IF NOT EXISTS btree_gist;   -- required by the exclusion constraint below

-- ---------- master data ----------------------------------------------------

-- FR-15: during the fermentation phase several iSpindels are in use, and each participant runs
-- *their own* broker - so the ingest is pointed at more than one broker. The **own** broker stays
-- where it always was, in `config.yml` (NFR-08) and is deliberately **not** a row here; the devices
-- of that broker carry `device.broker_id = NULL`. This table holds the brokers added at runtime
-- through the dashboard's "MQTT brokers" dialog.
CREATE TABLE mqtt_broker (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label         text NOT NULL UNIQUE,               -- what the dashboard shows (e.g. "Mueller Pi")
    host          text NOT NULL,                      -- host name or IP of the broker
    port          integer NOT NULL DEFAULT 1883 CHECK (port BETWEEN 1 AND 65535),
    username      text,                               -- NULL = anonymous (deploy/mosquitto.conf)
    password      text,
    topic_prefix  text NOT NULL DEFAULT 'ispindel',   -- other installations may use another prefix
    is_enabled    boolean NOT NULL DEFAULT true,      -- off = the ingest ignores this broker
    created_at    timestamptz NOT NULL DEFAULT now(),
    -- the ingest writes these three back so the dialog can show whether the broker is reachable
    -- and delivering (FR-15: "all iSpindels in use are visible at the same time")
    last_connected_at timestamptz,
    last_message_at   timestamptz,
    last_error        text
);

CREATE TABLE device (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    broker_id     bigint REFERENCES mqtt_broker(id) ON DELETE CASCADE,   -- NULL = config.yml
    mqtt_name     text NOT NULL,      -- the <name> in ispindel/<name>/<field>
    display_name  text,
    is_active     boolean NOT NULL DEFAULT true,
    first_seen_at timestamptz NOT NULL DEFAULT now()
);
-- Two participants may give their iSpindel the same name on *their* brokers, so the name is
-- unique per broker and not globally. A plain UNIQUE(broker_id, mqtt_name) would not work: NULL
-- (the config broker) compares as distinct, so the same name could be inserted twice there.
-- COALESCE turns the config broker into the value 0 for the index - the ingest upserts on
-- exactly this expression (`ON CONFLICT ((COALESCE(broker_id, 0)), mqtt_name)`).
CREATE UNIQUE INDEX device_broker_name_key ON device (COALESCE(broker_id, 0), mqtt_name);

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
       m.interval_s, m.rssi_dbm,
       -- appended 29.10.2026 (FR-15): which broker this iSpindel publishes to; NULL = config.yml
       d.broker_id AS broker_id, b.label AS broker_label
FROM device d
LEFT JOIN mqtt_broker b ON b.id = d.broker_id
LEFT JOIN measurement m ON m.device_id = d.id
ORDER BY d.id, m.recorded_at DESC;

CREATE VIEW v_experiment_overview AS
SELECT e.id, e.name, d.mqtt_name AS ispindel, e.started_at, e.ended_at,
       (e.ended_at IS NULL) AS is_active,
       count(m.id) AS measurements,
       max(m.recorded_at) AS last_seen_at,
       -- FR-01/FR-05: the optional experiment fields (appended, so that an existing database
       -- can be updated with CREATE OR REPLACE VIEW - see the migration note below)
       e.beer_style, e.og_plato, e.yeast, e.responsible, e.notes,
       -- appended 29.10.2026 (FR-15): the broker of the experiment's iSpindel; NULL = config.yml
       d.broker_id AS broker_id, b.label AS broker_label
FROM experiment e
JOIN device d ON d.id = e.device_id
LEFT JOIN mqtt_broker b ON b.id = d.broker_id
LEFT JOIN measurement m ON m.experiment_id = e.id
GROUP BY e.id, d.mqtt_name, d.broker_id, b.label
ORDER BY e.started_at DESC;

-- For an existing database a view can replace itself only as long as existing columns keep their
-- names and positions - new columns must be appended (see sql/migrations/).

