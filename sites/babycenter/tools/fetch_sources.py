#!/usr/bin/env python3
"""Fetch the upstream source corpus for the babycenter mirror.

Every fact the site serves has to be traceable to an openly licensed upstream
document. This script pulls the source articles from the MediaWiki API and
records, per article: the canonical URL, the exact revision id, the revision
timestamp, the fetch timestamp, the licence, and a sha256 of the stored text.

Output: sites/babycenter/source_data/wikipedia/<slug>.json  (tracked in git)

Re-running the script against the same revisions is a no-op apart from
`fetched_at`, so the seed stays deterministic. Pass --check to verify the
stored revisions are still the live ones without rewriting anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"

def _ssl_context() -> ssl.SSLContext:
    """Some Python installs ship without a usable system trust store."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_SSL = _ssl_context()
UA = "WebHarbor-babycenter-source-fetch/1.0 (https://github.com/aiming-lab/WebHarbor)"
LICENCE = {
    "name": "Creative Commons Attribution-ShareAlike 4.0 International",
    "spdx": "CC-BY-SA-4.0",
    "url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "attribution": "Wikipedia contributors, English Wikipedia",
}

# The articles the mirror's content is derived from.
ARTICLES = {
    "gestational-age": "Gestational age",
    "prenatal-care": "Prenatal care",
    "prenatal-testing": "Prenatal testing",
    "pregnancy": "Pregnancy",
    "prenatal-development": "Prenatal development",
    "child-development-stages": "Child development stages",
    "breastfeeding": "Breastfeeding",
    "infant-sleep": "Infant sleep training",
}

OUT = Path(__file__).resolve().parent.parent / "source_data" / "wikipedia"


def api(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45, context=_SSL) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_article(title: str) -> dict:
    """Plain-text extract plus the revision metadata that pins it."""
    meta = api({
        "action": "query",
        "prop": "revisions|info",
        "rvprop": "ids|timestamp",
        "inprop": "url",
        "titles": title,
    })["query"]["pages"][0]
    if meta.get("missing"):
        raise SystemExit(f"article not found: {title}")
    rev = meta["revisions"][0]

    extract = api({
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "titles": title,
    })["query"]["pages"][0]["extract"]

    sections = api({
        "action": "parse",
        "page": title,
        "prop": "sections",
    })["parse"]["sections"]

    return {
        "title": meta["title"],
        "canonical_url": meta["fullurl"],
        "revision_id": rev["revid"],
        "revision_timestamp": rev["timestamp"],
        "permanent_url": f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}",
        "licence": LICENCE,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sections": [{"number": s["number"], "line": s["line"]} for s in sections],
        "text_sha256": hashlib.sha256(extract.encode("utf-8")).hexdigest(),
        "text": extract,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify stored revisions are still live; write nothing")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    drift = []
    for slug, title in ARTICLES.items():
        path = OUT / f"{slug}.json"
        if args.check:
            if not path.exists():
                drift.append(f"{slug}: not fetched yet")
                continue
            stored = json.loads(path.read_text())
            live = api({"action": "query", "prop": "revisions",
                        "rvprop": "ids", "titles": title})["query"]["pages"][0]
            live_rev = live["revisions"][0]["revid"]
            state = "current" if live_rev == stored["revision_id"] else "SUPERSEDED"
            if state != "current":
                drift.append(f"{slug}: stored r{stored['revision_id']} -> live r{live_rev}")
            print(f"{slug:28s} r{stored['revision_id']:<12} {state}")
            continue

        doc = fetch_article(title)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        print(f"{slug:28s} r{doc['revision_id']:<12} "
              f"{len(doc['text']):>7d} chars  sha {doc['text_sha256'][:12]}")

    if args.check and drift:
        print("\nDRIFT:", *drift, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
