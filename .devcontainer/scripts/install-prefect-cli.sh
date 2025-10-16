#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-false}" == "true" ]]; then
  set -x
fi

install_packages() {
  local packages=(python3 python3-venv python3-pip pipx jq curl)
  local missing=()
  for pkg in "${packages[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      missing+=("$pkg")
    fi
  done

  if ((${#missing[@]} > 0)); then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing[@]}"
    sudo rm -rf /var/lib/apt/lists/*
  fi
}

fetch_latest_version() {
  curl -fsSL https://pypi.org/pypi/prefect/json | jq -r '.info.version'
}

install_prefect() {
  local resolved_version="$1"
  local requested_version="$2"
  local package="prefect"

  if [[ "$requested_version" != "latest" ]]; then
    local pinned="$requested_version"
    if [[ "$pinned" == v* ]]; then
      pinned="${pinned#v}"
    fi
    package="prefect==${pinned}"
  elif [[ -n "$resolved_version" ]]; then
    package="prefect==${resolved_version}"
  fi

  if ! command -v pipx >/dev/null 2>&1; then
    echo "[install-prefect-cli] pipx is required but not found after package installation" >&2
    exit 1
  fi

  # Ensure pipx bin dir is on PATH for the current session
  local pipx_bin
  pipx_bin="$(pipx environment --value BIN_DIR 2>/dev/null || true)"
  if [[ -n "$pipx_bin" ]]; then
    case ":$PATH:" in
      *":$pipx_bin:"*) ;;
      *) export PATH="$pipx_bin:$PATH" ;;
    esac
  fi

  pipx ensurepath >/dev/null 2>&1 || true

  pipx install --force "$package"
}

main() {
  install_packages

  local requested_version
  requested_version="${PREFECT_VERSION:-latest}"

  local resolved_version=""
  if [[ "$requested_version" == "latest" ]]; then
    resolved_version="$(fetch_latest_version)"
    echo "[install-prefect-cli] Latest Prefect release on PyPI: ${resolved_version}"
  fi

  install_prefect "$resolved_version" "$requested_version"

  if command -v prefect >/dev/null 2>&1; then
    echo -n "[install-prefect-cli] Installed Prefect CLI version: "
    prefect version --short 2>/dev/null || prefect --version || prefect version
  else
    echo "[install-prefect-cli] Prefect CLI installation failed" >&2
    exit 1
  fi
}

main "$@"
