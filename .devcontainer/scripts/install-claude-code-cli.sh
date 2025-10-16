#!/usr/bin/env bash
# Install Anthropic Claude Code CLI strictly via pnpm global, non-interactive with Corepack.
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
      echo "[claude-code-cli] ERROR: corepack not found on PATH." >&2
      exit 1
    fi
    corepack enable || true
    local WANT_PNPM
    WANT_PNPM="${PNPM_VERSION:-10.17.1}"
    echo "[claude-code-cli] Preparing pnpm@${WANT_PNPM} via corepack (non-interactive)..."
    corepack prepare "pnpm@${WANT_PNPM}" --activate
  fi
  pnpm config set global-bin-dir "$PNPM_HOME" >/dev/null 2>&1 || true
}

# Already installed?
if command -v claude >/dev/null 2>&1; then
  echo "[claude-code-cli] Claude Code CLI already installed: $(claude --version || echo 'version unknown')"
  exit 0
fi

ensure_pnpm

echo "[claude-code-cli] Installing Claude Code CLI globally via pnpm..."
pnpm add -g @anthropic-ai/claude-code

# Verify installation landed on PATH
if ! command -v claude >/dev/null 2>&1; then
  BIN_DIR="$(pnpm bin -g 2>/dev/null || echo "$PNPM_HOME")"
  echo "[claude-code-cli] ERROR: 'claude' not on PATH after pnpm global install." >&2
  if [[ -n "${BIN_DIR}" ]]; then
    echo "[claude-code-cli] pnpm global bin: ${BIN_DIR}" >&2
    echo "[claude-code-cli] Add it to PATH if necessary (e.g., export PATH=\"${BIN_DIR}:$PATH\")." >&2
  fi
  exit 1
fi

echo "[claude-code-cli] Installed successfully: $(claude --version || echo 'ok')"
