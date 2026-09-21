"""Exact run-local SQLite transitions; unrelated rows are immutable."""
import copy
import sqlite3
from pathlib import Path


def read_db(path):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        if not {'wines', 'users', 'cart_items', 'orders', 'order_items'} <= set(tables):
            raise ValueError('not a WineAccess snapshot')
        return {name: {r['id']: dict(r) for r in con.execute('SELECT * FROM "' + name.replace('"', '""') + '"')} for name in tables}


def user_id(db, email):
    return next(r['id'] for r in db['users'].values() if r['email'].lower() == email)


def qualifying(index, w):
    if index == 0:
        return w['variety'] == 'Cabernet Sauvignon' and w['region'] == 'Napa Valley' and w['price'] < 50
    if index == 1:
        return w['variety'] == 'Pinot Noir' and w['region'] == 'Sonoma Coast' and w['score'] >= 94
    if index == 4:
        return w['slug'] == 'm-brugnon-selection-brut-champagne'
    if index == 7:
        return w['country'] == 'France' and w['wine_type'] == 'White' and w['score'] >= 94
    if index == 13:
        return w['wine_type'] == 'Red' and 'blend' in w['variety'].lower() and w['price'] < 30
    return False


def transition(index, before, after):
    expected = copy.deepcopy(before)
    ctx = {'wine_ids': [], 'user_id': None}
    if index not in {0, 1, 4, 5, 7, 10, 13, 14, 16}:
        return before == after, 'read_only_state', ctx
    email = 'carol.d@test.com' if index == 10 else 'david.k@test.com' if index == 14 else 'alice.j@test.com'
    uid = user_id(before, email)
    if index == 13:
        new_users = set(after['users']) - set(before['users'])
        if len(new_users) != 1:
            return False, 'one_new_account_required', ctx
        uid = next(iter(new_users))
        row = after['users'][uid]
        if not row['email'] or '@' not in row['email'] or not row['username'] or not row['display_name'] or not row['password_hash']:
            return False, 'invalid_new_account', ctx
        expected['users'][uid] = row.copy()
    ctx['user_id'] = uid
    if index in {0, 4, 7, 13}:
        changed = [k for k in set(before['cart_items']) | set(after['cart_items']) if before['cart_items'].get(k) != after['cart_items'].get(k)]
        if len(changed) != 1:
            return False, 'one_cart_line_change_required', ctx
        k = changed[0]
        row, old = after['cart_items'].get(k), before['cart_items'].get(k)
        if not row or row['user_id'] != uid or row['wine_id'] not in before['wines'] or not qualifying(index, before['wines'][row['wine_id']]):
            return False, 'wrong_cart_product_or_owner', ctx
        amount = 2 if index == 7 else 1
        if index in {4, 13}:
            amount = row["quantity"] - (old["quantity"] if old else 0)
            if not isinstance(amount, int) or amount < 1 or row["quantity"] > 24:
                return False, "positive_cart_addition_required", ctx
        target = dict(old, quantity=old['quantity'] + amount) if old else {'id': k, 'user_id': uid, 'wine_id': row['wine_id'], 'quantity': amount}
        if row != target:
            return False, 'wrong_cart_quantity_or_identity', ctx
        expected['cart_items'][k] = target
        ctx['wine_ids'] = [row['wine_id']]
    elif index == 1:
        added = set(after['wishlist_items']) - set(before['wishlist_items'])
        if len(added) != 1:
            return False, 'one_saved_wine_required', ctx
        k = next(iter(added)); row = after['wishlist_items'][k]
        if row['user_id'] != uid or not qualifying(index, before['wines'][row['wine_id']]) or row['note'] not in ('', None):
            return False, 'wrong_saved_wine', ctx
        if any(r['user_id'] == uid and r['wine_id'] == row['wine_id'] for r in before['wishlist_items'].values()):
            return False, 'already_saved', ctx
        expected['wishlist_items'][k] = row.copy(); ctx['wine_ids'] = [row['wine_id']]
    elif index == 5:
        if before['users'][uid]['favorite_variety'] == 'Pinot Noir':
            return False, 'preference_already_set', ctx
        expected['users'][uid]['favorite_variety'] = 'Pinot Noir'
    elif index == 10:
        cid = next(r['id'] for r in before['clubs'].values() if r['slug'] == 'connoisseurs')
        added = set(after['club_memberships']) - set(before['club_memberships'])
        if len(added) != 1 or any(r['user_id'] == uid and r['club_id'] == cid for r in before['club_memberships'].values()):
            return False, 'one_new_membership_required', ctx
        k = next(iter(added))
        expected['club_memberships'][k] = {'id': k, 'user_id': uid, 'club_id': cid, 'status': 'Active', 'next_ship_date': 'June 18, 2026'}
    elif index == 14:
        removed = set(before['cart_items']) - set(after['cart_items'])
        if len(removed) != 1 or before['cart_items'][next(iter(removed))]['user_id'] != uid:
            return False, 'one_owned_cart_line_must_be_removed', ctx
        del expected['cart_items'][next(iter(removed))]
        def total(db):
            subtotal = sum(r['quantity'] * db['wines'][r['wine_id']]['price'] for r in db['cart_items'].values() if r['user_id'] == uid)
            return round(subtotal + (0 if subtotal == 0 or subtotal >= 150 else 19.95) + round(subtotal * .0825, 2), 2)
        ctx['old_total'], ctx['new_total'] = total(before), total(expected)
    elif index == 16:
        cart = [r for r in before['cart_items'].values() if r['user_id'] == uid]
        added = set(after['orders']) - set(before['orders'])
        if not cart or len(added) != 1:
            return False, 'one_order_from_nonempty_cart_required', ctx
        oid = next(iter(added)); user = before['users'][uid]
        subtotal = sum(r['quantity'] * before['wines'][r['wine_id']]['price'] for r in cart)
        shipping = 0 if subtotal >= 150 else 19.95
        tax = round(subtotal * .0825, 2)
        order = {'id': oid, 'user_id': uid, 'order_number': f'WA-260520-{uid}{len(before["orders"])+1:03d}', 'status': 'Processing', 'placed_at': '2026-05-20 09:00:00.000000', 'subtotal': subtotal, 'shipping': shipping, 'tax': tax, 'total': round(subtotal + shipping + tax, 2), 'tracking_number': 'Pending cellar release', 'ship_to': ', '.join(user[k] for k in ('address_line1', 'city', 'state', 'zip_code'))}
        expected['orders'][oid] = order
        new_items = set(after['order_items']) - set(before['order_items'])
        if len(new_items) != len(cart):
            return False, 'order_items_must_match_initial_cart', ctx
        remaining = list(new_items)
        for item in cart:
            wine = before['wines'][item['wine_id']]
            match = next((k for k in remaining if after['order_items'][k]['wine_id'] == item['wine_id']), None)
            if match is None:
                return False, 'order_wine_missing', ctx
            remaining.remove(match)
            expected['order_items'][match] = {'id': match, 'order_id': oid, 'wine_id': wine['id'], 'wine_name': wine['name'], 'quantity': item['quantity'], 'unit_price': wine['price']}
            expected['wines'][wine['id']]['inventory'] = max(0, wine['inventory'] - item['quantity'])
            del expected['cart_items'][item['id']]
        ctx['order'] = order
    ok = expected == after
    return ok, 'exact_state_transition' if ok else 'unexpected_database_changes', ctx
