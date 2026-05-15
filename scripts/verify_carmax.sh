#!/usr/bin/env bash
# Phase 1.9 — Docker container verification for the carmax mirror.
# Runs build + run + reset + md5sum + cleanup.
#
# Usage:  bash scripts/verify_carmax.sh
set -uo pipefail

cd "$(dirname "$0")/.."

CONTAINER=wh-test
PORT_CONTROL=8201
PORT_RANGE_LOW=41000
PORT_RANGE_HIGH=41015
SITE=carmax
SITE_PORT=41015

cleanup() {
    docker stop "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo ""
echo "============================================================"
echo " Phase 1.9 — Docker verification for site: $SITE"
echo "============================================================"

# ---- Step 1: clean stale container ----
echo ""
echo "[1/6] Stop any stale test container..."
docker stop "$CONTAINER" >/dev/null 2>&1 || true

# ---- Step 2: build image ----
echo ""
echo "[2/6] Build webharbor:dev (first time ~3 min, warm cache ~30 s)..."
bash scripts/build.sh webharbor:dev || { echo "BUILD FAILED"; exit 1; }

# ---- Step 3: run container on alt ports ----
echo ""
echo "[3/6] Run container on alt ports ($PORT_CONTROL + $PORT_RANGE_LOW-$PORT_RANGE_HIGH)..."
docker run -d --rm --name "$CONTAINER" \
    -p "$PORT_CONTROL:8101" \
    -p "$PORT_RANGE_LOW-$PORT_RANGE_HIGH:40000-40015" \
    webharbor:dev >/dev/null \
    || { echo "DOCKER RUN FAILED"; exit 1; }

echo "    container started. waiting 35s for all 16 sites to boot..."
sleep 35

# ---- Step 4: health check ----
echo ""
echo "[4/6] Control plane health + HTTP 200 sweep:"
curl -s "http://localhost:$PORT_CONTROL/health" \
    | python -m json.tool 2>/dev/null \
    | head -50 || echo "    (control plane not responding — see docker logs $CONTAINER)"

echo ""
echo "    Per-site HTTP status:"
for p in $(seq $PORT_RANGE_LOW $PORT_RANGE_HIGH); do
    code=$(curl -so /dev/null -w "%{http_code}" "http://localhost:$p/" || echo "ERR")
    printf "      :%d  %s\n" "$p" "$code"
done

# ---- Step 5: byte-identical reset ----
echo ""
echo "[5/6] /reset/$SITE  (the strict invariant)..."
RESET_RESP=$(curl -sX POST "http://localhost:$PORT_CONTROL/reset/$SITE")
echo "    reset response: $RESET_RESP"

echo ""
echo "    md5sum (the two values MUST match):"
# MSYS_NO_PATHCONV=1 disables Git Bash's path translation on Windows
# (otherwise /opt/WebSyn becomes C:/Program Files/Git/opt/WebSyn).
MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" md5sum \
    "/opt/WebSyn/$SITE/instance/$SITE.db" \
    "/opt/WebSyn/$SITE/instance_seed/$SITE.db"

# ---- Step 6: result ----
echo ""
echo "[6/6] Verification done."
echo ""
echo "============================================================"
echo " If both md5sums above are identical -> Phase 1 PASSED ✅"
echo " If they differ -> seed function isn't idempotent, see"
echo "   seed-database skill for diagnosis."
echo "============================================================"
