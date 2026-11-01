#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ ! -f config/collection_schedule.yaml ]]; then
  printf 'Missing config/collection_schedule.yaml. Copy and edit config/collection_schedule.yaml.example before starting.\n' >&2
  exit 1
fi

if [[ -n "${INVEST_BOT_PYTHON:-}" ]]; then
  readiness_python=$(command -v -- "$INVEST_BOT_PYTHON") || { printf 'Readiness failed: Python runtime not found.\n' >&2; exit 1; }
elif [[ -x .venv/bin/python ]]; then
  readiness_python="$PWD/.venv/bin/python"
else
  readiness_python=$(command -v python3) || { printf 'Readiness failed: Python runtime not found.\n' >&2; exit 1; }
fi
if readiness_confirmation=$("$readiness_python" -B scripts/service_readiness.py --check); then
  if [[ "$readiness_confirmation" != "invest-bot-readiness-check-v1" ]]; then
    printf 'Readiness failed: Python runtime verification failed.\n' >&2
    exit 1
  fi
else
  exit "$?"
fi

docker compose config --quiet
docker compose build
docker compose run --rm --no-deps scheduler python scripts/run_scheduled_collection.py --validate-config
"$readiness_python" -B scripts/service_readiness.py --restart
