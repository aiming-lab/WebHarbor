"""Deterministic parsing of the factual answer forms used by OSU tasks.

Keep units and clause boundaries: a bag of expected tokens cannot distinguish
swapped comparisons or a GRE requirement from an unrelated portfolio policy.
These parsers cover explicit factual statements, not unrestricted prose.
"""
from __future__ import annotations

import re
from decimal import Decimal

from verify_lib import affirmative_contains, normalize_text

SMALL = dict(enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()))
WORDS = {word: number for number, word in SMALL.items()}
WORDS.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10))))
WORD_PATTERN = '|'.join(WORDS)
NUMBER = r'(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?!\w|\.\d)'


def numeric_text(text: str) -> str:
    text = normalize_text(text)
    def convert(match):
        return str(sum(WORDS[word] for word in re.split(r'[ -]', match[0])))
    return re.sub(rf'\b(?:{WORD_PATTERN})(?:[ -](?:one|two|three|four|five|six|seven|eight|nine))?\b', convert, text)


def clauses(text: str) -> list[str]:
    # Split before normalizing whitespace; decimal points remain intact.
    text = str(text).replace('\n', ';')
    text = re.sub(r'\b([BMP])\.\s*([SA])\.', r'\1\2', text)
    text = re.sub(r'\bPh\.\s*D\.', 'PhD', text)
    return [numeric_text(part).strip(' ,:') for part in re.split(
        r';|[!?]|\.(?!\d)(?=\s|$)|\b(?:and|while|whereas|versus|vs\.?|but|however)\b',
        text, flags=re.I,
    ) if part.strip(' ,:')]


def mentions(text: str, labels: tuple[str, ...]) -> list[re.Match]:
    pattern = '|'.join(re.escape(normalize_text(label)) for label in sorted(labels, key=len, reverse=True))
    return list(re.finditer(rf'(?<!\w)(?:{pattern})(?!\w)', text))


def numbers(text: str) -> list[tuple[re.Match, Decimal]]:
    return [(m, Decimal(m[0].replace(',', ''))) for m in re.finditer(NUMBER, text)]


def bound_count(text: str, expected: int, labels: tuple[str, ...]) -> bool:
    values = []
    for clause in clauses(text):
        for entity in mentions(clause, labels):
            candidates = numbers(clause)
            if not candidates:
                continue
            # Prefer a following count unless this is a comparison conclusion.
            following = [(m, n) for m, n in candidates if m.start() >= entity.end()]
            preceding = [(m, n) for m, n in candidates if m.end() <= entity.start()]
            if following:
                match, value = following[0]
                if re.search(r'\b(?:more|higher|fewer|less|difference)\b', clause[entity.end():match.start()]):
                    continue
            elif preceding:
                match, value = preceding[-1]
            else:
                continue
            values.append(value if affirmative_contains(clause, match[0]) else None)
    return bool(values) and all(value == expected for value in values)


def difference(text: str, expected: int) -> bool:
    values = []
    for clause in clauses(text):
        for match, value in numbers(clause):
            before, after = clause[:match.start()], clause[match.end():]
            if re.search(r'\b(?:difference|gap|by)\b[^\d]*$', before) or re.match(r'\s*(?:students?\s+)?(?:more|fewer)\b', after):
                values.append(value if affirmative_contains(clause, match[0]) else None)
    return bool(values) and all(value == expected for value in values)


def winner(text: str, higher: tuple[str, ...], lower: tuple[str, ...]) -> bool:
    outcomes = []
    for clause in clauses(text):
        comparison = re.search(r'\b(more|higher|larger|greater|fewer|less|lower|smaller)\b', clause)
        if not comparison:
            continue
        subjects = [(m.start(), True) for m in mentions(clause[:comparison.start()], higher)]
        subjects += [(m.start(), False) for m in mentions(clause[:comparison.start()], lower)]
        if not subjects:
            continue
        subject_is_higher = max(subjects)[1]
        is_more = comparison[0] in ('more', 'higher', 'larger', 'greater')
        outcomes.append(subject_is_higher == is_more and affirmative_contains(clause, comparison[0]))
    return bool(outcomes) and all(outcomes)


def venue_pair(text: str, pairs: tuple[tuple[str, tuple[str, ...]], ...]) -> bool:
    found = set()
    for clause in clauses(text):
        entities = [i for i, (_, labels) in enumerate(pairs) if mentions(clause, labels)]
        venues = [i for i, (venue, _) in enumerate(pairs) if mentions(clause, (venue,))]
        if not entities or not venues:
            continue
        if len(entities) != 1 or venues != entities:
            return False
        i = entities[0]
        if not affirmative_contains(clause, pairs[i][0]):
            return False
        found.add(i)
    return len(found) == len(pairs)


def quantity(text: str, expected: int, units: tuple[str, ...]) -> bool:
    unit = '(?:' + '|'.join(units) + ')'
    values = []
    for clause in clauses(text):
        # Both “90 credits” and “credits: 90”; do not bind a number across units.
        for pattern in (rf'({NUMBER})\s*[- ]?\s*{unit}\b', rf'\b{unit}\b\s*(?:(?:count|of|is|are|required|total)\s*)*[:=-]?\s*({NUMBER})'):
            for match in re.finditer(pattern, clause):
                value = Decimal(match[1].replace(',', ''))
                values.append(value if affirmative_contains(clause, match[0]) else None)
    return bool(values) and all(value == expected for value in values)


def duration_years(text: str, expected: int) -> bool:
    has_years = bool(re.search(r'\byears?\b', normalize_text(text)))
    has_months = bool(re.search(r'\bmonths?\b', normalize_text(text)))
    return (has_years or has_months) and (not has_years or quantity(text, expected, ('years?',))) and (not has_months or quantity(text, expected * 12, ('months?',)))


def money(text: str, expected: int) -> bool:
    values = []
    pattern = rf'(?P<currency>\$|\busd\s*)?(?P<number>{NUMBER})\s*(?P<scale>billion|million|thousand|bn\b|[bm]\b)?\s*(?P<dollars>dollars?\b|usd\b)?'
    for clause in clauses(text):
        for match in re.finditer(pattern, clause):
            if not (match['currency'] or match['scale'] or match['dollars']):
                continue
            value = Decimal(match['number'].replace(',', ''))
            value *= {'billion':10**9, 'bn':10**9, 'b':10**9, 'million':10**6, 'm':10**6, 'thousand':1000}.get(match['scale'], 1)
            values.append(value if affirmative_contains(clause, match[0].strip()) else None)
    return bool(values) and all(value == expected for value in values)


MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december')
MONTH_PATTERN = '|'.join(month + '|' + month[:3] + r'\.?' for month in MONTHS)


def date_matches(text: str, month: int, day: int, year: int | None = None) -> bool:
    text = normalize_text(str(text).replace('\n', ';'))
    dates = []
    patterns = (
        rf'(?P<month>{MONTH_PATTERN})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?',
        rf'(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<month>{MONTH_PATTERN})(?:,?\s+(?P<year>\d{{4}}))?',
        r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})',
        r'(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})',
    )
    for pattern in patterns:
        for match in re.finditer(rf'(?<!\w)(?:{pattern})(?!\w)', text):
            value = match['month'].rstrip('.')
            parsed_month = int(value) if value.isdigit() else next(i for i, name in enumerate(MONTHS, 1) if name.startswith(value))
            parsed_year = int(match['year']) if match['year'] else None
            dates.append(parsed_month == month and int(match['day']) == day and (year is None or parsed_year == year)
                         and affirmative_contains(text, match[0]))
    return bool(dates) and all(dates)


def gre_optional(text: str) -> bool:
    policies = []
    for clause in clauses(text):
        if not mentions(clause, ('gre',)):
            continue
        optional = re.search(r"\bgre\b\s*(?:exam|test|scores?)?\s*[:=-]?\s*(?:(?:is|are)\s+)?(?:not\s+(?:required|necessary|mandatory)|optional|waived|no\b|isn't\s+required)", clause)
        optional = optional or re.search(r"\b(?:does\s+not\s+require|doesn't\s+require|no)\s+(?:the\s+)?gre\b", clause)
        policies.append(bool(optional) and not re.search(r'\b(?:false|incorrect|untrue)\b', clause)
                        and not re.search(r'\bgre\b.*\b(?:is|are)\s+(?:required|mandatory)\b', clause))
    return bool(policies) and all(policies)


def football_record(text: str) -> bool:
    text = numeric_text(text)
    return affirmative_contains(text, '11-2') or (
        quantity(text, 11, ('wins?',)) and quantity(text, 2, ('loss(?:es)?',)))


def varsity_count(text: str) -> bool:
    text = numeric_text(text).strip(' .')
    if text == '36':
        return True
    return bound_count(text, 36, ('varsity sports', 'varsity teams'))


def engineering_degrees(text: str) -> bool:
    # Canonicalize common written-out degree names, then validate the complete
    # enumeration rather than maintaining a blacklist of wrong degree types.
    original = text
    text = normalize_text(text).replace('ph.d.', 'phd').replace('ph.d', 'phd').replace('b.s.', 'bs').replace('m.s.', 'ms')
    for pattern, canonical in ((r"bachelor(?:'s)?\s+of\s+science", 'bs'), (r"master(?:'s)?\s+of\s+science", 'ms'), (r'doctor\s+of\s+philosophy', 'phd')):
        text = re.sub(pattern, canonical, text)
    groups = re.findall(r'\b(?:bs|ms|phd)\b', text)
    if set(groups) != {'bs', 'ms', 'phd'}:
        return False
    if not all(affirmative_contains(text, degree) for degree in groups):
        return False
    # A count must describe the result, not an unrelated program's duration.
    numeric = numeric_text(text)
    count = bound_count(numeric, 3, ('types', 'degree types', 'distinct types', 'degrees'))
    count = count or bool(re.search(r'\b(?:3\s+(?:distinct\s+)?(?:degree\s+)?types?|(?:count|total)\s*(?:is|of|:|=)?\s*3)\b', numeric))
    if not count:
        return False
    # Remove surrounding explanatory prose, then inspect the actual enumeration.
    # Degree abbreviations outside the three matches remain unconsumed, including
    # previously unseen ones such as BEng; negated exclusions are separate clauses.
    for clause in [numeric_text(part) for part in re.split(r';|[!?]|\.(?=\s|$)', text)]:
        matches = list(re.finditer(r'\b(?:bs|ms|phd)\b', clause))
        if not matches:
            continue
        start = clause.rfind(':', 0, matches[0].start()) + 1
        if start == 0:
            prefix = re.search(r'\b(?:show|shows|list|lists|are|include|includes|found)\s+', clause[:matches[0].start()])
            start = prefix.end() if prefix else matches[0].start()
        enumeration = clause[start:]
        enumeration = re.split(r'\b(?:are|is|shown|listed|in|with|for|which|there|not|excluding)\b', enumeration)[0]
        remainder = re.sub(r'\b(?:bs|ms|phd|3|distinct|degree|types?|degrees?|total|count|and|or|but)\b', '', enumeration)
        if re.search(r'[a-z]', remainder):
            return False
    # Also reject affirmative extra degree abbreviations outside the enumeration.
    tokens = re.findall(r'\b(?:[A-Z]{2,8}|[BMPD][a-z]*[A-Z][A-Za-z]*)\b', original)
    return not any(token.casefold() not in {'bs', 'ms', 'phd'} and affirmative_contains(text, token) for token in tokens)
