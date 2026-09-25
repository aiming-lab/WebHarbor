"""Harvest the MTA Accessible Stations list into source_data/accessible_stations.json.

Source: https://new.mta.info/accessibility/stations (public page, updated
2026-09-14 per the page header). The page lists every ADA-accessible station
per agency: New York City Subway (by borough), Long Island Rail Road (by
branch) and Metro-North Railroad (by line). The subway entries carry line
icons used to disambiguate same-named stations (e.g. the six-line 86 St vs
the R-line 86 St); several entries carry partial-accessibility notes
("downtown only", "L only; 4/5/6 is not accessible") which are preserved.

The upstream list names are matched to the GTFS station names harvested into
source_data/{subway,lirr,metro_north}.json via a normalization pass plus an
explicit alias table for the handful of spelling differences (Times Square-42 St
vs Times Sq-42 St, Mount Kisco vs Mt Kisco, ...). Stations absent from the
GTFS feeds (Belmont Park seasonal stop, NJ-Transit-operated west-of-Hudson
stations) are recorded in the JSON but flagged so the seeder can skip them.
"""
from __future__ import annotations

import html as htmllib
import json
import pathlib
import re
import subprocess

BASE = pathlib.Path(__file__).resolve().parent.parent
SOURCE = BASE / "source_data"
OUT = SOURCE / "accessible_stations.json"
UPSTREAM = "https://new.mta.info/accessibility/stations"

ALIASES = {
    # upstream accessible-list name -> GTFS station name
    "Times Square-42 St": "Times Sq-42 St",
    "West 4 St-Washington Sq": "W 4 St-Wash Sq",
    "62 St/New Utrecht Av": "New Utrecht Av",
    "Coney Island/Stillwell Av": "Coney Island-Stillwell Av",
    "Crown Hts/Utica Av": "Crown Hts-Utica Av",
    "Myrtle/Wyckoff Av": "Myrtle-Wyckoff Avs",
    "Canarsie/Rockaway Pkwy": "Canarsie-Rockaway Pkwy",
    "Sheepshead Bay Rd": "Sheepshead Bay",
    "Flushing/Main St": "Flushing-Main St",
    "Jackson Hts-Roosevelt Av/74 St-Broadway": "Jackson Hts-Roosevelt Av",
    "Jamaica/179 St": "Jamaica-179 St",
    "Middle Village/Metropolitan Av": "Middle Village-Metropolitan Av",
    "Sutphin Blvd-Archer Av/JFK Airport": "Sutphin Blvd-Archer Av-JFK Airport",
    "Gun Hill Rd-Dyre Ave": "Gun Hill Rd",
    "Gun Hill Rd-White Plains Rd line": "Gun Hill Rd",
    "Pelham Pkwy-White Plains Rd Line": "Pelham Pkwy",
    "Tremont Ave": "Tremont Av",
    "68 St Hunter College": "68 St-Hunter College",
    "St. George": "St George",
    "14 St-Union Sq": "14 St-Union Sq",
    "Yaphank": "Yaphank-BNL",
    "Flushing-Main St": "Flushing Main Street",
    "Mount Kisco": "Mt Kisco",
    "Mount Vernon West": "Mt Vernon West",
    "Mount Vernon East": "Mt Vernon East",
    "Croton Harmon": "Croton-Harmon",
    "Yankees-E 153 Street": "Yankees-E 153 St",
    "Harlem-125 Street": "Harlem-125 St",
}

# GTFS has no rows for these (seasonal stop / NJ-Transit operated terminals)
SKIP_GTFS = {
    "Nassau Blvd", "Belmont Park", "Hoboken", "Secaucus Junction",
    "Penn Station, New York", "Campbell Hall", "Harriman", "Middletown",
    "Port Jervis", "Salisbury Mills-Cornwall", "Nanuet", "Spring Valley",
}


def norm(name: str) -> str:
    name = name.replace("\u200b", " ").replace("\xa0", " ")
    name = name.replace("St.", "St")
    return re.sub(r"\s+", " ", name).strip().casefold()


def clean(text: str) -> str:
    text = htmllib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_html() -> str:
    # NOTE: the Akamai edge in front of new.mta.info blocks the desktop
    # Chrome UA from this network (403 error page) but serves plain curl,
    # so no -A flag is passed here.
    result = subprocess.run(
        ["curl", "-sL", "--max-time", "45", UPSTREAM],
        capture_output=True, text=True, check=True)
    return result.stdout


def parse(html: str) -> dict:
    m1 = re.search(r"<h2[^>]*>\s*New York City Subway\s*</h2>", html)
    m2 = re.search(r"<h2[^>]*>\s*Long Island Rail Road\s*</h2>", html)
    m3 = re.search(r"<h2[^>]*>\s*Metro-North Railroad\s*</h2>", html)
    if not (m1 and m2 and m3):
        raise ValueError("accessible-stations page structure not recognized")

    def parse_section(body: str, icon_label: str, stop_at: str | None = None) -> dict:
        out: dict[str, list[dict]] = {}
        current = None
        for m in re.finditer(r"<h3[^>]*>(.*?)</h3>|<li[^>]*>(.*?)</li>", body, re.S):
            if m.group(1) is not None:
                heading = clean(re.sub(r"<[^>]+>", " ", m.group(1)))
                if stop_at and heading == stop_at:
                    break
                out.setdefault(heading, [])
                current = heading
                continue
            if current is None:
                continue
            li = m.group(2)
            entry = parse_li(li, icon_label)
            if entry is None or not entry["name"] or entry["name"].startswith("Bus connections"):
                continue
            out[current].append(entry)
        return out

    subway = parse_section(html[m1.end():m2.start()], "subway", stop_at="Full Station List")
    lirr = parse_section(html[m2.end():m3.start()], "rail")
    mnr = parse_section(html[m3.end():], "rail")
    for footer in ("THE MTA", "INFORMATION", "Other"):
        mnr.pop(footer, None)
    return {"subway": subway, "lirr": lirr, "mnr": mnr}


def parse_li(li: str, icon_label: str) -> dict | None:
    """Parse one <li> into a token stream of text runs and line icons.

    The upstream markup alternates station name, line-icon spans and
    qualifier text, e.g.
        14 St-Union Sq [L][N][Q][R][W] only; [4][5][6] is not accessible
        28 St [6] downtown only
        Gun Hill Rd-Dyre Ave [5]
    so the icons must be kept in positional order to know which lines the
    qualifier applies to.
    """
    tokens: list[tuple[str, str]] = []  # ('text', ...) | ('icon', LINE)
    pos = 0
    for m in re.finditer(
            rf'<span[^>]*aria-label="{icon_label} line-([a-z0-9]+)"[^>]*>.*?</span>',
            li, re.S):
        text = li[pos:m.start()]
        text = clean(re.sub(r"<[^>]+>", " ", text))
        if text:
            tokens.append(("text", text))
        tokens.append(("icon", m.group(1)))
        pos = m.end()
    tail = clean(re.sub(r"<[^>]+>", " ", li[pos:]))
    if tail:
        tokens.append(("text", tail))
    if not tokens:
        return None

    name = tokens[0][1] if tokens[0][0] == "text" else ""
    name = name.replace("\u200b", " ").strip()
    rest = tokens[1:] if name else tokens

    icons: list[str] = [t[1] for t in rest if t[0] == "icon"]
    texts = [t[1] for t in rest if t[0] == "text"]
    note = " ".join(texts).strip()
    note = note.replace("\u200b", " ")
    note = re.sub(r"\s+", " ", note).strip(" ;\u00a7").strip()

    # 'X only; Y is/are not accessible' — the icons before 'only' are the
    # accessible platforms, the rest are not. Rebuild a readable note that
    # names both groups so the station page can render it verbatim.
    accessible_lines = icons
    m = re.match(r"(.*?)\bonly\b[;,.]?\s*(.*)", note)
    if m and "not accessible" in note:
        before = m.group(1).strip()
        # count icons that appeared before the 'only' keyword: reconstruct
        # from the raw token order — icons seen while collecting text that
        # ends with the 'only' fragment.
        seen: list[str] = []
        accessible_lines = []
        for kind, value in rest:
            if kind == "icon":
                seen.append(value)
            else:
                if re.search(r"\bonly\b", value):
                    accessible_lines = seen[:]
                    break
        if not accessible_lines:
            accessible_lines = seen
        not_accessible = [x for x in icons if x not in accessible_lines]
        acc = " ".join(x.upper() for x in accessible_lines) if accessible_lines else ""
        rest_ = " ".join(x.upper() for x in not_accessible)
        verb = "is" if len(not_accessible) == 1 else "are"
        note = f"{acc} only; {rest_} {verb} not accessible" if rest_ else f"{acc} only"
    if "(" in name and ")" not in name:
        head, _, tail_frag = name.partition("(")
        name = head.strip()
        note = ("(" + tail_frag + " " + note).strip()
    return {"name": name, "lines": accessible_lines, "all_lines": icons,
            "note": note}


def main() -> None:
    html = fetch_html()
    if "MTA Accessible Stations" not in html:
        raise ValueError("unexpected page title; aborting")
    parsed = parse(html)

    # load GTFS names per agency for matching
    subway_idx: dict[str, list[dict]] = {}
    for feed in ("subway.json", "lirr.json", "metro_north.json"):
        data = json.loads((SOURCE / feed).read_text())
        agency = feed.split(".")[0]
        for st in data["stations"]:
            # index under the RAW GTFS name; the alias table maps upstream
            # accessible-list spellings onto these, never the reverse.
            key = norm(st["name"])
            subway_idx.setdefault(key, []).append(
                {"agency": agency, "id": st["id"], "name": st["name"],
                 "borough": st.get("borough", ""),
                 "lines": [str(x) for x in st.get("lines", [])]})

    matched, unmatched = [], []
    for agency, groups in parsed.items():
        for group, entries in groups.items():
            for entry in entries:
                record = {
                    "agency": agency, "group": group,
                    "name": entry["name"], "lines": entry["lines"],
                    "note": entry["note"],
                }
                target = ALIASES.get(entry["name"], entry["name"])
                # west-of-Hudson terminal entries carry a parenthetical hint
                # ('Hoboken (please arrive ...)') — treat the bare name.
                bare = target.split("(")[0].strip()
                if bare in SKIP_GTFS or bare in {
                        "Hoboken", "Secaucus Junction", "Penn Station, New York"}:
                    unmatched.append({
                        "agency": agency, "group": group,
                        "name": entry["name"], "lines": entry["lines"],
                        "note": entry["note"], "gtfs_ids": [],
                        "skipped": "not in GTFS feeds",
                    })
                    continue
                candidates = subway_idx.get(norm(target), [])
                if entry["lines"] and candidates:
                    wanted = {x.casefold() for x in entry["lines"]}
                    # exact line-set match first, then borough, then overlap
                    exact = [c for c in candidates
                             if {x.casefold() for x in c["lines"]} == wanted]
                    if exact:
                        candidates = exact
                    else:
                        by_line = [c for c in candidates
                                   if {x.casefold() for x in c["lines"]} & wanted]
                        if by_line:
                            candidates = by_line
                if agency == "subway" and len(candidates) > 1:
                    boro = group.replace("Staten Island Railway", "Staten Island").casefold()
                    same_boro = [c for c in candidates if c.get("borough", "").casefold() == boro]
                    if same_boro:
                        candidates = same_boro
                if candidates:
                    record["gtfs_ids"] = sorted({c["id"] for c in candidates})
                    record["gtfs_name"] = candidates[0]["name"]
                    matched.append(record)
                else:
                    record["gtfs_ids"] = []
                    unmatched.append(record)

    summary = {
        "source_url": UPSTREAM,
        "captured": "2026-09-23",
        "page_updated": "2026-09-14",
        "subway_count": sum(len(v) for v in parsed["subway"].values()),
        "lirr_count": sum(len(v) for v in parsed["lirr"].values()),
        "mnr_count": sum(len(v) for v in parsed["mnr"].values()),
        "stations": matched,
        "unmatched": unmatched,
    }
    SOURCE.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(f"matched={len(matched)} unmatched={len(unmatched)} "
          f"(subway={summary['subway_count']} lirr={summary['lirr_count']} "
          f"mnr={summary['mnr_count']})")
    for u in unmatched:
        print("  unmatched:", u["agency"], u["group"], repr(u["name"]),
              u.get("skipped", ""))


if __name__ == "__main__":
    main()
