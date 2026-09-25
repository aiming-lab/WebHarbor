"""Bind recorder-observed DOM to exact same-origin routes and task entities."""
from urllib.parse import urlsplit, unquote, parse_qs
from answers import norm


def observations(traj):
    base = urlsplit(traj.get('start_url', ''))
    if base.scheme not in ('http', 'https') or not base.netloc:
        return []
    out = []
    for step in traj.get('steps', []):
        url = urlsplit(str(step.get('url', '')))
        if (url.scheme, url.netloc) != (base.scheme, base.netloc):
            continue
        text = step.get('page_text') or step.get('observed_text') or step.get('observed_text_before') or ''
        if text:
            out.append((unquote(url.path).rstrip('/') or '/', parse_qs(url.query), norm(text)))
    return out


def navigation_ok(index, traj, before, after, ctx):
    obs = observations(traj)
    def page(path, *tokens):
        return any(p == path and all(norm(t) in text for t in tokens) for p, _, text in obs)
    def listing(**filters):
        for p, q, text in obs:
            if not (p == '/store' or p.startswith('/store/')) or 'wine access store' not in text or 'selections' not in text:
                continue
            values = {k: norm(v[-1]) for k, v in q.items()}
            if p == '/store/sparkling': values['type'] = 'sparkling'
            if p == '/store/regions/italy': values['region'] = 'italy'
            if all(v in values.get(k, '') for k, v in filters.items()): return True
        return False
    def detail(wine, *tokens):
        return any(p in ('/wine/' + wine['slug'], '/catalog/' + wine['slug']) and norm(wine['name']) in text and all(norm(t) in text for t in tokens) for p, _, text in obs)
    def wine(fragment):
        return next(w for w in before['wines'].values() if fragment in w['slug'])
    def account(email):
        u = next(u for u in after['users'].values() if u['email'] == email)
        return page('/account', email, u['display_name'])
    def cart(): return page('/cart', 'Your Cart', 'Order Summary')
    # Login is not compulsory padding: an authenticated account/cart outcome is
    # sufficient, while account-specific reads must identify the requested user.
    ids = ctx.get('wine_ids', [])
    if index in {0, 1, 7, 13}:
        if not ids or not listing() or not all(detail(before['wines'][wid]) for wid in ids): return False
        if index == 1:
            return any(p == '/saved' and 'saved cellar' in text and all(norm(before['wines'][wid]['name']) in text for wid in ids) for p, _, text in obs)
        if index == 13:
            return page('/register', 'Create a Wine Access account') and cart() and page('/checkout', 'Shipping', 'Payment')
        return cart()
    if index == 2:
        return all(detail(wine(slug), 'Drinking Window') for slug in ('2022-dumol', '2022-fantesca'))
    if index == 3:
        return listing() and detail(wine('2015-chateau-haut-brion'), '100 points', 'Pessac-Leognan', '$950')
    if index == 4:
        # Both Champagne candidates may be compared on the filtered result page;
        # opening both details is a valid alternative, not a mandatory extra step.
        champs = [w for w in before['wines'].values() if w['wine_type'] == 'Sparkling' and w['region'] == 'Champagne']
        seen = all(any(norm(w['name']) in text and (p.startswith('/store') or p in ('/wine/' + w['slug'], '/catalog/' + w['slug'])) for p, _, text in obs) for w in champs)
        return listing(type='sparkling') and seen and detail(wine('m-brugnon'), 'Pairings') and cart()
    if index == 5:
        return account('alice.j@test.com')
    if index == 6:
        # The visible account identity and account's order number bind Bob's read.
        bob = next(u for u in before['users'].values() if u['email'] == 'bob.c@test.com')
        order = max((o for o in before['orders'].values() if o['user_id'] == bob['id']), key=lambda o: o['placed_at'])
        return any(p in ('/orders', '/orders/' + order['order_number']) and norm(order['order_number']) in text and norm(order['tracking_number']) in text and norm(bob['display_name'].split()[0]) in text for p, _, text in obs)
    if index == 8:
        return listing() and detail(wine('2021-pas-de-cheval-cabernet-sauvignon-prelude-oakville'), 'Drinking Window')
    if index == 9:
        return all(detail(wine(slug), 'per bottle by the case') for slug in ('2021-le-pich', '2021-bank-shot'))
    if index == 10:
        return page('/club', 'Connoisseurs') and page('/club/connoisseurs', 'Connoisseurs Club') and account('carol.d@test.com') and page('/account', 'carol.d@test.com', 'Connoisseurs Club', 'Active')
    if index == 11:
        order = ctx['order']
        items = [i for i in before['order_items'].values() if i['order_id'] == order['id']]
        return (account('alice.j@test.com')
                and page('/orders/' + order['order_number'], order['order_number'], 'Total', f"${order['total']:.2f}",
                         *(f"{i['quantity']} bottle(s)" for i in items), *(i['wine_name'] for i in items))
                and page('/contact-us', '122 Camino Oruga', 'Building A', '94558', '(866) 946-3923'))
    if index == 12:
        return listing(q='burgundy') and all(detail(wine(slug), 'Drinking Window') for slug in ('2017-maison-leroy-nuits', '2017-maison-leroy-gevrey', '2021-domaine-du-clos-de-tart'))
    if index == 14:
        return cart()
    if index == 15:
        # Country may be a category, query filter, or an explicit Italy search.
        italy = listing(region='italy') or listing(q='italy')
        return italy and detail(wine('2024-etna-bianco'), 'Pairings')
    if index == 16:
        order = ctx.get('order', {})
        return cart() and page('/checkout', 'Shipping', 'Payment') and page('/orders/' + order.get('order_number', ''), order.get('order_number', ''), 'Processing', 'Ship to', 'Total')
    if index == 17:
        return (page('/where-we-ship', 'Weather Holds', 'heat or cold', 'delay shipping', 'adult-signature')
                and all(page('/club/' + slug, name, terms) for slug, name, terms in (
                    ('discovery', 'Discovery Club', '4 bottles / Quarterly / $110 per shipment'),
                    ('connoisseurs', 'Connoisseurs Club', '2 bottles / Quarterly / $150 per shipment'))))
    return False
