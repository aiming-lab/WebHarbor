"""Conservative deterministic fact parsing, with benign format normalization.

Recognizes compact answers and explicit fact clauses, not arbitrary prose truth.
Never uses a language model. Unsupported/ambiguous prose is a task FAIL.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata


def norm(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = text.translate(str.maketrans({'–': '-', '—': '-', '−': '-', '’': "'"}))
    text = re.sub(r'(?<=\d)[,\s](?=\d{3}(?:\D|$))', '', text)
    return re.sub(r'\s+', ' ', text).strip()


NUMBER = r'(?<![\w.])\d+(?:\.\d+)?(?!\w|\.\d|,\d)'
MEASURE_NUMBER = r'(?<![\w.])\d+(?:\.\d+)?(?!\d|\.\d|,\d)'
MODELS = r'(?<!\w)(?:rtx\s*(?:pro\s*)?)?(?:50[0-9]0|40[0-9]0)(?:\s*ti)?(?:\s*super)?(?!\w)|(?<!\w)(?:gh200|h200|h100|a100)(?!\w)|(?<!\w)rtx\s+(?:pro\s+)?[645]000(?:\s+(?:blackwell|ada)(?:\s+generation)?)?(?!\w)'


def models(text):
    return [re.sub(r'\s+', ' ', m.group()).removeprefix('rtx ') for m in re.finditer(MODELS, norm(text))]


def negative_measure(text, kind):
    """An explicitly negative target number is never the requested positive spec."""
    if re.search(r'(?<![\w.])\s*-\s*(?:\d|\.\d)', norm(text)):
        return True
    if kind == 'memory' and re.search(r'-\s*(?:g(?:iga)?b(?:ytes?)?)', norm(text)):
        return True
    return False


def strip_harmless_contrasts(text):
    """Remove recognised non-target clarifications so -not X- contrast with
    another model, an unrelated metric or a variant name is not treated as denial
    of the requested fact. A denial of the target value (e.g. 'not 32 GB') is left
    intact for the caller to reject.

    Document-scope phrases ("not a live release feed", "frozen historical
    catalog") are deliberately NOT exempted here: only the driver tasks T9/T10
    carry a frozen-catalog qualifier, and predicates.driver_qualifier_scope applies
    that exemption for those two tasks alone (repair002, H2).
    """
    patterns = [
        r"\bnot\s+(?:its|the|a|an)?\s*(?:psu|power\s+supply|recommended\s+psu|"
        r"memory[- ]capacity\s+comparison|update\s+date)",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:photograph|product\s+photo)",
        r"\bnot\s+(?:(?:an?|the)\s+)?\d+\s*gb\s+variant",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:canada|germany|united\s+kingdom|uk|china|japan|france|"
        r"en[- ](?:ca|gb|de|cn|jp|fr))",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:nvidia\s+)?(?:geforce\s+)?(?:rtx\s+)?(?:pro\s+)?"
        r"(?:50[0-9]0|40[0-9]0|gh200|h200|h100|a100)(?:\s*ti|\s*super)?",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:ada(?:\s+lovelace)?|blackwell|hopper|ampere|lovelace)",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:tensor|rt|ray[- ]tracing|bandwidth|memory|tdp|power|psu|"
        r"capacity|vram|installation|download|game\s+ready|studio)(?:\s+cores?|\s+rating|\s+branch|\s+capacity)?",
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text)
    return text


def model_segments(text):
    """Split a normalised answer at real model mentions.

    Returns (name, following_text_until_next_model_or_sentence) pairs so a
    fact can be bound to the model it actually describes.
    """
    normed = norm(text)
    hits = list(re.finditer(MODELS, normed))
    out = []
    for index, hit in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(normed)
        piece = normed[hit.end():end]
        piece = re.split(r'(?<!\d)[.;!?](?:\s|$)', piece)[0]
        out.append((normed[hit.start():hit.end()], piece))
    return out


def names_model(name, token):
    """Whole-token model match (so h200 does not match inside gh200)."""
    return bool(re.search(r'(?<![\w.-])' + re.escape(token) + r'(?![\w-])', name))


def segment_ok(text, target, checks):
    """Bind each fact to the model it describes.

    - If the target model is named, every target mention must carry the
      expected facts; other models (a correct contrast) are ignored.
    - If only other models are named, the answer is about the wrong object.
    - If no model is named, the question supplies the object, so a bare
      value answer is checked directly (as before).
    """
    found = False
    for name, piece in model_segments(text):
        if not target(name):
            continue
        if not all(check(name + ' ' + piece) for check in checks):
            return False
        found = True
    if found:
        return True
    if model_segments(text):
        return False
    return all(check(norm(text)) for check in checks)


def only_model(text, expected):
    found = models(text)
    return bool(found) and all(m == expected for m in found)


def measurements(text, unit):
    units = {
        'memory': r'(?:g(?:iga)?b(?:ytes?)?|m(?:ega)?b(?:ytes?)?|t(?:era)?b(?:ytes?)?)',
        'power': r'(?:watts?|[km]?w)',
        'cuda': r'(?:cuda\s+cores?|tensor\s+cores?|rt\s+cores?|cores?)',
        'bandwidth': r'(?:[gmt]b\s*/\s*s|[gmt]bps|gigabytes?\s+per\s+second)',
    }
    out = []
    normed = norm(text)
    pattern = '(' + MEASURE_NUMBER + r')\s*(' + units[unit] + r')(?!\w)'
    for m in re.finditer(pattern, normed):
        out.append((Decimal(m[1]), re.sub(r'\s+', ' ', m[2])))
    # The site's own Tech Specs rows write the unit before the value
    # ("CUDA Cores  10,752"), so a value-first-only reader rejected a correct
    # number copied from the page the task points at (audit NVIDIA--1: medium).
    # The allowed-unit check in single_measure() still rejects another metric
    # ("Tensor Cores: 10,752") and a wrong value is still a wrong value.
    reverse = r'(?<!\w)(' + units[unit] + r')(?!\w)\s*[:=]?\s*(' + MEASURE_NUMBER + r')(?!\d)'
    for m in re.finditer(reverse, normed):
        out.append((Decimal(m[2]), re.sub(r'\s+', ' ', m[1])))
    return out


def single_measure(text, value, kind):
    allowed = {'memory': {'gb', 'gbyte', 'gbytes', 'gigabyte', 'gigabytes'},
               'power': {'w', 'watt', 'watts'}, 'cuda': {'core', 'cores', 'cuda core', 'cuda cores'}}[kind]
    if negative_measure(text, kind):
        return False
    values = measurements(text, kind)
    if values:
        if kind == 'power':
            scales = {'w': 1, 'watt': 1, 'watts': 1, 'kw': 1000, 'mw': 1000000}
            return all(unit in scales and n * scales[unit] == value for n, unit in values)
        return all(n == value and unit in allowed for n, unit in values)
    # Query establishes units for a bare scalar, but an explicitly wrong unit is never ignored.
    try:
        return Decimal(norm(text).strip(' .')) == value
    except InvalidOperation:
        return False


def memory(text, value, memory_type=None):
    ok = single_measure(text, value, 'memory')
    if memory_type:
        types = re.findall(r'(?<!\w)(?:gddr\s*\d+x?|lpddr\s*\d+|hbm\s*\d+e?)(?!\w)', norm(text))
        ok = ok and bool(types) and all(t.replace(' ', '') == memory_type.casefold() for t in types)
    return ok


def price(text, amount):
    text = norm(text)
    if re.search(r'-\s*\$\s*\d', text) or re.search(r'\$\s*-\s*\d', text):
        return False
    amounts = []
    for m in re.finditer(r'(?:\$|\busd\s*)\s*(' + NUMBER + r')|(' + NUMBER + r')\s*(?:usd|us\s+dollars?|dollars?)\b', text):
        amounts.append(Decimal(m[1] or m[2]))
    return bool(amounts) and all(p == amount for p in amounts)


def version(text, expected):
    found = re.findall(r'(?<![\w.])\d{3,}\.\d+(?:\.\d+)*(?!\w|\.\d)', norm(text))
    return bool(found) and all(v == expected for v in found)


def bandwidth_values(text):
    values = measurements(text, 'bandwidth')
    result = []
    for number, unit in values:
        u = unit.replace(' ', '')
        scale = Decimal('0.001') if u.startswith('mb') else Decimal(1000) if u.startswith('tb') else Decimal(1)
        value = number * scale
        # bits/s (gbps) is not bytes/s (gb/s); 8 bits per byte.
        if 'bps' in u and '/' not in u:
            value = value / 8
        result.append(value)
    return result


def bandwidth_comparison(text, higher, lower):
    """T7: bind absolute rates to GPUs; check optional differences separately.

    Percentage tolerance is half the last reported decimal place (at most
    half a percentage point). Omitted values/explanations remain optional.
    """
    text = strip_harmless_contrasts(norm(text))
    higher, lower = Decimal(str(higher)), Decimal(str(lower))
    # A decimal in an optional explanation must not interrupt subject/winner
    # recognition in the shared bounded direction parser.
    if not direction(re.sub(r'\d+\.\d+', 'value', text), '5080', '4080 super', 'bandwidth'):
        return False
    expected = {'5080': higher, '4080 super': lower}
    model_rx = re.compile(r'\b(?:geforce\s+)?(?:rtx\s+)?(5080|4080\s+super)\b')
    rate_rx = re.compile('(' + MEASURE_NUMBER + r')\s*([gmt]b\s*/\s*s|[gmt]bps|gigabytes?\s+per\s+second)\b')
    for raw in re.split(r'[;\n]+|(?<!\d)\.(?:\s+|$)', text):
        clause = norm(raw).replace('**', '')
        rates = list(rate_rx.finditer(clause))
        models_here = list(model_rx.finditer(clause))
        for index, match in enumerate(rates):
            value = bandwidth_values(match.group())[0]
            if match.start() and clause[match.start()-1] == '-':
                value = -value
            prefix = clause[:match.start()]
            end = rates[index+1].start() if index+1 < len(rates) else len(clause)
            suffix = clause[match.end():end]
            is_delta = bool(re.search(r'\b(?:by|(?:difference|delta|gap)(?:\s+(?:is|of))?)\s*[:=]?\s*$', prefix) or
                            re.match(r'\s*(?:\([^)]*\)\s*)?(?:higher|more|greater|extra|lower|less)\b', suffix))
            if is_delta:
                if value != higher - lower:
                    return False
                continue
            # Prefer explicit postfix attribution, e.g. "736 GB/s for RTX
            # 4080 SUPER", over a different model earlier in the sentence.
            following = model_rx.search(suffix)
            owner = None
            if following and re.fullmatch(r'\s*(?:for|on|of)\s+(?:the\s+)?', suffix[:following.start()]):
                owner = re.sub(r'\s+', ' ', following[1])
            if owner is None:
                preceding = [model for model in models_here if model.end() <= match.start()]
                if preceding:
                    last = preceding[-1]
                    # Don't reuse one subject for a second unbound rate.
                    if not any(last.end() <= rate.start() < match.start() for rate in rates):
                        owner = re.sub(r'\s+', ' ', last[1])
            if owner is None or value != expected[owner]:
                return False
        for match in re.finditer('(' + MEASURE_NUMBER + r')\s*(?:%|percent\b)', clause):
            reported = Decimal(match[1])
            if match.start() and clause[match.start()-1] == '-':
                reported = -reported
            # An inverse "4080 SUPER is ... lower than 5080" uses 960 as
            # denominator, whereas the requested winner's increase uses 736.
            decreasing = bool(re.search(r'\b(?:lower|less|decrease)\b', clause))
            actual = (higher - lower) / (higher if decreasing else lower) * 100
            places = len(match[1].split('.')[1]) if '.' in match[1] else 0
            tolerance = Decimal('0.5') * (Decimal(10) ** -places)
            if abs(reported - actual) > tolerance:
                return False
    return True


def direction(text, winner, loser, metric):
    text = norm(text)
    if any(model not in (winner, loser) for model in models(text)):
        return False
    # A concise named answer is sufficient when the question supplies the metric.
    if only_model(text, winner) and re.fullmatch(r'(?:the\s+)?(?:geforce\s+)?(?:rtx\s+)?' + re.escape(winner) + r'[.!]?', text):
        return True
    if re.search(r'\b(?:equal|same|tie|neither|not|no|less|lower|fewer)\b', text):
        # The unambiguous inverse form is handled below, rather than ignoring a negative token.
        inverse = re.search(r'(?:rtx\s+)?' + re.escape(loser) + r'\b[^.;]*\b(?:less|lower|fewer)\b[^.;]*\bthan\s+(?:(?:the|geforce)\s+)*(?:rtx\s+)?' + re.escape(winner) + r'\b', text)
        if not inverse or re.search(r'\b(?:equal|same|tie|neither|not|no)\b', text):
            return False
    if metric == 'cuda' and re.search(r'\b(?:tensor|bandwidth|rt\s+cores?)\b', text):
        return False
    if metric == 'bandwidth' and re.search(r'\b(?:cuda|tensor|tdp)\b', text):
        return False
    win = r'(?:rtx\s+)?' + re.escape(winner) + r'\b'
    lose = r'(?:rtx\s+)?' + re.escape(loser) + r'\b'
    # Subject must precede its predicate without another model taking over.
    model_free = r'(?:(?!\b(?:50\d0|40\d0)\b)[^.;]){0,100}'
    positive = re.search(win + model_free + r'(?:\b(?:more|higher|greater|faster|wins|winner)\b|>)', text)
    wrong = re.search(lose + model_free + r'(?:\b(?:more|higher|greater|faster|wins|winner)\b|>)', text)
    inverse = re.search(lose + model_free + r'(?:\b(?:less|lower|fewer)\b|<)', text)
    return bool((positive or inverse) and not wrong)


# Absolute CUDA counts of the two compared cards (GEAR: T6).
CUDA_ABS = {'5090': '21760', '4090': '16384'}
_CUDA_CARD = r'(?<!\w)(?:geforce\s+)?(?:rtx\s+)?(5090|4090)(?!\w)'
_CUDA_COMPARATIVE = r'\b(?:more|higher|greater|faster|larger|wins?|winner|leads?)\b'
_CUDA_LOWER = r'\b(?:fewer|less|lower|smaller)\b'
_CUDA_CONNECTOR = re.compile(
    r'^[\s(),/&+-]*(?:(?:vs\.?|versus|against|compared\s+to|and|then|to|with|at)\b[\s(),/&+-]*)*$')


def cuda_cards(text):
    """Ordered, de-duplicated card mentions (5090 / 4090 only)."""
    order = []
    for m in re.finditer(_CUDA_CARD, norm(text)):
        if m.group(1) not in order:
            order.append(m.group(1))
    return order


_CUDA_CLAUSE_SPLIT = re.compile(r'(?<!\d)[.;!?](?!\d)(?=\s|$)|;')


def cuda_claims(text, delta=None):
    """(kind, subject, object) comparative claims found in the answer's clauses.

    `kind` is 'higher' or 'lower', `subject` the card the comparative belongs to and
    `object` the card named after `than` (or None when the comparative stands
    alone). A clause break ends a card's ownership of a comparative, so "the 4090
    has 16,384; that is 5,376 more" does not read as a claim that the 4090 has more.
    "<card> has 5,376 more" stays a claim by that card; a bare restatement of the
    answer's delta after a count list ("… 16,384, so 5,376 more") does not.
    """
    normed = norm(text)
    delta_text = str(delta) if delta is not None else None
    claims = []
    for clause in _CUDA_CLAUSE_SPLIT.split(normed):
        cards = [(m.start(), m.end(), m.group(1)) for m in re.finditer(_CUDA_CARD, clause)]
        if not cards:
            continue
        for kind, pattern in (('higher', _CUDA_COMPARATIVE), ('lower', _CUDA_LOWER)):
            for m in re.finditer(pattern, clause):
                before = [card for card in cards if card[1] <= m.start()]
                after = [card for card in cards if card[0] >= m.end()]
                subject = before[-1] if before else None
                tail = clause[m.end():]
                if re.search(r'\bthan\b', tail) and after:
                    claims.append((kind, subject[2] if subject else None, after[0][2]))
                    continue
                if subject is None:
                    continue
                gap = clause[subject[1]:m.start()]
                if delta_text and delta_text in gap and not re.fullmatch(
                        r'\s*(?:has|is|with|owns|of)?\s*' + re.escape(delta_text) + r'\s*', gap):
                    continue
                claims.append((kind, subject[2], None))
    return claims


def cuda_direction(text, winner='5090', loser='4090', delta=None):
    """Which card the answer claims has more CUDA cores.

    The rubric's own wording puts the winner before its comparison and both absolute
    counts in a trailing parenthetical, which is why the earlier fixed-width window
    around the winner rejected it. Direction is read from the comparative claims and
    their subjects, so a trailing delta ("while the 4090 has 16,384; that is 5,376
    more") is bound to the sentence's subject and a reversed winner, an inverse
    form, an equality claim and a wrong metric all stay unambiguous.
    """
    normed = norm(text)
    if any(card not in (winner, loser) for card in models(normed)):
        return False
    if re.search(r'\b(?:equal|same|tie|neither)\b', normed):
        return False
    if re.search(r'\b(?:tensor|bandwidth|rt\s+cores?|tdp|watts?)\b', normed):
        return False
    accepted = False
    for kind, subject, obj in cuda_claims(normed, delta):
        if kind == 'higher':
            if subject == winner and obj in (None, loser):
                accepted = True
            elif (subject == loser and obj in (None, winner)) or obj == winner:
                return False
        else:
            if subject == loser and obj in (None, winner):
                accepted = True
            elif (subject == winner and obj in (None, loser)) or obj == loser:
                return False
    if accepted:
        return True
    if re.search(r'\b(?:in\s+favou?r\s+of|favou?ring|attributed\s+to|belongs\s+to)\s+(?:the\s+)?'
                 r'(?:geforce\s+)?(?:rtx\s+)?' + re.escape(winner) + r'\b', normed):
        return True
    order = cuda_cards(normed)
    if (order and order[0] == winner and delta is not None and cuda_counts_ok(normed)
            and re.search(r'\b' + re.escape(str(delta)) + r'\b\s*' + _CUDA_COMPARATIVE, normed)):
        # A trailing delta whose comparison sits in a separate clause: the winner is
        # the sentence's subject and the counts already fix the direction.
        return True
    return False


def cuda_counts_ok(text):
    """Bind absolute counts to the card they belong to.

    A value written inside its own card's clause binds to that card. When both
    counts sit in one trailing list after both cards were named (the rubric's own
    "(21,760 versus 16,384)"), the list follows the cards' mention order, which is
    how the sentence reads. An omitted list keeps the previous behaviour: a single
    absolute count belongs to the card mentioned before it.
    """
    normed = norm(text)
    counts = [(m.start(), m.group()) for m in re.finditer(r'\b(?:21760|16384)\b', normed)]
    if not counts:
        return True
    hits = list(re.finditer(_CUDA_CARD, normed))
    if not hits:
        return False
    order = []
    for hit in hits:
        if hit.group(1) not in order:
            order.append(hit.group(1))
    runs = []
    for position, value in counts:
        if runs:
            previous = runs[-1][-1]
            gap = normed[previous[0] + len(previous[1]):position]
            if _CUDA_CONNECTOR.match(gap):
                runs[-1].append((position, value))
                continue
        runs.append([(position, value)])
    for run in runs:
        if len(run) > 1:
            for index, (_, value) in enumerate(run):
                if index < len(order) and value != CUDA_ABS[order[index]]:
                    return False
                if index >= len(order) and value not in CUDA_ABS.values():
                    return False
        else:
            position, value = run[0]
            # Postfix attribution ("16,384 for the GeForce RTX 4090") names the card
            # after its own count, which is how a counts-first answer reads.
            tail = normed[position + len(value):]
            postfix = re.match(r'\s*(?:cuda\s+cores?\s+)?(?:for|on|of)\s+(?:the\s+)?(?:geforce\s+)?(?:rtx\s+)?'
                               r'(5090|4090)\b', tail)
            if postfix:
                owner = postfix.group(1)
            else:
                before = [hit.group(1) for hit in hits if hit.end() <= position]
                if not before:
                    return False
                owner = before[-1]
            if value != CUDA_ABS[owner]:
                return False
    return True


def cuda_compare(text, delta):
    """T6: the requested delta, the right metric and the right direction.

    Phrasing is not graded: the rubric's own sentence shape ("… 5,376 more CUDA
    cores … (21,760 versus 16,384)"), a counts-first shape and a trailing-delta
    shape are all accepted, while a reversed winner, a wrong metric, a wrong delta,
    an equality claim and swapped absolute counts all still fail.
    """
    normed = strip_harmless_contrasts(norm(text))
    if not cuda_direction(normed, '5090', '4090', delta):
        return False
    # The question establishes CUDA for a concise answer; an explicitly wrong
    # metric is rejected by cuda_direction(), without requiring a magic CUDA token.
    numbers = re.findall(NUMBER, normed)
    if str(delta) not in numbers:
        return False
    if not all(n in {'5090', '4090', '21760', '16384', str(delta)} for n in numbers):
        return False
    return cuda_counts_ok(normed)


def publication_date(text, expected):
    text = norm(text)
    # An era marker changes the date; it is not a formatting variant.
    if re.search(r'\b(?:bce|bc|ce|ad)\b', text):
        return False
    months = {name: i for i, name in enumerate(
        ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'], 1)}
    month_rx = '|'.join(m + '|' + m[:3] for m in months)
    found = []
    for m in re.finditer(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', text):
        found.append(tuple(map(int, m.groups())))
    for m in re.finditer(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b', text):
        a, b, y = map(int, m.groups())
        found.append((y, b, a) if a > 12 else (y, a, b))
    for m in re.finditer(r'\b(' + month_rx + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(\d{4})\b', text):
        month = next(v for k, v in months.items() if k.startswith(m[1]))
        found.append((int(m[3]), month, int(m[2])))
    for m in re.finditer(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(' + month_rx + r')\.?[,]?\s+(\d{4})\b', text):
        month = next(v for k, v in months.items() if k.startswith(m[2]))
        found.append((int(m[3]), month, int(m[1])))
    try:
        return bool(found) and all(date(*v).isoformat() == expected for v in found)
    except ValueError:
        return False


def jetson_compare(text):
    # Accumulate facts per product, not per mention. A table/paragraph may
    # establish capacity and identity once and later repeat a name in a summary.
    # Still validate EVERY explicit claim; a correct row cannot hide a later
    # swapped capacity, wrong identity, or reversed memory comparison.
    name_rx = re.compile(r'\b(?:jetson\s+)?(?:orin\s+)?nano\s+super\b|'
                         r'\b(?:jetson\s+)?orin\s+nx(?:\s*16\s*gb)?\b')
    kit_rx = r'\b(?:developer|development|dev)\s+kit\b'
    expected = {'nano': 8, 'nx': 16}
    facts = {key: set() for key in expected}
    active = None
    # Keep Markdown rows and sentence boundaries; norm() alone erases newlines.
    for raw in re.split(r'\n+|;|(?<!\d)[.!?](?:\s+|$)', text):
        clause = norm(raw).replace('**', '').replace('`', '')
        names = list(name_rx.finditer(clause))
        kinds = ['nano' if 'nano' in m.group() else 'nx' for m in names]
        if not names:
            # Support an immediate singular follow-up such as "It is a kit".
            if active and re.match(r'^(?:it|this product)\b', clause):
                clause = ('nano super ' if active == 'nano' else 'orin nx ') + clause
                names = list(name_rx.finditer(clause))
                kinds = [active]
            else:
                # Table headers/neutral introductions contain no asserted facts.
                if measurements(clause, 'memory') or re.search(kit_rx + r'|\bproduction module\b', clause):
                    return False  # Unbound fact: do not guess which product it describes.
                continue
        active = kinds[0] if len(set(kinds)) == 1 else None
        if len(names) >= 2:
            relation = clause[names[0].end():names[1].start()]
            if re.search(r'\b(?:twice|double|half|more|less|greater|lower|equal|same)\b', relation):
                if 'memory' not in relation or re.search(r'\b(?:not|never)\b', relation):
                    return False
                left, right = expected[kinds[0]], expected[kinds[1]]
                if re.search(r'\b(?:twice|double)\b', relation):
                    valid = left == 2 * right
                elif re.search(r'\bhalf\b', relation):
                    valid = 2 * left == right
                elif re.search(r'\b(?:more|greater)\b', relation):
                    valid = left > right
                elif re.search(r'\b(?:less|lower)\b', relation):
                    valid = left < right
                else:
                    valid = left == right
                if not valid:
                    return False
        for i, match in enumerate(names):
            kind = kinds[i]
            end = names[i+1].start() if i+1 < len(names) else len(clause)
            part = clause[match.end():end]
            opposite = r'(?:production\s+)?module' if kind == 'nano' else kit_rx
            part = re.sub(r'\bnot\s+(?:an?\s+)?' + opposite, '', part)
            if re.search(r'\b(?:not|never|maybe|perhaps)\b', part):
                return False
            claim = match.group() + ' ' + part
            values = measurements(claim, 'memory')
            if values:
                if not memory(claim, expected[kind]):
                    return False
                facts[kind].add('memory')
            types = re.findall(r'\b(?:lpddr|gddr|ddr|hbm)\s*\d+[a-z]*\b', claim)
            if any(t.replace(' ', '') != 'lpddr5' for t in types):
                return False
            kit = bool(re.search(kit_rx, part))
            module = bool(re.search(r'\bmodule\b', part))
            if kind == 'nano':
                # A kit comprises a module + carrier board; this is not a claim
                # that the kit IS a production module (even when names repeat).
                component = bool(re.search(r'\b(?:comprising|comprises|includes?|contains?|containing)\b[^|]*\bmodule\b', part))
                if re.search(r'\bproduction\s+module\b', part) or (module and not component):
                    return False
                if kit:
                    facts[kind].add('identity')
            else:
                if kit:
                    return False
                if module:
                    facts[kind].add('identity')
    return all(value == {'memory', 'identity'} for value in facts.values())


def blackwell_buying(text):
    text = strip_harmless_contrasts(norm(text))
    if not re.search(r'\bblackwell\b', text) or not re.search(r'\bnvidia\s+marketplace\b', text):
        return False
    if not re.search(r'\b(?:united\s+states|usa|u\.?s\.?a?\.?|en-us)\b', text):
        return False
    if models(text) and not only_model(text, '5080'):
        return False
    def generation(core, expected):
        names = {'tensor': r'tensor', 'rt': r'(?:rt|ray[- ]tracing)'}
        ordinal = r'(first|second|third|fourth|fifth|sixth|\d+(?:st|nd|rd|th)?)'
        gen = r'(?:gen(?:eration)?[- ]*)?'
        forward = re.findall(r'\b' + ordinal + r'[- ]*' + gen + names[core] + r'(?:\s+cores?)?\b', text)
        reverse = re.findall(r'\b' + names[core] + r'(?:\s+cores?)?\s*[:=-]?\s*(?:are\s+|is\s+|use\s+)?' + gen + ordinal + r'\b', text)
        words = dict(first=1, second=2, third=3, fourth=4, fifth=5, sixth=6)
        values = [words[v] if v in words else int(re.match(r'\d+', v)[0]) for v in forward + reverse]
        return bool(values) and all(v == expected for v in values)
    return (generation('tensor', 5) and generation('rt', 4) and
            not re.search(r'\b(?:instead|ada)\b', text) and
            not re.search(r'\bnot\s+(?:(?:the|a|nvidia)\s+)*(?:blackwell|marketplace|fifth|fourth|5th|4th|united\s+states)\b', text))
