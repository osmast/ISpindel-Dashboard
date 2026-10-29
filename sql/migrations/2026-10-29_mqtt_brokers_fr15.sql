-- Migration 2026-10-29: several MQTT brokers at the same time (FR-15).
--
-- Applies to a database that was created before the dashboard could add brokers: during the
-- fermentation phase the participants each run *their own* broker, so the ingest listens on all
-- of them at once instead of on one. `sql/schema.sql` already contains this structure for fresh
-- installations.
--
-- The **own** broker keeps living in `config.yml` (NFR-08) and is deliberately not a row of
-- `mqtt_broker`: devices of that broker carry `device.broker_id IS NULL`, which reads as "the
-- broker from the configuration file". Everything else in the table is added at runtime through
-- the dashboard's "MQTT brokers" dialog.
--
-- Run once:  psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" \
--              -f sql/migrations/2026-10-29_mqtt_brokers_fr15.sql

CREATE TABLE IF NOT EXISTS mqtt_broker (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label         text NOT NULL UNIQUE,
    host          text NOT NULL,
    port          integer NOT NULL DEFAULT 1883 CHECK (port BETWEEN 1 AND 65535),
    username      text,
    password      text,
    topic_prefix  text NOT NULL DEFAULT 'ispindel',
    is_enabled    boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_connected_at timestamptz,
    last_message_at   timestamptz,
    last_error        text
);

-- existing devices belong to the broker of config.yml -> NULL
ALTER TABLE device ADD COLUMN IF NOT EXISTS broker_id bigint
    REFERENCES mqtt_broker(id) ON DELETE CASCADE;

-- the iSpindel name was globally unique; from now on it is unique per broker, so that two
-- participants may both use the name "dfp_os_01" on their own brokers (COALESCE: NULL = config).
ALTER TABLE device DROP CONSTRAINT IF EXISTS device_mqtt_name_key;
DROP INDEX IF EXISTS device_mqtt_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS device_broker_name_key
    ON device (COALESCE(broker_id, 0), mqtt_name);

-- both views only *append* columns, so an existing view can replace itself (FR-15 adds the broker)
CREATE OR REPLACE VIEW v_device_latest AS
SELECT DISTINCT ON (d.id)
       d.id AS device_id, d.mqtt_name, m.recorded_at,
       m.tilt_deg::float8      AS tilt_deg,
       m.temp_c::float8        AS temp_c,
       m.gravity_plato::float8 AS gravity_plato,
       m.battery_v::float8     AS battery_v,
       m.interval_s, m.rssi_dbm,
       d.broker_id AS broker_id, b.label AS broker_label
FROM device d
LEFT JOIN mqtt_broker b ON b.id = d.broker_id
LEFT JOIN measurement m ON m.device_id = d.id
ORDER BY d.id, m.recorded_at DESC;

CREATE OR REPLACE VIEW v_experiment_overview AS
SELECT e.id, e.name, d.mqtt_name AS ispindel, e.started_at, e.ended_at,
       (e.ended_at IS NULL) AS is_active,
       count(m.id) AS measurements,
       max(m.recorded_at) AS last_seen_at,
       e.beer_style, e.og_plato, e.yeast, e.responsible, e.notes,
       d.broker_id AS broker_id, b.label AS broker_label
FROM experiment e
JOIN device d ON d.id = e.device_id
LEFT JOIN mqtt_broker b ON b.id = d.broker_id
LEFT JOIN measurement m ON m.experiment_id = e.id
GROUP BY e.id, d.mqtt_name, d.broker_id, b.label
ORDER BY e.started_at DESC;
