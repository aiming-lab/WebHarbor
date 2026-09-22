"""Bounded, offline parsing of the facts requested by AKC read tasks.

Supports ordinary prose, labelled lines and Markdown tables. This is not a
language model: unsupported or ambiguous assertions fail rather than earning
credit through a coincidental number/keyword match.
"""
from __future__ import annotations

from datetime import datetime
import re

from verify_lib import mentions, normalize

NUMBER_WORDS = dict(zip(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(),
    range(21),
))
# Unlike normalize(), retain line and table boundaries until facts are bound.
def canonical(text):
    text = '\n'.join(normalize(line) for line in str(text).splitlines())
    for word, number in NUMBER_WORDS.items():
        text = re.sub(r'\b' + word + r'\b', str(number), text)
    text = re.sub(r'\bbetween (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)', r'\1-\2', text)
    return text


def globally_denied(text):
    return bool(re.search(
        r'\b(?:following|these|all|above) (?:claims|facts|statements|answers)(?: below)? (?:are|were) (?:false|incorrect|wrong|untrue)\b',
        canonical(text),
    ))


def denied(text, start, end):
    """Polarity of a particular fact, not a ban on the word 'not'."""
    prefix = re.split(r'[;\n.!?]|\bbut\b|\bhowever\b', text[:start])[-1]
    return bool(re.search(r"\b(?:not|never|isn't|isnt|aren't|wasn't|false|incorrect|wrong|rather than|instead of)\b[^,;]*$", prefix)
                or re.match(r'\s*(?:(?:is|are)\s+(?:false|incorrect|wrong)|(?:is|was) not (?:the )?(?:author|venue|recommendation))\b', text[end:]))


def reference(text, start):
    return bool(re.search(r'\b(?:reference|example|quoted|quote)\b[^;\n.!?]*$', text[:start]))


def entity_blocks(answer, entities):
    """Bind rows/prose to named entities; propagate Markdown column labels."""
    text = canonical(answer)
    headers = None
    prepared = []
    for line in text.splitlines():
        if '|' in line:
            cells = [x.strip() for x in line.strip('|').split('|')]
            if any(re.search(r'\b(?:energy|trainability)\b', c) for c in cells) and not any(
                mentions(line, name) for names in entities.values() for name in names
            ):
                headers = cells
                continue
            if headers and len(headers) == len(cells):
                line = ' '.join(f'{header}: {cell}' for header, cell in zip(headers, cells))
        prepared.append(line)
    text = '\n'.join(prepared)
    hits = sorted((m.start(), m.end(), key) for key, names in entities.items()
                  for name in names for m in re.finditer(r'(?<!\w)' + re.escape(normalize(name)) + r'(?!\w)', text))
    nonoverlapping = []
    for hit in sorted(hits, key=lambda hit: (hit[0], -hit[1])):
        if not nonoverlapping or hit[0] >= nonoverlapping[-1][1]:
            nonoverlapping.append(hit)
    hits = nonoverlapping
    blocks = {key: [] for key in entities}
    for i, (start, end, key) in enumerate(hits):
        stop = hits[i+1][0] if i+1 < len(hits) else len(text)
        # Include local prefixes such as "not Border Collie" and "highest is".
        line_start = max(text.rfind('\n', 0, start), text.rfind(';', 0, start), text.rfind('. ', 0, start)) + 1
        prefix = text[line_start:start] if i == 0 or line_start >= hits[i-1][1] else ''
        blocks[key].append(prefix + text[start:stop])
    return {key: '\n'.join(parts) for key, parts in blocks.items()}


def subject_text(answer, name, names):
    entities = {candidate: [candidate] for candidate in names}
    blocks = entity_blocks(answer, entities)
    if any(blocks.values()):
        return blocks.get(name, '')
    # The required browser path already establishes a single subject.
    return answer


QUANTITY = re.compile(
    r'(?<![\w.])(?P<lo>-?\d+(?:\.\d+)?)'
    r'(?:\s*(?:-|to|through)\s*(?P<hi>-?\d+(?:\.\d+)?))?'
    r'\s*-?\s*(?P<unit>years?|yrs?|months?|pounds?|lbs?|kilograms?|kgs?|minutes?|mins?)\b'
)
PROPERTIES = re.compile(r'\b(life expectancy|lifespan|life span|lives?|weighs?|weight|read(?:ing)? time|takes?|height|energy|trainability|grooming|apartment fit)\b')


def quantity_facts(answer, expected):
    """Every assertion of a requested quantity must agree, including units."""
    if globally_denied(answer):
        return False
    text = canonical(answer)
    wanted = {}
    for value in expected:
        match = QUANTITY.fullmatch(canonical(value))
        if not match:
            return False
        unit = match['unit']
        kind = 'life' if unit.startswith(('year', 'yr', 'month')) else 'weight' if unit.startswith(('lb', 'pound', 'kg', 'kilogram')) else 'time'
        wanted[kind] = (float(match['lo']), float(match['hi'] or match['lo']))
    found = set()
    for match in QUANTITY.finditer(text):
        unit = match['unit']
        kind = 'life' if unit.startswith(('year', 'yr', 'month')) else 'weight' if unit.startswith(('lb', 'pound', 'kg', 'kilogram')) else 'time'
        if kind not in wanted or reference(text, match.start()):
            continue
        factor = 1/12 if unit.startswith('month') else 2.2046226218 if unit.startswith(('kg', 'kilogram')) else 1
        actual = tuple(float(x) * factor for x in (match['lo'], match['hi'] or match['lo']))
        tolerance = .15 if unit.startswith(('kg', 'kilogram')) else .001
        correct = all(abs(x-y) <= tolerance for x,y in zip(actual, wanted[kind]))
        if denied(text, match.start(), match.end()):
            if correct:
                return False
            continue
        # A weight-labelled value in years is not a lifespan assertion.
        prefix = re.split(r'[;.!?]|\band\b', text[:match.start()])[-1]
        labels = list(PROPERTIES.finditer(prefix))
        if labels:
            label = labels[-1].group()
            declared = 'weight' if label.startswith(('weigh',)) else 'life' if label.startswith(('life', 'live')) else 'time' if label.startswith(('read', 'take')) else None
            if declared is not None and declared != kind:
                return False
        if not correct:
            return False
        found.add(kind)
    return found == set(wanted)


RATING = re.compile(r'(?<![\w.])(?P<value>-?\d+(?:\.\d+)?)(?:\s*(?:/|out of|of)\s*(?P<scale>\d+(?:\.\d+)?)|\s*(?P<percent>%|percent))?(?!\w|\.\d)')


def rating(text, metric, value):
    text = canonical(text)
    found = False
    for m in RATING.finditer(text):
        prefix = re.split(r'[;\n.!?]', text[:m.start()])[-1]
        labels = list(PROPERTIES.finditer(prefix))
        if labels and labels[-1].group() not in {metric}:
            continue
        if reference(text, m.start()):
            continue
        suffix = text[m.end():]
        if re.match(r'\s*(?:/|out of\b|years?\b|months?\b|days?\b|hours?\b|minutes?\b|kgs?\b|lbs?\b|pounds?\b)', suffix):
            return False
        actual = float(m['value']) / 20 if m['percent'] else float(m['value'])
        correct = actual == value and (m['scale'] is None or float(m['scale']) == 5)
        if denied(text, m.start(), m.end()):
            if correct:
                return False
            continue
        if not correct:
            return False
        found = True
    return found


def winner(answer, entities, expected, *, terms=None):
    text = canonical(answer)
    if globally_denied(text):
        return False
    claims = []
    name_pattern = '|'.join(re.escape(normalize(name)) for names in entities.values() for name in names)
    name_to_key = {normalize(name): key for key,names in entities.items() for name in names}
    terms = terms or r'(?:higher|highest|winner|wins|most trainable|more trainable|more energetic|highest-rated|top-rated)'
    for clause in re.split(r'\n|(?<=[.!?])\s+', text):
        names = list(re.finditer(name_pattern, clause))
        for i,m in enumerate(names):
            stop = names[i+1].start() if i+1<len(names) else len(clause)
            tail = clause[m.end():stop]
            term = re.search(r'\b'+terms+r'\b', tail)
            if term:
                position = m.end()+term.start()
                if denied(clause, position, m.end()+term.end()):
                    if name_to_key[m.group()] == expected:
                        return False
                else:
                    claims.append(name_to_key[m.group()])
        # "The highest-rated breed is Papillon".
        prefix = re.search(r'\b'+terms+r'\b(?:\s+\w+){0,5}?\s+(?:is|:)\s*('+name_pattern+r')', clause)
        if prefix and not denied(clause, prefix.start(), prefix.end()):
            claims.append(name_to_key[prefix[1]])
        if len(names)==2 and re.search(r'\b(?:lower|less energetic|less trainable)\b.*\bthan\b', clause[names[0].end():names[1].start()]):
            claims.append(name_to_key[names[1].group()])
    return bool(claims) and set(claims) == {expected}


def named_fact(answer, expected, alternatives=()):
    if globally_denied(answer):
        return False
    text = canonical(answer)
    matches = list(re.finditer(r'(?<!\w)'+re.escape(normalize(expected))+r'(?!\w)', text))
    if not matches or any(denied(text,m.start(),m.end()) for m in matches):
        return False
    for other in alternatives:
        if normalize(other) == normalize(expected):
            continue
        for m in re.finditer(r'(?<!\w)'+re.escape(normalize(other))+r'(?!\w)',text):
            if not denied(text,m.start(),m.end()):
                return False
    return any(not reference(text,m.start()) for m in matches)


def event_date(answer, expected):
    if globally_denied(answer):
        return False
    text = canonical(answer)
    months = r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    pattern = re.compile(r'\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|'+months+r'\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+'+months+r'\s+\d{4})\b')
    found = False
    for m in pattern.finditer(text):
        raw = re.sub(r'(\d)(?:st|nd|rd|th)',r'\1',m.group()).replace(',','')
        parsed = None
        for fmt in ['%Y-%m-%d','%m/%d/%Y','%B %d %Y','%b %d %Y','%d %B %Y','%d %b %Y']:
            try: parsed = datetime.strptime(raw,fmt).date();break
            except ValueError: pass
        correct = parsed is not None and str(parsed) == str(expected)[:10]
        if reference(text,m.start()):continue
        if denied(text,m.start(),m.end()):
            if correct:return False
            continue
        if not correct:return False
        found=True
    return found
