#!/usr/bin/env bash
# Build webharbor-harbor-base:0.1, the image every per-site Harbor image starts from.
# Then run build_harness_base.sh to add the three agent harnesses (-> :0.2).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
OUTPUT_IMAGE="${1:-webharbor-harbor-base:0.1}"
CONTEXT="${REPO}/build/base-context"

rm -rf "${CONTEXT}"
mkdir -p "${CONTEXT}/guards"
cp "${HERE}/base.Dockerfile" "${CONTEXT}/Dockerfile"
cp "${REPO}/../requirements.lock" \
   "${HERE}/patch-browser-use-cdp.py" \
   "${HERE}/site_entrypoint.sh" \
   "${HERE}/site_launcher.py" \
   "${HERE}/access_log.py" \
   "${REPO}/harness/browseruse_gui.py" \
   "${REPO}/harness/opencode_capture.py" \
   "${CONTEXT}/"
cp "${HERE}/guards/curl-guard.py" "${HERE}/guards/browser-use-guard.py" "${CONTEXT}/guards/"

docker build -t "${OUTPUT_IMAGE}" -f "${CONTEXT}/Dockerfile" "${CONTEXT}"
echo "built ${OUTPUT_IMAGE}"
