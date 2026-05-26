"""IMDb mirror seed data — loads from scraped_data/*.json.

Phase 1 (clone-website) loader. Pulls real catalog from Playwright recon:
  scraped_data/chart_top.json         — Top 250 ordered list
  scraped_data/chart_toptv.json
  scraped_data/chart_moviemeter.json
  scraped_data/chart_boxoffice.json
  scraped_data/title_<tt_id>.json     — per-title detail
  scraped_data/name_<nm_id>.json      — per-person detail

Outputs into the SQLAlchemy DB:
  - 18 canonical Genre rows (skill recommends 5-15 categories; IMDb has 18)
  - All scraped Title rows (typed movie / tvSeries)
  - All scraped Person rows linked via Credit
  - 4 benchmark users (alice.j / bob.c / carol.d / david.k @ test.com,
    password TestPass123! — skill convention)
  - Per-user seeded watchlist (4) / ratings (4-6) / one review
  - Curated featured reviews per major title

Idempotent: returns immediately if titles already populated.
Image files are referenced as `static/images/<tt_id>.jpg` etc. — they live
under `static/images/` (HF-managed in the WebHarbor pipeline).

Data integrity safeguards (added after diagnosing scraper output):
  - html.unescape on all string fields (IMDb ld.name emits &apos; etc.)
  - prefer hero h1 (stripped) over ld.name (ld.name is in original language)
  - canonical-URL guard: skip JSON whose ld.url tt_id != filename tt_id
    (IMDb sometimes redirects an unknown tt_id to a different page; without
    this guard, BENCH_USERS' Spirited Away (tt0245429) silently became
    Psycho because IMDb returned the wrong page)
  - case-insensitive substring match on box-office detail keys
"""
import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCRAPED = BASE_DIR / 'scraped_data'
STATIC_IMG = BASE_DIR / 'static' / 'images'
STATIC_IMG.mkdir(parents=True, exist_ok=True)

# Pin reference date so any "today/latest" rendering is stable per skill.
MIRROR_REFERENCE_DATE = datetime(2026, 5, 26)


# IMDb's 18 standard genre buckets (matches their genre browse pages).
GENRES = [
    ('Action', 'action'), ('Adventure', 'adventure'), ('Animation', 'animation'),
    ('Biography', 'biography'), ('Comedy', 'comedy'), ('Crime', 'crime'),
    ('Documentary', 'documentary'), ('Drama', 'drama'), ('Family', 'family'),
    ('Fantasy', 'fantasy'), ('History', 'history'), ('Horror', 'horror'),
    ('Music', 'music'), ('Mystery', 'mystery'), ('Romance', 'romance'),
    ('Sci-Fi', 'sci-fi'), ('Thriller', 'thriller'), ('War', 'war'),
    ('Western', 'western'),
]
GENRE_ALIAS = {
    'sci-fi': 'Sci-Fi', 'science fiction': 'Sci-Fi', 'science-fiction': 'Sci-Fi',
    'film-noir': 'Mystery', 'film noir': 'Mystery', 'short': 'Drama',
    'reality-tv': 'Documentary', 'talk-show': 'Documentary', 'game-show': 'Family',
    'news': 'Documentary', 'sport': 'Documentary',
}


# ------------ helpers ------------------------------------------------------

VOTES_RE = re.compile(r'^([\d.]+)\s*([KMB]?)', re.I)


def _u(s):
    """html.unescape + strip; tolerant of None."""
    if s is None:
        return ''
    return html.unescape(str(s)).strip()


def _parse_votes(s):
    """'3.2M' / '780K' / '12,345' → int."""
    if not s:
        return 0
    s = s.strip().replace(',', '')
    m = VOTES_RE.match(s)
    if not m:
        return 0
    num = float(m.group(1))
    suf = m.group(2).upper() if m.group(2) else ''
    mult = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}.get(suf, 1)
    return int(num * mult)


def _parse_money(s):
    """'$28,341,469 | bo_cumulativeworldwidegross | ...' → 28341469."""
    if not s:
        return None
    m = re.search(r'\$([\d,]+)', s)
    if not m:
        return None
    try:
        return int(m.group(1).replace(',', ''))
    except ValueError:
        return None


def _find_money(details, *needles):
    """Look up detail value by case-insensitive substring of key.

    IMDb's data-testid keys are lowercase (bo_grossdomestic,
    bo_cumulativeworldwidegross, bo_openingweekenddomestic). Earlier camelCase
    lookups missed every entry, producing the all-zero box-office bug.
    """
    if not details:
        return None
    lc = {k.lower(): v for k, v in details.items()}
    for n in needles:
        n_lc = n.lower()
        for k, v in lc.items():
            if n_lc in k:
                return _parse_money(v)
    return None


DURATION_RE = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?')


def _parse_duration(s):
    if not s:
        return None
    m = DURATION_RE.match(s)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return h * 60 + mins or None


YEAR_PAREN_RE = re.compile(r'\((\d{4})(?:[-–](\d{4})?)?\)')
DISAMBIG_RE = re.compile(r'\([IVX]+\)')  # IMDb same-name suffix: (I), (II), (III), ...


def _h1_year(h1):
    """'Inception(2010)' → 2010 ; '12 Angry Men(1957)' → 1957"""
    m = YEAR_PAREN_RE.search(h1 or '')
    if m:
        try:
            return int(m.group(1)), (int(m.group(2)) if m.group(2) else None)
        except ValueError:
            pass
    return None, None


def _strip_year(h1):
    s = YEAR_PAREN_RE.sub('', h1 or '')
    s = DISAMBIG_RE.sub('', s)
    return _u(s)


TT_FROM_URL = re.compile(r'/title/(tt\d+)')


def _ld_tt_id(ld):
    if not ld:
        return None
    u = ld.get('url') or ''
    m = TT_FROM_URL.search(u)
    return m.group(1) if m else None


def _normalize_genre(name, name_to_genre):
    key = (name or '').strip()
    if not key:
        return None
    if key in name_to_genre:
        return name_to_genre[key]
    lo = key.lower()
    canon = GENRE_ALIAS.get(lo)
    if canon and canon in name_to_genre:
        return name_to_genre[canon]
    return None


def _release_year_from_ld(ld):
    dp = (ld or {}).get('datePublished') or ''
    m = re.match(r'^(\d{4})', dp)
    return int(m.group(1)) if m else None


def _country_from_ld(ld):
    """countryOfOrigin shape: [{'@type':'Country','name':'United States'}]"""
    coo = (ld or {}).get('countryOfOrigin') or (ld or {}).get('country')
    if isinstance(coo, list) and coo:
        return coo[0].get('name', '') if isinstance(coo[0], dict) else str(coo[0])
    if isinstance(coo, dict):
        return coo.get('name', '')
    return ''


def _type_from_ld(ld):
    t = (ld or {}).get('@type', '')
    if t == 'TVSeries':
        return 'tvSeries'
    return 'movie'


def _copy_image(src_name, dst_name):
    """Copy scraped image to static/images/. Returns relative path or ''."""
    src = SCRAPED / 'images' / src_name
    if not src.exists() or src.stat().st_size == 0:
        return ''
    dst = STATIC_IMG / dst_name
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    return dst_name


# ------------ chart rank map ----------------------------------------------

def _load_charts():
    """Return (top_rank, popularity_rank, box_office_us, top_tv_rank) dicts."""
    top_rank, pop_rank, top_tv_rank = {}, {}, {}
    bo_us = {}
    for chart, fname in [
        ('top', 'chart_top.json'),
        ('toptv', 'chart_toptv.json'),
        ('moviemeter', 'chart_moviemeter.json'),
        ('boxoffice', 'chart_boxoffice.json'),
    ]:
        f = SCRAPED / fname
        if not f.exists():
            continue
        rows = json.loads(f.read_text())
        for i, r in enumerate(rows, start=1):
            tt = r.get('tt_id')
            if not tt:
                continue
            if chart == 'top':
                top_rank[tt] = i
            elif chart == 'toptv':
                top_tv_rank[tt] = i
            elif chart == 'moviemeter':
                pop_rank[tt] = i
            elif chart == 'boxoffice':
                # box office chart rows have rating_str format too,
                # but no money there; money comes from per-title details.
                pass
    return top_rank, top_tv_rank, pop_rank, bo_us


# ------------ benchmark users (skill canonical) ---------------------------

USERS_SPEC = [
    {'email': 'alice.j@test.com', 'name': 'Alice Johnson',
     'password': 'TestPass123!'},
    {'email': 'bob.c@test.com',   'name': 'Bob Chen',
     'password': 'TestPass123!'},
    {'email': 'carol.d@test.com', 'name': 'Carol Davis',
     'password': 'TestPass123!'},
    {'email': 'david.k@test.com', 'name': 'David Kim',
     'password': 'TestPass123!'},
]


# Featured (seeded) reviews. Headlines avoid leaking title-level facts that
# tasks may ask about (no "Best Picture 1994", no "Box office champion").
SEED_REVIEWS = [
    # high-helpful reviews on the most-trafficked titles
    ('tt0111161', 'CinemaPilgrim',
     'A timeless meditation on hope',
     'Frank Darabont turns the Stephen King novella into a slow-burning hymn to friendship. The performances feel lived-in; the cinematography stays out of the way. Watch it twice — the second viewing is even better.',
     10, 2413),
    ('tt0111161', 'CelluloidDad',
     'Why this one stays at the top',
     'No special effects. No twist endings. Just two prisoners and a quiet question about whether anyone can be remade. Survives on craft alone.',
     10, 1902),
    ('tt0068646', 'NewWaveFan',
     'The blueprint for the modern crime epic',
     'Every modern crime drama lives in the shadow of this 1972 work. The slow gathering of menace, the cool jazz strings, the wedding day staged like a state funeral — it has not been bettered.',
     10, 3120),
    ('tt0468569', 'GothamFan',
     'A villain performance for the record books',
     'Forget the cape. The interrogation room scenes are some of the finest acting put to film in the 2000s. The realist Gotham makes every other comic-book movie look frivolous.',
     10, 4002),
    ('tt1375666', 'DreamArchitect',
     'A summer blockbuster that asks you to keep up',
     'Five-tiered nested heist, an emotional core that earns its sentiment, and an ending that has fueled bar arguments for fifteen years now.',
     9, 1551),
    ('tt0816692', 'DustBowlPilot',
     'Cosmic in the best sense',
     'Wears its Kubrick on its sleeve and earns the comparison. The docking sequence is the most exhilarating five minutes of the decade.',
     10, 1802),
    ('tt0110912', 'ReservoirDad',
     'Pulp, defined',
     'Three years before the Coen brothers found their groove, Tarantino weaponized non-linear narrative for the mainstream. The diner conversation is still a master class.',
     10, 2287),
    ('tt0167260', 'HobbitForever',
     'A trilogy ends in glory',
     'Twelve Academy Awards for a reason. Every character earns a quiet send-off, and the final harbour scene is the kind of farewell most franchises never figure out.',
     10, 1980),
    ('tt0903747', 'AlbuquerqueDealer',
     'Television\'s greatest pivot',
     'A show that began as a quirky drama about a chemistry teacher with cancer ended as a Greek tragedy of a man who became his own worst fear. Cranston\'s arc has no equal on TV.',
     10, 3500),
    ('tt0944947', 'IronThroneWatcher',
     'Eight seasons of grandeur and one of fumble',
     'For seven seasons, the gold standard of TV fantasy. The rushed final season cost it the crown but the first half remains required viewing.',
     8, 1320),
    ('tt15398776', 'AtomicFilmgoer',
     'Three hours of conversation, not a minute wasted',
     'Mostly dialogue, mostly close-up. Murphy is hauntingly internal; the Trinity sequence is craft beyond superlative. Worth the IMAX premium.',
     10, 1710),
    ('tt6751668', 'GenreNomad',
     'A class study in three acts',
     'Bong pivots from satire to thriller to tragedy without missing a beat. The first non-English Best Picture winner — every frame earned.',
     10, 1408),
]


# Watchlists / ratings / reviews per benchmark user.
# Picked to ensure disambiguation tasks: alice's watchlist has 4 items,
# carol's ratings span 5+ titles, etc.
USER_STATE = {
    'alice.j@test.com': {
        'watchlist': ['tt0111161', 'tt0468569', 'tt6751668', 'tt0816692'],
        'ratings': [('tt0111161', 10), ('tt0068646', 10), ('tt0468569', 9),
                    ('tt1375666', 9)],
        'reviews': [
            ('tt0816692', 'Cosmic in the best sense',
             'A film that wears its Kubrick on its sleeve and earns the comparison. The docking sequence alone is worth the IMAX premium.', 10),
        ],
    },
    'bob.c@test.com': {
        'watchlist': ['tt0903747', 'tt0944947', 'tt4574334', 'tt0386676'],
        'ratings': [('tt0903747', 10), ('tt0944947', 9), ('tt0386676', 9),
                    ('tt0167260', 10), ('tt0120737', 10)],
        'reviews': [
            ('tt0386676', 'Comfort TV for the ages',
             'Twenty seasons in and the cold opens still make me laugh out loud.', 9),
        ],
    },
    'carol.d@test.com': {
        'watchlist': ['tt0137523', 'tt0099685', 'tt0114369', 'tt0102926'],
        'ratings': [('tt0137523', 9), ('tt0114369', 8), ('tt0102926', 9),
                    ('tt0110912', 10), ('tt0099685', 9)],
        'reviews': [
            ('tt0137523', 'A movie that grows up with you',
             'Eye-rolling at 16, in love at 22, and at 40 I see it as a tragicomic indictment of consumerism.', 9),
        ],
    },
    'david.k@test.com': {
        'watchlist': ['tt0080684', 'tt0078788', 'tt0050083', 'tt0167260'],
        'ratings': [('tt0080684', 10), ('tt0078788', 9), ('tt0050083', 10)],
        'reviews': [],
    },
}


# News items (12). related_tt and related_nm both supported.
NEWS = [
    ('Oppenheimer dominates the 96th Academy Awards',
     'Christopher Nolan\'s historical epic took home seven Oscars including Best Picture, Best Director, and Best Actor.',
     'IMDb News', '2024-03-11', 'movie', 'tt15398776'),
    ('Stranger Things Season 5 wraps production',
     'The Duffer Brothers confirm filming has finished ahead of the show\'s final season premiere later this year.',
     'IMDb News', '2025-01-08', 'tv', 'tt4574334'),
    ('Greta Gerwig signs on to direct Narnia adaptations',
     'After Barbie\'s global success, Gerwig will helm at least two Narnia films for Netflix.',
     'Variety', '2024-09-22', 'movie', 'tt1517268'),
    ('Cillian Murphy joins Steve adaptation',
     'Following his Best Actor win, Murphy will star in and produce a Netflix film based on Cormac McCarthy\'s work.',
     'Deadline', '2024-06-30', 'celebrity', 'nm0614165'),
    ('Peter Jackson returns to Middle-earth with The Hunt for Gollum',
     'Warner Bros. confirms Andy Serkis will direct with Jackson producing, slated for 2026.',
     'Hollywood Reporter', '2024-05-09', 'movie', 'tt0167260'),
    ('Tom Hanks reflects on 30 years of Forrest Gump',
     'In a candid interview, Hanks revisits the making of the iconic 1994 drama.',
     'IndieWire', '2024-07-06', 'celebrity', 'tt0109830'),
    ('Bong Joon-ho returns with Mickey 17',
     'The Parasite director\'s sci-fi follow-up starring Robert Pattinson hits theaters in March.',
     'IMDb News', '2025-02-14', 'movie', 'tt6751668'),
    ('Robert Downey Jr. cast in Avengers: Doomsday',
     'In a surprise twist, Marvel announces Downey will return as Doctor Doom in 2026.',
     'Marvel Wire', '2024-07-27', 'celebrity', 'nm0000375'),
    ('Quentin Tarantino\'s final film delayed',
     'Production on The Movie Critic has been put on hold; Tarantino is reconsidering the project.',
     'Deadline', '2024-04-18', 'movie', 'tt0110912'),
    ('Anthony Hopkins begins memoir promotion',
     'The two-time Academy Award winner discusses six decades on screen.',
     'IMDb News', '2024-11-04', 'celebrity', 'nm0000164'),
    ('Breaking Bad turns 17',
     'Looking back at how a chemistry teacher became the most quoted antihero on TV.',
     'AV Club', '2025-01-20', 'tv', 'tt0903747'),
    ('Planet Earth III tops critic best-of lists',
     'Sir David Attenborough\'s latest series scores a 100 Metascore.',
     'IMDb News', '2024-12-29', 'tv', 'tt5491994'),
]


# ----------- main entrypoint -------------------------------------------------

def seed_all(db, Title, Person, Genre, Credit, Review, UserRating,
             WatchlistItem, User, NewsItem):
    """Idempotent. Returns silently if already populated."""
    if db.session.query(Title).count() > 0:
        return

    # 1) Genres ------------------------------------------------------------
    name_to_genre = {}
    for name, slug in GENRES:
        g = Genre(name=name, slug=slug)
        db.session.add(g)
        name_to_genre[name] = g
    db.session.flush()

    # 2) Load chart rank maps ---------------------------------------------
    top_rank, top_tv_rank, pop_rank, _ = _load_charts()

    # 3) Persons (load first so credits link cleanly) ---------------------
    nm_to_person = {}
    skipped_garbage = 0
    for f in sorted(SCRAPED.glob('name_*.json')):
        nm_id = f.stem.removeprefix('name_')
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        h1 = d.get('h1') or ''
        # GARBAGE FILTER: IMDb anti-bot rate-limit sometimes serves a 403
        # / Error page. Don't ship those into the DB as real people.
        if h1.startswith(('403', 'Error', '404', '502', '503')) or not h1.strip():
            skipped_garbage += 1
            continue
        ld = d.get('ld') or {}
        # Prefer h1 (stripped of year + (I)/(II) disambig) over ld.name.
        name = _strip_year(h1) or _u(ld.get('name')) or ''
        if not name:
            continue
        # birth_year / death_year: prefer ld.birthDate/deathDate, then h1, then born_block.
        by = dy = None
        bd = (ld.get('birthDate') or '').strip()
        dd = (ld.get('deathDate') or '').strip()
        if bd[:4].isdigit():
            by = int(bd[:4])
        if dd[:4].isdigit():
            dy = int(dd[:4])
        if not by:
            m = YEAR_PAREN_RE.search(h1)
            if m:
                try: by = int(m.group(1))
                except ValueError: pass
            if m and m.group(2):
                try: dy = int(m.group(2))
                except ValueError: pass
        if not by:
            # new scraper produces 'Born\nJuly 30, 1970'
            born_block = d.get('born_block') or ''
            m = re.search(r'(\d{4})', born_block)
            if m:
                by = int(m.group(1))
        if not dy:
            died_block = d.get('died_block') or ''
            m = re.search(r'(\d{4})', died_block)
            if m:
                dy = int(m.group(1))
        prof = ', '.join(d.get('profession') or []) or _u(ld.get('jobTitle'))
        bio = _u(d.get('bio')) or _u(ld.get('description'))
        photo_path = _copy_image(f"{nm_id}.jpg", f"{nm_id}.jpg") if (SCRAPED / 'images' / f'{nm_id}.jpg').exists() else ''
        known_for = d.get('known_for') or []
        p = Person(nm_id=nm_id, name=name, birth_year=by, death_year=dy,
                   birth_place='', bio=(bio or '')[:4000],
                   primary_profession=prof[:200],
                   photo_path=photo_path,
                   known_for_json=json.dumps(known_for))
        db.session.add(p)
        nm_to_person[nm_id] = p
    print(f"[seed] persons loaded={len(nm_to_person)}, garbage_skipped={skipped_garbage}", flush=True)
    db.session.flush()

    # 4) Titles + credits --------------------------------------------------
    tt_to_title = {}
    redirect_skipped = 0
    for f in sorted(SCRAPED.glob('title_*.json')):
        tt_id = f.stem.removeprefix('title_')
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        # CANONICAL-URL GUARD: IMDb sometimes serves a different title's page
        # for an unknown tt_id (Spirited Away → Psycho was observed). Drop any
        # scraped file whose ld.url disagrees with its filename.
        ld = d.get('ld') or {}
        canonical = _ld_tt_id(ld)
        if canonical and canonical != tt_id:
            redirect_skipped += 1
            continue
        if tt_id in tt_to_title:
            continue  # dedupe
        h1 = d.get('h1') or ''
        # Prefer h1 (original Japanese ld.name → en h1: 'Parasite' wins).
        title_text = _strip_year(h1) or _u(ld.get('name')) or tt_id
        year, end_year = _h1_year(h1)
        if year is None:
            year = _release_year_from_ld(ld)
        ttype = _type_from_ld(ld) if ld.get('@type') else 'movie'
        runtime = _parse_duration(ld.get('duration', ''))
        mpaa = _u(ld.get('contentRating'))
        plot = _u(d.get('plot')) or _u(ld.get('description'))
        plot_short = _u(d.get('plot_short')) or plot[:300]
        rating = d.get('rating')
        if rating is None:
            agg = ld.get('aggregateRating') or {}
            rating = agg.get('ratingValue')
        try:
            rating = float(rating) if rating is not None else 0.0
        except (TypeError, ValueError):
            rating = 0.0
        votes = _parse_votes(d.get('votes'))
        if not votes:
            agg = ld.get('aggregateRating') or {}
            votes = int(agg.get('ratingCount') or 0)
        country = _country_from_ld(ld)
        language = ''
        if ld.get('inLanguage'):
            language = ld['inLanguage'] if isinstance(ld['inLanguage'], str) else ''
        # box office: lowercase substring match (IMDb data-testid is lowercase)
        details = d.get('details') or {}
        bo_us   = _find_money(details, 'grossdomestic')
        bo_ww   = _find_money(details, 'cumulativeworldwidegross', 'worldwidegross')
        bo_open = _find_money(details, 'openingweekenddomestic', 'openingweekend')
        budget  = _find_money(details, 'budget')
        release_date = ''
        if details.get('releasedate'):
            release_date = _u(details['releasedate'])[:60]
        elif details.get('releaseDate'):
            release_date = _u(details['releaseDate'])[:60]
        elif ld.get('datePublished'):
            release_date = ld['datePublished']
        poster_path = _copy_image(f'{tt_id}.jpg', f'{tt_id}.jpg') if (SCRAPED / 'images' / f'{tt_id}.jpg').exists() else ''

        tagline = _u(d.get('tagline'))

        t = Title(
            tt_id=tt_id, title_type=ttype, primary_title=title_text,
            year=year, end_year=end_year, runtime_min=runtime, mpaa_rating=mpaa,
            plot_short=plot_short[:480], plot=plot,
            rating_avg=rating, num_votes=votes,
            popularity_rank=pop_rank.get(tt_id),
            top_rank=(top_rank.get(tt_id) or top_tv_rank.get(tt_id)),
            box_office_us=bo_us, box_office_world=bo_ww,
            box_office_opening=bo_open, budget=budget,
            release_date=release_date,
            country=country[:80], language=language[:80],
            poster_path=poster_path,
            taglines_json=json.dumps([tagline] if tagline else []),
        )
        # Genres from ld.genre (array of strings or single)
        g_raw = ld.get('genre') or d.get('genres') or []
        if isinstance(g_raw, str):
            g_raw = [g_raw]
        seen = set()
        for gname in g_raw:
            g = _normalize_genre(gname, name_to_genre)
            if g is not None and g.id not in seen:
                t.genres.append(g)
                seen.add(g.id)
        db.session.add(t)
        tt_to_title[tt_id] = (t, d)
    print(f"[seed] redirect_skipped={redirect_skipped}", flush=True)
    db.session.flush()

    # 5) Credits -----------------------------------------------------------
    for tt_id, (t, d) in tt_to_title.items():
        seen = set()
        # directors / writers / producers from credits dict
        for role_key, role in [('director', 'director'),
                                ('writer', 'writer'),
                                ('producer', 'producer'),
                                ('creator', 'writer')]:
            for pers in (d.get('credits') or {}).get(role_key) or []:
                nm = pers.get('nm_id')
                if not nm or (nm, role) in seen:
                    continue
                p = nm_to_person.get(nm)
                if p is None:
                    continue
                db.session.add(Credit(title_id=t.id, person_id=p.id,
                                      role=role, character='', billing_order=None))
                seen.add((nm, role))
        # cast
        for c in (d.get('cast') or [])[:15]:
            nm = c.get('nm_id')
            if not nm or (nm, 'actor') in seen:
                continue
            p = nm_to_person.get(nm)
            if p is None:
                continue
            db.session.add(Credit(title_id=t.id, person_id=p.id,
                                  role='actor',
                                  character=(c.get('character') or '')[:160],
                                  billing_order=c.get('billing')))
            seen.add((nm, 'actor'))
    db.session.flush()

    # 5b) Backfill known_for: pick 4 highest-voted titles per person ------
    for nm, p in nm_to_person.items():
        # Skip if scraper already produced ≥3 known_for entries
        try:
            existing = json.loads(p.known_for_json or '[]')
        except Exception:
            existing = []
        if len(existing) >= 3:
            continue
        their = [(c.title.num_votes or 0, c.title.tt_id) for c in p.credits if c.title]
        their.sort(reverse=True)
        seen, picked = set(), []
        for _, tt in their:
            if tt in seen: continue
            seen.add(tt); picked.append(tt)
            if len(picked) >= 4: break
        p.known_for_json = json.dumps(picked)
    db.session.flush()

    # 6) Benchmark users ---------------------------------------------------
    email_to_user = {}
    for spec in USERS_SPEC:
        u = User(email=spec['email'], name=spec['name'])
        u.set_password(spec['password'])
        db.session.add(u)
        email_to_user[spec['email']] = u
    db.session.flush()

    # 7) Featured review authors ------------------------------------------
    author_users = {}
    for _, author, *_ in SEED_REVIEWS:
        if author not in author_users:
            u = User(email=f'{author.lower()}@imdb-mirror.test', name=author)
            u.set_password('seeded-anon-' + author)
            db.session.add(u)
            author_users[author] = u
    db.session.flush()

    # 8) Seeded reviews ---------------------------------------------------
    for tt, author, headline, body, rating, helpful in SEED_REVIEWS:
        entry = tt_to_title.get(tt)
        if not entry:
            continue
        t = entry[0]
        u = author_users[author]
        r = Review(title_id=t.id, user_id=u.id, rating=rating,
                   headline=headline, body=body, helpful_count=helpful,
                   is_seed=True,
                   created_at=datetime(2024, 6, 1))
        db.session.add(r)

    # 9) Per-user state ---------------------------------------------------
    for email, st in USER_STATE.items():
        u = email_to_user.get(email)
        if u is None:
            continue
        for tt in st['watchlist']:
            entry = tt_to_title.get(tt)
            if not entry:
                continue
            db.session.add(WatchlistItem(user_id=u.id, title_id=entry[0].id,
                                         added_at=datetime(2024, 5, 1)))
        for tt, score in st['ratings']:
            entry = tt_to_title.get(tt)
            if not entry:
                continue
            db.session.add(UserRating(user_id=u.id, title_id=entry[0].id,
                                      rating=score,
                                      created_at=datetime(2024, 5, 5)))
        for tt, headline, body, rating in st['reviews']:
            entry = tt_to_title.get(tt)
            if not entry:
                continue
            db.session.add(Review(title_id=entry[0].id, user_id=u.id,
                                  rating=rating, headline=headline, body=body,
                                  helpful_count=42, is_seed=False,
                                  created_at=datetime(2024, 5, 10)))

    # 10) News ------------------------------------------------------------
    for headline, summary, source, pub, cat, related in NEWS:
        db.session.add(NewsItem(headline=headline, summary=summary,
                                source=source, published_at=pub,
                                category=cat, related_tt=related))

    db.session.commit()
