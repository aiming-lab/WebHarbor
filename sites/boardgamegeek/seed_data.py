"""Idempotent seed for BoardGameGeek mirror.

Loads sites/boardgamegeek/scraped_data/bgg.json (real BGG api.geekdo.com data)
into the SQLite DB. Two phases:

1. seed_database(db, app)       — games, designers, artists, publishers,
   categories, mechanics, families, ratings, reviews, forums, threads,
   posts, geeklists, geeklist items, hot list, real BGG users.

2. seed_benchmark_users(db, app, bcrypt) — 4 deterministic benchmark accounts
   alice_j / bob_c / carol_d / david_k with collections, ratings, plays,
   forum activity, and geeklists.

Byte-identical reset invariant: each function early-returns when the DB is
already populated. No commits unless it's the first run.
"""
import json
import os
import re
import shutil
import random
from datetime import datetime, timedelta, date


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'scraped_data', 'bgg.json')
EXTRAS_FILE = os.path.join(BASE_DIR, 'scraped_data', 'bgg_extras.json')
IMG_SRC = os.path.join(BASE_DIR, 'scraped_data', 'images')
IMG_DST = os.path.join(BASE_DIR, 'static', 'images')

MIRROR_NOW = datetime(2026, 5, 26, 12, 0, 0)

# Pinned deterministic RNG.
_R = random.Random(20260526)


def _slugify(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'item'


def _parse_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _parse_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _shift(seconds_back: int) -> datetime:
    return MIRROR_NOW - timedelta(seconds=seconds_back)


def _copy_images(_quiet: bool = False) -> None:
    if not os.path.isdir(IMG_SRC):
        return
    os.makedirs(IMG_DST, exist_ok=True)
    for fn in os.listdir(IMG_SRC):
        src = os.path.join(IMG_SRC, fn)
        dst = os.path.join(IMG_DST, fn)
        if os.path.exists(dst):
            continue
        try:
            shutil.copyfile(src, dst)
        except Exception as e:
            if not _quiet:
                print(f"  ! copy img {fn}: {e}")


# Hardcoded fallback so the site renders even when scraped_data is missing.
FALLBACK_GAMES = [
    {"bgg_id": 999001, "name": "Catan", "year": 1995, "minplayers": 3, "maxplayers": 4,
     "minplaytime": 60, "maxplaytime": 120, "minage": 10,
     "short_description": "Trade, build, settle the island of Catan.",
     "description_html": "<p>Catan is a tile-and-resource game where players build settlements, cities and roads on an island made from hex tiles.</p>",
     "categories": ["Economic", "Negotiation"],
     "mechanics": ["Dice Rolling", "Hexagon Grid", "Modular Board", "Network and Route Building", "Trading"],
     "designers": ["Klaus Teuber"],
     "publishers": ["Catan Studio"],
     "weight": 2.30, "avg": 7.13, "bayes": 7.10, "num_ratings": 110000, "rank": 415},
    {"bgg_id": 999002, "name": "Carcassonne", "year": 2000, "minplayers": 2, "maxplayers": 5,
     "minplaytime": 30, "maxplaytime": 45, "minage": 7,
     "short_description": "Build southern France by laying landscape tiles and placing meeples.",
     "description_html": "<p>Carcassonne is a tile-laying game in which players draw and place a tile with a piece of southern French landscape on it.</p>",
     "categories": ["Medieval", "Territory Building"],
     "mechanics": ["Area Majority / Influence", "Tile Placement"],
     "designers": ["Klaus-Jürgen Wrede"],
     "publishers": ["Z-Man Games"],
     "weight": 1.91, "avg": 7.40, "bayes": 7.39, "num_ratings": 120000, "rank": 199},
]


# Top-level (site-wide) forums shown on /forums.
SITEWIDE_FORUMS = [
    ('BoardGameGeek',        'announcements',  10, 'BGG announcements and site news.'),
    ('General Gaming',        'general',        20, 'All-around discussion of board games.'),
    ('Recommendations',       'general',        30, 'What should I play / buy?'),
    ('Strategy',              'strategy',       40, 'Game-specific strategy and tactics.'),
    ('Sessions',              'sessions',       50, 'Session reports from actual plays.'),
    ('Reviews',               'reviews',        60, 'In-depth game reviews.'),
    ('Variants & House Rules','variants',       70, 'Variants and house rules.'),
    ('Crowdfunding',          'crowdfunding',   80, 'Kickstarter, Gamefound, BackerKit.'),
    ('Solo Gaming',           'general',        90, 'Solo play, scenarios, AI bots.'),
    ('Two-Player Gaming',     'general',       100, 'Just the two of us.'),
    ('Trading & Marketplace', 'marketplace',   110, 'Buy, sell, trade.'),
    ('News',                  'news',          120, 'Industry news, new releases.'),
]


# Per-game forum subdivisions (created for every game).
PER_GAME_FORUMS = [
    ('General',         'general',     10),
    ('Reviews',         'reviews',     20),
    ('Strategy',        'strategy',    30),
    ('Sessions',        'sessions',    40),
    ('Rules',           'rules',       50),
    ('Variants',        'variants',    60),
    ('Crowdfunding',    'crowdfunding', 70),
]


SAMPLE_THREAD_TITLES = [
    'First impressions after 10 plays',
    'Quick reference card (PDF)',
    'Solo variant — works surprisingly well',
    'Question about the end-game scoring',
    'Box insert recommendations?',
    'How do you handle player elimination?',
    'Expansion buying guide',
    'Best at 3 or 4 players?',
    'Critical hit on the language dependence',
    'New player struggling — any tips?',
    'Late-game pacing problem',
    'Spoiler-free review',
    'Comparison with other titles in the genre',
    'Errata in the rulebook (printing 2)',
    'Heavy hand of the leader — fix or feature?',
]


SAMPLE_POST_BODIES = [
    "We just wrapped our 6th play and it keeps getting better — the early-game decisions matter more than I thought on my first run.",
    "I struggled with this in my first session, then realized I was completely missing the cascade in the middle phase. Once I locked that in, things clicked.",
    "Played at 4P last night and the downtime was noticeable, but the table talk made up for it. Probably want to stick to 3P for the heavier strategy sessions.",
    "Has anyone tried the variant from the rulebook appendix? Curious whether it shortens the game or just adds complexity.",
    "The art and component quality are a huge step up from the previous edition. The new tokens are easier to grip.",
    "I prefer this over the older sequel for one reason: the action economy feels less swingy.",
    "I lost track of how many times the leader pulled away in the final round. Anyone else find catch-up mechanisms too weak here?",
    "Bought a player aid PDF from the Files section — game flowed much faster after.",
    "Solo with the bot is great. Beat me 3 of 5 games — calibration feels right.",
    "Heavy on table presence but the upkeep is minimal once you internalize the symbols.",
]


SAMPLE_REVIEW_BODIES = [
    "<p>I came in expecting a heavy puzzle and got one — but also surprised by how much the table talk shapes my decisions. After 12 plays it stays fresh because every game pushes different paths.</p>",
    "<p>The first play felt overwhelming. By the third, the design clicked: each phase has one or two pivotal moments, and reading the table during them is everything.</p>",
    "<p>Components are gorgeous. Iconography mostly self-explanatory after a single play, though one or two ambiguous symbols send me back to the rulebook.</p>",
    "<p>For its weight class this delivers — the late-game tension is exactly right and player interaction never feels token. Highly recommend for groups who don't mind 90 minutes.</p>",
    "<p>The catch-up mechanism keeps the leader honest. Score spreads usually finish within 10 points which makes the last round meaningful.</p>",
    "<p>Hits the table because it's quick to teach, but rewards repeat play. I keep finding new angles 20 plays in.</p>",
]


def _build_fallback_data():
    """Convert the small FALLBACK_GAMES table into the same shape as bgg.json."""
    items = {}
    dyn = {}
    top_games = []
    for i, g in enumerate(FALLBACK_GAMES):
        oid = str(g['bgg_id'])
        links = {
            'boardgamedesigner': [{'objectid': 90000 + j, 'name': n}
                                  for j, n in enumerate(g.get('designers', []))],
            'boardgamepublisher': [{'objectid': 91000 + j, 'name': n}
                                  for j, n in enumerate(g.get('publishers', []))],
            'boardgamecategory': [{'objectid': 92000 + j, 'name': n}
                                  for j, n in enumerate(g.get('categories', []))],
            'boardgamemechanic': [{'objectid': 93000 + j, 'name': n}
                                  for j, n in enumerate(g.get('mechanics', []))],
        }
        items[oid] = {'item': {
            'objectid': g['bgg_id'], 'name': g['name'],
            'yearpublished': g['year'], 'minplayers': g['minplayers'],
            'maxplayers': g['maxplayers'], 'minplaytime': g['minplaytime'],
            'maxplaytime': g['maxplaytime'], 'minage': g['minage'],
            'short_description': g['short_description'],
            'description': g['description_html'],
            'subtype': 'boardgame', 'links': links,
        }}
        dyn[oid] = {'item': {
            'rankinfo': [{'rankobjectid': 1, 'rank': str(g['rank']),
                          'baverage': str(g['bayes'])}],
            'polls': {'boardgameweight': {'averageweight': g['weight'], 'totalvotes': 100}},
            'stats': {'usersrated': g['num_ratings'], 'average': g['avg'],
                      'bayesaverage': g['bayes'], 'owned': g['num_ratings'] // 2,
                      'wishing': g['num_ratings'] // 10, 'comments': g['num_ratings'] // 5},
        }}
        top_games.append({'objectid': str(g['bgg_id']), 'rank': str(g['rank']),
                          'name': g['name'], 'year': str(g['year']),
                          'thumb': '', 'geek_rating': str(g['bayes']),
                          'avg_rating': str(g['avg']), 'num_voters': str(g['num_ratings'])})
    return {'top_games': top_games, 'items': items, 'dyn': dyn,
            'reviews': {}, 'threads': {}, 'hot': [], 'users': {}, 'covers': {}}



# ----- main seed -----

def seed_database(db, app):
    """Idempotent: returns early if any games already exist."""
    from app import (User, Person, Publisher, Category, Mechanic, Family, Game,
                     GameLink, Rating, Collection, Play, Forum, Thread, Post,
                     GeekList, GeekListItem)
    if Game.query.count() > 0:
        return

    print('[bgg-seed] loading scraped data…')
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
    else:
        print(f'  ! {DATA_FILE} missing — using built-in fallback (~2 games)')
        data = _build_fallback_data()

    # Optional: expansion + low-rating augmentation pass (scrape_extras.py).
    extras = None
    if os.path.exists(EXTRAS_FILE):
        with open(EXTRAS_FILE) as f:
            extras = json.load(f)
        print(f'  + extras: {len(extras.get("exp_items", {}))} expansions, '
              f'{sum(len(v) for v in extras.get("low_reviews", {}).values())} low ratings')

        # Merge expansion games into the items/dyn/covers maps so the existing
        # seed loop creates them as first-class Game rows (subtype=expansion).
        merged_items = dict(data.get('items') or {})
        merged_dyn = dict(data.get('dyn') or {})
        merged_covers = dict(data.get('covers') or {})
        for oid, payload in (extras.get('exp_items') or {}).items():
            if oid in merged_items:
                continue
            merged_items[oid] = payload
        for oid, payload in (extras.get('exp_dyn') or {}).items():
            if oid in merged_dyn:
                continue
            merged_dyn[oid] = payload
        for oid, payload in (extras.get('exp_covers') or {}).items():
            merged_covers.setdefault(oid, payload)
        data['items'] = merged_items
        data['dyn'] = merged_dyn
        data['covers'] = merged_covers

        # Make sure every base game's boardgameexpansion link includes the
        # expansion ids we discovered (the first-pass scrape only captured
        # what api.geekitems happened to return, sometimes truncated).
        for base_oid, ids in (extras.get('exp_ids_per_base') or {}).items():
            base_payload = merged_items.get(base_oid)
            if not base_payload:
                continue
            gi = base_payload.get('item') or {}
            links = gi.setdefault('links', {})
            existing = links.get('boardgameexpansion') or []
            existing_ids = {str(e.get('objectid')) for e in existing if e.get('objectid')}
            for x in ids:
                if x not in existing_ids:
                    name = ((merged_items.get(x) or {}).get('item') or {}).get('name') or f'Expansion {x}'
                    existing.append({'objectid': x, 'name': name})
                    existing_ids.add(x)
            links['boardgameexpansion'] = existing

        # Merge low ratings into the reviews map.
        merged_reviews = dict(data.get('reviews') or {})
        # Two sources: text-review-restricted asc sort (low_reviews) AND
        # un-restricted asc sort (low_ratings_only — actual 1-5 star raw ratings).
        for src_key in ('low_reviews', 'low_ratings_only'):
            for oid, low_list in (extras.get(src_key) or {}).items():
                base = merged_reviews.get(oid) or []
                seen_collids = {r.get('collid') for r in base if r.get('collid')}
                for rv in low_list:
                    if rv.get('collid') and rv['collid'] in seen_collids:
                        continue
                    base.append(rv)
                    if rv.get('collid'):
                        seen_collids.add(rv['collid'])
                merged_reviews[oid] = base
        data['reviews'] = merged_reviews

    _copy_images()

    # ----- 1. real users from scraped reviewers -----
    print('[bgg-seed] users…')
    users_by_name: dict[str, 'User'] = {}
    raw_users = data.get('users') or {}
    for uname, payload in raw_users.items():
        base = payload.get('base') or {}
        if not uname:
            continue
        u = User(
            username=uname,
            email=None,
            password_hash='!disabled',          # real BGG users are display-only
            real_name=f"{base.get('firstname','')} {base.get('lastname','')}".strip(),
            country=base.get('country') or '',
            state=base.get('state') or '',
            city=base.get('city') or '',
            isocountry=base.get('isocountry') or '',
            about='',
            joined_at=_parse_user_join_date(base.get('regdate')),
            last_login=MIRROR_NOW,
            geekgold=_R.randint(0, 5000),
            is_supporter=bool(base.get('supportYears')),
        )
        users_by_name[uname] = u
        db.session.add(u)
    db.session.flush()

    # ----- 2. games -----
    print('[bgg-seed] games + their people/categories/mechanics…')
    people_by_bgg: dict[int, 'Person'] = {}
    publishers_by_bgg: dict[int, 'Publisher'] = {}
    categories_by_bgg: dict[int, 'Category'] = {}
    mechanics_by_bgg: dict[int, 'Mechanic'] = {}
    families_by_bgg: dict[int, 'Family'] = {}
    games_by_bgg: dict[int, 'Game'] = {}

    def get_or_make(map_, model, bgg_id, name):
        bgg_id = _parse_int(bgg_id)
        if not bgg_id or not name:
            return None
        if bgg_id in map_:
            return map_[bgg_id]
        obj = model(bgg_id=bgg_id, name=name, slug=_slugify(name))
        map_[bgg_id] = obj
        db.session.add(obj)
        return obj

    top_rank_by_oid = {}
    for tg in (data.get('top_games') or []):
        oid = _parse_int(tg.get('objectid'))
        rk = _parse_int(tg.get('rank'))
        if oid and rk:
            top_rank_by_oid[oid] = rk

    items = data.get('items') or {}
    dyn = data.get('dyn') or {}
    covers = data.get('covers') or {}

    for oid_str, payload in items.items():
        gi = (payload or {}).get('item') or {}
        oid = _parse_int(gi.get('objectid') or oid_str)
        if not oid:
            continue
        name = gi.get('name') or 'Untitled'
        cover = (covers.get(oid_str) or {}).get('cover')
        thumb = (covers.get(oid_str) or {}).get('thumb')
        dyn_item = (dyn.get(oid_str) or {}).get('item') or {}
        stats = dyn_item.get('stats') or {}
        polls = dyn_item.get('polls') or {}

        # Weight / language dependence / age suggestion
        weight = 0.0
        weight_votes = 0
        bgw = polls.get('boardgameweight')
        if isinstance(bgw, dict):
            weight = _parse_float(bgw.get('averageweight'))
            weight_votes = _parse_int(bgw.get('totalvotes'))
        lang_dep = polls.get('languagedependence') or ''
        suggested_age = polls.get('playerage') or ''

        # Player count poll → "best" / "recommended"
        best_str = ''
        rec_str = ''
        upoll = polls.get('userplayers') or {}
        best_list = upoll.get('best') or []
        if isinstance(best_list, list) and best_list:
            bmin = best_list[0].get('min')
            bmax = best_list[0].get('max')
            best_str = f"{bmin}" if bmin == bmax else f"{bmin}–{bmax}"
        rec_list = upoll.get('recommended') or []
        if isinstance(rec_list, list) and rec_list:
            mins = sorted(set(_parse_int(p.get('min')) for p in rec_list))
            maxs = sorted(set(_parse_int(p.get('max')) for p in rec_list))
            if mins and maxs:
                rec_str = f"{min(mins)}–{max(maxs)}"

        rank_info = dyn_item.get('rankinfo') or []
        overall_rank = 0
        bayes = 0.0
        for ri in rank_info:
            if ri.get('rankobjectid') in (1, '1') or ri.get('prettyname') == 'Board Game Rank':
                r = ri.get('rank')
                if r and r != 'Not Ranked':
                    overall_rank = _parse_int(r)
                bayes = _parse_float(ri.get('baverage'))
                break
        if not overall_rank:
            overall_rank = top_rank_by_oid.get(oid, 0)

        avg = _parse_float(stats.get('average'))
        num_ratings = _parse_int(stats.get('usersrated'))
        num_owners = _parse_int(stats.get('owned'))
        num_wishing = _parse_int(stats.get('wishing'))
        num_comments = _parse_int(stats.get('comments'))

        g = Game(
            bgg_id=oid,
            name=name,
            slug=_slugify(name),
            subtype=(gi.get('subtype') or 'boardgame'),
            year_published=_parse_int(gi.get('yearpublished')),
            minplayers=_parse_int(gi.get('minplayers')),
            maxplayers=_parse_int(gi.get('maxplayers')),
            minplaytime=_parse_int(gi.get('minplaytime')),
            maxplaytime=_parse_int(gi.get('maxplaytime')),
            minage=_parse_int(gi.get('minage')),
            short_description=(gi.get('short_description') or '')[:8000],
            description_html=(gi.get('description') or '')[:60000],
            image_filename=cover or '',
            thumb_filename=thumb or '',
            avg_rating=avg,
            bayes_average=bayes,
            weight=weight,
            weight_votes=weight_votes,
            num_ratings=num_ratings,
            num_owners=num_owners,
            num_wishing=num_wishing,
            num_comments=num_comments,
            overall_rank=overall_rank,
            best_player_count=best_str,
            recommended_player_count=rec_str,
            suggested_age=suggested_age,
            language_dependence=lang_dep,
            featured=False,
        )
        db.session.add(g)
        games_by_bgg[oid] = g

    db.session.flush()
    print(f'  games: {len(games_by_bgg)}')

    # ----- people / publishers / categories / mechanics + m2m links -----
    expansion_links = []   # (game_bgg_id, other_bgg_id)
    integration_links = []
    for oid_str, payload in items.items():
        gi = (payload or {}).get('item') or {}
        oid = _parse_int(gi.get('objectid') or oid_str)
        g = games_by_bgg.get(oid)
        if not g:
            continue
        links = gi.get('links') or {}
        for entry in (links.get('boardgamedesigner') or []):
            p = get_or_make(people_by_bgg, Person, entry.get('objectid'), entry.get('name'))
            if p:
                g.designers.append(p)
        for entry in (links.get('boardgameartist') or []):
            p = get_or_make(people_by_bgg, Person, entry.get('objectid'), entry.get('name'))
            if p:
                g.artists.append(p)
        for entry in (links.get('boardgamepublisher') or []):
            p = get_or_make(publishers_by_bgg, Publisher, entry.get('objectid'), entry.get('name'))
            if p:
                g.publishers.append(p)
        for entry in (links.get('boardgamecategory') or []):
            c = get_or_make(categories_by_bgg, Category, entry.get('objectid'), entry.get('name'))
            if c:
                g.categories.append(c)
        for entry in (links.get('boardgamemechanic') or []):
            m = get_or_make(mechanics_by_bgg, Mechanic, entry.get('objectid'), entry.get('name'))
            if m:
                g.mechanics.append(m)
        for entry in (links.get('boardgamefamily') or []):
            f = get_or_make(families_by_bgg, Family, entry.get('objectid'), entry.get('name'))
            if f:
                g.families.append(f)
        for entry in (links.get('boardgameexpansion') or []):
            other_oid = _parse_int(entry.get('objectid'))
            if other_oid:
                expansion_links.append((oid, other_oid))
        for entry in (links.get('boardgameintegration') or []):
            other_oid = _parse_int(entry.get('objectid'))
            if other_oid:
                integration_links.append((oid, other_oid))

    db.session.flush()
    print(f'  designers/artists: {len(people_by_bgg)}  publishers: {len(publishers_by_bgg)}  '
          f'categories: {len(categories_by_bgg)}  mechanics: {len(mechanics_by_bgg)}')

    # ----- game-to-game links -----
    for (g_oid, o_oid) in expansion_links:
        g = games_by_bgg.get(g_oid)
        other = games_by_bgg.get(o_oid)
        if g and other:
            db.session.add(GameLink(game_id=g.id, other_id=other.id, kind='expansion'))
    for (g_oid, o_oid) in integration_links:
        g = games_by_bgg.get(g_oid)
        other = games_by_bgg.get(o_oid)
        if g and other:
            db.session.add(GameLink(game_id=g.id, other_id=other.id, kind='integration'))

    # ----- featured set from hot list (intersect with seeded games) -----
    hot = data.get('hot') or []
    featured = 0
    for h in hot[:50]:
        h_oid = _parse_int(h.get('objectid') or h.get('id'))
        g = games_by_bgg.get(h_oid)
        if g:
            g.featured = True
            featured += 1
    if featured == 0:
        # If hot list didn't intersect, just feature the top 20 by rank.
        for g in sorted(games_by_bgg.values(), key=lambda x: x.overall_rank or 99999)[:20]:
            g.featured = True
    db.session.flush()

    # ----- ratings + reviews from real users -----
    print('[bgg-seed] real ratings/reviews…')
    rating_count = 0
    review_count = 0
    for oid_str, revs in (data.get('reviews') or {}).items():
        oid = _parse_int(oid_str)
        g = games_by_bgg.get(oid)
        if not g or not revs:
            continue
        for rv in revs:
            uname = rv.get('username')
            if not uname:
                continue
            u = users_by_name.get(uname)
            if not u:
                # synthesize a stub real user
                u = User(
                    username=uname,
                    email=None,
                    password_hash='!disabled',
                    real_name='',
                    country=rv.get('country') or '',
                    joined_at=MIRROR_NOW - timedelta(days=_R.randint(60, 4000)),
                    last_login=MIRROR_NOW,
                    geekgold=_R.randint(0, 200),
                )
                users_by_name[uname] = u
                db.session.add(u)
                db.session.flush()
            existing = Rating.query.filter_by(user_id=u.id, game_id=g.id).first()
            if existing:
                continue
            comment = rv.get('comment_html') or ''
            try:
                value = float(rv.get('rating')) if rv.get('rating') is not None else None
            except (TypeError, ValueError):
                value = None
            if value is None:
                continue
            tstamp = _parse_review_timestamp(rv.get('tstamp'))
            r = Rating(user_id=u.id, game_id=g.id, value=value,
                       review_html=comment, created_at=tstamp,
                       num_thumbs=_R.randint(0, 25) if comment else _R.randint(0, 3))
            db.session.add(r)
            rating_count += 1
            if comment:
                review_count += 1
    db.session.flush()
    print(f'  ratings: {rating_count}  text reviews: {review_count}')

    # ----- forums (site-wide + per-game) -----
    print('[bgg-seed] forums + threads + posts…')
    forums_created = []
    for title, section, sort, desc in SITEWIDE_FORUMS:
        f = Forum(title=title, section=section, sort_order=sort,
                  description=desc, game_id=None, num_threads=0, num_posts=0)
        db.session.add(f)
        forums_created.append(f)

    for g in games_by_bgg.values():
        # Only base games get a full per-game forum.  Expansions don't —
        # real BGG also keeps expansion discussion in the parent game's forum.
        if g.subtype != 'boardgame':
            continue
        for title, section, sort in PER_GAME_FORUMS:
            f = Forum(title=title, section=section, sort_order=sort,
                      description=f'{title} discussion for {g.name}.',
                      game_id=g.id, num_threads=0, num_posts=0)
            db.session.add(f)
    db.session.flush()
    print(f'  forums: {Forum.query.count()}')

    # Threads from real BGG thread headers (when available)
    thread_count = 0
    post_count = 0
    raw_threads = data.get('threads') or {}
    user_pool = [u for u in users_by_name.values() if u.password_hash == '!disabled']
    if not user_pool:
        user_pool = list(users_by_name.values())

    def _author_for_index(i: int):
        return user_pool[i % len(user_pool)] if user_pool else None

    for oid_str, headers in raw_threads.items():
        oid = _parse_int(oid_str)
        g = games_by_bgg.get(oid)
        if not g or not headers:
            continue
        # Pick a per-game forum at random (deterministic by thread index)
        forums_for_game = Forum.query.filter_by(game_id=g.id).all()
        if not forums_for_game:
            continue
        for ti, h in enumerate(headers[:8]):
            subject = (h.get('subject') or h.get('title') or
                       SAMPLE_THREAD_TITLES[ti % len(SAMPLE_THREAD_TITLES)])
            subject = subject.strip()[:300]
            fobj = forums_for_game[ti % len(forums_for_game)]
            author = _author_for_index(oid + ti)
            if not author:
                continue
            tcreated = MIRROR_NOW - timedelta(days=_R.randint(2, 1400),
                                              hours=_R.randint(0, 23))
            n_posts = max(1, _parse_int(h.get('numposts') or h.get('numreplies')) or
                          _R.randint(2, 30))
            n_posts = min(n_posts, 30)
            t = Thread(forum_id=fobj.id, subject=subject, author_id=author.id,
                       is_pinned=(ti == 0 and _R.random() < 0.15),
                       is_hot=(n_posts >= 15),
                       num_posts=n_posts, num_views=n_posts * _R.randint(8, 50),
                       created_at=tcreated, last_post_at=tcreated + timedelta(hours=n_posts * 2))
            db.session.add(t)
            db.session.flush()
            thread_count += 1
            fobj.num_threads = (fobj.num_threads or 0) + 1
            fobj.num_posts = (fobj.num_posts or 0) + n_posts
            for pi in range(n_posts):
                pauthor = _author_for_index(oid + ti + pi * 7) or author
                body = SAMPLE_POST_BODIES[(oid + ti + pi) % len(SAMPLE_POST_BODIES)]
                body_html = f'<p>{body}</p>'
                # Sprinkle in a quoted previous post for variety
                if pi > 0 and pi % 3 == 0:
                    prev = SAMPLE_POST_BODIES[(oid + ti + pi - 1) % len(SAMPLE_POST_BODIES)]
                    body_html = f'<blockquote>{prev[:120]}…</blockquote>' + body_html
                pcreated = tcreated + timedelta(hours=pi * 2 + _R.randint(0, 4))
                p = Post(thread_id=t.id, author_id=pauthor.id,
                         body_html=body_html, created_at=pcreated,
                         thumbs=_R.randint(0, 8))
                db.session.add(p)
                post_count += 1
            if thread_count % 200 == 0:
                db.session.flush()

    db.session.flush()
    print(f'  threads: {thread_count}  posts: {post_count}')

    # ----- GeekLists (synthesized from real games) -----
    print('[bgg-seed] geeklists…')
    list_count = _seed_geeklists(db, games_by_bgg, users_by_name, _R)
    print(f'  geeklists: {list_count}')

    db.session.commit()
    print('[bgg-seed] done.')


def _seed_geeklists(db, games_by_bgg, users_by_name, R):
    from app import GeekList, GeekListItem

    games_sorted = sorted(games_by_bgg.values(), key=lambda g: g.overall_rank or 99999)
    user_pool = list(users_by_name.values())
    if not user_pool:
        return 0

    LIST_DEFS = [
        ('Top 50 Heaviest Games of the Last Decade',
         lambda g: g.year_published >= 2014 and g.weight >= 3.5,
         lambda g: (-g.weight, g.overall_rank or 99999),
         '<p>The crunchiest cardboard-and-chrome experiences released since 2014. '
         'Ranked by community weight rating, descending.</p>'),
        ('Best Two-Player Only Games',
         lambda g: g.minplayers == 2 and g.maxplayers == 2,
         lambda g: (g.overall_rank or 99999,),
         '<p>Hand-curated list of games designed exclusively for two players. '
         'No "you can play it solo" cop-outs.</p>'),
        ('Sub-30-Minute Fillers I Will Defend',
         lambda g: g.maxplaytime > 0 and g.maxplaytime <= 30,
         lambda g: (g.overall_rank or 99999,),
         '<p>Quick games that still pack a punch. Perfect for the last hour of game night.</p>'),
        ('Gateway Games for Non-Gamers',
         lambda g: g.weight > 0 and g.weight < 2.0 and (g.overall_rank or 99999) < 800,
         lambda g: (g.overall_rank or 99999,),
         '<p>Low-weight modern designs that have introduced more people to the hobby '
         'than any Monopoly Special Edition ever did.</p>'),
        ('Solo Mode That Actually Earns the SKU',
         lambda g: 'Solitaire Game' in {c.name for c in g.categories} or g.minplayers == 1,
         lambda g: (g.overall_rank or 99999,),
         '<p>Games with bolted-on solo modes are forgivable. These games are designed with '
         'the lone player in mind from the start.</p>'),
        ('Wargame Newcomers Start Here',
         lambda g: 'Wargame' in {c.name for c in g.categories} and (g.overall_rank or 99999) < 2000,
         lambda g: (g.overall_rank or 99999,),
         '<p>Light to medium wargames that won\'t scare off the rest of your group.</p>'),
        ('Best Cooperative Games',
         lambda g: 'Cooperative Game' in {m.name for m in g.mechanics},
         lambda g: (g.overall_rank or 99999,),
         '<p>Win together or lose together — the best titles in the co-op space.</p>'),
        ('Deckbuilders That Deserve a Place at the Table',
         lambda g: 'Deck, Bag, and Pool Building' in {m.name for m in g.mechanics},
         lambda g: (g.overall_rank or 99999,),
         '<p>The deckbuilding genre keeps evolving. These are the standouts beyond the '
         'classics.</p>'),
        ('Hidden Gems Under 5000 Owners',
         lambda g: 0 < g.num_owners < 5000 and g.bayes_average >= 7.0,
         lambda g: (-g.bayes_average, g.overall_rank or 99999),
         '<p>Underrated games that fly under the radar. Help me make these owned numbers go up.</p>'),
        ('Designer Spotlight: Vital Lacerda',
         lambda g: any('lacerda' in p.name.lower() for p in g.designers),
         lambda g: (g.overall_rank or 99999,),
         '<p>Notes and rankings for every Lacerda title.</p>'),
        ('Award Winners 2020-2025',
         lambda g: 2020 <= g.year_published <= 2025 and (g.overall_rank or 99999) < 500,
         lambda g: (-g.year_published, g.overall_rank or 99999),
         '<p>Spiel des Jahres, Kennerspiel, and Golden Geek winners of the last five years.</p>'),
        ('My Heavy Euro Top 25',
         lambda g: g.weight >= 4.0,
         lambda g: (-g.bayes_average, g.overall_rank or 99999),
         '<p>If brain-burn was a food group I would die of it.</p>'),
    ]

    n_created = 0
    for li, (title, predicate, sort_key, desc) in enumerate(LIST_DEFS):
        author = user_pool[li % len(user_pool)]
        l = GeekList(title=title,
                     description_html=desc,
                     author_id=author.id,
                     created_at=MIRROR_NOW - timedelta(days=R.randint(15, 1200)),
                     num_items=0,
                     num_thumbs=R.randint(8, 480))
        db.session.add(l)
        db.session.flush()
        n_created += 1
        # Find matching games
        candidates = [g for g in games_sorted if g.overall_rank and predicate(g)]
        candidates.sort(key=sort_key)
        items = candidates[:25]
        for pos, g in enumerate(items, start=1):
            comment_body = R.choice([
                f"<p>{g.name} earns its spot because it nails the central design tension.</p>",
                f"<p>Brought {g.name} to game night last week and it played beautifully — added at #{pos}.</p>",
                f"<p>{g.name} keeps finding its way back to the table. Hard to argue with that.</p>",
                f"<p>Hugely underplayed in our group. {g.name} deserves more love.</p>",
                f"<p>The decision space in {g.name} is wider than the rulebook page count suggests.</p>",
            ])
            db.session.add(GeekListItem(
                list_id=l.id, game_id=g.id,
                body_html=comment_body, position=pos,
                num_thumbs=R.randint(0, 40),
            ))
        l.num_items = len(items)
    db.session.flush()
    return n_created


def _parse_user_join_date(s: str | None) -> datetime:
    if not s:
        return MIRROR_NOW - timedelta(days=_R.randint(365, 8000))
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except (ValueError, TypeError):
        return MIRROR_NOW - timedelta(days=_R.randint(365, 8000))


def _parse_review_timestamp(s: str | None) -> datetime:
    if not s:
        return MIRROR_NOW - timedelta(days=_R.randint(30, 3000))
    try:
        return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return MIRROR_NOW - timedelta(days=_R.randint(30, 3000))


# ----- benchmark users (deterministic) -----

BENCH_USERS = [
    {'username': 'alice_j', 'email': 'alice.j@test.com', 'real_name': 'Alice Johnson',
     'country': 'United States', 'state': 'California', 'city': 'Berkeley',
     'about': 'Heavy euro fan. Lacerda completist. Currently obsessed with Brass: Birmingham.'},
    {'username': 'bob_c', 'email': 'bob.c@test.com', 'real_name': 'Bob Chen',
     'country': 'Canada', 'state': 'British Columbia', 'city': 'Vancouver',
     'about': 'Cooperative games and dungeon crawlers. Gloomhaven scenario 95 grinder.'},
    {'username': 'carol_d', 'email': 'carol.d@test.com', 'real_name': 'Carol Davis',
     'country': 'United Kingdom', 'state': 'Greater London', 'city': 'London',
     'about': 'Two-player only. Race for the Galaxy until the heat-death of the universe.'},
    {'username': 'david_k', 'email': 'david.k@test.com', 'real_name': 'David Kim',
     'country': 'South Korea', 'state': 'Seoul', 'city': 'Seoul',
     'about': 'Wargames and economic sims. Will not apologise for owning every COIN game.'},
]
BENCH_PASSWORD = 'TestPass123!'


def seed_benchmark_users(db, app, bcrypt):
    from app import (User, Game, Rating, Collection, Play, GeekList,
                     GeekListItem, Thread, Post, Forum)
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    print('[bgg-seed] benchmark users…')
    created = []
    for u in BENCH_USERS:
        existing = User.query.filter_by(username=u['username']).first()
        if existing:
            # Real BGG dataset already has someone by that handle — promote it.
            existing.email = u['email']
            existing.password_hash = bcrypt.generate_password_hash(BENCH_PASSWORD).decode()
            existing.real_name = u['real_name']
            existing.country = u['country']
            existing.state = u['state']
            existing.city = u['city']
            existing.about = u['about']
            created.append(existing)
            continue
        new = User(username=u['username'], email=u['email'],
                   password_hash=bcrypt.generate_password_hash(BENCH_PASSWORD).decode(),
                   real_name=u['real_name'], country=u['country'],
                   state=u['state'], city=u['city'], about=u['about'],
                   joined_at=MIRROR_NOW - timedelta(days=3*365 + 100),
                   last_login=MIRROR_NOW, geekgold=120, is_supporter=True)
        db.session.add(new)
        created.append(new)
    db.session.flush()

    # Map of user → preferred game categories/mechanics, used to pick their collection
    profiles = {
        'alice_j': {
            'weight_range': (3.5, 5.0),
            'preferred_mechanics': {'Worker Placement', 'Network and Route Building',
                                     'Income', 'Hand Management'},
            'preferred_categories': {'Economic', 'Industry / Manufacturing'},
        },
        'bob_c': {
            'weight_range': (2.5, 4.5),
            'preferred_mechanics': {'Cooperative Game', 'Variable Player Powers',
                                     'Scenario / Mission / Campaign Game'},
            'preferred_categories': {'Adventure', 'Exploration', 'Fantasy', 'Fighting'},
        },
        'carol_d': {
            'weight_range': (1.5, 3.5),
            'preferred_mechanics': set(),
            'preferred_categories': set(),
            'players_must_include_two': True,
        },
        'david_k': {
            'weight_range': (3.5, 5.0),
            'preferred_mechanics': {'Area Movement', 'Hexagon Grid', 'Variable Player Powers',
                                     'Action Points', 'Simultaneous Action Selection'},
            'preferred_categories': {'Wargame', 'Civilization', 'World War II'},
        },
    }

    # Helper to pick N games for each user, scored by their preferences.
    def pick_games_for(uname: str, n: int = 25):
        prof = profiles.get(uname, {})
        candidates = []
        for g in Game.query.filter(Game.overall_rank > 0,
                                    Game.overall_rank <= 800).all():
            cats = {c.name for c in g.categories}
            mechs = {m.name for m in g.mechanics}
            score = 0.0
            if prof.get('weight_range'):
                wmin, wmax = prof['weight_range']
                if wmin <= (g.weight or 0) <= wmax:
                    score += 3
            score += len(cats & prof.get('preferred_categories', set())) * 2
            score += len(mechs & prof.get('preferred_mechanics', set())) * 2
            if prof.get('players_must_include_two'):
                if g.minplayers <= 2 <= g.maxplayers:
                    score += 2
            # Slight preference for higher-ranked
            score += max(0, (800 - g.overall_rank) / 800) * 1.5
            if score > 0:
                candidates.append((g, score))
        candidates.sort(key=lambda x: (-x[1], x[0].overall_rank))
        return [c[0] for c in candidates[:n]]

    # Pin choices so the seed is deterministic.
    R = random.Random(99887766)

    # 1. Collections + ratings
    for u in created:
        picks = pick_games_for(u.username, n=25)
        if not picks:
            # Fall back to the top ranked games
            picks = Game.query.filter(Game.overall_rank > 0) \
                .order_by(Game.overall_rank).limit(25).all()
        for i, g in enumerate(picks):
            own = i < 18                # first 18 owned
            wish = (18 <= i < 22)       # next 4 on wishlist
            wantbuy = (22 <= i < 24)    # 2 want-to-buy
            wantplay = (i == 24)        # last 1 want-to-play
            e = Collection(user_id=u.id, game_id=g.id,
                           own=own, wishlist=wish, want_to_buy=wantbuy,
                           want_to_play=wantplay,
                           wishlist_priority=(R.randint(1, 5) if wish else 0),
                           comment=R.choice([
                               '', '', '',  # most blank
                               'Shelf of shame for now.',
                               'Sleeved and ready for the next session.',
                               'Trade me if you want one.',
                               'KS edition with all stretch goals.',
                           ]),
                           acquired_on=(MIRROR_NOW - timedelta(days=R.randint(40, 1800))).strftime('%Y-%m-%d') if own else '',
                           updated_at=MIRROR_NOW - timedelta(days=R.randint(1, 200)))
            db.session.add(e)
            # Owned games get a personal rating
            if own:
                base = 7.5 + R.uniform(-1.5, 2.0)
                if g.bayes_average:
                    base = 0.6 * base + 0.4 * g.bayes_average
                value = round(min(10.0, max(3.0, base)) * 2) / 2  # half-step
                review = ''
                # First 5 owned per user become full text reviews
                if i < 5:
                    review = R.choice([
                        f"<p>{g.name} has stayed in my regular rotation for years. The decision points always feel meaningful, and the table arc lands on a tight finish.</p>",
                        f"<p>I almost sold {g.name} after my second play. Then a friend insisted on one more game and I finally saw the shape of it. Now it's a top-10 keeper.</p>",
                        f"<p>{g.name} is the game I pull out when I want to win an argument about what 'elegant' means in the hobby.</p>",
                        f"<p>The components in {g.name} are excellent, but what surprises me each play is how different the path-to-victory feels. Highly recommended for the right group.</p>",
                    ])
                rt = Rating(user_id=u.id, game_id=g.id, value=value,
                            review_html=review,
                            created_at=MIRROR_NOW - timedelta(days=R.randint(10, 900)),
                            num_thumbs=R.randint(0, 30) if review else 0)
                db.session.add(rt)

    db.session.flush()

    # 2. Plays log — last 60 days of plays per user
    for u in created:
        owned = Collection.query.filter_by(user_id=u.id, own=True).all()
        owned_games = [db.session.get(Game, e.game_id) for e in owned]
        owned_games = [g for g in owned_games if g]
        if not owned_games:
            continue
        for play_i in range(R.randint(10, 22)):
            g = R.choice(owned_games)
            played = (MIRROR_NOW - timedelta(days=R.randint(1, 90))).date()
            db.session.add(Play(user_id=u.id, game_id=g.id, played_on=played,
                                quantity=1,
                                length_minutes=(g.minplaytime + g.maxplaytime) // 2 if g.maxplaytime else 60,
                                num_players=max(g.minplayers,
                                                R.randint(g.minplayers, max(g.minplayers, g.maxplayers))),
                                location=R.choice(['Home', 'Friend\'s House', 'Game Cafe',
                                                    'Convention', 'FLGS']),
                                comments=R.choice(['',
                                                    'Tight finish, decided on the last turn.',
                                                    'Tried a new strategy — paid off.',
                                                    'Solo mode this time, lost narrowly.',
                                                    'Taught two new players, they want to play again.'])))

    # 3. Each benchmark user authors one GeekList
    bench_lists = [
        ('alice_j', 'Alice\'s Lacerda Project',
         '<p>Working through every Vital Lacerda title in publication order. Half ranking, half therapy.</p>',
         lambda g: any('lacerda' in p.name.lower() for p in g.designers) or g.weight >= 4.0,
         12),
        ('bob_c', 'Bob\'s Co-op Rotation',
         '<p>Cooperative games currently in our weekly rotation.</p>',
         lambda g: 'Cooperative Game' in {m.name for m in g.mechanics},
         12),
        ('carol_d', 'Carol\'s Two-Player-Only Shelf',
         '<p>Designed for two. No "scales to 5" compromises. The shelf as it stands today.</p>',
         lambda g: g.minplayers == 2 and g.maxplayers == 2,
         10),
        ('david_k', 'David\'s COIN Lectern',
         '<p>Every entry in the GMT COIN series I own, ranked by how often it hits the table.</p>',
         lambda g: 'Wargame' in {c.name for c in g.categories} and g.weight >= 3.5,
         10),
    ]
    for uname, title, desc, predicate, n in bench_lists:
        u = User.query.filter_by(username=uname).first()
        if not u:
            continue
        candidates = [g for g in Game.query.all() if g.overall_rank and predicate(g)]
        candidates.sort(key=lambda g: g.overall_rank or 99999)
        picks = candidates[:n]
        if not picks:
            continue
        gl = GeekList(title=title, description_html=desc,
                      author_id=u.id,
                      created_at=MIRROR_NOW - timedelta(days=R.randint(40, 800)),
                      num_items=len(picks),
                      num_thumbs=R.randint(20, 250))
        db.session.add(gl)
        db.session.flush()
        for pos, g in enumerate(picks, start=1):
            db.session.add(GeekListItem(
                list_id=gl.id, game_id=g.id, position=pos,
                body_html=f'<p>{u.real_name.split()[0]}\'s note: <em>{g.name}</em> belongs here because it nails the brief.</p>',
                num_thumbs=R.randint(0, 30),
            ))

    db.session.flush()

    # 4. Forum activity — each user starts one thread + replies to a few others
    general_forum = Forum.query.filter_by(title='General Gaming').first()
    rec_forum = Forum.query.filter_by(title='Recommendations').first()
    target_forums = [f for f in [general_forum, rec_forum] if f]
    for u, opening in zip(created, [
        ('What\'s your highest-rated 2024 release?',
         '<p>Yearly thread. Mine is Cyclades: Legendary Edition, against my own expectations.</p>'),
        ('Looking for co-op suggestions that AREN\'T Pandemic / Spirit Island',
         '<p>I love both, but the group has played them to death. What else should be in the conversation?</p>'),
        ('Best 2-player only deckbuilder?',
         '<p>I have Star Realms and 7 Wonders Duel. Looking for one more — preferably under 45 minutes.</p>'),
        ('Wargames at 2 players in under 3 hours',
         '<p>Title says it all. Block wargames welcome.</p>'),
    ]):
        if not target_forums:
            break
        fobj = target_forums[(u.id) % len(target_forums)]
        t = Thread(forum_id=fobj.id, subject=opening[0], author_id=u.id,
                   num_posts=1, num_views=R.randint(60, 800),
                   created_at=MIRROR_NOW - timedelta(days=R.randint(7, 120)),
                   last_post_at=MIRROR_NOW - timedelta(days=R.randint(1, 6)))
        db.session.add(t)
        db.session.flush()
        fobj.num_threads = (fobj.num_threads or 0) + 1
        fobj.num_posts = (fobj.num_posts or 0) + 1
        db.session.add(Post(thread_id=t.id, author_id=u.id,
                            body_html=opening[1],
                            created_at=t.created_at, thumbs=R.randint(0, 18)))

    db.session.commit()
    print(f'[bgg-seed] benchmark seed done. (users={len(created)})')
