#!/usr/bin/env bash
# Install Aider CLI strictly via pipx (Python-based tool).
# No fallbacks to npm/pnpm/Homebrew.
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

# Already installed?
if command -v aider >/dev/null 2>&1; then
  echo "[aider-cli] Aider already installed: $(aider --version 2>/dev/null || echo 'version unknown')"
  exit 0
fi

# Require pipx (preferred for Python CLIs)
if ! command -v pipx >/dev/null 2>&1; then
  echo "[aider-cli] ERROR: pipx not found on PATH. Install pipx first (e.g., python3 -m pip install --user pipx && pipx ensurepath)." >&2
  exit 1
fi

# Install via pipx
echo "[aider-cli] Installing Aider via pipx..."
pipx install --upgrade aider-chat

# Verify installation landed on PATH
if ! command -v aider >/dev/null 2>&1; then
  echo "[aider-cli] ERROR: 'aider' not on PATH after pipx install." >&2
  echo "[aider-cli] Ensure pipx bin directory is on PATH (e.g., export PATH=\"$HOME/.local/bin:$PATH\")." >&2
  exit 1
fi

echo "[aider-cli] Installed successfully: $(aider --version 2>/dev/null || echo 'ok')"
