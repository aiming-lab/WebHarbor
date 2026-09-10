#!/usr/bin/env bash
# Verify every site has the runtime-required asset dirs.
#
# Hard requirement: instance_seed/ (every site MUST have a seed DB).
# Soft check (warn-only): static/images/, static/external_cache/.
# Some sites legitimately have no external cache (only google_search uses it
# at present); some may have no scraped images.
#
# Used by build.sh and as a CI gate.
set -euo pipefail
cd "$(dirname "$0")/.."

REQUIRED=(instance_seed)
OPTIONAL=(static/images static/external_cache)

missing=0
warnings=0
for site in sites/*/; do
    s=$(basename "$site")
    for sub in "${REQUIRED[@]}"; do
        if [[ -f "sites/$s/.build-generated-seed" && "$sub" == "instance_seed" ]]; then
            continue
        fi
        if [[ ! -d "sites/$s/$sub" ]] || [[ -z $(ls -A "sites/$s/$sub" 2>/dev/null) ]]; then
            echo "  MISSING (required): sites/$s/$sub"
            missing=$((missing + 1))
        fi
    done
    for sub in "${OPTIONAL[@]}"; do
        if { [[ -f "sites/$s/.requires-images" && "$sub" == "static/images" ]] || [[ -f "sites/$s/.requires-external-cache" && "$sub" == "static/external_cache" ]]; } && { [[ ! -d "sites/$s/$sub" ]] || [[ -z $(ls -A "sites/$s/$sub" 2>/dev/null) ]]; }; then
            echo "  MISSING (required): sites/$s/$sub"
            missing=$((missing + 1))
        elif [[ ! -d "sites/$s/$sub" ]] || [[ -z $(ls -A "sites/$s/$sub" 2>/dev/null) ]]; then
            warnings=$((warnings + 1))
        fi
    done
    if [[ -f "sites/$s/asset_inventory.json" ]]; then
        python3 scripts/check_asset_inventory.py "sites/$s"
    fi
done

if (( missing > 0 )); then
    echo "[check] $missing required asset dirs missing — run scripts/fetch_assets.sh"
    exit 1
fi
python3 scripts/check_seed_databases.py sites --allow-build-generated
echo "[check] all non-build-generated sites have one valid SQLite seed database ($warnings sites lack at least one optional asset dir — that's OK)"
