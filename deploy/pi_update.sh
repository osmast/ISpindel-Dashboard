#!/usr/bin/env bash
# Deployment step 2 on the Raspberry Pi: adapt config.yml, migrate the database view,
# restart the two services and verify them. Run from ~/ispindel.
set -euo pipefail
cd "$HOME/ispindel"

DSN="postgresql://ispindel:ispindel@localhost:5432/ispindel"

echo
echo "== 0. the repository sync must NOT have overwritten the Pi's config.yml =="
echo "   (the Mac copy points at the local cluster 5433 and the local broker - the sed rules below fix it)"
grep -nE '^  (dsn|host):' config.yml | head -2

echo
echo "== 1. config.yml -> Pi values (same two sed rules as deploy/pi_setup.sh) =="
sed -i 's|localhost:5433|localhost:5432|' config.yml
sed -i -e 's|"192.168.0.92"|"localhost"|' -e 's|"clt-lab-n-1298.zhaw.ch"|"localhost"|' config.yml
sed -i 's|"ispindel-ingest-laptop"|"ispindel-ingest"|' config.yml
grep -nE '^  (dsn|host|port|refresh_ms|live_ms|battery_warn_v|battery_full_v|battery_empty_v|device_chart_days|expected_attenuation|timezone|gravity_unit|burst_seconds):' config.yml

echo
echo "== 2. apply the view migration (FR-01 columns in v_experiment_overview) =="
psql "$DSN" -v ON_ERROR_STOP=1 -q -f sql/migrations/2026-10-20_view_experiment_overview_fr01.sql
psql "$DSN" -tAc "SELECT string_agg(column_name, ', ' ORDER BY ordinal_position)
                  FROM information_schema.columns WHERE table_name='v_experiment_overview'"

echo
echo "== 3. restart the services =="
printf 'admin\n' | sudo -S -p "" systemctl restart ispindel-ingest ispindel-dashboard
sleep 3
printf 'admin\n' | sudo -S -p "" systemctl is-active ispindel-ingest ispindel-dashboard

echo
echo "== 4. verify =="
sleep 3
curl -s -o /dev/null -w "dashboard http:%{http_code}  time:%{time_total}s\n" http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/_dash-layout | python3 -c "import sys; s=sys.stdin.read(); print('new UI served - Time range:', 'Time range' in s, '| optional fields:', 'Original gravity' in s, '| chart row selection:', 'chart-select' in s)"
psql "$DSN" -c "SELECT count(*) AS rows, max(recorded_at) AS newest FROM measurement"
echo "== ingest log (last 3 lines) =="
printf 'admin\n' | sudo -S -p "" journalctl -u ispindel-ingest --no-pager -n 3 | tail -3
