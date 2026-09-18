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
#   ASSETS_REVISION=abc123 ./scripts/fetch_assets.sh   # override all pins
# .assets-revision may also contain site.<name>: <immutable SHA> entries.
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

# A site may pin an immutable bundle independently while its HF PR awaits
# integration. An explicit ASSETS_REVISION override deliberately replaces all
# pins, which is useful when validating a proposed consolidated release.
declare -A SITE_REVISIONS
declare -A SITE_REPOS
TARBALLS=()
BASE_INCLUDES=()
for archive in "${INCLUDES[@]}"; do
    site=${archive%.tar.gz}
    if [[ ! -d "sites/$site" || ! "$site" =~ ^[a-z0-9_]+$ ]]; then
        echo "fetch_assets: unknown site: $site" >&2
        exit 1
    fi
    revision="$REVISION"
    asset_repo="$REPO"
    if [[ -z "${ASSETS_REVISION:-}" ]]; then
        scoped=$(awk -v key="site.$site:" '$1 == key {print $2}' .assets-revision)
        scoped_repo=$(awk -v key="site.$site.repo:" '$1 == key {print $2}' .assets-revision)
        if [[ -n "$scoped" ]]; then
            [[ "$scoped" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid immutable pin for $site" >&2; exit 1; }
            revision="$scoped"
            asset_repo="${scoped_repo:-$REPO}"
        elif [[ -n "$scoped_repo" ]]; then
            echo "Scoped repository needs an immutable revision: $site" >&2
            exit 1
        fi
    fi
    SITE_REVISIONS[$site]="$revision"
    SITE_REPOS[$site]="$asset_repo"
    TARBALLS+=("sites/.cache/tarballs/$revision/$archive")
    if [[ "$revision" == "$REVISION" && "$asset_repo" == "$REPO" ]]; then
        BASE_INCLUDES+=(--include "$archive")
    fi
done
if (( ${#BASE_INCLUDES[@]} )); then
    hf download "$REPO" --repo-type dataset --revision "$REVISION" \
        "${BASE_INCLUDES[@]}" --local-dir "$CACHE_DIR"
fi
for archive in "${INCLUDES[@]}"; do
    site=${archive%.tar.gz}
    revision=${SITE_REVISIONS[$site]}
    if [[ "$revision" != "$REVISION" || "${SITE_REPOS[$site]}" != "$REPO" ]]; then
        echo "[fetch] $site scoped pin: $revision"
        hf download "${SITE_REPOS[$site]}" --include "$archive" --repo-type dataset --revision "$revision" \
            --local-dir "sites/.cache/tarballs/$revision"
    fi
done
AVAILABLE_TARBALLS=()
for tarball in "${TARBALLS[@]}"; do
    if [[ ! -f "$tarball" ]]; then
        site=$(basename "$tarball" .tar.gz)
        # Build-generated sites need no archive only when they also need no
        # downloaded images or external cache. Required assets still fail closed.
        if [[ -f "sites/$site/.build-generated-seed" &&
              ! -f "sites/$site/.requires-images" &&
              ! -f "sites/$site/.requires-external-cache" ]]; then
            echo "[fetch] $site: build-generated seed, no archive — skipping"
            if [[ -n "$ONLY_SITE" ]]; then exit 0; fi
            continue
        fi
        echo "fetch_assets: expected archive: $tarball" >&2
        exit 1
    fi
    AVAILABLE_TARBALLS+=("$tarball")
done
TARBALLS=("${AVAILABLE_TARBALLS[@]}")
extracted=0
for tarball in "${TARBALLS[@]}"; do
    site=$(basename "$tarball" .tar.gz)
    if [[ -n "$ONLY_SITE" && "$site" != "$ONLY_SITE" ]]; then continue; fi
    expected_sha=$(awk -v key="site.$site.sha256:" '$1 == key {print $2}' .assets-revision)
    if [[ -n "$expected_sha" && -z "${ASSETS_REVISION:-}" ]]; then
        [[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "Invalid archive hash: $site" >&2; exit 1; }
        actual_sha=$(sha256sum "$tarball" | cut -d' ' -f1)
        [[ "$actual_sha" == "$expected_sha" ]] || { echo "Archive hash mismatch: $site" >&2; exit 1; }
    fi
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
