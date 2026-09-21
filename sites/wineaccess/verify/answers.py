"""Bounded natural-answer checks, separate from browser and database evidence.

These rules cover benchmark facts and common paraphrases, not arbitrary English.
Entity-bound amounts, comparison direction and negation are checked explicitly.
"""
import re
import unicodedata


def norm(value):
    value = unicodedata.normalize('NFKD', str(value or '').replace('–', '-').replace('—', '-')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', value.replace(',', '')).strip()


def clauses(value):
    return [norm(s) for s in re.split(r'(?<!\d)\.(?!\d)|[;\n]|\b(?:but|whereas|while)\b', value, flags=re.I) if s.strip()]


def negative(s):
    return bool(re.search(r"\b(?:not|never|cannot|cant|isnt|doesnt|dont|no|couldnt)\b|n['’]t\b", s))


def affirmative(text, pattern):
    return any(re.search(pattern, s) and not negative(s) for s in clauses(text))


def money(s):
    matches = re.findall(r'(?:\$\s*|\b(?:price|costs?|usd)\s*(?:is|of|:|at)?\s*)(\d+(?:\.\d+)?)|\b(\d+(?:\.\d+)?)\s*(?:dollars|usd)\b', s)
    return [float(a or b) for a, b in matches]


def amount(s, expected):
    return any(abs(x - expected) < .005 for x in money(s))


def windows_match(text, entities):
    matches = list(re.finditer('|'.join('(?:' + pattern + ')' for pattern, _ in entities), text))
    for k, match in enumerate(matches):
        segment = text[match.end():matches[k+1].start() if k+1 < len(matches) else len(text)]
        # The vintage can precede the next product's name; it is not a window.
        years = {int(y) for y in re.findall(r'\b20\d{2}\b', segment) if int(y) >= 2026}
        allowed = next(set(years_) for pattern, years_ in entities if re.fullmatch(pattern, match.group()))
        if not years <= allowed:
            return False
    return True


def comparison(text, winner, loser, windows=None):
    s = norm(text)
    # Permit an explicit exclusion of the other candidate.
    s = re.sub(r'\bnot\s+' + loser + r'\b', '', s)
    if not re.search(winner, s):
        return False
    if re.search(loser + r'.{0,45}\b(?:is|has)\s+(?:the\s+)?(?:later|latest|longer|lower|cheaper|less expensive)', s):
        return False
    if re.search(winner + r'.{0,45}\b(?:is|has)\s+(?:the\s+)?(?:earlier|shorter|higher|more expensive)', s):
        return False
    for c in clauses(s):
        if re.search(winner, c) and negative(c):
            return False
    if windows and not windows_match(s, [(winner, windows[0]), (loser, windows[1])]):
        return False
    return True


def pairings(text, patterns, require_all=False):
    checks = [affirmative(text, p) for p in patterns]
    if any(re.search(p, c) and negative(c) for p in patterns for c in clauses(text)):
        return False
    return all(checks) if require_all else any(checks)


def answer_ok(index, text, ctx=None):
    ctx = ctx or {}
    s = norm(text)
    if not s:
        return False
    if index in {0, 1, 5, 7, 10, 13}:
        # State tasks are graded by the exact saved outcome, not a hidden template.
        return not re.search(r'\b(?:unable|failed|could not|did not (?:add|save|update|join|remove)|not saved)\b', s)
    if index == 2:
        return comparison(text, r'fantesca(?: estate)?(?: chardonnay)?', r'dumol(?: chloe)?(?: chardonnay)?', ((2026, 2037), (2026, 2034)))
    if index == 3:
        return bool(re.search(r'pessac[- ]leognan', s) and affirmative(text, r'pessac[- ]leognan') and amount(s, 950) and all(abs(v-950) < .005 for v in money(s)) and not any(negative(c) for c in clauses(text) if money(c)))
    if index == 4:
        return pairings(text, [r'fried chicken', r'triple[- ]cream(?: cheese)?', r'celebrations?'])
    if index == 6:
        numbers = re.findall(r'\b\d{10,}\b', s)
        return numbers == ['9400111899'] and affirmative(text, r'\b9400111899\b')
    if index == 8:
        return bool(re.search(r'2026\s*(?:-|to|through|until|and)\s*2031', s) or ('2026' in s and '2031' in s)) and set(re.findall(r'\b20\d{2}\b', s)) <= {'2021', '2026', '2031'} and not negative(s)
    if index == 9:
        if not comparison(text, r'bank shot', r'le pich'):
            return False
        if not re.search(r'lower|cheaper|less(?: expensive)?|lowest|more affordable', s):
            # Explicit entity-bound prices also establish the requested comparison.
            if not ('$' in s or 'price' in s):
                return False
        mentions = list(re.finditer(r'bank shot|le pich', s))
        for k, m in enumerate(mentions):
            segment = s[m.end():mentions[k+1].start() if k+1 < len(mentions) else len(s)]
            expected = 39.6 if m.group() == 'bank shot' else 57.2
            values = money(segment)
            values += [float(x) for x in re.findall(r'\b\d+\.\d{1,2}\b', segment)]
            values += [float(x) for x in re.findall(r'^\s*[:|]\s*(\d+(?:\.\d+)?)', segment)]
            if any(abs(x-expected) >= .005 for x in values):
                return False
            if re.search(r'\b(?:case|12 bottles)\b', segment) and not re.search(r'per bottle|a bottle|each|bottle by the case|case price per', segment) and values:
                # Reject per-case totals mislabeled as per-bottle amounts.
                if re.search(r'per case|for (?:a |the )?case|case total', segment):
                    return False
        return True
    if index == 11:
        address = all(x in s for x in ('122 camino oruga', 'building a', 'napa', '94558'))
        phone = re.findall(r'\(?\b\d{3}\)?[ .-]*\d{3}[ .-]*\d{4}\b', s)
        return address and [re.sub(r'\D', '', p) for p in phone] == ['8669463923'] and not any(negative(c) for c in clauses(text) if 'camino' in c or '866' in c)
    if index == 12:
        return comparison(text, r'(?:maison leroy )?gevrey[- ]chambertin', r'(?:nuits[- ]saint[- ]georges|clos de tart)') and affirmative(text, r'\b2035\b') and windows_match(s, [(r'(?:maison leroy )?gevrey[- ]chambertin', (2026,2035)), (r'(?:maison leroy )?nuits[- ]saint[- ]georges', (2026,2032)), (r'clos de tart', (2026,2033))])
    if index == 14:
        allowed = (ctx.get('old_total'), ctx.get('new_total'))
        return not re.search(r'unchanged|did not change|not changed|did not remove', s) and all(any(v is not None and abs(x-v)<.005 for v in allowed) for x in money(s))
    if index == 15:
        return not re.search(r'paltrinieri|campo della fortuna', s) and pairings(text, [r'roast(?:ed)? chicken', r'shellfish', r'spring (?:vegetables|veg)'], require_all=True)
    if index == 16:
        number = ctx.get('order', {}).get('order_number', '').lower()
        numbers = re.findall(r'\bwa-\d{6}-\d+\b', s)
        return bool(number and numbers == [number] and affirmative(text, re.escape(number)))
    if index == 17:
        weather = re.search(r'heat|cold|hot|freez|extreme temperatures?|weather', s)
        purpose = re.search(r'protect|safe|condition|quality|prevent.{0,12}damage|avoid.{0,12}damage', s)
        action = any(re.search(r'delay|hold|postpone|pause|defer|suspend|wait', c) and not negative(c) for c in clauses(text))
        action = action or bool(re.search(r'(?:not|never|dont|do not) ship.{0,35}(?:heat|cold|weather|extreme)', s))
        bad = re.search(r'(?:cannot|cant|do not|dont|not|never)\s+(?:be\s+)?(?:delay|hold|postpone|pause|defer)|ship(?:s|ping)?\s+(?:immediately|regardless)', s)
        return bool(weather and purpose and action and not bad)
    return False
