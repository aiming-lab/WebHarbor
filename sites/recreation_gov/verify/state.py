"""Read-only snapshot comparison and precise, whole-database mutation contracts."""
import copy
import hashlib
import hmac
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from answers import identified, norm


def snapshot(path):
    path = Path(path).resolve()
    with sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Corrupt snapshot')
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if not {'user', 'facility', 'review', 'reservation', 'cart_item', 'saved_item', 'address', 'payment_method', 'campsite'} <= set(tables):
            raise ValueError('Incomplete Recreation.gov snapshot')
        return {t: {r['id']: dict(r) for r in con.execute(f'SELECT * FROM "{t}"')} for t in tables}


def password_matches(stored, password):
    try:
        method, salt, expected = stored.split('$')
        if method.startswith('scrypt:'):
            _, n, r, p = method.split(':')
            if (int(n), int(r), int(p)) != (32768, 8, 1):
                return False
            actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=int(n), r=int(r), p=int(p), maxmem=132 * int(n) * int(r) * int(p), dklen=64)
        elif method.startswith('pbkdf2:sha256:'):
            rounds = int(method.rsplit(':', 1)[1])
            if not 100000 <= rounds <= 2000000:
                return False
            actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), rounds)
        else:
            return False
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def one(rows):
    if len(rows) != 1:
        raise ValueError(f'Expected one matching row, got {len(rows)}')
    return rows[0]


def verify_delta(task, before, after, answer):
    expected = copy.deepcopy(before)

    def user(email):
        return one([r for r in before['user'].values() if r['email'] == email])

    def facility(slug):
        return one([r for r in before['facility'].values() if r['slug'] == slug])

    def addition(table, fields, dynamic=()):
        row = one([r for key, r in after[table].items() if key not in before[table]])
        if row['id'] <= 0 or any(row.get(k) != v for k, v in fields.items()):
            raise ValueError(f'Incorrect {table} addition')
        if set(row) != {'id', *fields, *dynamic}:
            raise ValueError(f'Unchecked fields in {table}')
        if 'created_at' in dynamic:
            datetime.fromisoformat(row['created_at'])
        expected[table][row['id']] = row
        return row

    if task == 11:
        addition('saved_item', {'user_id': user('alice.j@test.com')['id'],
                                'facility_id': facility('fort-point-national-historic-site-tours')['id']}, ('created_at',))
    elif task == 12:
        uid = user('bob.c@test.com')['id']
        item = one([r for r in before['cart_item'].values() if r['user_id'] == uid])
        fac = before['facility'][item['facility_id']]
        camp = before['campsite'].get(item['campsite_id'])
        nights = max((date.fromisoformat(item['end_date']) - date.fromisoformat(item['start_date'])).days, 1)
        total = Decimal(str(camp['nightly_rate'] if camp else fac['price'])) * (nights if fac['inventory_type'] == 'camping' else item['quantity'])
        row = addition('reservation', {'user_id': uid, 'facility_id': fac['id'],
                       'campsite_name': camp['name'] if camp else {'camping': 'Camping & Lodging', 'tickets': 'Tickets & Tours', 'permits': 'Permits', 'passes': 'Activity & Site Passes', 'day_use': 'Day Use / Venues', 'lottery': 'Lotteries'}[fac['inventory_type']],
                       'start_date': item['start_date'], 'end_date': item['end_date'], 'guests': item['guests'],
                       'total_cost': total, 'status': 'Upcoming'}, ('confirmation_code', 'created_at'))
        if not row['confirmation_code'] or row['confirmation_code'] in {r['confirmation_code'] for r in before['reservation'].values()}:
            raise ValueError('Confirmation is not new')
        if not identified(answer, row['confirmation_code'].lower()):
            raise ValueError('Missing or negated new confirmation code')
        del expected['cart_item'][item['id']]
    elif task == 13:
        uid = user('alice.j@test.com')['id']
        row = one([r for r in before['reservation'].values() if r['user_id'] == uid and r['confirmation_code'] == 'RG-2026-AJ01' and r['status'] == 'Upcoming'])
        expected['reservation'][row['id']]['status'] = 'Cancelled'
        if not identified(answer, 'rg-2026-aj01'):
            raise ValueError('Missing cancelled confirmation code')
    elif task == 14:
        row = user('carol.d@test.com')
        expected['user'][row['id']].update(phone='555-0199', home_city='Boulder')
    elif task == 15:
        row = addition('user', {'username': 'river_stone', 'email': 'river.stone@example.com',
                               'display_name': 'River Stone', 'phone': '', 'home_city': ''}, ('password_hash', 'created_at'))
        if not password_matches(row['password_hash'], 'TrailPass2026'):
            raise ValueError('Incorrect registration password')
        addition('address', {'user_id': row['id'], 'label': 'Home', 'street': '100 Trailhead Dr',
                             'city': 'Denver', 'state': 'CO', 'zip_code': '80202', 'is_default': 1})
        addition('payment_method', {'user_id': row['id'], 'card_type': 'Visa', 'last4': '4242', 'expiry': '12/28', 'is_default': 1})
        if not identified(answer, '4242') or not identified(answer, 'denver'):
            raise ValueError('Incorrect account defaults answer')
    elif task == 16:
        owner = user('david.k@test.com')
        fac = facility('fort-point-national-historic-site-tours')
        addition('review', {'user_id': owner['id'], 'facility_id': fac['id'],
                            'author': owner['display_name'] or owner['username'], 'rating': 4,
                            'body': 'Accessible route was easy to follow.', 'visit_date': 'May 2026'})
        expected['facility'][fac['id']]['review_count'] = fac['review_count'] + 1
        expected['facility'][fac['id']]['rating'] = round((float(fac['rating']) * fac['review_count'] + 4) / (fac['review_count'] + 1), 1)
    elif task == 19:
        fac = facility('yellowstone-national-park-fishing-permit')
        addition('cart_item', {'user_id': user('alice.j@test.com')['id'], 'facility_id': fac['id'],
                              'campsite_id': None, 'start_date': fac['checkin_date'], 'end_date': fac['checkout_date'],
                              'guests': 2, 'quantity': 1})
    if expected != after:
        changed = sorted(t for t in set(expected) | set(after) if expected.get(t) != after.get(t))
        raise ValueError('Unexpected or missing changes: ' + ', '.join(changed))
    return True
