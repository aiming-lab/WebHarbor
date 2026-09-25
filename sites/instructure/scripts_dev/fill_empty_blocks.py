#!/usr/bin/env python3
"""Fill empty body blocks in source_data_resources.json from upstream pages.

A body block is "empty" when it carries a heading but no text and no html —
the detail template then renders an orphan heading with no content (review
finding F3: 87 resources, 97 empty blocks).

For every affected resource the script fetches the live upstream detail page
and, walking the Drupal paragraph DOM in document order, rebuilds:

  * h2.field.heading sections          -> heading text and, associated with the
    most recent heading, either the paragraph--type--text description
    (kept as <p> html) or the paragraph--type--text-list items (kept as a
    <ul>), exactly like the already-populated blocks in the source file;
  * paragraph--type--quote            -> quote text + attribution + title.

Each empty source block is then matched (case/punctuation-insensitive)
against the parsed sections. Quote-like headings — the scraper stored the
quote sentence itself as the heading — become pull-quote blocks: the heading
is emptied and the html becomes a styled blockquote. Unmatched blocks are
reported and left untouched for manual review.

Run with the repo agent_demo venv (bs4 + requests):
  agent_demo/.venv/bin/python scripts_dev/fill_empty_blocks.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

SITE_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC = SITE_DIR / "source_data_resources.json"
BASE = "https://www.instructure.com"
UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")}
SLEEP = 0.4
QUOTE_HTML = ('<blockquote class="pull-quote"><p>%s</p>'
              '<footer><strong>%s</strong><span>%s</span></footer></blockquote>')


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", (text or "").lower())).strip()


def block_is_empty(block: dict) -> bool:
    has_heading = bool((block.get("heading") or "").strip())
    has_body = bool((block.get("text") or "").strip()
                    or (block.get("html") or "").strip())
    return has_heading and not has_body


def parse_page(html: str):
    """Return (sections, quotes, callouts, statements, quote_anchors).

    sections:       {norm(heading): {"html": str, "text": str, "items": [str]}}
    quotes:         [{"quote": str, "name": str, "title": str}]
    callouts:       [{"text": str, "html": str}]  # text paragraphs without their own h2
    statements:     [{"text": str, "invert": bool}]  # h2-only text paragraphs
    quote_anchors:  [norm(last h2 text before the quote)] aligned with quotes
    """
    soup = BeautifulSoup(html, "html.parser")
    sections: dict = {}
    quotes: list = []
    callouts: list = []
    statements: list = []
    quote_anchors: list = []
    current = None

    for el in soup.find_all(True):
        classes = el.get("class") or []
        cls = " ".join(classes)
        if el.name == "h2" and "field" in classes and "heading" in classes:
            title = el.get_text(" ", strip=True)
            key = norm(title)
            if key and key not in sections:
                sections[key] = {"html": "", "text": "", "items": []}
            current = key
            continue
        if "paragraph--type--text" in cls and "paragraph--type--text-list" not in cls:
            head = el.find("h2", class_="heading")
            desc = el.find(class_="field--name-field-description")
            if head is not None and desc is None:
                # heading-only text paragraph: upstream renders the heading
                # itself as the content (inverted statement callouts)
                statements.append({
                    "text": head.get_text(" ", strip=True),
                    "invert": "invert" in cls,
                })
                continue
            if head is not None:
                title = head.get_text(" ", strip=True)
                key = norm(title)
                if key and key not in sections:
                    sections[key] = {"html": "", "text": "", "items": []}
                current = key
                if desc is not None:
                    sec = sections[current]
                    inner = desc.decode_contents().strip()
                    sec["html"] += ("" if not sec["html"] else "\n") + inner
                    sec["text"] += ("" if not sec["text"] else " ") + desc.get_text(" ", strip=True)
            else:
                # heading-less inverted text paragraph: a standalone callout,
                # never part of the previous section
                if desc is not None:
                    callouts.append({
                        "text": desc.get_text(" ", strip=True),
                        "html": desc.decode_contents().strip(),
                    })
            continue
        if "paragraph--type--text-list" in cls and current:
            sec = sections[current]
            for item in el.select(".field--name-field-text-list-item .field__item"):
                text = item.get_text(" ", strip=True)
                if text:
                    sec["items"].append(text)
            continue
        if "paragraph--type--quote" in cls:
            quote = el.find(class_="field--name-field-quote")
            name = el.find(class_="field--name-field-attribution")
            title = el.find(class_="field--name-field-attribution-description")
            quotes.append({
                "quote": quote.get_text(" ", strip=True) if quote else "",
                "name": name.get_text(" ", strip=True) if name else "",
                "title": title.get_text(" ", strip=True) if title else "",
            })
            quote_anchors.append(current or "")
    return sections, quotes, callouts, statements, quote_anchors


def escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fill_block(block: dict, sections: dict, quotes: list, callouts: list,
               statements: list) -> str:
    """Fill one empty block in place; return the fill mode used."""
    key = norm(block["heading"])

    sec = sections.get(key)
    if sec:
        if sec["items"]:
            items = [escape(i) for i in sec["items"]]
            block["html"] = "<ul>\n<li>%s</li>\n</ul>" % "</li>\n<li>".join(items)
            block["text"] = " ".join(sec["items"])
            return "text-list"
        if sec["html"].strip():
            block["html"] = sec["html"].strip()
            block["text"] = sec["text"].strip()
            return "text"

    for q in quotes:
        nq = norm(q["quote"])
        nb = norm(block["heading"])
        if not nq or not nb:
            continue
        if nq == nb or nq.startswith(nb[:40]) or nb.startswith(nq[:40]):
            block["heading"] = ""
            block["text"] = q["quote"]
            block["html"] = QUOTE_HTML % (escape(q["quote"]), escape(q["name"]),
                                          escape(q["title"]))
            return "quote"

    for c in callouts:
        nc = norm(c["text"])
        nb = norm(block["heading"])
        if not nc or not nb:
            continue
        if nc == nb or nc.startswith(nb[:40]) or nb.startswith(nc[:40]):
            block["heading"] = ""
            block["text"] = c["text"]
            block["html"] = '<div class="callout-text">%s</div>' % c["html"]
            return "callout"

    for s in statements:
        ns = norm(s["text"])
        nb = norm(block["heading"])
        if not ns or not nb:
            continue
        if ns == nb or ns.startswith(nb[:40]) or nb.startswith(ns[:40]):
            if s["invert"]:
                block["heading"] = ""
                block["text"] = s["text"]
                block["html"] = '<div class="callout-text">%s</div>' % escape(s["text"])
                return "statement"
            return "kept-bare-h2"

    return "unmatched"


# CTA headings the scraper lifted from upstream download buttons; the mirror
# hosts no gated PDF for these case studies, so the orphan label is dropped.
DELETE_HEADINGS = {"download case study"}
# Bare section headers whose following subsection blocks are already populated
# (upstream renders the same bare h2); kept as-is for fidelity.
KEEP_HEADINGS = {"district stories"}


def insert_missing_quotes(row: dict, quotes: list, quote_anchors: list,
                          report: dict) -> None:
    """Append upstream pull-quote blocks the scraper never captured.

    Each quote is inserted right after the body block whose heading matches
    the upstream section heading that immediately precedes the quote.
    """
    body = row.get("body") or []
    existing = {norm(b.get("text") or "") for b in body if b.get("text")}
    pending: dict = {}
    skipped = []
    for q, anchor in zip(quotes, quote_anchors):
        if not q["quote"]:
            continue
        if norm(q["quote"]) in existing:
            continue
        key = anchor
        if not key:
            # page-top quote: goes after the leading heading-less intro block
            key = "__intro__"
        pending.setdefault(key, []).append({
            "heading": "",
            "text": q["quote"],
            "html": QUOTE_HTML % (escape(q["quote"]), escape(q["name"]),
                                  escape(q["title"])),
        })
    if not pending:
        return
    new_body = []
    used = set()

    intro_done = "__intro__" not in pending
    for b in body:
        new_body.append(b)
        if not intro_done and not (b.get("heading") or "").strip():
            for qb in pending["__intro__"]:
                new_body.append(qb)
                report["inserted_quotes"] = report.get("inserted_quotes", 0) + 1
            used.add("__intro__")
            intro_done = True
        key = norm(b.get("heading") or "") or norm(b.get("text") or "")
        if key in pending and key not in used:
            used.add(key)
            for qb in pending[key]:
                new_body.append(qb)
                report["inserted_quotes"] = report.get("inserted_quotes", 0) + 1
    # anchors that never matched a body heading keep the quotes out; log them
    for key, qbs in pending.items():
        if key not in used:
            skipped.extend(qb["text"][:60] for qb in qbs)
    row["body"] = new_body
    if skipped:
        report.setdefault("quote_skips", {})[row["href"]] = skipped


def main() -> None:
    with open(SRC) as f:
        rows = json.load(f)

    targets = []
    for idx, row in enumerate(rows):
        empties = [i for i, b in enumerate(row.get("body") or [])
                   if block_is_empty(b)]
        if empties:
            targets.append((idx, row, empties))
    print(f"resources with empty blocks: {len(targets)}")

    session = requests.Session()
    session.headers.update(UA)
    report = {"filled": {}, "unmatched": {}, "errors": {}}

    for idx, row, empties in targets:
        url = BASE + row["href"]
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            report["errors"][row["href"]] = f"{type(exc).__name__}: {exc}"
            print(f"  FETCH FAIL {row['href']}: {exc}")
            continue
        sections, quotes, callouts, statements, quote_anchors = parse_page(resp.text)
        for pos in empties:
            block = row["body"][pos]
            if norm(block["heading"]) in DELETE_HEADINGS:
                row["body"][pos] = None
                label = row["href"]
                report["filled"].setdefault(label, []).append("deleted-cta")
                continue
            if norm(block["heading"]) in KEEP_HEADINGS:
                label = row["href"]
                report["filled"].setdefault(label, []).append("kept-bare-section")
                continue
            mode = fill_block(block, sections, quotes, callouts, statements)
            label = row["href"]
            if mode == "unmatched":
                report["unmatched"].setdefault(label, []).append(block["heading"])
                print(f"  UNMATCHED {label} :: {block['heading'][:70]}")
            else:
                report["filled"].setdefault(label, []).append(mode)
        row["body"] = [b for b in row["body"] if b is not None]
        insert_missing_quotes(row, quotes, quote_anchors, report)
        time.sleep(SLEEP)

    with open(SRC, "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
        f.write("\n")

    with open("/tmp/fill_empty_blocks_report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    total_filled = sum(len(v) for v in report["filled"].values())
    total_unmatched = sum(len(v) for v in report["unmatched"].values())
    print(f"blocks filled: {total_filled} | unmatched: {total_unmatched} | "
          f"fetch errors: {len(report['errors'])}")

    # post-check: how many empty blocks remain
    with open(SRC) as f:
        rows = json.load(f)
    remaining = sum(block_is_empty(b) for r in rows for b in (r.get("body") or []))
    print(f"empty blocks remaining: {remaining}")

    if report["unmatched"]:
        print("unmatched detail:", file=sys.stderr)
        for href, heads in report["unmatched"].items():
            print(f"  {href}", file=sys.stderr)
            for h in heads:
                print(f"    - {h[:100]}", file=sys.stderr)


if __name__ == "__main__":
    main()
