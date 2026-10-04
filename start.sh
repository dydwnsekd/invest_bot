#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ ! -f config/collection_schedule.yaml ]]; then
  printf 'Missing config/collection_schedule.yaml. Copy and edit config/collection_schedule.yaml.example before starting.\n' >&2
  exit 1
fi

docker compose up -d
