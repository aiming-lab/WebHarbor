#!/usr/bin/env python3
"""Build the tracked source_data_*.json snapshots from scraped_data/raw.

Normalizes the raw Playwright captures of https://www.remax.com/ (taken
2026-09-24) into the deterministic structures seed_data.py consumes.
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "scraped_data" / "raw"

SNAPSHOT = "2026-09-24"

STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee',
    'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
}

SUB_TYPE_MAP = {
    'Single Family Residence': 'House', 'Condominium': 'Condo', 'Townhouse': 'Townhouse',
    'Duplex': 'Multi-Family', 'Quadruplex': 'Multi-Family', 'Multi Family': 'Multi-Family',
    'Manufactured Home': 'Mobile', 'Lot': 'Land', 'Unimproved Land': 'Land',
}
JSONLD_TYPE_MAP = {
    'SingleFamilyResidence': 'House', 'Apartment': 'Condo', 'Accommodation': 'Condo',
    'ApartmentComplex': 'Condo',
}
BADGES = ['OPEN HOUSE', 'NEW LISTING', 'VIRTUAL TOUR', '3D VIRTUAL TOUR', 'PRICE CHANGE',
          'COMING SOON', 'FOR SALE']


def load(name):
    return json.loads((RAW / name).read_text(encoding='utf-8'))


def slugify(text):
    text = re.sub(r"[^a-z0-9]+", '-', (text or '').lower())
    return text.strip('-')


def img_path(directory, stem):
    """Return the asset path with the extension matching the file on disk
    (the upstream CDNs serve mixed JPEG/PNG bytes under fixed names)."""
    for ext in ('.jpg', '.png', '.webp'):
        p = f"{directory}/{stem}{ext}"
        f = HERE / 'static' / 'images' / p
        if f.exists():
            return p
    return f"{directory}/{stem}.jpg"


def parse_card(text):
    """Parse 'ACTIVE | OPEN HOUSE | $2,850,000 | 16530 NE 99TH ST | ...' card text."""
    parts = [p.strip() for p in (text or '').split('|')]
    out = {'badges': [], 'price': None, 'street': None, 'cityline': None,
           'beds': None, 'baths': None, 'sqft': None, 'broker': None,
           'agent': None, 'agent_phone': None, 'mls': None, 'status': 'active'}
    for p in parts:
        if not p:
            continue
        if re.fullmatch(r'\$[\d,]+', p):
            out['price'] = int(p.replace('$', '').replace(',', ''))
        elif p in ('ACTIVE', 'PENDING', 'CONTINGENT', 'COMING SOON'):
            out['status'] = p.lower().replace(' ', '_')
        elif p in BADGES:
            out['badges'].append(p)
        elif re.fullmatch(r'\d+', p) and out['beds'] is None:
            out['beds'] = int(p)
        elif re.fullmatch(r'\d+', p) and out['baths'] is None:
            out['baths'] = int(p)
        elif p.endswith('SQ FT'):
            try:
                out['sqft'] = int(float(p.replace(' SQ FT', '').replace(',', '')))
            except ValueError:
                pass
        elif p.startswith('Listing by'):
            lb = p.replace('Listing by', '', 1).strip().replace('\xa0', ' ')
            m = re.match(r'(.+?)\s+-\s+(.+?)\s+-\s+([\d\-]+)$', lb)
            if m:
                out['broker'], out['agent'], out['agent_phone'] = m.group(1).strip(), m.group(2).strip(), m.group(3)
            else:
                m = re.match(r'(.+?)\s+-\s+(.+)$', lb)
                if m:
                    out['broker'], out['agent'] = m.group(1).strip(), m.group(2).strip()
                else:
                    out['broker'] = lb
        elif p.startswith('MLS'):
            m = re.search(r'#\s*:?\s*(\w+)', p)
            if m:
                out['mls'] = m.group(1)
        elif re.match(r'^[A-Z0-9 ,.\'#-]+$', p) and ', ' in p and out['cityline'] is None and out['street'] is not None:
            out['cityline'] = p
        elif out['street'] is None and re.match(r'^[A-Z0-9 ,.\'#-]+$', p) and not p.startswith('MLS'):
            out['street'] = p
    return out


def clean_overview(items):
    out = []
    for it in items or []:
        it = (it or '').strip()
        if not it:
            continue
        if re.fullmatch(r'[\d,.]+', it) or re.fullmatch(r'\$[\d,.]+', it):
            continue
        out.append(it)
    return out


def parse_presented(text):
    if not text:
        return None
    m = re.search(r'Presented by\s+(.+?)\n+(.*?)\n+(\(?[\d]{3}[\)\-\s]*\d{3}[\-\s]*\d{4})?\s*\u2022?\s*([\w.@\-]+@[\w.\-]+)?', text)
    if not m:
        return None
    name = m.group(1).strip()
    addr = (m.group(2) or '').strip()
    phone = (m.group(3) or '').strip()
    if phone and not phone.startswith('('):
        phone = '(' + phone
    email = (m.group(4) or '').strip()
    if not (name or addr):
        return None
    return {'name': name, 'address': addr, 'phone': phone, 'email': email}


def oh_label(start, end=None):
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(start)
    except Exception:
        return None, None
    label = dt.strftime('%A %B ') + {'01': '1st', '02': '2nd', '03': '3rd'}.get(
        f"{dt.day:02d}", f"{dt.day}th")
    # upstream renders the window like "12-4pm" / "1:30-3pm"
    if end:
        try:
            de = datetime.fromisoformat(end)
        except Exception:
            de = None
    else:
        de = None
    s = dt.strftime('%-I:%M').rstrip(':0').replace(':00', '') if dt.minute else dt.strftime('%-I')
    if de is not None:
        if de.minute:
            e = de.strftime('%-I:%M%p').lower()
        else:
            e = de.strftime('%-I%p').lower()
        time_label = f"{s}-{e}"
    else:
        time_label = dt.strftime('%-I%p').lower()
    return label, time_label


def build_listings():
    ldp = {r['url']: r for r in load('ldp_all.json')}
    ldp_by_mls = {}
    for url, r in ldp.items():
        mls = (r.get('srp') or {}).get('mls')
        if mls:
            ldp_by_mls[mls] = r
    listings = []
    seen_mls = set()
    order = 0
    for f in sorted(RAW.glob('srp_*.json')):
        d = load(f.name)
        for l in d['listings']:
            mls = l.get('mls')
            if not mls or mls in seen_mls:
                continue
            seen_mls.add(mls)
            card = parse_card(l.get('card_text'))
            detail = ldp_by_mls.get(mls)
            city = (l.get('city') or '').title()
            state = l.get('state') or ''
            zipc = l.get('zip') or ''
            key = f"{slugify(city)}_{mls}"
            # home type
            sub = None
            home_type = JSONLD_TYPE_MAP.get(l.get('prop_type'), 'House')
            if detail:
                b = (detail.get('sections') or {}).get('building-and-construction') or {}
                sub = b.get('Property Sub Type') or b.get('Property Type')
                if isinstance(sub, str) and sub in SUB_TYPE_MAP:
                    home_type = SUB_TYPE_MAP[sub]
            price = card.get('price') or l.get('price')
            photo = img_path('listings', f'{key}/card')
            gallery = [photo]
            if detail:
                for i in range(1, 4):
                    p = img_path('listings', f'{key}/gallery_{i}')
                    if (HERE / 'static' / 'images' / p).exists():
                        gallery.append(p)
            open_houses = []
            for oh in l.get('open_houses') or []:
                label, tlabel = oh_label(oh.get('start') or '', oh.get('end'))
                if label:
                    open_houses.append({'label': label, 'time': tlabel,
                                        'start': oh.get('start'), 'end': oh.get('end')})
            row = {
                'mls': mls,
                'price': price,
                'beds': l.get('beds') if l.get('beds') is not None else card.get('beds'),
                'baths': l.get('baths') if l.get('baths') is not None else card.get('baths'),
                'sqft': l.get('sqft') if l.get('sqft') is not None else card.get('sqft'),
                'home_type': home_type,
                'prop_sub_type': sub if isinstance(sub, str) else None,
                'street': l.get('street') or card.get('street'),
                'city': city, 'state': state, 'zip': zipc,
                'status': card.get('status') or 'active',
                'badges': card.get('badges') or [],
                'broker': card.get('broker'), 'agent': card.get('agent'),
                'agent_phone': card.get('agent_phone'),
                'photo': photo,
                'gallery': gallery,
                'open_houses': open_houses,
                'has_detail': detail is not None,
                'srp_order': order,
            }
            if detail:
                row['description'] = (detail.get('ld_description') or '').strip() or None
                row['quick_overview'] = clean_overview(detail.get('quick_overview'))
                row['sections'] = detail.get('sections')
                row['presented_by'] = parse_presented(detail.get('presented_by'))
                la = (detail.get('listing_agent') or '')
                m = re.search(r'Listing Agent\s+(.+)', la)
                row['listed_by_agent'] = m.group(1).strip() if m else None
                m = re.search(r'Listing Office\s+(.+)', la)
                row['listed_by_office'] = m.group(1).strip() if m else None
                m = re.search(r'Updated\s+(.+)', la)
                row['updated_label'] = m.group(1).strip() if m else None
                # days on website
                for q in row['quick_overview']:
                    m = re.match(r'(\d+) days? on website', q)
                    if m:
                        row['days_on_site'] = int(m.group(1))
            listings.append(row)
            order += 1
    # deterministic listed_date: snapshot minus (days_on_site or srp_order)
    from datetime import date, timedelta
    snap = date(2026, 9, 24)
    for r in listings:
        d = r.get('days_on_site')
        if d is None:
            d = r['srp_order'] % 30 + 1
        r['listed_date'] = (snap - timedelta(days=int(d))).isoformat()
    # sort by mls for stable ids
    listings.sort(key=lambda r: (r['state'], r['city'], r['mls']))
    for i, r in enumerate(listings, start=1):
        r['id'] = i
        r['slug'] = slugify(f"{r['street']} {r['city']} {r['state']} {r['zip']}")
        r['is_luxury'] = r['price'] is not None and r['price'] >= 2000000
    return listings


def build_rentals():
    rows = load('rentals_linked.json')
    ldp = {r['url']: r for r in load('rental_ldp.json')}
    out = []
    for r in rows:
        parts = r['parts']
        addr = parts[0].replace(' For Rent', '').strip()
        m = re.match(r'(.*),\s*([A-Z ]+),\s*([A-Z]{2})\s*(\d{5})?$', addr)
        street, city, state, zipc = (m.groups() if m else (addr, None, None, None))
        price = int(parts[1].replace('$', '').replace(',', ''))
        m = re.match(r'(\d+) beds?,\s*(\d+) baths?,\s*([\d,]+) sqft', parts[2])
        beds, baths, sqft = (int(m.group(1)), int(m.group(2)), int(m.group(3).replace(',', ''))) if m else (None, None, None)
        detail = ldp.get(r.get('href'))
        key = slugify(addr)[:60]
        row = {
            'street': street, 'city': (city or '').title(), 'state': state, 'zip': zipc,
            'price': price, 'beds': beds, 'baths': baths, 'sqft': sqft,
            'date_added': parts[3] if len(parts) > 3 else None,
            'has_detail': detail is not None,
        }
        if detail:
            row['description'] = (detail.get('ld_description') or '').strip() or None
            gal = detail.get('gallery') or []
            row['photo'] = img_path('rentals', f'{key}/card') if gal else None
            photos = [row['photo']] if gal else []
            for i in range(1, 4):
                p = img_path('rentals', f'{key}/gallery_{i}')
                if (HERE / 'static' / 'images' / p).exists():
                    photos.append(p)
            row['gallery'] = photos
            row['quick_overview'] = clean_overview(detail.get('quick_overview'))
            pb = parse_presented(detail.get('presented_by'))
            if pb:
                row['presented_by'] = pb
            la = (detail.get('listing_agent') or '')
            m = re.search(r'Listing Agent\s+(.+)', la)
            if m:
                row['listed_by_agent'] = m.group(1).strip()
            m = re.search(r'Listing Office\s+(.+)', la)
            if m:
                row['listed_by_office'] = m.group(1).strip()
        out.append(row)
    out.sort(key=lambda r: (r['state'] or '', r['city'] or '', r['street'] or ''))
    for i, r in enumerate(out, start=1):
        r['id'] = i
        r['slug'] = slugify(f"{r['street']} {r['city']} {r['state']} {r['zip']}")
    return out


def agent_about(text):
    if not text:
        return None
    # strip the header through the Office Address line, then cut at Service Areas/Hobbies
    m = re.search(r'Office Address\s*\n[^\n]+\n(.*?)(?:\n\s*\nService Areas|\n\s*\nHobbies|\n\s*\nExperience|$)', text, re.S)
    if not m:
        m = re.search(r'(?:About Me|Team|Awards|Listings)\s*\n(.*?)(?:\n\s*\nService Areas|\n\s*\nHobbies|\n\s*\nExperience|$)', text, re.S)
    if m:
        body = m.group(1).strip()
        # drop leading tab labels if present
        body = re.sub(r'^(About Me|Team|Awards|Listings)\s*\n?', '', body).strip()
        return body or None
    return None


def split_list(text, label, stops=('More',)):
    if not text:
        return []
    body = text.replace(label, '', 1).strip()
    for stop in stops:
        body = body.split('\n' + stop)[0]
        body = body.split('\n\n' + stop)[0]
    body = body.replace('\n', ' ')
    items = [x.strip() for x in body.split(',') if x.strip()]
    # dedupe preserving order
    seen = set(); out = []
    for it in items:
        if it not in seen:
            seen.add(it); out.append(it)
    return out


def build_agents():
    ags = load('agents_detail.json')
    out = []
    for a in ags:
        url = a['url']
        remax_id = url.rstrip('/').split('/')[-1]
        card = a.get('card') or {}
        parts = [p.strip() for p in (card.get('text') or '').split('|')]
        name = parts[0] if parts else remax_id
        title = parts[1] if len(parts) > 1 else None
        licensed = next((p for p in parts if p.startswith('Licensed in')), None)
        city_state = next((p for p in parts if re.match(r'.+,\s*[A-Z]{2}$', p) and p != name and not p.startswith('Licensed')), None)
        office = next((p for p in parts if p.startswith('REMAX')), None)
        phone = next((p for p in parts if re.match(r'\(\d{3}\) \d{3}-\d{4}', p)), None)
        exp = a.get('experience') or ''
        m = re.search(r'(\d+) Years? Experience', exp)
        years = int(m.group(1)) if m else None
        lic = re.findall(r'License #([\w\d]+)', exp)
        lic = [l for l in lic if l != 'null']
        city, state = None, None
        if city_state:
            m = re.match(r'(.*),\s*([A-Z]{2})$', city_state)
            if m:
                city, state = m.group(1).strip(), m.group(2)
        row = {
            'remax_id': remax_id,
            'name': name,
            'title': title,
            'licensed': licensed.replace('Licensed in ', '') if licensed else None,
            'city': city, 'state': state,
            'office_name': office,
            'phone': phone,
            'photo': f"agents/{remax_id}.jpg" if a.get('photo') else None,
            'about': agent_about(a.get('about')),
            'hobbies': split_list(a.get('hobbies'), 'Hobbies'),
            'civic': split_list(a.get('civic'), 'Civic Activities'),
            'years': years,
            'license_numbers': lic,
            'languages': split_list(a.get('languages'), 'Languages'),
            'specialties': split_list(a.get('specialties'), 'Specialties'),
            'designations': split_list(a.get('designations'), 'Designations'),
            'website': a.get('website'),
            'office_address': None,
        }
        m = re.search(r'Office Address\s*\n(.+)', a.get('about') or '')
        if m:
            row['office_address'] = m.group(1).strip()
        out.append(row)
    out.sort(key=lambda r: r['name'])
    for i, r in enumerate(out, start=1):
        r['id'] = i
        r['slug'] = slugify(f"{r['name']} {r['city']} {r['state']}")
    return out


def office_about(text):
    if not text:
        return None
    m = re.search(r'(?:About|Our Agents|Our Listings)\s*\n(.*?)(?:\n\s*\nService Areas|$)', text, re.S)
    if m:
        return m.group(1).strip()
    return None


def build_offices():
    offices = load('offices_detail.json')
    cards = load('offices_cards.json')
    by_url = {o['url']: o for o in offices}
    out = []
    seen = set()
    for c in cards:
        url = c['href']
        oid = re.sub(r'\D', '', url.rstrip('/').split('/')[-1])
        if oid in seen:
            continue
        seen.add(oid)
        d = by_url.get(url)
        parts = [p.strip() for p in (c.get('text') or '').split('|')]
        name = parts[0]
        addr = parts[1] if len(parts) > 1 else None
        phone = next((p for p in parts if re.match(r'\(\d{3}\) \d{3}-\d{4}', p)), None)
        parts2 = [p.strip() for p in (addr or '').split(',')]
        city, state = None, None
        if len(parts2) >= 3:
            city = parts2[-3] if len(parts2) >= 3 else None
            m2 = re.match(r'([A-Z]{2})', parts2[-2])
            if m2:
                state = m2.group(1)
            else:
                city = None
        photo = img_path('offices', oid)
        if not (HERE / 'static' / 'images' / photo).exists():
            photo = None
        row = {
            'remax_id': oid,
            'name': name,
            'address': addr,
            'city': city, 'state': state,
            'phone': phone,
            'photo': photo,
            'has_detail': d is not None,
        }
        if d:
            row['about'] = office_about(d.get('about'))
            row['website'] = d.get('website')
            sa = split_list(d.get('service_areas'), 'Service Areas',
                            stops=('Languages', 'Specialties', 'More'))
            row['service_areas'] = sa
            row['languages'] = split_list(d.get('languages'), 'Languages',
                                          stops=('Specialties', 'More'))
            row['specialties'] = split_list(d.get('specialties'), 'Specialties',
                                           stops=('More',))
        out.append(row)
    out.sort(key=lambda r: (r['name']))
    for i, r in enumerate(out, start=1):
        r['id'] = i
        r['slug'] = slugify(f"{r['name']}")
    return out


def build_content():
    blog = load('blog_posts.json')
    blog_images = {b['url']: b['img'] for b in load('blog_images.json')}
    posts = []
    for b in blog:
        slug = b['url'].rstrip('/').split('/')[-1]
        text = (b.get('text') or '').strip()
        # split title/leading nav junk: text starts with nav; find first real paragraph
        # keep as-is; template renders body text
        m = re.search(r'\b(SHARE|Category|Posted|Published)\b', text)
        posts.append({
            'slug': slug,
            'title': (b.get('title') or slug.replace('-', ' ')).strip(),
            'image': img_path('blog', slug),
            'image_url': (blog_images.get(b['url']) or b.get('img') or '').split('?')[0] or None,
            'text': text,
        })
    # categories from the blog list scrape
    cat_map = {
        'buying': 'All About Buying', 'selling': 'All About Selling',
        'market-updates': 'News & Market Updates',
    }
    return {
        'snapshot_date': SNAPSHOT,
        'blog_posts': posts,
        'categories': cat_map,
        'personas': [
            {'title': 'Real Estate for the Golf Lifestyle',
             'subtitle': 'Explore golf communities with agents who know the market.',
             'button': 'EXPLORE GOLF LIFESTYLES', 'url': '/usa/en/lifestyles/golf',
             'image': 'homepage/golf_lifestyle.jpg'},
            {'title': 'Global Listings',
             'subtitle': 'Browse Global Real Estate from all over the world!',
             'button': 'WORLDWIDE LISTINGS', 'url': '/luxury',
             'image': 'homepage/global-listings.jpg'},
            {'title': 'First Time Buyer',
             'subtitle': 'Explore options including buyer advice, seller guides and more.',
             'button': 'BUYER TOOLS', 'url': '/advice/buying-a-home-in-august-2026-as-a-first-time-buyer',
             'image': 'homepage/first-time-buyer.jpg'},
            {'title': 'Move-Up Buyer',
             'subtitle': 'Find homes with more space for your growing lifestyle.',
             'button': 'SEE HOMES', 'url': '/homes-for-sale-united-states',
             'image': 'homepage/move-up-buyer.jpg'},
        ],
        'advice_cards': [
            {'category': 'CHOOSING AN AGENT', 'title': '10 Questions to Ask a Real Estate Agent',
             'slug': None, 'external_url': 'https://blog.remax.com/10-questions-to-ask-a-real-estate-agent/',
             'image': 'homepage/advice-choosing-an-agent.jpg'},
            {'category': 'FINDING A HOME', 'title': 'Tips for Choosing Your Perfect Starter Home',
             'slug': None, 'external_url': 'https://blog.remax.com/tips-for-choosing-your-perfect-starter-home/',
             'image': 'homepage/advice-starter-home-tips.jpg'},
            {'category': 'DUE DILIGENCE', 'title': 'What Happens If a Buyer Backs Out of Real Estate Contract?',
             'slug': None, 'external_url': 'https://blog.remax.com/what-happens-if-a-buyer-backs-out-of-real-estate-contract/',
             'image': 'homepage/advice-due-diligence.jpg'},
        ],
        'guides': [
            {'title': "Homebuyer's Guide", 'url': 'https://blog.remax.com/first-time-homebuyers-hub/',
             'image': 'homepage/advice-buyers-guide.jpg'},
            {'title': "Home Seller's Guide", 'url': 'https://blog.remax.com/home-sellers-hub/',
             'image': 'homepage/advice-sellers-guide.jpg'},
            {'title': 'Staging to Sell', 'url': 'https://blog.remax.com/10-expert-tips-for-staging-your-home-to-sell/',
             'image': 'homepage/advice-staging-to-sell.jpg'},
        ],
        'popular_cities': [
            ('Houston', 'TX'), ('Miami', 'FL'), ('Chicago', 'IL'), ('San Antonio', 'TX'),
            ('Atlanta', 'GA'), ('Tehachapi', 'CA'), ('Philadelphia', 'PA'), ('Myrtle Beach', 'SC'),
            ('Austin', 'TX'), ('Los Angeles', 'CA'), ('Denver', 'CO'), ('Naples', 'FL'),
        ],
        'popular_condos': [
            ('Myrtle Beach', 'SC'), ('Miami', 'FL'), ('Chicago', 'IL'), ('Atlanta', 'GA'),
            ('North Myrtle Beach', 'SC'), ('Denver', 'CO'), ('Honolulu', 'HI'), ('Naples', 'FL'),
            ('Houston', 'TX'), ('Boston', 'MA'),
        ],
        'popular_townhouses': [
            ('Philadelphia', 'PA'), ('Baltimore', 'MD'), ('Atlanta', 'GA'), ('Charlotte', 'NC'),
            ('Houston', 'TX'), ('Denver', 'CO'), ('Phoenix', 'AZ'), ('Kissimmee', 'FL'),
            ('Colorado Springs', 'CO'), ('Aurora', 'CO'),
        ],
    }


def main():
    listings = build_listings()
    rentals = build_rentals()
    agents = build_agents()
    offices = build_offices()
    content = build_content()
    (HERE / 'source_data_listings.json').write_text(json.dumps(
        {'snapshot_date': SNAPSHOT, 'listings': listings}, indent=1))
    (HERE / 'source_data_rentals.json').write_text(json.dumps(
        {'snapshot_date': SNAPSHOT, 'rentals': rentals}, indent=1))
    (HERE / 'source_data_agents.json').write_text(json.dumps(
        {'snapshot_date': SNAPSHOT, 'agents': agents}, indent=1))
    (HERE / 'source_data_offices.json').write_text(json.dumps(
        {'snapshot_date': SNAPSHOT, 'offices': offices}, indent=1))
    (HERE / 'source_data_content.json').write_text(json.dumps(content, indent=1))
    print(f"listings={len(listings)} rentals={len(rentals)} agents={len(agents)} "
          f"offices={len(offices)} blog={len(content['blog_posts'])}")
    n_detail = sum(1 for l in listings if l['has_detail'])
    n_oh = sum(1 for l in listings if l['open_houses'])
    print(f"detail={n_detail} openhouse={n_oh} luxury={sum(1 for l in listings if l['is_luxury'])}")


if __name__ == '__main__':
    main()
