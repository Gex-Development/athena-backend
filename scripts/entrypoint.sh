#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "chill" ]]; then
    exec sleep infinity
fi

if [[ "${1:-}" == "uvicorn" ]]; then
    alembic upgrade head
fi

exec "$@"
