"""One-shot data corrections for source_data/content.json (review §六-2/3/4/7).

Applies the fixes the independent review required, restoring upstream link
blocks the harvest lost and re-pointing same-origin absolute URLs at their
local equivalents:

  1. /fares-tolls/tolls        'Toll rates by vehicle type' -> local
     /tolls/vehicle-types (was an upstream absolute URL; the local page
     existed but was an orphan — review §六-4).
  2. /transparency              add the upstream 'Leadership' link block
     (board members + executive leadership) so the two pages gain in-site
     entry links — review §六-5.
  3. /about                     restore the upstream 'Who we are' leadership
     links (23-member Board / executive leadership) the harvest flattened.
  4. /fares-tolls/lirr-metro-north  fill the empty 'Fare tables' links block
     with the six official fare charts (served from source_data/fare_docs/
     via /fares-tolls/lirr-metro-north/fare-chart/<name>.pdf) and the
     'More information' block's local links — review §六-3.
  5. /fares-tolls               fill the hub's empty links block (how to
     save money / pre-tax benefits / 2025 changes), matching upstream.
  6. /fares-tolls/subway-bus    add the upstream in-section links (reduced
     fares / tap and ride / how to save money) — review §六-7.
  7. same-origin new.mta.info / www.mta.info hrefs with local equivalents
     are normalized to local paths (schedules, investor-info/sustainability,
     fares-tolls/subway-bus, project/cbtc-signal-upgrades).

Run once:  python3 scripts_dev/apply_content_fixes.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTENT = ROOT / "source_data" / "content.json"

data = json.loads(CONTENT.read_text(encoding="utf-8"))


def find_block(page, block_type, predicate=None):
    for i, b in enumerate(page["blocks"]):
        if b.get("type") == block_type and (predicate is None or predicate(b)):
            return i
    return None


# --- 1. tolls hub: vehicle-types link goes local -----------------------------
tolls = data["/fares-tolls/tolls"]
fixed = 0
for b in tolls["blocks"]:
    if b.get("type") == "links":
        for l in b.get("links", []):
            if l.get("href") == "https://new.mta.info/tolls/vehicle-types":
                l["href"] = "/tolls/vehicle-types"
                fixed += 1
assert fixed in (0, 1), f"unexpected vehicle-types link fixes: {fixed}"

# --- 2. /transparency: restore the upstream Leadership section ----------------
transparency = data["/transparency"]
has_leadership = any(
    b.get("type") == "links" and any(
        "/transparency/leadership/" in (l.get("href") or "")
        for l in b.get("links", []))
    for b in transparency["blocks"])
if not has_leadership:
    idx = find_block(transparency, "h2", lambda b: b.get("text") == "Financial and investor information")
    leadership = [
        {"type": "h2", "text": "Leadership"},
        {"type": "links", "links": [
            {"href": "/transparency/leadership/board-members", "text": "MTA Board members"}]},
        {"type": "links", "links": [
            {"href": "/transparency/leadership/executive-leadership",
             "text": "Executive leadership"}]},
    ]
    transparency["blocks"][idx:idx] = leadership

# --- 3. /about: restore the upstream 'Who we are' leadership links -----------
about = data["/about"]
has_about_links = any(
    "/transparency/leadership/" in (l.get("href") or "")
    for b in about["blocks"] if b.get("type") == "links"
    for l in b.get("links", []))
if not has_about_links:
    idx = find_block(about, "h2", lambda b: b.get("text") == "Who we are")
    # insert right after the 'Who we are' prose block
    about["blocks"][idx + 1:idx + 1] = [
        {"type": "links", "links": [
            {"href": "/transparency/leadership/executive-leadership",
             "text": "Learn more about the MTA's executive leadership"}]},
        {"type": "links", "links": [
            {"href": "/transparency/leadership/board-members",
             "text": "Learn more about the MTA Board and its members"}]},
    ]

# --- 4. LIRR/MNR fares page: the official fare tables ------------------------
rail = data["/fares-tolls/lirr-metro-north"]
fare_links = [
    {"href": "/fares-tolls/lirr-metro-north/fare-chart/lirr_fares.pdf",
     "text": "Long Island Rail Road fares"},
    {"href": "/fares-tolls/lirr-metro-north/fare-chart/mnr_harlem_hudson_gct.pdf",
     "text": "Metro-North Harlem and Hudson Line fares to GCT"},
    {"href": "/fares-tolls/lirr-metro-north/fare-chart/mnr_newhaven_gct.pdf",
     "text": "Metro-North New Haven Line fares to GCT"},
    {"href": "/fares-tolls/lirr-metro-north/fare-chart/mnr_harlem_hudson_intermediate.pdf",
     "text": "Metro-North Harlem and Hudson intermediate fares"},
    {"href": "/fares-tolls/lirr-metro-north/fare-chart/mnr_newhaven_intermediate.pdf",
     "text": "Metro-North New Haven Line intermediate fares"},
    {"href": "/fares-tolls/lirr-metro-north/fare-chart/port_jervis_pascack.pdf",
     "text": "Port Jervis and Pascack Valley Line fares"},
]
# the empty links block right before the fare-tables prose
filled_fare_tables = False
for i, b in enumerate(rail["blocks"]):
    if (b.get("type") == "links" and not b.get("links")
            and i + 1 < len(rail["blocks"])
            and rail["blocks"][i + 1].get("type") == "prose"
            and "Harlem and Hudson Line fares to GCT" in rail["blocks"][i + 1].get("text", "")):
        rail["blocks"][i]["links"] = fare_links
        filled_fare_tables = True
assert filled_fare_tables or any(
    (l.get("href") or "").startswith("/fares-tolls/lirr-metro-north/fare-chart/")
    for b in rail["blocks"] if b.get("type") == "links"
    for l in b.get("links", [])), "fare tables block not found"
# 'More information about fares' — restore the local links the harvest lost
# (refunds + pre-tax benefits; the ec0.mta.info claim portals stay upstream).
more_info = [
    {"href": "/fares-tolls/lirr-metro-north/ticket-refunds",
     "text": "Refunds on LIRR and Metro-North tickets"},
    {"href": "/fares-tolls/pre-tax-benefits",
     "text": "Pre-tax transit benefit information"},
]
tail = rail["blocks"][-1]
if tail.get("type") == "prose" and "Pre-tax transit benefit information" in tail.get("text", ""):
    rail["blocks"].append({"type": "links", "links": more_info})

# --- 5. fares hub: fill the empty links block ----------------------------------
hub = data["/fares-tolls"]
for b in hub["blocks"]:
    if b.get("type") == "links" and not b.get("links"):
        b["links"] = [
            {"href": "/fares-tolls/how-to-save-money", "text": "How to save money on fares"},
            {"href": "/fares-tolls/pre-tax-benefits",
             "text": "Pre-tax transit benefit information"},
            {"href": "/fares-tolls/2025-changes",
             "text": "Changes to MTA fares and tolls in 2025"},
        ]
        break

# --- 6. subway-bus fares page: upstream in-section links ----------------------
subway_bus = data["/fares-tolls/subway-bus"]
has_sb_links = any(
    (l.get("href") or "").startswith("/fares-tolls/subway-bus/")
    for b in subway_bus["blocks"] if b.get("type") == "links"
    for l in b.get("links", []))
if not has_sb_links:
    idx = find_block(subway_bus, "h2", lambda b: b.get("text") == "Tap and ride to pay your fare")
    subway_bus["blocks"][idx:idx] = [
        {"type": "links", "links": [
            {"href": "/fares-tolls/subway-bus/reduced-fare", "text": "Reduced fares"},
            {"href": "/fares-tolls/subway-bus/tap-and-ride",
             "text": "Tap and ride to pay your fare"},
            {"href": "/fares-tolls/how-to-save-money",
             "text": "Learn about more ways to save money on fares"},
        ]},
    ]

# --- 7. localize same-origin absolute URLs with local equivalents -------------
LOCALIZE = {
    "https://new.mta.info/tolls/vehicle-types": "/tolls/vehicle-types",
    "https://new.mta.info/investor-info/sustainability": "/investor-info/sustainability",
    "https://new.mta.info/schedules": "/schedules",
    "https://www.mta.info/schedules": "/schedules",
    "https://www.mta.info/fares-tolls/subway-bus": "/fares-tolls/subway-bus",
    "https://www.mta.info/project/cbtc-signal-upgrades": "/project/cbtc-signal-upgrades",
}
localized = 0
for page in data.values():
    for b in page.get("blocks", []):
        if b.get("type") == "links":
            for l in b.get("links", []):
                if l.get("href") in LOCALIZE:
                    l["href"] = LOCALIZE[l["href"]]
                    localized += 1
print(f"localized {localized} same-origin absolute links")

CONTENT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
print("content.json updated")
