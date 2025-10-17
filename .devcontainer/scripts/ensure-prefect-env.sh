#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <env-file> [KEY=VALUE ...]" >&2
  exit 1
fi

env_file=$1
shift

dirname "${env_file}" >/dev/null 2>&1 || true

mkdir -p "$(dirname "${env_file}")"

if [[ ! -f "${env_file}" ]]; then
  : >"${env_file}"
fi

if [[ $# -eq 0 ]]; then
  exit 0
fi

# Ensure the env file ends with a newline before appending
if [[ -s "${env_file}" ]] && [[ $(tail -c 1 "${env_file}" 2>/dev/null || printf '\n') != $'\n' ]]; then
  echo >>"${env_file}"
fi

for kv in "$@"; do
  key="${kv%%=*}"
  value="${kv#*=}"

  if [[ -z "${key}" ]]; then
    continue
  fi

  if grep -E "^${key}=" "${env_file}" >/dev/null 2>&1; then
    continue
  fi

  echo "${key}=${value}" >>"${env_file}"
done
