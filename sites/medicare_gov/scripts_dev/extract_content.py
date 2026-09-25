#!/usr/bin/env python3
"""Extract structured content blocks from saved Drupal pages (medicare.gov).

Walks the <main> region of each captured page in document order and emits
a flat list of blocks: headings, paragraphs (with inline links), bullet
lists, alerts, accordion toggles + panels and images. extract_page() then
groups accordion toggles with their panel blocks. The mirror's content
templates render these blocks, so page copy stays the real upstream text
(captured 2026-09-23).
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SCRAPED = HERE / "scraped_data"

SKIP_TAGS = {"script", "style", "nav", "header", "footer", "svg"}


class BlockCollector(HTMLParser):
    """Collect ordered content blocks from a Drupal main region."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self._skip_depth = 0
        self._mode = None
        self._buf: list[str] = []
        self._li_depth = 0
        self._li_buf: list[str] = []
        self._li_links: list[dict] = []
        self._link_target = None
        self._list_stack: list[dict] = []
        self._heading_level = 2
        self._alert_open = False

    # -- helpers ---------------------------------------------------------
    def _text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._li_buf if self._li_depth else self._buf)).strip()

    # -- parser hooks ------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if "ckeditor-accordion-toggle" in cls or "ckeditor-accordion-toggler" in cls:
            self._mode = "toggle"
            self._buf = []
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self._mode = "heading"
            self._heading_level = int(tag[1])
            self._buf = []
            return
        if tag == "p":
            if self._li_depth:
                # paragraph nested inside a list item: keep buffering the li
                return
            if self._alert_open or "ds-c-alert__body" in cls or "ds-c-alert__text" in cls:
                self._alert_open = True
                self._mode = "alert"
            else:
                self._mode = "para"
            self._buf = []
            return
        if tag in ("ul", "ol"):
            self._list_stack.append({"t": tag, "items": []})
            return
        if tag == "li":
            self._li_depth += 1
            if self._li_depth == 1:
                self._li_buf = []
                self._li_links = []
            return
        if tag == "a" and a.get("href"):
            self._link_target = a["href"]
            return
        if tag == "img" and a.get("src") and "sites/default/files" in a.get("src", ""):
            if not self._li_depth:
                self.blocks.append({"t": "image", "src": a["src"], "alt": a.get("alt", "")})

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "button" and self._mode == "toggle":
            text = self._text()
            self._buf = []
            self._mode = None
            if text:
                self.blocks.append({"t": "toggle", "text": text})
            return
        if tag in ("h1", "h2", "h3", "h4") and self._mode == "heading":
            text = self._text()
            self._buf = []
            self._mode = None
            if text:
                self.blocks.append({"t": "heading", "level": self._heading_level, "text": text})
            return
        if tag == "p":
            if self._li_depth:
                return
            if self._mode in ("para", "alert"):
                text = self._text()
                self._buf = []
                kind = self._mode
                self._mode = None
                if kind == "alert":
                    self._alert_open = False
                if text:
                    self.blocks.append({"t": kind, "text": text})
            return
        if tag == "li":
            self._li_depth = max(0, self._li_depth - 1)
            if self._li_depth == 0:
                text = re.sub(r"\s+", " ", "".join(self._li_buf)).strip()
                links, self._li_links = self._li_links, []
                self._li_buf = []
                if text or links:
                    item = {"text": text}
                    if links:
                        item["links"] = links
                    if self._list_stack:
                        self._list_stack[-1]["items"].append(item)
                    else:
                        self.blocks.append({"t": "li", "text": text})
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                finished = self._list_stack.pop()
                if finished["items"] and not self._list_stack:
                    self.blocks.append(finished)
                elif finished["items"]:
                    # nested list: attach to the parent's last item
                    parent = self._list_stack[-1]
                    if parent["items"]:
                        parent["items"][-1].setdefault("children", []).append(finished)
            return

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._li_depth:
            self._li_buf.append(data)
            return
        if self._mode in ("heading", "para", "alert", "toggle"):
            self._buf.append(data)




def extract_page(filename: str) -> dict:
    """Return {title, intro, blocks} for a saved Drupal page."""
    text = (SCRAPED / filename).read_text(encoding="utf-8")
    m = re.search(r"<main[^>]*>(.*?)</main>", text, flags=re.S)
    body = m.group(1) if m else text
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    parser = BlockCollector()
    parser.feed(body)
    raw = parser.blocks

    title = ""
    intro = ""
    kept: list[dict] = []
    for block in raw:
        if not title and block["t"] == "heading":
            title = block["text"]
            continue
        if title and not intro and block["t"] == "para":
            intro = block["text"]
            continue
        kept.append(block)

    # group accordion toggles with the blocks that follow them
    final: list[dict] = []
    i = 0
    while i < len(kept):
        block = kept[i]
        if block["t"] == "toggle":
            accordion = {"t": "accordion", "items": []}
            current = {"title": block["text"], "blocks": []}
            accordion["items"].append(current)
            i += 1
            while i < len(kept) and kept[i]["t"] != "toggle":
                nxt = kept[i]
                if nxt["t"] == "heading" and nxt.get("level", 2) <= 2:
                    break
                current["blocks"].append(nxt)
                i += 1
            final.append(accordion)
            continue
        final.append(block)
        i += 1
    return {"title": title, "intro": intro, "blocks": final}


if __name__ == "__main__":
    for fn in ["basics_rights.html", "sub_rights.html", "basics_fraud.html",
               "basics_death.html", "basics_esrd.html", "talk_to_someone.html",
               "sub_card.html", "sub_protections.html", "sub_rights_help.html",
               "sub_children_esrd.html"]:
        page = extract_page(fn)
        kinds = [b["t"] for b in page["blocks"]]
        print(f"== {fn}: title={page['title'][:50]!r} intro={page['intro'][:60]!r}")
        print("   blocks:", kinds[:22], "..." if len(kinds) > 22 else "")
        for b in page["blocks"][:3]:
            if b["t"] == "accordion":
                print("   accordion items:", [it["title"][:40] for it in b["items"]])
