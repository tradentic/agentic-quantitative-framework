#!/usr/bin/env bash
# Install Google's Gemini CLI strictly via pnpm global, non-interactive with Corepack.
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
      echo "[gemini-cli] ERROR: corepack not found on PATH." >&2
      exit 1
    fi
    corepack enable || true
    local WANT_PNPM
    WANT_PNPM="${PNPM_VERSION:-10.17.1}"
    echo "[gemini-cli] Preparing pnpm@${WANT_PNPM} via corepack (non-interactive)..."
    corepack prepare "pnpm@${WANT_PNPM}" --activate
  fi
  pnpm config set global-bin-dir "$PNPM_HOME" >/dev/null 2>&1 || true
}

# Already installed?
if command -v gemini >/dev/null 2>&1; then
  echo "[gemini-cli] Gemini CLI already installed: $(gemini --version 2>/dev/null || echo 'version unknown')"
  exit 0
fi

ensure_pnpm

echo "[gemini-cli] Installing Gemini CLI globally via pnpm..."
pnpm add -g @google/gemini-cli

# Verify installation landed on PATH
if ! command -v gemini >/dev/null 2>&1; then
  BIN_DIR="$(pnpm bin -g 2>/dev/null || echo "$PNPM_HOME")"
  echo "[gemini-cli] ERROR: 'gemini' not on PATH after pnpm global install." >&2
  if [[ -n "${BIN_DIR}" ]]; then
    echo "[gemini-cli] pnpm global bin: ${BIN_DIR}" >&2
    echo "[gemini-cli] Add it to PATH if necessary (e.g., export PATH=\"${BIN_DIR}:$PATH\")." >&2
  fi
  exit 1
fi

echo "[gemini-cli] Installed successfully: $(gemini --version 2>/dev/null || echo 'ok')"
