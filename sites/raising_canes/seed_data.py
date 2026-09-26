#!/usr/bin/env python3
"""Deterministic build-time seed for the Raising Cane's mirror.

Everything is materialized from the tracked source_data.json snapshot (real
data captured from the upstream properties on 2026-09-24 — see provenance.json).
The output must be byte-identical on every build: no wall clock, no random
salt, fixed insertion order, PYTHONHASHSEED=0 assumed.
"""
import hashlib
import json
import os
import re

from datetime import datetime
import json as _json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BENCHMARK_USERS = [
    {'username': 'alice_j', 'email': 'alice.j@test.com', 'display_name': 'Alice Johnson',
     'phone': '(225) 555-0142'},
    {'username': 'bob_c', 'email': 'bob.c@test.com', 'display_name': 'Bob Chen',
     'phone': '(281) 555-0177'},
    {'username': 'carol_d', 'email': 'carol.d@test.com', 'display_name': 'Carol Davis',
     'phone': '(214) 555-0198'},
    {'username': 'david_k', 'email': 'david.k@test.com', 'display_name': 'David Kim',
     'phone': '(512) 555-0121'},
]
BENCHMARK_PASSWORD = 'TestPass123!'
# bcrypt hash of BENCHMARK_PASSWORD (frozen so the seed DB is byte-reproducible;
# verified with bcrypt.check_password_hash(hash, 'TestPass123!') == True)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$PnCFwwnEYeF8Mgt0KFGSiOwDPEmD0ARKnfll0oLGJn8myyYD6oBIm')

# Official main-menu item names (raisingcanes.com/menu JSON-LD). The Olo
# catering platform spells the Caniac Combo with ®; the main menu uses ™.
MAIN_MENU_NAMES = {'The Caniac Combo®': 'The Caniac™ Combo'}

CATEGORY_SLUGS = {
    98194: ('combos', 'Combos'),
    97644: ('tailgates', 'Tailgates™'),
    97643: ('extras', 'Extras'),
    97642: ('drinks', 'Drinks'),
    97645: ('condiments', 'Condiments'),
}

CATEGORY_DESCRIPTIONS = {
    'combos': 'Order your favorite Combos in quantities of 10, 25, 50, or 100 to feed the whole Crew.',
    'tailgates': "Just craving Chicken Fingers? Order Tailgates™ of our hand-battered Chicken Fingers and craveable Cane’s Sauce®.",
    'extras': 'Hungry for more? Add Extras in whatever portion you need.',
    'drinks': 'Order 1 gallon JUGs of our freshly-brewed tea and freshly-squeezed lemonade.',
    'condiments': '',
}

MENU_IMAGES = {
    'the-box-combo': 'menu/box_combo.png',
    'the-3-finger-combo': 'menu/3finger_combo.png',
    'the-caniac-combo': 'menu/caniac_combo.png',
    'the-sandwich-combo': 'menu/sandwich_combo.png',
    'the-kids-combo': 'menu/kids_combo.png',
    '25-finger-tailgate': 'menu/tailgate_25.png',
    '50-finger-tailgate': 'menu/tailgate_50.png',
    '75-finger-tailgate': 'menu/tailgate_75.png',
    '100-finger-tailgate': 'menu/tailgate_100.png',
    '200-finger-tailgate': 'menu/tailgate_100.png',
    '300-finger-tailgate': 'menu/tailgate_100.png',
    'chicken-finger': 'menu/chicken_finger.png',
    'crinkle-cut-fries': 'menu/crinkle_fries.png',
    'canes-sauce': 'menu/canes_sauce.png',
    'texas-toast': 'menu/texas_toast.png',
    'coleslaw': 'menu/coleslaw.png',
    'chicken-sandwich': 'menu/chicken_sandwich.png',
    'ketchup': 'menu/ketchup.png',
    'sweet-tea': 'menu/sweet_tea.png',
    'unsweet-tea': 'menu/unsweet_tea.png',
    'half-tea-half-lemonade': 'menu/half_tea_lemonade.png',
    'lemonade': 'menu/lemonade.png',
    'jug-sweet-tea': 'menu/jug_sweet_tea.png',
    'jug-unsweet-tea': 'menu/jug_unsweet_tea.png',
    'jug-lemonade': 'menu/lemonade.png',
    'pan-of-crinkle-cut-fries': 'menu/crinkle_fries.png',
}

ORDER_IMAGES = {
    'the-box-combo': 'order/the_box_combo.png',
    'the-3-finger-combo': 'order/the_3_finger_combo.jpg',
    'the-caniac-combo': 'order/the_caniac_combo.png',
    'the-sandwich-combo': 'order/the_sandwich_combo.png',
    'the-kids-combo': 'order/the_kids_combo.png',
    '25-finger-tailgate': 'order/25_finger_tailgate.jpg',
    '50-finger-tailgate': 'order/50_finger_tailgate.jpg',
    '75-finger-tailgate': 'order/75_finger_tailgate.jpg',
    '100-finger-tailgate': 'order/100_finger_tailgate.jpg',
    '200-finger-tailgate': 'order/200_finger_tailgate.jpg',
    '300-finger-tailgate': 'order/300_finger_tailgate.jpg',
    'pan-of-crinkle-cut-fries': 'order/pan_of_crinkle_cut_fries.jpg',
    'texas-toast': 'order/texas_toast.jpg',
    'coleslaw': 'order/coleslaw.jpg',
    'canes-sauce': 'order/canes_sauce.jpg',
    'chicken-sandwich': 'order/sandwich.jpg',
    'jug-lemonade': 'order/jug_lemonade.png',
    'jug-sweet-tea': 'order/jug_sweet_tea.png',
    'jug-unsweet-tea': 'order/jug_unsweet_tea.png',
}

# The 25-Finger Tailgate price lives on the product card upstream (no option
# group), so mirror the same structure: a "Quantity" group per product.
TAILGATE_PRICES = {
    '25-finger-tailgate': [('1', 41.99)],
    '50-finger-tailgate': [('1', 79.99)],
    '75-finger-tailgate': [('1', 118.99)],
    '100-finger-tailgate': [('1', 142.99)],
    '200-finger-tailgate': [('1', 281.98)],
    '300-finger-tailgate': [('1', 420.97)],
}

GIFT_CARD_PRICES = [('5', 5.00), ('10', 10.00), ('15', 15.00), ('25', 25.00),
                    ('50', 50.00), ('75', 75.00), ('100', 100.00)]

NUTRITION_SECTION_RULES = [
    ('Individual Items', ['Chicken Finger', 'Crinkle-Cut Fries', 'Texas Toast',
                          'Coleslaw', "Cane's Sauce", 'Chicken Sandwich']),
    ('Combination Meals', ['3 Finger Combo', 'Box Combo', 'Caniac Combo',
                           'Sandwich Combo', 'Box Combo - The Posty Way', 'Kid']),
    ('Condiments & Extras', ['Honey Mustard', 'Ketchup', 'Louisiana', 'Kraft',
                             'Sugar Packet', 'Splenda', 'Equal', 'Sweet',
                             'Iodized', 'Black Pepper', 'Lemon Wedge', 'Milk 1%']),
]


def _slugify(name):
    s = name.replace('®', '').replace('™', '').replace("'", '')
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s


def _gift_card_number(seed_material):
    digest = hashlib.sha256(seed_material.encode('utf-8')).hexdigest()
    return '6049' + digest[:12]


def _caniac_card_number(seed_material):
    digest = hashlib.sha256(seed_material.encode('utf-8')).hexdigest()
    return '8823' + digest[:12]


def run_seed(db, MenuCategory, MenuItem, MenuOptionGroup,
                 MenuOption, NutritionRow, Location, GearProduct, GearVariant,
                 Job, FaqEntry, Article, Promotion, CaniacOffer, GiftCard):
    if MenuCategory.query.count() > 0:
        return

    src = json.load(open(os.path.join(BASE_DIR, 'source_data.json'), encoding='utf-8'))
    image_paths = src.get('image_paths', {})

    # ---- menu categories ----
    cat_by_id = {}
    for sort, (upstream_id, (slug, name)) in enumerate(CATEGORY_SLUGS.items()):
        cat = MenuCategory(slug=slug, name=name,
                           description=CATEGORY_DESCRIPTIONS.get(slug, ''), sort=sort)
        db.session.add(cat)
        cat_by_id[upstream_id] = cat
    db.session.flush()

    # ---- menu items + option groups ----
    for sort, product in enumerate(src['menu']['products']):
        slug = _slugify(product['name'])
        image = MENU_IMAGES.get(slug) or ORDER_IMAGES.get(slug) or ''
        item = MenuItem(
            slug=slug,
            name=MAIN_MENU_NAMES.get(product['name'], product['name']),
            category_id=cat_by_id[product['category']].id,
            description=product['description'].replace(' | ', '\n'),
            base_calories=product.get('base_cal'),
            max_calories=product.get('max_cal'),
            base_price=product.get('base_price'),
            image=image,
            sort=sort,
        )
        db.session.add(item)
        db.session.flush()

        group_sort = 0
        # quantity selector (combos, toast, slaw, sauce, tailgates, pans)
        qty_options = product.get('quantity_options') or []
        if qty_options:
            display_order = ['1', '10', '25', '50', '100']
            qty_options = sorted(qty_options,
                                 key=lambda c: display_order.index(c['name'])
                                 if c['name'] in display_order else 99)
            g = MenuOptionGroup(item_id=item.id, name='Quantity', mandatory=True,
                                multi=False, quantity_label=None, sort=group_sort)
            db.session.add(g)
            db.session.flush()
            for o in qty_options:
                db.session.add(MenuOption(group_id=g.id, name=o['name'],
                                          price_delta=o['price'] or 0.0, sort=0))
            group_sort += 1
            # per-quantity nested groups (customize + drink), exactly like upstream
            for qty_label, nested in (product.get('quantity_nested') or {}).items():
                for gname, choices in nested.items():
                    ng = MenuOptionGroup(item_id=item.id, name=gname, mandatory=True,
                                         multi=('Sandwich Combo' in product['name']
                                                and gname.startswith('Customize')),
                                         quantity_label=qty_label, sort=group_sort)
                    db.session.add(ng)
                    db.session.flush()
                    for o in choices:
                        db.session.add(MenuOption(group_id=ng.id, name=o['name'],
                                                  price_delta=o['price'] or 0.0, sort=0))
                    group_sort += 1
        elif slug in TAILGATE_PRICES:
            g = MenuOptionGroup(item_id=item.id, name='Quantity', mandatory=True,
                                multi=False, quantity_label=None, sort=group_sort)
            db.session.add(g)
            db.session.flush()
            for name, price in TAILGATE_PRICES[slug]:
                db.session.add(MenuOption(group_id=g.id, name=name,
                                          price_delta=price, sort=0))
            group_sort += 1
        elif slug == 'pan-of-crinkle-cut-fries':
            g = MenuOptionGroup(item_id=item.id, name='Quantity', mandatory=True,
                                multi=False, quantity_label=None, sort=group_sort)
            db.session.add(g)
            db.session.flush()
            for name, price in [('1 Pan', 17.43), ('2 Pan', 34.86),
                                ('3 Pan', 52.29), ('4 Pan', 69.72)]:
                db.session.add(MenuOption(group_id=g.id, name=name,
                                          price_delta=price, sort=0))
            group_sort += 1

        # always-on extra groups (sauce style, extra fingers)
        for gdata in product.get('extra_groups', []):
            g = MenuOptionGroup(item_id=item.id, name=gdata['description'],
                                mandatory=bool(gdata.get('mandatory')),
                                multi='Add Additional' in gdata['description'],
                                quantity_label=None, sort=group_sort)
            db.session.add(g)
            db.session.flush()
            for o in gdata['choices']:
                db.session.add(MenuOption(group_id=g.id, name=o['name'],
                                          price_delta=o['price'] or 0.0, sort=0))
            group_sort += 1

    # ---- nutrition rows (official upstream PDF) ----
    for row in src['nutrition']:
        name = row['name']
        section = 'Drinks'
        for sec, prefixes in NUTRITION_SECTION_RULES:
            if any(name.startswith(p) for p in prefixes):
                section = sec
                break
        values = row['values']
        db.session.add(NutritionRow(
            section=section, item_name=name, serving=row['serving'],
            calories=values[0], total_fat=values[1], sat_fat=values[2],
            trans_fat=values[3], cholesterol=values[4], sodium=values[5],
            total_carbs=values[6], fiber=values[7], sugars=values[8],
            protein=values[9], allergens=row['allergens'],
        ))

    # ---- locations (996 real restaurants) ----
    for slug, loc in sorted(src['locations'].items()):
        db.session.add(Location(
            slug=slug,
            street=loc['street'], city=loc['city'], state=loc['state'],
            zip_code=loc['zip'], phone=loc['phone'] or '',
            latitude=(loc.get('geo') or {}).get('latitude'),
            longitude=(loc.get('geo') or {}).get('longitude'),
            dine_in_hours=json.dumps(loc.get('dine_in_hours') or {}),
            drive_thru_hours=json.dumps(loc.get('drive_thru_hours') or {}),
            amenities='|'.join(loc.get('amenities') or []),
            offers='|'.join(loc.get('offers') or []),
            description=loc.get('description') or '',
        ))

    # ---- gear products ----
    # The upstream Shopify catalog types hats as product_type "Hats", while the
    # mirror's gear navigation exposes the upstream storefront collections
    # (Apparel / Headwear / Accessories / Plush / Gift Card). Map the raw type
    # onto the storefront collection name so every product stays reachable
    # from the primary navigation.
    COLLECTION_BY_TYPE = {'Hats': 'Headwear'}
    for sort, product in enumerate(src['gear']):
        tags = [t for t in (product.get('tags') or []) if not t.startswith('Category_')]
        category_tags = [t[len('Category_'):] for t in (product.get('tags') or [])
                         if t.startswith('Category_')]
        variants = product.get('variants') or []
        prices = [float(v['price']) for v in variants] or [0.0]
        main_image = image_paths.get(f"gear/{product['handle']}__0", '')
        alt_image = image_paths.get(f"gear/{product['handle']}__1", '')
        db.session.add(GearProduct(
            handle=product['handle'], title=product['title'],
            product_type=product.get('product_type') or '',
            collection=COLLECTION_BY_TYPE.get(product.get('product_type'),
                                              product.get('product_type')) or 'Accessories',
            price=min(prices),
            description=re.sub(r'<[^>]+>', ' ', product.get('body_html') or '').strip(),
            tags='|'.join(tags),
            image_main=main_image, image_alt=alt_image,
            new_item=any('New' in t for t in tags),
            sort=sort,
        ))
    db.session.flush()
    for product in src['gear']:
        gp = GearProduct.query.filter_by(handle=product['handle']).first()
        for v in (product.get('variants') or []):
            db.session.add(GearVariant(
                product_id=gp.id, title=v.get('title') or 'Default Title',
                price=float(v['price']), sku=v.get('sku') or '',
                available=bool(v.get('available', True)),
            ))

    # ---- jobs ----
    for job in src['jobs']:
        db.session.add(Job(
            reference=job['reference'], title=job['title'],
            department=job.get('brand') or 'Restaurant Crew',
            employment_type=', '.join(job.get('type') or []) or 'Full Time',
            street=job.get('street') or '', city=job.get('city') or '',
            state=job.get('state') or '', state_abbr=job.get('stateAbbr') or '',
            zip_code=job.get('zip') or '',
            apply_url=job.get('applyURL') or '',
        ))

    # ---- FAQ ----
    for entry in src['faq']:
        db.session.add(FaqEntry(category=entry['cat'], question=entry['q'],
                                answer=entry['a']))

    # ---- news + promotions ----
    for article in src['news']:
        slug = article.get('slug') or _slugify(article['title'])
        image = ''
        if 'Megan Moroney' in article['title']:
            image = 'home/news_megan_moroney.jpg'
        elif 'Brees' in article['title']:
            image = 'home/news_landon_donovan.jpg'
        elif 'Celebrities' in article['title']:
            image = 'home/news_fanatics_fest.jpg'
        elif 'Adrien' in article['title'] or 'Dunk Tank' in article['title']:
            image = 'home/news_adrien_brody.jpg'
        db.session.add(Article(slug=slug, title=article['title'],
                               published=article['date'],
                               category=article.get('category', "What's Happening"),
                               featured=bool(article.get('featured')),
                               image=image))
    for promo in src['promotions']:
        db.session.add(Promotion(title=promo, active=True))

    # ---- Caniac Club offers (mirrors the real members-only benefit structure) ----
    offers = [
        {'code': 'BDAY-BOX', 'title': 'Birthday Free Box Combo',
         'description': 'Happy birthday! Enjoy one free Box Combo® with the purchase of any combo.',
         'discount_type': 'dollars', 'value': 11.89, 'min_spend': 0.0},
        {'code': 'CANIAC-20', 'title': '20% Off Your Order',
         'description': 'Take 20% off your online order of $25 or more.',
         'discount_type': 'percent', 'value': 20.0, 'min_spend': 25.0},
        {'code': 'FREE-TEA', 'title': 'Free Large Sweet Tea',
         'description': 'A free Large Sweet Tea with any combo purchase.',
         'discount_type': 'dollars', 'value': 2.70, 'min_spend': 0.0},
        {'code': 'TAILGATE-10', 'title': '$10 Off Tailgates™',
         'description': 'Save $10 on any Tailgate™ order of $75 or more.',
         'discount_type': 'dollars', 'value': 10.0, 'min_spend': 75.0},
    ]
    for offer in offers:
        db.session.add(CaniacOffer(**offer))

    # ---- gift cards (deterministic test cards for balance-check tasks) ----
    gift_seed = [
        ('alice.j@test.com', 25.00), ('alice.j@test.com', 50.00),
        ('bob.c@test.com', 10.00), ('bob.c@test.com', 100.00),
        ('carol.d@test.com', 15.00), ('david.k@test.com', 75.00),
        ('', 250.00),
    ]
    for owner, amount in gift_seed:
        number = _gift_card_number(f'{owner}:{amount}')
        db.session.add(GiftCard(card_number=number, pin='2468',
                                balance=amount, initial_balance=amount,
                                owner_email=owner))

    db.session.commit()


def run_seed_users(db, User, Address, PaymentCard, CaniacCard,
                     UserOffer, FavoriteLocation, FoodOrder, FoodOrderItem,
                     GearOrder, GearOrderItem, GiftCard, Location, MenuItem,
                     GearProduct, CaniacOffer, bcrypt):
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    for data in BENCHMARK_USERS:
        user = User(email=data['email'], name=data['display_name'],
                    phone=data['phone'])
        user.password_hash = BENCHMARK_PASSWORD_HASH
        db.session.add(user)
    db.session.flush()

    alice = User.query.filter_by(email='alice.j@test.com').first()
    bob = User.query.filter_by(email='bob.c@test.com').first()
    carol = User.query.filter_by(email='carol.d@test.com').first()
    david = User.query.filter_by(email='david.k@test.com').first()

    # ---- addresses + payment cards ----
    addresses = [
        (alice, 'Home', '4321 Highland Road', 'Baton Rouge', 'LA', '70808', True),
        (alice, 'Office', '100 North St Suite 802', 'Baton Rouge', 'LA', '70802', False),
        (bob, 'Home', '815 Westheimer Road', 'Houston', 'TX', '77006', True),
        (carol, 'Home', '1902 North Central Expressway', 'McKinney', 'TX', '75069', True),
        (david, 'Home', '5501 Little York Road', 'Houston', 'TX', '77016', True),
    ]
    for user, label, line1, city, state, zip_code, default in addresses:
        db.session.add(Address(user_id=user.id, label=label, line1=line1,
                               city=city, state=state, zip_code=zip_code,
                               is_default=default))
    cards = [
        (alice, 'Personal', 'Visa', '4242', 9, 2027, True),
        (alice, 'Backup', 'Mastercard', '5309', 4, 2026, False),
        (bob, 'Personal', 'Visa', '1881', 11, 2027, True),
        (carol, 'Personal', 'Discover', '6011', 7, 2028, True),
        (david, 'Personal', 'Visa', '7356', 2, 2026, True),
    ]
    for user, label, brand, last4, month, year, default in cards:
        db.session.add(PaymentCard(user_id=user.id, label=label, brand=brand,
                                   last4=last4, exp_month=month, exp_year=year,
                                   is_default=default))

    # ---- Caniac Club cards + offers ----
    caniac = [
        (alice, 1275), (bob, 340), (carol, 560), (david, 92),
    ]
    for user, points in caniac:
        number = _caniac_card_number(user.email)
        db.session.add(CaniacCard(user_id=user.id, card_number=number,
                                  points=points))
    offers = CaniacOffer.query.order_by(CaniacOffer.id).all()
    # Alice: birthday offer + 20% offer; Bob: free tea; Carol: tailgate offer; David: birthday offer
    claims = [
        (alice, 0), (alice, 1),
        (bob, 2),
        (carol, 3),
        (david, 0),
    ]
    for user, idx in claims:
        db.session.add(UserOffer(user_id=user.id, offer_id=offers[idx].id))

    # ---- favorite locations ----
    def loc_by_slug(slug):
        return Location.query.filter_by(slug=slug).first()

    fav_slugs = [
        (alice, 'la_baton-rouge_6588-siegen-lane'),
        (alice, 'tx_houston_4055-little-york-rd'),
        (bob, 'tx_houston_4055-little-york-rd'),
        (carol, 'tx_mckinney_1902-north-central-expressway'),
        (david, 'tx_houston_12201-westheimer-rd'),
    ]
    for user, slug in fav_slugs:
        loc = loc_by_slug(slug)
        if loc:
            db.session.add(FavoriteLocation(user_id=user.id, location_id=loc.id))

    # ---- past food orders (real locations, real products, deterministic) ----
    def item_by_slug(slug):
        return MenuItem.query.filter_by(slug=slug).first()

    def make_food_order(user, loc_slug, mode, date_label, time_label, name,
                        phone, payment, lines, order_number, discount=0.0,
                        offer_code='', placed_day=20):
        loc = loc_by_slug(loc_slug)
        subtotal = round(sum(l[2] for l in lines), 2)
        tax = round((subtotal - discount) * 0.0825, 2)
        total = round(subtotal - discount + tax, 2)
        order = FoodOrder(
            order_number=order_number, user_id=user.id, location_id=loc.id,
            pickup_mode=mode, pickup_date=date_label, pickup_time=time_label,
            contact_name=name, contact_phone=phone, payment_method=payment,
            caniac_offer=offer_code, subtotal=subtotal, discount=discount,
            tax=tax, total=total, status='Completed',
            placed_at=__import__('datetime').datetime(2026, 9, placed_day, 12, 0),
            points_earned=int(total),
        )
        order.items = [FoodOrderItem(item_id=item_by_slug(l[0]).id,
                                     quantity_label=l[1], selections=json.dumps(l[3]),
                                     line_total=l[2]) for l in lines]
        db.session.add(order)

    make_food_order(
        alice, 'la_baton-rouge_6588-siegen-lane', 'Pickup', '2026-09-18',
        '6:15 PM', 'Alice Johnson', alice.phone, 'Visa ending 4242',
        [('the-box-combo', '1', 11.89, ['Regular', 'Regular Sweet Tea']),
         ('canes-sauce', '10', 4.50, [])],
        'RC-100235', placed_day=18)
    make_food_order(
        alice, 'tx_houston_4055-little-york-rd', 'Curbside', '2026-09-20',
        '1:30 PM', 'Alice Johnson', alice.phone, 'Visa ending 4242',
        [('the-caniac-combo', '1', 16.89, ['No Slaw (NSL)', 'Large Coke®']),
         ('texas-toast', '25', 34.50, [])],
        'RC-100236', discount=2.70, offer_code='FREE-TEA', placed_day=20)
    make_food_order(
        bob, 'tx_houston_4055-little-york-rd', 'Pickup', '2026-09-21',
        '7:45 PM', 'Bob Chen', bob.phone, 'Visa ending 1881',
        [('the-3-finger-combo', '10', 98.90, ['Regular', 'Regular Coke®']),
         ('jug-sweet-tea', '1', 5.99, [])],
        'RC-100237', placed_day=21)
    make_food_order(
        carol, 'tx_mckinney_1902-north-central-expressway', 'Pickup', '2026-09-22',
        '12:15 PM', 'Carol Davis', carol.phone, 'Discover ending 6011',
        [('the-kids-combo', '25', 169.75, ['Milk']),
         ('pan-of-crinkle-cut-fries', '2 Pan', 34.86, [])],
        'RC-100238', placed_day=22)
    make_food_order(
        david, 'tx_houston_12201-westheimer-rd', 'Curbside', '2026-09-22',
        '8:00 PM', 'David Kim', david.phone, 'Visa ending 7356',
        [('25-finger-tailgate', '1', 41.99, ['Individual Sauces']),
         ('jug-lemonade', '1', 10.89, [])],
        'RC-100239', placed_day=22)

    # ---- past gear orders ----
    def gear_by_handle(handle):
        return GearProduct.query.filter_by(handle=handle).first()

    def make_gear_order(user, email, name, line1, city, state, zip_code,
                        payment, lines, order_number, placed_day=12):
        subtotal = round(sum(l[2] for l in lines), 2)
        shipping = 0.0 if subtotal >= 50 else 6.95
        order = GearOrder(
            order_number=order_number, user_id=user.id, email=email,
            ship_name=name, ship_line1=line1, ship_city=city, ship_state=state,
            ship_zip=zip_code, payment_method=payment, subtotal=subtotal,
            shipping=shipping, total=round(subtotal + shipping, 2),
            placed_at=__import__('datetime').datetime(2026, 9, placed_day, 10, 0),
        )
        order.items = [GearOrderItem(product_id=gear_by_handle(l[0]).id,
                                     variant_title=l[1], qty=1, price=l[2])
                       for l in lines]
        db.session.add(order)

    make_gear_order(
        alice, alice.email, 'Alice Johnson', '4321 Highland Road',
        'Baton Rouge', 'LA', '70808', 'Visa ending 4242',
        [('raising-canes-retro-crewneck', 'M', 39.99),
         ('mid-profile-raising-canes-cap', 'Default Title', 19.99)],
        'GEAR-4502', placed_day=12)
    make_gear_order(
        bob, bob.email, 'Bob Chen', '815 Westheimer Road', 'Houston', 'TX',
        '77006', 'Visa ending 1881',
        [('cool-cane-era-tumbler-40oz', 'Default Title', 34.99),
         ('mini-canes-sauce-bag-charm', 'Default Title', 9.99),
         ('classic-trucker-hat', 'Default Title', 27.99)],
        'GEAR-4503', placed_day=15)

    db.session.commit()


def canonicalize():
    """Rebuild the SQLite file deterministically (VACUUM) after seeding so the
    seed DB is byte-identical on every build."""
    import sqlite3
    path = os.path.join(BASE_DIR, 'instance', 'raising_canes.db')
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.execute('VACUUM')
    conn.close()


if __name__ == '__main__':
    from app import (app, bcrypt, db, Address, Article, CaniacCard, CaniacOffer,
                     ContactSubmission, FaqEntry, FavoriteLocation, FoodOrder,
                     FoodOrderItem, GearOrder, GearOrderItem, GearProduct,
                     GearVariant, GiftCard, Job, Location, MenuCategory,
                     MenuItem, MenuOption, MenuOptionGroup, NutritionRow,
                     PaymentCard, Promotion, User, UserOffer)
    with app.app_context():
        run_seed(db, MenuCategory, MenuItem, MenuOptionGroup, MenuOption,
                 NutritionRow, Location, GearProduct, GearVariant, Job,
                 FaqEntry, Article, Promotion, CaniacOffer, GiftCard)
        run_seed_users(db, User, Address, PaymentCard, CaniacCard, UserOffer,
                       FavoriteLocation, FoodOrder, FoodOrderItem, GearOrder,
                       GearOrderItem, GiftCard, Location, MenuItem, GearProduct,
                       CaniacOffer, bcrypt)
    canonicalize()
    print('Raising Cane’s seed complete.')
