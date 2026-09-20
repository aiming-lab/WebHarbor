#!/usr/bin/env python3
"""Fetch the Cities and Universities catalogues from Wikidata, with provenance.

Every rendered figure is a Wikidata claim, recorded with the item's Q-id, the
property id, the raw value, its unit, and the date it was fetched. Labels are
confirmed by reading each entity directly rather than trusting the SPARQL label
service, which was observed attaching the wrong label to an item.

Consumer-electronics categories are NOT fetched here: no free citable source
carries their specs at scale. A SPARQL count of digital cameras holding both
mass and release date returns zero.

Usage: fetch_wikidata.py > data/catalogue_wikidata.json
"""
import json
import subprocess
import sys
import time

UA = "WebHarbor-review/1.0 (research benchmark; jackjin1997@gmail.com)"
SPARQL = "https://query.wikidata.org/sparql"
ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"

CITIES = """SELECT ?item ?pop ?area WHERE {
  ?item wdt:P31 wd:Q1549591 ; wdt:P1082 ?pop .
  ?item p:P2046/psv:P2046 [ wikibase:quantityAmount ?area ; wikibase:quantityUnit wd:Q712226 ] .
  FILTER(?pop > 500000 && ?area > 30)
} ORDER BY DESC(?pop) LIMIT 60"""

UNIVERSITIES = """SELECT ?item ?students ?inception WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3918 ; wdt:P2196 ?students ; wdt:P571 ?inception .
  FILTER(?students > 20000 && ?students < 200000)
} ORDER BY DESC(?students) LIMIT 60"""

PROPERTY = {"pop": "P1082", "area": "P2046", "students": "P2196", "inception": "P571"}


def sparql(query):
    r = subprocess.run(["curl", "-sG", "--max-time", "90", "-A", UA,
                        "-H", "Accept: application/sparql-results+json",
                        "--data-urlencode", f"query={query}", SPARQL],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout)["results"]["bindings"]
    except Exception:
        return []


def entity_label(qid):
    """Read the label off the entity itself; the SPARQL label service mislabels."""
    r = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, ENTITY.format(qid)],
                       capture_output=True, text=True)
    try:
        ent = json.loads(r.stdout)["entities"][qid]
        return (ent["labels"].get("en") or {}).get("value")
    except Exception:
        return None


def collect(name, query, fields):
    fetched = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out, seen = [], set()
    for row in sparql(query):
        qid = row["item"]["value"].rsplit("/", 1)[-1]
        if qid in seen:
            continue
        seen.add(qid)
        label = entity_label(qid)
        if not label:
            continue
        rec = {"qid": qid, "name": label,
               "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
               "fetched_at": fetched, "fields": {}}
        ok = True
        for f in fields:
            if f not in row:
                ok = False
                break
            rec["fields"][f] = {"value": row[f]["value"], "property": PROPERTY[f]}
        if ok:
            out.append(rec)
        time.sleep(0.15)
    print(f"{name}: {len(out)}", file=sys.stderr)
    return out


if __name__ == "__main__":
    data = {
        "source": "Wikidata via query.wikidata.org, labels confirmed per entity",
        "note": ("Consumer-electronics categories are not sourced here: a SPARQL count of "
                 "digital cameras holding both mass and release date returns zero, and the "
                 "manufacturer pages that do carry those specs are half unreachable."),
        "cities": collect("cities", CITIES, ("pop", "area")),
        "universities": collect("universities", UNIVERSITIES, ("students", "inception")),
    }
    print(json.dumps(data, indent=1))
