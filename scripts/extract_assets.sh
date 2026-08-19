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

# Subpaths inside each site/<site>/ that the tarball should include.
# Keep in sync with .assetpaths.
SUBPATHS=(instance_seed static/images static/external_cache)

echo "[pack] sites/ -> $TARGET/"
count=0
for site_dir in sites/*/; do
    site=$(basename "$site_dir")
    [[ -d "$site_dir" ]] || continue
    if [[ -n "$ONLY_SITE" && "$site" != "$ONLY_SITE" ]]; then continue; fi

    members=()
    for sub in "${SUBPATHS[@]}"; do
        [[ -e "$site_dir$sub" ]] && members+=("$site/$sub")
    done
    if [[ ${#members[@]} -eq 0 ]]; then
        echo "  $site: no managed assets, skipping"; continue
    fi

    out="$TARGET/$site.tar.gz"
    COPYFILE_DISABLE=1 tar -czf "$out" -C sites "${members[@]}"
    sz=$(du -sh "$out" 2>/dev/null | cut -f1)
    printf "  %-22s -> %-30s %s\n" "$site" "$site.tar.gz" "$sz"
    count=$((count + 1))
done

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
