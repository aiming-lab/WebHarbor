#!/bin/bash
# Dev launcher for the chronicle_jobs mirror (contributor worktree).
# Usage: PORT=43066 ./run_dev.sh
set -e
cd "$(dirname "$0")"
PORT="${PORT:-43066}"
mkdir -p instance
exec env PORT="$PORT" ./venv/bin/python app.py
