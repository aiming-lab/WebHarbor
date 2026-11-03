#!/usr/bin/env python3
"""Deterministic seeder for the united_airlines mirror.

Run from sites/united_airlines/:  PYTHONHASHSEED=0 python3 seed_data.py

All catalog rows come from the tracked source_data_*.json snapshots (real
united.com data captured 2026-09-28).
Every seed function is gated at the function level so re-running the boot
path is a no-op and /reset stays byte-identical. The four benchmark members
share one frozen bcrypt digest so the SQLite seed is byte-reproducible.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import random
import re

from app import (app, db, BENCHMARK_PASSWORD_HASH, MIRROR_DATE, MIRROR_TODAY,
                 Activity, Aircraft, Airport, BaggageItem, Booking,
                 BookingLeg, CabinInfo, Deal, Fare, Flight, HelpArticle,
                 Passenger, PolicyArticle, User,
                 base_fare_for, boarding_group, generate_confirmation)

SITE = pathlib.Path(__file__).resolve().parent
SEED_USERS = [
    # email, first, last, miles, pqf, pqp, tier, phone
    ('alice.j@example.com', 'Alice', 'Johnson', 68450, 9, 3420,
     'Premier Silver', '+1 555 010 1234'),
    ('bob.m@example.com', 'Bob', 'Miller', 143200, 31, 9180,
     'Premier Gold', '+1 555 010 5678'),
    ('carol.w@example.com', 'Carol', 'Williams', 5210, 2, 640,
     'Member', '+1 555 010 9012'),
    ('dave.t@example.com', 'Dave', 'Thomas', 98760, 48, 16500,
     'Premier Platinum', '+1 555 010 3456'),
]

# Curated help-center articles (question/answer pairs distilled from the
# captured help-center SDL pages — see source_data_content.json help-center).
HELP_ARTICLES = [
    ('check-in-online', 'Check-in',
     'How early can I check in for my flight?',
     'Online check-in opens 24 hours before departure and closes 60 minutes '
     'before departure for most flights. You can check in on united.com or the '
     'United app from the Check-in tab with your confirmation number and last '
     'name, or through your MileagePlus account.', ['bags-check-in', 'boarding-passes']),
    ('boarding-passes', 'Check-in',
     'When do I get my boarding pass and boarding group?',
     'Your boarding pass is issued as soon as you finish online check-in. '
     'Boarding groups are assigned by cabin and Premier status: Pre-board for '
     'Premier 1K, Group 1 for Business, First, Premium Plus, Premier Gold and '
     'Platinum, Group 2 for Premier Silver and Economy Plus, Groups 3-5 for '
     'United Economy, and Basic Economy boards in Group 6.',
     ['check-in-online']),
    ('bags-check-in', 'Baggage',
     'Can I pay for bags before I get to the airport?',
     'Yes. Prepay for your first and second checked bags online up to 24 hours '
     'before departure and you pay the discounted online price ($35 for the '
     'first bag, $40 for the second on most domestic routes) instead of the '
     'airport price ($40 / $45).', ['bag-fees', 'bag-weight']),
    ('bag-fees', 'Baggage',
     'How much does a checked bag cost?',
     'For most domestic routes the first checked bag is $35 when you prepay '
     'online ($40 at the airport) and the second is $40 online ($45 at the '
     'airport). Additional bags are $150 each. Premier members get free '
     'checked bags: 1 for Premier Silver, 2 for Premier Gold and 3 for '
     'Premier Platinum and Premier 1K, each up to 70 lb in Economy.',
     ['bags-check-in', 'premier-bags']),
    ('bag-weight', 'Baggage',
     'What is the weight limit for a checked bag?',
     'Checked bags may weigh up to 50 lb (23 kg) in United Economy and '
     'Premium Economy, and up to 70 lb (32 kg) in United Business, United '
     'First and United Polaris, and for all Premier members. Bags over the '
     'limit are charged $100 for 51-70 lb and $200 for 71-100 lb; nothing '
     'over 100 lb is accepted.', ['bag-fees']),
    ('carry-on-rules', 'Baggage',
     'What can I bring on board for free?',
     'Every United fare includes one personal item (up to 9 x 10 x 17 '
     'inches) that fits under the seat. Standard United Economy and '
     'premium fares also include a full-size carry-on bag (up to 9 x 14 x '
     '22 inches). Basic Economy includes the carry-on only on flights to '
     'Canada, South America, across the Atlantic or across the Pacific; '
     'Premier members and primary cardmembers always get it. Smart bags '
     'with lithium batteries must have the battery removed, and TSA '
     'liquid rules apply.',
     ['bag-fees', 'basic-economy-rules']),
    ('premier-bags', 'MileagePlus',
     'How many free checked bags do Premier members get?',
     'Premier Silver gets 1 free checked bag, Premier Gold 2, and Premier '
     'Platinum and Premier 1K get 3 free checked bags in Economy (up to 70 lb '
     'each). Premium cabin travelers also check up to 2 bags free at 70 lb.',
     ['premier-qualify', 'bag-fees']),
    ('premier-qualify', 'MileagePlus',
     'How do I earn Premier status?',
     'You need a combination of Premier qualifying flights (PQF) and Premier '
     'qualifying points (PQP): Premier Silver at 12 PQF and 4,000 PQP (or '
     '5,000 PQP), Premier Gold at 24 PQF and 8,000 PQP (or 10,000 PQP), '
     'Premier Platinum at 36 PQF and 12,000 PQP (or 15,000 PQP) and Premier '
     '1K at 54 PQF and 18,000 PQP (or 24,000 PQP). You must fly at least 4 '
     'paid segments on United or United Express each year.',
     ['premier-earn', 'premier-bags']),
    ('premier-earn', 'MileagePlus',
     'How many miles do I earn when I fly?',
     'Members earn 5 award miles per $1 of base fare, Premier Silver 7, '
     'Premier Gold 8, Premier Platinum 9 and Premier 1K 11. You also earn 1 '
     'PQP for every dollar of base fare, and 1 PQF per flight (Basic Economy '
     'tickets do not earn PQF).', ['premier-qualify', 'award-travel']),
    ('award-travel', 'MileagePlus',
     'How do I book award travel with miles?',
     'Sign in to your MileagePlus account, search for flights, and choose the '
     'Book with miles option at payment. Award pricing is dynamic but the '
     'mirror shows the exact miles needed for each fare before you pay. '
     'Miles are deducted when the booking is confirmed and the redemption is '
     'listed in your account activity.', ['premier-earn', 'change-award']),
    ('change-award', 'MileagePlus',
     'Can I get my miles back if I cancel an award flight?',
     'Award tickets canceled before departure return the miles to your '
     'account with no redeposit fee; the fee is waived for all members who '
     'cancel. If you do not show up for your flight, a $125 service fee '
     'applies to redeposit your award miles and it is nonrefundable. '
     'Redeposited miles are ready to use again in 5 to 7 business days.',
     ['award-travel']),
    ('change-flight', 'Changes & cancellations',
     'Can I change my flight after booking?',
     'Yes. United does not charge a change fee on standard United Economy and '
     'premium cabin tickets — you only pay the fare difference if the new '
     'flight is more expensive. Basic Economy tickets cannot be changed.',
     ['same-day-change', 'cancel-flight']),
    ('same-day-change', 'Changes & cancellations',
     'What is the same-day change option?',
     'You can move to a different flight on the same day between the same '
     'airports for a fee of up to $75, or for free on standby if you are a '
     'Premier member.', ['change-flight']),
    ('cancel-flight', 'Changes & cancellations',
     'Can I cancel my trip and get a refund?',
     'Yes. Under the 24-hour flexible booking policy you can cancel any trip '
     'booked within the last 24 hours for a full refund. Standard Economy '
     'and premium cabin tickets are refunded to the original payment method; '
     'Basic Economy tickets are not refundable but keep their value as a '
     'future flight credit.', ['change-flight', 'basic-economy-rules']),
    ('basic-economy-rules', 'Changes & cancellations',
     'What are the Basic Economy rules?',
     'Basic Economy is United\'s lowest fare. You get a full carry-on bag '
     'and an assigned seat at check-in, but tickets cannot be changed and are '
     'not refundable after the 24-hour booking window, boarding is in Group '
     '5, and you do not earn PQF. Advance seat assignments start at $15.',
     ['cancel-flight', 'carry-on-rules']),
    ('economy-plus', 'Cabins',
     'What is Economy Plus?',
     'Economy Plus seats offer up to 6 extra inches of legroom and are '
     'located toward the front of the Economy cabin. Prices start at $29 per '
     'flight. Premier Gold and above can select Economy Plus at booking for '
     'free; Premier Silver gets it free at check-in.',
     ['cabin-choice', 'premier-qualify']),
    ('cabin-choice', 'Cabins',
     'What cabins does United fly?',
     'United flies United First and United Business (domestic premium '
     'cabins), United Polaris business class on long-haul international '
     'flights, United Premium Plus premium economy, Economy Plus extra-'
     'legroom seats and United Economy. Basic Economy is the lowest fare in '
     'the Economy cabin.', ['economy-plus', 'polaris']),
    ('polaris', 'Cabins',
     'What is United Polaris business class?',
     'United Polaris is the long-haul business class: a 1-1-1 or 1-2-1 '
     'forward-facing seat that converts to a fully flat 6\'6" bed, Saks Fifth '
     'Avenue bedding, amenity kits, and Polaris lounge access before your '
     'flight.', ['cabin-choice']),
    ('flight-status-howto', 'Flight status',
     'How do I check my flight status?',
     'Open the Flight status tab and search by flight number, or search by '
     'route with the origin and destination airports and the date. Status '
     'pages show scheduled and estimated times, gates, terminals, aircraft '
     'type and links to the aircraft details.', ['check-in-online']),
    ('pets', 'Traveling',
     'Can I bring my pet on board?',
     'Pets can travel in cabin for a $125 fee each way on most flights '
     '(tickets purchased on or after 4/26/2024), subject to space. Service '
     'animals fly free.', ['carry-on-rules']),
    ('wifi', 'Onboard',
     'Is Wi-Fi available on board?',
     'Yes. United offers satellite Wi-Fi on most aircraft; per-flight pricing '
     'applies on U.S. domestic and short-haul international flights, and '
     'monthly subscriptions start at $49. Also, Starlink fast Wi-Fi is being '
     'rolled out across the fleet.', ['seat-entertainment']),
    ('seat-entertainment', 'Onboard',
     'What entertainment is on board?',
     'Seatback on-demand entertainment is available on most widebody and many '
     'narrowbody aircraft; personal device entertainment streams to your '
     'phone or laptop on Wi-Fi-equipped aircraft.', ['wifi']),
]

CABIN_PAGES = [
    ('basic-economy', 'Basic Economy',
     'United\'s lowest fare — personal item included, seat at check-in',
     'static/images/cabins_basic-economy/basic-economy-HERO-desktop-4095x1080.png',
     ['Personal item that fits under the seat',
      'Full-size carry-on only on international routes (Canada, South America, transatlantic, transpacific)',
      'Free carry-on for Premier members and cardholders',
      'Seat assigned at check-in (advance assignment from $15)',
      'Boards in Group 6', 'No changes permitted', 'No PQF earned']),
    ('united-economy', 'United Economy®',
     'The standard cabin on every United flight',
     'static/images/cabins_united-economy/JS_ECONOMY_2023_1617_rs-DeNoiseAI-Copy-3-864x360.jpg',
     ['Free seat selection at booking', 'No change fees',
      'First checked bag $35 online', 'Earn 5-11 miles per $1 based on tier']),
    ('economy-plus', 'Economy Plus®',
     'Extra legroom toward the front of the Economy cabin',
     'static/images/cabins_economy-plus/economy-plus-3.jpg',
     ['Up to 6 more inches of legroom', 'From $29 per flight',
      'Free at booking for Premier Gold and above', 'Free at check-in for Premier Silver']),
    ('premium-plus', 'United Premium Plus®',
     'Premium economy on long-haul international routes',
     'static/images/cabins_premium-plus/united-premium-plus-image-2x.png',
     ['Wider seat with deeper recline', 'Elevated dining service',
      'Amenity kit and Saks Fifth Avenue blanket',
      'Priority boarding in Group 2', '2 free checked bags at 50 lb']),
    ('united-first-business', 'United First® / United Business®',
     'The premium cabin on North American flights',
     'static/images/cabins_united-first-business/first-class.png',
     ['Spacious seat with extra recline', 'Pre-departure beverage service',
      'Dining on real dishware', 'Priority boarding and check-in',
      '2 free checked bags at 70 lb']),
    ('united-polaris', 'United Polaris® business class',
     'Business class on long-haul international routes',
     'static/images/cabins_united-polaris/source_POLARIS_UPP_230425_SLE0905_rs_v3.jpg',
     ['Lie-flat 6\'6" seat', 'Saks Fifth Avenue bedding',
      'Polaris lounge access', 'Slippers and amenity kit',
      '2 free checked bags at 70 lb']),
]

POLICY_PAGES = [
    ('flight-change', 'Flight changes',
     'Change your flight any time before departure. United charges no change '
     'fee on standard United Economy and premium cabin fares — you only pay '
     'the fare difference. Basic Economy tickets cannot be changed.',
     [['Standard Economy and premium cabins', 'No change fee, only the fare difference'],
      ['Basic Economy', 'Not changeable'],
      ['Same-day change', 'Up to $75, or free standby for Premier members'],
      ['24-hour flexible booking', 'Full refund within 24 hours of booking']]),
    ('refund-policy', 'Refunds',
     'Refundable fares are refunded to the original payment method. '
     'Non-refundable fares keep their value as a future flight credit. '
     'Tickets canceled within 24 hours of booking are always fully refunded.',
     [['24-hour flexible booking policy', 'Full refund, no charge'],
      ['Standard Economy and premium cabins', 'Refund to original payment'],
      ['Basic Economy', 'Future flight credit only'],
      ['Award tickets', 'Miles redeposited free after canceling; $125 no-show fee']]),
    ('flexible-booking-options', 'Flexible booking options',
     'United lets you hold, change and cancel trips with fewer fees. FareLock '
     'holds your fare and price for a small fee starting at $5.99 for three '
     'days, and future flight credits never expire.',
     [['FareLock hold', 'From $5.99 for three days'],
      ['Change fees', 'None on standard fares'],
      ['Future flight credit', 'Does not expire'],
      ['Award redeposit fee', 'Free after canceling; $125 for no-shows']]),
    ('missed-delayed-canceled', 'Missed, delayed and canceled flights',
     'If your flight is significantly delayed or canceled, you can switch to '
     'another flight in the app or on united.com, get a meal or hotel voucher '
     'in some cases, or cancel for a full refund.',
     [['Significant delay or cancellation', 'Free rebooking on the next available flight'],
      ['Cancel after a cancellation', 'Full refund to original payment'],
      ['Delays in the app', 'Automatic rebooking options offered'],
      ['Missed connection', 'Rebooked on the next available flight']]),
]


# Real upstream seat map images per aircraft family (see asset_inventory.json).
SEAT_MAP_IMAGES = {
    'Airbus A319': 'images/fleet/Airbus-319_SeatMap.png',
    'Airbus A320': 'images/fleet/Airbus-320_SeatMap.png',
    'Airbus A321neo': 'images/fleet/0043-A-Airbus-321-NEO_SeatMap_3850x1100.jpg',
    'Boeing 737 MAX 8': 'images/fleet/737-900-MAX9_Seatmap.png',
    'Boeing 737 MAX 9': 'images/fleet/737-900-MAX9_Seatmap.png',
    'Boeing 737-700': 'images/fleet/737-700_Seatmap.png',
    'Boeing 737-800': 'images/fleet/737-900-V1_Seatmap.png',
    'Boeing 737-800SFP': 'images/fleet/737-900-V2_Seatmap.png',
    'Boeing 737-900': 'images/fleet/737-900-V3_Seatmap.png',
    'Boeing 737-900ER': 'images/fleet/737-900-V3_Seatmap.png',
    'Boeing 757-200': 'images/fleet/0024_757-200_SeatMap_3850x1100.png',
    'Boeing 757-300': 'images/fleet/757-300_SeatMap.png',
    'Boeing 767-300': 'images/fleet/767-300-V3_SeatMap.png',
    'Boeing 767-300ER': 'images/fleet/767-300-V2_SeatMap.png',
    'Boeing 767-400ER': 'images/fleet/767-400_V2_Seatmap.png',
    'Boeing 777-200': 'images/fleet/777-200_V1_Seat_Map.png',
    'Boeing 777-200ER': 'images/fleet/777-200_V2_SeatMap.png',
    'Boeing 777-200 (777)': 'images/fleet/777-200_V1_SeatMap.png',
    'Boeing 777-300ER': 'images/fleet/777-300ER_SeatMap.png',
    'Boeing 787-8': 'images/fleet/787-8_SeatMap.png',
    'Boeing 787-9': 'images/fleet/0024_AO_787-9-Hi-J_SeatMap-R15-DRAFT.png',
    'Boeing 787-10': 'images/fleet/787-10_SeatMap.png',
    'Boeing 787-10 Dreamliner': 'images/fleet/787-10_SeatMap.png',
}


def _load(name: str):
    return json.loads((SITE / name).read_text())


def seed_database() -> None:
    if Airport.query.count() > 0:
        return

    airports_doc = _load('source_data_airports.json')
    for code, a in sorted(airports_doc.items()):
        db.session.add(Airport(code=code, name=a['name'], city=a['city'],
                               state=a.get('state', ''),
                               country=a['country'],
                               latitude=a['latitude'], longitude=a['longitude'],
                               is_hub=a.get('hub', False),
                               region=a.get('region', 'International')))

    aircraft_doc = _load('source_data_aircraft.json')
    aircraft_ids = {}
    for key, spec in sorted(aircraft_doc.items()):
        letters = ['A', 'B', 'C', 'D', 'E', 'F']
        first_rows = premium_rows = eplus_rows = economy_rows = 0
        for band in spec.get('cabin_specs_full') or []:
            if 'polaris' in band['name'].lower() or 'first' in band['name'].lower() \
                    or 'business' in band['name'].lower():
                first_rows += band['rows']
                letters = band['letters']
            elif 'premium plus' in band['name'].lower():
                premium_rows += band['rows']
                letters = band['letters'] or letters
            elif 'economy plus' in band['name'].lower():
                eplus_rows += band['rows']
                letters = band['letters'] or letters
            else:
                economy_rows += band['rows']
                letters = band['letters'] or letters
        # Total seat rows = the sum of every cabin's rows in the captured
        # interior specifications (787-9: 12+3+5+17 = 37, 777-300ER: 15+3+7+21
        # = 46). Derived from the upstream seat table, not a constant.
        seat_rows = first_rows + premium_rows + eplus_rows + economy_rows
        if not (first_rows or premium_rows or eplus_rows):
            # fall back to captured cabin specs (letter codes from the ops API)
            first_rows, premium_rows, eplus_rows, seat_rows = 4, 0, 4, 22
            for cs in spec.get('cabin_specs') or []:
                if cs['code'] in ('J', 'F'):
                    first_rows = max(4, cs['seats'] // 4)
                elif cs['code'] == 'O':
                    premium_rows = max(0, cs['seats'] // 6)
                elif cs['code'] == 'Y':
                    seat_rows = max(20, cs['seats'] // 6)
        # exit_rows = first/last row of the United Economy band
        economy_first = first_rows + premium_rows + eplus_rows + 1
        aircraft = Aircraft(key=key, name=spec['name'] or key,
                            description=spec.get('description', ''),
                            seat_rows=seat_rows,
                            exit_rows=[economy_first, seat_rows],
                            seat_letters=letters,
                            first_rows=first_rows, economy_plus_rows=eplus_rows,
                            premium_rows=premium_rows,
                            wifi=spec.get('wifi', ''),
                            cabin_specs=spec.get('cabin_specs_full') or [],
                            specs=spec.get('specs', {}),
                            seat_map_image=SEAT_MAP_IMAGES.get(spec['name'] or key, ''),
                            seat_map_config=spec.get('seat_config_code', ''))
        db.session.add(aircraft)
        aircraft_ids[key] = aircraft

    db.session.flush()

    flights_doc = _load('source_data_flights.json')
    rng = random.Random(20260928)
    for row in flights_doc['flights']:
        key = row.get('aircraft_key') or ''
        aircraft = aircraft_ids.get(key)
        if aircraft is None:
            # choose a deterministic narrowbody fallback for captured flights
            fallback = sorted(k for k in aircraft_ids
                              if k and re.match(r'^(3|7)', k))[:3]
            aircraft = aircraft_ids.get(fallback[0]) if fallback else None
        if aircraft is None:
            continue
        dep = dt.datetime.strptime(row['departure'], '%H:%M')
        arr = dt.datetime.strptime(row['arrival'], '%H:%M')
        duration = int((arr - dep).total_seconds() // 60) % (24 * 60)
        if duration < 45:
            duration += 24 * 60
        # long-haul westbound flights land next day local: honor the real
        # great-circle distance as a floor (block speed ~850 km/h)
        origin = db.session.get(Airport, row['origin'])
        dest = db.session.get(Airport, row['dest'])
        distance = origin.distance_to(dest)
        duration = max(duration, int(distance / 850 * 60))
        flight = Flight(flight_number=row['number'],
                        origin_code=row['origin'], dest_code=row['dest'],
                        departure=row['departure'], arrival=row['arrival'],
                        duration_minutes=duration,
                        aircraft_key=aircraft.key,
                        status_note=row.get('status', ''),
                        gate=row.get('gate', ''),
                        terminal=row.get('terminal', ''))
        db.session.add(flight)
        db.session.flush()
        # deterministic per-flight fare ladder anchored on route distance
        origin = db.session.get(Airport, row['origin'])
        dest = db.session.get(Airport, row['dest'])
        distance = int(origin.distance_to(dest))
        seed_key = f'{row["number"]}|{row["origin"]}{row["dest"]}'
        for cabin, _label in app.config.get('FARE_FAMILIES') or []:
            pass
        from app import FARE_FAMILIES  # noqa: WPS433
        for cabin, _label in FARE_FAMILIES:
            amount = base_fare_for(distance, cabin, seed_key)
            miles = int(amount * 100 / 5) * 5
            db.session.add(Fare(flight_id=flight.id, cabin=cabin,
                                amount=amount, miles=miles,
                                seats_left=rng.randint(2, 9)))

    _seed_cabins()
    _seed_help()
    _seed_policies()
    _seed_deals()
    db.session.commit()


def _cabin_body_blocks(blocks):
    """Reduce the captured upstream SDL blocks to a renderable page body.

    The SDL captures mix real content with navigation: 'card' blocks are
    link/summary cards whose text duplicates the headings and paragraphs
    around them, short paragraphs right under a card repeat its title as an
    anchor, accordion FAQs repeat each question heading after its answer,
    and tables repeat their header row as the first body row. Drop those,
    and reshape list-like paragraphs (feature cards flattened into one
    paragraph) into proper lists so nothing reads as a run-on sentence.
    """
    body = []
    seen_headings = set()
    for i, b in enumerate(blocks):
        kind = b.get('kind')
        if kind == 'card':
            continue
        if kind == 'heading':
            text = ' '.join(b.get('text', '').split())
            if b.get('level') == 1 or not text or text in seen_headings:
                continue                  # page title / repeated accordion
            seen_headings.add(text)
            body.append({'kind': 'heading', 'text': text})
        elif kind == 'para':
            text = b.get('text', '')
            prev = blocks[i - 1] if i else None
            if prev and prev.get('kind') == 'card' \
                    and text.strip() == prev.get('title', '').strip():
                continue                  # nav anchor under its card
            flat = ' '.join(text.split())
            half = len(flat) // 2
            if len(flat) >= 40 and flat[half:].strip() == flat[:half]:
                body.append({'kind': 'para', 'text': flat[:half].strip()})
                continue                  # accordion echo in the capture
            lines = [ln.strip() for ln in re.split(r'\r?\n', text) if ln.strip()]
            if not lines:
                continue
            fragments = [ln for ln in lines if not ln.endswith(('.', '!', '?', ':'))]
            if len(lines) > 1 and len(fragments) * 2 >= len(lines):
                body.append({'kind': 'list', 'items': lines})
            else:
                body.append({'kind': 'para', 'text': ' '.join(lines)})
        elif kind == 'list':
            body.append(b)
        elif kind == 'table':
            rows = [r for r in b.get('rows', []) if r]
            if rows and rows[0] == b.get('head'):
                rows = rows[1:]
            body.append({'kind': 'table', 'head': b.get('head', []),
                         'rows': rows})
    return body


# Mirror cabin slug -> captured upstream SDL page (source_data_content.json).
CABIN_CONTENT_PAGES = {
    'basic-economy': 'travel_inflight_basic-economy',
    'united-economy': 'travel_inflight_united-economy',
    'economy-plus': 'travel_inflight_economy-plus',
    'premium-plus': 'travel_inflight_united-premium-plus',
    'united-first-business': 'travel_inflight_united-first-and-united-business',
    'united-polaris': 'travel_inflight_united-polaris',
}


def _seed_cabins() -> None:
    content = _load('source_data_content.json')
    pages = content.get('pages') or {}
    for slug, name, tagline, image, highlights in CABIN_PAGES:
        blocks = pages.get(CABIN_CONTENT_PAGES.get(slug, ''), {}).get('blocks')
        body = _cabin_body_blocks(blocks) if blocks else []
        db.session.add(CabinInfo(slug=slug, name=name, tagline=tagline,
                                 image=image,
                                 body=json.dumps(body) if body else '',
                                 highlights=highlights))


def _seed_help() -> None:
    for slug, category, question, answer, related in HELP_ARTICLES:
        db.session.add(HelpArticle(slug=slug, category=category,
                                   question=question, answer=answer,
                                   related=related))


def _seed_policies() -> None:
    for slug, title, body, facts in POLICY_PAGES:
        db.session.add(PolicyArticle(slug=slug, title=title, body=body,
                                     facts=facts))


def _seed_deals() -> None:
    deals = [
        ('ord-to-den', 'Chicago to Denver', 'Domestic',
         'ORD', 'DEN', 49.0, 'static/images/deals/_3408x1068_GLTW_Chicago.jpg',
         'Daily nonstops between O\'Hare and our biggest hub, from $49 one way.'),
        ('sfo-to-den', 'San Francisco to Denver', 'Domestic',
         'SFO', 'DEN', 59.0, 'static/images/deals/3408x1068_GLTW_SanFrancisco.jpg',
         'From the Bay to the Rockies: evening nonstop SFO-DEN aboard the 737 MAX.'),
        ('fco-to-ewr', 'Rome to New York', 'Europe',
         'FCO', 'EWR', 399.0, 'static/images/deals/_3408x1068_GLTW_NewarkNewYork_Updated.jpg',
         'Fly the flagship route from Fiumicino to Newark with Polaris lie-flat seats.'),
        ('hnd-to-iad', 'Tokyo to Washington', 'Asia Pacific & Middle East',
         'HND', 'IAD', 599.0, 'static/images/deals/3408x1068_GLTW_Washington.jpg',
         'Nonstop from Haneda to Washington-Dulles aboard the 777.'),
        ('sfo-to-syd', 'San Francisco to Sydney', 'Asia Pacific & Middle East',
         'SFO', 'SYD', 799.0, 'static/images/deals/surfer-3x.png',
         'The long way down under, nonstop from SFO with Premium Plus.'),
        ('iah-to-lax', 'Houston to Los Angeles', 'Domestic',
         'IAH', 'LAX', 69.0, 'static/images/deals/2653_IAH_1940x611.jpg',
         'Afternoon nonstops from Bush Intercontinental to LAX.'),
        ('den-to-slc', 'Denver to Salt Lake', 'Domestic',
         'DEN', 'SLC', 39.0, 'static/images/deals/3408x1068_GLTW_Denver.jpg',
         'Ski season connections from the Denver hub to Salt Lake City.'),
        ('sfo-to-lhr', 'San Francisco to London', 'Europe',
         'SFO', 'LHR', 379.0, 'static/images/deals/LAX-Sept23_1940x720-mb.jpeg',
         'The daily flagship route to Heathrow, with Polaris business and Premium Plus cabins.'),
        ('ord-to-aus', 'Chicago to Austin', 'Domestic',
         'ORD', 'AUS', 89.0, 'static/images/deals/3408x1068_GLTW_LA.jpg',
         'Evening nonstops from O\'Hare to the Live Music Capital.'),
        ('lhr-to-den', 'London to Denver', 'Europe',
         'LHR', 'DEN', 429.0, 'static/images/deals/TABLET-brand-tile-large-style-2-3x-2307x420.webp',
         'Cross the pond into the Rockies: 787-9 nonstops Heathrow-Denver.'),
    ]
    for slug, title, category, origin, dest, price, image, summary in deals:
        db.session.add(Deal(slug=slug, title=title, category=category,
                            origin_code=origin, dest_code=dest,
                            summary=summary, fare_from=price, image=image))


def seed_benchmark_users() -> None:
    if User.query.count() > 0:
        return
    for i, (email, first, last, miles, pqf, pqp, tier, phone) in enumerate(SEED_USERS):
        digest = f'mp-{email}'
        number = str(100000000 + int(hashlib.sha256(
            digest.encode()).hexdigest()[:8], 16) % 899999999) + str(i)
        user = User(email=email, password_hash=BENCHMARK_PASSWORD_HASH,
                    first_name=first, last_name=last,
                    mp_number=number,
                    award_miles=miles, pqf=pqf, pqp=pqp, tier=tier,
                    plus_points=320 if tier == 'Premier Platinum' else
                    (280 if tier == 'Premier 1K®' else 0),
                    phone=phone)
        db.session.add(user)
    db.session.commit()
    _seed_benchmark_bookings()


def _seed_benchmark_bookings() -> None:
    """Each benchmark member carries pre-seeded trips so manage-booking,
    check-in and baggage tasks have real state to work on."""
    bookings = [
        # conf, user idx, route, date, cabin, status(email for lookup)
        ('KX42LM', 0, ('SFO', 'ORD'), dt.date(2026, 9, 29), 'ECO', 'alice.j@example.com'),
        ('QT83NB', 1, ('ORD', 'DEN'), dt.date(2026, 9, 28), 'EPU', 'bob.m@example.com'),
        ('ZW57PC', 2, ('IAH', 'LAX'), dt.date(2026, 10, 12), 'BE', 'carol.w@example.com'),
        ('HD19RK', 3, ('SFO', 'ORD'), dt.date(2026, 9, 28), 'BUS', 'dave.t@example.com'),
    ]
    users = [User.query.filter_by(email=email).first()
             for _, _, _, _, _, email in
             [(b[0], b[1], b[2], b[3], b[4], b[5]) for b in bookings]]
    for idx, (conf, uidx, (origin, dest), day, cabin, email) in enumerate(bookings):
        user = users[uidx]
        query = Flight.query.filter(Flight.origin_code == origin,
                                    Flight.dest_code == dest)
        if day == MIRROR_TODAY:
            # same-day trips must still be in the check-in window: pick the
            # first flight that departs after the mirror's frozen "now"
            query = query.filter(Flight.departure > '12:00')
        flight = query.order_by(Flight.departure).first()
        if not flight:
            flight = Flight.query.first()
        if not flight:
            continue
        fare = flight.fare_for(cabin) or flight.fare_for('ECO')
        booking = Booking(confirmation=conf, user_id=user.id,
                          contact_email=user.email, contact_phone=user.phone,
                          cabin=cabin, adults=1, children=0,
                          card_last4='4242', card_type='Visa',
                          total=fare.amount,
                          created_at=MIRROR_DATE)
        db.session.add(booking)
        db.session.flush()
        db.session.add(BookingLeg(booking_id=booking.id, flight_id=flight.id,
                                  travel_date=day, cabin=cabin,
                                  amount=fare.amount))
        pax = Passenger(booking_id=booking.id, first_name=user.first_name,
                        last_name=user.last_name, mp_number=user.mp_number,
                        title='Mr' if user.first_name in ('Bob', 'Dave') else 'Ms')
        db.session.add(pax)
        db.session.flush()
        if idx in (0, 2):
            db.session.add(BaggageItem(booking_id=booking.id,
                                       passenger_id=pax.id,
                                       description='Checked bag 1',
                                       weight_lb=42, fee=0.0
                                       if user.tier != 'Member' else 35.0))
    db.session.commit()


def main() -> None:
    with app.app_context():
        seed_database()
        seed_benchmark_users()
        from app import db as _db
        _db.session.commit()
        counts = {
            'airports': Airport.query.count(),
            'flights': Flight.query.count(),
            'fares': Fare.query.count(),
            'aircraft': Aircraft.query.count(),
            'users': User.query.count(),
            'bookings': Booking.query.count(),
            'help': HelpArticle.query.count(),
            'cabins': CabinInfo.query.count(),
            'deals': Deal.query.count(),
            'policies': PolicyArticle.query.count(),
        }
        print('seeded:', json.dumps(counts))


if __name__ == '__main__':
    main()
