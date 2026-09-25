"""Parse the frozen GTFS feeds into source_data/stations.json + routes.json.

- subway.zip: 28 routes, 496 station complexes, transfers, wheelchair flags
- lirr.zip:   11 branches, 127 stations
- metro_north.zip: 10 branches, 113 stations

Boroughs are derived from station coordinates (NYC boroughs are
geographically disjoint; Marble Hill is special-cased back to Manhattan).
Fare zones come from railroad_fares.json (parsed from the official fare
PDFs). Timetables stay in the zips — the seed builder reads them directly.
"""
from __future__ import annotations

import csv
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
GTFS = ROOT / "source_data" / "gtfs"
OUT = ROOT / "source_data"


def read_zip(which: str, filename: str):
    with zipfile.ZipFile(GTFS / f"{which}.zip") as z:
        return list(csv.DictReader(z.read(filename).decode("utf-8-sig").splitlines()))


def borough_of(lat: float, lon: float, name: str) -> str:
    if "Marble Hill" in name:
        return "Manhattan"
    if lon < -74.05 and lat < 40.65:
        return "Staten Island"
    if lat > 40.796 and lon > -73.934:
        return "Bronx"
    if -74.02 <= lon <= -73.91 and 40.69 <= lat <= 40.88:
        return "Manhattan"
    if lon > -73.96:
        return "Queens"
    return "Brooklyn"


def harvest_subway():
    stops = read_zip("subway", "stops.txt")
    routes = read_zip("subway", "routes.txt")
    transfers = read_zip("subway", "transfers.txt")

    # station complexes (location_type=1)
    complexes = {s["stop_id"]: s for s in stops if s.get("location_type") == "1"}
    platforms = [s for s in stops if s.get("location_type") in ("", "0", None)]

    # which routes serve each complex: from trip patterns — derive from
    # stop_id prefix (platform ids are <complex><dir> e.g. 101N/101S) and
    # stop_times. We instead map platforms -> complex and then route via
    # stop_times.
    stop_times = read_zip("subway", "stop_times.txt")
    trips = read_zip("subway", "trips.txt")
    trip_route = {t["trip_id"]: t["route_id"] for t in trips}
    serving: dict[str, set] = {}
    for st in stop_times:
        sid = st["stop_id"]
        route = trip_route.get(st["trip_id"])
        if not route:
            continue
        # platform -> complex
        base = sid
        if base[-1] in "NS" and base[:-1] in complexes:
            base = base[:-1]
        serving.setdefault(base, set()).add(route)

    stations = []
    x_map = {"6X": "6", "7X": "7", "FX": "F"}
    for cid, s in complexes.items():
        lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        lines = sorted({x_map.get(r, r) for r in serving.get(cid, set())})
        # wheelchair flag: any platform of this complex
        wc = "0"
        for p in platforms:
            pid = p["stop_id"]
            base = pid[:-1] if pid[-1] in "NS" and pid[:-1] in complexes else pid
            if base == cid and p.get("wheelchair_boarding") == "1":
                wc = "1"
                break
        stations.append({
            "id": cid,
            "name": s["stop_name"],
            "lat": lat,
            "lon": lon,
            "borough": borough_of(lat, lon, s["stop_name"]),
            "lines": lines,
            "wheelchair": wc == "1",
        })

    # transfers between complexes
    transfer_pairs = set()
    for t in transfers:
        a, b = t["from_stop_id"], t["to_stop_id"]
        for x in (a, b):
            if x[-1] in "NS" and x[:-1] in complexes:
                pass
        ca = a[:-1] if a[-1] in "NS" and a[:-1] in complexes else a
        cb = b[:-1] if b[-1] in "NS" and b[:-1] in complexes else b
        if ca in complexes and cb in complexes and ca != cb:
            transfer_pairs.add(tuple(sorted((ca, cb))))

    routes_out = []
    for r in routes:
        if r["route_id"] in x_map:
            continue  # express service patterns, folded into their base line
        routes_out.append({
            "id": r["route_id"],
            "name": r.get("route_long_name") or r.get("route_short_name"),
            "desc": r.get("route_desc", ""),
            "color": "#" + (r.get("route_color") or "000000"),
            "text_color": "#" + (r.get("route_text_color") or "FFFFFF"),
            "url": r.get("route_url", ""),
        })

    return {
        "routes": routes_out,
        "stations": stations,
        "transfers": sorted(list(p) for p in transfer_pairs),
    }


def harvest_railroad(which: str, fares_key: str):
    stops = read_zip(which, "stops.txt")
    routes = read_zip(which, "routes.txt")
    fares = json.loads((OUT / "railroad_fares.json").read_text())
    zone_map = fares[fares_key]["stations"] if fares_key in fares else {}

    stations = []
    for s in stops:
        name = s["stop_name"].strip()
        stations.append({
            "id": s["stop_id"],
            "name": name,
            "lat": float(s["stop_lat"]),
            "lon": float(s["stop_lon"]),
            "zone": zone_map.get(name),
            "wheelchair": s.get("wheelchair_boarding") == "1",
            "url": s.get("stop_url", ""),
        })
    routes_out = []
    for r in routes:
        routes_out.append({
            "id": r["route_id"],
            "name": r.get("route_long_name") or r.get("route_short_name"),
            "color": "#" + (r.get("route_color") or "000000"),
        })
    return {"routes": routes_out, "stations": stations}


def harvest():
    subway = harvest_subway()
    print("subway routes:", len(subway["routes"]), "stations:", len(subway["stations"]),
          "transfers:", len(subway["transfers"]))
    (OUT / "subway.json").write_text(json.dumps(subway, indent=1, ensure_ascii=False))

    lirr = harvest_railroad("lirr", "lirr")
    print("LIRR routes:", len(lirr["routes"]), "stations:", len(lirr["stations"]),
          "with zone:", sum(1 for s in lirr["stations"] if s["zone"]))
    (OUT / "lirr.json").write_text(json.dumps(lirr, indent=1, ensure_ascii=False))

    # Metro-North: merge the three fare tables into one zone map
    fares = json.loads((OUT / "railroad_fares.json").read_text())
    zone_map: dict[str, str] = {}
    for sec in fares["mnr_harlem_hudson"]:
        for st in sec["stations"]:
            zone_map[st] = sec["zone"]
    for sec in fares["mnr_newhaven"]:
        for st in sec["stations"]:
            zone_map[st] = sec["zone"]
    mnr = harvest_railroad("metro_north", "unused")
    for s in mnr["stations"]:
        s["zone"] = zone_map.get(s["name"])
    print("MNR routes:", len(mnr["routes"]), "stations:", len(mnr["stations"]),
          "with zone:", sum(1 for s in mnr["stations"] if s["zone"]))
    (OUT / "metro_north.json").write_text(json.dumps(mnr, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    harvest()
