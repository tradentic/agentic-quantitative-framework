#!/usr/bin/env bash
# Devcontainer post-create hook for the Agentic Quantitative Framework.
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

log() {
  echo "[post-create] $*"
}

if command -v poetry >/dev/null 2>&1 && [[ -f "${REPO_ROOT}/pyproject.toml" ]]; then
  log "Installing Python dependencies via Poetry..."
  (cd "${REPO_ROOT}" && poetry install --no-root)
else
  log "Poetry not available or pyproject.toml missing; skipping Python install."
fi

DOCS_DIR="${REPO_ROOT}/docs"
if [[ -f "${DOCS_DIR}/package.json" ]]; then
  if command -v npm >/dev/null 2>&1; then
    log "Installing Docusaurus dependencies with npm..."
    (cd "${DOCS_DIR}" && npm install)
  else
    log "npm not found; skipping docs dependency installation."
  fi
fi

log "post-create complete."
