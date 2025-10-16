#!/usr/bin/env bash
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

supabase_ready=false

if command -v supabase >/dev/null 2>&1; then
  echo "[post-start] Checking Supabase local stack status..."
  status_file="$(mktemp)"
  if supabase status >"${status_file}" 2>&1; then
    if grep -qi 'api url' "${status_file}"; then
      echo "[post-start] Supabase services already running."
      supabase_ready=true
    else
      echo "[post-start] Supabase services not running; starting now..."
      supabase start
      supabase_ready=true
    fi
  else
    echo "[post-start] Supabase status check failed; attempting to start services..." >&2
    supabase start
    supabase_ready=true
  fi
  rm -f "${status_file}"
else
  echo "[post-start] Supabase CLI not found on PATH; skipping Supabase startup." >&2
fi

# Directly call the env sync script (no package.json required)
SYNC_ENV_SCRIPT="${REPO_ROOT}/scripts/infra/sync-supabase-env.mjs"

if [[ "${supabase_ready}" == "true" ]]; then
  if [[ -x "${SYNC_ENV_SCRIPT}" ]]; then
    echo "[post-start] Syncing .env.local from Supabase status..."
    "${SYNC_ENV_SCRIPT}" --out ".env.local" || true
  else
    echo "[post-start] Env sync script not found/executable: ${SYNC_ENV_SCRIPT}" >&2
  fi
else
  echo "[post-start] Skipping env sync because Supabase services are not available." >&2
fi
