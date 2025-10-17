#!/usr/bin/env bash
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

require_command() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "[verify] Required command not found: ${cmd}" >&2
    exit 1
  fi
}

require_command docker
require_command prefect

server_container="${PREFECT_SERVER_CONTAINER_NAME:-prefect-server-dev}"
work_pool="${PREFECT_WORK_POOL_NAME:-my-docker-pool}"
expected_ui_path="${PREFECT_SERVER_UI_API_URL:-/api}"
expected_cli_api="${PREFECT_API_URL:-http://127.0.0.1:4200/api}"

check_container_running() {
  local name="$1"
  if ! docker ps --filter "name=^/${name}$" --format '{{.Names}}' | grep -Fxq "${name}"; then
    echo "[verify] Container '${name}' is not running." >&2
    exit 1
  fi
}

extract_container_env() {
  local name="$1"
  local var="$2"
  docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${name}" 2>/dev/null | awk -F'=' -v key="${var}" '$1==key {print $2}'
}

check_server_ui_path() {
  local actual
  actual="$(extract_container_env "${server_container}" "PREFECT_SERVER_UI_API_URL")"
  if [[ -z "${actual}" ]]; then
    echo "[verify] PREFECT_SERVER_UI_API_URL not set on '${server_container}'." >&2
    exit 1
  fi
  if [[ "${actual}" != "${expected_ui_path}" ]]; then
    echo "[verify] PREFECT_SERVER_UI_API_URL='${actual}' (expected '${expected_ui_path}')." >&2
    exit 1
  fi
  echo "[verify] Prefect server UI API path verified (${actual})."
}

check_cli_profile() {
  local actual
  if ! actual="$(prefect config view --json 2>/dev/null | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("PREFECT_API_URL",""))' 2>/dev/null)"; then
    echo "[verify] Failed to inspect Prefect CLI profile." >&2
    exit 1
  fi
  if [[ -z "${actual}" ]]; then
    echo "[verify] PREFECT_API_URL missing from CLI profile." >&2
    exit 1
  fi
  if [[ "${actual}" != "${expected_cli_api}" ]]; then
    echo "[verify] CLI PREFECT_API_URL='${actual}' (expected '${expected_cli_api}')." >&2
    exit 1
  fi
  echo "[verify] Prefect CLI API URL verified (${actual})."
}

check_prefect_flow_ls() {
  if prefect flow ls >/dev/null 2>&1; then
    echo "[verify] prefect flow ls succeeded."
  else
    echo "[verify] prefect flow ls failed." >&2
    exit 1
  fi
}

check_prefect_worker_ls() {
  local worker_json
  local worker_count
  if ! worker_json="$(prefect worker ls --json 2>/dev/null)"; then
    echo "[verify] prefect worker ls failed." >&2
    exit 1
  fi
  worker_count="$(python3 -c 'import json,sys; data=json.load(sys.stdin); print(sum(1 for w in data if w.get("name")))' <<<"${worker_json}" 2>/dev/null || echo 0)"
  if [[ "${worker_count}" -eq 0 ]]; then
    echo "[verify] No Prefect workers detected via prefect worker ls." >&2
    exit 1
  fi
  echo "[verify] Prefect worker ls reports ${worker_count} worker(s)."
}

check_work_pool() {
  if prefect work-pool inspect "${work_pool}" >/dev/null 2>&1; then
    echo "[verify] Work pool '${work_pool}' is available."
  else
    echo "[verify] Work pool '${work_pool}' is unavailable." >&2
    exit 1
  fi
}

check_container_running "${server_container}"
check_server_ui_path
check_cli_profile
check_prefect_flow_ls
check_prefect_worker_ls
check_work_pool

echo "[verify] Prefect local stack looks healthy."
