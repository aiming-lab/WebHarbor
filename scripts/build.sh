#!/usr/bin/env bash
# Build the webharbor docker image. Pulls assets from HF first if missing.
#
# Usage: ./scripts/build.sh [TAG]   (default tag: webharbor:dev)
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="${1:-webharbor:dev}"

# Fast probe — if any site is missing instance_seed/, run fetch_assets.
need_fetch=0
for site in sites/*/; do
    if [[ -f "${site}.requires-images" ]] && { [[ ! -d "${site}static/images" ]] || [[ -z $(ls -A "${site}static/images" 2>/dev/null) ]]; }; then
        need_fetch=1
        break
    fi
    if [[ -f "${site}.requires-external-cache" ]] && { [[ ! -d "${site}static/external_cache" ]] || [[ -z $(ls -A "${site}static/external_cache" 2>/dev/null) ]]; }; then
        need_fetch=1
        break
    fi
    if [[ -f "${site}.build-generated-seed" ]]; then
        continue
    fi
    if [[ ! -d "${site}instance_seed" ]]; then
        need_fetch=1
        break
    fi
done

if (( need_fetch )); then
    echo "[build] missing assets, fetching from HF..."
    ./scripts/fetch_assets.sh
fi

./scripts/check_assets.sh

echo "[build] docker build -t $TAG ."
docker build -t "$TAG" .
echo "[build] $TAG ready ($(docker images "$TAG" --format '{{.Size}}'))"
