#!/usr/bin/env python3
"""Enrich thin resource snapshots with body content from the scraped detail pages.

The upstream detail pages for ebooks, videos, webinars, research reports,
infographics, product overviews, and podcasts render an introduction, feature
lists, tables, and (for webinars) speaker blocks. The first harvest pass stored
listing-level snapshots (title/tags/card image) for 301 of the 700 resources
without those bodies. This script merges the parsed detail-page bodies from
scraped_data/records_*.json into source_data_resources.json so the detail
routes render the full upstream content.

Run from sites/instructure:  python3 scripts_dev/enrich_bodies.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = HERE / "source_data_resources.json"
SCRAP = HERE / "scraped_data"

SEG_OF_TYPE = {
    "blog": "blog", "ebook": "ebooks", "video": "videos",
    "webinar": "webinars", "case_study": "case-studies",
    "research_report": "research-reports", "infographic": "infographic",
    "podcast": "podcast", "product_overview": "product-overviews",
    "ai_resource": "artificial-intelligence",
}


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def blocks_to_body(blocks: list[dict]) -> list[dict]:
    """Convert {kind,text} parse blocks into {heading,text,html} seed blocks."""
    out: list[dict] = []
    current: dict | None = None
    open_ul = False

    def flush():
        nonlocal current, open_ul
        if open_ul:
            current["html"] += "</ul>"
            open_ul = False
        if current and (current["html"] or current["heading"]):
            current["text"] = re.sub(r"\s+", " ", current["text"]).strip()
            out.append(current)
        current = None

    for block in blocks:
        kind = block.get("kind")
        text = re.sub(r"\s+", " ", block.get("text") or "").strip()
        if not text:
            continue
        if kind in ("h2", "h3"):
            flush()
            current = {"heading": text, "text": text, "html": ""}
        else:
            if current is None:
                current = {"heading": "", "text": "", "html": ""}
            current["text"] += " " + text
            if kind == "li":
                if not open_ul:
                    current["html"] += "<ul>"
                    open_ul = True
                current["html"] += f"<li>{esc(text)}</li>"
            else:
                if open_ul:
                    current["html"] += "</ul>"
                    open_ul = False
                current["html"] += f"<p>{esc(text)}</p>"
    flush()
    return out


def table_to_block(table: dict) -> dict:
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body_html = ""
    for row in rows:
        body_html += "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
    return {
        "heading": "",
        "text": " ".join(" ".join(r) for r in rows)[:4000],
        "html": (f'<table class="data-table"><thead><tr>{thead}</tr></thead>'
                 f"<tbody>{body_html}</tbody></table>"),
    }


def speakers_to_block(speakers: list[dict]) -> dict:
    parts = []
    for s in speakers:
        name = esc(s.get("name") or "")
        role = esc(s.get("role") or "")
        parts.append(f'<p><strong>{name}</strong> — {role}</p>')
    return {"heading": "Featured Speakers", "text": " ".join(
        f"{s.get('name')} {s.get('role')}" for s in speakers)[:1000],
        "html": "".join(parts)}


def load_my_records() -> dict[tuple[str, str], dict]:
    """Index parsed detail records by (type, url-tail slug)."""
    out: dict[tuple[str, str], dict] = {}
    for f in sorted(SCRAP.glob("records_*.json")):
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for r in rows:
            rtype = r.get("type")
            slug = (r.get("slug") or "").strip("/").split("/")[-1]
            if rtype and slug and (rtype, slug) not in out:
                out[(rtype, slug)] = r
    return out


def main() -> int:
    resources = json.loads(SRC.read_text(encoding="utf-8"))
    mine = load_my_records()
    n_enriched = n_missing = 0
    for row in resources:
        existing = row.get("body") or []
        existing_text = sum(len((b.get("text") or "") + (b.get("html") or ""))
                            for b in existing)
        has_content = bool(existing) or \
            bool((row.get("case_study") or {}).get("stats")) or \
            bool((row.get("case_study") or {}).get("intro"))
        tail = (row.get("href") or "").rstrip("/").split("/")[-1]
        rec = mine.get((row.get("type"), tail))
        cand_blocks = blocks_to_body(rec.get("body_blocks") or []) if rec else []
        cand_text = sum(len(b.get("text") or "") + len(b.get("html") or "")
                        for b in cand_blocks)
        # enrich when the row is thin, or when the scraped body clearly has
        # more upstream content than the captured one
        if has_content and not (cand_text > max(existing_text * 2, existing_text + 400)):
            continue
        if not rec:
            if not has_content:
                n_missing += 1
            continue
        body: list[dict] = []
        blocks = rec.get("body_blocks") or []
        body.extend(blocks_to_body(blocks))
        if rec.get("table"):
            body.append(table_to_block(rec["table"]))
        if rec.get("speakers"):
            body.append(speakers_to_block(rec["speakers"]))
        if not body:
            if not has_content:
                n_missing += 1
            continue
        row["body"] = body
        if rec.get("published") and not row.get("date"):
            row["date"] = rec["published"]
        transcript = (rec.get("transcript") or "").strip()
        if transcript and not (row.get("media") or {}).get("transcript"):
            row.setdefault("media", {})["transcript"] = transcript
        n_enriched += 1
    SRC.write_text(json.dumps(resources, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    thin_left = sum(
        1 for r in resources
        if not r.get("body") and not (r.get("case_study") or {}).get("stats")
        and not (r.get("case_study") or {}).get("intro"))
    print(f"[enrich] enriched {n_enriched} thin records; "
          f"{n_missing} had no scraped detail; {thin_left} remain thin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
