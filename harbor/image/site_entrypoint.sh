#!/bin/bash
# WebHarbor-in-Harbor per-website container entrypoint. Runs as root (PID 1).
#
# Responsibilities, in order:
#   1. Reset the site database to the frozen seed (instance_seed -> instance).
#   2. Snapshot the pristine seed copy to /var/lib/webharbor/initial.db (root-only);
#      tests/test.sh uses it as the verifier's --initial_db.
#   3. Prepare agent-writable directories and hand /logs/agent to the agent user.
#   4. Start the site with the access-log middleware (root-owned evidence log).
#
# The agent user never gets read access to anything created here.
set -euo pipefail

SITE="${WH_SITE:?WH_SITE is required}"
PORT="${WH_PORT:?WH_PORT is required}"
DB_NAME="${WH_DB_NAME:?WH_DB_NAME is required}"
SITE_DIR="/opt/WebSyn/${SITE}"
SEED_DIR="${SITE_DIR}/instance_seed"
INSTANCE_DIR="${SITE_DIR}/instance"
AGENT_USER="${WH_AGENT_USER:-ubuntu}"
HARNESS_DIR="/opt/webharbor-harness"

echo "[entrypoint] resetting ${SITE} database to seed"
rm -rf "${INSTANCE_DIR}"
cp -a "${SEED_DIR}" "${INSTANCE_DIR}"
chmod -R go-rwx "${INSTANCE_DIR}"

echo "[entrypoint] snapshotting pristine seed for the verifier"
mkdir -p /var/lib/webharbor
cp "${INSTANCE_DIR}/${DB_NAME}" /var/lib/webharbor/initial.db
chmod 600 /var/lib/webharbor/initial.db

echo "[entrypoint] preparing agent-writable directories"
mkdir -p /logs/agent /logs/verifier /workspace /state /tmp/agent
rm -f /var/log/site_access.jsonl
touch /var/log/site_access.jsonl
chmod 600 /var/log/site_access.jsonl
chown -R "${AGENT_USER}:${AGENT_USER}" /logs/agent /workspace /state /tmp/agent

if [ "${WH_SKIP_AGENT_CHROMIUM:-0}" = "1" ]; then
    # RL rollout mode: the env_server launches its own playwright chromium;
    # the shared CDP browser for the Harbor harnesses is not needed.
    echo "[entrypoint] WH_SKIP_AGENT_CHROMIUM=1: skipping shared chromium daemon"
else
    CHROME=$(echo /opt/pw-browsers/chromium-*/chrome-linux64/chrome)
    echo "[entrypoint] starting shared chromium daemon (CDP 9222) as ${AGENT_USER}"
    su -s /bin/bash "${AGENT_USER}" -c "nohup ${CHROME} --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --remote-debugging-port=9222 --user-data-dir=/state/browser-profile --no-first-run --no-default-browser-check about:blank > /state/chromium.log 2>&1 &"
fi

echo "[entrypoint] starting ${SITE} on port ${PORT}"
exec python3 "${HARNESS_DIR}/site_launcher.py" "${SITE}" "${PORT}"
