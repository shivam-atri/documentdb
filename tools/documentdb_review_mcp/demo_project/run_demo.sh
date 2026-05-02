#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

PYTHONPATH="$ROOT" python3 "$ROOT/services/users/service.py" > /tmp/users.log 2>&1 &
P1=$!
PYTHONPATH="$ROOT" python3 "$ROOT/services/orders/service.py" > /tmp/orders.log 2>&1 &
P2=$!
PYTHONPATH="$ROOT" python3 "$ROOT/services/gateway/service.py" > /tmp/gateway.log 2>&1 &
P3=$!

cleanup() {
  kill $P1 $P2 $P3 >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 3
curl -sSf http://127.0.0.1:8010/profile/1
