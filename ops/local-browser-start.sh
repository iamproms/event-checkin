#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
for required in .env .env.compose.override.yaml; do
  if [[ ! -f "$required" ]]; then
    printf 'Missing local configuration: %s\n' "$required" >&2
    exit 1
  fi
done

dc=(docker compose -f compose.yaml -f .env.compose.override.yaml --env-file .env)
services=(db redis object-storage mailpit api web worker dispatcher
  domain-maintenance storage-maintenance https-proxy)

# A host-mode HTTPS listener cannot coexist with the Compose HTTPS edge.
# Fail before changing containers so the operator can stop only that listener.
for listener in $(fuser -n tcp 8443 2>/dev/null || true); do
  if [[ "$(ps -o args= -p "$listener")" == *'socat OPENSSL-LISTEN:8443'* ]]; then
    printf 'Port 8443 is held by the local host-mode socat listener (PID %s). Run bash .env.local-stop, then retry.\n' \
      "$listener" >&2
    exit 1
  fi
done

# Images are built explicitly after source changes. Routine starts preserve
# running infrastructure, named volumes, and existing built images.
if ! "${dc[@]}" up -d --no-build --wait --wait-timeout 120 "${services[@]}"; then
  printf '\nLocal services did not become healthy. Published-port owners:\n' >&2
  ss -ltnp '( sport = :1025 or sport = :5173 or sport = :5433 or sport = :6380 or sport = :8000 or sport = :8025 or sport = :8443 or sport = :9000 or sport = :9001 )' >&2 || true
  "${dc[@]}" ps >&2 || true
  exit 1
fi
for service in "${services[@]}"; do
  container="$("${dc[@]}" ps -q "$service")"
  if [[ -z "$container" ]] || [[ "$(docker inspect -f '{{.State.Running}}' "$container")" != true ]]; then
    printf 'Required service is not running: %s\n' "$service" >&2
    exit 1
  fi
done
"${dc[@]}" exec -T --user 10001 api python -c 'import app.auth.address'
printf 'Non-root API source import: ready\n'
"$root/ops/local-browser-check.sh"
