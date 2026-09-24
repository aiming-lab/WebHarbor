#!/usr/bin/env python3
"""Stage 8: consolidate all captured upstream data into source_data.json.

Merges the scraped artifacts (products, PDP parses, quick-view payloads,
Junip reviews, collections + memberships, homepage section map, blog
articles, storefront pages, Drinks compliance payloads) into the single
tracked snapshot that seed_data.py materializes into the SQLite seed.

Deterministic: no wall clock, no randomness. Every relative date is pinned to
MIRROR_DATE = 2026-09-22.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
SITE = "macyswineshop.com"
CDN_ROOT = "https://cdn.shopify.com/s/files/1/0737/9602/6657"
CDN = CDN_ROOT + "/files"
MIRROR_DATE = "2026-09-22"

NAV_COLLECTIONS = {
    "all-wine": "Wine",
    "red-wine": "Red Wines",
    "white-wine": "White Wines",
    "rose-wine": "Rosé Wines",
    "sparkling-wine": "Sparkling Wines",
    "non-alcoholic-wines": "Non-Alcoholic Wines",
    "ready-to-drink-cocktails": "Ready-to-Drink Cocktails",
    "new-arrivals": "New Arrivals",
    "on-sale-and-clearance": "On Sale",
    "beyond-the-familiar": "Beyond The Familiar",
    "sustainable": "Sustainable Wines",
    "moscato-other-sweet-wines": "Seasonal Sweet Wines",
    "sommeliers-choice": "Sommelier’s Choice",
    "customer-favorites": "Customer Favorites",
    "shop-all-wine-sets": "Shop All Wine Sets",
    "3-bottle-wine-sets": "3-Bottle Wine Sets",
    "6-bottle-wine-sets": "6-Bottle Wine Sets",
    "12-bottle-wine-sets": "12-Bottle Wine Sets",
    "luxe-gifts": "Luxe Gifts",
    "wine-sets-under-50": "Wine Sets Under $50",
    "wine-sets-under-100": "Wine Sets Under $100",
    "martha-stewart-wine-collection": "Martha Stewart",
    "award-winners": "Award Winners",
    "90-rated-wine-under-20": "90+ Rated Under $20",
    "winter-warming-reds": "Winter Warming Reds",
    "festive-vines-pumpkin-spice-chardonnay": "Pumpkin Spice Chardonnay",
}

WINE_VARIETALS = [
    "Cabernet Sauvignon", "Malbec", "Merlot", "Pinot Noir", "Red Blend",
    "Sangiovese", "Syrah/Shiraz", "Zinfandel", "Chardonnay",
    "Pinot Grigio/Pinot Gris", "Riesling", "Sauvignon Blanc", "White Blend",
]

WINE_COUNTRIES = ["Argentina", "Australia", "Chile", "France", "Italy",
                  "Portugal", "South Africa", "Spain", "United States",
                  "Austria", "Germany", "New Zealand"]


def load(name):
    return json.loads((OUT / name).read_text())


def bottle_count_from_option(option: str, product_type: str) -> int:
    m = re.match(r"\s*(\d+)[\s-]*(pack|bottle)", (option or "").lower())
    if m:
        return int(m.group(1))
    if product_type == "Pack":
        m2 = re.search(r"(\d+)[\s-]*pack", (option or "").lower())
        if m2:
            return int(m2.group(1))
    return 1


def gift_amount_from_title(title: str):
    m = re.search(r"\$(\d+(?:\.\d{2})?)", title or "")
    return float(m.group(1)) if m else 0.0


def normalize_image(url: str, width: int | None = None) -> str:
    url = (url or "").strip().replace("&amp;", "&")
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if "/cdn/shop/" in url:
        # canonical cdn.shopify.com form
        url = re.sub(r"^https?://[^/]+/cdn/shop/(files/.+)$",
                     lambda m: f"{CDN_ROOT}/{m.group(1)}", url)
    if width:
        sep = "&" if "?" in url else "?"
        if "width=" not in url:
            url = f"{url}{sep}width={width}"
        else:
            url = re.sub(r"width=\d+", f"width={width}", url)
    return url


def build_products(qv: dict, pdp: dict, junip: dict, memberships: dict) -> list:
    raw = load("products_visible.json")
    out = []
    for rank, p in enumerate(raw):
        handle = p["handle"]
        parse = pdp.get(handle, {})
        tags = {}
        for tag in p.get("tags") or []:
            if ":" in tag:
                key, value = tag.split(":", 1)
                tags.setdefault(key.strip(), []).append(value.strip())
        variants_out = []
        for pos, v in enumerate(p.get("variants") or []):
            option = v.get("title") or v.get("option1") or "Default Title"
            ptype = p.get("product_type") or "Bottle"
            bcount = bottle_count_from_option(option, ptype)
            gift = gift_amount_from_title(option) if p.get("product_type") == "Gift Card" else 0.0
            price = float(v.get("price") or 0)
            compare = float(v.get("compare_at_price") or 0) or price
            variants_out.append({
                "upstream_id": str(v.get("id")),
                "title": option,
                "label": re.sub(r"^\s*(\d+)[\s-]*pack\s*:?\s*$", r"\1 Pack", option, flags=re.I).strip() or option,
                "price": price,
                "compare_at_price": compare,
                "sku": v.get("sku") or "",
                "available": bool(v.get("available", True)),
                "bottle_count": bcount,
                "position": pos,
                "available_states": v.get("availableStates") or [],
                "gift_amount": gift,
            })
        price = min((v["price"] for v in variants_out), default=0.0)
        compare = min((v["compare_at_price"] for v in variants_out), default=0.0)
        on_sale = any(v["price"] < v["compare_at_price"] for v in variants_out)
        pct_off = 0
        if compare > price > 0:
            pct_off = int(round((compare - price) / compare * 100))

        images = []
        for pos, img in enumerate(p.get("images") or []):
            src = normalize_image(img.get("src", ""), 800)
            ext = ".png" if ".png" in src.lower() else (
                ".webp" if ".webp" in src.lower() else ".jpg")
            images.append({
                "path": f"products/{handle}-{pos + 1:02d}{ext}",
                "source_url": src,
                "alt": img.get("alt") or p["title"],
            })

        specs = parse.get("specs") or {}
        subheading = (qv.get(handle) or {}).get("subheading") or ""

        case_contents = {}
        for vid, case in (parse.get("case_contents") or {}).items():
            bottles = []
            for b in case.get("bottles") or []:
                q = b.get("quickview") or {}
                specs_b = b.get("specs") or {}
                raw = b.get("image", "").split("/")[-1].split("?")[0]
                stem = re.sub(r"\.(png|jpe?g|webp)$", "", raw, flags=re.I)
                slug = re.sub(r"[^a-z0-9-]+", "-", stem.lower()).strip("-")
                bottles.append({
                    "number": b.get("number"),
                    "title": b.get("title"),
                    "image_path": f"bottles/{slug or 'bottle'}.png",
                    "image_source_url": normalize_image(b.get("image", ""), 300),
                    "winery": q.get("winery") or specs_b.get("Winery") or "",
                    "varietal": q.get("varietal") or specs_b.get("Varietal") or "",
                    "year": q.get("year") or specs_b.get("Year") or "",
                    "type": q.get("type") or specs_b.get("Type") or "Bottle",
                    "abv": q.get("abv") or specs_b.get("ABV") or "",
                    "country": q.get("country") or specs_b.get("Country") or "",
                    "region": q.get("region") or specs_b.get("Region") or "",
                    "price": float(re.sub(r"[^\d.]", "", q.get("price") or "0") or 0),
                })
            case_contents[str(vid)] = {
                "count": case.get("count"),
                "split": case.get("split"),
                "bottles": bottles,
            }

        j = junip.get(str(p["id"]), {})
        summary = j.get("summary") or {}
        reviews = []
        for r in j.get("reviews") or []:
            reviews.append({
                "rating": r.get("rating"),
                "title": r.get("title") or "",
                "body": r.get("body") or "",
                "customer_name": " ".join(
                    x for x in [(r.get("customer") or {}).get("first_name"),
                                (r.get("customer") or {}).get("last_name")] if x) or "Verified buyer",
                "verified_buyer": bool(r.get("verified_buyer")),
                "would_recommend": bool(r.get("would_recommend")),
                "created_at": (r.get("created_at") or "")[:19],
            })

        spec_rows = []
        for key in ("Winery", "Varietal", "Year", "Type", "ABV", "Country", "Region"):
            value = specs.get(key) or ""
            if key == "Varietal" and not value:
                value = (tags.get("varietal") or [""])[0]
            if key == "Country" and not value:
                value = (tags.get("country") or [""])[0]
            if key == "Year" and not value:
                value = (tags.get("vintage") or [""])[0]
            if value:
                spec_rows.append([key, value])

        out.append({
            "upstream_id": p["id"],
            "handle": handle,
            "title": p["title"],
            "product_type": p.get("product_type") or "Bottle",
            "vendor": p.get("vendor") or "MacysWine Shop",
            "description_html": p.get("body_html") or "",
            "subheading": subheading,
            "color": (tags.get("color") or [""])[0],
            "sweetness": (tags.get("sweetness") or [""])[0],
            "country": (tags.get("country") or [""])[0],
            "varietal": (tags.get("varietal") or [""])[0],
            "vintage": (tags.get("vintage") or [""])[0],
            "wine_category": (tags.get("wine_category") or [""])[0],
            "region": specs.get("Region") or "",
            "winery": specs.get("Winery") or "",
            "abv": specs.get("ABV") or "",
            "specs_html_rows": spec_rows,
            "awards": parse.get("awards") or [],
            "price": price,
            "compare_at_price": compare,
            "on_sale": on_sale,
            "pct_off": pct_off,
            "available": all(v["available"] for v in variants_out) if variants_out else False,
            "published_at": (p.get("published_at") or MIRROR_DATE)[:10],
            "rating_average": summary.get("rating_average") or 0.0,
            "rating_count": summary.get("rating_count") or 0,
            "rating_distribution": summary.get("rating_distribution") or {},
            "recommended_percentage": summary.get("recommended_percentage") or 0.0,
            "reviews": reviews,
            "variants": variants_out,
            "images": images,
            "case_contents": case_contents,
            "related": parse.get("related") or [],
            "bestseller_rank": rank,
        })
    return out


def build_collections(products: list, memberships: dict) -> list:
    raw = load("collections_raw.json")
    by_handle = {p["handle"]: p for p in products}
    out = []
    for pos, c in enumerate(raw):
        handle = c["handle"]
        member_handles = [h for h in memberships.get(handle, []) if h in by_handle]
        out.append({
            "handle": handle,
            "title": c["title"],
            "description_html": c.get("body_html") or c.get("description") or "",
            "sort_order": "best-selling",
            "position": pos,
            "in_nav": handle in NAV_COLLECTIONS,
            "nav_label": NAV_COLLECTIONS.get(handle, ""),
            "products": member_handles,
        })
    return out


def parse_blog_articles() -> list:
    blog_dir = OUT / "blog_html"
    articles = []
    for path in sorted(blog_dir.glob("*.html")):
        if path.name.startswith("__index"):
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        slug = path.stem
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        og = re.search(r'property="og:image" content="([^"]+)"', html)
        og_title = re.search(r'property="og:title" content="([^"]+)"', html)
        content_start = html.find("id='ArticleContent'")
        if content_start < 0:
            content_start = html.find('id="ArticleContent"')
        content = ""
        if content_start >= 0:
            end = html.find("id='ArticleShare'", content_start)
            if end < 0:
                end = html.find('id="ArticleShare"', content_start)
            if end < 0:
                end = min(len(html), content_start + 60000)
            content = html[content_start:end]
            content = content[content.find(">") + 1:]
            content = content.split("</section>")[0]
            content = re.sub(r"\s+", " ", content).strip()
        title = (og_title.group(1) if og_title else
                 (re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else slug.replace("-", " ").title()))
        image = normalize_image(og.group(1), 800) if og else ""
        base = image.split("?")[0].lower()
        if base.endswith(".png"):
            image_path = f"blog/{slug}.png"
        elif base.endswith(".webp"):
            image_path = f"blog/{slug}.webp"
        elif image:
            image_path = f"blog/{slug}.jpg"
        else:
            image_path = ""
        articles.append({
            "handle": slug,
            "title": title,
            "excerpt": "",
            "author": "Macy's Wine Shop",
            "published_at": MIRROR_DATE,
            "image_source_url": image,
            "image_path": image_path,
            "content_html": content,
        })
    return articles


def parse_pages() -> list:
    page_dir = OUT / "page_html"
    pages = []
    for path in sorted(page_dir.glob("*.html")):
        slug = path.stem
        if slug.startswith("products_"):
            continue  # product captures are not storefront pages
        html = path.read_text(encoding="utf-8", errors="replace")
        slug = path.stem
        title_m = re.search(r"<title>\s*([^<]*?)\s*(?:&ndash;|–|-) MacysWine Shop\s*</title>", html, re.S)
        main_start = html.find("id='MainContent'")
        if main_start < 0:
            main_start = html.find('id="MainContent"')
        content = ""
        if main_start >= 0:
            tail = html[main_start:]
            end = tail.find("id='shopify-section-footer'")
            if end < 0:
                end = tail.find('id="shopify-section-footer"')
            content = tail[:end if end > 0 else len(tail)]
            content = content[content.find(">") + 1:]
            content = re.sub(r"<script.*?</script>", "", content, flags=re.S)
            content = re.sub(r"<style.*?</style>", "", content, flags=re.S)
            content = re.sub(r"\s+", " ", content).strip()
        pages.append({
            "handle": slug,
            "title": (title_m.group(1).strip() if title_m else slug.replace("_", " ").title()),
            "content_html": content,
        })
    return pages


def main() -> None:
    qv = load("quickview_data.json")
    pdp = load("pdp_parsed.json")
    memberships = load("collection_members.json")
    junip = {}
    for path in sorted((OUT / "junip").glob("*.json")):
        d = json.loads(path.read_text())
        junip[str(d["remote_id"])] = d

    products = build_products(qv, pdp, junip, memberships)
    collections = build_collections(products, memberships)
    articles = parse_blog_articles()
    pages = parse_pages()
    home = load("home_parsed.json")
    disclosures = load("state_disclosures.json")
    drinks = load("drinks_shop.json")

    source = {
        "snapshot_date": MIRROR_DATE,
        "upstream": "https://macyswineshop.com/",
        "products": products,
        "collections": collections,
        "blog_articles": articles,
        "pages": pages,
        "home": home,
        "state_disclosures": disclosures,
        "compliance_texts": [t for t in drinks.get("texts", [])],
        "nav": {
            "varietals": WINE_VARIETALS,
            "countries": WINE_COUNTRIES,
        },
    }
    dest = BASE / "source_data.json"
    dest.write_text(json.dumps(source, ensure_ascii=False))
    n_bottles = sum(len(v["bottles"]) for p in products for v in p["case_contents"].values())
    n_reviews = sum(len(p["reviews"]) for p in products)
    n_images = sum(len(p["images"]) for p in products)
    print(f"[source] products={len(products)} collections={len(collections)} "
          f"articles={len(articles)} pages={len(pages)} reviews={n_reviews} "
          f"product_images={n_images} case_bottles={n_bottles} "
          f"size={dest.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
