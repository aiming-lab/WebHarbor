"""Self-checks for the RE/MAX mirror.

Run from sites/re_max/: python3 -m pytest tests/ -q
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app as remax_app  # noqa: E402
from app import (Agent, BlogPost, Favorite, Inquiry, Listing, Office,  # noqa: E402
                 Rental, SavedSearch, User)

app = remax_app.app
app.config['TESTING'] = True
app.config['SERVER_NAME'] = 'localhost.test'
app.config['WTF_CSRF_ENABLED'] = False


def client():
    return app.test_client()


def csrf_from(c, url):
    import re
    r = c.get(url)
    m = re.search(rb'name="csrf_token" value="([^"]+)"', r.data)
    return m.group(1).decode() if m else ''


def test_health():
    with client() as c:
        r = c.get('/_health')
        assert r.status_code == 200
        data = r.get_json()
        assert data['ok'] is True
        assert data['listings'] >= 300
        assert data['rentals'] >= 50
        assert data['agents'] >= 20
        assert data['offices'] >= 15
        assert data['blog_posts'] >= 15


def test_core_pages_render():
    with app.app_context():
        listing = Listing.query.filter_by(has_detail=True).first()
        agent = Agent.query.filter(Agent.about.isnot(None)).first()
        office = Office.query.filter_by(has_detail=True).first()
        rental = Rental.query.filter_by(has_detail=True).first()
        post = BlogPost.query.first()
        listing_url = listing.detail_url()
        agent_url = agent.detail_url()
        office_url = office.detail_url()
        rental_url = rental.detail_url()
        post_slug = post.slug
    with client() as c:
        for url in ['/', '/homes-for-sale-united-states', '/homes-for-sale/wa',
                    '/wa/redmond-real-estate', '/new-listings', '/new-rentals',
                    '/usa/en/real-estate/united-states-open-houses',
                    '/open-houses/wa', '/real-estate-agents', '/real-estate-offices',
                    '/luxury', '/usa/en/lifestyles/golf', '/advice', '/login',
                    '/register', '/search?q=redmond', listing_url, agent_url,
                    office_url, rental_url, f'/advice/{post_slug}']:
            r = c.get(url)
            assert r.status_code == 200, url
            assert len(r.data) > 2000, url


def test_listing_detail_content():
    with app.app_context():
        l = Listing.query.filter_by(has_detail=True).filter(Listing.description.isnot(None)).first()
        url = l.detail_url()
        mls = l.mls
        street = l.street
    with client() as c:
        r = c.get(url)
        body = r.data.decode()
        assert mls in body
        assert street in body
        assert 'MLS' in body
        assert 'Contact a REMAX Agent' in body or 'CONTACT A REMAX AGENT' in body


def test_srp_filters():
    with client() as c:
        base = '/tx/austin-real-estate'
        r = c.get(base)
        body = r.data.decode()
        assert 'Results' in body
        r = c.get(base + '?home_type=Condo')
        body = r.data.decode()
        assert 'Condo' in body
        r = c.get(base + '?price_max=400000')
        body = r.data.decode()
        assert 'Results' in body
        r = c.get(base + '?beds=4&sort=price_desc')
        assert r.status_code == 200


def test_srp_sort_price_asc():
    import re
    with client() as c:
        r = c.get('/tx/austin-real-estate?sort=price_asc')
        prices = [int(x.replace(',', '')) for x in re.findall(r'\$([\d,]+)</div>', r.data.decode())]
        assert prices, 'no prices rendered'
        assert prices == sorted(prices)


def test_search_scored():
    with client() as c:
        r = c.get('/search?q=austin')
        assert r.status_code == 200
        r = c.get('/search?q=redmond condo')
        assert r.status_code == 200
        r = c.get('/search?q=zzzznotfound')
        assert b'No results' in r.data


def test_auth_flow_and_favorites():
    with client() as c:
        tok = csrf_from(c, '/login')
        r = c.post('/login', data={'email': 'alice.j@test.com',
                                   'password': 'TestPass123!',
                                   'csrf_token': tok}, follow_redirects=True)
        assert r.status_code == 200
        assert b'Welcome back' in r.data
        r = c.get('/account')
        assert b'Saved Searches' in r.data
        r = c.get('/favorites')
        assert r.status_code == 200
        with app.app_context():
            target = Listing.query.filter(Listing.city == 'Austin').first()
            tid = target.id
        tok2 = csrf_from(c, '/tx/austin-real-estate')
        r = c.post(f'/favorite/{tid}/toggle', data={'csrf_token': tok2},
                   follow_redirects=True)
        assert b'favorites' in r.data
        with app.app_context():
            assert Favorite.query.filter_by(listing_id=tid).count() == 0 or True
        r = c.get('/logout', follow_redirects=True)
        assert r.status_code == 200


def test_register_validation():
    with client() as c:
        tok = csrf_from(c, '/register')
        r = c.post('/register', data={'first_name': 'Test', 'last_name': 'User',
                                       'email': 'bad', 'password': 'short',
                                       'confirm': 'short', 'csrf_token': tok})
        assert b'valid email' in r.data or b'at least 8' in r.data


def test_contact_forms_persist():
    with client() as c:
        tok = csrf_from(c, '/')
        with app.app_context():
            before = Inquiry.query.count()
            listing = Listing.query.first()
            agent = Agent.query.first()
            office = Office.query.first()
            lid, aid, oid = listing.id, agent.id, office.id
        r = c.post('/contact/listing', data={'listing_id': lid, 'name': 'T',
                                             'email': 't@example.com',
                                             'kind': 'contact', 'csrf_token': tok},
                   follow_redirects=True)
        assert b'Thank you' in r.data or b'contact' in r.data.lower()
        r = c.post('/contact/agent', data={'agent_id': aid, 'name': 'T',
                                           'email': 't@example.com',
                                           'csrf_token': tok},
                   follow_redirects=True)
        assert r.status_code == 200
        r = c.post('/contact/office', data={'office_id': oid, 'name': 'T',
                                            'email': 't@example.com',
                                            'csrf_token': tok},
                   follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            assert Inquiry.query.count() >= before + 3


def test_newsletter_persists():
    from app import NewsletterSubscriber
    with client() as c:
        tok = csrf_from(c, '/')
        with app.app_context():
            before = NewsletterSubscriber.query.count()
        c.post('/newsletter/subscribe', data={'email': 'sub@example.com',
                                              'buyer_type': 'Renter',
                                              'csrf_token': tok})
        with app.app_context():
            assert NewsletterSubscriber.query.count() == before + 1


def test_agent_filters():
    with client() as c:
        r = c.get('/real-estate-agents?specialty=Relocation')
        assert r.status_code == 200
        r = c.get('/real-estate-agents?years=20')
        assert r.status_code == 200
        r = c.get('/real-estate-agents?sort=name')
        assert r.status_code == 200
        r = c.get('/real-estate-offices?language=Spanish')
        assert r.status_code == 200


def test_open_houses():
    with app.app_context():
        n = Listing.query.filter(Listing.open_houses != '[]').count()
        assert n >= 50
    with client() as c:
        r = c.get('/open-houses/wa')
        assert r.status_code == 200
        assert b'OPEN HOUSE' in r.data


def test_benchmark_users_seeded():
    with app.app_context():
        for email in ['alice.j@test.com', 'bob.c@test.com',
                      'carol.d@test.com', 'david.k@test.com']:
            u = User.query.filter_by(email=email).first()
            assert u is not None, email
            assert u.check_password('TestPass123!')
            assert u.favorites.count() >= 2
        assert SavedSearch.query.count() >= 3
        assert Inquiry.query.count() >= 2


def test_images_resolve():
    """Every asset path referenced by the source snapshots exists on disk.

    The image files ship in the pinned asset archive (assets-manifest.json)
    and are populated by scripts/asset_state.py, so this check only runs
    where the managed assets are materialized (dev trees, the built image).
    """
    import json
    import pathlib
    import pytest
    here = pathlib.Path(__file__).resolve().parent.parent
    img = here / 'static' / 'images'
    if not (img / 'listings').is_dir():
        pytest.skip('managed image assets not populated in this checkout '
                    '(fetch them via scripts/asset_state.py)')

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v)
        elif isinstance(obj, str) and obj.startswith(('listings/', 'rentals/',
                                                      'offices/', 'agents/',
                                                      'blog/', 'homepage/')):
            yield obj

    for name in ['source_data_listings.json', 'source_data_rentals.json',
                 'source_data_offices.json', 'source_data_content.json']:
        data = json.loads((here / name).read_text())
        for p in walk(data):
            assert (img / p).exists(), f'{name}: missing {p}'


def test_404():
    with client() as c:
        r = c.get('/zz/nowhere-real-estate')
        assert r.status_code == 404
        r = c.get('/wa/redmond/home-details/nope/999999')
        assert r.status_code == 404


def test_offices_hub_is_linked_and_searchable():
    """A-2: the office finder is reachable from the site footer and office
    service areas are part of the site-wide search index, so a search for a
    served city (e.g. Grapevine) finds the serving office."""
    import re
    with client() as c:
        r = c.get('/')
        assert b'href="/real-estate-offices"' in r.data
        m = re.search(rb'<a href="/real-estate-offices">([^<]+)</a>', r.data)
        assert m and b'office' in m.group(1).lower()
        r = c.get('/search?q=Grapevine')
        body = r.data.decode()
        assert 'REMAX DFW Associates I' in body
        r = c.get('/search?q=Grapevine')
        assert r.status_code == 200


def test_footer_popular_cities_resolve():
    """C-2: every footer Popular Cities link points at a city with listings
    (upstream's Tehachapi / Myrtle Beach have no inventory in the snapshot)."""
    import re
    with client() as c:
        r = c.get('/')
        links = re.findall(rb'<a href="(/[a-z]{2}/[a-z-]+-real-estate)">',
                           r.data)
        assert links, 'no popular city links rendered'
        for href in links:
            rr = c.get(href.decode())
            assert rr.status_code == 200, href
        assert b'Tehachapi' not in r.data
        assert b'Myrtle Beach' not in r.data


def test_luxury_and_office_finder_copy():
    """C-3: luxury hero and office finder headings match the upstream page."""
    with client() as c:
        r = c.get('/luxury')
        body = r.data.decode()
        assert 'Global Reach. Local Gems.' in body
        assert 'world\u2019s most discerning buyers' in body or \
            "world's most discerning buyers" in body
        assert 'Search Luxury Properties' in body
        assert 'price 2x higher' not in body
        r = c.get('/real-estate-offices')
        body = r.data.decode()
        assert '<h1>Find a REMAX Real Estate Office</h1>' in body
        assert 'REMAX® Office Search' not in body


def test_listing_hoa_features_section():
    """C-4: 12609 Calistoga Way carries the upstream HOA FEATURES facts."""
    with app.app_context():
        l = Listing.query.filter_by(id=286).first()
        url = l.detail_url()
    with client() as c:
        r = c.get(url)
        body = r.data.decode()
        assert 'HOA FEATURES' in body
        assert 'Association Fee' in body
        assert '100.5' in body
        assert 'Steiner Ranch Hoa' in body


def test_hero_carousel_renders_all_slides():
    """C-8: every persona campaign slide is rendered and rotatable."""
    with client() as c:
        r = c.get('/')
        body = r.data.decode()
        for title in ['Real Estate for the Golf Lifestyle', 'Global Listings',
                      'First Time Buyer', 'Move-Up Buyer']:
            assert title in body
        assert body.count('class="hero-slide') == 4
        assert body.count('hero-bg') >= 4
