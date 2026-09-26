#!/usr/bin/env bash
# Contributor self-check for the qatar_airways mirror in a running container.
#
#   scripts_dev/container_check.sh <container> [host-site-port] [host-control-port]
#
# Verifies: the site is alive on its port, /_health is green, /reset restores
# the instance DB byte-identical to the seed (immediately and after a
# container restart), and the heavy surfaces render 200.
set -euo pipefail

CONTAINER="${1:?usage: container_check.sh <container> [site-port] [control-port]}"
SITE_PORT="${2:-43089}"
CTRL_PORT="${3:-44089}"
SITE=qatar_airways
: "${WEBSYN_CONTROL_TOKEN:?WEBSYN_CONTROL_TOKEN must be exported (never printed)}"
AUTH="Authorization: Bearer ${WEBSYN_CONTROL_TOKEN}"

echo "== health =="
curl -s -H "$AUTH" "http://127.0.0.1:${CTRL_PORT}/health" | python3 -c "
import json, sys
d = json.load(sys.stdin)
site = d.get('sites', {}).get('${SITE}')
assert site and site.get('alive'), site
print('${SITE}: alive, pid', site.get('pid'))
"

echo "== site renders =="
for path in "/" "/en/destinations.html" "/en/offers.html" "/en/our-fleet.html" \
           "/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&cabin=Economy" \
           "/en/flight-status.html?mode=number&number=QR004&date=2026-09-24" \
           "/en/Privilege-Club/login.html"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${SITE_PORT}${path}")
  echo "  ${code} ${path}"
  [ "$code" = "200" ]
done

echo "== byte-identical reset =="
seed_md5=$(docker exec "${CONTAINER}" md5sum "/opt/WebSyn/${SITE}/instance_seed/${SITE}.db" | awk '{print $1}')
curl -s -X POST -H "$AUTH" "http://127.0.0.1:${CTRL_PORT}/reset/${SITE}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('ready'), d
print('reset ready:', d)
"
inst_md5=$(docker exec "${CONTAINER}" md5sum "/opt/WebSyn/${SITE}/instance/${SITE}.db" | awk '{print $1}')
echo "  seed=${seed_md5} instance=${inst_md5}"
[ "${seed_md5}" = "${inst_md5}" ]

echo "== byte-identical after container restart =="
docker restart "${CONTAINER}" >/dev/null
for _ in $(seq 1 30); do
  if curl -s -o /dev/null "http://127.0.0.1:${SITE_PORT}/_health"; then break; fi
  sleep 2
done
inst_md5_2=$(docker exec "${CONTAINER}" md5sum "/opt/WebSyn/${SITE}/instance/${SITE}.db" | awk '{print $1}')
echo "  instance-after-restart=${inst_md5_2}"
[ "${seed_md5}" = "${inst_md5_2}" ]

echo "ALL CHECKS PASSED"
