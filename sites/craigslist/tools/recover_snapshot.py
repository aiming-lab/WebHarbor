"""Build-time public-source capture. Requires beautifulsoup4; never used by HTTP handlers.

Usage: python recover_snapshot.py --output /path/out [--images /path/static/images]
Captures public listing pages only. Never opens reply/contact or posting endpoints.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

SEARCHES = [
    ("furniture", "fua", "office chair", 8),
    ("furniture", "fua", "desk", 8),
    ("bikes", "bia", "commuter", 8),
    ("cars_trucks", "cta", "Honda", 10),
    ("apartments", "apa", "studio", 10),
    ("electronics", "ela", "monitor", 8),
    ("free", "zip", "moving boxes", 5),
    ("healthcare", "hea", "speech", 5),
    ("lessons", "lss", "calculus", 4),
    ("labor_move", "lbs", "moving", 5),
    ("events", "eve", "", 7),
    ("volunteers", "vol", "", 6),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, path):
    if path.exists():
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def capture_listing(item, output, images):
    category, url = item
    key = sha(url.encode())[:20]
    try:
        raw = fetch(url, output / "pages" / f"{key}.html")
        soup = BeautifulSoup(raw, "html.parser")
        title = soup.select_one("#titletextonly")
        body = soup.select_one("#postingbody")
        if not title or not body:
            raise ValueError("not a public listing page")
        for el in body.select(".print-information"):
            el.decompose()
        breadcrumbs = json.loads(soup.select_one("#ld_breadcrumb_data").string)[
            "itemListElement"
        ]
        ld = soup.select_one("#ld_posting_data")
        structured = json.loads(ld.string) if ld else {}
        attrs = {}
        for attr in soup.select(".attrgroup .attr"):
            label, value = attr.select_one(".labl"), attr.select_one(".valu")
            if label and value:
                attrs[label.get_text(" ", strip=True).rstrip(":")] = value.get_text(
                    " ", strip=True
                )
        # Housing flags also occur as standalone spans.
        extras = [x.get_text(" ", strip=True) for x in soup.select(".attrgroup > span")]
        if extras:
            attrs["additional attributes"] = "; ".join(extras)
        price_el = soup.select_one(".postingtitle .price")
        price_raw = price_el.get_text(strip=True) if price_el else ""
        price = (
            int(re.sub(r"[^0-9]", "", price_raw))
            if re.search(r"\d", price_raw)
            else None
        )
        if category == "free" and price is None:
            price = 0
        titleline = soup.select_one(".postingtitletext")
        hood = titleline.get_text(" ", strip=True) if titleline else ""
        m = re.search(r"\(([^()]*)\)\s*$", hood)
        neighborhood = (
            m.group(1)
            if m
            else structured.get("offers", {})
            .get("availableAtOrFrom", {})
            .get("address", {})
            .get("addressLocality", "")
        )
        area = next(
            (
                x["name"]
                for x in breadcrumbs
                if "/subarea/" in x.get("item", "") and "?" not in x["item"]
            ),
            "",
        )
        times = [x.get("datetime") for x in soup.select(".postinginfos time")]
        post_id = re.search(r"post id:\s*(\d+)", soup.get_text(" ", strip=True))
        photos = []
        urls = list(dict.fromkeys(a["href"] for a in soup.select("#thumbs a[href]")))
        if not urls:
            urls = structured.get("image", [])
            if isinstance(urls, str):
                urls = [urls]
        # Preserve full source gallery, not unrelated search-result crops.
        for image_url in urls:
            if urllib.parse.urlparse(image_url).hostname != "images.craigslist.org":
                continue
            filename = sha(image_url.encode())[:24] + ".jpg"
            content = fetch(image_url, images / filename)
            photos.append(
                {"url": image_url, "path": "images/" + filename, "sha256": sha(content)}
            )
        return dict(
            source_url=url,
            source_sha256=sha(raw),
            source_id=post_id.group(1) if post_id else key,
            title=title.get_text(" ", strip=True),
            description=body.get_text("\n", strip=True),
            category_slug=category,
            source_breadcrumbs=breadcrumbs,
            area=area,
            neighborhood=neighborhood,
            price=price,
            attributes=attrs,
            posted_at=times[0] if times else None,
            updated_at=times[-1] if times else None,
            photos=photos,
            source_structured=structured,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        return {"source_url": url, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.images.mkdir(parents=True, exist_ok=True)
    items = []
    searchlog = []
    for category, code, query, count in SEARCHES:
        url = (
            "https://sfbay.craigslist.org/search/"
            + code
            + "?"
            + urllib.parse.urlencode({"query": query})
        )
        try:
            raw = fetch(
                url,
                args.output / "search" / f"{category}-{query.replace(' ', '-')}.html",
            )
            soup = BeautifulSoup(raw, "html.parser")
            links = [
                x["href"] for x in soup.select("li.cl-static-search-result a[href]")
            ][:count]
            items.extend((category, link) for link in links)
            searchlog.append({"url": url, "sha256": sha(raw), "selected": links})
            print(category, query, len(links), flush=True)
        except Exception as exc:
            searchlog.append({"url": url, "error": str(exc)})
    items = list(dict.fromkeys(items))
    with ThreadPoolExecutor(max_workers=4) as executor:
        rows = list(
            executor.map(
                lambda item: capture_listing(item, args.output, args.images), items
            )
        )
    (args.output / "searches.json").write_text(json.dumps(searchlog, indent=2))
    (args.output / "listings.json").write_text(json.dumps(rows, indent=2))
    print(
        json.dumps(
            {
                "captured": sum("error" not in r for r in rows),
                "errors": [r for r in rows if "error" in r],
                "photos": sum(len(r.get("photos", [])) for r in rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
