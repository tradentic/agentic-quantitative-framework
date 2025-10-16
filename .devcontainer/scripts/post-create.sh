#!/usr/bin/env bash
# Devcontainer post-create: prepare pnpm non-interactively, optional deps, and CLIs.
# Ensures a valid PNPM_HOME so global installs don't fail.
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null || cd "$HERE/.." && pwd)"

log() { echo "[post-create] $*"; }

ensure_pnpm() {
  # Avoid Corepack interactive prompt when downloading pnpm
  export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
  # Prefer a predictable PNPM_HOME if not provided by the container
  export PNPM_HOME="${PNPM_HOME:-$HOME/.local/share/pnpm}"
  mkdir -p "$PNPM_HOME"
  case ":$PATH:" in
    *":$PNPM_HOME:"*) ;;
    *) export PATH="$PNPM_HOME:$PATH" ;;
  esac

  if ! command -v pnpm >/dev/null 2>&1; then
    if ! command -v corepack >/dev/null 2>&1; then
      log "ERROR: corepack not found. Install Node with Corepack enabled."
      exit 1
    fi
    corepack enable || true
    local WANT_PNPM
    WANT_PNPM="${PNPM_VERSION:-10.17.1}"
    log "Preparing pnpm@${WANT_PNPM} via corepack (non-interactive)..."
    corepack prepare "pnpm@${WANT_PNPM}" --activate
  fi

  # Make sure pnpm knows where to put global bins
  pnpm config set global-bin-dir "$PNPM_HOME" >/dev/null 2>&1 || true
}

log "Ensuring pnpm is available without prompts and PNPM_HOME is set..."
ensure_pnpm

if [[ -f "$ROOT/package.json" ]]; then
  log "Installing workspace deps with pnpm..."
  (cd "$ROOT" && pnpm install)
else
  log "No package.json yet — skipping pnpm install."
fi

log "Installing Supabase CLI..."
"$HERE/install-supabase-cli.sh"

log "Installing Prefect CLI..."
"$HERE/install-prefect-cli.sh"

log "Installing OpenAI Codex CLI..."
"$HERE/install-codex-cli.sh"

log "Installing Anthropic Claude Code CLI..."
"$HERE/install-claude-code-cli.sh"

log "post-create complete."
