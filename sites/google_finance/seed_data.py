"""Idempotent seed for the Google Finance mirror.

Runs at every container boot and every /reset/google_finance. Each seed
function early-returns on a populated DB so re-seeding is a genuine no-op —
a bare commit on a populated DB still bumps SQLite metadata and would break
the byte-identical reset invariant.

Company identities, logos and profile prose come from `_companies.py`, which
is generated once from the recon harvest (`_dev/build_company_module.py`) and
committed. Nothing here reads scraped_data/ — that directory is gitignored and
dockerignored, so it does not exist inside the image.
"""
import json

import _market_data as MD
from _companies import ANCHORS, COMPANIES, PUBLISHERS
from _content import (MARKET_SUMMARIES, build_company_news, build_market_news)
from _universe import (CRYPTO, CURRENCIES, ETFS, FUTURES, INDEX_LEVELS,
                       INDEXES, SECTOR_INDEXES, SHORT_NAMES, STOCKS)

INTRADAY_POINTS = 79            # 5-minute bars across a 6.5-hour session
FIVEDAY_PER_SESSION = 13        # 30-minute bars

# Companies flagged on the Climate leaders board. Fixed list so the page is
# stable across reseeds; chosen to span several sectors rather than only tech.
CLIMATE_LEADERS = {
    'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'ORCL', 'CRM', 'ACN',
    'NEE', 'DUK', 'SO', 'AEP',
    'PG', 'KO', 'CL', 'KMB',
    'LIN', 'APD', 'ECL',
    'UNP', 'DE', 'HON',
    'V', 'MA', 'SPGI',
    'PLD', 'EQIX',
}

# Fallback display names for symbols the recon pass could not name.
FALLBACK_NAMES = {
    'CL=F': 'Crude Oil', 'GC=F': 'Gold', 'SI=F': 'Silver',
    'NG=F': 'Natural Gas', 'ZC=F': 'Corn', 'ES=F': 'E-Mini S&P 500',
}

FUTURE_UNITS = {
    'CL=F': 'USD / bbl', 'GC=F': 'USD / oz', 'SI=F': 'USD / oz',
    'NG=F': 'USD / MMBtu', 'ZC=F': 'USD / bu', 'ES=F': 'index points',
}

# Magnitude fallbacks when the recon pass has no anchor for a symbol.
DEFAULT_LEVEL = {
    'stock': 120.0, 'etf': 260.0, 'index': 4200.0, 'sector': 900.0,
    'crypto': 180.0, 'currency': 1.10, 'future': 78.0,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _anchor(slug, field, default=None):
    a = ANCHORS.get(slug) or {}
    v = a.get(field)
    return v if v not in (None, '') else default


def _level_for(slug, kind):
    """Price level for a symbol, nudged off its anchor.

    The anchor is a real open price (or a hand-set round number for crypto and
    FX). Shipping it unchanged would both look artificial — BTC at exactly
    108,000.00 — and imply the mirror serves live values. The nudge is
    deterministic, so the frozen number is stable across reseeds.
    """
    base = (_anchor(slug, 'price') or INDEX_LEVELS.get(slug)
            or DEFAULT_LEVEL[kind])
    return base * MD.rng_for(slug, 'level').uniform(0.93, 1.07)


def _five_day_path(symbol, closes, kind='stock'):
    """Concatenated intraday paths for the last five sessions."""
    out = []
    for k in range(5, 0, -1):
        seg = MD.intraday_path(symbol, closes[-k - 1], closes[-k],
                               FIVEDAY_PER_SESSION, 0.010, salt=f'5d{k}',
                               kind=kind)
        out.extend(seg)
    return out


def _make_series(db, M, inst, kind, sector, level):
    closes = MD.daily_closes(inst.slug, level, kind, sector)
    volumes = MD.daily_volumes(inst.slug, 1e7)
    sigma = MD.CLASS_PARAMS.get(kind, MD.CLASS_PARAMS['stock'])[0]
    intraday = MD.intraday_path(inst.slug, closes[-2], closes[-1],
                                INTRADAY_POINTS, sigma, kind=kind)
    five = _five_day_path(inst.slug, closes, kind)
    intra_vol = MD.intraday_volumes(inst.slug, volumes[-1], INTRADAY_POINTS)
    db.session.add(M['PriceHistory'](
        instrument_id=inst.id,
        daily_json=json.dumps(closes),
        volume_json=json.dumps(volumes),
        intraday_json=json.dumps(intraday),
        intraday_volume_json=json.dumps(intra_vol),
        intraday5d_json=json.dumps(five),
        after_json='[]'))
    return closes, volumes, intraday


def _add_quote_full(db, M, inst, sector, closes, volumes, intraday):
    anchors = {
        'mkt_cap': _anchor(inst.slug, 'mkt_cap'),
        'avg_volume': _anchor(inst.slug, 'avg_volume'),
    }
    s = MD.equity_stats(inst.slug, sector, closes, volumes, intraday, anchors)
    db.session.add(M['Quote'](
        instrument_id=inst.id, price=s['price'], prev_close=s['prev_close'],
        change=s['change'], change_pct=s['change_pct'],
        day_open=s['day_open'], day_high=s['day_high'], day_low=s['day_low'],
        wk52_high=s['wk52_high'], wk52_low=s['wk52_low'],
        volume=s['volume'], avg_volume=s['avg_volume'],
        shares_outstanding=s['shares_outstanding'], mkt_cap=s['mkt_cap'],
        eps=s['eps'], pe_ratio=s['pe_ratio'], beta=s['beta'],
        dividend_yield=s['dividend_yield'],
        quarterly_dividend=s['quarterly_dividend'],
        ex_dividend_date=s['ex_dividend_date'],
        after_price=s['after_price'], after_change=s['after_change'],
        after_change_pct=s['after_change_pct']))
    return s


def _add_quote_simple(db, M, inst, closes, intraday):
    s = MD.simple_stats(inst.slug, closes, intraday, inst.kind)
    r = MD.rng_for(inst.slug, 'simple')
    cap = None
    if inst.kind == 'crypto':
        cap = _anchor(inst.slug, 'mkt_cap') or s['price'] * r.uniform(2e7, 9e8)
    db.session.add(M['Quote'](
        instrument_id=inst.id, price=s['price'], prev_close=s['prev_close'],
        change=s['change'], change_pct=s['change_pct'],
        day_open=s['day_open'], day_high=s['day_high'], day_low=s['day_low'],
        wk52_high=s['wk52_high'], wk52_low=s['wk52_low'],
        volume=int(r.uniform(2e6, 9e9)) if inst.kind == 'crypto' else None,
        mkt_cap=cap))
    return s


# ---------------------------------------------------------------------------
# Phase 1 — instruments, prices, fundamentals
# ---------------------------------------------------------------------------

def seed_market(db, M):
    if M['Instrument'].query.count() > 0:
        return

    Instrument = M['Instrument']
    made = {}                       # slug -> Instrument

    # --- equities -----------------------------------------------------------
    equity_specs = []
    for sector, rows in STOCKS.items():
        for ticker, exch in rows:
            equity_specs.append((ticker, exch, sector, 'stock'))
    for ticker, exch in ETFS:
        equity_specs.append((ticker, exch, 'ETF', 'etf'))

    for ticker, exch, sector, kind in equity_specs:
        slug = f'{ticker}:{exch}'
        meta = COMPANIES.get(slug, {})
        about = meta.get('about', {})
        inst = Instrument(
            slug=slug, ticker=ticker, exchange=exch,
            name=meta.get('name') or ticker,
            kind=kind, sector=sector,
            industry=about.get('Sector', ''),
            currency='USD', region='us',
            logo_file=meta.get('logo_file') or '',
            profile=meta.get('profile', ''),
            ceo=about.get('CEO', ''),
            headquarters=about.get('Headquarters', ''),
            founded=about.get('Founded', ''),
            employees=about.get('Employees', ''),
            website=about.get('Website', '') if about.get('Website') != '-' else '',
            is_climate_leader=ticker in CLIMATE_LEADERS)
        db.session.add(inst)
        made[slug] = inst
    db.session.flush()

    for ticker, exch, sector, kind in equity_specs:
        inst = made[f'{ticker}:{exch}']
        closes, volumes, intraday = _make_series(
            db, M, inst, kind, sector, _level_for(inst.slug, kind))
        s = _add_quote_full(db, M, inst, sector, closes, volumes, intraday)
        inst.history.after_json = json.dumps(
            MD.after_hours_path(inst.slug, s['price'], s['after_price'],
                                kind=kind))
        if kind == 'stock' and s['revenue_ttm']:
            _seed_fundamentals(db, M, inst, s, closes)

    # --- indexes, sector indexes -------------------------------------------
    for ticker, exch, name, region in INDEXES:
        slug = f'{ticker}:{exch}'
        inst = Instrument(slug=slug, ticker=ticker, exchange=exch, name=name,
                          short_name=SHORT_NAMES.get(ticker, ''),
                          kind='index', region=region, currency='USD')
        db.session.add(inst)
        made[slug] = inst
    for ticker, label, gics in SECTOR_INDEXES:
        slug = f'{ticker}:INDEXCBOE'
        inst = Instrument(slug=slug, ticker=ticker, exchange='INDEXCBOE',
                          name=f'S&P Select Sector {label} Index',
                          kind='sector', sector=gics, industry=label,
                          region='us', currency='USD')
        db.session.add(inst)
        made[slug] = inst

    # --- crypto, currencies, futures ---------------------------------------
    for ticker, name in CRYPTO:
        inst = Instrument(slug=ticker, ticker=ticker, exchange='', name=name,
                          short_name=SHORT_NAMES.get(ticker, name),
                          kind='crypto', region='crypto', currency='USD')
        db.session.add(inst)
        made[ticker] = inst
    for ticker, name in CURRENCIES:
        inst = Instrument(slug=ticker, ticker=ticker, exchange='', name=name,
                          short_name=ticker.replace('-', ' / '),
                          kind='currency', region='currencies',
                          currency=ticker.split('-')[1])
        db.session.add(inst)
        made[ticker] = inst
    for ticker, name in FUTURES:
        inst = Instrument(slug=ticker, ticker=ticker, exchange='', name=name,
                          short_name=SHORT_NAMES.get(ticker, name),
                          kind='future', region='futures', currency='USD',
                          industry=FUTURE_UNITS.get(ticker, ''))
        db.session.add(inst)
        made[ticker] = inst
    db.session.flush()

    for slug, inst in made.items():
        if inst.kind in ('stock', 'etf'):
            continue
        kind = inst.kind
        closes, volumes, intraday = _make_series(
            db, M, inst, kind, None, _level_for(slug, kind))
        _add_quote_simple(db, M, inst, closes, intraday)

    db.session.flush()
    _seed_related(db, M, made)
    _seed_etf_holdings(db, M, made)
    db.session.commit()
    print(f'[google_finance] seeded {len(made)} instruments')


def _seed_fundamentals(db, M, inst, stats, closes):
    periods_q = MD.recent_quarters(8)
    income = MD.income_statement(inst.slug, stats['revenue_ttm'],
                                 stats['net_income_ttm'],
                                 stats['shares_outstanding'], periods_q)
    balance = MD.balance_sheet(inst.slug, stats['revenue_ttm'], periods_q)
    cash = MD.cash_flow(inst.slug, stats['net_income_ttm'], periods_q)

    for name, rows in (('income', income), ('balance', balance),
                       ('cashflow', cash)):
        for ordinal, row in enumerate(rows):
            db.session.add(M['FinancialRow'](
                instrument_id=inst.id, statement=name, period_type='quarterly',
                period_label=row['period'], ordinal=ordinal,
                items_json=json.dumps(row)))

    # Annual view: sum the four quarters of each calendar year we cover fully.
    for name, rows in (('income', income), ('cashflow', cash)):
        by_year = {}
        for row in rows:
            year = row['period'].split()[1]
            by_year.setdefault(year, []).append(row)
        ordinal = 0
        for year in sorted(by_year):
            group = by_year[year]
            if len(group) < 4:
                continue
            agg = {'period': year}
            for k in group[0]:
                if k == 'period':
                    continue
                vals = [g[k] for g in group if isinstance(g[k], (int, float))]
                if not vals:
                    continue
                agg[k] = (sum(vals) if k not in
                          ('net_profit_margin', 'effective_tax_rate')
                          else sum(vals) / len(vals))
            db.session.add(M['FinancialRow'](
                instrument_id=inst.id, statement=name, period_type='annual',
                period_label=year, ordinal=ordinal,
                items_json=json.dumps(agg)))
            ordinal += 1

    earn = MD.earnings_rows(inst.slug, income)
    for m in MD.key_moments(inst.slug, closes, MD.CALENDAR, earn):
        db.session.add(M['KeyMoment'](
            instrument_id=inst.id, moment_date=m['date'], kind=m['kind'],
            title=m['title']))

    for row in earn:
        db.session.add(M['EarningsRow'](
            instrument_id=inst.id, quarter=row['quarter'],
            report_date=row['report_date'], eps_estimate=row['eps_estimate'],
            eps_actual=row['eps_actual'],
            revenue_estimate=row['revenue_estimate'],
            revenue_actual=row['revenue_actual'],
            surprise_pct=row['surprise_pct']))

    for h in MD.institutional_holders(inst.slug, stats['shares_outstanding'],
                                      stats['price']):
        db.session.add(M['InstitutionalHolder'](
            instrument_id=inst.id, firm=h['firm'], pct_held=h['pct_held'],
            shares=h['shares'], value=h['value'], change_pct=h['change_pct']))

    for r in MD.analyst_coverage(inst.slug, stats['price']):
        db.session.add(M['AnalystRating'](
            instrument_id=inst.id, firm=r['firm'], rating=r['rating'],
            price_target=r['price_target'], rated_on=r['rated_on']))


def _seed_related(db, M, made):
    """Related-instrument graph: harvested neighbours first, then same sector."""
    by_sector = {}
    for slug, inst in made.items():
        if inst.kind == 'stock':
            by_sector.setdefault(inst.sector, []).append(slug)
    for k in by_sector:
        by_sector[k].sort()

    for slug, inst in made.items():
        rel = []
        for cand in (COMPANIES.get(slug, {}).get('related') or []):
            if cand in made and cand != slug and cand not in rel:
                rel.append(cand)
        if inst.kind == 'stock':
            for cand in by_sector.get(inst.sector, []):
                if len(rel) >= 6:
                    break
                if cand != slug and cand not in rel:
                    rel.append(cand)
        elif inst.kind in ('index', 'sector'):
            peers = sorted(s for s, i in made.items() if i.kind == inst.kind)
            for cand in peers:
                if len(rel) >= 6:
                    break
                if cand != slug and cand not in rel:
                    rel.append(cand)
        elif inst.kind in ('crypto', 'currency', 'future', 'etf'):
            peers = sorted(s for s, i in made.items() if i.kind == inst.kind)
            for cand in peers:
                if len(rel) >= 6:
                    break
                if cand != slug and cand not in rel:
                    rel.append(cand)
        inst.related_json = json.dumps(rel[:6])


ETF_MANDATE = {
    'SPY': None, 'VOO': None, 'IVV': None, 'VTI': None, 'IWM': None,
    'QQQ': ['Technology', 'Communication Services', 'Consumer Discretionary'],
    'XLK': ['Technology'],
    'XLE': ['Energy'],
    'XLF': ['Financials'],
    'ARKK': ['Technology', 'Health Care', 'Consumer Discretionary'],
    'VIG': ['Consumer Staples', 'Health Care', 'Industrials', 'Financials'],
    'SCHD': ['Consumer Staples', 'Energy', 'Health Care', 'Financials'],
}


def _seed_etf_holdings(db, M, made):
    stocks = [(s, i) for s, i in made.items() if i.kind == 'stock']
    for slug, inst in made.items():
        if inst.kind != 'etf':
            continue
        mandate = ETF_MANDATE.get(inst.ticker)
        pool = [(s, i) for s, i in stocks
                if mandate is None or i.sector in mandate]
        pool.sort(key=lambda x: -(x[1].quote.mkt_cap or 0) if x[1].quote else 0)
        picks = pool[:12]
        if not picks:
            continue
        rng = MD.rng_for(slug, 'holdings')
        raw = [max(0.4, rng.gauss(8, 4)) for _ in picks]
        total = sum(raw)
        for (hslug, hinst), w in zip(picks, raw):
            db.session.add(M['EtfHolding'](
                etf_id=inst.id, holding_id=hinst.id,
                weight_pct=round(w / total * 100 * 0.72, 2)))


# ---------------------------------------------------------------------------
# Phase 2 — publishers, market summaries, news
# ---------------------------------------------------------------------------

def seed_news(db, M):
    if M['NewsArticle'].query.count() > 0:
        return

    pubs = {}
    for p in PUBLISHERS:
        row = M['Publisher'](name=p['name'], domain=p['domain'],
                             favicon_file=p.get('file', ''))
        db.session.add(row)
        pubs[p['domain']] = row
    db.session.flush()
    pub_list = [pubs[p['domain']] for p in PUBLISHERS]

    for region, rows in MARKET_SUMMARIES.items():
        for rank, (headline, body, sources) in enumerate(rows):
            db.session.add(M['MarketSummary'](
                region=region, headline=headline, body=body,
                sources_count=sources, rank=rank))

    for i, (slug, headline, body, published, region) in enumerate(
            build_market_news()):
        db.session.add(M['NewsArticle'](
            slug=slug, headline=headline,
            publisher_id=pub_list[i % len(pub_list)].id,
            published_at=published, summary=body.split('\n\n')[0],
            body=body, scope='market', region=region))

    instruments = (M['Instrument'].query
                   .filter(M['Instrument'].kind.in_(['stock', 'etf']))
                   .order_by(M['Instrument'].slug).all())
    db.session.flush()
    counter = 0
    for inst in instruments:
        for slug, headline, summary, body, published in build_company_news(
                inst.ticker, inst.name):
            art = M['NewsArticle'](
                slug=slug, headline=headline,
                publisher_id=pub_list[counter % len(pub_list)].id,
                published_at=published, summary=summary, body=body,
                scope='company', region='us')
            db.session.add(art)
            db.session.flush()
            db.session.add(M['NewsLink'](news_id=art.id,
                                         instrument_id=inst.id))
            counter += 1

    db.session.commit()
    print(f'[google_finance] seeded {counter} company articles, '
          f'{len(PUBLISHERS)} publishers')


# ---------------------------------------------------------------------------
# Phase 3 — benchmark accounts
# ---------------------------------------------------------------------------

PASSWORD = 'TestPass123!'
BENCHMARK_USERS = [
    {'email': 'alice.j@test.com', 'username': 'alice_j', 'name': 'Alice Johnson'},
    {'email': 'bob.c@test.com', 'username': 'bob_c', 'name': 'Bob Chen'},
    {'email': 'carol.d@test.com', 'username': 'carol_d', 'name': 'Carol Davis'},
    {'email': 'david.k@test.com', 'username': 'david_k', 'name': 'David Kim'},
]

# Alice keeps two lists and two portfolios so "remove X from my list" and
# "what is my portfolio worth" are genuine disambiguation tasks rather than
# single-row lookups.
ALICE_LISTS = {
    'Tech watch': ['AAPL:NASDAQ', 'MSFT:NASDAQ', 'NVDA:NASDAQ',
                   'AMD:NASDAQ', 'CRM:NYSE'],
    'Dividend income': ['KO:NYSE', 'PG:NYSE', 'XOM:NYSE', 'DUK:NYSE',
                        'O:NYSE', 'VZ:NYSE'],
}
ALICE_PORTFOLIOS = {
    'Retirement': (4820.55, [
        ('AAPL:NASDAQ', 120, 214.30, '2024-03-18'),
        ('MSFT:NASDAQ', 65, 298.75, '2023-11-02'),
        ('JPM:NYSE', 90, 168.40, '2024-07-09'),
        ('JNJ:NYSE', 140, 152.15, '2023-05-22'),
        ('VOO:NYSEARCA', 45, 402.60, '2022-09-14'),
    ]),
    'Growth ideas': (1150.00, [
        ('NVDA:NASDAQ', 40, 96.85, '2024-01-25'),
        ('TSLA:NASDAQ', 55, 242.10, '2025-02-11'),
        ('ABNB:NASDAQ', 70, 131.45, '2024-10-30'),
    ]),
}
# Bob, Carol and David each carry a themed list and one portfolio, so every
# benchmark account has pre-existing auth-gated state. Cost bases are set
# against the frozen MARKET_DATE prices to give each portfolio a spread of
# gains including one losing position.
BOB_LISTS = {
    'Media & platforms': ['GOOGL:NASDAQ', 'META:NASDAQ', 'NFLX:NASDAQ',
                          'DIS:NYSE'],
}
BOB_PORTFOLIOS = {
    'Brokerage': (1540.60, [
        ('META:NASDAQ', 25, 372.80, '2023-09-27'),
        ('DIS:NYSE', 110, 104.50, '2024-04-03'),
        ('TMUS:NASDAQ', 40, 148.25, '2023-06-16'),
        ('VTI:NYSEARCA', 35, 226.15, '2022-08-10'),
    ]),
}
CAROL_LISTS = {
    'Healthcare': ['ABBV:NYSE', 'LLY:NYSE', 'MRK:NYSE', 'PFE:NYSE',
                   'TMO:NYSE', 'UNH:NYSE'],
}
CAROL_PORTFOLIOS = {
    'Core holdings': (2310.40, [
        ('UNH:NYSE', 35, 486.20, '2024-06-12'),
        ('LLY:NYSE', 20, 742.90, '2023-08-15'),
        ('COST:NASDAQ', 15, 605.20, '2022-12-06'),
        ('SPY:NYSEARCA', 30, 428.75, '2023-04-19'),
    ]),
}
DAVID_LISTS = {
    'Semiconductors': ['AMAT:NASDAQ', 'AVGO:NASDAQ', 'LRCX:NASDAQ',
                       'MU:NASDAQ', 'QCOM:NASDAQ', 'TXN:NASDAQ'],
}
DAVID_PORTFOLIOS = {
    'Long term': (745.80, [
        ('AMZN:NASDAQ', 50, 138.60, '2023-03-08'),
        ('GOOGL:NASDAQ', 60, 121.35, '2022-11-21'),
        ('QCOM:NASDAQ', 45, 182.90, '2025-01-14'),
        ('QQQ:NASDAQ', 25, 355.90, '2023-01-31'),
    ]),
}


def seed_benchmark_users(db, M, bcrypt):
    if M['User'].query.filter_by(email='alice.j@test.com').first():
        return

    users = {}
    for spec in BENCHMARK_USERS:
        u = M['User'](email=spec['email'], username=spec['username'],
                      name=spec['name'])
        u.password_hash = bcrypt.generate_password_hash(
            PASSWORD).decode('utf-8')
        db.session.add(u)
        users[spec['email']] = u
    db.session.flush()

    def inst_by(slug):
        return M['Instrument'].query.filter_by(slug=slug).first()

    def add_lists(user, mapping):
        for name, slugs in mapping.items():
            wl = M['Watchlist'](user_id=user.id, name=name)
            db.session.add(wl)
            db.session.flush()
            for s in slugs:
                inst = inst_by(s)
                if inst:
                    db.session.add(M['WatchlistItem'](watchlist_id=wl.id,
                                                      instrument_id=inst.id))

    def add_portfolios(user, mapping):
        for name, (cash, lots) in mapping.items():
            p = M['Portfolio'](user_id=user.id, name=name, cash=cash)
            db.session.add(p)
            db.session.flush()
            for slug, shares, cost, bought in lots:
                inst = inst_by(slug)
                if inst:
                    db.session.add(M['PortfolioLot'](
                        portfolio_id=p.id, instrument_id=inst.id,
                        shares=shares, cost_basis=cost, purchased_on=bought))

    # Order matters: watchlist ids are assigned in insertion order and the
    # robustness suite reads /lists/3 as "a list Alice does not own".
    add_lists(users['alice.j@test.com'], ALICE_LISTS)
    add_portfolios(users['alice.j@test.com'], ALICE_PORTFOLIOS)
    add_lists(users['bob.c@test.com'], BOB_LISTS)
    add_portfolios(users['bob.c@test.com'], BOB_PORTFOLIOS)
    add_lists(users['carol.d@test.com'], CAROL_LISTS)
    add_portfolios(users['carol.d@test.com'], CAROL_PORTFOLIOS)
    add_lists(users['david.k@test.com'], DAVID_LISTS)
    add_portfolios(users['david.k@test.com'], DAVID_PORTFOLIOS)

    db.session.commit()
    print(f'[google_finance] seeded {len(BENCHMARK_USERS)} benchmark users')
