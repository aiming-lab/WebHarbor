#!/usr/bin/env python3
"""Build the tracked source-data snapshots for the megabus mirror.

Converts the raw upstream capture (scraped JSON under scraped_data/, produced
by Playwright + httpx against https://us.megabus.com/ on 2026-09-23) into the
three deterministic JSON snapshots seed_data.py reads:

    source_data_network.json    cities / stops / route network / site fees
    source_data_journeys.json   journey + leg + travel-date rows
    source_data_content.json    faqs, city guides, route guides, static pages

Determinism: every list is sorted before it is written.
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent.parent
SCRAPE = HERE / 'scraped_data'

OUT_NETWORK = HERE / 'source_data_network.json'
OUT_JOURNEYS = HERE / 'source_data_journeys.json'
OUT_CONTENT = HERE / 'source_data_content.json'

SNAPSHOT = '2026-09-23'


def load(name):
    return json.loads((SCRAPE / name).read_text(encoding='utf-8'))


def build_network():
    origin_cities = load('origin_cities.json')['cities']
    cities = []
    for c in origin_cities:
        name = c['name']
        state = ''
        if ',' in name:
            state = name.split(',', 1)[1].strip()
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower().split(',')[0]).strip('-')
        # disambiguate slugs that collide (city names repeat across states)
        cities.append({'id': c['id'], 'name': name, 'state': state, 'slug': slug,
                       'latitude': c['latitude'], 'longitude': c['longitude']})
    slugs = {}
    for c in sorted(cities, key=lambda x: x['id']):
        base = c['slug']
        if base in slugs:
            slugs[base] += 1
            c['slug'] = f"{base}-{slugs[base]}"
        else:
            slugs[base] = 0
    stops_raw = load('stops_raw.json')
    stops = []
    for city_name in sorted(stops_raw):
        arr = stops_raw[city_name]
        for idx, stop_name in enumerate(arr):
            stops.append({'city': city_name, 'seq': idx, 'name': stop_name})
    destinations = {}
    dest = load('destinations.json')
    for hub, data in dest.items():
        ids = sorted(int(c['id']) for c in data.get('cities', []))
        destinations[str(hub)] = ids
    info = load('site_information.json')
    network = {
        'snapshot': SNAPSHOT,
        'cities': sorted(cities, key=lambda c: c['id']),
        'stops': stops,
        'destinations': {k: destinations[k] for k in sorted(destinations, key=int)},
        'fees': info,
    }
    OUT_NETWORK.write_text(json.dumps(network, indent=1, sort_keys=False), encoding='utf-8')
    print('network:', len(cities), 'cities', len(stops), 'stops',
          len(destinations), 'hub destination lists')


def build_journeys():
    journeys = {}
    for line in (SCRAPE / 'journeys.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        j = json.loads(line)
        jid = str(j['journeyId'])
        # a journeyId can recur for the same slot on a different date; key on id+date
        key = f"{jid}-{j['departureDateTime'][:10]}"
        journeys[key] = j
    rows = []
    for key in sorted(journeys):
        j = journeys[key]
        dep = j['departureDateTime']
        arr = j['arrivalDateTime']
        dur = j['duration']
        m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?', dur)
        hours = int(m.group(1) or 0) if m else 0
        mins = int(m.group(2) or 0) if m else 0
        legs = []
        for idx, leg in enumerate(j.get('legs', [])):
            legs.append({
                'seq': idx,
                'carrier': leg.get('carrier', ''),
                'carrier_icon': leg.get('carrierIcon', ''),
                'dep': leg.get('departureDateTime', ''),
                'arr': leg.get('arrivalDateTime', ''),
                'origin_stop': leg.get('origin', {}).get('stopName', ''),
                'origin_stop_id': leg.get('origin', {}).get('stopId', ''),
                'dest_stop': leg.get('destination', {}).get('stopName', ''),
                'dest_stop_id': leg.get('destination', {}).get('stopId', ''),
            })
        rows.append({
            'id': str(j['journeyId']),
            'origin_city_id': int(j['origin']['cityId']),
            'dest_city_id': int(j['destination']['cityId']),
            'departure_date': dep[:10],
            'dep_time': dep[11:16],
            'arr_time': arr[11:16],
            'duration_min': hours * 60 + mins,
            'price': j.get('price'),
            'route_name': j.get('routeName', ''),
            'reservable': j.get('reservableType', 'NONE'),
            'service_information': j.get('serviceInformation', 'INFORMATION'),
            'legs': legs,
        })
    travel = load('travel_dates.json')
    travel_rows = []
    for key in sorted(travel, key=lambda k: tuple(int(x) for x in k.split('_'))):
        o, d = key.split('_')
        for day in sorted(travel[key]):
            travel_rows.append({'origin_city_id': int(o), 'dest_city_id': int(d), 'day': day})
    data = {'snapshot': SNAPSHOT, 'journeys': rows, 'travel_dates': travel_rows}
    OUT_JOURNEYS.write_text(json.dumps(data, indent=1), encoding='utf-8')
    print('journeys:', len(rows), 'travel-date rows:', len(travel_rows))


def build_content():
    faqs = load('faqs.json')
    faq_rows = []
    topic_map = {
        'help': 'help',
        'help_making_reservations': 'making-reservations',
        'help_changing_reservations': 'changing-reservations',
        'help_traveling': 'traveling-on-the-bus',
        'help_bus_routes_stops': 'bus-routes-stops',
        'help_special_requirements': 'customers-with-special-requirements',
        'help_terms': 'terms-and-conditions',
    }
    for key in sorted(faqs):
        topic = topic_map.get(key)
        if not topic:
            continue
        for idx, (q, a) in enumerate(faqs[key]):
            faq_rows.append({'topic': topic, 'seq': idx, 'question': q, 'answer': a})
    city_guides = load('city_guides.json')
    cg_rows = []
    city_slugs = {'albany', 'ann-arbor', 'baltimore', 'binghamton', 'boston', 'buffalo',
                  'burlington', 'chicago', 'dc', 'des-moines', 'detroit', 'fayetteville',
                  'indianapolis', 'lincoln', 'miami', 'milwaukee', 'minneapolis', 'new-york',
                  'omaha', 'orlando', 'philadelphia', 'pittsburgh', 'state-college', 'toronto'}
    for slug in sorted(city_guides):
        g = city_guides[slug]
        cg_rows.append({'slug': slug, 'title': g.get('title', ''),
                        'page_title': g.get('page_title', ''),
                        'hero': g.get('hero', ''),
                        'is_city': slug in city_slugs,
                        'sections': g.get('sections', [])})
    route_guides = load('route_guides.json')
    index_labels = load('route_index_labels.json')
    rg_rows = []
    for idx, slug in enumerate(sorted(route_guides)):
        g = route_guides[slug]
        rg_rows.append({
            'slug': slug, 'seq': idx,
            'link_title': index_labels.get(slug, g.get('title', '')),
            'title': g.get('title', ''), 'subtitle': g.get('subtitle', ''),
            'origin_id': g.get('origin_id'), 'dest_id': g.get('dest_id'),
            'banner': g.get('banner', ''), 'stats': g.get('stats', {}),
            'details': g.get('details', ''), 'faqs': g.get('faqs', []),
            'related': g.get('related', []),
        })
    static_pages = load('static_pages.json')
    # Mirror-authored rows in the upstream formats (documented in
    # provenance.json): the upstream severe-alerts API returned an empty list
    # on the snapshot date, so the two advisories below follow the site's own
    # service-alert format to give the /service-alerts page realistic content.
    service_alerts = [
        {
            'severity': 'major',
            'title': 'Philadelphia stop temporarily moved for departing services',
            'body': ('From Monday 5 October to Monday 12 October 2026, Peter Pan '
                     'Bus Lines and Adirondack Trailways services departing '
                     'Philadelphia will board from Platform C at 1001 Filbert '
                     'Street instead of the usual gates. Allow an extra 10 '
                     'minutes to find the new boarding point. Arrivals are not '
                     'affected.'),
            'route_name': 'PP0E',
            'published_on': '2026-09-18',
        },
        {
            'severity': 'information',
            'title': 'Thanksgiving 2026 schedules are now open for booking',
            'body': ('Services for the Thanksgiving travel period (Wednesday '
                     '25 November to Sunday 29 November 2026) are now on sale. '
                     'The busiest travel days fill quickly - book early for the '
                     'best fares and a reserved seat on your preferred '
                     'departure.'),
            'route_name': '',
            'published_on': '2026-09-10',
        },
    ]
    # Mirror-authored promotion in the site\'s redemption-code format; it is
    # disclosed on the fare finder page so agents can discover it on-site.
    promo_codes = [
        {
            'code': 'EMAIL5',
            'kind': 'amount',
            'value': 5.00,
            'min_spend': 15.00,
            'description': '$5.00 off your next booking over $15.00',
            'active': True,
        },
    ]
    content = {'snapshot': SNAPSHOT, 'faqs': faq_rows, 'city_guides': cg_rows,
               'route_guides': rg_rows, 'static_pages': static_pages,
               'service_alerts': service_alerts, 'promo_codes': promo_codes}
    OUT_CONTENT.write_text(json.dumps(content, indent=1), encoding='utf-8')
    print('content: faqs', len(faq_rows), '| city guides', len(cg_rows),
          '| route guides', len(rg_rows), '| static pages', len(static_pages))


if __name__ == '__main__':
    build_network()
    build_journeys()
    build_content()
