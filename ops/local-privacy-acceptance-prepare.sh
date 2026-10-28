#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if [[ "$(git branch --show-current)" != feat/privacy-import-workflow ]]; then
  echo 'Expected branch feat/privacy-import-workflow; refusing to prepare another worktree.' >&2
  exit 1
fi
for required in .env .env.compose.override.yaml; do
  if [[ ! -f "$required" ]]; then
    printf 'Missing local configuration: %s\n' "$required" >&2
    exit 1
  fi
done

dc=(docker compose -f compose.yaml -f .env.compose.override.yaml --env-file .env)
"${dc[@]}" up -d --no-build --wait db

identity="$("${dc[@]}" exec -T db psql -X -v ON_ERROR_STOP=1 -U eventcheckin -d eventcheckin -At \
  -c "SELECT current_database() || '|' || current_user || '|' || version_num FROM alembic_version")"
case "$identity" in
  'eventcheckin|eventcheckin|0012_shared_event_release'|'eventcheckin|eventcheckin|0013_privacy_notice_workflow') ;;
  *) printf 'Unexpected local database, role, or migration: %s\n' "$identity" >&2; exit 1 ;;
esac
printf 'Verified local database and role: %s\n' "$identity"

counts_before="$("${dc[@]}" exec -T db psql -X -v ON_ERROR_STOP=1 -U eventcheckin -d eventcheckin -At \
  -c "SELECT (SELECT count(*) FROM tenants) || '|' || (SELECT count(*) FROM users) || '|' || (SELECT count(*) FROM events) || '|' || (SELECT count(*) FROM registrations)")"
printf 'Records before (organizations|users|events|registrations): %s\n' "$counts_before"

if [[ "$identity" == *'0012_shared_event_release' ]]; then
  umask 077
  mkdir -p .env.runtime/backups
  backup=".env.runtime/backups/eventcheckin-before-0013-$(date -u +%Y%m%dT%H%M%SZ).dump"
  "${dc[@]}" exec -T db pg_dump -U eventcheckin -d eventcheckin -Fc --no-owner --no-acl > "$backup"
  if [[ ! -s "$backup" ]]; then
    echo 'Database backup is empty; refusing migration.' >&2
    exit 1
  fi
  printf 'Restricted database backup: %s\n' "$backup"
fi

# The API image also supplies the migration and background worker code.
"${dc[@]}" build api web
"${dc[@]}" --profile tools run --rm --no-deps migrate
"${dc[@]}" up -d --no-build --wait --wait-timeout 120 \
  api web worker dispatcher https-proxy
for service in db redis object-storage mailpit api web worker dispatcher https-proxy; do
  container="$("${dc[@]}" ps -q "$service")"
  if [[ -z "$container" ]] || [[ "$(docker inspect -f '{{.State.Running}}' "$container")" != true ]]; then
    printf 'Required local service is not running: %s\n' "$service" >&2
    exit 1
  fi
  printf '%s: running\n' "$service"
done
"${dc[@]}" exec -T --user 10001 api python -c 'import app.tenancy.privacy_notices'
"$root/ops/local-browser-check.sh"

version="$("${dc[@]}" exec -T db psql -X -v ON_ERROR_STOP=1 -U eventcheckin -d eventcheckin -At \
  -c 'SELECT version_num FROM alembic_version')"
if [[ "$version" != 0013_privacy_notice_workflow ]]; then
  printf 'Unexpected migration after startup: %s\n' "$version" >&2
  exit 1
fi
printf 'Migration: %s\n' "$version"

counts_after="$("${dc[@]}" exec -T db psql -X -v ON_ERROR_STOP=1 -U eventcheckin -d eventcheckin -At \
  -c "SELECT (SELECT count(*) FROM tenants) || '|' || (SELECT count(*) FROM users) || '|' || (SELECT count(*) FROM events) || '|' || (SELECT count(*) FROM registrations)")"
printf 'Records after  (organizations|users|events|registrations): %s\n' "$counts_after"
if [[ "$counts_after" != "$counts_before" ]]; then
  echo 'Record counts changed during preparation; investigate before manual testing.' >&2
  exit 1
fi

host=platform.local.example.test
base="https://$host:8443"
request=(curl --insecure --silent --show-error --fail --max-time 10 --resolve "$host:8443:127.0.0.1")
module="$(mktemp)"
trap 'rm -f "$module"' EXIT
if ! "${request[@]}" --output "$module" "$base/src/product/PrivacyNotices.tsx" || \
   ! grep -q 'Record approval' "$module"; then
  echo 'Updated platform privacy-notice module is not served through local HTTPS.' >&2
  exit 1
fi
if ! "${request[@]}" --output "$module" "$base/src/features/event-critical.tsx" || \
   ! grep -q 'appropriate authority and lawful basis' "$module"; then
  echo 'Updated organizer import module is not served through local HTTPS.' >&2
  exit 1
fi
printf 'Privacy-notice screen: served through HTTPS\n'
printf 'Organizer bulk import: served through HTTPS\n'
printf 'Platform URL: %s/platform-console.html#privacy\n' "$base"
printf 'Organizer URL: %s/workspace.html#participants\n' "$base"
