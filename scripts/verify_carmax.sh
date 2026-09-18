#!/usr/bin/env bash
# Build and verify all registered sites; reset CarMax byte-identically.
# Uses an owned container only. Override ports/tag with CARMAX_VERIFY_*.
set -euo pipefail
cd "$(dirname "$0")/.."

verify_container="wh-carmax-verify-$$"
verify_image="${CARMAX_VERIFY_IMAGE:-webharbor:carmax-check}"
verify_control="${CARMAX_VERIFY_CONTROL_PORT:-8201}"
verify_low="${CARMAX_VERIFY_BASE_PORT:-41000}"
verify_count=$(python3 -c 'import ast; m=ast.parse(open("control_server.py").read()); print(len(next(ast.literal_eval(n.value) for n in m.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SITES" for t in n.targets))))')
verify_high=$((verify_low + verify_count - 1))
verify_internal_high=$((40000 + verify_count - 1))
verify_started=0
cleanup() {
    if (( verify_started )); then docker stop "$verify_container" >/dev/null; fi
}
trap cleanup EXIT

./scripts/build.sh "$verify_image"
docker run -d --rm --name "$verify_container" \
    -p "127.0.0.1:$verify_control:8101" \
    -p "127.0.0.1:$verify_low-$verify_high:40000-$verify_internal_high" \
    "$verify_image"
verify_started=1
verify_ready=0
for ((attempt=0; attempt<120; attempt++)); do
    if curl -fsS --max-time 5 "http://localhost:$verify_control/health" >/dev/null 2>&1; then
        verify_ready=1
        break
    fi
    sleep 1
done
if (( ! verify_ready )); then docker logs "$verify_container"; exit 1; fi
for ((port=verify_low; port<=verify_high; port++)); do
    code=$(curl -sS --max-time 15 -o /dev/null -w '%{http_code}' "http://localhost:$port/")
    [[ "$code" == 200 ]] || { echo "Homepage $port returned $code"; exit 1; }
done
curl -fsS --max-time 30 -X POST "http://localhost:$verify_control/reset/carmax"
verify_hashes=$(docker exec "$verify_container" md5sum \
    /opt/WebSyn/carmax/instance/carmax.db /opt/WebSyn/carmax/instance_seed/carmax.db)
[[ $(awk '{print $1}' <<< "$verify_hashes" | sort -u | wc -l) -eq 1 ]]
echo "PASS: $verify_count homepages, healthy control plane, byte-identical CarMax reset."
