"""Bounded, deterministic parsing of prose, bullets and simple Markdown tables.

Require numbers to describe their entity/property, reject contradictory claims,
and accept common equivalent units/phrasing. This is not a general language model.
Unknown constructions fail closed; supported paraphrases are regression-tested.
"""
import re
import unicodedata


def normalize(text):
    return unicodedata.normalize('NFKC', text).casefold().replace('×', 'x').replace('—', '-').replace('–', '-').replace('’', "'")


def tag_entities(text, entities):
    text = normalize(text)
    # Longest names first; accept the title either with or without its extension.
    for i, name in sorted(enumerate(entities), key=lambda x: -len(x[1])):
        stem = re.sub(r'\.(?:epub|mp4|pdf)$', '', normalize(name))
        text = re.sub(re.escape(stem) + r'(?:\.(?:epub|mp4|pdf))?', f'ENTITY{i}', text)
    return text


def clauses(text):
    return re.split(r'[.!?](?=\s|$)|[;\n]|\b(?:but|however|whereas)\b', text)


def is_negated(text, start, end):
    before = re.split(r'[,;:]|\b(?:and|but|whereas)\b|ENTITY\d+', text[:start])[-1]
    after = text[end:]
    return bool(re.search(r"\b(?:not|never|no|isn't|isnt|wrong|incorrect)\b", before)
                or re.match(r"\s*(?:(?:is|are)\s+)?(?:not|wrong|incorrect)\b", after))


SMALL = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
ONES = '|'.join(SMALL)
TENS_PATTERN = '(?:' + '|'.join(TENS) + r')(?:[ -]+(?:' + '|'.join(list(SMALL)[1:10]) + '))?'
WORDS = rf'(?:(?:{ONES}) hundred(?:[ -]+(?:and[ -]+)?(?:{TENS_PATTERN}|{ONES}))?|{TENS_PATTERN}|{ONES})'
NUMBER = rf'(?:\d+(?:,\d{{3}})*|{WORDS})'



def integer(text):
    if text[0].isdigit():
        return int(text.replace(',', ''))
    total = 0
    for word in re.split(r'[ -]+', text):
        if word == 'hundred':
            total *= 100
        elif word != 'and':
            total += SMALL.get(word, TENS.get(word, 0))
    return total


def count_claims(text, entity, entities, unit, expected):
    """Accept e.g. '58 pages', 'page count: 58', words, and labelled table cells."""
    text = tag_entities(text, entities)
    target = f'ENTITY{entities.index(entity)}'
    claims = []
    # Markdown tables have explicit property columns; never interpret a bare ID.
    header = None
    for line in text.splitlines():
        cells = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(cells) > 1 and any(re.fullmatch(rf'{unit}s?(?: count)?', c) for c in cells):
            header = cells
        elif header and target in line and len(cells) == len(header):
            for col, value in zip(header, cells):
                if re.fullmatch(rf'{unit}s?(?: count)?', col) and re.fullmatch(NUMBER, value):
                    claims.append(integer(value) == expected)
    singular = unit.rstrip('s')
    patterns = [rf'(?<![\d.])(?P<n>{NUMBER})\s*[- ]?\s*{singular}s?\b',
                rf'\b(?:{singular}s|{singular} count)\s*(?:[:=]|(?:is|are|of|was|were|total(?:s|ing)?|comes to))?\s*(?P<n>{NUMBER})\b']
    last_subject = None
    for clause in clauses(text):
        mentions = list(re.finditer(r'ENTITY\d+', clause))
        for pattern in patterns:
            for m in re.finditer(pattern, clause):
                prior = [x for x in mentions if x.end() <= m.start()]
                future = [x for x in mentions if x.start() >= m.end()]
                subject = prior[-1].group() if prior else (future[0].group() if future else last_subject)
                if subject == target:
                    value = integer(m['n'])
                    if is_negated(clause, m.start(), m.end()):
                        if value == expected:
                            claims.append(False)
                    else:
                        claims.append(value == expected)
        if mentions:
            last_subject = mentions[-1].group()
    return bool(claims) and all(claims)


TIME_PATTERN = re.compile(r'(?<![\d:])(?:(?P<mins>\d+):(?P<secs>[0-5]\d)(?!\d)|(?P<m>\d+)\s*(?:minutes?|mins?\.?|m)\s*(?:and\s*)?(?P<s>\d+)\s*(?:seconds?|secs?\.?|s)\b)')


def runtime_claims(text, entities, expected):
    text = tag_entities(text, entities)
    def time_token(m):
        return f'TIME{int(m["mins"] or m["m"])*60 + int(m["secs"] or m["s"])}'
    text = TIME_PATTERN.sub(time_token, text)
    claims = {i: [] for i in range(len(entities))}
    seen_entities = []
    for clause in clauses(text):
        names = list(re.finditer(r'ENTITY(\d+)', clause))
        times = list(re.finditer(r'TIME(\d+)', clause))
        for n in names:
            if int(n[1]) not in seen_entities:
                seen_entities.append(int(n[1]))
        if 'respectively' in clause:
            order = [int(n[1]) for n in names] or seen_entities
            if len(order) == len(times):
                for i, t in zip(order, times):
                    claims[i].append(int(t[1]) == expected[i] and not is_negated(clause, t.start(), t.end()))
                continue
        # Inverted subject: 'At 27:03, longer than City ... , is Open Data ...'.
        trailing = re.search(r'\b(?:is|was)\s+(ENTITY\d+)\s*$', clause.strip())
        if trailing and len(times) > 1 and times[0].start() < (names[0].start() if names else 0):
            clause = trailing[1] + ' ' + clause[:trailing.start()]
        tokens = list(re.finditer(r'ENTITY(\d+)|TIME(\d+)', clause))
        assigned = set()
        # Explicit '19:05 for City Cycling ...' binds to the following title.
        for a, b in zip(tokens, tokens[1:]):
            gap = clause[a.end():b.start()]
            if a[2] and b[1] and re.fullmatch(r'\s*(?:(?:for|by|belongs to|is the runtime of)\s+|[-:()]\s*)', gap):
                i = int(b[1]);claims[i].append(int(a[2]) == expected[i] and not is_negated(clause, a.start(), a.end()));assigned.add(a.start())
        for a, b in zip(tokens, tokens[1:]):
            if a[1] and b[2] and b.start() not in assigned:
                i = int(a[1]);claims[i].append(int(b[2]) == expected[i] and not is_negated(clause, b.start(), b.end()));assigned.add(b.start())
        # Unknown unbound runtimes cannot be used as filler to satisfy the answer.
        if any(t[2] and t.start() not in assigned for t in tokens):
            return False
    return all(values and all(values) for values in claims.values())


def winner_claim(text, winner, losers):
    entities = [winner, *losers]
    text = tag_entities(text, entities)
    if 'ENTITY0' not in text:
        return False
    saw = False
    order = []
    for clause in clauses(text):
        names = list(re.finditer(r'ENTITY(\d+)', clause))
        for n in names:
            if n[1] not in order:
                order.append(n[1])
        for cue in re.finditer(r'\b(longer|longest|most|more|highest|largest|biggest|shorter|shortest|less|fewer|fewest|smaller|smallest|lower|lowest)\b', clause):
            before = [n for n in names if n.end() <= cue.start()]
            after = [n for n in names if n.start() >= cue.end()]
            trailing = re.search(r'\b(?:is|was)\s+ENTITY(\d+)\s*$', clause.strip())
            near = clause[max(0,cue.start()-25):cue.end()+25]
            if trailing and not before:
                subject = trailing[1]
            elif re.search(r'\bformer\b', near) and order:
                subject = order[0]
            elif re.search(r'\blatter\b', near) and order:
                subject = order[-1]
            else:
                subject = before[-1][1] if before else (after[0][1] if after else None)
            if subject is None:
                return False
            inverse = cue.group() in {'shorter','shortest','less','fewer','fewest','smaller','smallest','lower','lowest'}
            negated = is_negated(clause, cue.start(), cue.end())
            credits_winner = (not inverse) != negated
            if (subject == '0') != credits_winner:
                return False
            saw = True
    return saw or (order and order[0] == '0')
