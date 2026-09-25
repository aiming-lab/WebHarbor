"""Long-running, resumable destination harvester with cool-down backoff."""
from __future__ import annotations

import json
import pathlib
import random
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mfetch import fetch

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from harvest_destinations import DESTINATIONS, extract_destination, CACHE, OUT


def main() -> None:
    parsed_all = []
    dest_done = set()
    state = OUT / "destinations_state.json"
    if state.exists():
        parsed_all = json.loads(state.read_text())
        dest_done = {d["slug"] for d in parsed_all}
    failures = {}
    for slug, path in DESTINATIONS:
        cache_file = CACHE / f"{slug}.json"
        if cache_file.exists() and slug in dest_done:
            continue
        url = f"https://www.marriott.com/en-us/destinations/{path}.mi"
        resp = fetch(url, tries=3, sleep=(30, 60))
        if resp is None:
            failures[slug] = failures.get(slug, 0) + 1
            print(f"[fail {failures[slug]}] {slug} -- cooling down", flush=True)
            time.sleep(random.uniform(90, 180))
            continue
        cache_file.write_text(resp.text)
        parsed = extract_destination(resp.text, slug)
        if parsed is None or not parsed.get("hotels"):
            print(f"[empty] {slug}", flush=True)
            time.sleep(random.uniform(3, 8))
            continue
        parsed_all.append(parsed)
        state.write_text(json.dumps(parsed_all, indent=1, ensure_ascii=False))
        print(f"[ok] {slug}: {len(parsed['hotels'])} hotels (total {len(parsed_all)} dests)", flush=True)
        time.sleep(random.uniform(4, 12))
    (OUT / "destinations.json").write_text(json.dumps(parsed_all, indent=1, ensure_ascii=False))
    codes = {}
    for d in parsed_all:
        for h in d["hotels"]:
            codes.setdefault(h["marsha"], d["slug"])
    print(f"DONE destinations={len(parsed_all)} unique_hotels={len(codes)}")


if __name__ == "__main__":
    main()
