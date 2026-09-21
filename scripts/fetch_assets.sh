#!/usr/bin/env bash
# Fetch only registered sites, honoring optional site.<slug> immutable pins.
# A scoped pin lets a new site's assets coexist with the other tested bundles.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(awk '/^repo:/ {print $2}' .assets-revision)
REVISION="${ASSETS_REVISION:-$(awk '/^revision:/ {print $2}' .assets-revision)}"
ONLY_SITE="${1:-}"
command -v hf >/dev/null 2>&1 || { echo "fetch_assets: install huggingface_hub CLI" >&2; exit 1; }
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo "Expected immutable asset revision" >&2; exit 1; }
if [[ -n "$ONLY_SITE" ]]; then
    [[ "$ONLY_SITE" =~ ^[a-z0-9_]+$ && -d "sites/$ONLY_SITE" ]] || { echo "Unknown site: $ONLY_SITE" >&2; exit 1; }
    SITES=("$ONLY_SITE")
else
    SITES=()
    for dir in sites/*/; do SITES+=("$(basename "$dir")"); done
fi
# Download in revision groups; never extract unrelated or stale cached archives.
declare -A SITE_REVISIONS=()
declare -A REVISIONS=()
for site in "${SITES[@]}"; do
    pin=$(awk -v key="site.$site:" '$1 == key {print $2}' .assets-revision)
    pin="${pin:-$REVISION}"
    [[ "$pin" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid pin for $site" >&2; exit 1; }
    SITE_REVISIONS["$site"]="$pin"
    REVISIONS["$pin"]=1
done
for pin in "${!REVISIONS[@]}"; do
    includes=()
    for site in "${SITES[@]}"; do
        [[ "${SITE_REVISIONS[$site]}" != "$pin" ]] || includes+=(--include "$site.tar.gz")
    done
    cache="sites/.cache/tarballs/$pin"
    mkdir -p "$cache"
    hf download "$REPO" --repo-type dataset --revision "$pin" "${includes[@]}" --local-dir "$cache"
done
for site in "${SITES[@]}"; do
    pin="${SITE_REVISIONS[$site]}"
    archive="sites/.cache/tarballs/$pin/$site.tar.gz"
    [[ -f "$archive" ]] || { echo "Missing pinned archive: $site @ $pin" >&2; exit 1; }
    echo "[fetch] $site @ $pin"
    python3 - "$archive" "$site" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
archive, site = sys.argv[1:]
with tarfile.open(archive) as bundle:
    for member in bundle.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != site:
            raise SystemExit('Archive member outside requested site')
        if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
            raise SystemExit('Unsupported archive member')
    bundle.extractall('sites', filter='data')
PY
done
echo "[fetch] done — ${#SITES[@]} registered site(s)"
