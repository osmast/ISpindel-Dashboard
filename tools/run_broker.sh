#!/usr/bin/env bash
# Start a throwaway MQTT broker on this machine (0.0.0.0:1883) for testing.
#
#   ./tools/run_broker.sh              # foreground, Ctrl-C to stop
#   ./tools/run_broker.sh -d           # start in the background, log to /tmp/ispindel-broker.log
#
# Uses amqtt from the "beer" conda environment (no mosquitto install needed).
# It allows anonymous clients and listens on every interface, so the iSpindel
# can publish to this machine's LAN IP.
set -euo pipefail

ENV_BIN="${ISPINDEL_ENV_BIN:-/opt/homebrew/Caskroom/miniconda/base/envs/beer/bin}"
CONF="$(mktemp -t amqtt-ispindel).conf"
LOG="${ISPINDEL_BROKER_LOG:-/tmp/ispindel-broker.log}"

cat > "$CONF" <<'EOF'
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
    max_connections: 50
auth:
  allow-anonymous: true
sys_interval: 0
EOF

if [ "${1:-}" = "-d" ]; then
  nohup "$ENV_BIN/amqtt" -c "$CONF" > "$LOG" 2>&1 &
  echo "broker started (pid $!), log: $LOG"
  echo "listening on: $(ifconfig | awk '/inet /&&$2!="127.0.0.1"{print $2}' | tr '\n' ' ')"
else
  echo "broker config: $CONF   (Ctrl-C to stop)"
  echo "listening on: $(ifconfig | awk '/inet /&&$2!="127.0.0.1"{print $2}' | tr '\n' ' ')"
  exec "$ENV_BIN/amqtt" -c "$CONF"
fi
