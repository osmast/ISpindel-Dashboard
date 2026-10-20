#!/usr/bin/env bash
# One-shot setup for the Raspberry Pi (broker + database + schema + config.yml).
#
# Run ON the Pi, from the repository root:
#
#   cd ~/ispindel && bash deploy/pi_setup.sh
#
# It is idempotent - running it again is safe. It does NOT install Miniconda
# (that is a one-liner in README section 2.2) and it does NOT change Wi-Fi.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "repository: $REPO"

echo
echo "== 1/5  system packages =="
sudo apt update
sudo apt install -y mosquitto mosquitto-clients postgresql chrony
sudo systemctl enable --now mosquitto postgresql chrony

echo
echo "== 2/5  broker config (mosquitto 2.x must listen on 0.0.0.0) =="
sudo install -m 0644 deploy/mosquitto.conf /etc/mosquitto/conf.d/ispindel.conf
sudo systemctl restart mosquitto
sleep 1
ss -ltn | grep 1883 || true
if ss -ltn | grep -q '0\.0\.0\.0:1883'; then
    echo "OK: mosquitto is listening on 0.0.0.0:1883"
elif ss -ltn | grep -q '127\.0\.0\.1:1883'; then
    echo "WARNING: mosquitto only listens on localhost - the iSpindel cannot reach it."
    echo "         check /etc/mosquitto/conf.d/ispindel.conf for 'listener 1883 0.0.0.0'"
else
    echo "WARNING: nothing on port 1883 - check:  sudo systemctl status mosquitto"
fi

echo
echo "== 3/5  PostgreSQL role + database =="
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='ispindel'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER ispindel WITH PASSWORD 'ispindel';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='ispindel'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE ispindel OWNER ispindel;"

echo
echo "== 4/5  schema =="
DSN="postgresql://ispindel:ispindel@localhost:5432/ispindel"
if psql "$DSN" -tAc "SELECT to_regclass('public.measurement')" | grep -q measurement; then
    echo "schema already applied - skipped"
else
    psql "$DSN" -f sql/schema.sql
fi

echo
echo "== 5/5  config.yml -> local broker + local database =="
sed -i 's|localhost:5433|localhost:5432|' config.yml
sed -i 's|"ispindel-ingest-laptop"|"ispindel-ingest"|' config.yml
# reset the broker host to "localhost": the repository copy points at the ZHAW lab Pi
sed -i -e 's|"192.168.0.92"|"localhost"|' -e 's|"clt-lab-n-1298.zhaw.ch"|"localhost"|' config.yml
grep -E '^\s+(dsn|host):' config.yml

cat <<'EOF'

done. next steps (in the "beer" conda environment):

  mosquitto_sub -h 127.0.0.1 -t 'ispindel/#' -v    # watch the broker
  python ingest/mqtt_ingest.py                     # ingest -> PostgreSQL
  python app/main.py                               # dashboard on http://<pi-ip>:8080

Then set the iSpindel's MQTT server to this Pi's IP (hostname -I), port 1883.
EOF
