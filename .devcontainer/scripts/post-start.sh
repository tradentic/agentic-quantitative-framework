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

prefect_ready=false
prefect_api_default="http://127.0.0.1:4200/api"
prefect_base_url="${prefect_api_default%/api}"
prefect_health_url="${prefect_api_default%/}/health"

if command -v prefect >/dev/null 2>&1; then
  echo "[post-start] Checking Prefect server health..."
  if curl -fsS --max-time 2 "${prefect_health_url}" >/dev/null 2>&1; then
    echo "[post-start] Prefect server already running."
    prefect_ready=true
  else
    echo "[post-start] Prefect server not running; starting in background..."
    prefect_log="$(mktemp -t prefect-start-XXXX.log)"
    if PREFECT_API_URL="${prefect_api_default}" prefect server start --background --host 0.0.0.0 --port 4200 >"${prefect_log}" 2>&1; then
      for attempt in {1..20}; do
        if curl -fsS --max-time 2 "${prefect_health_url}" >/dev/null 2>&1; then
          prefect_ready=true
          break
        fi
        sleep 3
      done
      if [[ "${prefect_ready}" == "true" ]]; then
        echo "[post-start] Prefect server is ready on ${prefect_base_url}."
        prefect config set "PREFECT_API_URL=${prefect_api_default}" >/dev/null 2>&1 || true
      else
        echo "[post-start] Prefect server did not become healthy; logs:" >&2
        cat "${prefect_log}" >&2 || true
      fi
    else
      echo "[post-start] Failed to launch Prefect server; logs:" >&2
      cat "${prefect_log}" >&2 || true
    fi
    rm -f "${prefect_log}"
  fi
else
  echo "[post-start] Prefect CLI not found on PATH; skipping Prefect startup." >&2
fi

# Directly call the env sync script (no package.json required)
if [[ "${supabase_ready}" == "true" ]]; then
  if [[ -x "${SCRIPT_DIR}/sync-supabase-env.mjs" ]]; then
    echo "[post-start] Syncing .env.local from Supabase status..."
    "${SCRIPT_DIR}/sync-supabase-env.mjs" --out ".env.local" || true
  else
    echo "[post-start] Env sync script not found/executable: ${SCRIPT_DIR}/sync-supabase-env.mjs" >&2
  fi
else
  echo "[post-start] Skipping env sync because Supabase services are not available." >&2
fi
