#!/usr/bin/env bash
# Dev mirror launcher for the instructure contribution (port 43072).
# Runs until killed; suitable for pueue / nohup supervision.
#
# Uses the site-local virtualenv (.venv). The shared agent_demo venv at the
# repository root is pruned by `uv sync` runs from other sessions (it lost its
# Flask install that way once), so the mirror must not depend on it.
set -euo pipefail
SITE_DIR="/data/zhaoyang-user-projects/websyn/WebHarbor/_wh_review_tools/orch/contribute/build/instructure/sites/instructure"
cd "$SITE_DIR"
if [[ ! -x "$SITE_DIR/.venv/bin/python" ]]; then
    uv venv "$SITE_DIR/.venv"
    uv pip install --python "$SITE_DIR/.venv/bin/python" -r "$SITE_DIR/requirements.txt"
fi
export INSTRUCTURE_DB_PATH="sqlite:///$SITE_DIR/instance/instructure.db"
exec "$SITE_DIR/.venv/bin/python" -c \
    "from app import app; app.run(host='0.0.0.0', port=43072, debug=False, use_reloader=False, threaded=True)"
