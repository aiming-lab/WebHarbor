"""Parkers mirror — site test suite (pytest).

Run from sites/parkers:  python -m pytest tests/ -q
Uses the app's test client against a scratch copy of the shipped seed DB
(see conftest.py) so write-path tests never mutate the real instance DB.
"""
import os
import re
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import (ReviewSection, app, db, CarModel, Derivative, Generation, Guide,
                 Listing, Make, NewsArticle, OwnerReview, SavedValuation, TaxRate,
                 User, Valuation, RegLookup)


@pytest.fixture()
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with app.app_context():
            yield c


def test_health(client):
    r = client.get('/_health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['counts']['models'] > 100
    assert data['counts']['listings'] > 300
    assert data['counts']['valuations'] > 500


def test_core_pages_200(client):
    for path in ['/', '/car-reviews/', '/car-valuation/', '/car-specs/',
                 '/cars-for-sale/', '/cars-for-sale/used/', '/car-news/',
                 '/best-cars/', '/owner-reviews/', '/car-tax/',
                 '/car-insurance/insurance-groups/', '/search/?q=golf',
                 '/my-parkers/login/', '/about-us/', '/contact-us/']:
        assert client.get(path).status_code == 200, path


def test_review_chain(client):
    r = client.get('/car-reviews/')
    assert b'Car reviews' in r.data
    r = client.get('/ford/reviews/')
    assert r.status_code == 200 and b'Fiesta' in r.data
    r = client.get('/ford/fiesta/review/')
    assert r.status_code == 200
    r = client.get('/ford/fiesta/review/verdict/')
    assert r.status_code == 200
    r = client.get('/ford/fiesta/review/practicality/')
    assert r.status_code == 200
    assert client.get('/ford/fiesta/review/notasection/').status_code == 404


def test_specs_chain(client):
    r = client.get('/car-specs/')
    assert r.status_code == 200
    r = client.get('/ford/fiesta/specs/')
    assert r.status_code == 200
    with app.app_context():
        g = (Generation.query
             .join(CarModel, Generation.model_id == CarModel.id)
             .join(Make, CarModel.make_id == Make.id)
             .filter(Make.slug == 'ford', CarModel.slug == 'fiesta')
             .order_by(Generation.year_from.desc()).first())
        assert g is not None
        gen_slug = g.slug
        d = g.derivatives[0] if g.derivatives else None
        assert d is not None
        dslug = d.urlslug
    r = client.get(f'/ford/fiesta/{gen_slug}/specs/')
    assert r.status_code == 200
    r = client.get(f'/ford/fiesta/{gen_slug}/specs/?deriv={dslug}')
    assert r.status_code == 200 and d.name.encode() in r.data
    r = client.get(f'/ford/fiesta/{gen_slug}/{dslug}/specs/')
    assert r.status_code == 200


def test_valuation_chain(client):
    with app.app_context():
        v = (Valuation.query
             .join(Derivative, Valuation.derivative_id == Derivative.id)
             .join(Generation, Derivative.generation_id == Generation.id)
             .join(CarModel, Generation.model_id == CarModel.id)
             .join(Make, CarModel.make_id == Make.id)
             .filter(Make.slug == 'ford', CarModel.slug == 'fiesta')
             .order_by(Valuation.year_plate).first())
        assert v is not None
        d = v.derivative
        g = d.generation
        m = g.model
        gen_path = f'/{m.make.slug}/{m.slug}/{g.slug}/used-prices/'
        sel_url = (f'/{m.make.slug}/{m.slug}/{g.slug}/{d.urlslug}/{v.id}/'
                   'select-a-valuation/')
        free_url = (f'/{m.make.slug}/{m.slug}/{g.slug}/{d.urlslug}/{v.id}/'
                    'free-valuation/')
        pro_url = (f'/{m.make.slug}/{m.slug}/{g.slug}/{d.urlslug}/{v.id}/'
                   'pro-valuation/')
        year = v.year_plate
    r = client.get(gen_path)
    assert r.status_code == 200 and year.encode() in r.data
    r = client.get(gen_path + f'?year={year}')
    assert r.status_code == 200 and d.name.encode() in r.data
    r = client.get(sel_url)
    assert r.status_code == 200 and b'Free Valuation' in r.data
    r = client.get(free_url)
    assert r.status_code == 200 and b'Buying privately' in r.data
    r = client.get(pro_url)
    assert r.status_code == 200 and b'6.99' in r.data
    assert client.get(sel_url + 'x').status_code == 404


def test_reg_lookup(client):
    with app.app_context():
        reg = RegLookup.query.first()
        assert reg is not None
        reg_text, vid = reg.reg, reg.valuation_id
        v = db.session.get(Valuation, vid)
        d = v.derivative
        g = d.generation
        m = g.model
        expect = (f'/{m.make.slug}/{m.slug}/{g.slug}/{d.urlslug}/{vid}/'
                  'select-a-valuation/')
    r = client.post('/car-valuation/lookup/', data={'reg': reg_text},
                    follow_redirects=False)
    assert r.status_code == 302 and r.headers['Location'].endswith(expect)
    r = client.post('/car-valuation/lookup/', data={'reg': 'ZZ99ZZZ'})
    assert b'no valuation data found' in r.data


def test_cars_for_sale_filters(client):
    r = client.get('/cars-for-sale/search-results/?make=ford&price_max=15000&sort=price-asc')
    assert r.status_code == 200
    r = client.get('/cars-for-sale/search-results/?transmission=Automatic&fuel=Petrol')
    assert r.status_code == 200
    r = client.get('/cars-for-sale/fuel-electric/')
    assert r.status_code == 200
    r = client.get('/cars-for-sale/price-10000/')
    assert r.status_code == 200
    r = client.get('/ford/for-sale/')
    assert r.status_code == 200
    r = client.get('/ford/fiesta/for-sale/')
    assert r.status_code == 200
    with app.app_context():
        l = Listing.query.filter(Listing.image != '').first()
        assert l is not None
        lid = l.id
    r = client.get(f'/cars-for-sale/listing/{lid}/')
    assert r.status_code == 200


def test_search_scored(client):
    r = client.get('/search/?q=ford fiesta')
    assert r.status_code == 200
    assert b'Fiesta' in r.data
    r = client.get('/search/?q=zzzznothing')
    assert b'No results' in r.data


def test_news_and_guides(client):
    with app.app_context():
        a = NewsArticle.query.filter(NewsArticle.body_json != '[]').first()
        assert a is not None
        slug = a.slug
        g = Guide.query.filter(Guide.ranked_json != '[]').first()
        assert g is not None
        gslug = g.slug
    r = client.get('/car-news/')
    assert r.status_code == 200
    r = client.get(f'/car-news/{slug}/')
    assert r.status_code == 200
    r = client.get('/best-cars/')
    assert r.status_code == 200
    r = client.get(f'/best-cars/{gslug}/')
    assert r.status_code == 200
    assert client.get('/car-news/does-not-exist/').status_code == 404


def test_insurance_and_tax(client):
    r = client.get('/car-insurance/insurance-groups/')
    assert r.status_code == 200
    with app.app_context():
        g = (Generation.query
             .join(CarModel, Generation.model_id == CarModel.id)
             .join(Make, CarModel.make_id == Make.id)
             .join(Derivative, Derivative.generation_id == Generation.id)
             .filter(Derivative.insurance_group.isnot(None))
             .first())
        assert g is not None
        m = g.model
        path = f'/{m.make.slug}/{m.slug}/{g.slug}/insurance-groups/'
        tax_path = f'/{m.make.slug}/{m.slug}/{g.slug}/car-tax/'
    r = client.get(path)
    assert r.status_code == 200 and b'Insurance group' in r.data
    r = client.get('/car-tax/')
    assert r.status_code == 200
    r = client.get(tax_path)
    assert r.status_code == 200


def test_owner_reviews(client):
    r = client.get('/owner-reviews/')
    assert r.status_code == 200
    with app.app_context():
        o = OwnerReview.query.filter(OwnerReview.body_json != '[]').first()
        assert o is not None
        path = f'/{o.make_slug}/{o.model_slug}/{o.gen_slug}/owner-reviews/'
    r = client.get(path)
    assert r.status_code == 200
    # submit a review
    r = client.post(path, data={
        'rating': '4', 'derivative': '1.0 Test Edition 5d',
        'year_plate': '2021/21', 'bought': 'Used in 2023',
        'author': 'Test Runner', 'body': 'Great little car.\nNo issues so far.'},
        follow_redirects=True)
    assert r.status_code == 200 and b'Test Runner' in r.data
    with app.app_context():
        assert OwnerReview.query.filter_by(author='Test Runner').count() == 1
        db.session.query(OwnerReview).filter_by(author='Test Runner').delete()
        db.session.commit()


def test_auth_and_shortlist(client):
    r = client.post('/my-parkers/login/',
                    data={'email': 'alice.j@test.com', 'password': 'TestPass123!'},
                    follow_redirects=True)
    assert r.status_code == 200 and b'Alice' in r.data
    with app.app_context():
        l = Listing.query.order_by(Listing.price).first()
        lid = l.id
    r = client.post(f'/cars-for-sale/listing/{lid}/save/',
                    data={'next': '/my-parkers/shortlist/'},
                    follow_redirects=True)
    assert b'shortlist' in r.data
    r = client.get('/my-parkers/shortlist/')
    assert r.status_code == 200
    # toggle it back off to restore state
    client.post(f'/cars-for-sale/listing/{lid}/save/',
                data={'next': '/my-parkers/shortlist/'})
    r = client.get('/my-parkers/logout/', follow_redirects=True)
    assert r.status_code == 200
    r = client.get('/my-parkers/')
    assert r.status_code == 302  # login required


def test_saved_valuation_flow(client):
    client.post('/my-parkers/login/',
                data={'email': 'alice.j@test.com', 'password': 'TestPass123!'})
    with app.app_context():
        alice = User.query.filter_by(email='alice.j@test.com').first()
        already = {s.valuation_id for s in SavedValuation.query.filter_by(user_id=alice.id)}
        v = next(x for x in Valuation.query.order_by(Valuation.id).all()
                 if x.id not in already)
        d = v.derivative
        g = d.generation
        m = g.model
        free_url = (f'/{m.make.slug}/{m.slug}/{g.slug}/{d.urlslug}/{v.id}/'
                    'free-valuation/')
    r = client.get(free_url)
    assert r.status_code == 200 and b'saved to your Parkers account' in r.data
    r = client.get('/my-parkers/saved-valuations/')
    assert r.status_code == 200
    client.get('/my-parkers/logout/')


def test_register_profile(client):
    r = client.post('/my-parkers/register/',
                    data={'name': 'Test User', 'email': 'test.user@test.com',
                          'password': 'Password123'},
                    follow_redirects=True)
    assert r.status_code == 200 and b'Test User' in r.data
    with app.app_context():
        u = User.query.filter_by(email='test.user@test.com').first()
        assert u is not None
        uid = u.id
    r = client.post('/my-parkers/profile/',
                    data={'name': 'Renamed User', 'postcode': 'M1 1AA'},
                    follow_redirects=True)
    assert b'profile has been updated' in r.data
    with app.app_context():
        u = db.session.get(User, uid)
        assert u.display_name == 'Renamed User'
        db.session.delete(u)
        db.session.commit()


def test_seed_idempotence_shape(client):
    """The shipped seed functions must be whole-function gated."""
    import seed_data
    with app.app_context():
        before = CarModel.query.count()
        seed_data.seed_database()
        seed_data.seed_benchmark_users()
        assert CarModel.query.count() == before


def test_review_sections_render_prose(client):
    """A-2: every review section page renders its captured body text."""
    with app.app_context():
        secs = ReviewSection.query.filter(ReviewSection.paragraphs_json != '[]').all()
        assert len(secs) > 900
        sample = [s for s in secs if s.section_key == 'verdict'][:40]
        paths = []
        for s in sample:
            m = (CarModel.query.join(Make, CarModel.make_id == Make.id)
                 .filter(CarModel.id == s.model_id).first())
            paths.append((f'/{m.make.slug}/{m.slug}/review/verdict/', s))
    for path, s in paths:
        r = client.get(path)
        assert r.status_code == 200, path
        body = r.data.decode()
        assert 'review-prose' in body
        # the first captured paragraph must actually render
        import json as _json
        first = _json.loads(s.paragraphs_json)[0]
        assert first[:60] in body, (path, first[:60])
    # no stylesheet/footer junk survives materialization
    with app.app_context():
        for s in ReviewSection.query.all():
            assert '@media' not in s.paragraphs_json
            assert 'Bauer Media Group consists' not in s.paragraphs_json


def test_owner_reviews_full_content(client):
    """A-3: seed owner reviews carry full text and metadata and render it."""
    with app.app_context():
        n = OwnerReview.query.count()
        full = OwnerReview.query.filter(
            OwnerReview.author != '', OwnerReview.published != '',
            OwnerReview.year_plate != '', OwnerReview.bought != '').count()
        assert n == full == 126
        o = OwnerReview.query.filter(OwnerReview.make_slug == 'ford',
                                     OwnerReview.model_slug == 'fiesta').first()
        assert 'Gearbox output bearing' in (o.body_json or '')
        path = f'/{o.make_slug}/{o.model_slug}/{o.gen_slug}/owner-reviews/'
    r = client.get(path)
    assert r.status_code == 200
    body = r.data.decode()
    assert 'By john rogula on 15 July 2024' in body
    assert 'Year/plate: 2018/18' in body
    assert 'Bought: Used in February 2021' in body
    assert 'Gearbox output bearing replaced under warranty' in body


def test_tax_rates_2026_27(client):
    """A-4: the car-tax table carries the 2026/27 rates and matches per-car tax."""
    r = client.get('/car-tax/')
    assert r.status_code == 200
    body = r.data.decode()
    assert '£200' in body          # standard annual rate (petrol/diesel/hybrid)
    assert '£10 first-year rate' in body   # EV first-year wording
    assert '£560' in body          # 131-150 g/km first-year rate
    assert '£425' in body          # Expensive Car Supplement
    assert '£195' not in body       # FY2024/25 standard rate must be gone
    with app.app_context():
        g = (Generation.query
             .join(CarModel, Generation.model_id == CarModel.id)
             .join(Make, CarModel.make_id == Make.id)
             .filter(Make.slug == 'ford', CarModel.slug == 'fiesta')
             .order_by(Generation.year_from.desc()).first())
        d = next(x for x in g.derivatives if x.slug == 'zetec-10t-ecoboost-100ps-3d')
        assert d.tax_cost == 200   # per-car tax matches the table's standard rate


def test_hub_make_model_searches(client):
    """C-1/C-2/C-3: the insurance, tax and specs hubs populate model options
    server-side and link to the per-generation pages after a make+model pick."""
    # insurance hub
    r = client.get('/car-insurance/insurance-groups/?make=ford')
    assert r.status_code == 200 and '>Fiesta<' in r.data.decode()
    r = client.get('/car-insurance/insurance-groups/?make=ford&model=fiesta')
    body = r.data.decode()
    assert '/ford/fiesta/hatchback-2017/insurance-groups/' in body
    # cheap-insurance buttons point at insurance pages, not review pages
    r = client.get('/car-insurance/insurance-groups/')
    assert 'insurance-groups/' in r.data.decode()
    assert 'href="/ford/reviews/"' not in r.data.decode()
    # car tax hub
    r = client.get('/car-tax/?make=mazda')
    assert '>CX-5<' in r.data.decode()
    r = client.get('/car-tax/?make=mazda&model=cx-5')
    assert '/mazda/cx-5/suv-2026/car-tax/' in r.data.decode()
    # specs hub
    r = client.get('/car-specs/?make=skoda')
    assert '>Kodiaq<' in r.data.decode()
    r = client.get('/car-specs/?make=skoda&model=kodiaq')
    assert '/skoda/kodiaq/specs/' in r.data.decode()


def test_c4s_hub_lists_all_makes(client):
    """C-4: the cars-for-sale manufacturer index is not truncated."""
    r = client.get('/cars-for-sale/')
    body = r.data.decode()
    with app.app_context():
        for mk in Make.query.order_by(Make.name).all():
            assert f'href="/{mk.slug}/for-sale/"' in body, mk.slug


def test_static_advice_pages(client):
    """C-5: the footer/owner-hub link targets all resolve."""
    for path in ['/advertise/', '/terms-and-conditions/', '/car-advice/']:
        assert client.get(path).status_code == 200, path
    # owner hub no longer links the retired star-ratings page
    r = client.get('/owner-reviews/')
    assert 'how-parkers-star-ratings-work' not in r.data.decode()


def test_cx5_suv2017_and_smart_models(client):
    """C-6: the CX-5 (2017-2026) generation and the Smart #1/#3 reviews exist
    under upstream's URL slugs; the review-less C3 Aircross 404s."""
    r = client.get('/mazda/cx-5/suv-2017/owner-reviews/')
    assert r.status_code == 200
    assert 'SUV (2017 - 2026)' in r.data.decode()
    with app.app_context():
        o = OwnerReview.query.filter_by(make_slug='mazda', model_slug='cx-5').first()
        assert o is not None and o.body_json != '[]'
    for path in ['/mazda/cx-5/suv-2017/specs/', '/mazda/cx-5/suv-2017/used-prices/',
                 '/mazda/cx-5/suv-2017/car-tax/']:
        assert client.get(path).status_code == 200, path
    r = client.get('/smart/1/review/')
    assert r.status_code == 200 and '3.8' in r.data.decode()
    r = client.get('/smart/1/review/verdict/')
    assert r.status_code == 200
    r = client.get('/smart/3/review/')
    assert r.status_code == 200 and '3.5' in r.data.decode()
    r = client.get('/smart/1/suv-2022/specs/')
    assert r.status_code == 200
    assert client.get('/citroen/c3-aircross/review/').status_code == 404


def test_gen_page_titles_carry_model_name(client):
    """D-1: generation-level page titles include the model name."""
    r = client.get('/ford/fiesta/hatchback-2017/car-tax/')
    assert '<title>Ford Fiesta Hatchback (2017 - 2023) car tax' in r.data.decode()
    r = client.get('/ford/fiesta/hatchback-2017/used-prices/')
    assert 'Ford Fiesta Hatchback (2017 - 2023) — used prices' in r.data.decode()
    r = client.get('/ford/fiesta/hatchback-2017/insurance-groups/')
    assert 'Ford Fiesta Hatchback (2017 - 2023) (Hatchback (2017 - 2023)) insurance groups' in r.data.decode()


def test_review_nav_only_links_existing_sections(client):
    """Audit fix: the "Review contents" navigation renders only the sections
    a model actually has — partial-section models no longer emit links to
    404 pages, and full-section models keep all six entries."""
    # 600e has overview+verdict only: nav must not link the four missing ones
    r = client.get('/abarth/600e/review/')
    body = r.data.decode()
    assert r.status_code == 200
    for key in ('practicality', 'interior', 'engines', 'mpg-running-costs'):
        assert f'/abarth/600e/review/{key}' not in body, key
    assert '/abarth/600e/review/verdict' in body
    # the verdict section page of a partial model carries the same filtered nav
    r = client.get('/abarth/600e/review/verdict/')
    body = r.data.decode()
    assert r.status_code == 200
    for key in ('practicality', 'interior', 'engines', 'mpg-running-costs'):
        assert f'/abarth/600e/review/{key}' not in body, key
    # aygo-x has overview only: nav shows just the overview entry
    r = client.get('/toyota/aygo-x/review/')
    body = r.data.decode()
    assert r.status_code == 200
    assert '/toyota/aygo-x/review/verdict' not in body
    # a full-section model keeps the complete six-entry nav
    r = client.get('/bmw/3-series/review/')
    body = r.data.decode()
    assert r.status_code == 200
    for key in ('practicality', 'interior', 'engines', 'mpg-running-costs',
                'verdict'):
        assert f'/bmw/3-series/review/{key}' in body, key


def test_reviewless_model_not_linked_from_review_surfaces(client):
    """Audit fix: the review-less c3-aircross is no longer linked from any
    review surface (make-reviews, body-type listing, model for-sale header,
    generation owner-reviews header) and the hub counts match the filtered
    body-type pages."""
    for path in ('/citroen/reviews/', '/car-reviews/hatchback/'):
        body = client.get(path).data.decode()
        assert '/citroen/c3-aircross/review/' not in body, path
    # model for-sale page: no "Read the review" for a review-less model
    body = client.get('/citroen/c3-aircross/for-sale/').data.decode()
    assert '/citroen/c3-aircross/review/' not in body
    # generation owner-reviews page: no "Review" link for a review-less model
    body = client.get('/citroen/c3-aircross/suv-2025/owner-reviews/').data.decode()
    assert '/citroen/c3-aircross/review/' not in body
    # reviewed models keep their links everywhere
    body = client.get('/citroen/reviews/').data.decode()
    assert '/citroen/c4/review/' in body
    body = client.get('/ford/fiesta/for-sale/').data.decode()
    assert '/ford/fiesta/review/' in body
    # hub counts now count only reviewed models (hatchback: 73 with c3-aircross out)
    with app.app_context():
        n = CarModel.query.filter_by(body_type='hatchback', has_review=True).count()
        assert n == 73, n
    body = client.get('/car-reviews/').data.decode()
    assert f'{n} models reviewed' in body
    body = client.get('/car-reviews/hatchback/').data.decode()
    assert f'{n} hatchbacks reviewed' in body


def test_strapline_renders_first_line_only(client):
    """Audit fix: the scraper stored the whole at-a-glance block after the
    real strapline for some models; the review callout renders only the
    first (human-legit) line, so no page chrome or junk tokens appear."""
    r = client.get('/abarth/600e/review/')
    body = r.data.decode()
    assert r.status_code == 200
    assert 'Hot 600e is a riot' in body
    assert 'data-item-id' not in body
    # the callout itself carries only the one-line strapline
    m = re.search(r'<p class="callout">([^<]*)</p>', body)
    assert m, 'callout missing'
    assert m.group(1).strip() == '" Hot 600e is a riot “ "'
    assert 'At a glance' not in m.group(1)
    # a clean single-line strapline renders unchanged
    r = client.get('/peugeot/308/review/')
    assert 'Looks well-rounded on paper' in r.data.decode()


def test_header_wraps_below_720px():
    """Audit fix (r1 D-2): the one-line header row (logo + 6 nav items +
    account buttons, ~679px minimum) pushed every page 289px past a 390px
    viewport (359px at 320px). Below 720px the row must wrap so the nav
    drops to its own line; at 768px (tablet) the one-line header is kept
    exactly as the r1 review recorded it."""
    css_path = os.path.join(BASE_DIR, 'static', 'css', 'parkers.css')
    with open(css_path) as f:
        css = f.read()
    m = re.search(r'@media \(max-width: 720px\) \{.*?\n\}', css, re.S)
    assert m, '720px header media query missing from parkers.css'
    block = m.group(0)
    assert '.site-header__row' in block and 'flex-wrap: wrap' in block, \
        'header row must wrap below 720px'
    assert '.site-header__nav' in block and 'flex-basis: 100%' in block, \
        'nav must take its own full-width line below 720px'
    assert re.search(r'\.primary-nav[^{]*\{[^}]*flex-wrap: wrap', block), \
        'nav items must be allowed to wrap below 720px'

