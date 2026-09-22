"""Entity-bound checks for the expanded Best Buy research tasks."""
import re
import answer_checks as a


def expand_tables(answer):
    """Give bare Markdown table values the units supplied by their headers."""
    headers = None
    lines = []
    for line in answer.splitlines():
        if '|' not in line:
            lines.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if any(re.fullmatch(r'points|certificates|total|(?:dollar )?savings|discount(?: %)?', cell, re.I) for cell in cells):
            headers = [cell.casefold() for cell in cells]
            continue
        if headers and len(cells) == len(headers):
            for i, (header, cell) in enumerate(zip(headers, cells)):
                if not re.fullmatch(r'[\d,.]+', cell):
                    continue
                if header == 'points': cells[i] += ' points'
                elif header == 'certificates': cells[i] += ' certificates'
                elif header in {'total', 'savings', 'dollar savings'}: cells[i] = '$' + cell
                elif header.startswith('discount'): cells[i] += '%'
        lines.append(' | '.join(cells))
    return '\n'.join(lines)


def entity_text(answer, aliases):
    """Keep facts attached to the nearest preceding named entity (also tables)."""
    text = a.canonical(expand_tables(answer))
    if a.global_denial(text):
        return {}
    pattern = '|'.join(f'(?P<e{i}>{alias})' for i, alias in enumerate(aliases.values()))
    matches = list(re.finditer(pattern, text))
    result = {key: [] for key in aliases}
    keys = list(aliases)
    for i, match in enumerate(matches):
        if a.denied(text, match.start(), match.end()):
            return {}
        key = keys[int(match.lastgroup[1:])]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[key].append(text[match.end():end])
    return {key: '\n'.join(parts) for key, parts in result.items()}


def difference(answer, expected, unit='money'):
    value = a.VALUE
    suffix = r'\s*(?:points?|pts)\b' if unit == 'points' else r'\s*(?:dollars?|usd)?'
    patterns = [r'\b(?:by|difference(?: is| of)?|premium(?: is| of)?|extra(?: cost)?(?: is| of)?)\s*[:=]?\s*\$?\s*' + value + suffix,
                r'\$?\s*' + value + suffix + r'\s*(?:extra|more|higher|greater)\b']
    text = a.canonical(answer)
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if unit == 'money' and re.match(r'\s*(?:points?|pts|percent|%|hours?|minutes?)\b', text[match.end():]):
                return False
            if match.start() and text[match.start() - 1] in '€£¥':
                return False
    return a.facts(answer, patterns, expected)


def camera_premium(answer, expected):
    return a.lenses(answer) and difference(answer, expected) and not re.search(
        r'\b(?:starter(?: bundle)?|11834823)\s+(?:is |costs )?(?:more|higher|pricier)', a.canonical(answer))


def fact_text(answer):
    clauses = re.split(r"[;\n]|\.(?!\d)", expand_tables(answer))
    return '\n'.join(c for c in clauses if not re.search(r'\b(?:higher|lower|more|fewer|greater|less|difference|leads)\b', c, re.I))


def reward_comparison(answer, accounts, delta):
    entities = entity_text(fact_text(answer), {'alice': r'\balice(?:\.j@test\.com)?\b', 'bob': r'\bbob(?:\.c@test\.com)?\b'})
    if not entities or not all(a.rewards(entities[key], *values) for key, values in accounts.items()):
        return False
    subjects = entity_text(answer, {'alice': r'\balice\b', 'bob': r'\bbob\b'})
    higher = a.positive_mentions(subjects.get('bob', ''), r'\b(?:higher|more|greater|leads)\b')
    lower = a.positive_mentions(subjects.get('alice', ''), r'\b(?:lower|fewer|less)\b')
    wrong = (re.search(r'\b(?:higher|more|greater|leads)\b', subjects.get('alice', ''))
             or re.search(r'\b(?:lower|fewer|less)\b', subjects.get('bob', '')))
    return bool((higher or lower) and not wrong and difference(answer, delta, 'points'))



def order_comparison(answer, orders, higher, delta):
    entities = entity_text(fact_text(answer), {key: rf'\b{re.escape(key.lower())}\b' for key in orders})
    if not entities:
        return False
    for number, (method, status, total) in orders.items():
        part = entities[number]
        method_pattern = r'\b(?:pickup|pick up|collected in store)\b' if method == 'pickup' else r'\b(?:delivery|shipping|ship to home)\b'
        status_pattern = r'\bdelivered\b' if status == 'Delivered' else r'\b(?:shipped|dispatched)\b'
        if not (a.positive_mentions(part, method_pattern) and a.positive_mentions(part, status_pattern) and a.price(part, total)):
            return False
        wrong = r'\b(?:processing|cancelled|canceled|ready for pickup|' + ('shipped|delivery|shipping' if method == 'pickup' else 'delivered|pickup') + r')\b'
        if re.search(wrong, part):
            return False
    # Comparison sentences may repeat an order number; omit their delta from totals.
    text = a.canonical(answer)
    subjects = entity_text(answer, {key: rf'\b{re.escape(key.lower())}\b' for key in orders})
    return difference(answer, delta) and a.positive_mentions(subjects.get(higher, ''), r'\b(?:higher|more|greater)\b') and not any(re.search(r'\b(?:higher|more|greater)\b', part) for key, part in subjects.items() if key != higher)


def pickup_plan(answer, aisle):
    text = a.canonical(answer)
    if not (a.pickup_requirements(answer)
            and (a.facts(answer, [a.VALUE + r'\s*(?:hours?|hrs?)\b'], 1) or a.facts(answer, [a.VALUE + r'\s*(?:minutes?|mins?)\b'], 60))
            and a.positive_mentions(answer, rf'\b{re.escape(aisle.lower())}\b')):
        return False
    for match in re.finditer(r'\b[a-z]-\d+\b|\btomorrow\b|\b(?:in|within) \d+ hours?\b', text):
        if match[0] not in {aisle.lower(), 'in 1 hour', 'within 1 hour'} and not a.denied(text, match.start(), match.end()):
            return False
    return True


def deals(answer, expected):
    entities = entity_text(answer, {'omnibook': r'\b(?:omnibook(?: 3)?|6672899)\b', 'victus': r'\b(?:victus|6623881)\b'})
    return bool(entities) and all(
        a.facts(entities[key], [a.VALUE + r'\s*(?:%|percent|per cent)'], percent)
        and a.price(entities[key], saving)
        for key, (percent, saving) in expected.items())
