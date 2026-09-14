#!/bin/zsh
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DST="/opt/data/skills/ld-restaurant-browser"
DATA="/opt/data/ld"

mkdir -p "$DST" "$DST/tests" "$DATA"

cp "$SRC_DIR/browser_booking.py" "$DST/browser_booking.py"
cp "$SRC_DIR/chrome_probe.py" "$DST/chrome_probe.py"
cp "$SRC_DIR/system_prompt_browser.txt" "$DST/system_prompt_browser.txt"
cp "$SRC_DIR/tests/test_helpers.py" "$DST/tests/test_helpers.py"

chmod 750 "$DST/browser_booking.py" "$DST/chrome_probe.py"

if [[ ! -f "$DATA/restaurant_reservations.json" ]]; then
  printf '%s\n' '{"schema_version":1,"reservations":[]}' > "$DATA/restaurant_reservations.json"
  chmod 600 "$DATA/restaurant_reservations.json"
fi

echo "Installed Hermes browser booking harness."
echo "Next: /usr/bin/python3 $DST/chrome_probe.py"
