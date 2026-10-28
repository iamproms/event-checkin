#!/usr/bin/env bash
set -euo pipefail

host=platform.local.example.test
base="https://$host:8443"
temp="$(mktemp -d)"
trap 'rm -rf "$temp"' EXIT

# Caddy's local development CA may not be installed in curl's trust store.
# This probe checks the application route; browser certificate trust is separate.
request=(curl --insecure --silent --show-error --max-time 10
  --resolve "$host:8443:127.0.0.1")

check_json() {
  local path="$1" label="$2" expected="$3" code
  code="$("${request[@]}" --output "$temp/body" --write-out '%{http_code}' "$base$path")"
  if [[ "$code" != "$expected" ]]; then
    printf '%s: HTTP %s (expected %s)\n' "$label" "$code" "$expected" >&2
    cat "$temp/body" >&2
    return 1
  fi
  python3 -m json.tool "$temp/body" >/dev/null
  printf '%s: HTTP %s\n' "$label" "$code"
}

check_json /health health 200
check_json /ready readiness 200
check_json /api/v1/platform/auth/csrf platform-CSRF 200
python3 - "$temp/body" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    if not json.load(response).get("csrf_token"):
        raise SystemExit("Platform CSRF response has no token")
PY

code="$("${request[@]}" --output "$temp/console" --write-out '%{http_code}' \
  "$base/platform-console.html")"
if [[ "$code" != 200 ]] || ! grep -q '/src/platform-console.tsx' "$temp/console"; then
  printf 'Platform console: unavailable or stale HTML (HTTP %s)\n' "$code" >&2
  exit 1
fi
code="$("${request[@]}" --output "$temp/module" --write-out '%{http_code}' \
  "$base/src/platform-console.tsx")"
if [[ "$code" != 200 ]] || ! grep -q 'Create and invite organizer' "$temp/module"; then
  printf 'Simplified organization screen: missing or stale module (HTTP %s)\n' "$code" >&2
  exit 1
fi
printf 'Current organization screen: HTTP 200\n'

if [[ "${1:-}" == "--login-probe" ]]; then
  # A single synthetic invalid login verifies that CSRF, cookies, and the
  # external HTTPS Origin reach authentication. Do not run on every startup:
  # failed logins are audited and rate limited.
  "${request[@]}" --cookie-jar "$temp/cookies" --output "$temp/body" \
    "$base/api/v1/platform/auth/csrf"
  csrf="$(python3 - "$temp/body" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as response:
    print(json.load(response)["csrf_token"])
PY
)"
  code="$("${request[@]}" --cookie "$temp/cookies" \
    --header "origin: $base" --header "x-csrf-token: $csrf" \
    --header 'content-type: application/json' \
    --data '{"email":"local-probe-invalid@example.invalid","password":"synthetic-invalid-password"}' \
    --output "$temp/body" --write-out '%{http_code}' \
    "$base/api/v1/platform/auth/login")"
  if [[ "$code" != 401 ]] || ! python3 - "$temp/body" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as response:
    assert json.load(response).get("detail", {}).get("code") == "AUTH_DENIED"
PY
  then
    printf 'Synthetic login: HTTP %s (expected AUTH_DENIED 401)\n' "$code" >&2
    cat "$temp/body" >&2
    exit 1
  fi
  printf 'Synthetic login reached authentication: HTTP 401\n'
fi
printf 'Browser entry: %s/\n' "$base"
