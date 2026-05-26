"""Idempotent seed loader for the Discogs mirror.

Pulls real catalog metadata from scraped_data/releases.json (Discogs API)
and scraped_data/mb_releases.json (MusicBrainz), plus Wikipedia
descriptions/cover URLs from scraped_data/wikipedia.json. Generates a
benchmark community on top — users, ratings, reviews, collections,
wantlists, lists, marketplace listings, forums.

Every seed_*() function is gated by an existence check so it is a no-op
on a populated DB. That is the contract that keeps /reset/discogs
byte-identical.
"""
import json
import os
import random
import re
import unicodedata
from datetime import datetime, timedelta

from app import (
    app, db, bcrypt,
    User, Artist, Label, Genre, Style, Format, Master, Release, Track,
    Rating, Review, CollectionItem, WantlistItem, List, ListItem,
    Listing, Forum, Thread, Post,
    release_genres, release_styles, release_labels, release_formats,
    COLLECTION_FOLDERS, GRADES,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPED = os.path.join(BASE_DIR, "scraped_data")

# Pin a reference date so re-seeding from scraped_data/ is deterministic
# (NOW would otherwise make the produced DB non-reproducible
# and break byte-identical reset across rebuilds).
NOW = datetime(2026, 5, 26, 0, 0, 0)


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "x"


def _load_json(name):
    p = os.path.join(SCRAPED, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        print(f"[seed] failed to read {name}: {e}")
        return None


# ──────────────────────────────────────────────
# 1. Genres / Styles / Formats taxonomy
# ──────────────────────────────────────────────

CANONICAL_GENRES = [
    "Rock", "Electronic", "Pop", "Hip Hop", "Jazz", "Funk / Soul", "Classical",
    "Reggae", "Blues", "Folk, World, & Country", "Latin", "Non-Music",
    "Stage & Screen", "Brass & Military", "Children's",
]

CANONICAL_FORMATS = [
    "Vinyl", "CD", "Cassette", "8-Track", "Reel-To-Reel", "DVD", "Box Set",
    "LP", "EP", "Single", "12\"", "7\"", "10\"",
    "Album", "Compilation", "Reissue", "Remastered", "Mono", "Stereo",
    "Limited Edition", "Promo", "Test Pressing", "Picture Disc", "Coloured Vinyl",
    "Maxi-Single", "Mini-Album", "Digital", "FLAC", "MP3", "Shellac", "File", "Acetate",
]


# ──────────────────────────────────────────────
# 2. Releases (catalogue)
# ──────────────────────────────────────────────

def _get_or_create_artist(name, cache):
    name = (name or "Unknown").strip() or "Unknown"
    if name in cache:
        return cache[name]
    base_slug = slugify(name)
    slug = base_slug
    i = 1
    while Artist.query.filter_by(slug=slug).first() is not None:
        i += 1
        slug = f"{base_slug}-{i}"
    a = Artist(name=name[:200], slug=slug[:220])
    db.session.add(a)
    db.session.flush()
    cache[name] = a
    return a


def _get_or_create_label(name, cache):
    name = (name or "").strip()
    if not name or name in cache:
        return cache.get(name)
    base_slug = slugify(name)
    slug = base_slug
    i = 1
    while Label.query.filter_by(slug=slug).first() is not None:
        i += 1
        slug = f"{base_slug}-{i}"
    l = Label(name=name[:200], slug=slug[:220])
    db.session.add(l)
    db.session.flush()
    cache[name] = l
    return l


def _get_or_create_named(model, name, cache):
    name = (name or "").strip()
    if not name:
        return None
    if name in cache:
        return cache[name]
    base_slug = slugify(name)
    slug = base_slug
    i = 1
    while model.query.filter_by(slug=slug).first() is not None:
        i += 1
        slug = f"{base_slug}-{i}"
    obj = model(name=name[:80], slug=slug[:80])
    db.session.add(obj)
    db.session.flush()
    cache[name] = obj
    return obj


def _build_tracklist_for(release_id, n=8, base_title=""):
    """Plausible-looking placeholder tracklist when we have none."""
    rng = random.Random(release_id * 13 + 7)
    tracks = []
    for i in range(1, n + 1):
        side = "A" if i <= n / 2 else "B"
        pos = f"{side}{i if i <= n/2 else i - int(n/2)}"
        title = f"Track {i}"
        dur_sec = rng.randint(150, 360)
        tracks.append((pos, title, f"{dur_sec//60}:{dur_sec%60:02d}"))
    return tracks


def seed_taxonomy():
    if Genre.query.count() > 0:
        return
    print("[seed] taxonomy (genres/formats)")
    for n in CANONICAL_GENRES:
        db.session.add(Genre(name=n, slug=slugify(n)))
    for n in CANONICAL_FORMATS:
        db.session.add(Format(name=n, slug=slugify(n)))
    db.session.commit()


def seed_forums():
    if Forum.query.count() > 0:
        return
    print("[seed] forums")
    forums = [
        ("Discogs Updates", "discogs-updates", "Announcements from the Discogs team."),
        ("General Discussion", "general", "Talk about anything music-related."),
        ("Marketplace", "marketplace", "Trading, sellers, buyers, and orders."),
        ("Database", "database", "Submissions, formatting, master releases."),
        ("Vinyl Collectors", "vinyl", "All things vinyl — pressings, pressings, pressings."),
        ("Genre: Jazz", "jazz", "Bebop, fusion, free, modal, you name it."),
        ("Genre: Electronic", "electronic", "Techno, house, ambient, IDM, dub."),
        ("Genre: Hip Hop", "hip-hop", "From boom bap to drill."),
        ("Crate Diggers", "crate-diggers", "Field reports from the world's record bins."),
        ("Help & Feedback", "help", "Site bugs, account questions, suggestions."),
    ]
    for name, slug, desc in forums:
        db.session.add(Forum(name=name, slug=slug, description=desc))
    db.session.commit()


def _release_image_exists(rid):
    return os.path.exists(os.path.join(BASE_DIR, "static", "images", "release", f"{rid}.jpg"))


def seed_database():
    if Release.query.count() > 0:
        return
    print("[seed] catalogue (releases / artists / labels / tracks)")

    seed_taxonomy()
    seed_forums()

    artist_cache = {}
    label_cache = {}
    genre_cache = {g.name: g for g in Genre.query.all()}
    style_cache = {}
    format_cache = {f.name: f for f in Format.query.all()}
    master_cache = {}

    wp_cache = _load_json("wikipedia.json") or {}
    discogs_data = _load_json("releases.json") or []
    mb_data = _load_json("mb_releases.json") or []

    next_synth_id = 90_000_001  # synthetic discogs_id for non-Discogs sources

    seen_keys = set()

    # ── Discogs source ──────────────────────────
    for d in discogs_data:
        title = (d.get("title") or "").strip()
        artist_name = (d.get("artist") or "").strip() or "Various"
        if not title:
            continue
        key = f"discogs-{d['id']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        artist = _get_or_create_artist(artist_name, artist_cache)
        year = None
        if d.get("year"):
            try: year = int(d["year"])
            except (TypeError, ValueError): pass

        master_key = (artist.id, title.lower())
        if master_key not in master_cache:
            m = Master(title=title[:300], artist_id=artist.id, year=year)
            db.session.add(m); db.session.flush()
            master_cache[master_key] = m
        master = master_cache[master_key]

        # Wikipedia extract
        wp = wp_cache.get(key, {})
        notes = wp.get("extract") or ""

        r = Release(
            discogs_id=int(d["id"]),
            title=title[:300],
            artist_id=artist.id,
            master_id=master.id,
            year=year,
            country=(d.get("country") or "")[:80],
            notes=notes,
            barcode=(d.get("barcode")[0] if d.get("barcode") else "")[:80],
            catno=(d.get("catno") or "")[:80],
            image_path=f"images/release/{d['id']}.jpg" if _release_image_exists(d['id']) else "",
            have_count=(d.get("community") or {}).get("have", 0) or random.randint(20, 500),
            want_count=(d.get("community") or {}).get("want", 0) or random.randint(5, 200),
            added_at=NOW - timedelta(days=random.randint(1, 800)),
        )
        db.session.add(r); db.session.flush()

        # Genres
        for gn in (d.get("genre") or []):
            g = genre_cache.get(gn) or _get_or_create_named(Genre, gn, genre_cache)
            if g and g not in r.genres:
                r.genres.append(g)
        # Styles
        for sn in (d.get("style") or []):
            s = _get_or_create_named(Style, sn, style_cache)
            if s and s not in r.styles:
                r.styles.append(s)
        # Formats
        for fn in (d.get("format") or [])[:4]:
            f = format_cache.get(fn) or _get_or_create_named(Format, fn, format_cache)
            if f and f not in r.formats:
                r.formats.append(f)
        # Labels (first 3)
        for ln in (d.get("label") or [])[:3]:
            l = _get_or_create_label(ln, label_cache)
            if l and l not in r.labels:
                r.labels.append(l)

        # Tracks (placeholder if none)
        for pos, title_t, dur in _build_tracklist_for(r.discogs_id):
            db.session.add(Track(release_id=r.id, position=pos, title=title_t, duration=dur))

    db.session.commit()

    # ── MusicBrainz source ──────────────────────
    for d in mb_data:
        title = (d.get("title") or "").strip()
        if not title:
            continue
        artists = d.get("artists") or []
        artist_name = (artists[0].get("name") if artists else "Various Artists").strip() or "Various"
        key = f"mb-{d['id']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        artist = _get_or_create_artist(artist_name, artist_cache)

        year = None
        d_str = d.get("first_release_date") or ""
        if d_str:
            try: year = int(d_str[:4])
            except (ValueError, TypeError): pass

        master_key = (artist.id, title.lower())
        if master_key not in master_cache:
            m = Master(title=title[:300], artist_id=artist.id, year=year)
            db.session.add(m); db.session.flush()
            master_cache[master_key] = m
        master = master_cache[master_key]

        wp = wp_cache.get(key, {})
        notes = wp.get("extract") or ""

        synth_id = next_synth_id
        next_synth_id += 1

        # Pick a plausible format spread.
        fmt_choices = random.choice([
            ["Vinyl", "LP", "Album"],
            ["CD", "Album"],
            ["Vinyl", "LP", "Album", "Reissue"],
            ["Cassette", "Album"],
            ["CD", "Album", "Compilation"],
            ["File", "FLAC", "Album"],
        ])

        r = Release(
            discogs_id=synth_id,
            title=title[:300],
            artist_id=artist.id,
            master_id=master.id,
            year=year,
            released=d_str,
            country=random.choice(["US", "UK", "Germany", "Japan", "France", "Netherlands",
                                    "Italy", "Brazil", "Canada", "Australia", "Sweden", ""]),
            notes=notes,
            image_path="",  # MB releases don't have an image_path; cover_url checks at request time
            have_count=random.randint(10, 800),
            want_count=random.randint(2, 350),
            added_at=NOW - timedelta(days=random.randint(1, 1200)),
        )
        db.session.add(r); db.session.flush()

        # Use the source tag as a genre fallback.
        tag = (d.get("tag_query") or "").strip()
        gname_map = {
            "hip hop": "Hip Hop", "techno": "Electronic", "house": "Electronic",
            "ambient": "Electronic", "drum and bass": "Electronic", "dubstep": "Electronic",
            "trance": "Electronic", "downtempo": "Electronic", "trip hop": "Electronic",
            "soul": "Funk / Soul", "funk": "Funk / Soul", "disco": "Funk / Soul",
            "country": "Folk, World, & Country", "folk": "Folk, World, & Country",
            "blues": "Blues", "classical": "Classical", "jazz": "Jazz",
            "reggae": "Reggae", "dub": "Reggae", "ska": "Reggae",
            "pop": "Pop", "k-pop": "Pop", "j-pop": "Pop", "city pop": "Pop",
            "metal": "Rock", "death metal": "Rock", "black metal": "Rock",
            "thrash metal": "Rock", "punk": "Rock", "hardcore": "Rock",
            "post-hardcore": "Rock", "alternative rock": "Rock",
            "garage rock": "Rock", "psychedelic rock": "Rock",
            "progressive rock": "Rock", "krautrock": "Rock", "post-rock": "Rock",
            "math rock": "Rock", "indie pop": "Pop", "synth-pop": "Pop",
            "post-punk": "Rock", "shoegaze": "Rock", "experimental": "Electronic",
            "noise": "Electronic", "drone": "Electronic", "industrial": "Electronic",
            "minimal": "Electronic", "lo-fi": "Pop", "salsa": "Latin",
            "bossa nova": "Latin", "latin": "Latin", "afrobeat": "Funk / Soul",
            "world": "Folk, World, & Country", "electronic": "Electronic",
            "boom bap": "Hip Hop", "trap": "Hip Hop", "gangsta rap": "Hip Hop",
            "conscious hip hop": "Hip Hop", "soundtrack": "Stage & Screen",
        }
        gname = gname_map.get(tag, "Electronic" if not tag else "Rock")
        if gname not in genre_cache:
            genre_cache[gname] = _get_or_create_named(Genre, gname, genre_cache)
        g = genre_cache[gname]
        if g and g not in r.genres:
            r.genres.append(g)
        # The tag itself becomes a style.
        if tag and tag.title() != gname:
            s = _get_or_create_named(Style, tag.title(), style_cache)
            if s and s not in r.styles:
                r.styles.append(s)

        for fn in fmt_choices:
            f = format_cache.get(fn) or _get_or_create_named(Format, fn, format_cache)
            if f and f not in r.formats:
                r.formats.append(f)

        # Tracks
        for pos, title_t, dur in _build_tracklist_for(r.id, n=random.choice([8, 10, 12])):
            db.session.add(Track(release_id=r.id, position=pos, title=title_t, duration=dur))

    db.session.commit()

    # Aggregate artist.in_collection (used to sort artist search).
    for a in Artist.query.all():
        a.in_collection = a.releases.count()
    db.session.commit()

    print(f"[seed] inserted {Release.query.count()} releases / {Artist.query.count()} artists "
          f"/ {Label.query.count()} labels / {Master.query.count()} masters")


# ──────────────────────────────────────────────
# 3. Benchmark users (deterministic)
# ──────────────────────────────────────────────

BENCH_USERS = [
    ("alice_crate",  "alice@test.com",   "alice12345", "Alice Johnson",      "Brooklyn, USA"),
    ("bob_vinyl",    "bob@test.com",     "bob123456",  "Bob Martinez",       "London, UK"),
    ("carol_jazz",   "carol@test.com",   "carol12345", "Carol Tanaka",       "Tokyo, Japan"),
    ("dave_techno",  "dave@test.com",    "dave12345",  "Dave Müller",        "Berlin, Germany"),
]

EXTRA_USERS = [
    ("dustyfingers", "dusty@example.com",      "dusty12345",  "Marcus Reid",       "Detroit, USA"),
    ("modulator",    "modulator@example.com",  "modul12345",  "Sandra Kowalski",   "Warsaw, Poland"),
    ("dubplate",     "dubplate@example.com",   "dubpl12345",  "Marvin Henderson",  "Kingston, Jamaica"),
    ("kosmische",    "kosmische@example.com",  "kosmi12345",  "Anke Berger",       "Cologne, Germany"),
    ("acidhouse303", "acid303@example.com",    "acid12345",   "Luis Fernandez",    "Chicago, USA"),
    ("freejazz",     "freejazz@example.com",   "freej12345",  "Eric Lefèvre",      "Paris, France"),
    ("bossanovafan", "bossa@example.com",      "bossa12345",  "Renata Souza",      "Rio de Janeiro, Brazil"),
    ("punk77",       "punk77@example.com",     "punkr12345",  "Eddie O'Connell",   "Dublin, Ireland"),
    ("synthpopgirl", "synthpop@example.com",   "synth12345",  "Yuki Sato",         "Osaka, Japan"),
    ("metalhead",    "metal@example.com",      "metal12345",  "Hans Eriksson",     "Stockholm, Sweden"),
    ("kpopcollector","kpop@example.com",       "kpopc12345",  "Min-jun Park",      "Seoul, South Korea"),
    ("dubstep_dj",   "dubstep@example.com",    "dubst12345",  "Tariq Williams",    "Croydon, UK"),
    ("classicalfan", "classical@example.com",  "class12345",  "Eleanor Whitfield", "Vienna, Austria"),
    ("indiekid",     "indie@example.com",      "indie12345",  "Sam Patel",         "Manchester, UK"),
    ("countrypicker","country@example.com",    "count12345",  "Bobby Ray",         "Nashville, USA"),
    ("ambientlover", "ambient@example.com",    "ambie12345",  "Lin Chen",          "Shanghai, China"),
    ("northernsoul", "soul@example.com",       "soulm12345",  "Jenny Walsh",       "Wigan, UK"),
    ("reggaeroots",  "roots@example.com",      "roots12345",  "Marcus Brown",      "Bristol, UK"),
    ("vaporwave",    "vapor@example.com",      "vapor12345",  "Hayden Cooper",     "Portland, USA"),
    ("krautrocker",  "kraut@example.com",      "kraut12345",  "Klaus Werner",      "Munich, Germany"),
    ("hip_hop_head", "hiphop@example.com",     "hipho12345",  "Andre Wright",      "Atlanta, USA"),
    ("psyckedelic",  "psych@example.com",      "psych12345",  "Olivia Stone",      "San Francisco, USA"),
    ("garagerocker", "garage@example.com",     "garag12345",  "Tom Beckett",       "Brooklyn, USA"),
    ("vinylonly",    "vinyl@example.com",      "vinyl12345",  "Sophia Romano",     "Milan, Italy"),
    ("djmixer",      "mixer@example.com",      "mixer12345",  "Karim Hassan",      "Cairo, Egypt"),
]


def seed_benchmark_users():
    if User.query.filter_by(email="alice@test.com").first():
        return
    print("[seed] users")
    all_users = BENCH_USERS + EXTRA_USERS
    for username, email, pw, real_name, location in all_users:
        u = User(
            username=username,
            email=email,
            password_hash=bcrypt.generate_password_hash(pw).decode("utf-8"),
            real_name=real_name,
            location=location,
            avatar_seed=username,
            bio=f"Collector and crate-digger based in {location.split(',')[0]}.",
            joined_at=datetime(2014 + random.randint(0, 11),
                                random.randint(1, 12),
                                random.randint(1, 28)),
            is_seller=random.random() < 0.45,
            seller_rating=round(random.uniform(4.2, 5.0), 1),
            seller_feedback_count=random.randint(8, 540),
        )
        db.session.add(u)
    db.session.commit()


# ──────────────────────────────────────────────
# 4. Community: ratings / reviews / collections / wantlists / lists / listings / threads
# ──────────────────────────────────────────────

REVIEW_TEMPLATES = [
    "An absolutely essential record. The production holds up beautifully decades later.",
    "Picked this up at a flea market in {city} for a song — easily one of the best buys of my collecting life.",
    "{artist} at the peak of their powers. Side B in particular is a masterclass.",
    "Pressing quality on this {country} edition is superb. Quiet vinyl, deep grooves.",
    "A divisive record but I love it. The transition from the third track to the fourth alone is worth the price.",
    "Has aged better than I expected. Holds its own next to anything released today.",
    "Don't sleep on the deeper cuts. The opener is the obvious banger, but the closer is what stays with you.",
    "Mastered for the format. If you have a decent system, you can hear every detail.",
    "Caught {artist} live around the time this came out and they were on fire. The record captures that energy.",
    "Reissue sounds noticeably brighter than my original — some will love that, some won't.",
    "Mono mix is, in my opinion, the way to hear this. The stereo separation feels gimmicky in places.",
    "Cover art alone earns this a spot on the shelf. The music? Pure gold.",
]

CITIES = ["Berlin", "Tokyo", "London", "Brooklyn", "Detroit", "Lagos", "São Paulo",
          "Mexico City", "Bristol", "Manchester", "Athens", "Paris"]

LIST_TITLES = [
    "Essential {decade}s — A Personal Top 25",
    "Records I Always Bring to the Listening Bar",
    "Late-Night Headphones Listens",
    "Underrated {genre} Gems",
    "Pressings Worth Tracking Down",
    "First Albums Before They Broke Through",
    "Records You Should Hear at Least Once",
    "The {genre} Starter Pack",
    "Crate Digger's Holy Grail List",
    "{decade}s — My Favourite Year by Year",
    "Sunday Morning Coffee Stack",
    "Field Recordings & Experiments",
]

THREAD_TITLES = [
    ("general", [
        "What did you spin this weekend?",
        "The one record you'd save from a fire",
        "Best record store you've ever visited",
        "Favourite album opener of all time",
        "Re-discovering an old favourite — share yours",
        "Records that grow on you over time",
        "Hidden gems from the year you were born",
    ]),
    ("vinyl", [
        "Best turntable under $500 in 2026?",
        "How do you clean used records?",
        "Brand new pressing has a warp — what would you do?",
        "Mono vs Stereo — when does it actually matter?",
        "Cartridges: MM vs MC for jazz",
        "Storage solutions that actually work",
        "What's your dream pressing plant?",
    ]),
    ("jazz", [
        "Top 5 Blue Note pressings of all time",
        "Modal jazz starter records",
        "Free jazz: where do I begin?",
        "Spiritual jazz — fed up of trying to find original pressings",
        "Best fusion records that aren't cheesy",
    ]),
    ("electronic", [
        "Underrated Detroit techno you should hear",
        "What's the heaviest dub record in your collection?",
        "Ambient for working from home",
        "Acid house — where it all began",
        "IDM's golden age — 1995–2002 or 2009–2014?",
    ]),
    ("hip-hop", [
        "Best instrumental hip-hop LPs",
        "Underrated boom bap producers from the 90s",
        "Records that changed your life as a kid",
        "Sample sources — share your finds",
    ]),
    ("marketplace", [
        "Seller scammed me — what now?",
        "Pricing my collection — how do you decide?",
        "Shipping internationally: what's the best courier?",
        "Buyer offered half my asking price. Counter or no?",
    ]),
    ("database", [
        "How to correctly submit a misprint variant",
        "Master release vs Versions — when to split?",
        "Discogs guidelines for promo pressings",
        "Foreign-language credits — translate or leave?",
    ]),
    ("crate-diggers", [
        "Found a sealed copy of {something} for $5 — pictures inside",
        "Best record fair you've ever been to",
        "Tips for digging at estate sales",
        "Pulled this rarity out of a $1 bin",
    ]),
    ("help", [
        "Forgot my password",
        "Wantlist not syncing to mobile app",
        "How do I edit a release I submitted years ago?",
    ]),
]

POST_TEMPLATES = [
    "Great question — for me, it's {artist}'s record from {year}. Nothing else comes close.",
    "Cosigned. {city} is criminally underrated for crate digging.",
    "I'd lean towards mono myself. The stereo mix on most of those records was an afterthought.",
    "Original pressings are getting hard to find, but the {year} reissue is a great alternative.",
    "Patience is everything in this hobby. The right copy always shows up eventually.",
    "Try a wet clean first, then dry brush before every play. Big difference.",
    "I bought one off Discogs last month — solid grade-VG+ for around $40. They're out there.",
    "Have you tried the {country} pressing? The mastering on those is noticeably different.",
    "Counter at 60% and see what happens. Worst case they say no.",
    "Spinning {album} right now. Such a perfect Sunday morning record.",
]


def seed_community():
    if Rating.query.count() > 0:
        return
    print("[seed] community (ratings/reviews/collections/wantlists/lists/listings/threads)")

    users = User.query.all()
    releases = Release.query.all()
    if not users or not releases:
        return

    rng = random.Random(42)

    # 4a. Ratings: ~12 per release on average, weighted toward "popular" ones.
    for r in releases:
        n = rng.choices([0, 3, 6, 10, 16, 25, 40], weights=[10, 14, 18, 18, 16, 14, 10])[0]
        if not n:
            continue
        raters = rng.sample(users, min(n, len(users)))
        # Slight bias toward 4-5 stars (Discogs ratings skew high).
        weights = [3, 7, 18, 36, 36]  # 1..5
        for u in raters:
            v = rng.choices([1, 2, 3, 4, 5], weights=weights)[0]
            db.session.add(Rating(user_id=u.id, release_id=r.id, value=v,
                                  created_at=NOW - timedelta(days=rng.randint(1, 700))))
    db.session.commit()

    # Recompute avg + count.
    for r in releases:
        ratings = list(r.ratings)
        if ratings:
            r.avg_rating = sum(rt.value for rt in ratings) / len(ratings)
            r.rating_count = len(ratings)
    db.session.commit()

    # 4b. Reviews: ~30% of releases get 1-3 reviews.
    for r in releases:
        if rng.random() > 0.30:
            continue
        n = rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
        for _ in range(n):
            u = rng.choice(users)
            template = rng.choice(REVIEW_TEMPLATES)
            body = template.format(
                city=rng.choice(CITIES),
                artist=r.artist.name,
                country=r.country or "Japanese",
            )
            db.session.add(Review(user_id=u.id, release_id=r.id,
                                  body=body,
                                  rating=rng.choices([3, 4, 5], weights=[20, 40, 40])[0],
                                  helpful=rng.randint(0, 18),
                                  created_at=NOW - timedelta(days=rng.randint(1, 600))))
    db.session.commit()

    # 4c. Collections + wantlists per user.
    for u in users:
        coll_n = rng.randint(40, 200)
        want_n = rng.randint(20, 80)
        coll_releases = rng.sample(releases, min(coll_n, len(releases)))
        want_pool = [r for r in releases if r not in coll_releases]
        want_releases = rng.sample(want_pool, min(want_n, len(want_pool)))
        for r in coll_releases:
            db.session.add(CollectionItem(
                user_id=u.id, release_id=r.id,
                folder=rng.choices(COLLECTION_FOLDERS, weights=[40, 0, 30, 25, 5])[0]
                       if rng.random() < 0.7 else "Uncategorized",
                media_condition=rng.choices(GRADES[:5], weights=[5, 35, 35, 20, 5])[0],
                sleeve_condition=rng.choices(GRADES[:5], weights=[4, 30, 35, 24, 7])[0],
                added_at=NOW - timedelta(days=rng.randint(1, 1500)),
            ))
        for r in want_releases:
            db.session.add(WantlistItem(
                user_id=u.id, release_id=r.id,
                min_grade=rng.choice(GRADES[:6]),
                added_at=NOW - timedelta(days=rng.randint(1, 700)),
            ))
    db.session.commit()

    # Refresh have/want counts.
    for r in releases:
        r.have_count = CollectionItem.query.filter_by(release_id=r.id).count() or r.have_count
        r.want_count = WantlistItem.query.filter_by(release_id=r.id).count() or r.want_count
    db.session.commit()

    # 4d. Lists: each user makes 0-3.
    genres = [g.name for g in Genre.query.all()]
    for u in users:
        n = rng.choices([0, 1, 2, 3], weights=[20, 40, 30, 10])[0]
        for _ in range(n):
            title = rng.choice(LIST_TITLES).format(
                decade=str(rng.choice([1960, 1970, 1980, 1990, 2000, 2010])),
                genre=rng.choice(genres),
            )
            lst = List(user_id=u.id,
                       title=title[:200],
                       description=f"Curated by {u.username}.",
                       is_public=rng.random() < 0.92,
                       created_at=NOW - timedelta(days=rng.randint(1, 800)))
            db.session.add(lst); db.session.flush()
            for i, rel in enumerate(rng.sample(releases, rng.randint(6, 25)), start=1):
                db.session.add(ListItem(list_id=lst.id, release_id=rel.id,
                                        comment="" if rng.random() < 0.6 else f"#{i} — a personal favourite.",
                                        position=i))
    db.session.commit()

    # 4e. Marketplace listings: ~20% of releases get 1-4 listings.
    sellers = [u for u in users if u.is_seller]
    if sellers:
        for r in releases:
            if rng.random() > 0.22:
                continue
            n = rng.choices([1, 2, 3, 4], weights=[55, 25, 12, 8])[0]
            for _ in range(n):
                seller = rng.choice(sellers)
                # Reasonable price spread by format & year scarcity.
                base = rng.uniform(8.0, 60.0)
                if r.year and r.year < 1970:
                    base *= rng.uniform(1.4, 4.0)
                price = round(base, 2)
                l = Listing(
                    user_id=seller.id, release_id=r.id,
                    media_condition=rng.choices(GRADES[:6], weights=[4, 25, 36, 20, 10, 5])[0],
                    sleeve_condition=rng.choices(GRADES[:6], weights=[4, 22, 36, 22, 11, 5])[0],
                    comments=rng.choice([
                        "Plays beautifully, light hairlines that don't affect playback.",
                        "Original inner sleeve included. Stunning copy.",
                        "Sleeve has light ringwear. Vinyl is mint.",
                        "Pressed at the original plant — checked the matrix runout.",
                        "Test played in full. Quiet pressing throughout.",
                        "",
                    ]),
                    price=price,
                    currency=rng.choice(["USD", "USD", "USD", "EUR", "GBP", "JPY"]),
                    shipping_from=seller.location.split(",")[-1].strip() if seller.location else "United States",
                    allow_offers=rng.random() < 0.45,
                    posted_at=NOW - timedelta(days=rng.randint(1, 90)),
                )
                db.session.add(l)
        db.session.commit()
        for r in releases:
            n = Listing.query.filter_by(release_id=r.id, status="For Sale").count()
            r.num_for_sale = n
            if n:
                r.lowest_price = db.session.query(db.func.min(Listing.price)) \
                                  .filter(Listing.release_id == r.id,
                                          Listing.status == "For Sale").scalar()
        db.session.commit()

    # 4f. Forum threads + posts.
    forums = {f.slug: f for f in Forum.query.all()}
    for slug, titles in THREAD_TITLES:
        f = forums.get(slug)
        if not f:
            continue
        for title in titles:
            starter = rng.choice(users)
            t = Thread(forum_id=f.id, user_id=starter.id,
                       title=title.format(something="John Coltrane")[:280],
                       pinned=(title.startswith("Best") and rng.random() < 0.15),
                       created_at=NOW - timedelta(days=rng.randint(1, 365)))
            db.session.add(t); db.session.flush()
            opener_body = rng.choice([
                f"Curious to hear what everyone thinks. {title.lower()}? Share your picks.",
                f"Was thinking about this on the train home tonight — {title.lower()}",
                f"Long-time lurker, first time poster. Tell me your stories.",
            ])
            db.session.add(Post(thread_id=t.id, user_id=starter.id,
                                body=opener_body,
                                created_at=t.created_at + timedelta(minutes=1)))
            # 2-12 replies.
            for _ in range(rng.randint(2, 12)):
                u = rng.choice(users)
                some_release = rng.choice(releases)
                body = rng.choice(POST_TEMPLATES).format(
                    artist=some_release.artist.name,
                    year=some_release.year or 1973,
                    city=rng.choice(CITIES),
                    country=some_release.country or "Japanese",
                    album=some_release.title,
                )
                db.session.add(Post(thread_id=t.id, user_id=u.id, body=body,
                                    created_at=t.created_at + timedelta(
                                        hours=rng.randint(1, 720))))
    db.session.commit()

    print(f"[seed] community done: {Rating.query.count()} ratings, "
          f"{Review.query.count()} reviews, {CollectionItem.query.count()} collection items, "
          f"{WantlistItem.query.count()} wantlist items, {List.query.count()} lists, "
          f"{Listing.query.count()} listings, {Thread.query.count()} threads, "
          f"{Post.query.count()} posts")
