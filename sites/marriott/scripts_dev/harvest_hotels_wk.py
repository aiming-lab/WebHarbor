"""WebKit-based harvester for hotel detail pages.

Fetches the live site's own /en-us/hotels/<marsha>-<slug>/overview/ and
/rooms/ pages with a real WebKit engine (fresh profiles per round; the
engine executes Akamai's behavioral interstitial automatically) and
extracts, per hotel: the schema.org JSON-LD Hotel blob (name, description,
postal address, telephone, check-in/check-out, amenities), the rendered
gallery, and the rooms-page room imagery. Writes into
scraped_data/hotel_pages/hotel_details_state.json, mirroring
harvest_hotels.py's format.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from harvest_hotels import extract_hotel, extract_rooms  # noqa: E402

sys.path.insert(0, "/tmp/marriott-scrape/.venv/lib/python3.12/site-packages")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
STATE = ROOT / "scraped_data" / "hotel_pages" / "hotel_details_state.json"
STOP = pathlib.Path("/tmp/stop_wk_hotels")

MAX_HOTELS = int(os.environ.get("MARRIOTT_DETAIL_LIMIT", "260"))


def build_targets() -> list:
    dests = json.loads((OUT / "destinations.json").read_text())
    hotels = {}
    for d in dests:
        for h in d["hotels"]:
            marsha = (h.get("marsha") or "").upper()
            if not marsha or marsha in hotels:
                continue
            hotels[marsha] = {"marsha": marsha, "slug": h.get("slug") or "",
                              "title": h.get("title")}
    targets = [(m, v["slug"]) for m, v in sorted(hotels.items()) if v["slug"]]
    return targets[:MAX_HOTELS]


def _load_state() -> dict:
    """Re-read the shared on-disk state (merged across harvester instances)."""
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except ValueError:
            return {}
    return {}


def _save_state(state: dict) -> None:
    """Merge-write: fold in rows captured by other instances, then persist."""
    merged = _load_state()
    merged.update(state)
    STATE.write_text(json.dumps(merged, indent=1, ensure_ascii=False))


def main() -> None:
    targets = build_targets()
    state = _load_state()
    todo = [(m, s) for m, s in targets if m not in state]
    print(f"{len(targets)} target hotels, {len(todo)} to fetch", flush=True)

    tag = os.environ.get("WK_PROFILE_TAG", "h")
    round_no = 0
    while todo and not STOP.exists():
        round_no += 1
        denials = 0
        with sync_playwright() as p:
            ctx = p.webkit.launch_persistent_context(
                f"/tmp/marriott-wk-hotels-{tag}{round_no}", headless=True,
                viewport={"width": 1440, "height": 900}, locale="en-US")
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            for marsha, slug in todo:
                if STOP.exists():
                    break
                if marsha in state or marsha in _load_state():
                    continue
                base = f"https://www.marriott.com/en-us/hotels/{marsha.lower()}-{slug}"
                try:
                    pg.goto(f"{base}/overview/", wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(7000)
                    ov_html = pg.content()
                    if "Access Denied" in pg.title() or len(ov_html) < 2000:
                        denials += 1
                        if denials >= 5:
                            break
                        time.sleep(random.uniform(2, 5))
                        continue
                    denials = 0
                    parsed = extract_hotel(ov_html, marsha, slug)
                    if parsed is None:
                        print(f"[no-ld] {marsha}", flush=True)
                        state[marsha] = {"marsha": marsha, "slug": slug,
                                         "name": None, "missing": True}
                        _save_state(state)
                        continue
                    pg.goto(f"{base}/rooms/", wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(6000)
                    parsed["rooms_imagery"] = extract_rooms(pg.content())
                    state[marsha] = parsed
                    _save_state(state)
                    print(f"[ok] {marsha} {parsed['name']} "
                          f"gallery={len(parsed['gallery'])} "
                          f"rooms={len(parsed['rooms_imagery'])}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"[err] {marsha}: {str(exc)[:90]}", flush=True)
                time.sleep(random.uniform(1.0, 2.5))
            ctx.close()
        state = _load_state()
        todo = [(m, s) for m, s in targets if m not in state]
        print(f"[round {round_no}] {len(todo)} hotels remaining", flush=True)
        if todo:
            time.sleep(random.uniform(20, 60))

    details = {m: v for m, v in state.items() if not v.get("missing")}
    (OUT / "hotel_details.json").write_text(json.dumps(details, indent=1, ensure_ascii=False))
    print(f"DONE {len(details)} hotel details", flush=True)


if __name__ == "__main__":
    main()
