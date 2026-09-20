#!/usr/bin/env python3
"""Build the Versus catalogue from citable sources, with provenance per field.

Every rendered number that claims to be a real-world fact -- price, release year,
weight, battery life, display size, megapixels, burst speed, VRAM, power draw --
is extracted from a Wikipedia revision and stored next to the revision id and the
raw text it came from. Nothing is filled in from memory: a candidate whose fields
cannot be extracted is not added to the catalogue.

The scores (Versus Score, camera/ANC/fitness score, benchmark points) are NOT
sourced. They are synthetic benchmark values and are marked as such in the
output and documented in NOTICE.md.

Usage: build_catalogue.py > data/catalogue.json
"""
import json
import re
import subprocess
import sys
import urllib.parse

UA = "WebHarbor-review/1.0 (research benchmark; jackjin1997@gmail.com)"
API = "https://en.wikipedia.org/w/api.php"


def revision(title):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "revisions",
                                "rvprop": "content|ids", "rvslots": "main",
                                "titles": title, "redirects": 1})
    r = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, f"{API}?{q}"],
                       capture_output=True, text=True)
    try:
        page = list(json.loads(r.stdout)["query"]["pages"].values())[0]
        rev = page["revisions"][0]
        return rev["slots"]["main"]["*"], rev["revid"], page["title"]
    except Exception:
        return None, None, None


def raw_field(text, *names):
    for name in names:
        m = re.search(rf"^\s*\|\s*{name}\s*=\s*(.+)$", text, re.I | re.M)
        if m:
            return re.sub(r"<ref[^>]*>.*?</ref>|<ref[^/]*/>|<[^>]+>|\[\[|\]\]|'''", " ",
                          m.group(1)).strip()
    return None


def first_number(s, pattern=r"(\d[\d,]*\.?\d*)"):
    if not s:
        return None
    m = re.search(pattern, s.replace(",", ""))
    return float(m.group(1)) if m else None


def usd(s):
    """US list price. Explicitly ignores other currencies rather than converting."""
    if not s:
        return None
    m = re.search(r"US\$\s?(\d[\d,]*\.?\d*)|USD\s?(\d[\d,]*\.?\d*)|\$(\d[\d,]*\.?\d*)", s)
    if not m:
        return None
    return round(float(next(g for g in m.groups() if g).replace(",", "")))


def year(s):
    m = re.search(r"\b(20\d{2})\b", s or "")
    return int(m.group(1)) if m else None


def grams(s):
    if not s:
        return None
    m = re.search(r"(\d[\d,]*\.?\d*)\s*(?:g\b|grams?)", s, re.I)
    return float(m.group(1).replace(",", "")) if m else None


def extract(title, wants):
    text, rev, resolved = revision(title)
    if not text:
        return None
    src = f"https://en.wikipedia.org/w/index.php?oldid={rev}"
    out = {"wikipedia_title": resolved, "revision_id": rev, "source_url": src, "fields": {}}
    for key, (names, parse) in wants.items():
        raw = raw_field(text, *names)
        value = parse(raw) if raw else None
        if value is None:
            return None            # a missing field disqualifies the candidate
        out["fields"][key] = {"value": value, "raw": raw[:160], "source_url": src}
    return out


if __name__ == "__main__":
    print(json.dumps({"note": "run with a candidate list; see probe_candidates.py"}, indent=2))
