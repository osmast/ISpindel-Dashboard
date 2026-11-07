-- Migration 2026-11-07: a measurement carries a note of its own (FR-06).
--
-- Applies to a database that was created before the experiment dialog could edit the individual
-- measurements: the edit dialog lists every measurement and lets the user add a note per row and
-- remove a row. `sql/schema.sql` already contains this column for fresh installations.
--
-- Appending one column to `measurement` cannot break the views - it touches neither
-- v_device_latest nor v_experiment_overview.
--
-- Run once:  psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" \
--              -f sql/migrations/2026-11-07_measurement_note_fr06.sql

ALTER TABLE measurement ADD COLUMN IF NOT EXISTS note text;
