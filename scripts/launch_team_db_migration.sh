#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${TMUX:-}" ]]; then
  echo "This launcher must be run from an attached tmux OMX CLI session." >&2
  echo "Start with: omx --tmux" >&2
  exit 1
fi

TASK_TEXT="${1:-Finalize ERD, docker-compose draft, repository interfaces, and implementation-ready team plan for invest_bot DB migration}"

exec omx team 5:executor "$TASK_TEXT"
