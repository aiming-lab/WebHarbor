"""Process the frozen upstream feeds into source_data/*.json:

- all-alerts.json (MTA GTFS-realtime /Dataservice feed) -> service_alerts.json
- nyct_ene_equipments.json / nyct_ene.json / nyct_ene_upcoming.json -> elevators.json

Everything is captured verbatim from the live MTA feeds; this step only
normalizes shapes for the seed builder.
"""
from __future__ import annotations

import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRAPE = ROOT / "scraped_data"
OUT = ROOT / "source_data"

SNAPSHOT_DATE = "2026-09-23"


def process_alerts():
    data = json.loads((SCRAPE / "all-alerts.json").read_bytes())
    out = []
    for ent in data.get("entity", []):
        alert = ent.get("alert", {})
        mercury = alert.get("transit_realtime.mercury_alert", {})
        routes = []
        stops = []
        for ie in alert.get("informed_entity", []):
            if ie.get("route_id"):
                routes.append({"agency": ie.get("agency_id", ""), "route_id": ie["route_id"]})
            if ie.get("stop_id"):
                stops.append(ie["stop_id"])
        periods = []
        for ap in alert.get("active_period", []):
            periods.append({
                "start": ap.get("start"),
                "end": ap.get("end"),
            })

        def translation(field):
            for tr in alert.get(field, {}).get("translation", []):
                if tr.get("language") == "en":
                    return tr.get("text", "")
            for tr in alert.get(field, {}).get("translation", []):
                if tr.get("language") == "en-html":
                    return tr.get("text", "")
            return ""

        def html_translation(field):
            for tr in alert.get(field, {}).get("translation", []):
                if tr.get("language") == "en-html":
                    return tr.get("text", "")
            return ""

        out.append({
            "id": ent.get("id", ""),
            "alert_type": mercury.get("alert_type", ""),
            "created_at": mercury.get("created_at"),
            "updated_at": mercury.get("updated_at"),
            "routes": routes,
            "stops": stops,
            "active_period": periods,
            "header_text": translation("header_text"),
            "header_html": html_translation("header_text"),
            "description_text": translation("description_text"),
            "description_html": html_translation("description_text"),
        })
    (OUT / "service_alerts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"service_alerts.json: {len(out)} alerts")
    types = {}
    for a in out:
        types[a["alert_type"]] = types.get(a["alert_type"], 0) + 1
    print("types:", sorted(types.items(), key=lambda kv: -kv[1])[:8])


def process_elevators():
    equipment = json.loads((SCRAPE / "ene_equipments.json").read_bytes())
    outages = json.loads((SCRAPE / "ene.json").read_bytes())
    upcoming = json.loads((SCRAPE / "ene_upcoming.json").read_bytes())
    print("equipment:", len(equipment), "outage feed:", type(outages), "upcoming:", type(upcoming))

    def normalize_outage(rec):
        return rec

    if isinstance(outages, dict):
        outages = outages.get("entity", [])
    if isinstance(upcoming, dict):
        upcoming = upcoming.get("entity", [])

    out = {
        "snapshot_date": SNAPSHOT_DATE,
        "equipment": equipment,
        "outages": outages,
        "upcoming": upcoming,
    }
    (OUT / "elevators.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"elevators.json: {len(equipment)} equipment, {len(outages)} outage records, {len(upcoming)} upcoming")
    if outages:
        print("outage sample keys:", sorted(outages[0].keys())[:15] if isinstance(outages[0], dict) else outages[0])


if __name__ == "__main__":
    process_alerts()
    process_elevators()
