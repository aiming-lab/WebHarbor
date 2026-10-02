#!/usr/bin/env python3
"""Capture the live sec.gov content that feeds the tracked source_data/*.json.

The SEC fair-access policy (https://www.sec.gov/privacy.htm#security) asks for
a declared User-Agent and <= 10 requests/second; this scraper identifies
itself and sleeps between every request. Every capture is written to
scraped_data/captures/ with a .meta.json sidecar recording the exact URL, the
HTTP status, the byte length and the UTC capture timestamp, following the
disney capture protocol. Nothing is synthesized: rows that could not be
captured are reported and skipped.

Run:  python3 scripts_dev/scrape_upstream.py   (from sites/sec)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "scraped_data" / "captures"
OUT.mkdir(parents=True, exist_ok=True)

UA = "WebHarbor Mirror Research admin@webharbor.example"
HEADERS = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SLEEP = 0.45          # ~2 req/s, well under the SEC fair-access ceiling
TIMEOUT = 40

session = requests.Session()
session.headers.update(HEADERS)

CAPTURE_LOG = []


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, binary: bool = False, allow_redirects: bool = True) -> bytes | None:
    """GET a URL, store the capture + a .meta.json sidecar, sleep politely."""
    name = urlsplit(url)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name.path.strip("/").replace("/", "__"))
    if not stem:
        stem = "root"
    stem = stem[-140:]
    path = OUT / stem
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=allow_redirects)
        status = r.status_code
        data = r.content
        final = str(r.url)
    except requests.RequestException as exc:  # pragma: no cover - network
        print(f"[capture] FAILED {url}: {exc}", file=sys.stderr)
        CAPTURE_LOG.append({"url": url, "status": None, "error": str(exc),
                            "captured_at": now_utc()})
        time.sleep(SLEEP)
        return None
    meta = {"url": url, "final_url": final, "status": status,
            "bytes": len(data), "captured_at": now_utc()}
    if status == 200:
        suffix = ".bin" if binary else ".html"
        if not path.suffix:
            path = path.with_suffix(suffix)
        path.write_bytes(data)
        Path(str(path) + ".meta.json").write_text(json.dumps(meta, indent=1))
    CAPTURE_LOG.append(meta)
    print(f"[capture] {status} {len(data):>8}B {url}")
    time.sleep(SLEEP)
    return data if status == 200 else None


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def main_content(html: str) -> str:
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    return m.group(1) if m else html


# --------------------------------------------------------------------------
# 1. Homepage
# --------------------------------------------------------------------------
def scrape_home() -> dict:
    data = fetch("https://www.sec.gov/")
    html = data.decode("utf-8", "replace")
    body = main_content(html)
    out = {"hero": {}, "quick_links": [], "material_matters": {},
           "latest_news": [], "upcoming_events": [], "investor_teaser": {}}

    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    out["hero"]["h1"] = strip_tags(m.group(1)) if m else None
    m = re.search(r"<p[^>]*>(.*?)</p>", body, re.S)
    out["hero"]["intro"] = strip_tags(m.group(1)) if m else None

    # Quick links block
    m = re.search(r'home-hero__links__list(.*?)</ul>', body, re.S)
    if m:
        for a in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S):
            label = strip_tags(a.group(2))
            if label:
                out["quick_links"].append({"label": label,
                                            "href": unescape(a.group(1))})

    # Material Matters card (first horizontal-card article)
    m = re.search(r'card-horz--spotlight(.*?)(?:</div>\s*</div>\s*</div>\s*</div>|</section>)', body, re.S)
    if m:
        card = m.group(1)
        t = re.search(r"usa-collection__heading[^>]*>\s*(.*?)\s*</h2>", card, re.S)
        d = re.search(r'usa-collection__description[^>]*>\s*(.*?)\s*</div>', card, re.S)
        img = re.search(r'src="(/files/styles/horizontal_card_x_small[^"]+)"', card)
        alt = re.search(r'alt="([^"]*)"', card)
        cta = re.search(r'card-horz__footer.*?<a[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', card, re.S)
        out["material_matters"] = {
            "title": strip_tags(t.group(1)) if t else None,
            "description": strip_tags(d.group(1)) if d else None,
            "image": unescape(img.group(1)) if img else None,
            "alt": unescape(alt.group(1)) if alt else None,
            "cta_label": strip_tags(cta.group(2)) if cta else None,
            "cta_href": unescape(cta.group(1)) if cta else None,
        }

    # Latest News collection (press releases with dates)
    m = re.search(r'Latest News</h2>(.*?)(Upcoming Events|</main>)', body, re.S)
    if m:
        for item in re.finditer(r'usa-collection__item[^>]*>(.*?)(?=<li\s|</ul>)', m.group(1), re.S):
            card = item.group(1)
            a = re.search(r'<a href="(/newsroom/press-releases/[^"]+)"[^>]*>(.*?)</a>', card, re.S)
            if not a:
                continue
            tm = re.search(r"<time[^>]*datetime=\"([^\"]+)\"[^>]*>\s*([^<]+?)\s*</time>", card, re.S)
            out["latest_news"].append({
                "href": unescape(a.group(1)),
                "label": strip_tags(a.group(2)),
                "datetime": tm.group(1) if tm else None,
                "date": strip_tags(tm.group(2)) if tm else None,
            })

    # Upcoming events (calendar chips + meeting links)
    m = re.search(r'Upcoming Events</h2>(.*?)(SEC Rulemaking|</main>)', body, re.S)
    if m:
        for item in re.finditer(r'usa-collection__item[^>]*>(.*?)(?=<li\s|</ul>)', m.group(1), re.S):
            card = item.group(1)
            a = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', card, re.S)
            if not a:
                continue
            label = strip_tags(a.group(2))
            month = re.search(r'calendar-date-month">([^<]+)<', card)
            day = re.search(r'calendar-date-day">([^<]+)<', card)
            if label:
                out["upcoming_events"].append({
                    "href": unescape(a.group(1)), "label": label,
                    "month": month.group(1) if month else None,
                    "day": day.group(1) if day else None,
                })

    # Investor.gov teaser (card with sidebar logo)
    m = re.search(r'card-with-sidebar-logo(.*?)</article>', body, re.S)
    if m:
        m2 = re.search(r'card-sidebar__text">([^<]+)<', body[m.start():], re.S)
        out["investor_teaser"]["text"] = strip_tags(m2.group(1)) if m2 else None
        a = re.search(r'card-sidebar__footer.*?<a[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
                      body[m.start():], re.S)
        out["investor_teaser"]["cta_label"] = strip_tags(a.group(2)) if a else None
        out["investor_teaser"]["cta_href"] = unescape(a.group(1)) if a else None
        img = re.search(r'src="(/files/styles/card_with_sidebar_1x[^"]+)"', m.group(1))
        out["investor_teaser"]["image"] = unescape(img.group(1)) if img else None
        seg = re.search(r'card-sidebar__sidebar__list(.*?)</ul>', body[m.start():], re.S)
        bullets = [strip_tags(li) for li in re.findall(
            r"<li[^>]*>(.*?)</li>", seg.group(1), re.S)] if seg else []
        out["investor_teaser"]["bullets"] = [b for b in bullets if b]
    # SEC Rulemaking blurb
    m = re.search(r'SEC Rulemaking(.*?)(Submit a Comment|</main>)', body, re.S)
    if m:
        ps = [strip_tags(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", m.group(1), re.S)]
        out["rulemaking"] = " ".join(p for p in ps if p)
    return out


# --------------------------------------------------------------------------
# 2. Press releases (list pages + detail pages)
# --------------------------------------------------------------------------
PRESS_FIELDS = ("newsroom/press-releases",)


def scrape_press_releases(pages: int = 2) -> list[dict]:
    rows = []
    seen = set()
    for page in range(0, pages):
        url = ("https://www.sec.gov/newsroom/press-releases"
               f"?page={page}" if page else "https://www.sec.gov/newsroom/press-releases")
        data = fetch(url)
        if not data:
            continue
        body = main_content(data.decode("utf-8", "replace"))
        for a in re.finditer(
                r'<a href="(/newsroom/press-releases/([^"]+))"[^>]*>(.*?)</a>', body, re.S):
            href, slug, label = a.group(1), a.group(2), strip_tags(a.group(3))
            if slug in seen or not label:
                continue
            seen.add(slug)
            date = None
            dm = re.search(r"([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})", label)
            if dm:
                date = dm.group(1)
            rows.append({"slug": slug, "href": href, "title": label, "date": date})
    out = []
    for row in rows:
        data = fetch("https://www.sec.gov" + row["href"])
        if not data:
            continue
        html = data.decode("utf-8", "replace")
        body = main_content(html)
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
        title = strip_tags(tm.group(1)) if tm else row["title"]
        # release number
        rnm = re.search(r'field--name-field-release-number[^>]*>\s*<div class="field__item">([^<]+)<', body)
        release_no = strip_tags(rnm.group(1)) if rnm else None
        # date from the lead-in ("Washington D.C., Sept. 30, 2026 — ")
        dm = re.search(r"Washington\s+D\.?C\.?,?\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})", body)
        date = dm.group(1) if dm else row["date"]
        # paragraphs of the body
        ps = []
        for p in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.S):
            t = strip_tags(p.group(1))
            if t and len(t) > 40 and not t.lower().startswith("return to top"):
                ps.append(t)
        # related press release links
        related = []
        for a in re.finditer(r'<a href="(/newsroom/press-releases/[^"]+)"[^>]*>(.*?)</a>',
                             body, re.S):
            if a.group(2).strip() and a.group(1) != row["href"]:
                related.append({"href": unescape(a.group(1)),
                                "label": strip_tags(a.group(2))})
        out.append({"slug": row["slug"], "title": title, "date": date,
                    "release_no": release_no,
                    "paragraphs": ps[:14], "related": related[:6]})
    return out


# --------------------------------------------------------------------------
# 3. Litigation releases / administrative proceedings / trading suspensions
# --------------------------------------------------------------------------
def scrape_table_page(url: str, kind: str) -> list[dict]:
    data = fetch(url)
    rows_out = []
    if not data:
        return rows_out
    html = data.decode("utf-8", "replace")
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        if len(cells) < 2:
            continue
        date = strip_tags(cells[0])
        if not re.search(r"\d{4}", date):
            continue
        rest = cells[1]
        links = [{"href": unescape(h), "label": strip_tags(t)}
                 for h, t in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', rest, re.S)]
        text = strip_tags(rest)
        rel = re.search(r"Release No\.\s*([A-Za-z0-9.\-]+)", text)
        fileno = re.search(r"File Number:\s*([0-9\-]+)", text)
        respondents = text
        rm = re.search(r"^(.*?)(?:Release No\.|$)", text)
        if rm:
            respondents = rm.group(1).strip().rstrip(",")
        rows_out.append({
            "kind": kind,
            "date": date,
            "respondents": respondents,
            "release_no": rel.group(1) if rel else None,
            "file_number": fileno.group(1) if fileno else None,
            "links": links,
            "text": text,
        })
    return rows_out


# --------------------------------------------------------------------------
# 4. EDGAR: submissions for a fixed set of well-known companies
# --------------------------------------------------------------------------
COMPANIES = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM",
    "V", "XOM", "WMT", "KO", "CVX", "PG", "HD", "MRK", "PEP", "BAC", "ABBV",
    "COST", "DIS", "CRM", "MCD", "CSCO", "TMO", "ACN", "ABT", "NFLX", "LIN",
    "ORCL", "INTC", "QCOM", "AMD", "IBM", "GE", "F", "GM", "BA", "CAT",
    "GS", "MS", "C", "BLK", "SCHW", "PFE", "JNJ", "UNH", "T", "VZ",
]
FORMS_KEEP = {"10-K", "10-Q", "8-K", "S-1", "S-1/A", "DEF 14A", "20-F", "40-F",
              "10-K/A", "10-Q/A", "8-K/A", "4", "SC 13D", "SC 13G", "13F-HR",
              " Form 144", "144", "S-3", "S-4", "424B2", "424B4", "FWP",
              "6-K", "11-K", "25-NSE", "POS AM", "S-8", "15-12B", "15"}


def cik10(cik: int) -> str:
    return f"{cik:010d}"


def scrape_company(cik: int, name: str, ticker: str) -> dict | None:
    url = f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json"
    data = fetch(url)
    if not data:
        return None
    d = json.loads(data)
    recent = d["filings"]["recent"]
    filings = []
    for i in range(len(recent["accessionNumber"])):
        form = recent["form"][i]
        if form not in FORMS_KEEP:
            continue
        acc = recent["accessionNumber"][i]
        acc_nodash = acc.replace("-", "")
        filings.append({
            "accession": acc,
            "form": form,
            "filed": recent["filingDate"][i],
            "report_date": recent["reportDate"][i] or None,
            "acceptance": recent.get("acceptanceDateTime", [""] * (i + 1))[i]
                           if i < len(recent.get("acceptanceDateTime", [])) else None,
            "items": recent["items"][i] or None,
            "primary_doc": recent["primaryDocument"][i],
            "primary_desc": recent["primaryDocDescription"][i],
            "file_num": recent["fileNumber"][i] or None,
            "film_num": recent["filmNumber"][i] or None,
            "size": recent["size"][i],
            "is_xbrl": bool(recent["isXBRL"][i]),
            "doc_url": (f"/Archives/edgar/data/{cik}/{acc_nodash}/"
                        f"{recent['primaryDocument'][i]}"),
        })
        if len(filings) >= 40:
            break
    return {
        "cik": cik10(cik),
        "name": d["name"],
        "ticker": ticker,
        "tickers": d.get("tickers", []),
        "exchanges": d.get("exchanges", []),
        "sic": d.get("sic"),
        "sic_description": d.get("sicDescription"),
        "state": d.get("stateOfIncorporationation") or d.get("addresses", {}).get("business", {}).get("stateOrCountry"),
        "state_of_incorporation": d.get("stateOfIncorporation"),
        "fiscal_year_end": d.get("fiscalYearEnd"),
        "category": d.get("category"),
        "description": d.get("description"),
        "website": d.get("website"),
        "ein": d.get("ein"),
        "filings": filings,
    }


def scrape_edgar_companies() -> list[dict]:
    tickers = json.loads(fetch("https://www.sec.gov/files/company_tickers.json").decode())
    by_ticker = {v["ticker"]: v for v in tickers.values()}
    out = []
    for sym in COMPANIES:
        row = by_ticker.get(sym)
        if not row:
            print(f"[edgar] no company_tickers entry for {sym}", file=sys.stderr)
            continue
        info = scrape_company(row["cik_str"], row["title"], sym)
        if info:
            out.append(info)
    return out


# --------------------------------------------------------------------------
# 5. EDGAR full-text search captures (real efts.sec.gov responses)
# --------------------------------------------------------------------------
FTS_QUERIES = [
    ("artificial intelligence", "8-K", 10),
    ("artificial intelligence", "10-K", 10),
    ("cybersecurity incident", "8-K", 10),
    ("pandemic", "10-K", 10),
    ("supply chain", "10-Q", 10),
    ("climate change", "10-K", 10),
    ("digital assets", "8-K", 10),
    ("bankruptcy", "8-K", 10),
]


def scrape_fts() -> list[dict]:
    out = []
    for q, form, size in FTS_QUERIES:
        url = ("https://efts.sec.gov/LATEST/search-index?q="
               + requests.utils.quote(f'"{q}"') + f"&forms={form}")
        data = fetch(url)
        if not data:
            continue
        d = json.loads(data)
        hits = []
        for hit in d.get("hits", {}).get("hits", [])[:size]:
            s = hit["_source"]
            hits.append({
                "id": hit["_id"],
                "score": hit.get("_score"),
                "cik": s["ciks"][0] if s.get("ciks") else None,
                "display_names": s.get("display_names", []),
                "form": s.get("form"),
                "file_date": s.get("file_date"),
                "period": s.get("period_ending"),
                "adsh": s.get("adsh"),
                "biz_states": s.get("biz_states", []),
                "sics": s.get("sics", []),
                "file_num": (s.get("file_num") or [None])[0],
                "root_forms": s.get("root_forms", []),
                "sequence": s.get("sequence"),
            })
        total = d.get("hits", {}).get("total", {})
        out.append({"query": q, "form": form,
                    "total_value": total.get("value"),
                    "total_relation": total.get("relation"),
                    "hits": hits})
    return out


# --------------------------------------------------------------------------
# 6. Forms index
# --------------------------------------------------------------------------
def scrape_forms_index() -> dict:
    data = fetch("https://www.sec.gov/submit-filings/forms-index")
    if not data:
        return {"rows": [], "facets": {}}
    html = data.decode("utf-8", "replace")
    body = main_content(html)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        links = re.findall(r'<a href="(/files/form[^"]+)"[^>]*>(.*?)</a>', tr, re.S)
        if not links:
            continue
        cells = [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        href, label = links[0][0], strip_tags(links[0][1])
        cells = [c for c in cells if c]
        row = {"pdf": href, "title": label, "cells": cells}
        if cells and len(cells[0]) <= 12 and not cells[0].startswith("Supplemental"):
            row["form"] = cells[0]
        else:
            row["form"] = None
        lu = None
        for c in cells:
            if re.fullmatch(r"(?:[A-Z][a-z]+\.?\s+)?\d{4}", c) and not re.fullmatch(r"SEC\d+", c):
                lu = c
                break
        row["last_updated"] = lu
        for c in cells:
            if re.fullmatch(r"SEC\d+", c):
                row["sec_number"] = c
                break
        else:
            row["sec_number"] = None
        rows.append(row)
    facets = {}
    for name in ("field_audience_target_id", "field_act_target_id"):
        m = re.search(rf'<select[^>]*name="{name}"[^>]*>(.*?)</select>', html, re.S)
        if m:
            opts = re.findall(r'<option value="(\d+)"[^>]*>([^<]+)<', m.group(1))
            facets[name] = [{"value": v, "label": t.strip()} for v, t in opts]
    return {"rows": rows, "facets": facets}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    t0 = time.time()
    home = scrape_home()
    (HERE / "scraped_data").mkdir(exist_ok=True)
    Path(HERE / "scraped_data" / "home.json").write_text(json.dumps(home, indent=1))

    press = scrape_press_releases(pages=4)
    Path(HERE / "scraped_data" / "press_releases.json").write_text(
        json.dumps(press, indent=1))

    lit = scrape_table_page(
        "https://www.sec.gov/enforcement-litigation/litigation-releases",
        "litigation_release")
    Path(HERE / "scraped_data" / "litigation_releases.json").write_text(
        json.dumps(lit, indent=1))

    admin = scrape_table_page(
        "https://www.sec.gov/enforcement-litigation/administrative-proceedings",
        "administrative_proceeding")
    Path(HERE / "scraped_data" / "admin_proceedings.json").write_text(
        json.dumps(admin, indent=1))

    susp = scrape_table_page(
        "https://www.sec.gov/enforcement-litigation/trading-suspensions",
        "trading_suspension")
    Path(HERE / "scraped_data" / "trading_suspensions.json").write_text(
        json.dumps(susp, indent=1))

    companies = scrape_edgar_companies()
    Path(HERE / "scraped_data" / "edgar_companies.json").write_text(
        json.dumps(companies, indent=1))

    fts = scrape_fts()
    Path(HERE / "scraped_data" / "fts_captures.json").write_text(
        json.dumps(fts, indent=1))

    forms = scrape_forms_index()
    Path(HERE / "scraped_data" / "forms_index.json").write_text(
        json.dumps(forms, indent=1))

    Path(HERE / "scraped_data" / "capture_log.json").write_text(
        json.dumps(CAPTURE_LOG, indent=1))

    failures = [c for c in CAPTURE_LOG if c.get("status") != 200]
    print(f"\n[scrape] {len(CAPTURE_LOG)} captures, {len(failures)} failures, "
          f"{time.time() - t0:.0f}s")
    for f in failures:
        print("  FAIL:", f.get("url"), f.get("status"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
