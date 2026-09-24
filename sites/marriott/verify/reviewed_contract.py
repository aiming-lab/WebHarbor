"""Precise state preservation and entity-bound answer checks for reviewed tasks."""
import re
from verify_lib import (table_delta, row_dict, table_rows, user_by_email,
                        contains_phrase, contains_amount, contains_count, norm)


def check_precise_state(judge, traj, initial, after):
    index = int(traj['task_id'].split('--')[-1])
    allowed_user = {1: (1, {'points'}), 8: (2, {'phone', 'street_address', 'city', 'state'}),
                    18: (4, {'points'})}
    if index in allowed_user:
        uid, fields = allowed_user[index]
        delta = table_delta(initial, after, 'users')
        ok = not delta['added'] and not delta['removed'] and len(delta['changed']) == 1
        for before, now in delta['changed']:
            a, b = row_dict(initial, 'users', before), row_dict(after, 'users', now)
            ok = ok and a['id'] == uid and all(a[k] == b[k] for k in a if k not in fields)
        judge.check('exact_user_delta', ok, 'only the requested fields and account may change')
    if index in {9, 10, 11, 17}:
        table = 'payment_methods' if index == 9 else 'favorites'
        delta = table_delta(initial, after, table)
        ok = not delta['changed'] and len(delta['added']) == 1 and len(delta['removed']) == (1 if index in {9, 10} else 0)
        if index == 9:
            before = row_dict(initial, table, delta['removed'][0]) if delta['removed'] else {}
            added = row_dict(after, table, delta['added'][0]) if delta['added'] else {}
            ok = ok and before.get('user_id') == added.get('user_id') == 3 and added.get('is_default') == 1
        if index == 10:
            before = row_dict(initial, table, delta['removed'][0]) if delta['removed'] else {}
            added = row_dict(after, table, delta['added'][0]) if delta['added'] else {}
            ok = ok and before.get('user_id') == added.get('user_id') == 1
        judge.check('exact_related_row_delta', ok, 'preserve all existing unrelated rows')
    if index == 11:
        delta = table_delta(initial, after, 'users')
        judge.check('only_one_new_account', not delta['changed'] and not delta['removed'] and len(delta['added']) == 1,
                    'registration must preserve every existing account')


def entity_text(answer, entity):
    """Use paragraphs, sentences, bullets or table rows containing this entity.

    Decimal dots are retained. This deliberately bounded deterministic parser
    accepts local facts; it does not claim unrestricted coreference resolution.
    """
    chunks = re.split(r'\n+|;\s*|(?<=[.!?])\s+(?=[A-Z])|\s+(?:and|versus|vs\.?)\s+(?=(?:Element|citizenM|Residence Inn|The (?:Westin|Lexington)|Courtyard))', answer)
    return ' '.join(c for c in chunks if contains_phrase(c, entity))


def amount_for(answer, entity, value):
    return contains_amount(entity_text(answer, entity), value)


def _check_task_relations(judge, traj):
    i = int(traj['task_id'].split('--')[-1]);answer = traj['final_answer']
    if i in {1, 18}:
        # Redeemed points and remaining balance must not be exchanged.
        remaining = 129350 if i == 1 else 157400
        clauses = re.split(r'[;\n]|(?<=[.!?])\s+', answer)
        judge.check('balance_bound_to_remaining', any(re.search(r'remain|balance|left', c, re.I) and contains_amount(c, remaining) for c in clauses), 'remaining points balance')
    if i == 8:
        judge.check('answer_saved_profile', bool(re.search(r'updat|sav|chang', norm(answer))) and not re.search(r'not (?:updated|saved|changed)', norm(answer)), 'affirmative profile-save confirmation')
    if i == 9:
        judge.check('answer_card_expiration', bool(re.search(r'09/2029|9/2029|sep(?:tember)?\.?\s+2029', answer, re.I)), 'Visa expiry September 2029')
    if i == 7:
        judge.check('answer_extension_dates', bool(re.search(r'10/19/2026|October 19,? 2026|Oct\.? 19,? 2026', answer)) and bool(re.search(r'10/21/2026|October 21,? 2026|Oct\.? 21,? 2026', answer)), 'October 19–21 extension')
        judge.check('answer_extension_hotel', contains_phrase(answer, 'AC Hotel Atlanta Downtown'), 'same hotel')
    if i == 20:
        for entity, values in [('Midtown East', [4.5, 540, 54000]), ('Times Square', [4.0, 460, 46000])]:
            judge.check('bound_'+entity, all(amount_for(answer, entity, v) for v in values), 'rating, cash and points attached to correct property')
            judge.check('rating_'+entity, stated_rating(entity_text(answer, entity), values[0]), 'rating label attached to correct value')
    if i == 17:
        for entity, values in [('Lexington', [3.7, 4354, 739]), ('Westin', [3.9, 3997, 509])]:
            judge.check('bound_'+entity, all(amount_for(answer, entity, v) for v in values), 'review facts attached to correct property')
            judge.check('rating_'+entity, stated_rating(entity_text(answer, entity), values[0]), 'rating label attached to correct value')


def stated_cash_total(answer, expected):
    """Bind currency amounts to a total/cost, rejecting contradictory totals."""
    money = r'\$\s*([\d,]+(?:\.\d+)?)'
    patterns = [r'(?:total|cost)(?:\s+(?:shown|on|the|confirmation|page|is|was|of|for|stay|room|comes|to))*\s*[:=]?\s*' + money,
                money + r'\s*(?:in\s+)?total']
    values = [float(v.replace(',', '')) for p in patterns for v in re.findall(p, answer, re.I)]
    # Natural alternatives such as "340 dollars for the stay".
    values += [float(v.replace(',', '')) for v in re.findall(r'(?:total|cost)\s*(?:is|was|of|:)?\s*([\d,]+(?:\.\d+)?)\s*(?:US\s*)?dollars', answer, re.I)]
    return bool(values) and all(v == expected for v in values)


def comparison_claim(answer, winner, terms):
    clauses = re.split(r'\n|(?<=[.!?])\s+(?=[A-Z])', answer)
    matching = [c for c in clauses if any(re.search(t, c, re.I) for t in terms)]
    return any(contains_phrase(c, winner) and not re.search(r'\b(?:not|isn.t|is not)\b', c, re.I) for c in matching)


def check_answer_relations(judge, traj):
    _check_task_relations(judge, traj)
    i = int(traj['task_id'].split('--')[-1]);answer = traj['final_answer']
    totals = {0: 340, 3: 820, 4: 525, 5: 290, 6: 380, 7: 340, 14: 720, 15: 670, 16: 2350}
    if i in totals:
        judge.check('reported_cash_total', stated_cash_total(answer, totals[i]), 'currency amount bound to total, with no contradictory total')
    if i == 13:
        for entity, values in [('citizenM Miami Brickell', [170, 17000]), ('Element by Marriott Miami Brickell', [190, 19000])]:
            judge.check('rates_'+entity, all(amount_for(answer, entity, v) for v in values), 'cash and points belong to the property')
        judge.check('higher_rating_comparison', comparison_claim(answer, 'citizenM Miami Brickell', ['higher.*rating', 'better.*rat']), 'higher-rated property')
    if i == 17:
        judge.check('lower_one_star_share', comparison_claim(answer, 'Westin', ['lower.*share', 'fewer.*one.star', 'lower.*percentage']), 'Westin has lower one-star share')
    if i == 20:
        judge.check('cheaper_property', comparison_claim(answer, 'Times Square', ['cheaper', 'less expensive', 'lower.*(?:cash|rate|price)']), 'Times Square has lower cash rate')


def stated_rating(text, value):
    numbers = re.findall(r'(?:average\s+|guest\s+)?rat(?:ing|ed)\s*(?:of|is|:)?\s*(\d(?:\.\d+)?)', text, re.I)
    return bool(numbers) and all(float(n) == value for n in numbers)


def stated_capacity(answer, expected):
    numbers = re.findall(r'(?:sleeps?|sleeping|capacity(?:\s+of)?|accommodates)\s*(\d+|one|two|three|four)', answer, re.I)
    words = {'one': 1, 'two': 2, 'three': 3, 'four': 4}
    return bool(numbers) and all((int(n) if n.isdigit() else words[n.lower()]) == expected for n in numbers)
