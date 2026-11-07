#!/usr/bin/env bash
# Capture screenshots of every dashboard feature + popup from the running Pi.
#
# Usage:
#   ./presentation/capture_screenshots.sh [BASE_URL]
#   BASE_URL defaults to http://beer.chios.ch:8080
#
# Two ways to capture:
#   1. Chrome headless  (default, non-interactive)  -> the *_static_* shots
#   2. The interactive chrome-devtools MCP session   -> the popup/click shots
#      (a headless screenshot cannot click through the Dash callbacks, so the
#       modal/dialog shots were taken through the MCP browser and are kept in
#       this folder - re-capture them by hand if the UI changed)
#
# Nothing here runs in the container; it is a documentation tool only.
set -u

BASE="${1:-http://beer.chios.ch:8080}"
OUT="$(cd "$(dirname "$0")" && pwd)/screenshots"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p "$OUT"

echo "Target : $BASE"
echo "Output : $OUT"

# 1 - quick reachability check, the same way curl would do it
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$BASE/")"
echo "GET /  -> HTTP $code"
[ "$code" = "200" ] || { echo "dashboard not reachable - is the Pi up?"; exit 1; }

if [ ! -x "$CHROME" ]; then
  echo "Google Chrome not found at $CHROME - skipping the headless shots."
  exit 0
fi

shot () {  # shot <file-name> <window-size>
  local file="$1" size="$2"
  echo "  - $file ($size)"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --virtual-time-budget=12000 --window-size="$size" \
    --screenshot="$OUT/$file" "$BASE/" >/dev/null 2>&1
}

echo "Headless shots (reloads the static page; Dash calls settle within 12 s):"
shot "00_dashboard_overview.png"  "1600,1000"
shot "14_mobile_responsive.png"   "390,844"
shot "01_overview_top.png"        "1600,1000"

echo
echo "Done. The interactive popup shots (07-13) and the tab/chart states"
echo "need the MCP browser or a manual click-through - see screenshots/INDEX.md."
