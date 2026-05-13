"""Phys.org mirror — idempotent seed data.

Loads ``scraped_data/phys_data.json`` (real RSS-derived articles) and synthesizes
the side data agents need: source journals/institutions, additional body text,
benchmark users with saved articles + comments + search history.

The byte-identical reset invariant requires that each ``seed_*`` function is a
no-op when the DB is already populated. Per-row gates aren't enough — even an
empty ``commit()`` bumps SQLite metadata.
"""
import json
import os
import random
import re
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'scraped_data', 'phys_data.json')

# Pinned reference date so "published_at" values are stable across rebuilds and
# the byte-identical reset invariant holds.
MIRROR_REFERENCE_DATE = datetime(2026, 5, 12, 12, 0, 0)


CATEGORIES = [
    ('physics', 'Physics',
     'Latest news in physics, materials science, optics, quantum and superconductivity.', 10),
    ('earth', 'Earth Sciences',
     'Climate, geology, oceanography and the planet that supports us.', 20),
    ('technology', 'Technology',
     'AI, robotics, computing, energy, and engineering breakthroughs.', 30),
    ('biology', 'Biology',
     'Cell biology, ecology, evolution, plants and animals.', 40),
    ('chemistry', 'Chemistry',
     'Molecules, reactions, materials and analytical chemistry.', 50),
    ('astronomy', 'Astronomy & Space',
     'Cosmology, planetary science, missions and space exploration.', 60),
    ('nanotechnology', 'Nanotechnology',
     'Nanomaterials, nanoelectronics, bio- and nano-technology.', 70),
    ('other', 'Other Sciences',
     'Mathematics, social sciences, archaeology and education.', 80),
]


# Pools used to synthesize plausible journal / institution data per category.
# Real phys.org articles cite these journals heavily; using them keeps the
# detail page realistic. Each tuple is (journal, parent publisher).
JOURNALS_BY_CATEGORY = {
    'physics': [
        'Physical Review Letters', 'Nature Physics', 'Physical Review B',
        'Reviews of Modern Physics', 'New Journal of Physics',
        'Physical Review Applied', 'Optics Express', 'Nature Photonics',
    ],
    'earth': [
        'Nature Geoscience', 'Geophysical Research Letters',
        'Journal of Climate', 'Earth and Planetary Science Letters',
        'Nature Climate Change', 'Geology', 'Journal of Geophysical Research: Atmospheres',
    ],
    'technology': [
        'Nature Electronics', 'IEEE Transactions on Robotics',
        'ACM Computing Surveys', 'Joule', 'Energy & Environmental Science',
        'Nature Machine Intelligence', 'Science Robotics',
    ],
    'biology': [
        'Cell', 'Nature', 'Current Biology', 'Proceedings of the National Academy of Sciences',
        'eLife', 'Nature Ecology & Evolution', 'PLOS Biology', 'Molecular Ecology',
    ],
    'chemistry': [
        'Journal of the American Chemical Society', 'Nature Chemistry',
        'Angewandte Chemie International Edition', 'ACS Central Science',
        'Chemical Science', 'Inorganic Chemistry',
    ],
    'astronomy': [
        'The Astrophysical Journal', 'Monthly Notices of the Royal Astronomical Society',
        'Astronomy & Astrophysics', 'Nature Astronomy', 'Icarus',
        'Astrophysical Journal Letters',
    ],
    'nanotechnology': [
        'Nature Nanotechnology', 'ACS Nano', 'Nano Letters',
        'Advanced Materials', 'Small', 'npj 2D Materials and Applications',
    ],
    'other': [
        'Journal of Archaeological Science', 'Nature Human Behaviour',
        'PNAS', 'Science Advances', 'PLOS ONE', 'Proceedings of the Royal Society B',
    ],
}


INSTITUTIONS_BY_CATEGORY = {
    'physics': [
        'Massachusetts Institute of Technology', 'Stanford University',
        'CERN', 'University of Cambridge', 'ETH Zurich', 'Caltech',
        'Max Planck Institute for Quantum Optics', 'Technion',
        'Princeton University', 'Argonne National Laboratory',
    ],
    'earth': [
        'NOAA', 'University of Washington', 'Scripps Institution of Oceanography',
        'University of Oxford', 'Potsdam Institute for Climate Impact Research',
        'Woods Hole Oceanographic Institution', 'NASA Goddard Space Flight Center',
        'Columbia University',
    ],
    'technology': [
        'Carnegie Mellon University', 'Google DeepMind', 'IBM Research',
        'University of California, Berkeley', 'University of Toronto',
        'EPFL', 'Microsoft Research', 'KAIST', 'Tsinghua University',
    ],
    'biology': [
        'Harvard Medical School', 'University of Oxford',
        'Howard Hughes Medical Institute', 'EMBL-EBI',
        'Salk Institute', 'University of Tokyo', 'Wellcome Sanger Institute',
        'University of Pennsylvania',
    ],
    'chemistry': [
        'Northwestern University', 'University of Chicago',
        'University of California, Los Angeles', 'Scripps Research',
        'University of Bristol', 'Tokyo Institute of Technology',
        'Imperial College London',
    ],
    'astronomy': [
        'NASA Jet Propulsion Laboratory', 'European Southern Observatory',
        'Space Telescope Science Institute', 'Harvard-Smithsonian Center for Astrophysics',
        'Max Planck Institute for Astronomy', 'Caltech', 'University of Arizona',
    ],
    'nanotechnology': [
        'KAIST', 'Rice University', 'IBM Research – Zurich',
        'National University of Singapore', 'University of Manchester',
        'Tsinghua University', 'Lawrence Berkeley National Laboratory',
    ],
    'other': [
        'University of Oxford', 'Max Planck Institute for the Science of Human History',
        'University of Chicago', 'London School of Economics',
        'University of Cape Town', 'Hebrew University of Jerusalem',
    ],
}


# Synthetic body filler. Only used when the RSS description is too short.
GENERIC_PARAGRAPHS = [
    "The findings, the team writes, open new questions about how robust the underlying assumptions of the field really are, and suggest that further independent replications will be needed before the wider community converges on a single explanation.",
    "Beyond the immediate result, the work hints at practical applications. The authors caution, however, that translating these laboratory observations into deployable systems is likely to take several more years of engineering effort and additional safety review.",
    "Independent researchers not involved in the study described the data as 'compelling' and 'a useful starting point,' while noting that some of the boldest claims will need to be tested in larger and more diverse samples before being accepted as established science.",
]


def _slugify(text: str, maxlen: int = 70) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return s[:maxlen] or "article"


def _parse_pub(s: str) -> datetime:
    """Parse RSS pubDate. Falls back to MIRROR_REFERENCE_DATE.

    strptime's %Z only accepts UTC/GMT and the local TZ on most platforms, so
    real RSS dates like 'EDT' / 'PDT' don't parse. Strip the trailing zone
    word (or +0000-style offset) and parse the remainder."""
    if not s:
        return MIRROR_REFERENCE_DATE
    s = s.strip()
    m = re.match(r'(.+?\d{2}:\d{2}:\d{2})\s*\S+', s)
    base = m.group(1) if m else s
    for fmt in ("%a, %d %b %Y %H:%M:%S",
                "%a, %d %b %Y %H:%M",
                "%a, %d %b %Y"):
        try:
            return datetime.strptime(base.strip(), fmt)
        except Exception:
            continue
    return MIRROR_REFERENCE_DATE


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_body(rss_desc: str, title: str, *, rng: random.Random) -> str:
    """Return paragraph-separated body text. Use the RSS description as the
    lede and append synthetic-but-plausible follow-on paragraphs so each
    article has at least 3 paragraphs."""
    lede = _strip_html(rss_desc) or title
    paragraphs = [lede]
    pool = GENERIC_PARAGRAPHS[:]
    rng.shuffle(pool)
    paragraphs.append(pool[0])
    paragraphs.append(pool[1])
    return "\n\n".join(paragraphs)


def seed_database(db, User, Category, Article, Comment, bcrypt):
    if Article.query.count() > 0:
        return

    # Seed categories first (only if empty — gated by the outer check on
    # Article, but we double-check here to keep the function self-contained).
    cat_id_map = {}
    for slug, name, desc, order in CATEGORIES:
        c = Category.query.filter_by(slug=slug).first()
        if c is None:
            c = Category(slug=slug, name=name, description=desc, sort_order=order)
            db.session.add(c)
            db.session.flush()
        cat_id_map[slug] = c.id

    if not os.path.exists(DATA_FILE):
        # No scraped data — bail without committing anything else, leaving
        # only categories. (The reset invariant still holds because we did
        # commit categories on the first call; subsequent calls are gated.)
        db.session.commit()
        return

    with open(DATA_FILE) as f:
        items = json.load(f)

    rng = random.Random(20260513)

    # Determine featured article ids ahead of time so the same items are
    # picked across rebuilds.
    item_keys = [it.get('link') or it.get('title') for it in items]
    featured_count = min(8, len(items))
    featured_keys = set(rng.sample(item_keys, featured_count)) if item_keys else set()

    next_id = 1
    seen_slugs = set()
    for it in items:
        title = (it.get('title') or '').strip()
        if not title:
            continue
        slug = it.get('slug') or _slugify(title)
        original = slug
        n = 2
        while slug in seen_slugs:
            slug = f"{original}-{n}"
            n += 1
        seen_slugs.add(slug)

        cat_slug = it.get('category_slug') or 'other'
        if cat_slug not in cat_id_map:
            cat_slug = 'other'
        cat_id = cat_id_map[cat_slug]

        published = _parse_pub(it.get('pub_date') or '')
        # Subsection from RSS categories (e.g. "Optics & Photonics")
        rss_cats = it.get('rss_categories') or []
        subsection = (rss_cats[0] if rss_cats else '').strip()

        # Author: real RSS dc:creator if present, else synthesized.
        author_real = (it.get('author') or '').strip()
        if author_real:
            author_name = author_real
        else:
            # Reproducible synthesized author per article slug.
            r2 = random.Random(slug + ':author')
            firsts = ['Sarah', 'Michael', 'Ananya', 'Jorge', 'Mei', 'David',
                      'Priya', 'Liam', 'Fatima', 'Hiroshi', 'Olivia', 'Karim',
                      'Nina', 'Oluwa', 'Bjorn', 'Elena']
            lasts = ['Patel', 'Garcia', 'Nguyen', 'Kowalski', 'Rossi', 'Tanaka',
                     'Andersen', 'Okafor', 'Singh', 'Yamamoto', 'Hernandez',
                     'Mueller', 'Ahmed', 'Park']
            author_name = f"{r2.choice(firsts)} {r2.choice(lasts)}"

        # Journal / institution synthesized per article (deterministic by slug)
        r3 = random.Random(slug + ':source')
        journal = r3.choice(JOURNALS_BY_CATEGORY.get(cat_slug, JOURNALS_BY_CATEGORY['other']))
        institution = r3.choice(INSTITUTIONS_BY_CATEGORY.get(cat_slug, INSTITUTIONS_BY_CATEGORY['other']))
        # DOI: synthesize a stable but fake-looking DOI per article id.
        doi = f"https://doi.org/10.{1000 + next_id}/phys.{published.year}.{next_id:05d}"

        body = _build_body(it.get('description') or '', title, rng=rng)
        subtitle = _strip_html(it.get('description') or '')[:240]

        image_filename = it.get('local_image') or ''

        # Deterministic view counts so trending lists are stable across
        # rebuilds (only changes when new articles are added). Range chosen
        # to give a clear winner: ~1500-9000 with one popular article in
        # each category capped near the top.
        rv = random.Random(slug + ':views')
        views = rv.randint(150, 9000)

        is_featured = (it.get('link') or it.get('title')) in featured_keys

        art = Article(
            id=next_id,
            slug=slug,
            title=title,
            subtitle=subtitle,
            body=body,
            author_name=author_name,
            source_journal=journal,
            source_institution=institution,
            doi_url=doi,
            image_filename=image_filename,
            subsection=subsection,
            category_id=cat_id,
            published_at=published,
            views=views,
            featured=is_featured,
        )
        db.session.add(art)
        next_id += 1

    db.session.commit()


# ---------------------------------------------------------------------------
# Benchmark users
# ---------------------------------------------------------------------------

BENCH_USERS = [
    dict(username='alice_j', email='alice.j@test.com', full_name='Alice Johnson',
         bio='PhD student in astrophysics. Saving everything about exoplanets and dark matter.',
         location='Boston, MA', interests='astronomy,physics'),
    dict(username='bob_c', email='bob.c@test.com', full_name='Bob Chen',
         bio='Climate-tech reporter. Following ocean carbon, methane and renewables stories.',
         location='Seattle, WA', interests='earth,technology'),
    dict(username='carol_d', email='carol.d@test.com', full_name='Carol Davis',
         bio='Computational biologist. Long-time fan of CRISPR, protein design and ecology.',
         location='Cambridge, UK', interests='biology,chemistry'),
    dict(username='david_k', email='david.k@test.com', full_name='David Kim',
         bio='Materials engineer. Reads everything tagged Nanotechnology, Optics & Photonics.',
         location='Seoul, South Korea', interests='nanotechnology,physics'),
]
PASSWORD = 'TestPass123!'

# Pre-generated bcrypt hash for PASSWORD. bcrypt.generate_password_hash uses a
# random salt on every call, which would break the byte-identical reset
# invariant — so we pin one valid hash here. Verified at boot time by
# bcrypt.check_password_hash; rotate by running:
#   from flask_bcrypt import Bcrypt; from flask import Flask
#   print(Bcrypt(Flask(__name__)).generate_password_hash('TestPass123!').decode())
PINNED_PASSWORD_HASH = (
    '$2b$12$zV7HfiJmZTqLsgP30kyvJemamXfJyBv66FPuQOrwYXXsyQvrafvie'
)


# Stable user-id mapping: 1001..1004 (well above article-derived ids so we
# don't collide with any future re-numbering).
USER_ID_BASE = 1001


def _pick_articles(Article, *, where: dict, n: int, seed: str) -> list:
    """Return up to n articles matching ``where`` filters, deterministically
    ordered by id so the result is identical across rebuilds."""
    q = Article.query
    for k, v in where.items():
        q = q.filter(getattr(Article, k) == v)
    items = q.order_by(Article.id).all()
    rng = random.Random(seed)
    rng.shuffle(items)
    return items[:n]


def seed_benchmark_users(db, User, Category, Article, Comment, SavedArticle, SearchHistory, bcrypt):
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    # Categories must exist (created by seed_database). Look up ids.
    pw_hash = PINNED_PASSWORD_HASH

    user_objs = {}
    for i, u in enumerate(BENCH_USERS):
        obj = User(
            id=USER_ID_BASE + i,
            username=u['username'],
            email=u['email'],
            full_name=u['full_name'],
            bio=u['bio'],
            location=u['location'],
            interests=u['interests'],
            password_hash=pw_hash,
            created_at=MIRROR_REFERENCE_DATE - timedelta(days=180 + i * 30),
        )
        db.session.add(obj)
        user_objs[u['username']] = obj
    db.session.flush()

    # Save articles aligned to each user's interests so saved-list tasks have
    # depth and disambiguation candidates.
    save_targets = {
        'alice_j': [
            ('astronomy', 4),
            ('physics', 2),
        ],
        'bob_c': [
            ('earth', 4),
            ('technology', 2),
        ],
        'carol_d': [
            ('biology', 4),
            ('chemistry', 2),
        ],
        'david_k': [
            ('nanotechnology', 3),
            ('physics', 2),
        ],
    }
    next_save_id = 1
    save_notes_by_user = {
        'alice_j': ['Read for thesis chapter 3', 'Cite in proposal', 'Follow-up reading',
                    'Discuss with advisor', 'Seminar candidate', 'Review for journal club'],
        'bob_c': ['Story idea — angle 2', 'Lead source candidate', 'Background reading',
                  'Quote for upcoming feature', 'Verify with NOAA contact', 'Pitch to editor'],
        'carol_d': ['Methods section', 'Lab meeting share', 'Forward to postdocs',
                    'Compare with our pipeline', 'Re-read after deadline', 'Class material'],
        'david_k': ['Material spec lookup', 'Patent landscape', 'Contact authors',
                    'Internal report cite', 'Compare with our process', 'Lab notebook ref'],
    }
    for username, plan in save_targets.items():
        u = user_objs[username]
        notes = save_notes_by_user[username]
        used = 0
        for cat_slug, n in plan:
            cat = Category.query.filter_by(slug=cat_slug).first()
            if cat is None:
                continue
            articles = _pick_articles(Article, where={'category_id': cat.id}, n=n,
                                      seed=f"{username}:save:{cat_slug}")
            for art in articles:
                sa = SavedArticle(
                    id=next_save_id,
                    user_id=u.id,
                    article_id=art.id,
                    note=notes[used % len(notes)],
                    created_at=MIRROR_REFERENCE_DATE - timedelta(days=2 + used * 3),
                )
                db.session.add(sa)
                next_save_id += 1
                used += 1

    # Comments per user (2-4 each) on a deterministic spread of articles.
    comments_plan = {
        'alice_j': [
            'Beautiful explanation of the dark-matter constraints — the figure 3 plot is doing a lot of work here.',
            'Worth comparing with the 2024 Planck re-analysis — different priors but converging conclusions.',
            'Saving this for the journal club tomorrow; the methodology section is a great teaching example.',
        ],
        'bob_c': [
            'This contradicts the line a senator pushed last week. Sourcing this for my Wednesday column.',
            'The institution statement and the paper itself disagree on the 2030 timeline. Anyone seen the PRR?',
            'Modeling assumptions feel optimistic, but the data underlying them is solid. Cautious thumbs up.',
        ],
        'carol_d': [
            'The CRISPR off-target rates here are an order of magnitude lower than what we see in our pipeline.',
            'I love that they released the raw sequencing data. Re-running their analysis tonight.',
            'Nice work, but I expected more discussion of polyploid edge cases.',
        ],
        'david_k': [
            'The fabrication tolerance is the real story here, not the zero-resistance claim.',
            'Anyone have access to the SI? The thickness vs. mobility curve is the only thing that matters.',
            'Calling it now: this technique will be in commercial sensors by 2028.',
        ],
    }
    next_comment_id = 1
    for username, comment_texts in comments_plan.items():
        u = user_objs[username]
        # Pick articles whose category matches the user's first interest tag,
        # so a "comments by alice on physics articles" task is well-defined.
        first_interest = u.interests.split(',')[0]
        cat = Category.query.filter_by(slug=first_interest).first()
        if cat is None:
            target_articles = Article.query.order_by(Article.id).limit(len(comment_texts)).all()
        else:
            target_articles = _pick_articles(Article, where={'category_id': cat.id},
                                             n=len(comment_texts),
                                             seed=f"{username}:comment")
        for i, art in enumerate(target_articles):
            c = Comment(
                id=next_comment_id,
                text=comment_texts[i],
                user_id=u.id,
                article_id=art.id,
                parent_id=None,
                score=0,
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=1 + i * 4),
            )
            db.session.add(c)
            next_comment_id += 1

    # Seed a few cross-user reply chains so commenter-thread tasks work.
    reply_seeds = [
        ('bob_c', 'alice_j', 0, 'Totally agree on the priors point — the new constraint is much tighter though.'),
        ('alice_j', 'carol_d', 0, 'The polyploid section was a missed opportunity, you are right.'),
        ('david_k', 'bob_c', 1, 'I think the institution is hedging because of an unannounced pilot — keep watching.'),
    ]
    for replier_username, target_username, target_idx, text in reply_seeds:
        replier = user_objs[replier_username]
        target_user = user_objs[target_username]
        target_comments = Comment.query.filter_by(user_id=target_user.id) \
            .order_by(Comment.id).all()
        if target_idx >= len(target_comments):
            continue
        parent = target_comments[target_idx]
        c = Comment(
            id=next_comment_id,
            text=text,
            user_id=replier.id,
            article_id=parent.article_id,
            parent_id=parent.id,
            score=0,
            created_at=parent.created_at + timedelta(hours=6),
        )
        db.session.add(c)
        next_comment_id += 1

    # Search history per user (2-3 each)
    search_plan = {
        'alice_j': ['exoplanet atmosphere', 'dark matter halo', 'james webb'],
        'bob_c':   ['ocean carbon capture', 'methane emissions arctic'],
        'carol_d': ['CRISPR off-target', 'protein structure prediction', 'mitochondria'],
        'david_k': ['2D material superconductor', 'graphene transistor'],
    }
    next_sh_id = 1
    for username, queries in search_plan.items():
        u = user_objs[username]
        for j, q in enumerate(queries):
            sh = SearchHistory(
                id=next_sh_id,
                user_id=u.id,
                query_text=q,
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=1 + j * 2,
                                                             hours=j * 5),
            )
            db.session.add(sh)
            next_sh_id += 1

    db.session.commit()
