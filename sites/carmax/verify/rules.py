"""CarMax task contracts; expected facts belong here, never in tasks.jsonl."""
import re

from deterministic import date_in, field, has, measure, money, norm, number


def matching_clauses(answer, label):
    """Keep related facts in one sentence/line; do not split decimal prices."""
    return [norm(c) for c in re.split(r'\n|;|(?<=[.!?])\s+', answer)
            if re.search(label, norm(c))]


def affirmative(clause):
    return not re.search(r'\b(?:not|never|no|incorrect|excluded|unavailable)\b', clause)


def evaluate(r):
    n, answer = r.task, r.answer
    text = norm(answer)
    vehicles = r.initial['vehicles']

    def candidates(**where):
        return [v for v in vehicles if all(v[k] == value for k, value in where.items())]

    def opened(options):
        hits = [v for v in options if r.nav('/vehicle/' + v['slug'])]
        r.check('opened eligible vehicle detail', bool(hits))
        return hits[0] if hits else options[0]

    def price(v):
        r.check('asking price', money(answer, v['price']))

    def mileage(v):
        r.check('mileage with miles units', measure(answer, v['mileage'], r'mi|miles'))

    def store(v, name=False):
        s = r.row('stores', id=v['store_id'])
        r.store_answer(s, name)
        return s

    def positive(subject):
        return not re.search(r'(?:no|not|never|without|failed|cancelled|canceled)\b[^.;\n]{0,35}(?:' + subject + r')|(?:' + subject + r')[^.;\n]{0,25}\b(?:not|never|cancelled|canceled)', text)

    if n in (0, 1, 4):
        where = {0: dict(year=2022, make='Honda', model='Civic'),
                 1: dict(make='Toyota', model='Tacoma', trim='TRD Off-Road'),
                 4: dict(year=2022, make='Honda', model='CR-V')}[n]
        v = opened(candidates(**where))
        if n == 0:
            r.vehicle_answer(v, trim=True)
        if n in (0, 1):
            price(v)
            mileage(v)
        if n in (1, 4):
            store(v)
        if n == 4:
            r.check('horsepower', measure(answer, v['horsepower'], 'hp|horsepower') or field(answer, 'horsepower', v['horsepower']))
            r.check('combined MPG', field(answer, 'combined mpg', v['mpg_combined']) or measure(answer, v['mpg_combined'], 'combined mpg'))
            r.check('exterior color', has(answer, v['exterior_color']))

    elif n == 2:
        options = [v for v in candidates(body_style='SUV', drive_type='AWD') if v['price'] < 25000]
        lowest = min(v['price'] for v in options)
        targets = [v for v in options if v['price'] == lowest]
        r.require_nav('/cars', lambda q: q.get('body_style') == ['SUV'] and q.get('drive_type') == ['AWD']
                      and float(q.get('price_max', ['inf'])[0]) <= 25000 and q.get('sort') == ['price_low'])
        r.check('cheapest complete vehicle identity', any(all(has(answer, v[k]) for k in ['year','make','model','trim']) for v in targets))
        r.check('cheapest price', money(answer, lowest))

    elif n == 3:
        options = [v for v in candidates(make='Tesla', model='Model 3') if v['mileage'] < 60000]
        if not options:
            raise ValueError('No Tesla Model 3 under 60,000 miles in fixture')
        low = min(v['mileage'] for v in options)
        v = opened([v for v in options if v['mileage'] == low])
        r.require_nav('/cars', lambda q: q.get('sort') == ['mileage_low']
                      and float(q.get('mileage_max', ['inf'])[0]) < 60000
                      and ('model 3' in norm(q.get('q', [''])[0]))
                      and (q.get('make') == ['tesla'] or 'tesla' in norm(q.get('q', [''])[0])))
        price(v)
        mileage(v)
        store(v)
        r.check('exterior color', has(answer, v['exterior_color']))

    elif n == 5:
        r.require_nav('/research/honda/civic/2022')
        options = candidates(year=2022, make='Honda', model='Civic')
        reviews = [v for v in r.initial['reviews'] if v['year'] == 2022 and v['make_slug'] == 'honda' and v['model_slug'] == 'civic']
        rating = round(sum(v['rating'] for v in reviews) / len(reviews), 1) if reviews else options[0]['customer_rating']
        r.check('all available trims', all(has(answer, v['trim']) for v in options))
        r.check('RepairPal rating correctly attributed', field(answer, r'repairpal(?: reliability)?(?: rating)?', options[0]['repairpal_rating']))
        r.check('customer average correctly attributed', field(answer, r'(?:average |avg )?customer rating', rating))

    elif n == 6:
        r.require_nav('/compare')
        comparisons = r.added('comparisons')
        items = r.added('comparison_items', 3)
        required = {(2022, 'Honda', 'Accord'), (2022, 'Toyota', 'Camry'), (2022, 'Nissan', 'Altima')}
        selected = [r.row('vehicles', id=i['vehicle_id']) for i in items]
        r.check('exact three requested comparison vehicles', {(v['year'], v['make'], v['model']) for v in selected} == required)
        if comparisons:
            r.check('all items belong to new comparison', all(i['comparison_id'] == comparisons[0]['id'] for i in items))
        for attr, label in [('horsepower', r'(?:most|highest|max(?:imum)?) horsepower'), ('mpg_combined', r'(?:best|highest|max(?:imum)?) combined mpg')]:
            if not selected:
                r.check('comparison has items', False)
                continue
            top = max(v[attr] for v in selected)
            winners = [v for v in selected if v[attr] == top]
            # Limit the relationship to one clause; names elsewhere are not evidence.
            clauses = re.split(r'[.;\n]|,?\s+(?:and|while|whereas)\s+', text)
            r.check('correct winner: ' + attr, any(re.search(label, c) and any(has(c, v['model']) for v in winners)
                                                   and not re.search(r'\b(?:not|never)\b', c) for c in clauses))

    elif n == 7:
        additions = r.added('appraisals')
        if additions:
            a = additions[0]
            r.fields(a, year=2018, make='Toyota', model='Camry', trim='LE', mileage=78500,
                     condition='good', zip_code='30303', has_accidents=0, owner_count=1,
                     status='active', offer_amount=4850, offer_valid_until='2026-05-21')
            r.require_nav('/sell-my-car/offer/' + str(a['id']))
            r.check('offer amount', money(answer, a['offer_amount']))
            r.check('offer expiry', date_in(answer, a['offer_valid_until']))

    elif n == 8:
        r.require_nav('/stores')
        count = len({s['state'] for s in r.initial['stores']})
        r.check('number of states', measure(answer, count, 'states'))
        ca = [s for s in r.initial['stores'] if s['state'] == 'CA']
        r.check('California street address', any(has(answer.replace('Drive','Dr'), s['street']) for s in ca))
        r.check('visited California location', r.nav('/stores/CA') or any(r.nav('/store/' + s['slug']) for s in ca))

    elif n == 9:
        users = r.added('users')
        applications = r.added('finance_prequals')
        r.require_nav('/register')
        r.require_nav('/pre-qual/result')
        if users:
            user = users[0]
            r.fields(user, email='new.buyer.benchmark@test.com', first_name='Test', last_name='Buyer',
                     phone='4045550199', zip_code='30303', annual_income=80000,
                     employment_status='employed_full_time', pre_qual_active=1,
                     pre_qual_monthly_max=500, pre_qual_down_payment=2000,
                     pre_qual_term_months=72, pre_qual_credit_tier='good', pre_qual_apr=7.99)
            import bcrypt
            r.check('requested password', bcrypt.checkpw(b'Welcome2026', user['password_hash'].encode()))
            if applications:
                r.fields(applications[0], user_id=user['id'], annual_income=80000,
                         employment_status='employed_full_time', monthly_payment_max=500,
                         down_payment=2000, term_months=72, credit_tier='good', estimated_apr=7.99,
                         status='active', expires_at=user['pre_qual_expires_at'])
        r.check('APR with percent units', bool(re.search(number(7.99) + r'\s*(?:%|percent)', text)))

    elif n in (10, 11):
        is_drive = n == 11
        table = 'test_drives' if is_drive else 'reservations'
        user = r.row('users', email='bob.k@test.com' if is_drive else 'alice.j@test.com')
        additions = r.added(table)
        r.require_nav('/account/test-drives' if is_drive else '/account/reservations')
        if additions:
            row = additions[0]
            v = r.row('vehicles', id=row['vehicle_id'])
            r.fields(v, year=2022, make='Ford' if is_drive else 'Toyota', model='F-150' if is_drive else 'Camry')
            r.fields(row, user_id=user['id'], store_id=v['store_id'], status='confirmed' if is_drive else 'active')
            if is_drive:
                r.fields(row, scheduled_date='2026-05-22', scheduled_time='2:00 PM', location_type='at_home', notes='Please call gate buzzer 4B')
                r.check('affirmative test drive confirmation', has(answer, 'F-150') and positive('test drive|test-drive|scheduled|confirmed'))
            else:
                r.fields(row, appointment_date='2026-05-20', expires_at='2026-05-21', transfer_required=0,
                         transfer_fee=v['transfer_fee'] or 0)
                r.check('affirmative active reservation', has(answer, 'active') and positive('active|reserv'))

    elif n == 12:
        user = r.row('users', email='carol.l@test.com')
        a = r.row('appraisals', user_id=user['id'], status='active')
        r.require_nav('/account/appraisals')
        r.require_nav('/faq/selling-a-car/how-long-is-my-appraisal-offer-good-for')
        r.require_nav('/faq/selling-a-car/can-i-get-both-an-online-and-in-store-appraisal')
        r.vehicle_answer(a, trim=True)
        r.check('saved appraisal amount', money(answer, a['offer_amount']))
        r.check('saved appraisal expiry', date_in(answer, a['offer_valid_until']))
        r.check('appraisal offer validity', (measure(answer, 7, 'days') or has(answer, 'seven days')) and positive('7 days|seven days'))
        r.check('online offer requires in-store verification', any(
            re.search(r'in[- ](?:store|person)|at (?:a |the )?store|to (?:a |the )?store', c)
            and re.search(r'verif(?:y|ication|ied)', c) and affirmative(c)
            for c in matching_clauses(answer, r'online|instant offer')))
        r.check('same outright sale and trade-in price', any(
            re.search(r'sell|sale|outright', c) and re.search(r'trad', c)
            and re.search(r'same|equal|unchanged|does not change|no (?:price )?difference', c)
            and not re.search(r'not (?:the )?same|different|higher|lower', c)
            for c in matching_clauses(answer, 'price|amount|offer')))

    elif n == 13:
        user = r.row('users', email='alice.j@test.com')
        saved = [s for s in r.initial['saved_vehicles'] if s['user_id'] == user['id']]
        r.check('two saved cars initially', len(saved) == 2)
        highest = max(saved, key=lambda s: r.row('vehicles', id=s['vehicle_id'])['mileage'])
        r.expected['saved_vehicles'] = [s for s in r.initial['saved_vehicles'] if s['id'] != highest['id']]
        remaining = [s for s in saved if s['id'] != highest['id']][0]
        v = r.row('vehicles', id=remaining['vehicle_id'])
        r.require_nav('/saved')
        r.vehicle_answer(v)
        store(v)

    elif n == 14:
        user = r.row('users', email='carol.l@test.com')
        appraisals = [a for a in r.initial['appraisals'] if a['user_id'] == user['id'] and a['status'] == 'active']
        r.check('one active appraisal initially', len(appraisals) == 1)
        a = appraisals[0]
        orders = r.added('orders')
        if orders:
            o = orders[0]
            v = r.row('vehicles', id=o['vehicle_id'])
            r.fields(v, year=2022, make='Honda', model='CR-V')
            total = round(v['price'] * 1.06 + (v['transfer_fee'] or 0) + 99 + 55 - a['offer_amount'], 2)
            r.fields(o, user_id=user['id'], store_id=v['store_id'], status='processing',
                     trade_in_appraisal_id=a['id'], trade_in_value=a['offer_amount'],
                     payment_method='carmax_auto_finance', payment_term_months=60,
                     down_payment=3000, payment_apr=6.49, maxcare_plan='', maxcare_price=0,
                     subtotal=v['price'], transfer_fee=v['transfer_fee'] or 0, tax=v['price'] * .06,
                     title_fee=99, registration_fee=55, total=total)
            for row in r.expected['appraisals']:
                if row['id'] == a['id']:
                    row['status'] = 'redeemed'
            r.require_nav('/vehicle/' + str(v['id']) + '/checkout')
            r.require_nav('/order/' + o['order_number'])
            r.check('order number', has(answer, o['order_number']))
            r.check('order total', money(answer, total))
            r.check('identified appraisal vehicle', all(has(answer, a[k]) for k in ['year','make','model']))
            r.check('identified appraisal amount', money(answer, a['offer_amount']))

    elif n == 15:
        options = candidates(year=2023)
        low = min(v['price'] for v in options)
        v = opened([v for v in options if v['price'] == low])
        r.vehicle_answer(v)
        price(v)
        s = store(v, name=True)
        r.require_nav('/store/' + s['slug'])
        r.check('home delivery available', has(answer, 'home delivery') and positive('home delivery'))

    elif n == 16:
        user = r.row('users', email='bob.k@test.com')
        r.require_nav('/pre-qual/result')
        r.require_nav('/faq/financing/what-is-pre-qualification')
        r.check('saved APR with percent units', any(
            re.search(number(user['pre_qual_apr']) + r'\s*(?:%|percent)', c)
            for c in matching_clauses(answer, r'apr')))
        r.check('saved loan term', any(measure(c, user['pre_qual_term_months'], 'months|mo')
                                     for c in matching_clauses(answer, r'term|loan')))
        r.check('saved down payment', any(money(c, user['pre_qual_down_payment'])
                                        for c in matching_clauses(answer, r'down')))
        r.check('saved prequalification expiry', date_in(answer, user['pre_qual_expires_at']))
        r.check('policy validity duration', any(measure(c, 30, 'days') or has(c, 'thirty days')
                                              for c in matching_clauses(answer, r'valid|policy')))
        article = next(a for a in r.initial['articles'] if a['title'].startswith('Getting Pre-Qualified:'))
        r.require_nav('/articles/' + article['slug'])
        r.check('prequalification soft inquiry', bool(re.search(r'pre[- ]qualif[^.;]{0,65}\bsoft\b', text)))
        r.check('no credit score impact', bool(re.search(r'(?:does not|doesn.t|won.t|will not|no|without)[^.;]{0,30}(?:impact|affect|hurt|effect)[^.;]{0,25}credit', text)))
        r.check('final application hard inquiry', bool(re.search(r'(?:final|credit application)[^.;]{0,65}\bhard\b', text)))
        r.check('no reversed inquiries', not re.search(r'pre[- ]qualif[^,;]{0,30}\bhard\b|final[^,;]{0,40}\bsoft\b', text))

    elif n == 17:
        user = r.row('users', email='dan.m@test.com')
        o = r.row('orders', user_id=user['id'])
        v = r.row('vehicles', id=o['vehicle_id'])
        r.check('visited order history or detail', r.nav('/account/orders') or r.nav('/order/' + o['order_number']))
        r.check('order number', has(answer, o['order_number']))
        r.vehicle_answer(v)
        r.check('order total (exact or displayed rounding)', money(answer, o['total']) or money(answer, int(o['total'] + .5)))
        r.check('MaxCare included', has(answer, 'maxcare') and (has(answer, 'gold') or has(answer, 'included') or has(answer, 'yes')) and positive('maxcare|included'))
        r.check('pickup date', date_in(answer, o['pickup_date']))

    elif n == 18:
        r.require_nav('/value/honda/accord/2020')
        values = [v['price'] for v in candidates(year=2020, make='Honda', model='Accord')]
        average, low, high = round(sum(values) / len(values)), min(values), max(values)
        r.check('average price', field(answer, r'(?:carmax )?(?:average|avg)(?: price)?', average))
        r.check('price range', bool(re.search(number(low) + r'\s*(?:-|to)\s*\$?' + number(high), text))
                or (field(answer, 'lowest in stock', low) and field(answer, 'highest in stock', high)))
        r.check('inventory count', measure(answer, len(values), r'(?:cars|vehicles|accords|in (?:current inventory|stock))')
                or field(answer, r'(?:count|in stock|inventory count)', len(values)))

    elif n == 19:
        user = r.row('users', email='dan.m@test.com')
        order = r.row('orders', user_id=user['id'])
        vehicle = r.row('vehicles', id=order['vehicle_id'])
        r.require_nav('/order/' + order['order_number'])
        r.require_nav('/car-buying-process/maxcare-service-plans')
        r.require_nav('/faq/warranty-and-returns/what-does-maxcare-cover')
        r.check('order number', has(answer, order['order_number']))
        r.vehicle_answer(vehicle, trim=True)
        r.check('ordered MaxCare tier and charge', any(
            has(c, order['maxcare_plan']) and money(c, order['maxcare_price']) and affirmative(c)
            for c in matching_clauses(answer, r'order|current|included')))
        plans = {'silver': (1495, 36, 50000), 'gold': (1895, 48, 75000), 'platinum': (2395, 60, 100000)}
        for name, (cost, months, miles) in plans.items():
            parts = [c for c in matching_clauses(answer, r'\b' + name + r'\b')
                     if not any(has(c, other) for other in plans if other != name)]
            r.check(name + ' price and coverage', any(money(c, cost)
                    and measure(c, months, 'months|mo') and measure(c, miles, 'miles|mi')
                    and affirmative(c) for c in parts))
        current = plans[order['maxcare_plan']]
        difference = tuple(a - b for a, b in zip(plans['platinum'], current))
        r.check('upgrade price and coverage differences', any(
            has(c, 'platinum') and has(c, order['maxcare_plan'])
            and money(c, difference[0]) and measure(c, difference[1], 'months|mo')
            and measure(c, difference[2], 'miles|mi') and affirmative(c)
            for c in matching_clauses(answer, r'upgrade|additional|extra|difference')))
        r.check('rental daily reimbursement cap', any(
            re.search(r'\$\s*40(?:\.00)?\s*(?:/\s*day|per day|daily)|40\s*(?:dollars|usd)\s*(?:per day|daily)', c)
            and affirmative(c) for c in matching_clauses(answer, 'rental')))
        r.check('Canada included in coverage', any(
            re.search(r'cover|includ', c) and affirmative(c)
            for c in matching_clauses(answer, r'\bcanada\b')))
