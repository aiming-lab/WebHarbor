#!/bin/bash
# WebSyn startup: launch all 12 mirror sites, then exec the original CMD.
# This preserves the base image's browser env server (port 8100) as PID 1.
set -e

SITES=(allrecipes amazon apple arxiv bbc_news booking github
       google_flights google_map google_search huggingface wolfram_alpha
       cambridge_dictionary coursera espn phet_simulations)
BASE_PORT=40000
PID_DIR=/tmp/websyn_pids
mkdir -p "$PID_DIR"
rm -f "$PID_DIR"/*.pid

echo "[WebSyn] Resetting all databases to seed state..."
for d in "${SITES[@]}"; do
    rm -rf "/opt/WebSyn/$d/instance"
    cp -a "/opt/WebSyn/$d/instance_seed" "/opt/WebSyn/$d/instance"
done

echo "[WebSyn] Starting 16 sites on ports ${BASE_PORT}-$((BASE_PORT + 15))..."
for i in "${!SITES[@]}"; do
    site="${SITES[$i]}"
    port=$((BASE_PORT + i))
    # Spawn via /opt/site_runner.py supervisor so SIGTERM works.
    # See site_runner.py for the rationale (Werkzeug ignores SIGTERM).
    exec python3 /opt/site_runner.py "$site" "$port" \
        > "/tmp/websyn_${site}.log" 2>&1 &
    echo "$!" > "$PID_DIR/${site}.pid"
    echo "  $site -> port $port (PID $!)"
done


# Wait for all sites to bind — retry up to 30 seconds
echo "[WebSyn] Waiting for sites to become ready..."
max_wait=30
interval=2
elapsed=0
while [ $elapsed -lt $max_wait ]; do
    sleep $interval
    elapsed=$((elapsed + interval))
    ready=0
    for i in "${!SITES[@]}"; do
        port=$((BASE_PORT + i))
        if python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:$port/', timeout=2)
    exit(0 if r.status < 500 else 1)
except Exception: exit(1)
" 2>/dev/null; then
            ready=$((ready + 1))
        fi
    done
    echo "  [${elapsed}/${max_wait}s] ${ready}/16 sites ready"
    if [ $ready -eq 16 ]; then
        break
    fi
done

# Final status report
echo "[WebSyn] Site status:"
for i in "${!SITES[@]}"; do
    site="${SITES[$i]}"
    port=$((BASE_PORT + i))
    if python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:$port/', timeout=2)
    exit(0 if r.status < 500 else 1)
except Exception: exit(1)
" 2>/dev/null; then
        echo "  [OK] $site :$port"
    else
        echo "  [!!] $site :$port FAILED -- check /tmp/websyn_${site}.log"
    fi
done

echo "[WebSyn] Starting control server on :8101 (PID 1)..."

# Control server becomes PID 1 — receives SIGTERM on `docker stop`,
# keeps the container alive as long as it's running. The 15 site
# subprocesses are managed via /tmp/websyn_pids/<site>.pid.
exec python3 /opt/control_server.py --port 8101
