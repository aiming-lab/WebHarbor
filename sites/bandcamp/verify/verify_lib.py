#!/usr/bin/env python3
"""Snapshot-only grading. Healthy task failures are distinct from input errors."""
import argparse
from collections import Counter
from contextlib import closing
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import parse_qs, urlsplit

TASK_COUNT = 18
STATEFUL_TASKS = {3, 4, 7, 8}
# Every business column participates in equality, including unqueried fields.
COLUMNS = {
    'album_tags': 'album_id tag_id',
    'albums': 'id artist_id label_id primary_genre_id scene_id title slug description story cover_image header_image price release_date track_count duration_seconds fan_count catalog_no is_featured is_new is_editorial',
    'artists': 'id name slug location bio headline formed_year follow_count avatar_image hero_image scene_id label_id primary_genre_id',
    'cart_items': 'id user_id album_id merch_item_id format_variant_id quantity added_at',
    'fan_collection_items': 'id user_id album_id format_variant_id favorite_track_id acquired_via notes added_at',
    'fan_comments': 'id user_id album_id track_id headline body rating created_at',
    'format_variants': 'id album_id merch_item_id kind name option_a option_b price inventory sku shipping_note edition_note is_default',
    'genres': 'id name slug description accent_color',
    'labels': 'id name slug location description',
    'merch_items': 'id artist_id album_id title slug item_type description short_blurb image price inventory release_date is_featured',
    'order_items': 'id order_id album_id merch_item_id format_variant_id title artist_name image_path variant_label quantity unit_price',
    'orders': 'id user_id order_number status subtotal shipping tax total shipping_name shipping_line1 shipping_city shipping_country payment_label note placed_at',
    'scenes': 'id name slug country description',
    'tags': 'id name slug',
    'tracks': 'id album_id title slug track_number duration_seconds preview_hook lyrics_excerpt is_focus_track',
    'users': 'id username email password_hash display_name bio city country address_line1 postal_code favorite_format favorite_scene_id created_at',
    'wishlist_items': 'id user_id album_id merch_item_id added_at',
}


def snapshot(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('missing snapshot: ' + str(path))
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('snapshot integrity failure')
        schema = db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        if {r[1] for r in schema if r[0] == 'table'} != set(COLUMNS):
            raise ValueError('snapshot table contract mismatch')
        result = {}
        for table, columns in COLUMNS.items():
            cursor = db.execute(f'SELECT * FROM "{table}"')
            names = [c[0] for c in cursor.description]
            if names != columns.split():
                raise ValueError('snapshot column contract mismatch: ' + table)
            result[table] = [dict(zip(names, r)) for r in cursor.fetchall()]
        return result, schema, db.execute('PRAGMA foreign_key_check').fetchall()


def rows_equal(left, right):
    return Counter(tuple(sorted(r.items())) for r in left) == Counter(tuple(sorted(r.items())) for r in right)


def unchanged(before, after):
    return all(rows_equal(before[t], after[t]) for t in before)


def one(rows, **where):
    matches = [r for r in rows if all(r[k] == v for k, v in where.items())]
    if len(matches) != 1:
        raise ValueError('missing/ambiguous authoritative target: ' + repr(where))
    return matches[0]


def additions(before, after):
    old = Counter(tuple(r.items()) for r in before)
    new = Counter(tuple(r.items()) for r in after)
    if old - new:
        return None
    return [dict(r) for r in (new - old).elements()]


def state_ok(index, before, after):
    expected = deepcopy(before)
    email = {3: 'alice.j@test.com', 4: 'bob.c@test.com', 7: 'bob.c@test.com', 8: 'david.k@test.com'}[index]
    user = one(expected['users'], email=email)
    uid = user['id']
    if index in (3, 4):
        table = 'wishlist_items' if index == 3 else 'cart_items'
        added = additions(before[table], after[table])
        if added is None or len(added) != 1:
            return False
        if index == 3:
            album = one(before['albums'], slug='machine-prayer')
            if any(r['user_id'] == uid and r['album_id'] == album['id'] for r in before[table]):
                return False
            fields = dict(user_id=uid, album_id=album['id'], merch_item_id=None)
        else:
            merch = one(before['merch_items'], slug='soft-locale-drift-hoodie')
            variant = one(before['format_variants'], merch_item_id=merch['id'], album_id=None, option_a='M', option_b='Stone')
            if any(r['user_id'] == uid and r['merch_item_id'] == merch['id'] for r in before[table]):
                return False
            fields = dict(user_id=uid, album_id=None, merch_item_id=merch['id'], format_variant_id=variant['id'], quantity=1)
        if not all(added[0][k] == v for k, v in fields.items()):
            return False
        expected[table].append(added[0])  # Only the new id/timestamp are generated.
    elif index == 8:
        if (user['city'], user['favorite_format']) != ('Portland', 'shirt'):
            return False
        user.update(city='Eugene', favorite_format='vinyl')
    else:
        cart = [r for r in before['cart_items'] if r['user_id'] == uid]
        new_orders = additions(before['orders'], after['orders'])
        if not cart or new_orders is None or len(new_orders) != 1:
            return False
        order = new_orders[0]
        if (order['user_id'] != uid or order['status'] != 'paid'
                or order['shipping_line1'] != '77 Fulton Market'
                or order['shipping_city'] != 'Chicago' or order['shipping_country'] != 'United States'
                or order['shipping_name'] != user['display_name']
                or not isinstance(order['payment_label'], str) or not order['payment_label'].strip()
                or not order['order_number'] or not order['placed_at']):
            return False
        new_items = additions(before['order_items'], after['order_items'])
        if new_items is None or len(new_items) != len(cart):
            return False
        wanted_items, wanted_collection = [], []
        subtotal = 0
        for item in cart:
            if type(item['quantity']) is not int or item['quantity'] <= 0:
                return False
            album = one(expected['albums'], id=item['album_id']) if item['album_id'] else None
            merch = one(expected['merch_items'], id=item['merch_item_id']) if item['merch_item_id'] else None
            if bool(album) == bool(merch):
                return False
            subject = album or merch
            variant = one(expected['format_variants'], id=item['format_variant_id']) if item['format_variant_id'] else None
            if variant and (variant['album_id'], variant['merch_item_id']) != (item['album_id'], item['merch_item_id']):
                return False
            price = variant['price'] if variant else subject['price']
            label = ' / '.join(v for v in (variant['name'], variant['option_a'], variant['option_b']) if v) if variant else 'Standard'
            artist = one(before['artists'], id=subject['artist_id'])
            wanted_items.append(dict(order_id=order['id'], album_id=item['album_id'], merch_item_id=item['merch_item_id'],
                                     format_variant_id=item['format_variant_id'], title=subject['title'], artist_name=artist['name'],
                                     image_path=subject['cover_image'] if album else subject['image'], variant_label=label,
                                     quantity=item['quantity'], unit_price=price))
            subtotal += price * item['quantity']
            if album:
                album['fan_count'] += item['quantity']
                if not any(r['user_id'] == uid and r['album_id'] == album['id'] for r in expected['fan_collection_items'] + wanted_collection):
                    tracks = [r for r in before['tracks'] if r['album_id'] == album['id']]
                    focus = next((r for r in tracks if r['is_focus_track']), tracks[0] if tracks else None)
                    wanted_collection.append(dict(user_id=uid, album_id=album['id'], format_variant_id=item['format_variant_id'],
                                                  favorite_track_id=focus['id'] if focus else None, acquired_via='purchase',
                                                  notes='Added from checkout', added_at='2026-05-01 12:00:00.000000'))
            if variant and variant['inventory'] < 9999:
                variant['inventory'] = max(0, variant['inventory'] - item['quantity'])
            elif merch:
                merch['inventory'] = max(0, merch['inventory'] - item['quantity'])
        # Compare full payloads, not title sets; variants, quantities and FKs matter.
        if not rows_equal(wanted_items, [{k: v for k, v in r.items() if k != 'id'} for r in new_items]):
            return False
        collected = additions(before['fan_collection_items'], after['fan_collection_items'])
        if collected is None or not rows_equal(wanted_collection, [{k: v for k, v in r.items() if k != 'id'} for r in collected]):
            return False
        subtotal = round(subtotal, 2)
        shipping = 0.0 if subtotal >= 45 or subtotal == 0 else 6.5
        tax = round(subtotal * .0825, 2)
        if any(order[k] != v for k, v in dict(subtotal=subtotal, shipping=shipping, tax=tax, total=round(subtotal + shipping + tax, 2)).items()):
            return False
        expected['cart_items'] = [r for r in before['cart_items'] if r['user_id'] != uid]
        expected['orders'].append(order)
        expected['order_items'].extend(new_items)
        expected['fan_collection_items'].extend(collected)
        user.update(address_line1=order['shipping_line1'], city=order['shipping_city'], country=order['shipping_country'])
    return unchanged(expected, after)


PAGES = {
    0: ('/album/tidal-memory',), 1: ('/album/between-stations',),
    2: ('/merch/ashen-circuit-grid-slipmat',), 3: ('/album/machine-prayer', '/wishlist'),
    4: ('/merch/soft-locale-drift-hoodie', '/cart'), 5: ('/compare/releases',),
    6: ('/album/tidal-memory',), 7: ('/checkout', '/orders'), 8: ('/account/edit', '/account'),
    9: ('/orders', '/account'), 10: ('/album/resin-language',),
    11: ('/album/elastic-hearts',), 12: ('/merch/velvet-avenue-night-shift-poster',),
    13: ('/album/blue-hour-broadcast',), 14: ('/collection',),
    15: ('/artist/glass-choir', '/album/static-bloom'), 16: ('/album/harbor-burn',),
    17: ('/merch/salt-meadow-field-notes-tote',),
}


def navigation_ok(index, traj, before=None):
    start = urlsplit(traj['start_url'])
    if start.scheme not in ('http', 'https') or start.hostname not in ('localhost', '127.0.0.1', '::1') or start.username or start.password:
        raise ValueError('invalid local start origin')
    origin = (start.scheme, start.hostname, start.port)
    pages = []
    for step in traj['steps']:
        if not isinstance(step, dict) or not isinstance(step.get('url', ''), str):
            raise ValueError('invalid step URL')
        url = urlsplit(step.get('url', ''))
        if not url.username and not url.password and (url.scheme, url.hostname, url.port) == origin:
            pages.append(url)
    if index == 5:
        return any(p.path.rstrip('/') == '/compare/releases' and
                   {tuple(parse_qs(p.query).get(k, [])) for k in ('left', 'right')} ==
                   {('tidal-memory',), ('harbor-burn',)} for p in pages)
    if index == 9:
        _, latest = order_context(before)
        # URLs establish page relevance, NOT the authenticated principal.
        paths = (*PAGES[9], '/orders/' + latest['order_number'])
        return any(p.path in paths for p in pages)
    return any(p.path.rstrip('/') in PAGES[index] for p in pages)


def norm(text):
    return re.sub(r'\s+', ' ', text.casefold().replace('\u2019', "'").replace('**', '').replace('`', '')).strip()


def prose(text):
    """Local normalization for 9/11 only; never rewrite stored answers or URLs."""
    text = unicodedata.normalize('NFKC', text)
    text = text.translate(str.maketrans({c: '-' for c in '\u2010\u2011\u2012\u2013\u2014\u2212'}))
    return norm(text)


def order_text(text):
    return re.sub(r'\s*-\s*', '-', prose(text))


def order_context(before):
    if before is None:
        raise ValueError('task9 requires initial snapshot context')
    # Account is fixed by the task, not by an actor-supplied query/identity claim.
    user = one(before['users'], email='alice.j@test.com')
    orders = [r for r in before['orders'] if r['user_id'] == user['id']]
    if not orders:
        raise ValueError('task9 fixture: named account has no initial orders')
    for row in orders:
        stamp = row['placed_at']
        if not isinstance(stamp, str) or not re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d{1,6})?', stamp):
            raise ValueError('task9 fixture: unsupported placed_at')
        datetime.fromisoformat(stamp)  # Reject invalid calendar values, not just bad shapes.
        if not isinstance(row['order_number'], str) or not row['order_number'].strip():
            raise ValueError('task9 fixture: missing order number')
    # Mirrors ORDER BY placed_at DESC. No invented id tie-break for equal times.
    stamp = max(r['placed_at'] for r in orders)
    latest = [r for r in orders if r['placed_at'] == stamp]
    times = [datetime.fromisoformat(r['placed_at']) for r in orders]
    if len(latest) != 1 or times.count(max(times)) != 1 or datetime.fromisoformat(stamp) != max(times):
        raise ValueError('task9 fixture: ambiguous latest order/page time ordering')
    ids = [order_text(r['order_number']) for r in before['orders']]
    if len(ids) != len(set(ids)):
        raise ValueError('task9 fixture: ambiguous normalized order numbers')
    return user, latest[0]


def order_answer(answer, before):
    """Bounded affirmative-ID grammar; unknown prose fails closed (exit 1)."""
    user, latest = order_context(before)
    text = order_text(answer)
    if re.search(r'\b(?:either|or|maybe|perhaps|possibly|guess|false|incorrect|wrong|orderref\d+)\b|\?', text):
        return False, 'unsupported_or_ambiguous_order_claim'
    known = {order_text(r['order_number']): r for r in before['orders']}
    wanted = order_text(latest['order_number'])
    # Match complete identifiers, including plausible unknown candidates. A suffix
    # or prefix cannot turn a wrong ID into a match of the expected ID.
    pattern = r'(?<![\w-])(?:' + '|'.join(re.escape(k) for k in sorted(known, key=len, reverse=True)) + r'|[a-z0-9]+(?:-[a-z0-9]+)+)(?![\w-])'
    markers = {}
    def mark(match):
        value = match[0]
        if value not in known and (not any(c.isdigit() for c in value) or re.fullmatch(r'\d{4}-\d\d-\d\d', value)):
            return value
        key = f'orderref{len(markers)}'
        markers[key] = value
        return key
    text = re.sub(pattern, mark, text)
    if not markers or any(k not in known for k in markers.values()):
        return False, 'missing_or_unknown_order_id'
    name = re.escape(order_text(user['display_name']))
    owner = rf"(?:(?:her|the|{name}(?:'s)?)\s+)?"
    recent = r'(?:most recent|latest|newest)'
    order = r'(?:seeded\s+)?order(?:\s+(?:number|id))?'
    prefix = rf'{owner}(?:{recent}\b\s*)?(?:{order}\s*)?(?:(?:is|was|:)\s*)?'
    positive = False
    # Commas in dates remain intact; only explicit comparison boundaries split.
    clauses = re.split(r'[.;!]|\bbut\b|\bwhereas\b|,\s*(?=(?:not|older|previous|old|compared with)\b)', text)
    for clause in clauses:
        clause = clause.strip(' ,')
        if not clause:
            continue
        if re.fullmatch(rf'(?:signed|logged) in as {name}', clause):
            continue  # Wording is not an authentication proof.
        refs = re.findall(r'orderref\d+', clause)
        if len(refs) != 1:
            return False, 'unsupported_or_ambiguous_order_claim'
        key = refs[0]
        row = known[markers[key]]
        left, right = clause.split(key)
        left, right = left.strip(), right.strip()
        # Optional dates are checked if supplied in the supported date grammar.
        date = re.search(r',?\s*(?:dated|on)\s+(.+)$', right)
        if date:
            dt = datetime.fromisoformat(row['placed_at'])
            valid_dates = {dt.strftime('%Y-%m-%d'), f'{dt:%B} {dt.day}, {dt.year}'.casefold()}
            if date[1] not in valid_dates:
                return False, 'incorrect_or_unsupported_order_date'
            right = right[:date.start()].strip()
        if markers[key] == wanted:
            if not re.fullmatch(prefix, left + (' ' if left else '')) or not re.fullmatch(rf'(?:is\s+(?:the\s+)?{recent}(?:\s+(?:seeded\s+)?order)?)?', right):
                return False, 'negated_or_unsupported_latest_claim'
            positive = True
        else:
            # Legal comparisons may mention several older IDs; they must belong
            # to this account and be explicitly excluded/labelled older.
            old_prefix = rf'(?:not\s+(?:{owner}{order}\s*)?|(?:compared with\s+)?(?:the\s+)?(?:old|older|previous)\s*(?:{order}\s*)?(?:(?:is|:)\s*)?)'
            old_suffix = r'is\s+(?:the\s+)?(?:old|older|previous)(?:\s+(?:seeded\s+)?order)?'
            if row['user_id'] != user['id'] or not (
                    (re.fullmatch(old_prefix, left + ' ') and not right)
                    or (not left and re.fullmatch(old_suffix, right))):
                return False, 'competing_order_claim'
    return positive, 'initial_latest_id; authentication_requires_native_visual_audit'


# Vocabulary classifies mentions, never defines the expected answer set. Names
# and kinds from the initial seed extend it; absent media remain detectable extras.
FORMAT_ALIASES = {
    'cd': ('cd', 'cds', 'compact disc', 'compact discs', 'compact disk', 'compact disks'),
    'vinyl': ('vinyl', 'vinyl record', 'vinyl records', 'lp', 'lps'),
    'cassette': ('cassette', 'cassettes', 'cassette tape', 'tape'),
    'digital': ('digital', 'digital download', 'download', 'mp3', 'flac'),
    'minidisc': ('minidisc', 'mini disc', 'mini-disc'),
    'usb': ('usb', 'usb stick'), 'dvd': ('dvd',), 'blu-ray': ('blu-ray',),
}


def format_context(before):
    if before is None:
        raise ValueError('task11 requires initial snapshot context')
    album = one(before['albums'], slug='elastic-hearts')
    variants = [r for r in before['format_variants'] if r['album_id'] == album['id']]
    if not variants or any(not isinstance(r['kind'], str) or not r['kind'].strip() for r in variants):
        raise ValueError('task11 fixture: missing/invalid album formats')
    expected = {prose(r['kind']) for r in variants if prose(r['kind']) != 'digital'}
    if not expected:
        raise ValueError('task11 fixture: no physical formats to enumerate')
    aliases = {a: kind for kind, values in FORMAT_ALIASES.items() for a in values}
    for row in before['format_variants']:
        if row['album_id'] is None:
            continue
        kind = prose(row['kind'])
        for alias in (kind, prose(row['name'])):
            if not alias or (alias in aliases and aliases[alias] != kind):
                raise ValueError('task11 fixture: ambiguous format alias ' + alias)
            aliases[alias] = kind
    return album, variants, expected, aliases


def format_details_ok(detail, kind, variants):
    """Optional structured annotations bind to one variant, not a word bag."""
    detail = detail.strip(' ,:()/ -')
    detail = re.sub(r'^(?:is|are)\s+(?:available|offered)(?:\s+physically)?$', '', detail)
    if not detail:
        return True
    for row in variants:
        if prose(row['kind']) != kind:
            continue
        options = [prose(row[k]) for k in ('option_a', 'option_b') if row[k]]
        price = f"{row['price']:.2f}"
        price_pattern = re.escape(price.rstrip('0').rstrip('.'))
        if price.endswith('.00'):
            price_pattern += r'(?:\.00)?'
        elif price.endswith('0'):
            price_pattern += '0?'
        options += [rf'\$?{price_pattern}(?:\s+usd)?']
        option_pattern = '|'.join([re.escape(o) for o in options[:-1]] + options[-1:])
        # Repeated annotations don't create additional kinds.
        if re.fullmatch(rf'(?:{option_pattern})(?:[\s,:()/ -]+(?:{option_pattern}))*', detail):
            return True
    return False


def format_answer(answer, before):
    """Parse affirmative lists with local exclusions, not arbitrary English."""
    album, variants, expected, aliases = format_context(before)
    text = prose(re.sub(r'\n\s*[-*•]\s+', '; ', answer))
    for other in before['albums']:
        if other['id'] != album['id'] and re.search(r'(?<!\w)' + re.escape(prose(other['title'])) + r'(?!\w)', text):
            return False, 'competing_album_subject'
    if re.search(r'\b(?:either|or|maybe|perhaps|possibly|false|incorrect|wrong|neither|nor)\b|\?', text):
        return False, 'unsupported_or_ambiguous_format_claim'
    mention = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')(?!\w)')
    subject = rf"(?:(?:the\s+)?(?:{re.escape(prose(album['title']))}(?:'s)?|it|this release|release|album)\s*)?"
    counts = {'one': 1, 'two': 2, 'both': 2, 'three': 3, 'four': 4, 'five': 5}
    count = '(?:' + '|'.join(counts) + r'|\d+)'
    introduction = rf'{subject}(?:(?:offers|has|is available|comes)\s*(?:in|on|as)?\s*)?(?:(?:the\s+)?(?:{count}\s+)?physical\s+formats?\s*)?(?:(?:are|is|include|includes)\s*)?:?\s*'
    positive, negative, supplemental = set(), set(), []
    clauses = re.split(r'(?<!\d)\.|\.(?!\d)|[;!]|\bbut\b|\bwhereas\b', text)
    for clause in clauses:
        clause = clause.strip(' ,')
        if not clause:
            continue
        matches = list(mention.finditer(clause))
        if not matches:
            if re.search(r"\b(?:not|no|none|never|unavailable|isn't|aren't|cannot|offers|formats?|available)\b", clause):
                return False, 'unsupported_or_ambiguous_format_claim'
            if re.search(r'\b(?:release|album)\s+is\b', clause) and not re.search(r'(?<!\w)' + re.escape(prose(album['title'])) + r'(?!\w)', clause):
                return False, 'unsupported_album_subject'
            supplemental.append(clause)
            continue
        prefix = clause[:matches[0].start()].strip()
        declared = re.search(rf'\b({count})\s+physical\s+formats?\b', prefix)
        if declared and counts.get(declared[1], int(declared[1]) if declared[1].isdigit() else None) != len(expected):
            return False, 'incorrect_physical_format_count'
        denied = bool(re.fullmatch(r'(?:not|no|without|excluding)', prefix))
        if not denied and not re.fullmatch(introduction, prefix + (' ' if prefix else '')):
            return False, 'unsupported_format_subject_or_predicate'
        for n, match in enumerate(matches):
            kind = aliases[match[0]]
            end = matches[n + 1].start() if n + 1 < len(matches) else len(clause)
            detail = clause[match.end():end]
            next_denied = False
            if n + 1 < len(matches):
                separator = re.search(r'(,\s*(?:and\s+)?|\s+(?:and|&)\s+|\s*/\s*|\s*\(\s*)(?:(not|no|excluding|rather than)\s+)?$', detail)
                if not separator:
                    return False, 'unsupported_format_list_separator'
                next_denied = bool(separator[2]) or (denied and ',' not in separator[1] and '(' not in separator[1])
                detail = detail[:separator.start()]
            suffix = detail.strip(' ,()')
            if re.fullmatch(r"(?:(?:is|are)\s+)?(?:unavailable|not (?:available|offered))", suffix):
                denied = True
                detail = ''
            elif kind == 'digital' and re.fullmatch(r'(?:is not|does not count as)\s+(?:a\s+)?physical(?:\s+format)?', suffix):
                denied = True
                detail = ''
            if not format_details_ok(detail, kind, variants):
                return False, 'unsupported_or_incorrect_format_annotation'
            (negative if denied else positive).add(kind)
            denied = next_denied
    if positive != expected or negative & expected:
        return False, 'incomplete_extra_or_contradicted_physical_set'
    note = 'initial_physical_kind_set=' + ','.join(sorted(expected))
    if supplemental:
        note += '; supplementary_prose_not_verified_requires_review=' + repr(supplemental)
    return True, note


def fact_context_ok(index, answer, before):
    """Bind implicit answers to the task page; reject explicit competing subjects."""
    targets = {0: 'tidal-memory', 1: 'between-stations', 5: 'tidal-memory', 6: 'tidal-memory',
               10: 'resin-language', 11: 'elastic-hearts', 13: 'blue-hour-broadcast',
               14: 'between-stations', 15: 'static-bloom', 16: 'harbor-burn'}
    text = norm(answer)
    if index in targets:
        album = one(before['albums'], slug=targets[index])
        related = {album['id']}
        if index == 5:
            other = one(before['albums'], slug='harbor-burn')
            related.add(other['id'])
            valid = (album['duration_seconds'], other['duration_seconds']) == (1210, 1075)
        elif index in (0, 10, 13):
            kind, amount = {0: ('cassette', 15.0), 10: ('digital', 8.5), 13: ('digital', 9.5)}[index]
            variant = one(before['format_variants'], album_id=album['id'], kind=kind)
            valid = variant['price'] == amount
            if index == 13:
                valid = valid and amount == min(r['price'] for r in before['format_variants'] if r['album_id'] == album['id'])
        elif index in (1, 6, 16):
            number, title, duration = {1: (3, 'Between Stations', None), 6: (4, 'Low Pier', 271), 16: (5, 'Wide Exit', None)}[index]
            track = one(before['tracks'], album_id=album['id'], track_number=number)
            valid = track['title'] == title and (duration is None or track['duration_seconds'] == duration)
        elif index == 11:
            format_context(before)
            valid = True
        elif index == 14:
            user = one(before['users'], email='carol.d@test.com')
            item = one(before['fan_collection_items'], user_id=user['id'], album_id=album['id'])
            valid = one(before['tracks'], id=item['favorite_track_id'])['title'] == 'Between Stations'
        else:
            artist = one(before['artists'], slug='glass-choir')
            valid = album['artist_id'] == artist['id'] and album['release_date'] == max(r['release_date'] for r in before['albums'] if r['artist_id'] == artist['id'])
        if not valid:
            raise ValueError('authoritative facts differ from reviewed task seed')
        # Brief answers may inherit the requested subject. Explicitly naming a
        # different album as that subject must not turn a token match into PASS.
        for other in before['albums']:
            title = norm(other['title'])
            if other['id'] not in related and re.search(r'\b' + re.escape(title) + r"(?:'s)?\s+(?:cassette|digital|third|fourth|track|physical|favorite|favourite|is|has|offers|costs)", text):
                return False
    elif index in (2, 12, 17):
        slug = {2: 'ashen-circuit-grid-slipmat', 12: 'velvet-avenue-night-shift-poster', 17: 'salt-meadow-field-notes-tote'}[index]
        merch = one(before['merch_items'], slug=slug)
        variants = [r for r in before['format_variants'] if r['merch_item_id'] == merch['id']]
        if index == 2:
            valid = min(variants, key=lambda r: r['price'])['name'] == 'Pair'
        elif index == 12:
            valid = one(variants, name='Signed')['price'] == 27 and one(before['albums'], id=merch['album_id'])['slug'] == 'blue-hour-broadcast'
        else:
            valid = {r['option_a'] for r in variants} == {'Natural', 'Forest'}
        if not valid:
            raise ValueError('authoritative merch facts differ from reviewed seed')
    elif index == 9:
        order_context(before)
    return True


def answer_ok(index, answer, before=None):
    if index in (9, 11):
        return (order_answer if index == 9 else format_answer)(answer, before)[0]
    text = norm(answer)
    if not text:
        return False
    if index in STATEFUL_TASKS:
        return True
    if index == 5:
        text = re.sub(r'\btidal memory\s+is\s+not\s+shorter\b', 'tidal memory is longer', text)
    # Negated clauses are not evidence. Exclusions of losing options are valid.
    clauses = re.split(r'(?<!\d)[.;!?](?!\d)|\bbut\b|\bwhereas\b', text)
    affirmative = []
    for clause in clauses:
        clause = re.sub(r',?\s*(?:not|rather than)\s+(?:the\s+)?(?:glow pair|digital)(?:\s+edition)?\b', '', clause)
        if index == 5:
            clause = re.sub(r',?\s*(?:not|rather than)\s+harbor burn\b', '', clause)
        if not re.search(r"\b(?:not|never|neither|false|incorrect|wrong|isn't|isnt|cannot|can't)\b", clause):
            affirmative.append(clause)
    value = ' ; '.join(affirmative)
    if re.search(r'\b(?:false|incorrect)\s+that\b', text):
        return False
    contradictions = {
        0: r'cassette.{0,20}(?:not|isn\x27t).{0,10}\$?15',
        1: r'(?:third|3rd|track 3).{0,20}(?:not|isn\x27t).{0,10}between stations',
        2: r'(?<!glow )pair\s+(?:is |isn\x27t )?(?:not |never )?(?:the )?(?:more expensive|costlier)|(?<!glow )pair\s+is\s+not\s+(?:the )?cheaper',
        5: r'tidal memory\s+is\s+not\s+(?:the )?longer',
        6: r'(?:not|isn\x27t)\s+4:31',
        10: r'digital.{0,20}(?:not|isn\x27t).{0,10}\$?8\.5',
        12: r'signed.{0,20}(?:not|isn\x27t).{0,10}\$?27',
        13: r'digital.{0,20}(?:not|isn\x27t).{0,10}(?:cheapest|\$?9\.5)',
        14: r'favou?rite.{0,20}(?:not|isn\x27t).{0,10}between stations',
        15: r'static bloom\s+is\s+not\s+(?:the )?newest',
        16: r'wide exit\s+is\s+not\s+(?:the )?closing',
    }
    if index in contradictions and re.search(contradictions[index], text):
        return False
    def has(*tokens):
        return all(re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', value) for t in tokens)
    def price(amount):
        return bool(re.search(r'(?<![\w.])\$?' + re.escape(amount) + r'(?:0)?(?!\d|\.\d)', value))
    if index in (0, 10, 12):
        amount = {0: r'15(?:\.00)?', 10: r'8\.50?', 12: r'27(?:\.00)?'}[index]
        if re.fullmatch(r'\$?' + amount + r'\s*(?:usd|dollars)?[.!]?', value.strip()):
            return True
    if index == 0:
        return bool(has('cassette') and (price('15.0') or price('15')))
    if index == 1:
        return bool(has('between stations') and re.search(r'\b(?:third track|3rd track|track (?:3|three))\b', value))
    if index == 2:
        winner = re.sub(r'glow pair', 'loser', value)
        if re.fullmatch(r'(?:the\s+)?pair(?:\s+option)?(?:\s*(?:at|:|\()?\s*\$?22(?:\.00)?\)?)?[.!]?', winner.strip()):
            return True
        return bool(re.search(r'\bpair\b.{0,45}\b(?:cheaper|cheapest|less expensive|lower priced)\b|\b(?:cheaper|cheapest|less expensive)\b.{0,35}\bpair\b', winner)
                    and not re.search(r'\bloser\b.{0,20}\b(?:is|costs)\s+(?:the\s+)?(?:cheaper|cheapest|less)', winner)
                    and not re.search(r'\bpair\s+(?:costs|at|is)\s+\$?27\b|\bloser\s+(?:(?:costs|at|is)\s+)?\$?22\b', winner)
                    and not re.search(r'pair.{0,20}\b(?:more expensive|costlier)\b', winner))
    if index == 5:
        if value.strip(' .!') == 'tidal memory':
            return True
        return bool(re.search(r'tidal memory.{0,25}\b(?:is |runs |lasts )?(?:the )?(?:longer|longest)\b|harbor burn.{0,25}\b(?:is )?(?:the )?shorter\b', value)
                    and not re.search(r'harbor burn.{0,20}\b(?:is )?(?:the )?longer\b|tidal memory.{0,20}\b(?:is )?(?:the )?shorter\b', value)
                    and not re.search(r'tidal memory.{0,15}17:55|harbor burn.{0,15}20:10', value))
    if index == 6:
        return bool(re.search(r'\b4:31\b|\b271\s*(?:s|seconds)\b|\b4\s*(?:minutes|min)\s*(?:and )?31\s*(?:seconds|sec)\b', value))
    if index == 10:
        return bool(has('digital') and price('8.5'))
    if index == 12:
        return bool(has('signed') and (price('27') or price('27.0')))
    if index == 13:
        return bool(has('digital') and price('9.5') and not re.search(r'\b(?:most expensive|costliest|priciest)\b', value))
    if index == 14:
        return bool(has('between stations') and re.search(r'\bfavou?rite(?: track)?\b', value))
    if index == 15:
        return bool(has('static bloom') and not re.search(r'\b(?:oldest|earliest)\b', value))
    if index == 16:
        return bool(has('wide exit') and not re.search(r'\b(?:first|opening|penultimate)\b', value))
    if index == 17:
        remainder = re.sub(r"\b(?:salt meadow(?:'s)?|field notes tote|the|two|available|color|colour|colors|colours|variants|options|are|is|and|in|for|comes|tote|natural|forest)\b", ' ', value)
        return bool(has('natural', 'forest') and not re.search(r'[a-z0-9]', remainder))
    raise ValueError('unknown task')


def evaluate(task_index, traj, initial_db='', after_db='', container=None):
    if not isinstance(traj, dict) or traj.get('task_id') != f'Bandcamp--{task_index}':
        raise ValueError('trajectory task identity mismatch')
    if not isinstance(traj.get('steps'), list) or not isinstance(traj.get('final_answer'), str) or not isinstance(traj.get('start_url'), str):
        raise ValueError('invalid trajectory schema')
    before, schema, before_fk = snapshot(initial_db)
    after, after_schema, after_fk = snapshot(after_db)
    if schema != after_schema:
        raise ValueError('snapshot schema changed')
    if before_fk:
        raise ValueError('initial snapshot foreign key failure')
    focused = (order_answer if task_index == 9 else format_answer)(traj['final_answer'], before) if task_index in (9, 11) else None
    state = state_ok(task_index, before, after) if task_index in STATEFUL_TASKS else unchanged(before, after)
    checks = [('final_answer_nonempty', bool(traj['final_answer'].strip())),
              ('required_navigation', navigation_ok(task_index, traj, before)),
              ('frozen_answer', (focused[0] if focused is not None else answer_ok(task_index, traj['final_answer'])) and
               (task_index in STATEFUL_TASKS or fact_context_ok(task_index, traj['final_answer'], before))),
              ('authoritative_state', state and not after_fk)]
    return dict(task_id=f'Bandcamp--{task_index}', **{'pass': all(v for _, v in checks)},
                reason=next((k for k, v in checks if not v), ''), evidence=[f'{k}: {bool(v)}' for k, v in checks] +
                ([focused[1]] if focused is not None else []))


def main(task_index):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--initial_db', '--before_db', default='')
    parser.add_argument('--after_db', default='')
    parser.add_argument('--container', default=None, help='Legacy argument; never fetches live state')
    parser.add_argument('--no_llm', nargs='?', const='True', default='False')
    args = parser.parse_args()
    try:
        run = Path(args.run_dir)
        traj = json.loads((run / 'trajectory.json').read_text())
        if (run / 'task.json').exists() and json.loads((run / 'task.json').read_text()).get('id') != f'Bandcamp--{task_index}':
            raise ValueError('task.json identity mismatch')
        initial = args.initial_db or next((str(run / n) for n in ('initial.db', 'before.db') if (run / n).is_file()), '')
        after = args.after_db or str(run / 'after.db')
        verdict = evaluate(task_index, traj, initial, after)
        code = 0 if verdict['pass'] else 1
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        verdict = dict(task_id=f'Bandcamp--{task_index}', **{'pass': False}, reason='infrastructure_error', evidence=[str(exc)])
        code = 2
    print(json.dumps(verdict, indent=2))
    sys.exit(code)
