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
    INCLUDES=("$ONLY_SITE.tar.gz")
    echo "[fetch] scope: $ONLY_SITE only"
else
    # Request exactly the archives this checkout registers. The dataset may also
    # hold archives for sites whose code has not merged yet; downloading them
    # would waste bandwidth and make the inventory below ambiguous.
    INCLUDES=()
    for site_dir in sites/*/; do
        [[ -d "$site_dir" ]] || continue
        INCLUDES+=("$(basename "$site_dir").tar.gz")
    done
    echo "[fetch] scope: ${#INCLUDES[@]} registered site(s)"
fi

INCLUDE_ARGS=()
for pattern in "${INCLUDES[@]}"; do
    INCLUDE_ARGS+=(--include "$pattern")
done

hf download "$REPO" --repo-type dataset --revision "$REVISION" \
    "${INCLUDE_ARGS[@]}" --local-dir "$CACHE_DIR"

shopt -s nullglob
missing=()
if [[ -n "$ONLY_SITE" ]]; then
    TARBALLS=("$CACHE_DIR/$ONLY_SITE.tar.gz")
    if [[ ! -f "${TARBALLS[0]}" ]]; then
        echo "fetch_assets: expected archive for $ONLY_SITE" >&2
        exit 1
    fi
else
    # Every site in this checkout must have an archive at the pinned revision.
    # Archives for sites that are not in this checkout are ignored: the dataset
    # can legitimately carry assets that were merged ahead of their code PR, and
    # rejecting them would make an otherwise complete pin unusable.
    TARBALLS=()
    for site_dir in sites/*/; do
        [[ -d "$site_dir" ]] || continue
        site=$(basename "$site_dir")
        if [[ -f "$CACHE_DIR/$site.tar.gz" ]]; then
            TARBALLS+=("$CACHE_DIR/$site.tar.gz")
        else
            missing+=("$site")
        fi
    done
    if (( ${#missing[@]} > 0 )); then
        echo "fetch_assets: revision $REVISION has no archive for: ${missing[*]}" >&2
        exit 1
    fi
    unregistered=0
    for tarball in "$CACHE_DIR"/*.tar.gz; do
        site=$(basename "$tarball" .tar.gz)
        [[ -d "sites/$site" ]] || unregistered=$((unregistered + 1))
    done
    if (( unregistered > 0 )); then
        echo "[fetch] ignoring $unregistered archive(s) for sites not present in this checkout"
    fi
fi
extracted=0
for tarball in "${TARBALLS[@]}"; do
    site=$(basename "$tarball" .tar.gz)
    if [[ -n "$ONLY_SITE" && "$site" != "$ONLY_SITE" ]]; then continue; fi
    python3 scripts/validate_asset_archive.py "$tarball" "$site"
    echo "[fetch] extracting $site"
    python3 scripts/extract_asset_archive.py "$tarball" sites "$site"
    # An archive can outlive the code that used it: a site may stop shipping a
    # managed root, or stop generating per-record art. asset_inventory.json is
    # the declared contract for what the site actually serves, and the build
    # validates it, so prune managed files the contract does not declare instead
    # of leaving stale members to fail the inventory gate.
    python3 scripts/sync_assets_to_inventory.py "sites/$site"
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
