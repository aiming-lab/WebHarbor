#!/usr/bin/env python3
"""Generate and build all 153 per-website images.

Each image: FROM webharbor-harbor-base + the site tree copied out of the
monolith image, stripped of verify/, tests/, and tasks.jsonl, and made
root-only. Seeds and assets are byte-identical to the validated monolith
build (same revision), so every site's verifier seed contract holds.

Usage:
  python3 build_site_images.py --metadata sites-metadata.json [--only a,b] [--jobs N]

Reads the adapter's site metadata JSON (ports, DB names, images) and the
task counts to sanity-check each built image.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_ROOT = HERE.parent / "build" / "site-images"
MONOLITH_DEFAULT = "wildawm/webharbor:all-v1"
BASE_DEFAULT = "webharbor-harbor-base:0.2"

DOCKERFILE = """ARG BASE={base}
ARG MONOLITH={monolith}
FROM ${{MONOLITH}} AS monolith-src
FROM ${{BASE}}
COPY --from=monolith-src /opt/WebSyn/{site} /opt/WebSyn/{site}
RUN rm -rf /opt/WebSyn/{site}/verify /opt/WebSyn/{site}/tests /opt/WebSyn/{site}/tasks.jsonl \\
    && rm -rf /opt/WebSyn/{site}/instance \\
    && chmod -R go-rwx /opt/WebSyn/{site} \\
    && test -f /opt/WebSyn/{site}/instance_seed/{db} \\
    && test ! -f /opt/WebSyn/{site}/tasks.jsonl \\
    && test ! -d /opt/WebSyn/{site}/verify
ENV WH_SITE={site} WH_PORT={port} WH_DB_NAME={db}
EXPOSE {port}
ENTRYPOINT ["/opt/webharbor-harness/site_entrypoint.sh"]
"""


def build_one(site: str, meta: dict, monolith: str, base: str, force: bool) -> tuple[str, str]:
    ctx = BUILD_ROOT / site
    ctx.mkdir(parents=True, exist_ok=True)
    (ctx / "site.Dockerfile").write_text(
        DOCKERFILE.format(site=site, db=meta["db_name"], port=meta["port"],
                          monolith=monolith, base=base),
        encoding="utf-8",
    )
    # NOTE: docker build progress must go to a FILE, never a pipe. BuildKit
    # emits megabytes of progress; subprocess.run(capture_output=True) fills
    # its 64KB pipe, the CLI blocks on write, and the worker slot deadlocks
    # (observed live: images get tagged by the daemon while the CLI hangs).
    build_log = ctx / "build.log"
    cmd = ["docker", "build", "-t", meta["image"], "-f", "site.Dockerfile", "."]
    if force:
        cmd.insert(2, "--no-cache")
    with open(build_log, "w") as handle:
        result = subprocess.run(cmd, cwd=ctx, stdout=handle, stderr=subprocess.STDOUT,
                                timeout=3600)
    if result.returncode != 0:
        tail = ""
        try:
            tail = build_log.read_text(encoding="utf-8", errors="replace")[-500:]
        except OSError:
            pass
        return site, "BUILD FAIL: " + tail
    verify_log = ctx / "verify.log"
    with open(verify_log, "w") as handle:
        verify = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "sh", meta["image"], "-c",
             f"test -f /opt/WebSyn/{site}/instance_seed/{meta['db_name']} && "
             f"test ! -f /opt/WebSyn/{site}/tasks.jsonl && "
             f"test ! -d /opt/WebSyn/{site}/verify && "
             f"su ubuntu -c 'cat /opt/WebSyn/{site}/app.py' 2>&1 | grep -q 'Permission denied' && echo OK"],
            stdout=handle, stderr=subprocess.STDOUT, timeout=300,
        )
    try:
        out = verify_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        out = ""
    if "OK" not in out:
        return site, f"VERIFY FAIL: {out[:300]!r}"
    return site, "OK"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--monolith", default=MONOLITH_DEFAULT)
    parser.add_argument("--base", default=BASE_DEFAULT)
    parser.add_argument("--only", default=None)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    metadata = json.loads(Path(args.metadata).read_text())
    sites = sorted(metadata)
    if args.only:
        wanted = set(args.only.split(","))
        sites = [s for s in sites if s in wanted]

    print(f"building {len(sites)} site images (monolith={args.monolith}, jobs={args.jobs})")
    failures: list[tuple[str, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(build_one, site, metadata[site], args.monolith, args.base, args.force): site
            for site in sites
        }
        for future in as_completed(futures):
            site, status = future.result()
            done += 1
            if status == "OK":
                print(f"[{done}/{len(sites)}] {site}: OK", flush=True)
            else:
                failures.append((site, status))
                print(f"[{done}/{len(sites)}] {site}: {status}", flush=True)

    if failures:
        print(f"FAILURES: {len(failures)}")
        for site, status in failures:
            print(f"  {site}: {status[:300]}")
        return 1
    print(f"all {len(sites)} site images built and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
