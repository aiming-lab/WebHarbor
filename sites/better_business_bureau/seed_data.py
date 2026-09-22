#!/usr/bin/env python3
"""Build the deterministic Better Business Bureau SQLite seed from tracked source data.

The seed is generated at image build time (see the Dockerfile step) from
source_catalog.json, which records BBB.org content captured on 2026-09-21.
All iteration is over sorted keys and the benchmark password hash is frozen,
so the produced database is byte-identical on every build (PYTHONHASHSEED=0).

The seed functions are also called from app.py's bootstrap; each one early-returns
when its tables are already populated so runtime boots never re-seed.
"""
import json
import pathlib
import re
from datetime import datetime

from app import (AdPlacement, Article, Business, Complaint, Favorite,
                 MIRROR_REFERENCE_DATE, Review, ScamReport, ScamSubmission,
                 User, db, slugify)

SOURCE = pathlib.Path(__file__).resolve().parent / "source_catalog.json"

# Frozen hash of the benchmark password "TestPass123!" — bcrypt output is salted,
# so the hash is precomputed once to keep the seed byte-reproducible.
BENCHMARK_PASSWORD_HASH = "$2a$12$bQCwkeRfhT/ngOtGlQ21UO1z3tr0pANRot2YlrkSClVGzdXznfNm2"

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson",
     "city": "Redmond", "state": "WA"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen",
     "city": "Bellevue", "state": "WA"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis",
     "city": "Kirkland", "state": "WA"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim",
     "city": "Seattle", "state": "WA"},
]


def _jdump(value):
    return json.dumps(value, ensure_ascii=False)


def _city_from_slug(city_slug):
    mapping = {
        "redmond": "Redmond", "seattle": "Seattle", "bellevue": "Bellevue",
        "kirkland": "Kirkland", "issaquah": "Issaquah", "lynnwood": "Lynnwood",
        "renton": "Renton", "portland": "Portland", "denver": "Denver",
        "austin": "Austin", "chicago": "Chicago", "new-york": "New York",
        "san-francisco": "San Francisco", "phoenix": "Phoenix", "boston": "Boston",
        "tumwater": "Tumwater", "bothell": "Bothell", "bremerton": "Bremerton",
    }
    return mapping.get(city_slug, city_slug.replace("-", " ").title())


def _addr_parts(card_address):
    """Split a card address like '18019 Redmond Way # 79, Redmond, WA 98052-5600'."""
    street, city, state, zip_code = "", "", "", ""
    if card_address:
        parts = [p.strip() for p in card_address.split(",")]
        street = parts[0]
        if len(parts) >= 3:
            city = parts[1]
            tail = parts[-1].split()
            if len(tail) >= 3:
                state, zip_code = tail[1], tail[2]
            elif len(tail) == 2:
                state, zip_code = tail[0], tail[1]
    return street, city, state, zip_code


def _split_cards_text(text):
    return [c.strip() for c in (text or "").split(",") if c.strip() and "..." not in c][:6]


def _asset_rel(kind, stem):
    """Resolve a managed asset path by content-bearing extension."""
    images_dir = pathlib.Path(__file__).resolve().parent / "static" / "images"
    for ext in (".png", ".jpeg", ".gif", ".svg", ".webp"):
        candidate = images_dir / kind / f"{stem}{ext}"
        if candidate.exists():
            return f"{kind}/{stem}{ext}"
    return ""


def _logo_path(card_logo, business_id):
    if not card_logo:
        return ""
    return _asset_rel("logos", str(business_id))


PS_JUNK = re.compile(
    r"Started|Opened|Incorporated|Entity|Alternate|Management|Employees|Contact|"
    r"Categories|Resources|Licensing|Information|BBB|Accredited|Reviews|Photos|"
    r"^\d{1,2}/\d|:$|^MORE|^Industry")


def _clean_products(items):
    out = []
    for item in items:
        item = (item or "").strip()
        if item in {"Business Details", "Additional Contact Information", "Business Management"}:
            break
        if not item or len(item) > 50:
            continue
        if PS_JUNK.search(item):
            continue
        out.append(item)
    return out[:24]


def clean_consumer_text(text):
    """Remove captured profile/footer chrome after the consumer's own text."""
    markers = (
        r"\n[^\n]*is (?:NOT )?a BBB Accredited Business\.",
        r"\nBBB Business Profiles are provided solely",
        r"\nWhy choose a BBB Accredited Business\?",
        r"\n(?:TM\n)?For Consumers\nGet a Quote",
    )
    endings = [match.start() for pattern in markers
               if (match := re.search(pattern, text or ""))]
    return (text[:min(endings)] if endings else text).strip()


def seed_database():
    if Business.query.count() > 0:
        return
    catalog = json.loads(SOURCE.read_text(encoding="utf-8"))
    for record in catalog["businesses"]:
        if not record.get("profile"):
            continue  # only deep-scraped profiles become seeded businesses
        card = record["card"]
        main = (record.get("profile") or {}).get("main") or {}
        reviews = (record.get("profile") or {}).get("reviews") or {}
        complaints = (record.get("profile") or {}).get("complaints") or {}
        ids = record
        street, addr_city, addr_state, zip_code = _addr_parts(card.get("address"))
        city = _city_from_slug(ids["city_slug"]) or addr_city
        state_code = ids["state_slug"].upper()
        rating = card.get("rating") or "NR"
        accredited = bool(card.get("accredited"))
        categories = _split_cards_text(card.get("categories_text"))
        if not categories:
            categories = [main.get("headerCategory") or ids["cat_slug"].replace("-", " ").title()]
        primary = main.get("headerCategory") or (categories[0] if categories else "Business")
        logo_rel = _logo_path(card.get("logo"), ids["id"])
        photos = []
        for i, _url in enumerate(main.get("photoUrls") or []):
            rel = _asset_rel("photos", f"{ids['id']}_{i}")
            if rel:
                photos.append(rel)

        about = (main.get("aboutText") or "").strip()
        if about.startswith("About This Business"):
            about = about[len("About This Business"):].strip()
        for marker in ("Products and Services", "BBB Accredited Since:", "Years in Business:"):
            about = about.split(marker)[0].strip()
        about = about[:1500]
        years = main.get("yearsInBusiness")
        try:
            years_in_business = int(years) if years else 0
        except (TypeError, ValueError):
            years_in_business = 0

        biz = Business(
            id=ids["id"],
            name=card["name"],
            slug_key=ids["slug_key"],
            primary_category=primary,
            primary_category_slug=ids["cat_slug"],
            categories=_jdump(categories),
            address=street,
            city=city,
            city_slug=ids["city_slug"],
            state=state_code,
            state_slug=ids["state_slug"],
            zip=zip_code,
            phone=card.get("phone") or main.get("headerPhone") or "",
            phones_extra=_jdump(main.get("additionalPhones") or []),
            website="",
            social=_jdump(main.get("socialLinks") or []),
            about=about,
            products_services=_jdump(_clean_products(main.get("productsServices") or [])),
            local_bbb=main.get("localBBB") or "BBB Great West + Pacific",
            file_opened=main.get("fileOpened") or "",
            started=main.get("businessStarted") or "",
            started_locally=main.get("businessStartedLocally") or "",
            incorporated=main.get("businessIncorporated") or "",
            entity_type=main.get("typeOfEntity") or "",
            alternate_names=_jdump([]),
            management=_jdump(main.get("businessManagement") or []),
            employees=main.get("numberOfEmployees") or "",
            principal_contacts=_jdump(main.get("principalContacts") or []),
            customer_contacts=_jdump(main.get("customerContacts") or []),
            payment_methods=main.get("paymentMethods") or "",
            refund_policy=main.get("refundPolicy") or "",
            rating=rating,
            accredited=accredited,
            accredited_since=main.get("accreditedSince") or "",
            years_in_business=years_in_business,
            service_area=bool(card.get("service_area")),
            offers_quotes=bool(card.get("get_quote")),
            logo=logo_rel,
            photos=_jdump(photos),
            industry_tip=main.get("industryTip") or "",
            bureau_id=ids["bureau_id"],
            reviews_total=int(reviews.get("totalReviews") or 0),
            complaints_total=int(complaints.get("totalComplaints") or 0),
            complaints_closed_12m=int(complaints.get("closedLast12") or 0),
        )
        db.session.add(biz)

        for review in (reviews.get("reviews") or []):
            text = (review.get("text") or "").strip()
            name = review.get("name")
            date = review.get("date")
            stars = review.get("stars")
            if not text or not name or not date or not stars:
                continue
            # The captured text includes the author line and sometimes meta lines; strip them.
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            body = "\n".join(
                ln for ln in lines
                if not re_startswith_meta(ln, name, date))
            if not body or len(body) < 40:
                continue
            db.session.add(Review(
                business_id=biz.id, author_name=name, rating=int(stars),
                text=clean_consumer_text(body)[:4000], review_date=date,
                sort_date=_iso(date)))
        for complaint in (complaints.get("complaints") or []):
            text = (complaint.get("text") or "").strip()
            if not text or len(text) < 40:
                continue
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            body = "\n".join(ln for ln in lines if not re_startswith_meta(ln, "", complaint.get("date") or ""))
            db.session.add(Complaint(
                business_id=biz.id,
                author_name="BBB Consumer",
                complaint_type=complaint.get("type") or "Problems with Product or Service",
                status=complaint.get("status") or "Answered",
                complaint_date=complaint.get("date") or "",
                sort_date=_iso(complaint.get("date")),
                text=clean_consumer_text(body)[:4000],
                business_response=clean_consumer_text(complaint.get("businessResponse") or ""),
                business_response_date=complaint.get("businessResponseDate") or "",
                customer_answer=clean_consumer_text(complaint.get("customerAnswer") or ""),
                customer_answer_date=complaint.get("customerAnswerDate") or ""))

    # Ad placements observed on upstream search pages (resolved to seeded businesses)
    for ad in catalog.get("ad_placements", []):
        m = re.search(r"-(\d+)-(\d+)$", (ad.get("real_url") or "").split("?")[0].split("/")[-1])
        if not m:
            continue
        biz = db.session.get(Business, int(m.group(2)))
        if not biz:
            continue
        db.session.add(AdPlacement(
            business_id=biz.id,
            find_text=(ad.get("find_text") or "").lower(),
            find_loc=ad.get("find_loc") or ""))

    # Scam reports
    for hit in catalog.get("scams", []):
        scam_id = hit.get("scam_id")
        scam_type = hit.get("scam_type")
        if not scam_id or not scam_type:
            continue
        db.session.add(ScamReport(
            id=hit.get("pk_id") or scam_id,
            scam_id=scam_id,
            scam_type=scam_type,
            description=_clean_html(hit.get("description") or ""),
            target_city=hit.get("target_city") or "",
            target_state=hit.get("target_state") or "",
            target_zip=hit.get("target_zip") or "",
            target_country=hit.get("target_country") or "USA",
            scammer_address=hit.get("scammer_address_1") or "",
            scammer_city=hit.get("scammer_city") or "",
            scammer_state=hit.get("scammer_state") or "",
            scammer_zip=hit.get("scammer_zip") or "",
            scammer_phone=hit.get("scammer_phone") or "",
            scammer_email=hit.get("scammer_email") or "",
            scammer_url=hit.get("scammer_url") or "",
            scammer_business_name=hit.get("scammer_business_name") or "",
            dollar_value=int(hit.get("dollar_value") or 0),
            date_reported=hit.get("createdOn") or ""))

    # Newsroom articles
    for art in catalog.get("articles", []):
        slug = slugify(art.get("title") or "")[:150]
        if not slug:
            continue
        url_path = art.get("url") or ""
        category = "News"
        m = re.search(r"/article/([a-z-]+)/", url_path)
        if m:
            category = m.group(1).replace("-", " ").title()
        paragraphs = list(art.get("paragraphs") or [])
        deck = (art.get("deck") or "").strip()
        # The upstream body lead paragraph usually equals the deck; keep one copy.
        if deck and not any(p.strip() == deck or p.strip().startswith(deck) for p in paragraphs):
            paragraphs.insert(0, deck)
        paragraphs = [x for x in paragraphs if x]
        body = "\n\n".join(paragraphs)
        image_url = (art.get("image") or {}).get("url") or ""
        image_rel = _asset_rel("articles", str(art["id"])) if image_url else ""
        db.session.add(Article(
            id=int(art["id"]),
            slug=slug,
            title=art.get("h1") or art.get("title") or slug,
            category=category,
            published=(art.get("modified") or "2026-09-01")[:10],
            excerpt=(art.get("summary") or (art.get("deck") or ""))[:300],
            body=body,
            image=image_rel))
    db.session.commit()


def re_startswith_meta(line, name, date):
    lowered = line.lower()
    return (lowered.startswith("date:") or lowered.startswith("status:")
            or lowered.startswith("type:") or lowered.startswith("initial complaint")
            or lowered.startswith("business response") or lowered.startswith("customer answer")
            or (name and lowered == name.lower())
            or (date and lowered == date.lower()))


def _clean_html(text):
    return (text or "").replace("<br class=\"t-last-br\" />", "\n").replace("<br />", "\n").strip()


def _iso(date_text):
    try:
        return datetime.strptime((date_text or "").strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return "1970-01-01"


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    import re as _re
    users = {}
    for spec in BENCHMARK_USERS:
        user = User(username=spec["username"], email=spec["email"],
                    display_name=spec["display_name"], city=spec["city"],
                    state=spec["state"],
                    created_at=datetime(2025, 1, 15, 9, 30, 0))
        user.password_hash = BENCHMARK_PASSWORD_HASH
        db.session.add(user)
        users[spec["username"]] = user
    db.session.flush()

    # Deterministic benchmark state: favorites, one review, one complaint per user.
    alice, bob, carol, david = (users[u] for u in ("alice_j", "bob_c", "carol_d", "david_k"))
    favorites = {
        "alice_j": ["Autosys, Inc.", "Hardware World LLC", "Millen Autobody"],
        "bob_c": ["Honda of Kirkland", "FixAuto Bellevue"],
        "carol_d": ["Autosys, Inc.", "Accurate Auto Body Inc", "Klahanie Service Center Inc"],
        "david_k": ["Metropolitan Detail Inc"],
    }
    for username, names in favorites.items():
        for name in names:
            biz = Business.query.filter_by(name=name).first()
            if biz:
                db.session.add(Favorite(user_id=users[username].id, business_id=biz.id,
                             created_at=datetime(2025, 2, 20, 10, 15, 0)))

    benchmark_reviews = [
        ("alice_j", "Autosys, Inc.", 5, "2025-03-14",
         "Autosys has serviced both of our family cars for years. Honest estimates, no upselling, "
         "and the work is always finished when promised. Last visit they found a failing battery "
         "cable during a routine service and fixed it the same afternoon."),
        ("bob_c", "Honda of Kirkland", 2, "2024-11-02",
         "The service department quoted one price for a brake job over the phone and billed a "
         "higher one at pickup. The work itself seems fine, but the estimate process needs to "
         "be more transparent."),
        ("carol_d", "Accurate Auto Body Inc", 4, "2026-01-20",
         "After a parking lot fender bender they handled the insurance paperwork end to end. "
         "The repair matched the factory paint exactly and the car was ready two days early."),
    ]
    for username, name, stars, date, text in benchmark_reviews:
        biz = Business.query.filter_by(name=name).first()
        if not biz:
            continue
        db.session.add(Review(
            business_id=biz.id, user_id=users[username].id,
            author_name=users[username].display_name, rating=stars, text=text,
            review_date=datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d/%Y"),
            sort_date=date))

    benchmark_complaints = [
        ("carol_d", "Hardware World LLC", "Delivery Issues", "Resolved", "2025-08-11",
         "An online order arrived with two of six items missing. The store resolved it by "
         "shipping the missing items and refunding the shipping fee after I opened a BBB "
         "complaint.", "2025-08-15"),
        ("david_k", "Millen Autobody", "Service or Repair Issues", "Answered", "2026-02-03",
         "The promised repair completion date slipped twice without notice, and I had to call "
         "for updates each time. The final paint work was acceptable but communication needs "
         "improvement.", "2026-02-07"),
    ]
    for username, name, ctype, status, date, text, resp_date in benchmark_complaints:
        biz = Business.query.filter_by(name=name).first()
        if not biz:
            continue
        db.session.add(Complaint(
            business_id=biz.id, user_id=users[username].id,
            author_name=users[username].display_name,
            complaint_type=ctype, status=status,
            complaint_date=datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d/%Y"),
            sort_date=date, text=text,
            business_response="The business responded to BBB with an explanation and offered a resolution." if status == "Resolved" else "The business apologized for the scheduling delays and described steps taken to improve customer communication.",
            business_response_date=datetime.strptime(resp_date, "%Y-%m-%d").strftime("%m/%d/%Y")))

    db.session.add(ScamSubmission(
        user_id=alice.id, scam_type="Phishing",
        description="I received a text claiming my package delivery needed an extra payment "
                    "and to click a tracking link. The link led to a fake courier site asking "
                    "for card details. I did not click further.",
        target_city="Redmond", target_state="WA", target_zip="98052",
        scammer_phone="(425) 555-0148", dollar_value=0,
        date_reported="2026-09-02"))
    db.session.commit()
