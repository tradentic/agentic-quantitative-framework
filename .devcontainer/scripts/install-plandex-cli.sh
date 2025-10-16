#!/usr/bin/env bash
# Install Plandex CLI via official install script (curl pipeline).
# No npm/pnpm package for the CLI binary at this time.
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

# Already installed?
if command -v plandex >/dev/null 2>&1; then
  echo "[plandex-cli] Plandex already installed: $(plandex --version 2>/dev/null || echo 'version unknown')"
  exit 0
fi

# Require curl
if ! command -v curl >/dev/null 2>&1; then
  echo "[plandex-cli] ERROR: 'curl' is required to fetch the official installer." >&2
  exit 1
fi

# Install via official script
echo "[plandex-cli] Installing Plandex via official installer..."
curl -sL https://plandex.ai/install.sh | bash

# Verify installation landed on PATH
if ! command -v plandex >/dev/null 2>&1; then
  echo "[plandex-cli] ERROR: 'plandex' not on PATH after install. Add the installer’s output bin dir to PATH (e.g., $HOME/.local/bin)." >&2
  exit 1
fi

echo "[plandex-cli] Installed successfully: $(plandex --version 2>/dev/null || echo 'ok')"
