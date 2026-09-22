"""Bounded natural-language checks for the ten frozen read-task answers.

Accept prose, short answers and labelled rows. Check quantities with their units
and properties, not a bag of numbers. These deterministic patterns intentionally
make no claim to general semantic understanding; regression examples document
supported phrasing and contradictions.
"""
from __future__ import annotations

import re
from fractions import Fraction

WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
         'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
         'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
         'thirty-eight': 38, 'thirty eight': 38, 'four point two': '4.2', 'one hundred and twenty': 120,
         'one hundred twenty': 120, 'four hundred and forty': 440,
         'four hundred forty': 440, 'a trio of': 3}
NUMBER = r'(?:\d+(?:\.\d+)?|' + '|'.join(re.escape(w) for w in sorted(WORDS, key=len, reverse=True)) + ')'
NEGATION = r"\b(?:not|never|no|isn't|isnt|wasn't|wasnt|incorrect|wrong|rather than)\b"


def clean(text):
    text = str(text).casefold().replace('’', "'").replace('–', '-').replace('—', ';')
    text = re.sub(r'\ba\.?\s*m\.(?=\s|$)', 'am', text)
    text = re.sub(r'\bp\.?\s*m\.(?=\s|$)', 'pm', text)
    text = re.sub(r"\bsix\s*(?:o'clock\s*)?(?:in the morning|am)\b", '6am', text)
    return re.sub(r'[ \t]+', ' ', text)


def clauses(text):
    # Decimal points and abbreviations have already been handled.
    return [s.strip(' |:-') for s in re.split(r'(?<!\d)\.|\.(?!\d)|[!?;\n]|\bbut\b|\bhowever\b', clean(text)) if s.strip()]


def affirmative(text, match):
    before = re.split(r'[,;]|\band\b|\bbut\b', text[:match.start()])[-1]
    after = text[match.end():]
    return not re.search(NEGATION, before) and not re.match(r'\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b', after)


def phrase(text, pattern):
    return any(affirmative(c, m) for c in clauses(text) for m in re.finditer(pattern, c))


def number(value):
    return Fraction(WORDS[value]) if value in WORDS else Fraction(value)


def quantity(text, units, expected, *, reverse=False):
    """All affirmative mentions of a property must agree, including unit scale.

    Unit dictionaries include plausible wrong units so '440 kHz' cannot satisfy
    a 440 Hz answer. Boundaries exclude reference IDs and embedded digit runs.
    """
    unit_pattern = '|'.join(re.escape(u) for u in sorted(units, key=len, reverse=True))
    patterns = [rf'(?<![\w.])(?P<number>{NUMBER})\s*[- ]?\s*(?P<unit>{unit_pattern})(?!\w)']
    if reverse:
        patterns.append(rf'\b(?P<unit>{unit_pattern})\s*(?:number|no\.?|mark|:|=|is|was)?\s*(?P<number>{NUMBER})(?!\w|\.\d)')
    values = []
    for c in clauses(text):
        for pattern in patterns:
            for m in re.finditer(pattern, c):
                if affirmative(c, m):
                    values.append(number(m['number']) * Fraction(str(units[m['unit']])))
    return bool(values) and all(v == Fraction(str(expected)) for v in values)


LENGTH = {'m': 1, 'meter': 1, 'meters': 1, 'metre': 1, 'metres': 1,
          'cm': '.01', 'centimeters': '.01', 'centimetres': '.01',
          'feet': '.3048', 'foot': '.3048', 'ft': '.3048'}
POWER = {'w': 1, 'watt': 1, 'watts': 1, 'kw': 1000, 'kilowatt': 1000, 'kilowatts': 1000}
FREQUENCY = {'hz': 1, 'hertz': 1, 'khz': 1000, 'kilohertz': 1000}
DAYS = {'day': 1, 'days': 1, 'week': 7, 'weeks': 7, 'month': 30, 'months': 30, 'hours': '1/24'}
DISTANCE = {'km': 1, 'kilometer': 1, 'kilometers': 1, 'kilometre': 1, 'kilometres': 1,
            'mile': '1.609344', 'miles': '1.609344', 'm': '.001', 'meters': '.001'}
HOURS = {'hour': 1, 'hours': 1, 'h': 1, 'hr': 1, 'hrs': 1, 'minutes': '1/60', 'days': 24}


def attribute(text, expected, subjects, alternatives, other_subjects=''):
    """Match an attribute of the requested subject, excluding competing claims.

    Short answer fragments need no repeated subject; a clause explicitly about
    another object's material/color does not supply the requested attribute.
    """
    relevant = []
    for c in clauses(text):
        for part in re.split(r'\band\b|[,|]', c):
            if other_subjects and re.search(rf'\b(?:{other_subjects})\b', part) and not re.search(rf'\b(?:{subjects})\b', part):
                continue
            relevant.append(part)
    good = False
    for c in relevant:
        if phrase(c, rf'\b(?:{expected})\b'):
            good = True
        if re.search(rf'\b(?:{subjects})\b', c) and phrase(c, rf'\b(?:{alternatives})\b'):
            return False
    return good


def restock_clauses(text):
    parts = clauses(text)
    named = [c for c in parts if re.search(r'\b(?:restock\w*|refill\w*|replenish\w*|stocked)\b', c)]
    return named or parts


def restock_day(text):
    parts = restock_clauses(text)
    days = []
    for c in parts:
        for m in re.finditer(r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b', c):
            if affirmative(c, m):
                days.append(m[0].removesuffix('s'))
    return bool(days) and all(d == 'thursday' for d in days)


def restock_time(text):
    found = []
    for c in restock_clauses(text):
        for m in re.finditer(r'(?<!\d)(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', c):
            if not (m[2] or m[3]) or not affirmative(c, m):
                continue
            hour = int(m[1]);minute = int(m[2] or 0)
            if m[3]:
                hour = hour % 12 + (12 if m[3] == 'pm' else 0)
            found.append((hour, minute))
    return bool(found) and all(t == (6, 0) for t in found)


def winner(text):
    if not phrase(text, r'\bcopper\b'):
        return False
    # A name-only answer identifies the winner after the required detail visit.
    # Explicit comparative assertions must identify the fox, never the cat/dog.
    for c in clauses(text):
        if phrase(c, r'\b(?:winner|most points|highest points)\s*(?:is|:|=|belongs? to)\s*(?:the\s+)?(?:rescue[- ]cat|cat|kayak(?:ing)?[- ]dog|dog|miso|pepper)\b'):
            return False
        if re.search(r'\b(?:most|highest|wins?|winner|greatest|leads?|more points)\b', c):
            if re.search(r'\b(?:cat|dog|miso|pepper)\b[^;.!?]{0,45}\b(?:has|is|wins?|leads?)\b[^;.!?]{0,25}(?:most|highest|winner|greatest|points)?', c):
                # Excluding the cat/dog is fine, asserting it wins is not.
                m = re.search(r'\b(?:cat|dog|miso|pepper)\b', c)
                if m and not re.search(NEGATION, c):
                    return False
            if re.search(r'\b(?:fox|copper)\b.{0,30}\b(?:does not|doesn.t|is not|isn.t)\b.{0,20}\b(?:most|highest|win|winner)\b', c):
                return False
    return True


def switches(text):
    if phrase(text, r'\b(?:clicky|linear)\s+switches\b'):
        return False
    return (phrase(text, r'\b(?:silent|quiet|silenced|noiseless)[, ]+(?:and\s+)?tactile(?:\s+switches)?\b')
            or phrase(text, r'\btactile[, ]+(?:and\s+)?(?:silent|quiet)\s+switches\b')
            or phrase(text, r'\btactile\s+switches\s+(?:that\s+are\s+|are\s+)?(?:silent|quiet)\b'))


def check(task, key, answer):
    a = clean(answer)
    tests = {
        0: {'width': lambda: quantity(a, LENGTH, '4.2'),
            'material': lambda: attribute(a, r'(?:reclaimed|salvaged|recycled|repurposed|reused)\s+oak|oak\s+(?:that\s+)?(?:was\s+|is\s+)?(?:reclaimed|salvaged|reused)', r'desk|desktop|tabletop', r'walnut|pine|plastic|steel|mahogany|maple', r'shelf|shelves|floor|door')},
        1: {'month': lambda: phrase(a, r'\bfebruary\b') and not phrase(a, r'\b(?:arriv\w*|adopt\w*|came)\b[^.!?;]{0,40}\b(?:january|march|april|may|june|july|august|september|october|november|december)\b'),
            'days': lambda: quantity(a, DAYS, 11)},
        2: {'power': lambda: quantity(a, POWER, 120),
            'protection': lambda: attribute(a, r'lunch[ -]?box', r'controller|protection', r'dry bag|plastic bag|tarp|umbrella', r'food|sandwiches')},
        3: {'frequency': lambda: quantity(a, FREQUENCY, 440),
            'feature': lambda: attribute(a, r'railings?|guardrails?', r'note|sound|resonat\w*|produc\w*|hums?|feature', r'cables?|deck|seam', r'paint|decoration')},
        4: {'color': lambda: attribute(a, 'blue', 'cabinet|colour|color', 'red|green|yellow|orange|black|white', 'flags?|books?|roof'),
            'day': lambda: restock_day(a), 'time': lambda: restock_time(a)},
        5: {'distance': lambda: quantity(a, DISTANCE, 38, reverse=True),
            'color': lambda: attribute(a, 'orange', 'flags?|colour|color', 'red|green|yellow|blue|black|white', 'shirts?|shoes?|banners?')},
        6: {'attempts': lambda: quantity(a, {'attempt': 1, 'attempts': 1, 'tries': 1, 'try': 1}, 3, reverse=True),
            'hours': lambda: quantity(a, HOURS, 14)},
        7: {'switches': lambda: switches(a),
            'case': lambda: attribute(a, 'acrylic|perspex|plexiglas|plexiglass', 'case|casing|housing', 'alumini?um|steel|wood', 'keycaps?|desk')},
        8: {'platform': lambda: quantity(a, {'platform': 1, 'platforms': 1}, 7, reverse=True) or bool(re.fullmatch(r'(?:7|seven)[.!]?', a.strip()))},
        9: {'name': lambda: winner(a)},
    }
    return bool(tests[task][key]())
