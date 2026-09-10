#!/usr/bin/env bash
# Pull per-site asset tarballs from the Hugging Face dataset and extract
# them into sites/.
#
# The dataset stores assets as <site>.tar.gz (one tarball per site) to
# dodge the small-file tax that previously made `hf download` stall on
# 4000+ tiny image files. Each tarball extracts back to
# sites/<site>/{instance_seed,static/images,static/external_cache}.
#
# Usage:
#   ./scripts/fetch_assets.sh                 # fetch all sites at pinned rev
#   ./scripts/fetch_assets.sh google_search   # fetch one site only
#   ASSETS_REVISION=abc123 ./scripts/fetch_assets.sh   # override pin
#
# Requires:
#   - hf CLI  (pip install -U "huggingface_hub[cli]")
#   - (optional) HF auth if the dataset becomes gated: hf auth login  (or set HF_TOKEN env)
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=$(awk '/^repo:/ {print $2}' .assets-revision)
REVISION="${ASSETS_REVISION:-$(awk '/^revision:/ {print $2}' .assets-revision)}"
ONLY_SITE="${1:-}"
CACHE_DIR="sites/.cache/tarballs/$REVISION"

if ! command -v hf >/dev/null 2>&1; then
    echo "fetch_assets: 'hf' CLI not found. Install with: pip install -U \"huggingface_hub[cli]\"" >&2
    exit 1
fi

mkdir -p "$CACHE_DIR"
echo "[fetch] huggingface.co/datasets/$REPO @ $REVISION -> sites/"

if [[ -n "$ONLY_SITE" ]]; then
    INCLUDE="$ONLY_SITE.tar.gz"
    echo "[fetch] scope: $ONLY_SITE only"
else
    INCLUDE="*.tar.gz"
fi

hf download "$REPO" --repo-type dataset --revision "$REVISION" \
    --include "$INCLUDE" --local-dir "$CACHE_DIR"

shopt -s nullglob
if [[ -n "$ONLY_SITE" ]]; then
    TARBALLS=("$CACHE_DIR/$ONLY_SITE.tar.gz")
    if [[ ! -f "${TARBALLS[0]}" ]]; then
        echo "fetch_assets: expected archive for $ONLY_SITE" >&2
        exit 1
    fi
else
    TARBALLS=("$CACHE_DIR"/*.tar.gz)
    expected=0
    for site_dir in sites/*/; do
        [[ -d "$site_dir" ]] && expected=$((expected + 1))
    done
    if [[ ${#TARBALLS[@]} -ne $expected ]]; then
        echo "fetch_assets: expected $expected site archives at revision $REVISION, found ${#TARBALLS[@]}" >&2
        exit 1
    fi
fi
extracted=0
for tarball in "${TARBALLS[@]}"; do
    site=$(basename "$tarball" .tar.gz)
    if [[ -n "$ONLY_SITE" && "$site" != "$ONLY_SITE" ]]; then continue; fi
    python3 scripts/validate_asset_archive.py "$tarball" "$site"
    echo "[fetch] extracting $site"
    python3 scripts/extract_asset_archive.py "$tarball" sites "$site"
    migrator="sites/$site/migrate_seed.py"
    database="sites/$site/instance_seed/$site.db"
    if [[ -f "sites/$site/.build-generated-seed" ]]; then
        rm -rf "sites/$site/instance_seed"
    elif [[ -f "$migrator" && -f "$database" ]]; then
        echo "[fetch] applying tracked $site seed migration"
        PYTHONHASHSEED=0 python3 "$migrator" "$database"
    fi
    extracted=$((extracted + 1))
done

if [[ -n "$ONLY_SITE" && $extracted -ne 1 ]]; then
    echo "fetch_assets: did not extract requested site $ONLY_SITE" >&2
    exit 1
fi
echo "[fetch] done — $extracted site(s) extracted into sites/"
