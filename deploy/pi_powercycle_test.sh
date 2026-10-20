#!/usr/bin/env bash
# T-07 / NFR-03 / NFR-04 from the laptop: reboot the Raspberry Pi, wait for it to come back and
# then check that every service started again, that no measurement was lost and that the
# dashboard answers - the remote equivalent of pulling the plug.
#
#   ./deploy/pi_powercycle_test.sh          # writes to /tmp/pi_reboot.log
#
# Expect ~60 s until everything is up: Wi-Fi associates, network-online.target and
# chrony-wait.service (the Pi has no RTC, the clock is days behind until NTP answers), then
# PostgreSQL, mosquitto and the two iSpindel services. Measured 20.10.2026: SSH back after
# 24 s, all services active after ~60 s, 213 of 213 rows kept.
set -u
SSH="ssh -i /Users/os/.ssh/rpi_1298_ed25519 -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o LogLevel=ERROR ispindel-pi"
LOG=/tmp/pi_reboot.log
exec >>"$LOG" 2>&1

echo "== $(date +%T) rows before the second power cycle =="
$SSH 'psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" -tAc "select count(*) from measurement"'

echo "== $(date +%T) rebooting =="
$SSH 'printf "admin\n" | sudo -S -p "" sh -c "sleep 2; systemctl reboot" >/dev/null 2>&1 & echo reboot issued'

for i in $(seq 1 40); do
    sleep 8
    if $SSH true 2>/dev/null; then
        echo "== $(date +%T) ssh back after about $((i * 8)) s =="
        break
    fi
done

echo "== waiting 60 s so the whole boot (Wi-Fi, NTP, chained services) is finished =="
sleep 60

$SSH 'date; uptime
echo "--- services (NFR-03) ---"
systemctl is-active ssh mosquitto postgresql ispindel-ingest ispindel-dashboard nftables chrony-wait | tr "\n" " "; echo
echo "--- rows (NFR-04: must be >= the value before) ---"
psql "postgresql://ispindel:ispindel@localhost:5432/ispindel" -c "select count(*) rows, max(recorded_at) newest, now()-max(recorded_at) age from measurement"
echo "--- boot order: did the clock get corrected before the ingest started? ---"
printf "admin\n" | sudo -S -p "" journalctl -b --no-pager | grep -iE "Time has been changed|ingest running|System clock" | head -4
echo "--- firewall still loaded (NFR-02) ---"
printf "admin\n" | sudo -S -p "" /usr/sbin/nft list chain inet filter input | wc -l'

echo "== $(date +%T) from the laptop =="
for u in http://clt-lab-n-1298.zhaw.ch:8080/ http://160.85.142.209:8080/; do
    printf '%-40s ' "$u"
    curl -s -m 10 -o /dev/null -w 'http:%{http_code} in %{time_total}s\n' "$u"
done
echo "== done $(date +%T) =="
