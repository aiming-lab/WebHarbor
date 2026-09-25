#!/bin/bash
# Local dev runner for the medicare_gov mirror (matches site_runner.py's
# production invocation). Prefers the local venv when present.
cd "$(dirname "$0")/.."
if [ -x "venv/bin/python" ]; then PY="venv/bin/python"; else PY="python3"; fi
PORT="${1:-4378}"
exec "$PY" -c "from app import app; app.run(host='0.0.0.0', port=$PORT, debug=False, use_reloader=False, threaded=True)"
