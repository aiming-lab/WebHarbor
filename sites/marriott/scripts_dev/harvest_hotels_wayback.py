"""Wayback Machine harvester for hotel detail pages.

For hotels whose live overview page has a Wayback snapshot (see
/tmp/wayback_coverage.json from the CDX probe), fetches the archived copy
of https://www.marriott.com/en-us/hotels/<marsha>-<slug>/overview/ in raw
mode (id_ suffix, no toolbar) and extracts the same JSON-LD Hotel blob the
live harvester (harvest_hotels_wk.py) captures: name, description, postal
address, telephone, check-in/check-out, amenityFeature list, and the
rendered gallery. Merges results into scraped_data/hotel_pages/
hotel_details_state.json with the same layout the seed builder folds in,
skipping hotels already captured by the live harvester.

Resumable: re-running continues where it left off. Polite to
web.archive.org: serial requests with jittered gaps; 503/429 back off.
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from harvest_hotels import extract_hotel  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
STATE = ROOT / "scraped_data" / "hotel_pages" / "hotel_details_state.json"
COVERAGE = pathlib.Path("/tmp/wayback_coverage.json")
STOP = pathlib.Path("/tmp/stop_wb_hotels")


def _load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except ValueError:
            return {}
    return {}


def _save_state(state: dict) -> None:
    merged = _load_state()
    merged.update(state)
    STATE.write_text(json.dumps(merged, indent=1, ensure_ascii=False))


def _fetch(url: str, cl) -> "tuple[str, str] | None":
    """Fetch with retry; returns (status, text) or None on repeated failure."""
    for attempt in range(4):
        try:
            r = cl.get(url)
            if r.status_code == 200 and len(r.text) > 2000:
                return r.text
            if r.status_code in (429, 503, 502):
                time.sleep(random.uniform(20, 45) * (attempt + 1))
                continue
            # 404 snapshot gone etc — don't hammer
            time.sleep(random.uniform(3, 8))
            return None
        except Exception:
            time.sleep(random.uniform(15, 30) * (attempt + 1))
    return None


def main() -> None:
    import httpx

    dests = json.loads((OUT / "destinations.json").read_text())
    slug_of = {}
    for dd in dests:
        for h in dd.get("hotels") or []:
            m = (h.get("marsha") or "").upper()
            if m:
                slug_of.setdefault(m.lower(), h.get("slug"))

    coverage = json.loads(COVERAGE.read_text()) if COVERAGE.exists() else {}
    state = _load_state()
    targets = [m for m in sorted(coverage)
               if coverage.get(m)
               and m.upper() not in state]
    print(f"{len(targets)} wayback targets not yet captured", flush=True)

    captured = 0
    with httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0"},
                      follow_redirects=True) as cl:
        for i, m in enumerate(targets):
            if STOP.exists():
                print("stop requested", flush=True)
                break
            slug = slug_of.get(m)
            if not slug:
                continue
            ts_list = coverage[m]
            html = None
            used_ts = None
            for ts in ts_list[:3]:
                url = (f"https://web.archive.org/web/{ts}id_/"
                       f"https://www.marriott.com/en-us/hotels/{m}-{slug}/overview/")
                got = _fetch(url, cl)
                if got:
                    html = got
                    used_ts = ts
                    break
            if not html:
                print(f"[miss] {m}", flush=True)
                time.sleep(random.uniform(4, 10))
                continue
            parsed = extract_hotel(html, m.upper(), slug)
            if parsed is None:
                # archived page without the JSON-LD blob (or a bot-page);
                # record as missing so we don't retry forever
                state[m.upper()] = {"marsha": m.upper(), "slug": slug,
                                    "name": None, "missing": True,
                                    "wayback_ts": used_ts}
                _save_state(state)
                print(f"[no-ld] {m}", flush=True)
            else:
                parsed["wayback_ts"] = used_ts
                state[m.upper()] = parsed
                _save_state(state)
                captured += 1
                print(f"[ok] {m} {parsed.get('name')} "
                      f"amen={len(parsed.get('amenities') or [])} "
                      f"gallery={len(parsed.get('gallery') or [])}", flush=True)
            time.sleep(random.uniform(3, 8))
            if (i + 1) % 20 == 0:
                print(f"  progress {i + 1}/{len(targets)} captured={captured}",
                      flush=True)

    details = {m: v for m, v in _load_state().items() if not v.get("missing")}
    (OUT / "hotel_details.json").write_text(
        json.dumps(details, indent=1, ensure_ascii=False))
    print(f"DONE captured={captured} total-details={len(details)}", flush=True)


if __name__ == "__main__":
    main()
