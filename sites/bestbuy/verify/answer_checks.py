"""Bounded offline fact checks for natural Best Buy answers.

Accept prose, labelled values and common number/unit equivalents. These checks
are deliberately not a general semantic judge: ambiguous claims fail closed.
"""
from __future__ import annotations

import re
import unicodedata

ONES = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
WORDS = ONES | TENS | {'hundred': 100, 'thousand': 1000}
NUMBER = r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.]|\.\d)'
BOUNDARY = r'[;\n!?]|(?<!\d)\.(?!\d)|\b(?:but|however)\b'


def canonical(answer: str) -> str:
    text = unicodedata.normalize('NFKC', answer).casefold().replace('’', "'").replace('–', '-').replace('—', '-')
    text = re.sub(r'(?<=\d),(?=\d{3}\b)', '', text)
    text = re.sub(r'\b(' + '|'.join(WORDS) + r')-(' + '|'.join(WORDS) + r')\b', r'\1 \2', text)
    pattern = r'\b(?:' + '|'.join(WORDS) + r')(?:\s+(?:and\s+)?(?:' + '|'.join(WORDS) + r'))*\b'
    def number(m):
        total = current = 0
        for word in m.group().split():
            if word == 'and': continue
            if word == 'hundred': current *= 100
            elif word == 'thousand': total += current * 1000; current = 0
            else: current += WORDS[word]
        return str(total + current)
    text = re.sub(pattern, number, text)
    text = re.sub(r'\b(\d+) and a half\b', lambda m: str(int(m[1]) + .5), text)
    text = re.sub(r'\b(\d+) dollars?(?: and)? (\d+) cents?\b', lambda m: '$' + str(int(m[1]) + int(m[2])/100), text)
    text = re.sub(r'\b(?:no|none|zero)(?= (?:available )?certificates?\b)', '0', text)
    return text


def denied(text: str, start: int, end: int) -> bool:
    prefix = re.split(BOUNDARY, text[:start])[-1]
    # A negation after a completed assertion refers to the next claim.
    return bool(re.search(r"\b(?:not|never|neither|nor|isn't|aren't|wasn't|don't|doesn't|do not|does not|instead of|rather than)\b[^,;]*$", prefix)
                or re.match(r'\s*(?:(?:is|are|was) )?(?:false|incorrect|wrong|not included|not required)\b', text[end:]))


def reference(text: str, start: int) -> bool:
    return bool(re.search(r'\b(?:reference|ref|example|quoted|sku|identifier)\s*(?:number|id)?\s*[:#=]?\s*$', text[:start]))


def global_denial(text: str) -> bool:
    return bool(re.search(r'\b(?:these|above|following|all) (?:facts|claims|statements|answers) (?:are|were) (?:false|wrong|incorrect)\b', text))


def facts(answer: str, patterns: list[str], expected: float) -> bool:
    text = canonical(answer)
    if global_denial(text): return False
    found = False
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            if reference(text, m.start()): continue
            value = float(m['value'])
            correct = abs(value - expected) < .00001
            if denied(text, m.start(), m.end()):
                if correct: return False
                continue
            if not correct: return False
            found = True
    return found


VALUE = r'(?P<value>(?<![\w.])-?\d+(?:\.\d+)?)(?!\w|\.\d)'
MONEY = [r'(?:\$|\busd)\s*' + VALUE, VALUE + r'\s*(?:dollars?|usd)\b', r'\b(?:price|costs?|difference)\s*(?:is|of|:|=)?\s*' + VALUE]


def price(answer: str, expected: float) -> bool:
    return facts(answer, MONEY, expected)


def rating(answer: str, expected: float) -> bool:
    text = canonical(answer)
    patterns = [r'\b(?:rating|rated|score)\s*(?:is|of|:|=)?\s*' + VALUE,
                VALUE + r'\s*(?:stars?|★|out of\s*\d|/\s*\d)']
    if not facts(text, patterns, expected): return False
    for m in re.finditer(VALUE + r'\s*(?:stars?\s*)?(?:/|out of|of)\s*(?P<scale>\d+(?:\.\d+)?)', text):
        if float(m['value']) == expected and not denied(text, m.start(), m.end()) and float(m['scale']) != 5:
            return False
    return True


def rewards(answer: str, points: int, certificates: int) -> bool:
    return (facts(answer, [VALUE + r'\s*(?:reward )?(?:points?|pts)\b', r'\b(?:points?|balance)\s*(?:balance|is|:|=)*\s*' + VALUE], points)
            and facts(answer, [VALUE + r'\s*(?:available )?certificate(?:s|\(s\))?\b', r'\bcertificates?\s*(?:available|is|:|=)*\s*' + VALUE], certificates))


def lenses(answer: str) -> bool:
    text = canonical(answer); wanted = {(18.,55.),(75.,300.)}; seen = set()
    if global_denial(text): return False
    for m in re.finditer(r'(?<![\w.])(?P<lo>\d+(?:\.\d+)?)\s*(?:-|to|through)\s*(?P<hi>\d+(?:\.\d+)?)\s*(?P<unit>mm|millimeters?|millimetres?|cm|centimeters?)\b', text):
        factor = 10 if m['unit'].startswith(('cm','centimeter')) else 1
        value = (float(m['lo'])*factor,float(m['hi'])*factor)
        if denied(text,m.start(),m.end()):
            if value in wanted:return False
            continue
        if value not in wanted:return False
        seen.add(value)
    return seen == wanted


def positive_mentions(answer: str, pattern: str) -> bool:
    text=canonical(answer);seen=False
    if global_denial(text):return False
    for m in re.finditer(pattern,text):
        if reference(text,m.start()):continue
        if denied(text,m.start(),m.end()):return False
        seen=True
    return seen


def pickup_status(answer: str) -> bool:
    text=canonical(answer)
    if not positive_mentions(text,r'\b(?:pickup|pick up|collected in store|in-store (?:collection|pickup))\b'):return False
    if not positive_mentions(text,r'\bdelivered\b'):return False
    for m in re.finditer(r'\b(?:processing|preparing shipment|shipped|cancelled|canceled|ready for pickup)\b',text):
        if not denied(text,m.start(),m.end()):return False
    return True


def pickup_requirements(answer: str) -> bool:
    return positive_mentions(answer,r'\border (?:number|confirmation number)\b') and positive_mentions(answer,r'\b(?:photo(?:graphic)? (?:id|identification)|government-issued photo identification)\b')


def savings(answer: str, expected: float) -> bool:
    return positive_mentions(answer,r'\b(?:hp\s*[- ]*omnibook|omnibook)\b') and facts(answer,[VALUE+r'\s*(?:%|percent(?:age)?|per cent)'],expected)


def cheaper(answer: str, difference: float) -> bool:
    text=canonical(answer)
    # Prices of both products may be included; bind the delta to its comparison.
    deltas=[r'\b(?:by|difference(?: is| of)?|save[sd]?)\s*\$?\s*'+VALUE,
            r'\$?\s*'+VALUE+r'\s*(?:dollars?\s*)?(?:cheaper|less expensive|less than|lower)']
    if not facts(text,deltas,difference):return False
    found=False
    for clause in re.split(BOUNDARY,text):
        hp=re.search(r'\b(?:hp|omnibook|6672899)\b',clause);dell=re.search(r'\b(?:dell|6668953)\b',clause)
        for m in re.finditer(r'\b(?:cheaper|less expensive|lower[- ]priced|more expensive|costlier|less than|more than)\b',clause):
            before=clause[:m.start()];entities=list(re.finditer(r'\b(hp|omnibook|6672899|dell|6668953)\b',before))
            who=entities[-1][1] if entities else ('hp' if hp and not dell else 'dell' if dell and not hp else None)
            if who is None:continue
            correct=(who in ('hp','omnibook','6672899')) == (m[0] in ('cheaper','less expensive','lower-priced','lower priced','less than'))
            if denied(clause,m.start(),m.end()):
                if correct:return False
                continue
            if not correct:return False
            found=True
    return found


def order_number(answer: str, expected: str) -> bool:
    text=canonical(answer);found=False
    for m in re.finditer(r'\bbby-\d+\b',text):
        if reference(text,m.start()):continue
        correct=m[0]==expected.casefold()
        if denied(text,m.start(),m.end()):
            if correct:return False
            continue
        if not correct:return False
        found=True
    return found
