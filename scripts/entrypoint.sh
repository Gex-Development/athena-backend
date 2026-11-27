#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "chill" ]]; then
    exec sleep infinity
fi

exec "$@"
