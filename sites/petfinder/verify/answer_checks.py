"""Bounded deterministic English answer checks, independent of browser/state checks.

Accept prose, bullets and simple tables. This is not an unrestricted language
understander: unsupported formulations fail closed; see verify/README.md.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal


NUMBER_WORDS = dict(zip(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(),
    range(21),
))
NEGATIVE = r"\b(?:not|never|no|without|isn't|wasn't|doesn't|didn't|don't|cannot|can't)\b"


def text(value):
    value = unicodedata.normalize('NFKC', str(value)).casefold().replace('’', "'").replace('–', '-').replace('—', '-')
    value = re.sub(r'\b(?:' + '|'.join(NUMBER_WORDS) + r')\b', lambda m: str(NUMBER_WORDS[m[0]]), value)
    return re.sub(r'[^\S\n]+', ' ', value).replace('**', '').replace('`', '')


def clauses(value):
    return [s.strip() for s in re.split(r'(?<!\d)[.!?]|[.!?](?!\d)|[;\n]|\bbut\b', text(value)) if s.strip()]


def negated(value):
    return bool(re.search(NEGATIVE, value))


def mentions(value, names):
    found = []
    for name in names:
        # Pet first names are unique in the task candidate set.
        pattern = r'\b' + re.escape(text(name).split()[0]) + r'\b'
        found += [(m.start(), m.end(), name) for m in re.finditer(pattern, value)]
    return sorted(found)


def pet_named(value, name):
    first = text(name).split()[0]
    return any(re.search(r'\b' + re.escape(first) + r'\b', s) and not negated(s) for s in clauses(value))


def numeric_fact(value, expected, kind, entity=None, candidates=()):
    """Require all asserted values for one property/subject to equal expected.

    Units/field labels establish the property; local named subjects establish
    ownership. Reference numbers cannot satisfy a property, even if adjacent.
    """
    value = text(value)
    names = tuple(candidates) or ((entity,) if entity else ())
    found_names = mentions(value, names)
    values = []
    for m in re.finditer(r'(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?!\w|\.\d)', value):
        left = value[:m.start()]
        right = value[m.end():]
        prefix = re.split(r'(?<!\d)[.!?]|[.!?](?!\d)|[;\n]', left)[-1]
        suffix = re.split(r'[;\n]|(?<!\d)[.!?]|[.!?](?!\d)', right)[0]
        # Do not interpret reference IDs or list numbering as property values.
        if re.search(r'\b(?:reference|ref|id|number)\s*[:#]?\s*\$?\s*$', prefix):
            continue
        currency = re.search(r'(?:\$|usd\s*)\s*$', prefix) or re.match(r'\s*(?:dollars?|usd)\b', suffix)
        days = re.match(r'\s*days?\b', suffix) or re.search(r'\bdays?(?: on petfinder)?\s*[:|=()]\s*$', prefix)
        fee = currency or re.search(r'\b(?:adoption\s+)?(?:fee|cost|price)\s*(?:is|of|:|=|\|)?\s*\$?\s*$', prefix)
        count = re.match(r'\s*(?:favorite(?:s| pets)?|saved pets?|pets?)(?:\b)', suffix) or re.search(r'\b(?:favorite(?:s| pets)?|saved pets?|total|count)(?:\s+(?:is|of|remains|pets))?\s*[:|=(]*\s*$', prefix)
        # Plain table cells inherit an explicit property header.
        table = bool('|' in prefix and re.search({'fee': r'\b(?:fee|cost|price)\b', 'days': r'\bdays?\b', 'count': r'\bfavorites?\b'}[kind], value[:m.start()]))
        if not {'fee': fee, 'days': days and not currency, 'count': count and not currency}[kind] and not table:
            continue
        if kind == 'fee' and re.match(r'\s*(?:cents?|euros?|pounds?)\b', suffix):
            return False
        before = [x for x in found_names if x[1] <= m.start()]
        after = [x for x in found_names if x[0] >= m.end()]
        owner = before[-1][2] if before else None
        if after:
            between = value[m.end():after[0][0]]
            # "18 days for Maple", "With only 5 days, Ollie ...".
            if re.fullmatch(r'\s*(?:days?|dollars?)?\s*(?:for|by|at)\s+', between) or (not before and re.fullmatch(r'\s*(?:days?|dollars?)?\s*[,|:]?\s*', between)):
                owner = after[0][2]
        if entity and owner != entity:
            continue
        assertion_prefix = prefix
        if before and before[-1][0] >= m.start() - len(prefix):
            assertion_prefix = value[before[-1][1]:m.start()]
        if negated(assertion_prefix) or re.match(r"\s*(?:days?|dollars?)?\s*(?:is|was)?\s*not\b", suffix):
            return False
        values.append(Decimal(m[0].replace(',', '')))
    return bool(values) and all(n == Decimal(expected) for n in values)


def winner(value, expected, candidates, kind):
    pattern = r'\b(?:fewer(?: days)?|fewest(?: days)?|less time|shorter(?: time| stay)?|more recent(?:ly)?)\b' if kind == 'days' else r'\b(?:lowest(?: adoption fee| fee| cost)?|cheapest(?: to adopt)?|least expensive|least costly|minimum(?: fee)?)\b'
    winners = []
    for clause in clauses(value):
        names = mentions(clause, candidates)
        for m in re.finditer(pattern, clause):
            before = [x for x in names if x[1] <= m.start()]
            after = [x for x in names if x[0] >= m.end()]
            owner = before[-1] if before else after[0] if after else None
            if owner is None:
                continue
            assertion = clause[owner[1]:m.start()] if before else clause[:owner[0]]
            if negated(assertion):
                if owner[2] == expected:
                    return False
                continue
            winners.append(owner[2])
    return bool(winners) and set(winners) == {expected}


def checklist(value, kind):
    # Each group requires all concepts together in one affirmative list item or
    # clause, so disconnected keywords and negated instructions do not suffice.
    groups = [
        [r'\b(?:choose|select|find|pick)\b', r'\b(?:vet|veterinarian)\b', r'\b(?:save|keep|record|note)\b', r'\b(?:phone|number|contact)\b'],
        [r'\b(?:set up|prepare|create|arrange)\b', r'\bquiet\b', r'\b(?:room|space)\b', r'\bfood\b', r'\bwater\b', r'\b(?:comfortable|comfy|cozy)\b', r'\bbed\b'],
        [r'\b(?:check|inspect|review)\b', r'\bfences?\b', r'\bwindows?\b', r'\bplants?\b', r'\bhazards?\b'],
    ] if kind == 'adoption' else [
        [r'\b(?:set up|prepare|create|arrange)\b', r'\brabbit(?:-friendly| friendly)?\b', r'\b(?:space|home|area)\b'],
        [r'\b(?:offer|provide|give|supply)\b', r'\b(?:unlimited|unrestricted|constant)\b', r'\bgrass hay\b'],
        [r'\b(?:cover|protect|shield)\b', r'\bcords?\b', r'\b(?:unsafe|dangerous)\b', r'\bbaseboards?\b'],
        [r'\b(?:include|provide|add|supply)\b', r'\b(?:hide box|hiding box|hideaway)\b', r'\b(?:non-slip|nonslip|non slip|slip-resistant)\b', r'\b(?:flooring|floor|surface)\b'],
    ]
    parts = clauses(value)
    for group in groups:
        matches = [s for s in parts if all(re.search(p, s) for p in group)]
        if not matches or any(negated(s) for s in matches):
            return False
    return True


def inquiry_submitted(value):
    parts = clauses(value)
    for part in parts:
        # A conversational "No, it was rejected" is an affirmative rejection;
        # only negation immediately attached to the status reverses it.
        for m in re.finditer(r"\b(?:rejected|failed|pending|cancelled|canceled)\b", part):
            if not re.search(r"\b(?:not|never|isn't|wasn't)\s+$", part[:m.start()]):
                return False
        if re.search(r"\b(?:not|never)\s+submitted\b", part):
            return False
    return any(
        not re.search(r"\b(?:not|never|isn't|wasn't)(?: been)?\s*$", s[:m.start()])
        and not re.match(r"\s+(?:is|was)\s+not\b", s[m.end():])
        for s in parts for m in re.finditer(r"\bsubmitted\b", s)
    )


def no_duplicate(value):
    parts = clauses(value)
    positive = False
    for s in parts:
        duplicate = re.search(r'\b(?:duplicate|another|extra|second)\s+(?:favorite|entry|copy|pet)?\b', s)
        if duplicate and re.search(r'\b(?:added|created|saved)\b', s) and not negated(s):
            return False
        if (re.search(r'\b(?:already|previously|before this attempt)\b', s) and re.search(r'\b(?:saved|favorites?)\b', s) and not negated(s)) or (re.search(r'\b(?:nothing|none)\b.*\b(?:added|created)\b', s)) or (duplicate and negated(s)):
            positive = True
    return positive
