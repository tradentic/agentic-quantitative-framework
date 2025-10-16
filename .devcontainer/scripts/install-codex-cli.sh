#!/usr/bin/env bash
# Install OpenAI Codex CLI strictly via pnpm global, non-interactive with Corepack.
# Ensures PNPM_HOME exists and is on PATH to avoid ERR_PNPM_NO_GLOBAL_BIN_DIR.
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

ensure_pnpm() {
  export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
  export PNPM_HOME="${PNPM_HOME:-$HOME/.local/share/pnpm}"
  mkdir -p "$PNPM_HOME"
  case ":$PATH:" in *":$PNPM_HOME:"*) ;; *) export PATH="$PNPM_HOME:$PATH" ;; esac

  if ! command -v pnpm >/dev/null 2>&1; then
    if ! command -v corepack >/dev/null 2>&1; then
      echo "[codex-cli] ERROR: corepack not found on PATH." >&2
      exit 1
    fi
    corepack enable || true
    local WANT_PNPM
    WANT_PNPM="${PNPM_VERSION:-10.17.1}"
    echo "[codex-cli] Preparing pnpm@${WANT_PNPM} via corepack (non-interactive)..."
    corepack prepare "pnpm@${WANT_PNPM}" --activate
  fi
  pnpm config set global-bin-dir "$PNPM_HOME" >/dev/null 2>&1 || true
}

# Already installed?
if command -v codex >/dev/null 2>&1; then
  echo "[codex-cli] Codex CLI already installed: $(codex --version || echo 'version unknown')"
  exit 0
fi

ensure_pnpm

echo "[codex-cli] Installing Codex CLI globally via pnpm..."
pnpm add -g @openai/codex

# Verify installation landed on PATH
if ! command -v codex >/dev/null 2>&1; then
  BIN_DIR="$(pnpm bin -g 2>/dev/null || echo "$PNPM_HOME")"
  echo "[codex-cli] ERROR: 'codex' not on PATH after pnpm global install." >&2
  if [[ -n "${BIN_DIR}" ]]; then
    echo "[codex-cli] pnpm global bin: ${BIN_DIR}" >&2
    echo "[codex-cli] Add it to PATH if necessary (e.g., export PATH=\"${BIN_DIR}:$PATH\")." >&2
  fi
  exit 1
fi

echo "[codex-cli] Installed successfully: $(codex --version || echo 'ok')"
