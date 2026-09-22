#!/usr/bin/env python3
"""Build the cboe seed database from the scraped upstream snapshot.

Run from the site directory:
    python3 seed_data.py

Sources live in ../../scraped_data (gitignored, build-time only):
- market/*.json        delayed quotes + intraday + full option chains + symbol book
- market_stats/*.json  daily market statistics for nine business days
- articles/*.json      Insights category listings + 319 article pages
- pages/*.html         Options Institute / products / about reference pages
- recon/home.html      the rendered homepage (volume snapshot values)
- images_raw/manifest.json  URL -> local asset mapping for images

The seed functions are idempotent (whole-function gates) so container boot
and /reset keep the database byte-identical to instance_seed/cboe.db.
"""
import json
import os
import re
from datetime import datetime

from bs4 import BeautifulSoup

# Model imports happen inside each seed function (deferred) so the module
# can be imported by app.py's bootstrap without a circular import.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "scraped_data"))


def load(relpath):
    with open(os.path.join(SCRAPE, relpath), encoding="utf-8") as fh:
        return json.load(fh)


def load_html(relpath):
    with open(os.path.join(SCRAPE, relpath), encoding="utf-8") as fh:
        return fh.read()


SYMBOL_NAMES = {
    "SPX": ("S&P 500 Index", "^SPX"),
    "VIX": ("Cboe Volatility Index", "^VIX"),
    "XSP": ("Mini-SPX Index", "^XSP"),
    "NDX": ("Nasdaq-100 Index", "^NDX"),
    "RUT": ("Russell 2000 Index", "^RUT"),
    "OEX": ("S&P 100 Index", "^OEX"),
    "DJX": ("Dow Jones Industrial Average Index", "^DJX"),
    "MRUT": ("Mini-Russell 2000 Index", "^MRUT"),
}

SYMBOL_ORDER = ["SPX", "VIX", "XSP", "NDX", "RUT", "OEX", "DJX", "MRUT"]


def seed_database():
    from app import OptionContract, db
    if OptionContract.query.count() > 0:
        return

    seed_symbols_and_chains()
    seed_symbol_directory()
    seed_market_statistics()
    seed_articles()
    seed_experts_and_classes()
    seed_courses()
    seed_products()
    seed_home_cards()
    seed_static_pages()
    db.session.commit()


# ---------------------------------------------------------------------------
# 1. Symbols / quotes / intraday / option chains
# ---------------------------------------------------------------------------

def seed_symbols_and_chains():
    from app import (Symbol, Quote, IntradayBar,
                                OptionContract, db, parse_osi)
    for order, ticker in enumerate(SYMBOL_ORDER):
        name, display = SYMBOL_NAMES[ticker]
        sym = Symbol(ticker=ticker, display_symbol=display, name=name,
                     security_type="index", has_options=True, order=order)
        db.session.add(sym)
        db.session.flush()

        data = load(f"market/{ticker.lower()}.json")
        quote_data = data["quote"]["data"]
        hist = data.get("historical", {}).get("data", {})
        as_of = quote_data.get("last_trade_time", "")
        if as_of:
            as_of = as_of.replace("T", " ") + " ET (Delayed)"
        q = Quote(
            symbol_id=sym.id,
            as_of=as_of,
            current_price=quote_data.get("current_price") or 0.0,
            price_change=quote_data.get("price_change") or 0.0,
            price_change_percent=quote_data.get("price_change_percent") or 0.0,
            bid=quote_data.get("bid") or 0.0,
            ask=quote_data.get("ask") or 0.0,
            open=quote_data.get("open") or 0.0,
            high=quote_data.get("high") or 0.0,
            low=quote_data.get("low") or 0.0,
            close=quote_data.get("close") or 0.0,
            prev_day_close=quote_data.get("prev_day_close") or 0.0,
            volume=quote_data.get("volume") or 0,
            iv30=quote_data.get("iv30") or 0.0,
            iv30_change_percent=quote_data.get("iv30_change_percent") or 0.0,
            tick=quote_data.get("tick") or "",
            last_trade_time=quote_data.get("last_trade_time") or "",
            annual_high=hist.get("annual_high") or 0.0,
            annual_low=hist.get("annual_low") or 0.0,
        )
        db.session.add(q)

        bars = data.get("intraday", {}).get("data", [])
        if isinstance(bars, list):
            for bar in bars:
                price = bar.get("price", {})
                vol = bar.get("volume", {})
                db.session.add(IntradayBar(
                    symbol_id=sym.id,
                    dt=bar.get("datetime", ""),
                    open=price.get("open") or 0.0,
                    high=price.get("high") or 0.0,
                    low=price.get("low") or 0.0,
                    close=price.get("close") or 0.0,
                    calls_volume=vol.get("calls_volume") or 0,
                    puts_volume=vol.get("puts_volume") or 0,
                    total_options_volume=vol.get("total_options_volume") or 0,
                ))

        contracts = data.get("options", {}).get("data", {}).get("options", [])
        for opt in contracts:
            parsed = parse_osi(opt.get("option", ""))
            if parsed is None:
                continue
            root, expiry, cp, strike = parsed
            db.session.add(OptionContract(
                symbol_id=sym.id,
                code=opt["option"],
                root=root,
                expiry=expiry,
                cp=cp,
                strike=strike,
                bid=opt.get("bid") or 0.0,
                ask=opt.get("ask") or 0.0,
                bid_size=opt.get("bid_size") or 0.0,
                ask_size=opt.get("ask_size") or 0.0,
                iv=opt.get("iv") or 0.0,
                open_interest=opt.get("open_interest") or 0.0,
                volume=opt.get("volume") or 0.0,
                delta=opt.get("delta") or 0.0,
                gamma=opt.get("gamma") or 0.0,
                vega=opt.get("vega") or 0.0,
                theta=opt.get("theta") or 0.0,
                change=opt.get("change") or 0.0,
                open=opt.get("open") or 0.0,
                high=opt.get("high") or 0.0,
                low=opt.get("low") or 0.0,
                last_trade_price=opt.get("last_trade_price") or 0.0,
                last_trade_time=opt.get("last_trade_time") or "",
                percent_change=opt.get("percent_change") or 0.0,
                prev_day_close=opt.get("prev_day_close") or 0.0,
                tick=opt.get("tick") or "",
            ))
        db.session.commit()
        print(f"[seed] {ticker}: {len(contracts)} contracts, {len(bars)} bars", flush=True)


def seed_symbol_directory():
    from app import SymbolDirectory, db
    book = load("market/symbol_book.json")
    entries = book.get("data", book) if isinstance(book, dict) else book
    if isinstance(entries, dict):
        entries = entries.get("symbol_book", [])
    chunk = []
    for i, entry in enumerate(entries):
        chunk.append(SymbolDirectory(name=entry["name"],
                                     company_name=entry.get("company_name", "")))
        if len(chunk) >= 5000:
            db.session.add_all(chunk)
            db.session.commit()
            chunk = []
    if chunk:
        db.session.add_all(chunk)
        db.session.commit()
    print(f"[seed] symbol directory: {len(entries)} rows", flush=True)


# ---------------------------------------------------------------------------
# 2. Daily market statistics
# ---------------------------------------------------------------------------

def seed_market_statistics():
    from app import MarketStatRatio, MarketStatProduct, db
    stats = load("market_stats/all_stats.json")
    for day in stats:
        date = day["date"]
        for key, value in day.get("ratios", {}).items():
            db.session.add(MarketStatRatio(stat_date=date, stat_key=key, value=value))
        for prod in day.get("products", []):
            if prod.get("kind") in ("volume", "open_interest"):
                db.session.add(MarketStatProduct(
                    stat_date=date, section=prod["section"], kind=prod["kind"],
                    call=prod["call"], put=prod["put"], total=prod["total"]))
    db.session.commit()
    print(f"[seed] market statistics: {len(stats)} dates", flush=True)


# ---------------------------------------------------------------------------
# 3. Insights articles
# ---------------------------------------------------------------------------

CATEGORY_META = {
    "Today's Market Take": ("todaysmarkettake", "Timely daily commentary on what is moving the markets and why it matters."),
    "Trading and Investing": ("trading_investing", "Longer takes on trading strategies and market trends."),
    "Derivatives Research": ("derivativesresearch", "Research-driven notes from the Cboe derivatives team."),
    "Macro Volatility Digest": ("macro_volatility_digest", "A recurring digest connecting macro themes with volatility markets."),
    "Mini-SPX (XSP)": ("minispx", "Focused coverage of the Mini-SPX (XSP) options complex."),
    "Products": ("products", "Updates on Cboe tradable products and new listings."),
    "Derivatives Market Intelligence": ("derivatives-market-intelligence", "Actionable derivatives insights and analysis from the market intelligence team."),
}

AUTHOR_META = {
    "JJ Kinahan": ("Senior Vice President, Head of Retail Expansion and Alternative Investment Products",
                   "JJ Kinahan brings more than three decades of trading and markets experience to his role at Cboe, where he leads the firm's retail expansion and alternative investment products strategy. A recognized authority on derivatives, options, and volatility, JJ translates complex market dynamics into clear, actionable insights for active investors and financial advisors."),
    "Henry Schwartz": ("Senior Director, Derivative Market Intelligence",
                        "Henry Schwartz covers options market structure and industry trends for Cboe, with a focus on index products, exchange-traded funds and multi-listed equity options."),
    "Mandy Xu": ("Vice President, Head of Derivatives Market Intelligence",
                 "Mandy Xu leads the Derivatives Market Intelligence team at Cboe, publishing research on index options, volatility and macro markets."),
    "Matt Moran": ("Consultant, Cboe Global Markets",
                   "Matt Moran has worked in the financial services industry for decades and writes about options-based strategies for institutional portfolios."),
}


def seed_articles():
    from app import (ArticleCategory, Author, Article, db)
    listings = load("articles/listings.json")
    articles_raw = load("articles/articles.json")

    category_ids = {}
    for order, (label, (slug, blurb)) in enumerate(CATEGORY_META.items()):
        cat = ArticleCategory(slug=slug, name=label, blurb=blurb, order=order)
        db.session.add(cat)
        category_ids[label] = cat
    db.session.flush()

    author_ids = {}
    seen_authors = {}
    for slug, art in articles_raw.items():
        name = (art.get("author") or "").strip()
        # Some article layouts carry only a date in the meta line; treat that
        # as "no author listed" (matches how the live page renders).
        if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", name):
            name = ""
        if not name or art.get("fetch_failed"):
            continue
        if name and name not in seen_authors:
            title, bio = AUTHOR_META.get(name, ("", ""))
            author = Author(name=name, title=title, bio=bio)
            db.session.add(author)
            db.session.flush()
            seen_authors[name] = author
    db.session.commit()

    count = 0
    for slug, art in articles_raw.items():
        if art.get("fetch_failed"):
            continue
        title = art.get("title", "")
        if not title:
            continue
        # Primary category: first listing category, else first page link.
        cats = art.get("categories") or []
        label = cats[0] if cats else ""
        category = category_ids.get(label)
        if category is None:
            for link in art.get("page_category_links", []):
                category = next((c for c in category_ids.values() if c.name == link), None)
                if category:
                    break
        author = seen_authors.get((art.get("author") or "").strip())
        date_text = art.get("date", "")
        date_sort = ""
        m = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", date_text)
        if m:
            try:
                date_sort = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
            except ValueError:
                date_sort = ""
        body = art.get("body", [])
        # Per-article author name, cleaned of the date-only layout variant.
        author_name = (art.get("author") or "").strip()
        if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", author_name):
            author_name = ""
        # Localize article chart images to static/images/articles/
        body = [_localize_image_block(b) for b in body]
        flat = " ".join(
            re.sub(r"\s+", " ", b.get("text", "")) for b in body if b.get("type") in ("p", "ul", "ol", "h2", "h3", "blockquote"))
        summary = next((b.get("text", "") for b in body if b.get("type") == "p" and b.get("text")), "")
        db.session.add(Article(
            slug=slug,
            title=title,
            category_id=category.id if category else None,
            author_id=author.id if author else None,
            author_name=author_name,
            date=date_text,
            date_sort=date_sort,
            summary=summary[:400],
            body_json=json.dumps(body, ensure_ascii=False),
            tags_json=json.dumps(art.get("page_category_links", [])),
            body_text=flat[:20000],
        ))
        count += 1
    db.session.commit()
    print(f"[seed] articles: {count}", flush=True)


def _image_manifest():
    path = os.path.join(SCRAPE, "images_raw", "manifest.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


IMAGE_MANIFEST = None


def _image_map():
    """source_url -> static/images/<category>/<name> from the asset inventory."""
    global IMAGE_MANIFEST
    if IMAGE_MANIFEST is None:
        path = os.path.join(BASE_DIR, "asset_inventory.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                inventory = json.load(fh)
            IMAGE_MANIFEST = {
                a["source_url"]: a["path"].replace("static/images/", "")
                for a in inventory.get("assets", [])
            }
        else:
            IMAGE_MANIFEST = {}
    return IMAGE_MANIFEST


def _localize_image_block(block):
    """Rewrite article image URLs to local static/images paths."""
    if block.get("type") != "image":
        return block
    url = block.get("src", "")
    local = _image_map().get(url)
    block = dict(block)
    block["src"] = local or ""
    return block


# ---------------------------------------------------------------------------
# 4. Experts + classes
# ---------------------------------------------------------------------------

def _expert_dialogs():
    """Extract (name, title, company, bio) tuples from the experts page's
    embedded RSC flight payload (each expert card ships a hidden bio dialog)."""
    html = load_html("pages/oi_experts.html")
    names = [r[0] for r in _expert_names_from_dom(html)]
    chunks = []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html):
        try:
            decoded = json.loads('"' + m.group(1) + '"')
        except (ValueError, TypeError):
            continue
        idx = decoded.find(":")
        chunks.append((decoded[:idx], decoded[idx + 1:]))
    paras = []
    for _cid, frag in chunks:
        for m in re.finditer(r'"\$","\$L3d",null,\{"children":(.*)', frag, re.S):
            for p in re.findall(r'"children":"((?:[^"\\]|\\.)*)"', m.group(1)):
                try:
                    text = json.loads('"' + p + '"') if p else ""
                except (ValueError, TypeError):
                    continue
                if len(text) > 40:
                    paras.append(text)
    order = {n: i for i, n in enumerate(names)}
    first = {}
    for n in names:
        first.setdefault(n.split()[0], []).append(n)
    assign = {n: [] for n in names}
    current = None
    for p in paras:
        target = None
        for f, cands in first.items():
            if p.startswith(f):
                later = [c for c in cands if current is None or order[c] >= order[current]]
                if later:
                    target = later[0]
                    break
        if target is None and current is not None:
            for f, cands in first.items():
                if re.search(r"\b" + re.escape(f) + r"\b", p[:150]):
                    later = [c for c in cands if order[c] > order[current]]
                    if later:
                        target = later[0]
                        break
        if target:
            current = target
        if current:
            assign[current].append(p)
    results = []
    for n in names:
        results.append({"name": n, "title": "", "company": "",
                        "bio": " ".join(assign.get(n, []))})
    return results


def _expert_names_from_dom(html):
    """The ordered (name, title) list rendered in the experts grid."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    grid = None
    for h in main.find_all(["h1", "h2", "h3"]):
        if h.get_text(strip=True).lower().startswith("get to know our faculty"):
            grid = h.find_next("div")
            break
    scope = grid if grid is not None else main
    rows = []
    for h1 in scope.find_all("h1"):
        name = h1.get_text(strip=True)
        if not name or name.lower().startswith("hero") or name.lower().startswith("meet"):
            continue
        h2 = h1.find_next("h2")
        title = h2.get_text(strip=True) if h2 else ""
        rows.append((name, title))
    return rows


def seed_experts_and_classes():
    from app import Expert, OIClass, OiEventFilter, db
    # --- experts from the rendered experts page --------------------------
    html = load_html("pages/oi_experts.html")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    dialogs = {d["name"].strip(): d for d in _expert_dialogs()}
    order = 0
    seen = set()
    for img in main.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if not alt or alt.lower() in {"cboe logo", "options institute logo",
                                      "hero oi experts desktop image"}:
            continue
        src = img.get("src") or ""
        m = re.search(r"url=([^&]+)", src)
        from urllib.parse import unquote
        real = unquote(m.group(1)) if m else src
        if alt in seen:
            continue
        seen.add(alt)
        local = _expert_headshot_local(real)
        h1 = main.find("h1", string=lambda t: t and alt.split()[0] in t)
        title = ""
        if h1 and h1.find_next("h2"):
            title = h1.find_next("h2").get_text(strip=True)
        dialog = dialogs.get(alt)
        if dialog is None:
            for dname, d in dialogs.items():
                if dname.split(",")[0].strip() == alt or alt.startswith(dname.split(",")[0].strip()):
                    dialog = d
                    break
        db.session.add(Expert(
            name=alt,
            title=title or dialog.get("title", ""),
            headshot=local,
            bio=dialog.get("bio", ""),
            order=order,
        ))
        order += 1
    db.session.flush()
    db.session.commit()
    print(f"[seed] experts: {len(seen)}", flush=True)

    # --- classes from the events API payload ------------------------------
    events = load("market/home_cards.json")["oi_events"]
    for ev in events.get("eventsData", []):
        speaker = (ev.get("speaker") or [{}])[0]
        date_text = ev.get("date", "")
        date_sort = ""
        m = re.search(r"([A-Z][a-z]+ \d{1,2} \d{4})", date_text)
        if m:
            try:
                date_sort = datetime.strptime(m.group(1), "%B %d %Y").strftime("%Y-%m-%d")
            except ValueError:
                date_sort = ""
        filt = ev.get("filter", {})
        info = " ".join(ev.get("info", []))
        db.session.add(OIClass(
            title=ev.get("title", ""),
            series=_first_bold(info),
            description=info,
            instructor=speaker.get("name", ""),
            instructor_title=speaker.get("title", ""),
            instructor_bio=" ".join(speaker.get("info", [])),
            date=date_text,
            date_sort=date_sort,
            time=ev.get("time", ""),
            format=(filt.get("format") or ["Virtual"])[0],
            level=(filt.get("courselevel") or ["Foundational"])[0],
            language=(filt.get("language") or ["English"])[0],
            region=(filt.get("region") or ["North America"])[0],
            topic=(filt.get("topic") or [""])[0],
        ))
        for facet in ("courselevel", "language", "region", "format"):
            for i, value in enumerate(filt.get(facet, [])):
                db.session.add(OiEventFilter(facet=facet, value=value, order=i))
    # Instructor facet values come from the API speaker list.
    for i, name in enumerate(events.get("speakerData", [])):
        db.session.add(OiEventFilter(facet="instructor", value=name, order=i))
    db.session.commit()
    print("[seed] classes: ", events.get("eventsData") and len(events["eventsData"]), flush=True)


def _first_bold(html):
    m = re.search(r"<b>(.*?)</b>", html, re.S)
    return m.group(1).strip() if m else ""


def _expert_headshot_local(url):
    local = _image_map().get(url)
    return local or ""


# ---------------------------------------------------------------------------
# 5. Courses
# ---------------------------------------------------------------------------

def seed_courses():
    from app import Course, db
    # --- Options 101 ------------------------------------------------------
    html = load_html("pages/oi_options101.html")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    modules = []
    # Modules are cards with an h2/h3 title and a duration label.
    for h in main.find_all(["h2", "h3"]):
        text = h.get_text(strip=True)
        if not text or text in ("Explore more courses", "New to Options?"):
            continue
        # The duration/plan labels are rendered as h3 siblings next to the
        # module title ("20 min course", "Learning plan comprised of 22
        # courses."); they are labels, not module titles.
        if re.fullmatch(r"\d+\s*min course", text) or \
                re.fullmatch(r"Learning plan comprised of \d+ courses\.?", text):
            continue
        card = h.find_parent(["div", "li", "article"]) or h
        body = card.get_text("\n", strip=True)
        duration = ""
        m = re.search(r"(\d+\s*min course|Learning plan comprised of \d+ courses)", body)
        if m:
            duration = m.group(1)
        if text not in [mod["title"] for mod in modules]:
            modules.append({"title": text, "duration": duration})
    db.session.add(Course(
        slug="options101",
        title="Options 101",
        intro="Build your education foundation with the essential course covering options use cases, terminology, and mechanics.",
        hero_image="banners/banner-OI-portal-desktop.png",
        modules_json=json.dumps(modules[:12]),
        order=0,
    ))

    # --- Defining Options (glossary) — answers live in the RSC flight data.
    html = load_html("pages/oi_defining.html")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    qa = []
    by_q = {q: a for q, a in _defining_options_flight_pairs(html)}
    for h in main.find_all(["h2", "h3"]):
        q = h.get_text(strip=True)
        if not q or q.lower().startswith("new to options"):
            continue
        qa.append({"q": q, "a": by_q.get(q, "")[:2000]})
    db.session.add(Course(
        slug="defining-options",
        title="Options Definitions & Glossary",
        intro="The essential options definitions and glossary from The Options Institute.",
        hero_image="heros/Hero-OI-Homepage-desktop.png",
        modules_json=json.dumps(qa[:30]),
        order=1,
    ))
    db.session.commit()
    print("[seed] courses: 2", flush=True)



COMPONENT_NAMES = {"$", "p", "span", "div", "br", "li", "ul", "b", "i", "em", "strong"}


def _flight_flatten(node, out):
    if isinstance(node, str):
        if not node.startswith("$") and node not in COMPONENT_NAMES and not node.startswith("tw-"):
            out.append(node)
    elif isinstance(node, list):
        for n in node:
            _flight_flatten(n, out)
    elif isinstance(node, dict):
        if "children" in node:
            _flight_flatten(node["children"], out)


def _defining_options_flight_pairs(html):
    """Extract glossary question/answer pairs from the page's RSC flight payload."""
    from json import JSONDecodeError
    parts = []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html):
        try:
            decoded = json.loads('"' + m.group(1) + '"')
        except (ValueError, TypeError):
            continue
        idx = decoded.find(":")
        parts.append(decoded[idx + 1:])
    stream = "".join(parts)
    decoder = json.JSONDecoder()
    pos = 0
    values = []
    while pos < len(stream):
        if stream[pos] in " \n\t\r":
            pos += 1
            continue
        try:
            val, end = decoder.raw_decode(stream, pos)
            values.append(val)
            pos = end
        except JSONDecodeError:
            pos += 1
    pairs = []
    for val in values:
        stack = [val]
        while stack:
            node = stack.pop()
            if (isinstance(node, list) and len(node) >= 4 and node[0] == "$"
                    and isinstance(node[1], str) and "L1e" in node[1]
                    and isinstance(node[3], dict)):
                inner = node[3].get("children", [])
                q = a = ""
                for item in inner:
                    if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], str):
                        if "L1f" in item[1] and isinstance(item[3], dict):
                            q = item[3].get("children", "")
                            if not isinstance(q, str):
                                q = ""
                        elif "L20" in item[1] and isinstance(item[3], dict):
                            out = []
                            _flight_flatten(item[3].get("children"), out)
                            a = " ".join(x.strip() for x in out if x.strip())
                if q:
                    pairs.append((q, a))
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                stack.extend(node.values())
    return pairs


# ---------------------------------------------------------------------------
# 6. Tradable products
# ---------------------------------------------------------------------------

def seed_products():
    from app import Product, db
    spx_html = load_html("pages/spx_product.html")
    spx = _parse_product_page(spx_html)
    db.session.add(Product(
        slug="spx-options", family="sp-500",
        name="S&P 500 Index Options",
        eyebrow="S&P 500 INDEX OPTIONS",
        hero_title=spx["hero_title"],
        hero_desc=spx["hero_desc"],
        trade_volume="6,498,237", trade_open_interest="20,716,226",
        trade_as_of="September 21, 2026", quote_symbol="SPX",
        benefits_json=json.dumps(spx["benefits"]),
        sections_json=json.dumps(spx["sections"]),
        gth_note=spx["gth_note"],
        gth_json=json.dumps(spx["gth"]),
        resources_json=json.dumps(spx["resources"]),
        quick_links_json=json.dumps(spx["quick_links"]),
        calculator=True, order=0,
    ))
    specs = _parse_specs_page(load_html("pages/spx_specs.html"))
    prod = db.session.query(Product).filter_by(slug="spx-options").first()
    prod.specs_json = json.dumps(specs)

    xsp = _parse_product_page(load_html("pages/xsp_product.html"))
    db.session.add(Product(
        slug="xsp-options", family="sp-500",
        name="Mini-SPX (XSP) Index Options",
        eyebrow="MINI-SPX (XSP) INDEX OPTIONS",
        hero_title=xsp["hero_title"],
        hero_desc=xsp["hero_desc"],
        trade_volume="315,743", trade_open_interest="773,786",
        trade_as_of="September 21, 2026", quote_symbol="XSP",
        benefits_json=json.dumps(xsp["benefits"]),
        sections_json=json.dumps(xsp["sections"]),
        gth_note=xsp["gth_note"],
        gth_json=json.dumps(xsp["gth"]),
        resources_json=json.dumps(xsp["resources"]),
        quick_links_json=json.dumps(xsp["quick_links"]),
        calculator=False, order=1,
    ))

    vix = _parse_product_page(load_html("pages/vix_product.html"))
    db.session.add(Product(
        slug="vix-options", family="vix",
        name="Cboe Volatility Index (VIX) Options",
        eyebrow="CBOE VOLATILITY INDEX (VIX) OPTIONS",
        hero_title=vix["hero_title"],
        hero_desc=vix["hero_desc"],
        trade_volume="713,342", trade_open_interest="11,520,530",
        trade_as_of="September 21, 2026", quote_symbol="VIX",
        benefits_json=json.dumps(vix["benefits"]),
        sections_json=json.dumps(vix["sections"]),
        gth_note=vix["gth_note"],
        gth_json=json.dumps(vix["gth"]),
        resources_json=json.dumps(vix["resources"]),
        quick_links_json=json.dumps(vix["quick_links"]),
        calculator=False, order=2,
    ))

    vxf = _parse_product_page(load_html("pages/vix_futures.html"))
    db.session.add(Product(
        slug="vix-futures", family="vix",
        name="Cboe Volatility Index (VIX) Futures",
        eyebrow="CBOE VOLATILITY INDEX (VIX) FUTURES",
        hero_title=vxf["hero_title"],
        hero_desc=vxf["hero_desc"],
        trade_volume="127,133", trade_open_interest="-",
        trade_as_of="September 18, 2026", quote_symbol="VIX",
        benefits_json=json.dumps(vxf["benefits"]),
        sections_json=json.dumps(vxf["sections"]),
        gth_note=vxf["gth_note"],
        gth_json=json.dumps(vxf["gth"]),
        resources_json=json.dumps(vxf["resources"]),
        quick_links_json=json.dumps(vxf["quick_links"]),
        calculator=False, order=3,
    ))
    db.session.commit()
    print("[seed] products: 4", flush=True)


def _parse_product_page(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    out = {"hero_title": "", "hero_desc": "", "benefits": [], "gth_note": "",
           "gth": [], "resources": [], "quick_links": [], "sections": []}
    h1s = [h for h in main.find_all("h1") if h.get_text(strip=True)]
    if h1s:
        out["hero_title"] = re.sub(r"\s+", " ", h1s[0].get_text(" ", strip=True))
    # hero description: first long paragraph after hero title
    for p in main.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text) > 90 and "options" in text.lower():
            out["hero_desc"] = text
            break
    # benefits: card headings between the "Why X" section heading and the
    # next structural heading (Extended Global Trading Hours / Comparison)
    h2s = main.find_all("h2")
    why_idx = None
    stop_idx = len(h2s)
    for i, h in enumerate(h2s):
        text = h.get_text(strip=True)
        if why_idx is None and text.lower().startswith("why "):
            why_idx = i
        elif why_idx is not None and ("global trading hours" in text.lower()
                                      or "comparison calculator" in text.lower()):
            stop_idx = i
            break
    if why_idx is not None:
        for h in h2s[why_idx + 1:stop_idx]:
            title = h.get_text(" ", strip=True)
            if not title or title.lower().startswith(("benefit", "why ")):
                continue
            if len(title) > 40 or title.lower().startswith(("key resources", "subscription", "the options institute", "s&p 500")):
                break
            desc = ""
            p = h.find_next("p")
            if p:
                t = p.get_text(" ", strip=True)
                if t and t != title:
                    desc = t
            out["benefits"].append({"title": title, "desc": desc[:300]})
    # GTH table
    for table in main.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Regular Trading Hours" in " ".join(headers):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if cells:
                    rows.append(cells)
            out["gth"] = {"headers": headers, "rows": rows}
    gth_sec = None
    for h in main.find_all("h2"):
        if "Global Trading Hours" in h.get_text(strip=True):
            gth_sec = h
            break
    if gth_sec:
        node = gth_sec.next_sibling
        for _ in range(8):
            if node is None:
                break
            if getattr(node, "name", None) == "p":
                out["gth_note"] = node.get_text(" ", strip=True)
                break
            node = node.next_sibling
        if not out["gth_note"]:
            p = gth_sec.find_next("p")
            out["gth_note"] = p.get_text(" ", strip=True) if p else ""
    # generic content sections: group every h2 with the paragraphs after it
    skip_prefixes = ("why ", "key resources", "latest market insights", "the options institute",
                     "extended global trading hours", "comparison calculator", "trade data",
                     "subscription")
    current = None
    for el in main.find_all(["h2", "p"]):
        if el.name == "h2":
            heading = el.get_text(" ", strip=True)
            if (not heading or heading.startswith("(") or heading.lower().startswith(skip_prefixes)
                    or heading in [b["title"] for b in out["benefits"]]):
                current = None
                continue
            current = {"heading": heading, "paras": []}
            out["sections"].append(current)
        else:
            t = el.get_text(" ", strip=True)
            if current is not None and len(t) > 40 and len(current["paras"]) < 4:
                current["paras"].append(t[:900])
    # quick links
    for el in main.find_all(string=re.compile("QUICK LINKS")):
        container = el.find_parent("div")
        if container:
            for a in container.find_all("a"):
                label = a.get_text(strip=True)
                if label:
                    out["quick_links"].append(label)
            break
    return out


def _parse_specs_page(html):
    """Parse the SPX specifications page: the server-rendered Product Snapshot
    (symbol/CUSIP/multiplier, trading hours, expiration rules, underlying)."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    specs = []

    # Product Snapshot: <p>value</p><p>LABEL</p> pairs inside the snapshot panel.
    for el in main.find_all(string=re.compile("Product Snapshot")):
        container = el.find_parent("section")
        while container is not None and "648815" not in container.get_text(" ", strip=True) and "CUSIP" not in container.get_text(" ", strip=True):
            container = container.find_parent("section") or (container.parent if container.name == "div" else None)
        if container is None:
            container = el.find_parent("div")
        if container is None:
            continue
        ps = {"label": "Product Snapshot",
              "value": _snapshot_text(container)}
        specs.append(ps)
        break

    # Trading hours: h3 + following p.
    for h3 in main.find_all("h3"):
        label = h3.get_text(" ", strip=True)
        if label in ("Regular Hours", "Curb", "Global Trading Hours"):
            p = h3.find_next("p")
            specs.append({"label": label,
                          "value": p.get_text(" ", strip=True) if p else ""})

    # EXPIRATION TRADING HOURS paragraph.
    for h in main.find_all(["h2", "h3"]):
        if h.get_text(" ", strip=True).upper().startswith("EXPIRATION TRADING HOURS"):
            p = h.find_next("p")
            specs.append({"label": "Expiration Trading Hours",
                          "value": (p.get_text(" ", strip=True) if p else "")[:1200]})
            break

    # Accordion spec rows (trigger h3 + role=region content), skipping the
    # sidebar nav headings.
    ACCORDION_LABELS = ("Underlying", "Premium Quote", "Strike Prices",
                        "Strike Price Intervals", "Expiration Month",
                        "Expiration Date", "Exercise Style", "Last Trading Day",
                        "Settlement Value", "Position and Exercise Limits", "Margin")
    for label in ACCORDION_LABELS:
        for h3 in main.find_all("h3"):
            if h3.get_text(" ", strip=True) != label:
                continue
            region = h3.find_next("div", attrs={"role": "region"})
            if region is None:
                break
            value = region.get_text(" ", strip=True)
            if value:
                specs.append({"label": label, "value": value[:1200]})
            break
    return [s for s in specs if s.get("value") and s["label"] not in
            ("New To Options?",)][:20]


def _snapshot_text(container):
    parts = []
    for p in container.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            parts.append(text)
    return " | ".join(parts[:24])[:1600]


# ---------------------------------------------------------------------------
# 7. Homepage cards
# ---------------------------------------------------------------------------

def seed_home_cards():
    from app import HomePageCard, db
    cards = load("market/home_cards.json")
    most_active = cards.get("most_active", {}).get("mostActive", [])
    vx = cards.get("vx_futures", {}).get("data", [])
    market_share = cards.get("options_market_share", {}).get("data", {}).get("stats", {}).get("integrated", [])
    products = cards.get("tradable_products", {}).get("data", {})

    db.session.add(HomePageCard(section="volume_snapshot", order=0, payload_json=json.dumps({
        "label": "daily volume for September 18, 2026",
        "spx_index_options": "5.27M",
        "vix_index_options": "652.79K",
        "vix_futures": "127.13K",
        "industry_volume": "73.35M",
    })))
    db.session.add(HomePageCard(section="market_snapshot", order=1, payload_json=json.dumps({
        "most_active": most_active,
        "vx_futures": [{"symbol": v.get("symbol"), "settlement": v.get("settlement"),
                        "expiration": v.get("expiration")} for v in vx[:4]],
        "options_market_share": [{"name": m.get("mkthtml"), "share": round(m.get("mktshare", 0) * 100, 2)}
                                 for m in market_share[:5]],
        "us_options_avg_daily": "13.48M",
        "canada_avg_daily": "220M+",
        "fx_avg_daily": "$55.10B",
    })))
    db.session.add(HomePageCard(section="hero", order=2, payload_json=json.dumps({
        "badge": "New",
        "line1": "Trade the Market's Next Move",
        "line2": "Meet S&P 500® Predictions",
        "cta": "Cboe Predicts",
    })))
    db.session.commit()
    print("[seed] home cards: 3", flush=True)


# ---------------------------------------------------------------------------
# 8. Static pages (about / hours / gth / markets)
# ---------------------------------------------------------------------------

def seed_static_pages():
    from app import StaticPage, db
    db.session.add(StaticPage(slug="about", title="About Us", intro=(
        "Cboe Global Markets is a leading provider of market infrastructure and "
        "tradable products, delivering cutting-edge trading, clearing and "
        "investment solutions to market participants around the world."),
        sections_json=json.dumps(_sections_from_page("pages/about.html", skip_names={
            "Get to KnowCboe"}))))
    hours_sections = _sections_from_page("pages/about_hours.html")
    db.session.add(StaticPage(slug="hours", title="Hours & Holidays",
                              intro="Cboe exchange trading hours and holiday schedules.",
                              sections_json=json.dumps(hours_sections)))
    gth_sections = _sections_from_page("pages/about_gth.html")
    db.session.add(StaticPage(slug="gth", title="Global Trading Hours",
                              intro="Nearly 24 hours a day, five days a week access for key Cboe index products.",
                              sections_json=json.dumps(gth_sections)))
    markets_sections = _sections_from_page("pages/markets_us_options.html")
    db.session.add(StaticPage(slug="markets-us-options", title="Cboe Options Exchanges",
                              intro="Cboe operates four U.S. options exchanges.",
                              sections_json=json.dumps(markets_sections)))
    db.session.commit()
    print("[seed] static pages: 4", flush=True)


def _sections_from_page(relpath, skip_names=frozenset()):
    html = load_html(relpath)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    sections = []
    current = None
    for el in main.find_all(["h1", "h2", "h3", "p", "table", "ul"], recursive=True):
        if el.find_parent("table") is not None and el.name != "table":
            continue
        if el.find_parent(["ul", "ol"]) is not None and el.name not in ("ul", "li"):
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2", "h3"):
            if text in skip_names or text.lower().startswith("new to options") or \
               text.lower().startswith("next level learning"):
                continue
            current = {"heading": text, "blocks": []}
            sections.append(current)
            continue
        if current is None:
            continue
        if el.name == "table":
            headers = [th.get_text(strip=True) for th in el.find_all("th")]
            rows = [[td.get_text(strip=True) for td in tr.find_all("td")]
                    for tr in el.find_all("tr")]
            current["blocks"].append({
                "type": "table",
                "headers": headers,
                "rows": [r for r in rows if r],
            })
        elif el.name == "p" and len(text) > 2:
            current["blocks"].append({"type": "p", "text": text[:1500]})
        elif el.name == "ul":
            items = [li.get_text(" ", strip=True) for li in el.find_all("li")]
            current["blocks"].append({"type": "ul", "items": items[:12]})
    # drop empty sections
    sections = [s for s in sections if s["blocks"]]
    return sections[:14]


# ---------------------------------------------------------------------------
# 9. Benchmark users + pre-populated account data
# ---------------------------------------------------------------------------

USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson",
     "first_name": "Alice", "last_name": "Johnson", "country": "United States",
     "trader_type": "Individual investor", "notify_market_take": True,
     "notify_research": True, "notify_products": False},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen",
     "first_name": "Bob", "last_name": "Chen", "country": "United States",
     "trader_type": "Financial advisor", "notify_market_take": True,
     "notify_research": False, "notify_products": True},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis",
     "first_name": "Carol", "last_name": "Davis", "country": "Canada",
     "trader_type": "Institutional investor", "notify_market_take": False,
     "notify_research": True, "notify_products": False},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim",
     "first_name": "David", "last_name": "Kim", "country": "United States",
     "trader_type": "Active trader", "notify_market_take": True,
     "notify_research": False, "notify_products": True},
]
PASSWORD = "TestPass123!"


def seed_benchmark_users():
    from app import (User, WatchlistItem, ClassRegistration,
                                  OIClass, ArticleCategory, Article, SavedArticle,
                                  Subscriber, MIRROR_REFERENCE_DATE, Symbol, db, app)
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    # Fixed-salt bcrypt hash so re-seeding is byte-identical (the random
    # gensalt() default would change the DB bytes on every seed run).
    # Same scheme the other WebHarbor seeds use (2b, 12 rounds, TestPass123!).
    PASSWORD_HASH = ('$2b$12$C1UoOqH9zW3kV2sE8yJ7Ne'
                     '/iPilks4a8N9cpu0.AGHnbFLbYr0aUK')
    for spec in USERS:
        user = User(created_at=MIRROR_REFERENCE_DATE, **spec)
        user.password_hash = PASSWORD_HASH
        db.session.add(user)
    db.session.commit()

    # --- watchlist: 2-3 symbols per user -----------------------------------
    plan = {
        "alice_j": ["SPX", "VIX"],
        "bob_c": ["VIX", "XSP", "NDX"],
        "carol_d": ["SPX", "RUT"],
        "david_k": ["VIX", "DJX", "OEX"],
    }
    for username, tickers in plan.items():
        user = User.query.filter_by(username=username).first()
        for ticker in tickers:
            sym = Symbol.query.filter_by(ticker=ticker).first()
            if sym:
                db.session.add(WatchlistItem(user_id=user.id, symbol_id=sym.id))
    db.session.commit()

    # --- class registrations: 1-2 per user ---------------------------------
    classes = OIClass.query.order_by(OIClass.date_sort).all()
    reg_plan = {"alice_j": 0, "bob_c": 1, "carol_d": 1, "david_k": 0}
    if classes:
        for username, idx in reg_plan.items():
            user = User.query.filter_by(username=username).first()
            klass = classes[idx % len(classes)]
            db.session.add(ClassRegistration(user_id=user.id, class_id=klass.id))
    db.session.commit()

    # --- saved articles: 2-4 per user --------------------------------------
    tmt = ArticleCategory.query.filter_by(slug="todaysmarkettake").first()
    tmt_articles = Article.query.filter_by(category_id=tmt.id).order_by(
        Article.date_sort.desc()).limit(6).all() if tmt else []
    saved_plan = {
        "alice_j": [0, 2],
        "bob_c": [1, 3, 4],
        "carol_d": [0, 5],
        "david_k": [2],
    }
    for username, idxs in saved_plan.items():
        user = User.query.filter_by(username=username).first()
        for idx in idxs:
            if idx < len(tmt_articles):
                db.session.add(SavedArticle(user_id=user.id,
                                            article_id=tmt_articles[idx].id))
    db.session.commit()

    # --- newsletter subscribers --------------------------------------------
    db.session.add(Subscriber(email="trader.weekly@example.com",
                              first_name="Maya", last_name="Okafor",
                              country="United States", trader_type="Active trader",
                              prefs_json=json.dumps(["Today's Market Take"])))
    db.session.add(Subscriber(email="risk.desk@example.com",
                             first_name="Luis", last_name="Ferreira",
                             country="Portugal", trader_type="Institutional investor",
                             prefs_json=json.dumps(["Derivatives Research"])))
    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
        print("[seed] done")
