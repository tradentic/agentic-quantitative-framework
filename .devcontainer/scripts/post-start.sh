#!/usr/bin/env bash
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

wait_for_docker_daemon() {
  local max_attempts="${1:-30}"
  local sleep_seconds="${2:-2}"
  local attempt

  for attempt in $(seq 1 "${max_attempts}"); do
    if docker info >/dev/null 2>&1; then
      return 0
    fi

    if [[ "${attempt}" -eq 1 ]]; then
      echo "[post-start] Waiting for Docker daemon to become ready..." >&2
    fi

    sleep "${sleep_seconds}"
  done

  return 1
}

detect_prefect_version() {
  local prefect_config
  prefect_config="${REPO_ROOT}/prefect.yaml"
  if [[ -f "${prefect_config}" ]]; then
    python3 - "$prefect_config" <<'PY' 2>/dev/null
import sys
from pathlib import Path

path = Path(sys.argv[1])
version_line = None
for line in path.read_text().splitlines():
    striped = line.strip()
    if not striped or striped.startswith("#"):
        continue
    if striped.lower().startswith("prefect-version"):
        version_line = striped.split(":", 1)[1].strip().strip('"\'"'"')
        break

if version_line:
    print(version_line)
PY
  fi
}

supabase_ready=false
docker_cli_present=false
docker_available=false

if command -v docker >/dev/null 2>&1; then
  docker_cli_present=true
  if wait_for_docker_daemon 40 2; then
    docker_available=true
  else
    echo "[post-start] Docker daemon did not become ready; Docker-dependent services will be skipped." >&2
  fi
fi

if command -v supabase >/dev/null 2>&1; then
  if [[ "${docker_available}" == "true" ]]; then
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
    echo "[post-start] Docker unavailable; skipping Supabase startup." >&2
  fi
else
  echo "[post-start] Supabase CLI not found on PATH; skipping Supabase startup." >&2
fi

prefect_ready=false
prefect_cli_available=false
prefect_api_host_port="${PREFECT_API_HOST_PORT:-4200}"
prefect_base_url="http://127.0.0.1:${prefect_api_host_port}"
prefect_api_default="${prefect_base_url}/api"
prefect_health_urls=("${prefect_api_default}/health" "${prefect_base_url}/health")
prefect_ui_api_path="/api"
prefect_pool_name="${PREFECT_WORK_POOL_NAME:-my-docker-pool}"
prefect_worker_type="${PREFECT_WORKER_TYPE:-docker}"
prefect_docker_network="${PREFECT_DOCKER_NETWORK:-prefect-dev}"
prefect_server_container="${PREFECT_SERVER_CONTAINER_NAME:-prefect-server-dev}"
prefect_worker_container="${PREFECT_WORKER_CONTAINER_NAME:-prefect-worker-${prefect_pool_name}}"

prefect_version_detected="$(detect_prefect_version || true)"
prefect_version_detected="${prefect_version_detected//[$'\r\n']}"
prefect_version_effective="${PREFECT_VERSION:-${prefect_version_detected:-2.14.0}}"
prefect_version_effective="${prefect_version_effective#v}"
prefect_docker_default_image="prefecthq/prefect:${prefect_version_effective}-python3.11"
prefect_docker_image="${PREFECT_DOCKER_IMAGE:-${prefect_docker_default_image}}"

if [[ -n "${prefect_version_detected}" && -z "${PREFECT_VERSION:-}" ]]; then
  echo "[post-start] Prefect version detected from prefect.yaml: ${prefect_version_effective}"
elif [[ -n "${PREFECT_VERSION:-}" ]]; then
  echo "[post-start] Prefect version overridden via PREFECT_VERSION: ${prefect_version_effective}"
fi

if command -v prefect >/dev/null 2>&1; then
  prefect_cli_available=true
else
  echo "[post-start] Prefect CLI not found on PATH; skipping Prefect configuration." >&2
fi

if [[ "${docker_cli_present}" == "true" ]]; then
  if [[ "${docker_available}" == "true" ]]; then
    echo "[post-start] Prefect Docker image target: '${prefect_docker_image}'."
    if ! docker image inspect "${prefect_docker_image}" >/dev/null 2>&1; then
      echo "[post-start] Pulling Prefect base image '${prefect_docker_image}' for worker + job runs..."
      if ! docker pull "${prefect_docker_image}" >/dev/null 2>&1; then
        echo "[post-start] Failed to pull image '${prefect_docker_image}'." >&2
      fi
    fi
  else
    echo "[post-start] Docker is installed but not available (docker info failed)." >&2
  fi
else
  echo "[post-start] Docker CLI not found; cannot manage Prefect server/worker containers." >&2
fi

if [[ "${docker_available}" == "true" && "${prefect_cli_available}" == "true" ]]; then
  if ! docker network inspect "${prefect_docker_network}" >/dev/null 2>&1; then
    echo "[post-start] Creating Docker network '${prefect_docker_network}' for Prefect services..."
    docker network create "${prefect_docker_network}" >/dev/null 2>&1 || echo "[post-start] Failed to create network '${prefect_docker_network}'." >&2
  fi

  if docker ps --filter "name=^/${prefect_server_container}$" --format '{{.Names}}' | grep -Fxq "${prefect_server_container}"; then
    echo "[post-start] Prefect server container '${prefect_server_container}' already running."
  else
    echo "[post-start] Starting Prefect server container '${prefect_server_container}'..."
    docker run \
      --detach \
      --rm \
      --name "${prefect_server_container}" \
      --network "${prefect_docker_network}" \
      --publish "${prefect_api_host_port}:4200" \
      "${prefect_docker_image}" \
      prefect server start --host 0.0.0.0 --port 4200 >/dev/null 2>&1 || {
        echo "[post-start] Failed to launch Prefect server container." >&2
      }
  fi

  prefect_health_endpoint=""
  for attempt in {1..40}; do
    for health_candidate in "${prefect_health_urls[@]}"; do
      if curl -fsS --max-time 2 "${health_candidate}" >/dev/null 2>&1; then
        prefect_ready=true
        prefect_health_endpoint="${health_candidate}"
        break 2
      fi
    done
    sleep 3
  done

  if [[ "${prefect_ready}" == "true" ]]; then
    if [[ -n "${prefect_health_endpoint}" ]]; then
      echo "[post-start] Prefect server is ready on ${prefect_base_url} (health: ${prefect_health_endpoint})."
    else
      echo "[post-start] Prefect server is ready on ${prefect_base_url}."
    fi
  else
    echo "[post-start] Prefect server container did not become healthy; logs:" >&2
    docker logs "${prefect_server_container}" 2>&1 || true
  fi
fi

# Once Prefect is healthy, ensure deployments and workers are ready
if [[ "${prefect_ready}" == "true" && "${prefect_cli_available}" == "true" ]]; then
  export PREFECT_API_URL="${prefect_api_default}"
  export PREFECT_UI_API_URL="${prefect_ui_api_path}"

  PREFECT_API_URL="${prefect_api_default}" prefect config set "PREFECT_API_URL=${prefect_api_default}" >/dev/null 2>&1 || true
  PREFECT_API_URL="${prefect_api_default}" prefect config set "PREFECT_UI_API_URL=${prefect_ui_api_path}" >/dev/null 2>&1 || true
  PREFECT_API_URL="${prefect_api_default}" prefect config set "PREFECT_SERVER_ALLOW_EPHEMERAL_MODE=false" >/dev/null 2>&1 || true

  echo "[post-start] Ensuring Prefect work pool '${prefect_pool_name}' exists (${prefect_worker_type})."
  if ! prefect work-pool inspect "${prefect_pool_name}" >/dev/null 2>&1; then
    if prefect work-pool create "${prefect_pool_name}" --type "${prefect_worker_type}" >/dev/null 2>&1; then
      echo "[post-start] Created work pool '${prefect_pool_name}'."
    else
      echo "[post-start] Failed to create work pool '${prefect_pool_name}'." >&2
    fi
  fi

  echo "[post-start] Deploying Prefect flows from prefect.yaml (Docker work pool)..."
  if PREFECT_CLI_PROMPT=false prefect deploy --all >/dev/null 2>&1; then
    echo "[post-start] Prefect deployments are up to date."
  else
    echo "[post-start] Failed to deploy Prefect flows." >&2
  fi

  if [[ "${docker_available}" == "true" ]]; then
    if docker ps --filter "name=^/${prefect_worker_container}$" --format '{{.Names}}' | grep -Fxq "${prefect_worker_container}"; then
      echo "[post-start] Prefect worker container '${prefect_worker_container}' already running."
    else
      echo "[post-start] Launching Prefect worker container '${prefect_worker_container}'."
      docker run \
        --detach \
        --rm \
        --name "${prefect_worker_container}" \
        --network "${prefect_docker_network}" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -e PREFECT_API_URL="http://${prefect_server_container}:4200/api" \
        -e PREFECT_UI_API_URL="${prefect_ui_api_path}" \
        "${prefect_docker_image}" \
        prefect worker start --pool "${prefect_pool_name}" --type "${prefect_worker_type}" >/dev/null 2>&1 || {
          echo "[post-start] Failed to launch Prefect worker container." >&2
          docker logs "${prefect_worker_container}" 2>&1 || true
        }
    fi
  else
    echo "[post-start] Docker unavailable; skipping Prefect worker container startup." >&2
  fi
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
