"""Phys.org mirror — idempotent seed data.

Loads ``scraped_data/phys_data.json`` (RSS-derived articles), preserves only source-derived article text and verified metadata, and seeds deterministic benchmark users with saved articles, comments, and search history.

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
]

# Metadata verified against the corresponding public Phys.org/Tech Xplore pages; unverified fields remain blank rather than presenting generated values as facts.
SOURCE_METADATA_FILE = os.path.join(BASE_DIR, 'source_metadata.json')
with open(SOURCE_METADATA_FILE, encoding='utf-8') as source_metadata_file:
    SOURCE_METADATA_OVERRIDES = json.load(source_metadata_file)['articles']

VIEW_OVERRIDES = {
    # Keep the named Task 10 target on the first Popular page without making it the first result.
    'how-a-single-star-can-reshape-an-entire-galaxy': 7000,
}


def source_metadata(category_slug, subsection, slug):
    """Return source-verified journal and institution values when available."""
    del category_slug, subsection
    metadata = SOURCE_METADATA_OVERRIDES.get(slug, {})
    return metadata.get('journal', ''), metadata.get('institution', '')


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
    """Return only source-derived article text; never invent attributed claims."""
    del rng
    return _strip_html(rss_desc) or title


def _truncate_summary(text: str, limit: int = 240) -> str:
    """Truncate at a word boundary and make truncation explicit."""
    cleaned = _strip_html(text)
    if len(cleaned) <= limit:
        return cleaned
    shortened = cleaned[: limit - 1].rsplit(' ', 1)[0].rstrip(' ,;:-')
    return f"{shortened}…"


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
            # Ignore unsupported feeds instead of creating an empty catch-all
            # category that cannot be exercised by a benchmark task.
            continue
        cat_id = cat_id_map[cat_slug]

        published = _parse_pub(it.get('pub_date') or '')
        # Subsection from RSS categories (e.g. "Optics & Photonics")
        rss_cats = it.get('rss_categories') or []
        subsection = (rss_cats[0] if rss_cats else '').strip()

        # Preserve the RSS creator when present; otherwise use the verified publisher fallback recorded in source_metadata.json.
        author_real = (it.get('author') or '').strip()
        metadata = SOURCE_METADATA_OVERRIDES.get(slug, {})
        if author_real:
            author_name = author_real
        elif metadata.get('author'):
            author_name = metadata['author']
        else:
            author_name = 'Tech Xplore' if cat_slug == 'technology' else 'Phys.org'

        journal, institution = source_metadata(cat_slug, subsection, slug)
        doi = metadata.get('doi', '')

        body = _build_body(it.get('description') or '', title, rng=rng)
        if metadata.get('body_append'):
            body = f"{body}\n\n{metadata['body_append']}"
        subtitle = _truncate_summary(it.get('description') or '')

        image_filename = it.get('local_image') or ''

        # Deterministic view counts so trending lists are stable across
        # rebuilds (only changes when new articles are added). Range chosen
        # to give a clear winner: ~1500-9000 with one popular article in
        # each category capped near the top.
        rv = random.Random(slug + ':views')
        views = VIEW_OVERRIDES.get(slug, rv.randint(150, 9000))

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
