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
    declare -A expected_sites=()
    declare -A archive_sites=()
    for site_dir in sites/*/; do
        [[ -d "$site_dir" ]] && expected_sites["$(basename "$site_dir")"]=1
    done
    for tarball in "${TARBALLS[@]}"; do
        archive_sites["$(basename "$tarball" .tar.gz)"]=1
    done
    missing=()
    extra=()
    for site in "${!expected_sites[@]}"; do
        [[ -n "${archive_sites[$site]:-}" ]] || missing+=("$site")
    done
    for site in "${!archive_sites[@]}"; do
        [[ -n "${expected_sites[$site]:-}" ]] || extra+=("$site")
    done
    if (( ${#missing[@]} || ${#extra[@]} )); then
        echo "fetch_assets: archive set mismatch at revision $REVISION; missing=[${missing[*]}] extra=[${extra[*]}]" >&2
        exit 1
    fi
fi

TRANSACTION=""
rollback_assets() {
    status=$?
    trap - ERR INT TERM
    if [[ -n "$TRANSACTION" && -d "$TRANSACTION" ]]; then
        echo "fetch_assets: rolling back repository-wide managed-asset transaction" >&2
        python3 scripts/asset_transaction.py rollback sites "$TRANSACTION"
    fi
    exit "$status"
}

if [[ -z "$ONLY_SITE" ]]; then
    echo "[fetch] pre-validating complete archive set before changing managed roots"
    for tarball in "${TARBALLS[@]}"; do
        site=$(basename "$tarball" .tar.gz)
        validator_args=()
        [[ -f "sites/$site/.build-generated-seed" ]] && validator_args+=(--allow-missing-seed)
        python3 scripts/validate_asset_archive.py "$tarball" "$site" "${validator_args[@]}"
    done
    TRANSACTION="sites/.cache/asset-transaction-$$"
    python3 scripts/asset_transaction.py begin sites "$TRANSACTION"
    trap rollback_assets ERR INT TERM
fi

extracted=0
for tarball in "${TARBALLS[@]}"; do
    site=$(basename "$tarball" .tar.gz)
    if [[ -n "$ONLY_SITE" && "$site" != "$ONLY_SITE" ]]; then continue; fi
    validator_args=()
    if [[ -f "sites/$site/.build-generated-seed" ]]; then
        validator_args+=(--allow-missing-seed)
    fi
    python3 scripts/validate_asset_archive.py "$tarball" "$site" "${validator_args[@]}"
    echo "[fetch] extracting $site"
    extractor_args=()
    migrator="sites/$site/migrate_seed.py"
    if [[ ! -f "sites/$site/.build-generated-seed" && -f "$migrator" ]]; then
        echo "[fetch] applying tracked $site seed migration in staging"
        extractor_args+=(--migrator "$migrator")
    fi
    python3 scripts/extract_asset_archive.py "$tarball" sites "$site" "${extractor_args[@]}"
    if [[ -f "sites/$site/.build-generated-seed" ]]; then
        rm -rf "sites/$site/instance_seed"
    fi
    extracted=$((extracted + 1))
done

if [[ -n "$TRANSACTION" ]]; then
    completed_transaction="$TRANSACTION"
    TRANSACTION=""
    trap - ERR INT TERM
    python3 scripts/asset_transaction.py commit sites "$completed_transaction"
fi

if [[ -n "$ONLY_SITE" && $extracted -ne 1 ]]; then
    echo "fetch_assets: did not extract requested site $ONLY_SITE" >&2
    exit 1
fi
if [[ -n "$ONLY_SITE" ]]; then
    rm -f sites/.assets-state.json
    echo "[fetch] single-site fetch invalidated full-tree asset state; run a full fetch before building"
else
    python3 scripts/asset_state.py write sites .assets-revision sites/.assets-state.json --cache "$CACHE_DIR"
fi
echo "[fetch] done — $extracted site(s) extracted into sites/"
