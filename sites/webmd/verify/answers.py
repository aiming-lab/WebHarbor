"""Bounded natural-answer checks for this frozen task set.

Accept prose, labelled bullets/tables, and common number/unit equivalents. These
rules are intentionally local to the requested facts; they are not a general
semantic parser. Navigation and saved-state evidence are checked independently.
"""
import re
import unicodedata
from decimal import Decimal

NUMBERS = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
           'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
           'thirty': '30', 'sixty': '60', 'eighty': '80'}


def norm(text):
    text = unicodedata.normalize('NFKC', text).casefold().replace('’', "'")
    text = text.replace('—', ';').replace('–', '-').replace('&', ' and ')
    text = re.sub(r'\bhalf (?:an? )?hour\b', '30 minutes', text)
    text = re.sub(r'\ba quarter of an hour\b', '15 minutes', text)
    text = re.sub(r'\btwo hundred\b', '200', text)
    for word, number in NUMBERS.items():
        text = re.sub(r'\b' + word + r'\b', number, text)
    text = re.sub(r'\bmilligrams?\b', 'mg', text)
    text = re.sub(r'\bmicrograms?\b|µg|μg', 'mcg', text)
    text = re.sub(r'\bkilograms?\b', 'kg', text)
    text = re.sub(r'\bhours?\b|\bhrs?\.?', 'hours', text)
    text = re.sub(r'\bminutes?\b|\bmins?\.?', 'minutes', text)
    text = re.sub(r'(?<=\d)-(?=hours|minutes)', ' ', text)
    text = re.sub(r'\b(?:once (?:a day|daily)|1 time (?:a day|daily))\b', 'once daily', text)
    text = re.sub(r'\b(?:twice (?:a day|daily)|2 times (?:a day|daily)|bid|2x daily)\b', 'twice daily', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def has(text, pattern):
    return bool(re.search(pattern, text))


def clauses(text):
    # Preserve decimal points and date punctuation. Tables and bullets may
    # attach labels with colons or pipes instead of full sentences.
    return [s.strip(' -*|') for s in re.split(r';|\n|(?<!\d)\.(?!\d)|(?<=\d)\.(?!\d)', text) if s.strip(' -*|')]


def negative(text):
    text = re.sub(r'\bnot (?:only|less than|more than|before|until|exceed(?:ing)?)\b', '', text)
    return has(text, r"\b(?:not|never|neither|isn't|wasn't|doesn't|incorrect|wrong|instead of|rather than|except|excluding)\b")


def assertion(text, pattern):
    """An affirmative mention, with explicit denial of the same fact rejected."""
    yes = False
    for c in [part for clause in clauses(text) for part in re.split(r',\s+(?=not\b)|\s+(?=but\s+not\b)', clause)]:
        if not has(c, pattern):
            continue
        if negative(c):
            return False
        yes = True
    return yes


def names(text, *patterns):
    return all(assertion(text, r'\b(?:' + p + r')\b') for p in patterns)


def role(text, label, value, other_values=()):
    # Split when a second fact label begins, permitting one sentence containing
    # both author and reviewer, while binding each value to its own role.
    ok = False
    for sentence in clauses(text):
        # Inverse person-before-verb statements are bounded by the sentence.
        if has(sentence, r'^' + value + r'.{0,15}\b(?:wrote|reviewed)\b') and has(sentence, label):
            if negative(sentence) or any(has(sentence, x) for x in other_values):
                return False
            ok = True
            continue
        pieces = re.split(r'(?=\b(?:written by|author\b|review(?:ed|er| date)\b|medically reviewed|published|publication date)\b)', sentence)
        for part in pieces:
            if not has(part, label):
                continue
            part = re.split(r'\band (?=(?:medically|review|written|author|publish))', part)[0]
            if has(part, value):
                if negative(part):
                    return False
                ok = True
            if any(has(part, other) for other in other_values):
                return False
    return ok


def byline(text, author, reviewer):
    # Labelled values or conventional two-column "author / reviewer" tables.
    return (role(text, r'\b(?:written by|author|wrote)\b', author, [reviewer]) and
            role(text, r'\breview(?:ed|er)\b', reviewer, [author]))


def dates(text):
    # Normalize only complete date expressions, leaving the role attached.
    for day in (23, 27):
        formats = [rf'\bdec(?:ember)?\.?\s+{day}(?:st|rd|th)?,?\s+2024\b',
                   rf'\b{day}\s+dec(?:ember)?\.?\s+2024\b',
                   rf'\b2024-12-{day}\b', rf'\b12/{day}/2024\b']
        for pattern in formats:
            text = re.sub(pattern, f'date{day}', text)
    return (role(text, r'\b(?:published|publication date)\b', r'\bdate23\b', [r'\bdate27\b']) and
            role(text, r'\breview(?:ed| date)\b', r'\bdate27\b', [r'\bdate23\b']))


def quantities(text, unit_pattern):
    return [(Decimal(m.group(1)), m.group(2)) for m in re.finditer(
        r'(?<![\w.])(\d+(?:\.\d+)?)\s*(' + unit_pattern + r')\b', text)]


def dose(text, expected, *, frequency=None):
    values = quantities(text, r'mg|mcg|g|grams?')
    converted = [n * (1000 if u in ('g', 'gram', 'grams') else Decimal('.001') if u == 'mcg' else 1) for n, u in values]
    if not converted or any(n != Decimal(str(expected)) for n in converted) or negative(text):
        return False
    if frequency:
        if frequency not in text:
            return False
        bad = r'\b(?:twice|[2-9] times|hourly)\b' if frequency == 'once daily' else r'\b(?:once|[3-9] times|hourly)\b'
        if has(text, bad):
            return False
    return True


def count(text, expected, noun):
    found = []
    for c in clauses(text):
        if not has(c, noun):
            continue
        # Count next to the entity, or after a count/total label. This excludes
        # incidental ages, page numbers, dates and reference identifiers.
        pats = [r'\b(\d+)\s+(?:(?:medically reviewed|saved|selected|matching|of (?:the )?\d+ selected)\s+)?' + noun,
                noun + r'\s*(?:count|total|are|is|:|=|\|)+\s*(\d+)\b',
                r'\b(?:count|total)\s*(?:is|:|=|\|)?\s*(\d+)\b']
        for pat in pats:
            for m in re.finditer(pat, c):
                if negative(c):
                    return False
                found.append(int(m.group(1)))
    if re.fullmatch(r'\d+[.!]?', text):
        found.append(int(text.rstrip('.!')))
    return bool(found) and all(n == expected for n in found)


def answer_ok(task, answer, initial):
    t = norm(answer)
    if not t:
        return task in (16, 17)  # These tasks request saved state, not a report.
    if task == 0:
        return names(t, r'(?:miguel\s+)?santana')
    if task == 1:
        return dates(t)
    if task == 2:
        return byline(t, r'\b(?:sofia\s+)?andersson\b', r'\b(?:danielle\s+)?hart\b')
    if task == 3:
        return byline(t, r'\b(?:sofia\s+)?andersson\b', r'\b(?:karen\s+)?shale\b') and names(t, 'healthy living')
    if task == 4:
        # The requested starting dose must not be replaced by an escalation dose.
        starts = [c for c in clauses(t) if quantities(c, 'mg|mcg|g|grams?') and not has(c, r'\b(?:increase|increased|escalat)')]
        timing = any(has(c, r'\b30 minutes\b.{0,35}\bafter\b.{0,25}\bsame meal\b') and
                     not has(c, r'\bbefore\b') and not negative(c)
                     for c in clauses(t))
        return bool(starts) and all(dose(c, '.4', frequency='once daily') for c in starts) and timing
    if task == 5:
        return names(t, r'(?:steven\s+)?marsh', 'pharmd', 'bcps')
    if task == 6:
        wanted = ['ciprofloxacin', 'azithromycin', 'amoxicillin']
        others = ['rifampin', 'amiodarone', 'aspirin', 'doxycycline', 'penicillin', 'clarithromycin']
        return names(t, *wanted) and not any(assertion(t, r'\b' + x + r'\b') for x in others if has(t, r'\b' + x + r'\b'))
    if task == 7:
        return names(t, 'hormones', 'thyroid', r'hyperthyroidism|overactive thyroid', r'hypothyroidism|underactive thyroid')
    if task == 8:
        maxes = [c for c in clauses(t) if quantities(c, 'mg|mcg|g|grams?')]
        waits = [c for c in clauses(t) if has(c, r'\b(?:wait|second|repeat|another|interval)\b')]
        limit = any(has(c, r'\b(?:24 hours|1 day|daily|per day)\b') for c in maxes)
        wait = any(has(c, r'\b(?:at least|minimum|minimum of|wait|after|every)\s+(?:of\s+)?2 hours\b|\b2 hours\s+(?:minimum|apart|after|before)') and not negative(c) for c in waits)
        # Ignore the 24-hour maximum period; all other wait periods must be 2h.
        bad_wait = any(n != 2 for c in waits for n, u in quantities(c, 'hours') if n != 24)
        return bool(maxes) and all(dose(c, 200) for c in maxes) and limit and wait and not bad_wait
    if task == 9:
        # Split standard AFib dose from reduced-dose/DVT clauses before checking.
        standard = re.split(r'\b(?:reduc(?:ed|es)|dvt)\b', t, maxsplit=1)[0]
        age = has(t, r'\bage\s*(?:of\s*)?(?:>=|≥|at least)?\s*80\s*(?:\+|or older|or above|and (?:older|over)|years? or (?:older|above))|\b(?:at least|aged? >=|aged? ≥)\s*80\b')
        weight = has(t, r'\b(?:body )?weight\s*(?:of\s*)?(?:<=|≤|at most|no more than)?\s*60 kg\s*(?:or (?:less|below)|and (?:under|below))|\b(?:at most|no more than|<=|≤)\s*60 kg\b')
        creatinine = has(t, r'\b(?:elevated|raised|high|increased)\s+(?:serum\s+)?creatinine\b')
        age = age or has(t, r'\bage\s*(?:>=|≥|at least)\s*80\b')
        weight = weight or has(t, r'\b(?:body )?weight\s*(?:<=|≤|at most|no more than)\s*60 kg\b')
        reversed_criteria = negative(t) or has(t, r'\b(?:age.{0,12}(?:under|below|less than)\s*80|weight.{0,12}(?:over|above|more than)\s*60|(?:low|normal|decreased) creatinine)\b')
        return dose(standard, 5, frequency='twice daily') and age and weight and creatinine and not reversed_criteria
    if task == 10:
        return names(t, 'hydrochlorothiazide', r'(?:curtis\s+)?boone')
    if task == 11:
        return names(t, 'epley', 'ondansetron')
    if task == 12:
        winner = names(t, r'atrial fibrillation|a-?fib')
        match = count(t, 4, r'symptoms?') or (has(t, r'\b4\s+(?:of|out of|/)\s*(?:the )?4\b') and not negative(t))
        return winner and match
    if task == 13:
        return names(t, r'urinary tract infection|uti')
    if task == 14:
        reviewer = next(a for a in initial['authors'] if a['slug'] == 'lucia-ferreira-md')
        n = sum(a['reviewer_id'] == reviewer['id'] for a in initial['articles'])
        return names(t, r'(?:lucia\s+)?ferreira') and count(t, n, r'articles?')
    if task == 15:
        return names(t, 'jordan rivera')
    if task in (16, 17):
        return True  # The UI transition and precise DB change are authoritative.
    if task == 18:
        user = next(u for u in initial['users'] if u['email'] == 'carol.w@test.com')
        n = sum(r['user_id'] == user['id'] for r in initial['saved_articles'])
        return count(t, n, r'articles?')
    if task == 19:
        t = re.sub(r'atorvastatin,? not rosuvastatin,?', 'atorvastatin', t)
        winner = has(t, r'\batorvastatin(?:\x27s)?\s+(?:links?|has|lists?|covers?|includes?)\s+(?:the )?more\b|\b(?:winner|more conditions)\s*[:|=-]\s*atorvastatin\b')
        inverse = has(t, r'\brosuvastatin(?:\x27s)?\s+(?:links?|has|lists?|covers?|includes?)\s+(?:the )?more\b')
        # A compact count comparison is also an unambiguous winner statement.
        numeric = has(t, r'\batorvastatin\s*[:|(-]?\s*4\b') and has(t, r'\brosuvastatin\s*[:|(-]?\s*2\b')
        extras = names(t, 'chronic kidney disease', 'stroke')
        wrong_assignment = has(t, r'rosuvastatin(?:\x27s)?\s+(?:alone|only|uniquely).{0,35}(?:chronic kidney disease|stroke)') or has(t, r'(?:chronic kidney disease|stroke).{0,40}(?:only|unique).{0,20}rosuvastatin')
        denied_winner = any('atorvastatin' in c and 'more' in c and negative(c) for c in clauses(t))
        wrong_extra = has(t, r'(?:unique|only|extra|additional).{0,45}(?:coronary artery disease|high cholesterol)')
        return (winner or numeric) and not inverse and extras and not wrong_extra and not wrong_assignment and not denied_winner
    return False
