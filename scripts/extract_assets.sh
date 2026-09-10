#!/usr/bin/env bash
# Pack each site's HF-managed assets into <site>.tar.gz for upload.
#
# The Hugging Face dataset stores one tarball per site to avoid the
# small-file tax (4000+ tiny files made `hf download` stall). Each
# <site>.tar.gz extracts back to sites/<site>/{instance_seed,static/images,
# static/external_cache} in place.
#
# Usage:
#   ./scripts/extract_assets.sh <staging-dir>                    # all sites
#   ./scripts/extract_assets.sh <staging-dir> google_search      # one site
#   ./scripts/extract_assets.sh <staging-dir> --push             # all + upload
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:?usage: extract_assets.sh <staging-dir> [site|--push]}"
ARG2="${2:-}"
PUSH=""
ONLY_SITE=""
if [[ "$ARG2" == "--push" ]]; then PUSH="--push"; else ONLY_SITE="$ARG2"; fi

REPO=$(awk '/^repo:/ {print $2}' .assets-revision)
mkdir -p "$TARGET"
shopt -s nullglob dotglob
existing_output=("$TARGET"/*)
if [[ ${#existing_output[@]} -ne 0 ]]; then
    echo "[pack] target directory must be empty: $TARGET" >&2
    exit 1
fi
shopt -u dotglob

# Subpaths inside each site/<site>/ that the tarball should include.
# Keep in sync with .assetpaths.
SUBPATHS=(instance_seed static/images static/external_cache)

echo "[pack] sites/ -> $TARGET/"
count=0
for site_dir in sites/*/; do
    site=$(basename "$site_dir")
    [[ -d "$site_dir" ]] || continue
    if [[ -n "$ONLY_SITE" && "$site" != "$ONLY_SITE" ]]; then continue; fi

    if [[ ! -f "${site_dir}.build-generated-seed" ]]; then
        seed_databases=("${site_dir}instance_seed/"*.db)
        if [[ ${#seed_databases[@]} -ne 1 || ! -s "${seed_databases[0]:-}" ]]; then
            echo "[pack] $site must have exactly one non-empty instance_seed/*.db file" >&2
            exit 1
        fi
    fi

    members=()
    for sub in "${SUBPATHS[@]}"; do
        if [[ "$sub" == "instance_seed" && -f "${site_dir}.build-generated-seed" ]]; then
            continue
        fi
        [[ -e "$site_dir$sub" ]] && members+=("$site/$sub")
    done
    if [[ ${#members[@]} -eq 0 ]]; then
        echo "[pack] $site has no managed roots; refusing an incomplete archive set" >&2
        exit 1
    fi

    out="$TARGET/$site.tar.gz"
    # macOS may synthesize AppleDouble ``._*`` metadata while archiving files.
    # Exclude it explicitly so uploaded assets are portable and reproducible.
    COPYFILE_DISABLE=1 tar --exclude='._*' -czf "$out" -C sites "${members[@]}"
    validator_args=()
    [[ -f "${site_dir}.build-generated-seed" ]] && validator_args+=(--allow-missing-seed)
    python3 scripts/validate_asset_archive.py "$out" "$site" "${validator_args[@]}"
    sz=$(du -sh "$out" 2>/dev/null | cut -f1)
    printf "  %-22s -> %-30s %s\n" "$site" "$site.tar.gz" "$sz"
    count=$((count + 1))
done

expected_count=0
for site_dir in sites/*/; do
    [[ -d "$site_dir" ]] || continue
    [[ -n "$ONLY_SITE" && "$(basename "$site_dir")" != "$ONLY_SITE" ]] && continue
    expected_count=$((expected_count + 1))
done
archives=("$TARGET"/*.tar.gz)
if [[ $count -ne $expected_count || ${#archives[@]} -ne $expected_count ]]; then
    echo "[pack] exact archive-set check failed: expected=$expected_count generated=$count present=${#archives[@]}" >&2
    exit 1
fi

echo "[pack] done — $count tarballs in $TARGET/"

if [[ "$PUSH" == "--push" ]]; then
    if ! command -v hf >/dev/null; then
        echo "[pack] cannot push: 'hf' CLI not found" >&2; exit 1
    fi
    echo "[pack] hf upload-large-folder $REPO $TARGET --repo-type dataset"
    hf upload-large-folder "$REPO" "$TARGET" --repo-type dataset
else
    echo "[pack] next: hf upload-large-folder $REPO $TARGET --repo-type dataset"
fi
