"""Conservative natural-answer checks for labelled prices, durations and colors.

These checks accept prose, bullets and compact tables. They bind each asserted
measurement to its local subject; they do not implement arbitrary English
entailment. Unknown or ambiguous measurement claims fail closed.
"""
from decimal import Decimal
import re
import unicodedata

ONES = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
WORDS = {**ONES, **TENS}
NUMBER_WORDS = re.compile(r'\b(?:' + '|'.join(TENS) + r')(?:[ -](?:' + '|'.join(list(ONES)[1:10]) + r'))?\b|\b(?:' + '|'.join(ONES) + r')\b')


def normalize(answer):
    text = unicodedata.normalize('NFKC', answer).casefold().replace('’', "'")
    text = text.replace('**', '').replace('`', '')
    text = re.sub(r'[–—]', ' ', text)
    def number(match):
        return str(sum(WORDS[w] for w in re.split('[ -]', match[0])))
    return NUMBER_WORDS.sub(number, text)


def clauses(text):
    return [c.strip(' \t-•|') for c in re.split(r'(?<!\d)\.|\.(?!\d)|[;!\n]|\bbut\b|\bwhereas\b', text) if c.strip(' \t-•|')]


NEGATIVE = re.compile(r"\b(?:not|never|neither|false|incorrect|wrong|isn't|isnt|cannot|can't|no)\b")
UNCERTAIN = re.compile(r'\b(?:maybe|perhaps|possibly|unknown)\b|\?')
PRICE_LABEL = re.compile(r'\b(digital(?: album| edition| download)?|cassette(?: edition)?|signed(?: edition| poster)?|standard(?: edition)?|(?:colored )?vinyl|(?:compact disc|cd))\b')
AMOUNT = re.compile(r'(?<![\w.])(?P<prefix>us\s*\$|\$|usd\s*)?\s*(?P<number>\d+(?:\.\d+)?)(?:\s*(?P<suffix>usd|us dollars?|dollars?|cents?))?(?![\w.]|\.\d)')


def label_name(match):
    text = match[0]
    if 'vinyl' in text:
        return 'vinyl'
    if text in ('compact disc', 'cd'):
        return 'cd'
    return text.split()[0]


def price_answer(index, answer):
    target, prices = {
        0: ('cassette', {'cassette': '15', 'digital': '8.5', 'vinyl': '24'}),
        10: ('digital', {'digital': '8.5', 'cassette': '15'}),
        12: ('signed', {'signed': '27', 'standard': '19'}),
        13: ('digital', {'digital': '9.5', 'vinyl': '25', 'cd': '17.5'}),
    }[index]
    text = normalize(answer)
    if UNCERTAIN.search(text) or re.search(r'€|£|¥|\b(?:eur|euros?|gbp|pounds?|yen|cad|aud)\b', text):
        return False
    found = False
    for clause in clauses(text):
        labels = list(PRICE_LABEL.finditer(clause))
        amounts = list(AMOUNT.finditer(clause))
        # Reject a wrong cheapest-format claim even if the digital price is right.
        if index == 13 and re.search(r'\b(?:cheapest|least expensive|lowest(?: priced| price)?|minimum)\b', clause):
            comparative = re.search(r'\b(?:cheapest|least expensive|lowest(?: priced| price)?|minimum)\b', clause)
            preceding = [m for m in labels if m.end() <= comparative.start()]
            following = [m for m in labels if m.start() >= comparative.end()]
            winner = preceding[-1] if preceding else (following[0] if following else None)
            if winner is None or label_name(winner) != target or NEGATIVE.search(clause):
                return False
        if index == 13 and re.search(r'\b(?:most expensive|costliest|priciest)\b', clause):
            return False
        if not amounts:
            if any(label_name(m) == target for m in labels) and NEGATIVE.search(clause):
                return False
            continue
        for amount in amounts:
            # An id/reference is never evidence of price.
            prefix = clause[:amount.start()]
            if re.search(r'\b(?:reference|product|catalog|order)(?: number| id)?\s*[:#]?\s*$', prefix):
                continue
            preceding = [m for m in labels if m.end() <= amount.start()]
            following = [m for m in labels if m.start() >= amount.end()]
            subject = preceding[-1] if preceding else (following[0] if following else None)
            kind = label_name(subject) if subject else target
            # Bare amounts inherit the task subject. In prose, require a price
            # marker, label or predicate, rather than an incidental number.
            marked = amount['prefix'] or amount['suffix']
            bare = re.fullmatch(r'\s*(?:us\s*\$|\$|usd\s*)?\d+(?:\.\d+)?\s*(?:usd|us dollars?|dollars?|cents?)?\s*', clause)
            if not (marked or bare or subject or re.search(r'\b(?:costs?|price|priced|at)\b', clause)):
                continue
            if NEGATIVE.search(clause) or kind not in prices:
                return False
            value = Decimal(amount['number'])
            if amount['suffix'] and amount['suffix'].startswith('cent'):
                value /= 100
            if value != Decimal(prices[kind]):
                return False
            if kind == target:
                found = True
    return found


DURATION = re.compile(r'(?<![\w:])(?:(?P<minutes>\d+):(?P<seconds>\d{2})(?![\d:])|(?P<mins>\d+)\s*(?:minutes?|mins?)(?:\s*(?:and\s*)?(?P<secs>\d+)\s*(?:seconds?|secs?|s)\b)?|(?P<total>\d+)\s*(?:seconds?|secs?|s)\b)')
TRACK = re.compile(r'\b(?:(?:track|song)\s*(?P<number>[1-5])|(?P<ordinal>first|second|third|fourth|fifth)\s+(?:track|song)|(?P<title>incoming tide|mooring light|breakwater|low pier|morning channel))\b')


def duration_answer(answer):
    text = normalize(answer)
    if UNCERTAIN.search(text):
        return False
    seconds = {1: 184, 2: 213, 3: 242, 4: 271, 5: 300}
    titles = ['incoming tide', 'mooring light', 'breakwater', 'low pier', 'morning channel']
    ordinals = ['first', 'second', 'third', 'fourth', 'fifth']
    found = False
    for clause in clauses(text):
        durations = list(DURATION.finditer(clause))
        tracks = list(TRACK.finditer(clause))
        if not durations and tracks and re.search(r'\b(?:lasts?|duration|runs?|minutes?|seconds?|hours?|milliseconds?)\b', clause):
            return False
        for duration in durations:
            if NEGATIVE.search(clause):
                return False
            prior = [t for t in tracks if t.end() <= duration.start()]
            after = [t for t in tracks if t.start() >= duration.end()]
            subject = prior[-1] if prior else (after[0] if after else None)
            n = (int(subject['number']) if subject['number'] else ordinals.index(subject['ordinal']) + 1 if subject['ordinal'] else titles.index(subject['title']) + 1) if subject else 4
            if duration['seconds'] and int(duration['seconds']) >= 60:
                return False
            value = int(duration['total']) if duration['total'] else 60 * int(duration['minutes'] or duration['mins']) + int(duration['seconds'] or duration['secs'] or 0)
            if value != seconds[n]:
                return False
            found |= n == 4
    return found


def color_answer(answer):
    text = normalize(answer)
    if NEGATIVE.search(text) or UNCERTAIN.search(text):
        return False
    if not all(re.search(r'\b' + c + r'\b', text) for c in ('natural', 'forest')):
        return False
    # Enumerations may use "either ... or ..." when describing choices, but an
    # uncertain answer ("maybe", question mark) is not a complete enumeration.
    remainder = re.sub(r"\b(?:salt meadow(?:'s)?|field notes tote|you|can|choose|either|or|both|the|2|available|color|colour|colors|colours|variants|options|choices|are|is|and|in|for|comes|tote|natural|forest)\b", ' ', text)
    return not re.search(r'[a-z0-9]', remainder)
