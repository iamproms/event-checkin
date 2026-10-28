#!/bin/sh
set -eu
: "${ORIGIN_AUTH_SECRET:?ORIGIN_AUTH_SECRET is required}"

uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers &
api_pid=$!
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
caddy_pid=$!

shutdown() {
  kill -TERM "$api_pid" "$caddy_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
  wait "$caddy_pid" 2>/dev/null || true
}
trap shutdown INT TERM EXIT

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$caddy_pid" 2>/dev/null; do
  sleep 1
done
exit 1
