#!/usr/bin/env python3
"""Extract per-site seed DB names from the built monolith image.

Sites with build-generated seeds have no DB in the HF tarball; the monolith
docker build materializes instance_seed/<name>.db inside the image. This
script lists every site's instance_seed in one container run and writes the
full site metadata (port, db name, task count, verify modules) needed by
the adapter and the image builder.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO_DEFAULT = str(Path(__file__).resolve().parents[2])
REVISION_DEFAULT = "HEAD"


def git(repo: str, *args: str) -> str:
    return subprocess.check_output(["git", "-C", repo, *args], text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monolith-image", required=True)
    parser.add_argument("--repo", default=REPO_DEFAULT)
    parser.add_argument("--revision", default=REVISION_DEFAULT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    listing = subprocess.check_output(
        [
            "docker", "run", "--rm", "--entrypoint", "sh", args.monolith_image,
            "-c",
            "for d in /opt/WebSyn/*/; do site=$(basename $d); "
            "for f in $d/instance_seed/*.db; do echo \"$site $(basename $f)\"; done; done",
        ],
        text=True,
        timeout=600,
    )

    db_names: dict[str, str] = {}
    for line in listing.splitlines():
        line = line.strip()
        if not line:
            continue
        site, db = line.split()
        if db.startswith("._"):
            continue  # AppleDouble metadata artifacts from macOS-created tarballs
        if site in db_names and db_names[site] != db:
            sys.exit(f"site {site}: multiple seed DBs ({db_names[site]}, {db})")
        db_names[site] = db

    sites = [
        l.strip()[len("sites/"):].rstrip("/")
        for l in git(args.repo, "ls-tree", "--name-only", args.revision, "sites/").splitlines()
        if l.strip().startswith("sites/") and l.strip().count("/") == 1
    ]

    metadata = {}
    for site in sorted(sites):
        raw = git(args.repo, "show", f"{args.revision}:sites/{site}/tasks.jsonl")
        records = [json.loads(l) for l in raw.splitlines() if l.strip()]
        urls = {r["web"] for r in records}
        if len(urls) != 1:
            sys.exit(f"site {site}: inconsistent web URLs {urls}")
        port = urlsplit(next(iter(urls))).port
        if site not in db_names:
            sys.exit(f"site {site}: no seed DB found in monolith image")
        metadata[site] = {
            "port": port,
            "db_name": db_names[site],
            "image": f"wildawm/webharbor:{site}-v1",
            "start_url": next(iter(urls)),
            "n_tasks": len(records),
            "verify_modules": sorted({Path(r["verifier_path"]).stem for r in records}),
        }

    Path(args.out).write_text(json.dumps(metadata, indent=1), encoding="utf-8")
    print(f"{len(metadata)} sites; DB names extracted from {args.monolith_image}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
