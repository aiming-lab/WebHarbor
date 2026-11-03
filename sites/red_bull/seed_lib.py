#!/usr/bin/env python3
"""Deterministic, idempotent seed materialization for the red_bull mirror.

Every seed_* helper early-returns when its table is already populated, so
the boot path is a no-op after the first seed and /reset/<site> restores
byte-identity. All rows come from the tracked source_data/*.json snapshots
in a fixed order; benchmark users use a frozen bcrypt hash.

The image binding step recorded the local
static/images/... path for every entity in source_data, so the seed never
guesses filesystem state.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "display": "Alice Johnson"},
    {"email": "bob.c@test.com", "display": "Bob Chen"},
    {"email": "carol.d@test.com", "display": "Carol Davis"},
    {"email": "dana.k@test.com", "display": "Dana Kim"},
]


def _iso(day: str) -> str:
    return day


def seed_all(*, db, models, bcrypt, base_dir, load):
    seed_users(db=db, models=models)
    seed_products(db=db, models=models, load=load)
    seed_events(db=db, models=models, load=load)
    seed_athletes(db=db, models=models, load=load)
    seed_films(db=db, models=models, load=load)
    seed_shows(db=db, models=models, load=load)
    seed_stories(db=db, models=models, load=load)
    seed_shop(db=db, models=models, load=load)
    seed_benchmark_state(db=db, models=models, load=load)
    db.session.commit()


# ------------------------------------------------------------------ helpers --

def _img(rec, key="image_path"):
    return rec.get(key)


# -------------------------------------------------------------------- users --

def seed_users(*, db, models):
    if models['User'].query.count() > 0:
        return
    for spec in BENCHMARK_USERS:
        db.session.add(models['User'](
            email=spec["email"], password_hash=BENCHMARK_PASSWORD_HASH,
            display_name=spec["display"]))
    db.session.flush()


# ----------------------------------------------------------------- products --

def seed_products(*, db, models, load):
    Product = models['Product']
    if Product.query.count() > 0:
        return
    data = load("products.json")
    for p in data["products"]:
        db.session.add(Product(
            slug=p["slug"], name=p["name"], line=p["line"], flavor=p.get("flavor"),
            meta_description=p.get("meta_description"),
            flavor_text=p.get("flavor_text"),
            benefits=json.dumps(p.get("benefits", []), ensure_ascii=False),
            ingredients=json.dumps(p.get("ingredients", []), ensure_ascii=False),
            sizes=json.dumps(p.get("sizes", []), ensure_ascii=False),
            can_image=_img(p, "can_image_path") or p.get("can_image"),
            scene_image=_img(p, "scene_image_path") or p.get("scene_image")))
    db.session.flush()


# ------------------------------------------------------------------- events --

def seed_events(*, db, models, load):
    EventSeries = models['EventSeries']
    Event = models['Event']
    EventScheduleItem = models['EventScheduleItem']
    EventFaq = models['EventFaq']
    if Event.query.count() > 0:
        return
    series_data = load("event_series.json")
    series_by_slug = {}
    for s in series_data["series"]:
        row = EventSeries(slug=s["slug"], title=s["title"],
                          standfirst=s.get("standfirst"),
                          description=json.dumps(s.get("description", []), ensure_ascii=False),
                          image=_img(s) or s.get("image"))
        db.session.add(row)
        series_by_slug[s["slug"]] = row
    db.session.flush()

    events_data = load("events.json")
    for e in events_data["events"]:
        series = series_by_slug.get(e.get("series_slug"))
        reg = e.get("registration") or {}
        db.session.add(Event(
            slug=e["slug"], title=e["title"], standfirst=e.get("standfirst"),
            discipline=e.get("discipline"), status=e.get("status", "upcoming"),
            start_date=e.get("start_date"), end_date=e.get("end_date"),
            venue=e.get("venue"), city=e.get("city"), country=e.get("country"),
            country_code=e.get("country_code"),
            image=_img(e) or e.get("image"),
            hero_image=_img(e) or e.get("hero_image"),
            description=json.dumps(e.get("description", []), ensure_ascii=False),
            series_id=series.id if series else None,
            is_tv_event=bool(e.get("is_tv_event")),
            reg_price=reg.get("price"), reg_currency=reg.get("currency"),
            reg_title=reg.get("registration_title"),
            reg_type_name=reg.get("type_name")))
    db.session.flush()

    for e in events_data["events"]:
        event = Event.query.filter_by(slug=e["slug"]).first()
        for pos, item in enumerate(e.get("schedule", [])):
            db.session.add(EventScheduleItem(event_id=event.id, text=item,
                                             position=pos))
        for pos, faq in enumerate(e.get("faqs", [])):
            db.session.add(EventFaq(event_id=event.id,
                                    question=faq["question"],
                                    answer=faq["answer"], position=pos))
    db.session.flush()


# ----------------------------------------------------------------- athletes --

def seed_athletes(*, db, models, load):
    Athlete = models['Athlete']
    if Athlete.query.count() > 0:
        return
    data = load("athletes.json")
    for a in data["athletes"]:
        db.session.add(Athlete(
            slug=a["slug"], name=a["name"], standfirst=a.get("standfirst"),
            discipline=a.get("discipline"), dob=a.get("dob"),
            birthplace=a.get("birthplace"), age=a.get("age"),
            nationality=a.get("nationality"), career_start=a.get("career_start"),
            bio=json.dumps(a.get("bio", []), ensure_ascii=False),
            hero_image=_img(a) or a.get("hero_image")))
    db.session.flush()


# -------------------------------------------------------------------- films --

def seed_films(*, db, models, load):
    Film = models['Film']
    if Film.query.count() > 0:
        return
    data = load("films.json")
    for f in data["films"]:
        db.session.add(Film(
            slug=f["slug"], title=f["title"], subheading=f.get("subheading"),
            standfirst=f.get("standfirst"), discipline=f.get("discipline"),
            published=f.get("published"), duration=f.get("duration"),
            image=_img(f) or f.get("image")))
    db.session.flush()


# -------------------------------------------------------------------- shows --

def seed_shows(*, db, models, load):
    Show = models['Show']
    Episode = models['Episode']
    if Show.query.count() > 0:
        return
    data = load("shows.json")
    for s in data["shows"]:
        row = Show(slug=s["slug"], title=s["title"],
                   subheading=s.get("subheading"), standfirst=s.get("standfirst"),
                   discipline=s.get("discipline"), nr_seasons=s.get("nr_seasons"),
                   nr_episodes=s.get("nr_episodes"),
                   image=_img(s) or s.get("image"))
        db.session.add(row)
        db.session.flush()
        for ep in s.get("episodes", []):
            db.session.add(Episode(show_id=row.id, title=ep["title"],
                                   season=ep.get("season"), episode=ep.get("episode"),
                                   standfirst=ep.get("standfirst"),
                                   duration=ep.get("duration"),
                                   published=ep.get("published")))
    db.session.flush()


# ------------------------------------------------------------------ stories --

def seed_stories(*, db, models, load):
    Story = models['Story']
    if Story.query.count() > 0:
        return
    data = load("stories.json")
    for s in data["stories"]:
        db.session.add(Story(
            slug=s["slug"], title=s["title"], standfirst=s.get("standfirst"),
            discipline=s.get("discipline"), published=s.get("published"),
            body=json.dumps(s.get("body", []), ensure_ascii=False),
            hero_image=_img(s) or s.get("hero_image")))
    db.session.flush()


# --------------------------------------------------------------------- shop --

def seed_shop(*, db, models, load):
    ShopProduct = models['ShopProduct']
    ShopVariant = models['ShopVariant']
    if ShopProduct.query.count() > 0:
        return
    data = load("shop_products.json")
    for p in data["products"]:
        if not p.get("image_path") and not p.get("images"):
            continue
        row = ShopProduct(handle=p["handle"], title=p["title"],
                          vendor=p.get("vendor"), product_type=p.get("product_type"),
                          category=p["category"],
                          tags=json.dumps(p.get("tags", []), ensure_ascii=False),
                          description=p.get("description"),
                          image=_img(p) or (p.get("images") or [None])[0])
        db.session.add(row)
        db.session.flush()
        for v in p.get("variants", []):
            db.session.add(ShopVariant(
                product_id=row.id, title=v["title"], option1=v.get("option1"),
                option2=v.get("option2"), price=float(v["price"]) if v.get("price") is not None else None,
                sku=v.get("sku"), available=bool(v.get("available"))))
    db.session.flush()


# ---------------------------------------------------------- benchmark state --

def seed_benchmark_state(*, db, models, load):
    """Alice/Bob/Carol/Dana's orders, registrations and favorites.

    Deterministic fixtures (declared in provenance.json): fixed items,
    fixed codes, fixed timestamps.
    """
    ShopOrder = models['ShopOrder']
    ShopOrderLine = models['ShopOrderLine']
    EventRegistration = models['EventRegistration']
    Favorite = models['Favorite']
    User = models['User']
    if ShopOrder.query.count() > 0 or EventRegistration.query.count() > 0:
        return
    users = {u.email: u for u in User.query.all()}

    def event(slug):
        return models['Event'].query.filter_by(slug=slug).first()

    def variant_by_sku(sku):
        return models['ShopVariant'].query.filter_by(sku=sku).first()

    def product_by_handle(handle):
        return models['ShopProduct'].query.filter_by(handle=handle).first()

    # ---- Alice: one shop order + two event registrations + favorites ----
    alice = users.get("alice.j@test.com")
    if alice:
        lines = []
        for handle, sku_suffix, qty in (("fc-red-bull-salzburg-embossed-hoodie", None, 1),):
            product = product_by_handle(handle)
            if not product:
                continue
            variant = product.variants[0] if product.variants else None
            if variant:
                lines.append((variant, qty))
        if lines:
            total = round(sum(v.price * q for v, q in lines), 2)
            order = ShopOrder(order_number="RB-100234", user_id=alice.id,
                              status="shipped", placed_at="2026-09-18T15:04:11Z",
                              total=total, ship_name="Alice Johnson",
                              ship_email="alice.j@test.com")
            db.session.add(order)
            db.session.flush()
            for v, q in lines:
                db.session.add(ShopOrderLine(
                    order_id=order.id, variant_id=v.id,
                    product_title=v.product.title, variant_title=v.title,
                    sku=v.sku, unit_price=v.price, quantity=q))
        ev = event("red-bull-foam-wreckers-virginia-beach")
        if ev:
            db.session.add(EventRegistration(
                registration_code="RB7F3A21", user_id=alice.id, event_id=ev.id,
                ticket_type=ev.reg_type_name or "registration",
                first_name="Alice", last_name="Johnson",
                email="alice.j@test.com", price=ev.reg_price,
                currency=ev.reg_currency, status="confirmed",
                created_at="2026-09-21T09:12:33Z"))
        ev = event("red-bull-rapid-release")
        if ev:
            db.session.add(EventRegistration(
                registration_code="RB9C04D7", user_id=alice.id, event_id=ev.id,
                ticket_type="registration", first_name="Alice",
                last_name="Johnson", email="alice.j@test.com",
                price=ev.reg_price, currency=ev.reg_currency,
                status="confirmed", created_at="2026-09-22T18:40:02Z"))
        for kind, slug in (("event", "red-bull-foam-wreckers-narragansett"),
                           ("film", "chrysalis-an-izzi-gomez-surf-film"),
                           ("athlete", "sky-brown")):
            db.session.add(Favorite(user_id=alice.id, kind=kind, item_slug=slug))

    # ---- Bob: one past registration + favorites ----
    bob = users.get("bob.c@test.com")
    if bob:
        ev = event("red-bull-barn-find-open")
        if ev:
            db.session.add(EventRegistration(
                registration_code="RB2B8E90", user_id=bob.id, event_id=ev.id,
                ticket_type="registration", first_name="Bob", last_name="Chen",
                email="bob.c@test.com", price=ev.reg_price,
                currency=ev.reg_currency, status="confirmed",
                created_at="2026-09-05T11:26:47Z"))
        for kind, slug in (("story", "jreamz-wins-2026-red-bull-dance-your-style-national-final"),
                           ("show", "inside-pro-surfing"),
                           ("event", "sypher-showdown")):
            db.session.add(Favorite(user_id=bob.id, kind=kind, item_slug=slug))

    # ---- Carol: favorites only ----
    carol = users.get("carol.d@test.com")
    if carol:
        for kind, slug in (("event", "red-bull-wings-cup-united-states-2026"),
                           ("film", "9191")):
            db.session.add(Favorite(user_id=carol.id, kind=kind, item_slug=slug))

    # ---- Dana: clean account (no fixtures) ----
    db.session.flush()
