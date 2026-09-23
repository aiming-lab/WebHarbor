#!/usr/bin/env python3
"""Build-time seed for the America's Health Rankings mirror.

Converts the harvested live-site data under scraped_data/ into SQLite rows.
Every seed function early-returns when the DB is already populated so the
container boot path and /reset keep the DB byte-identical.

All data was harvested from https://www.americashealthrankings.org/ (SSR flight
payloads, the site's own GraphQL persisted queries, and rendered pages) — see
scraped_data/harvest/ for the tooling.
"""
import json
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE = os.path.join(BASE_DIR, 'scraped_data')
HARVEST = os.path.join(SCRAPE, 'harvest')

# Benchmark reference date pinned by the seed.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 21)


def _load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def _load_all(directory):
    out = {}
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if name.endswith('.json'):
            out[name[:-5]] = _load(os.path.join(directory, name))
    return out


def _text(value):
    return str(value) if value is not None else ''


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Seed functions (each gated at the whole-function level)
# ---------------------------------------------------------------------------

def seed_database(db, StateGeo, StateFact, MeasureCategory, Measure,
                  MeasureValue, MeasureDisparity, MeasureOption,
                  MeasureLink, Edition, MeasureEdition, EditionMeasureState,
                  Report, ReportSection, Article, Topic, FaqItem,
                  StaticPage, HomeBlock):
    if Measure.query.count() > 0:
        return

    # ---- editions -------------------------------------------------------
    for ed in [(284, '2025 Annual', 1, 2025), (283, '2025 HWC', 3, 2025),
               (286, '2026 Senior', 2, 2026)]:
        db.session.add(Edition(id=ed[0], name=ed[1], report_type_id=ed[2],
                               year=ed[3]))

    # ---- measure categories + measures ------------------------------------
    nav = _load(os.path.join(HARVEST, 'navdata.json'))['nav']
    measures_json = _load_all(os.path.join(SCRAPE, 'measures'))
    cat_by_name = {}
    for idx, cat in enumerate(nav):
        name = cat['label']
        mc = MeasureCategory(name=name, display_order=idx)
        db.session.add(mc)
        cat_by_name[name] = mc

    # slugs that 500 on the live site: kept in the directory but without data
    upstream_error_slugs = {'covid_deaths_provisional_annual'}

    seen_slugs = {}
    order_by_slug = {}
    for cat in nav:
        for opt in cat.get('options', []):
            slug = opt['value']
            order_by_slug.setdefault(slug, len(order_by_slug))

    for slug, rec in measures_json.items():
        md = rec.get('measureData') or {}
        td = rec.get('trendData') or {}
        about = rec.get('about') or {}
        acc = (about.get('accordionContent') or {}) if about else {}
        rms = md.get('reportMeasures') or []
        latest = max(rms, key=lambda x: x.get('editionId', 0)) if rms else None
        trend_rows = rec.get('trendGraphQL') or []
        # Upstream splits a measure's history into multiple trendGraphQL series
        # rows at methodology breaks (e.g. Obesity: 1990-2010 + 2011-2024).
        # Ingest the UNION of all series; on the rare (state, displayYear)
        # collision keep the newer methodology's row (higher metricTypeID) so
        # the trend line stays continuous with the series that extends to the
        # latest year.
        trend_rows = sorted(trend_rows,
                            key=lambda r: _int(r.get('metricTypeID')), reverse=True)
        trend_data = []
        _seen_series_keys = set()
        for row in trend_rows:
            for d in row.get('metricData') or []:
                key = (d.get('stateCode') or '', d.get('displayYear') or '')
                if not key[0] or key in _seen_series_keys:
                    continue
                _seen_series_keys.add(key)
                trend_data.append(d)
        # latest displayYear = the one matching the latest edition's end date
        latest_year = ''
        if latest and trend_data:
            for d in trend_data:
                if (d.get('sourceEndDate') or '') == (latest.get('endDate') or ''):
                    latest_year = d.get('displayYear') or ''
                    break
            if not latest_year:
                latest_year = max((d.get('displayYear') or '' for d in trend_data),
                                  key=lambda y: y)
        source = (td.get('measure') or {}).get('source') or {}
        if not source and trend_rows:
            # trend_rows is newest-methodology first; prefer the source of the
            # series that carries the latest year
            latest_source = next((row.get('source') for row in trend_rows
                                  if any((d.get('displayYear') or '') == latest_year
                                         for d in row.get('metricData') or [])), None)
            source = latest_source or (trend_rows[0].get('source') or {})
        src_years = latest_year
        citation = ''
        if source.get('displayName'):
            citation = (f"America's Health Rankings analysis of "
                        f"{source['displayName']}, United Health Foundation, "
                        f"AmericasHealthRankings.org, accessed 2026.")
        appears = []
        for rm in rms:
            rep = rm.get('report') or {}
            if rep.get('displayName'):
                appears.append({'edition': rep['displayName'],
                                'edition_id': rm.get('editionId')})
        category_name = next((c['label'] for c in nav
                              if any(o['value'] == slug for o in c.get('options', []))), None)
        m = Measure(
            slug=slug,
            metric_type_id=_text(md.get('metricTypeID')),
            display_name=md.get('displayName') or slug,
            description=_text(md.get('description')),
            unit=_text((td.get('measure') or {}).get('unitTypeDescription')),
            display_format=_text((td.get('measure') or {}).get('displayFormat')) or 'Numeric',
            precision=int((td.get('measure') or {}).get('precision') or 1),
            is_summation=bool((td.get('measure') or {}).get('isSummation')),
            category_id=cat_by_name[category_name].id if category_name in cat_by_name else None,
            population=_text((md.get('populationType') or {}).get('name') or ''),
            source_name=_text(source.get('displayName')),
            source_years=src_years,
            citation=citation,
            latest_year=latest_year,
            latest_edition_id=latest.get('editionId') if latest else None,
            display_order=order_by_slug.get(slug, 9999),
            about_why=_text(acc.get('phiWhyItMatters') or acc.get('htmlcontent')),
            about_who=_text(acc.get('phiWhoIsAffected')),
            about_works=_text(acc.get('phiWhatWorks')),
            about_goals=_text(acc.get('phiGoals')),
            about_references=_text(acc.get('phiBibliography')),
            appears_in=json.dumps(appears),
        )
        db.session.add(m)
        seen_slugs[slug] = m
        db.session.flush()
        # values + ranks per state per year (from the site's Trend2022 API)
        for d in trend_data:
            state_code = d.get('stateCode') or ''
            if not state_code:
                continue
            start, end = d.get('sourceStartDate') or '', d.get('sourceEndDate') or ''
            date_order = int(datetime.fromisoformat(end.replace('Z', '+00:00')).timestamp() // 1000000) if end else 0
            db.session.add(MeasureValue(
                measure_id=m.id, state_code=state_code,
                display_year=d.get('displayYear') or '',
                value=d.get('value'),
                value_display=_text(d.get('valueDisplay')),
                rank=d.get('rank'),
                source_end_date=end, date_order=date_order))
        # population dropdown options
        pos = 0
        for group in rec.get('populationOptions') or []:
            for opt in group.get('options', []):
                db.session.add(MeasureOption(
                    measure_id=m.id, group_label=group.get('label') or '',
                    option_label=opt.get('label') or '',
                    option_value=opt.get('value') or '',
                    position=pos))
                pos += 1
        # disparity sub-measures
        pos = 0
        for dp in md.get('disparities') or []:
            dm = dp.get('disparityMeasure') or {}
            dcat = dp.get('disparityCategory') or {}
            if isinstance(dcat, dict):
                dcat = dcat.get('name') or ''
            db.session.add(MeasureDisparity(
                measure_id=m.id, slug=dm.get('compareName') or '',
                display_name=dm.get('displayName') or '',
                metric_type_id=_text(dm.get('metricTypeID')),
                category=dcat,
                display_order=pos))
            pos += 1
        # additional measures
        for pos, am in enumerate(rec.get('additionalMeasuresData') or []):
            db.session.add(MeasureLink(
                measure_id=m.id, kind='additional',
                target_slug=am.get('value') or '',
                target_name=am.get('label') or '', position=pos))
        # related measures
        related = (about.get('relatedMeasures') or []) if about else []
        for pos, rm in enumerate(related):
            db.session.add(MeasureLink(
                measure_id=m.id, kind='related',
                target_slug=rm.get('compareName') or '',
                target_name=rm.get('displayName') or '', position=pos))
        # measure -> editions
        for rm in rms:
            db.session.add(MeasureEdition(
                measure_id=m.id, edition_id=rm.get('editionId') or 0,
                end_date=rm.get('endDate') or ''))
    # upstream-500 stub (linked from the directory like on the live site)
    for slug in upstream_error_slugs:
        if slug in seen_slugs:
            continue
        category_name = next((c['label'] for c in nav
                              if any(o['value'] == slug for o in c.get('options', []))), None)
        label = next((o['label'] for c in nav for o in c.get('options', [])
                     if o['value'] == slug), slug)
        m = Measure(slug=slug, display_name=label,
                    description='', category_id=cat_by_name[category_name].id
                    if category_name in cat_by_name else None,
                    display_order=order_by_slug.get(slug, 9999))
        db.session.add(m)
        seen_slugs[slug] = m

    db.session.flush()

    # ---- states ---------------------------------------------------------
    geo = _load(os.path.join(HARVEST, 'us_map_geometry.json'))
    states_json = _load_all(os.path.join(SCRAPE, 'states'))
    # state names from a measure page's impact data (stateName per code)
    state_names = {}
    for rec in measures_json.values():
        imp = ((rec.get('about') or {}).get('impactData') or {})
        for d in imp.get('metricData') or []:
            st = d.get('state') or {}
            if st.get('stateCode') and st.get('stateName'):
                state_names[st['stateCode']] = st['stateName']
        if len(state_names) >= 52:
            break
    for code, rec in states_json.items():
        name = state_names.get(code, code)
        sch = rec.get('stateSCHData') or {}
        db.session.add(StateGeo(
            code=code, name=name,
            dept_website=sch.get('stateDepartmentWebsite') or '',
            svg=(rec.get('state_svg') or '').replace('https://www.americashealthrankings.org', ''),
            map_path=geo.get('states', {}).get(code, ''),
            is_us=(code == 'ALL')))
        facts = []
        for pos, s in enumerate(sch.get('strengths') or []):
            facts.append(('strength', s, pos))
        for pos, c in enumerate(sch.get('challenges') or []):
            facts.append(('challenge', c, pos))
        for pos, h in enumerate(sch.get('highlights') or []):
            facts.append(('highlight', h, pos))
        for kind, item, pos in facts:
            db.session.add(StateFact(
                state_code=code, kind=kind, content=item.get('content') or '',
                measure_slug=item.get('compareName') or '',
                measure_name=item.get('displayName') or '',
                comparison_positive=item.get('comparisonPositive'),
                position=pos))

    # ---- per-state per-edition measure tables ---------------------------
    editions_json = _load_all(os.path.join(SCRAPE, 'state_editions'))
    for key, rec in editions_json.items():
        edition_id = rec.get('edition_id')
        state = rec.get('state')
        rep = ((rec.get('table') or {}).get('data') or {}).get('report') or {}
        # impact weights/direction per measure from the site's CoreMeasuresImpact API
        impact_info = {}
        imp_rep = (((rec.get('impact') or {}).get('data') or {}).get('report') or {})
        for irm in imp_rep.get('reportMeasures') or []:
            imref = irm.get('measure') or {}
            islug = imref.get('compareName') or ''
            weight = irm.get('weight')
            direction = 1 if imref.get('isWeightPositive') == 'Y' else -1
            if islug and weight is not None:
                impact_info[islug] = (weight, direction)
        for rm in rep.get('reportMeasures') or []:
            mref = rm.get('measure') or {}
            cat = (rm.get('metricCategory') or {}).get('displayName') or ''
            mdata = mref.get('metricData') or []
            latest_datum = None
            if mdata:
                latest_datum = max(
                    mdata,
                    key=lambda d: d.get('sourceEndDate') or '')
            if latest_datum is None:
                continue
            db.session.add(EditionMeasureState(
                edition_id=edition_id, state_code=state,
                measure_slug=mref.get('compareName') or '',
                measure_name=mref.get('displayName') or '',
                category=cat,
                value=latest_datum.get('value'),
                value_display=_text(latest_datum.get('valueDisplay')),
                rank=latest_datum.get('rank'),
                score=latest_datum.get('score'),
                is_core=rm.get('isCoreMeasure') or 'C',
                display_order=rm.get('displayOrder') or 0,
                unit=_text(mref.get('unitTypeDescription')),
                description=_text(mref.get('description')),
                is_summation=bool(mref.get('isSummation')),
                impact_score=None,
                contribution=_contribution(impact_info, mref, latest_datum)))

    # ---- reports + sections ---------------------------------------------
    reports_json = _load_all(os.path.join(SCRAPE, 'reports'))
    for slug, rec in reports_json.items():
        sections = rec.get('sections') or []
        main = next((s for s in sections if s.get('slug') == slug), None)
        others = [s for s in sections if s.get('slug') != slug]
        if main is None:
            continue
        pub = _published_label(main.get('date'))
        db.session.add(Report(
            slug=slug, title=main.get('title') or slug,
            excerpt=_text(main.get('excerpt')), published=pub,
            date=(main.get('date') or '')[:10],
            edition_id=main.get('editionId'),
            menu_order=main.get('menuOrder') or 9999,
            featured=bool(main.get('featured')),
            explorable=bool(main.get('explorable')),
            parent_slug=None,
            attachments=json.dumps(main.get('attachments') or [])))
        db.session.add(ReportSection(
            report_slug=slug, slug=slug,
            title=main.get('title') or slug,
            subtitle=_text(main.get('subTitle')),
            excerpt=_text(main.get('excerpt')),
            content_html=_text(main.get('contentHtml')),
            parent_slug=None,
            menu_order=main.get('menuOrder') or 0,
            featured=bool(main.get('featured')),
            attachments=json.dumps(main.get('attachments') or [])))
        for s in others:
            db.session.add(ReportSection(
                report_slug=slug, slug=s.get('slug') or '',
                title=s.get('title') or '',
                subtitle=_text(s.get('subTitle')),
                excerpt=_text(s.get('excerpt')),
                content_html=_text(s.get('contentHtml')),
                parent_slug=s.get('parent', {}).get('slug') if s.get('parent') else None,
                menu_order=s.get('menuOrder') or 0,
                featured=bool(s.get('featured')),
                attachments=json.dumps(s.get('attachments') or [])))

    # ---- articles ---------------------------------------------------------
    articles_json = _load_all(os.path.join(SCRAPE, 'articles'))
    pos = 0
    for slug in sorted(articles_json.keys()):
        rec = articles_json[slug]
        d = rec.get('data') or {}
        images = rec.get('images') or []
        img = images[0] if images else {}
        date = d.get('date') or ''
        pub = _published_label(date)
        db.session.add(Article(
            slug=slug, title=d.get('title') or slug,
            author_name=d.get('author_name') or '',
            published=pub, date=date[:10],
            excerpt=_text(d.get('excerpt')),
            body_html=rec.get('body_html') or '',
            image_url=img.get('url') or '',
            image_alt=img.get('alt') or '',
            position=pos))
        pos += 1

    # ---- topics / faq / static pages / homepage blocks --------------------
    topics = _load(os.path.join(HARVEST, 'topics.json'))
    for pos, tp in enumerate(topics):
        db.session.add(Topic(tid=tp['id'], title=tp['title'],
                             description=tp['description'], href=tp['href'],
                             position=pos))
    faqs = _load(os.path.join(HARVEST, 'faqs.json'))
    for pos, f in enumerate(faqs):
        db.session.add(FaqItem(question=f['q'], answer_html=f['a_html'],
                               position=pos))
    meth = open(os.path.join(HARVEST, 'methodology_main.html'),
                encoding='utf-8').read()
    db.session.add(StaticPage(key='methodology', title='Data Sources', html=meth))
    pubshub = open(os.path.join(HARVEST, 'publications_main.html'),
                   encoding='utf-8').read()
    db.session.add(StaticPage(key='publications', title='Publications', html=pubshub))

    layout = _load(os.path.join(SCRAPE, 'homepage_layout.json'))
    for pos, block in enumerate(layout):
        db.session.add(HomeBlock(block_type=block.get('blockType') or '',
                                 position=pos,
                                 data=json.dumps(block, default=str)))

    db.session.commit()


def _contribution(impact_info, mref, datum):
    """weight x z-score x direction = contribution to the state's overall score."""
    slug = mref.get('compareName') or ''
    weight, direction = impact_info.get(slug, (None, 1))
    z = datum.get('score')
    if weight is None or z is None or mref.get('isSummation'):
        return None
    return weight * z * direction


def _published_label(iso):
    """'2026-01-08T05:00:00.000Z' -> 'January 2026'."""
    if not iso:
        return ''
    m = re.match(r'(\d{4})-(\d{2})', iso)
    if not m:
        return ''
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
              'August', 'September', 'October', 'November', 'December']
    return f"{months[int(m.group(2)) - 1]} {m.group(1)}"


def seed_benchmark_users(db, User, Bookmark, ReadingHistory, bcrypt):
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    USERS = [
        {'name': 'Alice Johnson', 'email': 'alice.j@test.com'},
        {'name': 'Bob Chen', 'email': 'bob.c@test.com'},
        {'name': 'Carol Davis', 'email': 'carol.d@test.com'},
        {'name': 'David Kim', 'email': 'david.k@test.com'},
    ]
    PASSWORD = 'TestPass123!'
    # Fixed-salt bcrypt hash so re-seeding is byte-identical (the random
    # gensalt() default would change the DB bytes on every seed run).
    PASSWORD_HASH = ('$2b$12$C1UoOqH9zW3kV2sE8yJ7Ne'
                     '/iPilks4a8N9cpu0.AGHnbFLbYr0aUK')
    for idx, u in enumerate(USERS):
        user = User(email=u['email'], name=u['name'])
        user.password_hash = PASSWORD_HASH
        db.session.add(user)
        db.session.flush()
        # a few saved measures/states and browsing history per user
        seeds = [
            ('measure', 'Obesity', 'Obesity'),
            ('measure', 'mental_distress', 'Frequent Mental Distress'),
            ('state', 'CA', 'California'),
        ]
        for kind, slug, title in seeds[: 2 + (idx % 2)]:
            db.session.add(Bookmark(user_id=user.id, kind=kind, item_slug=slug,
                                    title=title))
        db.session.add(ReadingHistory(
            user_id=user.id, url='/explore/measures/Obesity',
            title='Obesity in United States'))
    db.session.commit()
