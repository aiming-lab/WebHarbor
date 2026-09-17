"""Small answer checks shared by the IMDb task verifiers.

Accept prose and ordinary Markdown tables. Monetary answers may use the
displayed precision or the exact catalog value, with equivalent unit names.
Run provenance and screenshot authenticity are checked outside this parser.
"""
from datetime import datetime
from decimal import Decimal
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace('’', "'").replace('–', '-').replace('—', '-')
    return re.sub(r'[\t ]+', ' ', text.replace('**', '').replace('`', '')).strip()


def mentions(text, phrase):
    """Whole phrase, without an immediately negated assertion."""
    text, phrase = normalize(text), normalize(phrase)
    pattern = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
    found = list(re.finditer(pattern, text))
    return bool(found) and all(
        not re.search(r'\b(?:not|neither|except|isn\x27t|wasn\x27t)\s+(?:the\s+)?$',
                      text[max(0, m.start() - 30):m.start()])
        for m in found
    )


def has_number(text, value):
    expected = Decimal(str(value))
    return any(Decimal(m.group().replace(',', '')) == expected
               for m in re.finditer(r'(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?!\w|\.\d)', normalize(text)))


AMOUNT = re.compile(
    r'(?<![\w.])(?P<currency>\$|usd\s*)?\s*'
    r'(?P<number>\d[\d,]*(?:\.\d+)?)\s*'
    r'(?P<unit>billion|million|thousand|bn|mn|[bmk])?(?!\w)', re.I)
SCALE = {'billion': 10**9, 'bn': 10**9, 'b': 10**9,
         'million': 10**6, 'mn': 10**6, 'm': 10**6,
         'thousand': 10**3, 'k': 10**3}


def amount_values(text):
    values = []
    for m in AMOUNT.finditer(normalize(text)):
        value = Decimal(m['number'].replace(',', ''))
        unit = m['unit'] or ''
        if m['currency'] or unit or (value >= 1000 and not 1900 <= value <= 2100):
            values.append(value * SCALE.get(unit, 1))
    return values


def displayed_money(value):
    if value is None:
        raise ValueError('Missing catalog amount')
    for scale in (10**9, 10**6, 10**3):
        if value >= scale:
            return Decimal(f'{value / scale:.1f}') * scale
    return Decimal(value)


def has_amount(text, value):
    allowed = {Decimal(value), displayed_money(value)}
    values = amount_values(text)
    return bool(values) and all(v in allowed for v in values)


MONEY_FIELDS = {
    'budget': ('production budget', 'budget'),
    'opening': ('opening weekend us & canada', 'opening weekend', 'opening gross', 'opening'),
    'worldwide': ('gross worldwide', 'worldwide gross', 'worldwide', 'global gross'),
    'domestic': ('gross us & canada', 'domestic gross', 'us gross', 'domestic'),
}


def money_field(text, field, value, allow_unlabeled=False):
    text = normalize(text)
    # Ordinary prose also puts the amount before its label. When a clause has
    # only one money field, the direction does not change the binding.
    clauses = re.split(r'[;|\n]|\band\b', text)
    single_field_clauses = []
    for clause in clauses:
        present = {key for key, variants in MONEY_FIELDS.items()
                   if any(re.search(r'(?<!\w)' + re.escape(label) + r'(?!\w)', clause)
                          for label in variants)}
        if present == {field} and amount_values(clause):
            single_field_clauses.append(clause)
    if single_field_clauses:
        return all(has_amount(clause, value) for clause in single_field_clauses)
    labels = []
    for key, variants in MONEY_FIELDS.items():
        for variant in variants:
            for m in re.finditer(r'(?<!\w)' + re.escape(variant) + r'(?!\w)', text):
                labels.append((m.start(), m.end(), key))
    # Keep the longest label when a phrase contains a shorter alias.
    labels.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    nonoverlap = []
    for label in labels:
        if not nonoverlap or label[0] >= nonoverlap[-1][1]:
            nonoverlap.append(label)
    relevant = []
    for i, (_, end, key) in enumerate(nonoverlap):
        if key == field:
            stop = nonoverlap[i + 1][0] if i + 1 < len(nonoverlap) else len(text)
            relevant.append(text[end:stop])
    if relevant:
        return all(has_amount(part, value) for part in relevant)
    return allow_unlabeled and not nonoverlap and has_amount(text, value)


def has_date(text, date):
    date = datetime.strptime(str(date)[:10], '%Y-%m-%d')
    text = normalize(text).replace(',', '')
    variants = [date.strftime('%Y-%m-%d'), f'{date:%B} {date.day} {date.year}',
                f'{date.day} {date:%B} {date.year}',
                f'{date:%b} {date.day} {date.year}', f'{date.day} {date:%b} {date.year}']
    return any(mentions(text, variant) for variant in variants)


def entity_texts(answer, entities):
    """Return text bound to each entity, including row/column Markdown tables.

    entities maps stable keys to visible names and explicitly supported aliases.
    A paragraph with several names is split at their mentions; an entity on
    its own line retains both prefix and suffix facts from that line.
    """
    answer = normalize(answer)
    output = {key: [] for key in entities}
    patterns = {key: re.compile(r'(?<!\w)(?:' + '|'.join(
        re.escape(normalize(s)) for s in sorted(names, key=len, reverse=True)) + r')(?!\w)')
        for key, names in entities.items()}

    def matching_keys(text):
        return [key for key, pattern in patterns.items() if pattern.search(text)]

    lines = answer.splitlines()
    used = set()
    for i in range(len(lines) - 1):
        if '|' not in lines[i] or not re.fullmatch(r'[| :\-]+', lines[i + 1].strip()):
            continue
        headers = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        used.update((i, i + 1))
        for j in range(i + 2, len(lines)):
            if '|' not in lines[j]:
                break
            cells = [c.strip() for c in lines[j].strip().strip('|').split('|')]
            if len(cells) != len(headers):
                break
            used.add(j)
            row_keys = matching_keys(' | '.join(cells))
            if len(row_keys) == 1:
                output[row_keys[0]].append('; '.join(f'{h}: {c}' for h, c in zip(headers, cells)))
            for index, header in enumerate(headers):
                for key in matching_keys(header):
                    output[key].append(f'{cells[0]}: {cells[index]}')

    for i, line in enumerate(lines):
        if i in used:
            continue
        keys = matching_keys(line)
        if len(keys) == 1:
            output[keys[0]].append(line)
        elif len(keys) > 1:
            matches = [(m.start(), m.end(), key) for key, pattern in patterns.items()
                       for m in pattern.finditer(line)]
            matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
            nonoverlap = []
            for match in matches:
                if not nonoverlap or match[0] >= nonoverlap[-1][1]:
                    nonoverlap.append(match)
            for pos, (start, _, key) in enumerate(nonoverlap):
                stop = nonoverlap[pos + 1][0] if pos + 1 < len(nonoverlap) else len(line)
                output[key].append(line[start:stop])
    return {key: '\n'.join(parts) for key, parts in output.items()}
