#!/usr/bin/env bash
# Install Block Goose CLI via official install script (curl pipeline).
# No npm/pnpm package for the CLI binary at this time.
set -euo pipefail
[[ "${DEBUG:-false}" == "true" ]] && set -x

# Already installed?
if command -v goose >/dev/null 2>&1; then
  echo "[goose-cli] Goose CLI already installed: $(goose --version 2>/dev/null || echo 'version unknown')"
  exit 0
fi

# Require curl
if ! command -v curl >/dev/null 2>&1; then
  echo "[goose-cli] ERROR: 'curl' is required to fetch the official installer." >&2
  exit 1
fi

# Install via official script (Linux/macOS/Windows Git Bash)
echo "[goose-cli] Installing Goose CLI via official installer..."
curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | bash

# Verify installation landed on PATH
if ! command -v goose >/dev/null 2>&1; then
  echo "[goose-cli] ERROR: 'goose' not on PATH after install. Add the installer’s output bin dir to PATH (e.g., $HOME/.local/bin)." >&2
  exit 1
fi

echo "[goose-cli] Installed successfully: $(goose --version 2>/dev/null || echo 'ok')"
