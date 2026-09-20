"""Task-specific predicates. Facts come from the supplied initial snapshot.

Blackwell generation/Marketplace facts are the reviewed offline reference in
README.md; no new application model is required for those static pages.
"""
import re

import answers as a
from verify_lib import InfraError, delta, preserved, require, row_counter

G = 'geforce-rtx-'
NANO = 'jetson-orin-nano-super'
NX = 'jetson-orin-nx'
PRO = 'rtx-pro-6000-blackwell'
NEWS = 'blackwell-mlperf-training-6-0'
EMAIL = 'alice.j@test.com'


def one(rows, description):
    if len(rows) != 1:
        raise InfraError('missing/ambiguous ' + description)
    return rows[0]


def minimum(ctx, series=None, memory=None):
    candidates = [p for p in ctx.before['products'] if p['category'] == 'GeForce Gaming' and
                  (not series or p['series'] == series) and
                  (memory is None or (p['memory_gb'] or 0) >= memory) and
                  type(p['price_usd']) is int]
    if not candidates:
        raise InfraError('catalog lacks eligible products')
    price = min(p['price_usd'] for p in candidates)
    return one([p for p in candidates if p['price_usd'] == price], 'lowest-price product')


def driver_evidence(ctx, target):
    """Target-row evidence for T9/T10.

    The question names a product series, so a results page must scope itself to that
    series: branch and OS may stay unset (a broad search that still displays the
    requested row is valid), but a query that never pins the series is not evidence
    for it (audit NVIDIA--9 / --10: low). The target row's own detail page is
    sufficient on its own.
    """
    for path, q in ctx.pages:
        if path == f"/drivers/{target['id']}":
            return True
        if path != '/drivers':
            continue
        if q.get('series', [''])[0] != target['product_series']:
            continue
        if all(q.get(key, [''])[0] in ('', target[column]) for key, column in
               [('branch', 'branch'), ('os', 'os')]):
            return True
    return False


def news_evidence(ctx, article):
    """Article/date evidence for T18.

    The rubric accepts "Relevant article, Newsroom listing or search result that
    includes the Blackwell MLPerf Training 6.0 article and date", so the listing and
    the app's search route stay valid. A search query must carry at least one word
    token that actually occurs in the article; a numeric-only query (the "0" of
    "6.0") no longer counts as having found it (audit NVIDIA--18: low).
    """
    for path, q in ctx.pages:
        if path == '/news/' + article['slug']:
            return True
        if path == '/news' and q.get('category', [''])[0] in ('', article['category']):
            return True  # The list visibly includes each article's publication date.
        if path == '/search':
            words = [t for t in re.findall(r'[a-z0-9]+', q.get('q', [''])[0].lower())
                     if len(t) >= 3 and not t.isdigit()]
            haystack = ' '.join(str(article[k]) for k in ('title', 'category', 'author', 'excerpt', 'body')).lower()
            if words and any(word in haystack for word in words):
                return True  # App search uses token overlap, not strict AND.
    return False


def target_answer(text, model):
    found = a.models(text)
    return not found or all(m == model for m in found)


def driver_qualifier_scope(text):
    """Negation-only view for a narrow historical-catalog qualification.

    Never remove a sentence or any version/branch/OS text. Only the negative
    token in a fully recognized non-live-feed phrase is exempted; every other
    denial/uncertainty remains. Full original text still goes to fact checks.
    """
    if not re.search(r'\b(?:frozen|historical|fixed|snapshot)\b', text):
        return text
    if not re.search(r'\b(?:catalog|catalogue|snapshot)\b', text):
        return text
    phrase = (r"\b(?P<negative>not|isn't|aren't)\s+(?:(?:a|an|the)\s+)?"
              r'(?:live|real[- ]time|realtime)\s+(?:driver\s+)?'
              r'(?:release\s+)?(?:feed|catalog|catalogue)\b')
    return re.sub(phrase, lambda m: m.group().replace(m['negative'], '', 1), text)


def information(ctx):
    n, answer = ctx.number, ctx.answer
    require(bool(answer.strip()), 'final answer is empty')
    preserved(ctx)
    # Do not accept a denial or unresolved guess as an asserted fact. Benign
    # contrasts (another model, an unrelated metric, a live-feed note, a
    # variant name) are exempted first; a denial of the target value is not.
    if n not in (5, 11):
        negation_view = a.strip_harmless_contrasts(a.norm(answer))
        if n in (9, 10):
            negation_view = driver_qualifier_scope(negation_view)
        require(not re.search(r"\b(?:not|neither|maybe|perhaps|unknown|isn't|aren't)\b", negation_view),
                'answer is negated, uncertain or contradictory')
    if n in (0, 1, 2):
        slug = G + {0: '5090', 1: '5080', 2: '4090'}[n]
        p = ctx.product(slug)
        require(ctx.specs(slug), 'missing relevant product specifications')
        model = slug.removeprefix(G)
        if n == 0:
            check = lambda t: a.memory(t, p['memory_gb'], p['memory_type'])
        elif n == 1:
            check = lambda t: a.single_measure(t, p['cuda_cores'], 'cuda')
        else:
            check = lambda t: a.single_measure(t, p['tdp_watts'], 'power')
        ok = a.segment_ok(answer, lambda name: a.names_model(name, model), [check])
    elif n == 3:
        p = minimum(ctx, series='RTX 50 Series')
        group = [p['slug'] for p in ctx.before['products'] if p['series'] == 'RTX 50 Series']
        require(ctx.listing('geforce-gaming', 'RTX 50 Series') or ctx.compare(group) or
                all(ctx.detail(s) for s in group) or ctx.buying(),
                'missing RTX 50 price comparison evidence')
        ok = a.segment_ok(answer, lambda name: a.names_model(name, '5060') and 'ti' not in name,
                          [lambda t: a.price(t, p['price_usd'])])
        # The question asks which card is least expensive, so the answer must name the
        # model as well as its price; a bare price is half an answer (audit NVIDIA--3: low).
        ok = ok and bool(a.models(answer))
        ok = ok and not re.search(r'\b(?:most\s+expensive|priciest|highest[- ]priced)\b', a.norm(answer))
    elif n == 4:
        p = one([p for p in ctx.before['products'] if p['category'] == 'Data Center' and p['memory_gb'] == 141], '141GB GPU')
        require(ctx.specs(p['slug']), 'missing 141GB GPU specification evidence')
        if a.measurements(answer, 'memory'):
            def t4_memory(t, whole=answer):
                return a.memory(t, 141) if a.measurements(t, 'memory') else a.memory(whole, 141)
            ok = a.segment_ok(answer, lambda name: a.names_model(name, 'h200'),
                              [lambda t: a.only_model(t, 'h200'), t4_memory])
        else:
            ok = a.segment_ok(answer, lambda name: a.names_model(name, 'h200'),
                              [lambda t: a.only_model(t, 'h200')])
    elif n == 5:
        # The rubric requires specifications for BOTH Jetson products and fails
        # one-product-only evidence, so a single detail page is no longer enough
        # (audit NVIDIA--5: low); a comparison of both products or both detail pages is.
        require(ctx.compare([NANO, NX]) or (ctx.detail(NANO) and ctx.detail(NX)),
                'missing specifications for both Jetson products')
        # These targets are explicitly the reviewed kit/module variants.
        if ctx.product(NANO)['memory_gb'] != 8 or ctx.product(NX)['memory_gb'] != 16:
            raise InfraError('Jetson reference variant changed; review task contract')
        ok = a.jetson_compare(answer)
    elif n == 6:
        require(ctx.compare([G+'5090', G+'4090']), 'comparison must include both requested GPUs')
        difference = ctx.product(G+'5090')['cuda_cores'] - ctx.product(G+'4090')['cuda_cores']
        ok = a.cuda_compare(answer, difference)
    elif n == 7:
        require(ctx.specs(G+'5080') and ctx.specs(G+'4080-super'), 'both bandwidth specifications required')
        higher = a.bandwidth_values(ctx.product(G+'5080')['memory_bandwidth'])[0]
        lower = a.bandwidth_values(ctx.product(G+'4080-super')['memory_bandwidth'])[0]
        ok = a.bandwidth_comparison(answer, higher, lower)
    elif n == 8:
        rows = [p for p in ctx.before['products'] if p['category'] == 'Studio / Professional']
        if not rows:
            raise InfraError('no professional GPUs')
        p = one([p for p in rows if p['memory_gb'] == max(x['memory_gb'] or 0 for x in rows)], 'maximum-memory GPU')
        require(ctx.specs(p['slug']), 'missing maximum-memory product specifications')
        slugs = [x['slug'] for x in rows]
        others = [s for s in slugs if s != p['slug']]
        # "most memory of all" needs a visible basis: compare against another
        # candidate, or details covering more than the target alone.
        require(any(ctx.compare([p['slug'], o]) for o in others) or
                all(ctx.detail(s) for s in slugs) or
                (ctx.detail(p['slug']) and any(ctx.detail(s) for s in others)),
                'missing maximum-memory comparison evidence')
        ok = a.segment_ok(answer, lambda name: a.names_model(name, 'pro 6000'),
                          [lambda t: (a.only_model(t, 'pro 6000 blackwell') or a.only_model(t, 'pro 6000'))
                           and a.memory(t, p['memory_gb'])])
    elif n in (9, 10):
        series = 'GeForce RTX 50 Series' if n == 9 else 'GeForce RTX 40 Series'
        branch = 'Game Ready' if n == 9 else 'Studio'
        candidates = [d for d in ctx.before['drivers'] if d['product_series'] == series and d['branch'] == branch and d['os'] == 'Windows 11']
        if not candidates:
            raise InfraError('missing requested driver')
        latest = max(d['released'] for d in candidates)
        d = one([d for d in candidates if d['released'] == latest], 'latest driver')
        require(driver_evidence(ctx, d), 'no result/detail displaying requested driver')
        view = a.strip_harmless_contrasts(a.norm(answer))
        ok = a.version(view, d['version'])
        wrong_branch = 'studio' if n == 9 else 'game ready'
        ok = ok and wrong_branch not in view
        ok = ok and not re.search(r'\b(?:windows\s*10|linux|rtx\s*(?:30|' + ('40' if n == 9 else '50') + r')\s*series)\b', view)
        # Any OS explicitly named must be the requested Windows 11.
        os_claims = re.findall(r'\bwindows\s*(\d+)', view)
        ok = ok and all(value == '11' for value in os_claims)
    elif n == 11:
        require(any(path == '/geforce/graphics-cards/50-series' for path, _ in ctx.pages), 'missing RTX 50 architecture/technology page')
        require(any(path == '/where-to-buy/' + G+'5080' for path, _ in ctx.pages), 'missing RTX 5080 buying information')
        require(ctx.final is not None and ctx.final[0] == '/where-to-buy/' + G+'5080', 'must stop on local RTX 5080 buying information')
        # The named region/locale must not be contradicted elsewhere in the answer.
        require(not re.search(r'\b(?:germany|canada|united\s+kingdom|uk|china|japan|france|'
                              r'en[- ](?:ca|gb|de|cn|jp|fr))\b',
                              a.strip_harmless_contrasts(a.norm(answer))),
                'contradictory buying region claim')
        ok = a.blackwell_buying(answer)
    elif n == 18:
        article = one([r for r in ctx.before['articles'] if r['slug'] == NEWS], 'MLPerf article')
        require(news_evidence(ctx, article), 'missing relevant article/date evidence')
        ok = a.publication_date(answer, article['published'])
    else:
        raise InfraError('unknown information task')
    require(ok, 'answer facts, units, object, relationship or date do not match')
    return ['Relevant local page/object evidence', 'Normalized task-specific facts', 'Protected state preserved']


def state(ctx):
    n = ctx.number
    if n == 19:
        preserved(ctx, 'newsletter')
        added, removed, modified = delta(ctx, 'newsletter')
        require(not removed and not modified and len(added) == 1, 'must add exactly one subscription and preserve existing rows')
        require(a.norm(added[0]['email']) == 'gamer42@example.com', 'wrong subscription email')
        # The subscription is the site's GeForce newsletter list; the row's topic is
        # part of the requested state (audit NVIDIA--19: low).
        require(a.norm(added[0]['topic'] or '') == 'geforce', 'newsletter topic must be the GeForce list')
        require(not any(a.norm(r['email']) == 'gamer42@example.com' for r in ctx.before['newsletter']), 'subscription already existed')
        return ['New target subscription; existing state preserved']
    user = one([r for r in ctx.before['users'] if r['email'] == EMAIL], 'seeded Alice account')
    uid = user['id']
    if n in (12, 13, 16, 17):
        preserved(ctx, 'wishlist_items')
        slug = {12: G+'4060', 13: G+'5070-ti', 16: PRO, 17: G+'5060-ti'}[n]
        p = ctx.product(slug)
        if n in (12, 17):
            selected = minimum(ctx, series='RTX 40 Series' if n == 12 else None, memory=16 if n == 17 else None)
            if selected['id'] != p['id']:
                raise InfraError('frozen catalog selection changed; review task mapping')
        added, removed, modified = delta(ctx, 'wishlist_items')
        target = lambda r: r['user_id'] == uid and r['product_id'] == p['id']
        if n == 16:
            require(not added and not modified and len(removed) == 1 and target(removed[0]), 'must remove only Alice target wishlist row')
            require(sum(r['user_id'] == uid for r in ctx.before['wishlist_items']) > 1, 'initial wishlist precondition missing')
            require(not any(target(r) for r in ctx.after['wishlist_items']), 'target still in wishlist')
        else:
            require(not removed and not modified and len(added) == 1 and target(added[0]), 'must add only one Alice target wishlist row')
            require(not any(target(r) for r in ctx.before['wishlist_items']), 'target already existed; no requested addition')
        # DB is authoritative. No login/account/wishlist click sequence is needed.
        return ['Exact Alice wishlist row delta', 'Other wishlist and protected state preserved']
    if n == 14:
        preserved(ctx, 'users')
        added, removed, modified = delta(ctx, 'users')
        require(not added and not removed and modified == [uid], 'only Alice profile may change')
        after = one([r for r in ctx.after['users'] if r['id'] == uid], 'after Alice account')
        require(a.norm(after['country'] or '') == 'germany' and a.norm(user['country'] or '') != 'germany', 'country must change to Germany')
        require(row_counter([user], ('country',)) == row_counter([after], ('country',)), 'unrequested profile field changed')
        return ['Alice country changed to Germany; all other fields preserved']
    if n == 15:
        preserved(ctx, 'reviews')
        added, removed, modified = delta(ctx, 'reviews')
        require(not removed and not modified and len(added) == 1, 'must add one review and preserve all existing reviews')
        r = added[0]
        p = ctx.product(NANO)
        require(r['user_id'] == uid and r['product_id'] == p['id'], 'wrong review account/product')
        require(type(r['rating']) is int and r['rating'] == 5, 'review must be five stars')
        require(a.norm(r['title'] or '') == 'incredible', 'review title must equal Incredible')
        require(bool((r['body'] or '').strip()), 'review body missing')
        require(not any(x['user_id'] == uid and x['product_id'] == p['id'] for x in ctx.before['reviews']), 'Alice already reviewed this product')
        return ['Single new Alice Jetson review, rating 5, exact normalized title', 'Existing reviews/state preserved']
    raise InfraError('unknown state task')


def grade(ctx):
    return state(ctx) if ctx.number in (12, 13, 14, 15, 16, 17, 19) else information(ctx)
