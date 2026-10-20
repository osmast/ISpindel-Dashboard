-- Migration 2026-10-20: v_experiment_overview gains the FR-01 optional fields.
--
-- Applies to a database that was created before the optional experiment fields were shown in
-- the dashboard table (beer style, original gravity, yeast, responsible, notes).
-- `sql/schema.sql` already contains the new definition for fresh installations.
--
-- Run once:  psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" -f sql/migrations/2026-10-20_view_experiment_overview_fr01.sql

CREATE OR REPLACE VIEW v_experiment_overview AS
SELECT e.id, e.name, d.mqtt_name AS ispindel, e.started_at, e.ended_at,
       (e.ended_at IS NULL) AS is_active,
       count(m.id) AS measurements,
       max(m.recorded_at) AS last_seen_at,
       -- appended: CREATE OR REPLACE VIEW may add columns at the end, but not in the middle
       e.beer_style, e.og_plato, e.yeast, e.responsible, e.notes
FROM experiment e
JOIN device d ON d.id = e.device_id
LEFT JOIN measurement m ON m.experiment_id = e.id
GROUP BY e.id, d.mqtt_name
ORDER BY e.started_at DESC;
