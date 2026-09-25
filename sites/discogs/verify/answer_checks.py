"""Bounded deterministic checks for natural Discogs answers.

These rules recognize common prose, labelled bullets and Markdown tables, not
arbitrary English. They deliberately keep entity scopes and asserted properties
separate; a correct value elsewhere in an answer cannot repair a wrong assertion.
Navigation and frozen-state checks live in verify_lib, independently of these.
"""
import re
import unicodedata


def normal(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"\b([a-z])\.(?=\s+[a-z])", r"\1", text)
    text = re.sub(r"\b(\d+)\s*(?:minutes?|mins?|m)\s*(?:and\s*)?(\d+)\s*(?:seconds?|secs?|s)\b",
                  lambda m: f"{int(m[1])}:{int(m[2]):02}", text)
    text = re.sub(r"\b(seven|six|ten|thirteen|three)\b", lambda m: {
        "seven": "7", "six": "6", "ten": "10", "thirteen": "13", "three": "3"}[m[1]], text)
    return text.replace('"', '').replace('“', '').replace('”', '').replace('**', '')


def tables(text):
    """Retain row/column bindings instead of flattening a table to keywords."""
    lines = text.splitlines(); headers = None; result = []
    for line in lines:
        if '|' not in line:
            headers = None; result.append(line); continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r'[:\- ]+', c or '-') for c in cells):
            continue
        if headers is None:
            headers = cells
            continue
        result.append('; '.join(f'{h}: {v}' for h, v in zip(headers, cells)))
    return '\n'.join(result)


def clauses(text):
    return [s.strip(' -*') for s in re.split(r'(?<!\d)\.(?=\s|$)|(?<=\d)\.(?!\d)|[;\n]+', text) if s.strip()]


def present(text, value):
    return re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text) is not None


def negated(text):
    return bool(re.search(r"\b(?:not|no|never|neither|isn't|isnt|doesn't|doesnt|without|lacks?|absent|blank|unlisted)\b", text))


def scopes(text, names):
    """Group forward-labelled statements under the release/edition they name."""
    pattern = '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    result = {n: [] for n in names}
    current = None
    for clause in clauses(text):
        matches = list(re.finditer(r'(?<!\w)(?:' + pattern + r')(?!\w)', clause))
        if not matches:
            if current: result[current].append(clause)
        elif len({m.group() for m in matches}) == 1:
            current = matches[0].group()
            result[current].append(clause)
        else:
            for i, match in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(clause)
                current = match.group()
                result[current].append(clause[0 if i == 0 else match.start():end])
    return {k: '\n'.join(v) for k, v in result.items()}


def property_matches(text, key, expected, reverse=None):
    """Check every recognized assignment, not just one correct occurrence."""
    values = []
    for clause in clauses(text):
        # Stop at the next independent property in a compound sentence.
        parts = re.split(r',?\s+and\s+(?:the\s+)?(?=(?:final|last|closing|bass|duration|catalog|seller|price)\b)', clause)
        for part in parts:
            pattern = (rf'\b(?:{key})\s*(?:\([^)]*\)\s*)?'
                       rf'(?:[:=-]|(?:is|was|are|by)\b|(?:is\s+)?credited\s+to\b)\s*(.+)')
            m = re.search(pattern, part)
            if m:
                values.append(m[1])
            elif reverse:
                m = re.search(reverse, part)
                if m:
                    values.append(m[1])
    return bool(values) and all(re.search(expected, v) and not negated(v) for v in values)


def asserted_presence(text, noun):
    values = []
    for c in clauses(text):
        if re.search(noun, c) and re.search(r'\b(?:print\w*|list\w*|show\w*|has|have|contains?|includes?|duration|timing|absent|blank|lacks?|yes|no)\b', c):
            values.append(not negated(c))
    return values


def named_pair(text, title, artist):
    t, a = re.escape(title), re.escape(artist)
    prose = bool(re.search(rf'{t}\s*,?\s+(?:by|[-])\s+{a}(?!\w)', text))
    denied = bool(re.search(rf'\b(?:not|isnt|isn\x27t)\s+(?:the\s+)?{t}\b', text))
    labelled = property_matches(text, r'(?:release\s+)?title', rf'^{t}(?:$|[,;])') and property_matches(text, r'artist', rf'^{a}(?:$|[,;])')
    wrong_title = any(not re.search(rf'^{t}(?:$|[,;])', m[1]) for m in re.finditer(r'\btitle\s*(?::|is)\s*([^;\n.]+)', text))
    wrong_artist = any(not re.search(rf'^{a}(?:$|[,;])', m[1]) for m in re.finditer(r'\bartist\s*(?::|is)\s*([^;\n.]+)', text))
    return (prose or labelled) and not denied and not wrong_title and not wrong_artist


def count_assertions(text):
    values = re.findall(r'\b(\d+)[ \t]+(?:numbered[ \t]+)?tracks?\b(?![ \t]+count)', text)
    values += re.findall(r'\b(?:track count|tracks)\s*(?::|is|=)\s*(\d+)\b', text)
    return [int(v) for v in values]


def catalog_assertions(text, expected, prefix='', required=True):
    values = []
    key = prefix + r'cat(?:alog(?:ue)?(?:\s+(?:numbers?|identifiers?))?|\.?\s*nos?)s?'
    for clause in clauses(text):
        m = re.search(rf'\b{key}\s*(?:(?:are|is)\s+|[:=-]\s*)?(.+)', clause)
        if m:
            value = re.split(r',|\band\s+(?:joe|(?:(?:a|the|its)\s+)?(?:displayed\s+)?duration)\b', m[1])[0]
            values.append(value)
    if not values:
        return not required and all(present(text, code) for code in expected)
    for value in values:
        if negated(value) or not all(present(value, code) for code in expected):
            return False
        remainder = value
        for code in sorted(expected, key=len, reverse=True):
            remainder = re.sub(r'(?<!\w)' + re.escape(code) + r'(?!\w)', '', remainder)
        if re.search(r'\d', remainder):  # another assigned catalog number
            return False
    return True


def check_answer(index, answer):
    text = normal(tables(answer)); checks = {}
    def check(name, value): checks[name] = bool(value)
    if index == 0:
        parts = scopes(text, ['1961', '1966'])
        yes = asserted_presence(parts['1966'], r'\b(?:durations?|timings?|track times)\b')
        other = asserted_presence(parts['1961'], r'\b(?:durations?|timings?|track times)\b')
        selected = re.search(r'(?:it is|answer is|edition is|year:)\s*(?:the )?1966', text)
        check('duration_edition', (bool(yes) or selected) and all(yes) and not any(other))
        check('catalogs', catalog_assertions(parts['1966'], ['242', 'rs 9242']))
        duration = re.findall(r'\b\d{1,2}:\d{2}\b', text)
        check('track_duration', bool(duration) and all(d == '11:24' for d in duration))
        check('track_binding', bool(re.search(r"well,? you needn't.{0,65}11:24|11:24.{0,65}well,? you needn't", text, re.S)))
        check('duration_polarity', not any(negated(c) for c in clauses(text) if '11:24' in c))
    elif index == 1:
        parts = scopes(text, ['1986', '1994'])
        yes = asserted_presence(parts['1986'], r'\bbellarosa\b')
        other = asserted_presence(parts['1994'], r'\bbellarosa\b')
        check('bellarosa_edition', bool(yes) and all(yes) and not any(other))
        check('medium_catalog', present(parts['1986'], 'cd') and catalog_assertions(parts['1986'], ['cp32-5244'], required=False))
        durations = re.findall(r'\b\d{1,2}:\d{2}\b', text)
        check('track_duration', bool(durations) and all(d == '4:15' for d in durations))
        check('duration_polarity', not any(negated(c) for c in clauses(text) if '4:15' in c))
    elif index == 2:
        parts = scopes(text, ['1982', '2007'])
        counts = count_assertions(parts['2007'])
        check('track_count', bool(counts) and all(n == 7 for n in counts) and 7 not in count_assertions(parts['1982']))
        check('edition', bool(re.search(r"japan(?:ese|'s)?\s*(?:edition\s*)?2007|2007\s*(?:edition\s*)?japan(?:ese)?", text)))
        check('catalog', catalog_assertions(parts['2007'], ['ucco-9038'], required=False))
        check('remastering', property_matches(text, r'(?:digital\s+)?remaster(?:ed|ing)(?:\s+(?:by|credit))?', r'joe tarantino', r'([a-z ]+)\s+(?:is\s+)?credited for (?:digital )?remastering'))
    elif index == 3:
        parts = scopes(text, ['9732909', '8837214'])
        check('ids', all(present(text, n) for n in parts))
        tax = [c for c in clauses(parts['9732909']) if '6649' in c or 'impuesto' in c]
        check('tax_binding', bool(tax) and any('6649' in c for c in tax) and not any(negated(c) for c in tax))
        wrong = [c for c in clauses(parts['8837214']) if ('impuesto' in c or '6649' in c) and not negated(c)]
        check('no_swapped_tax', not wrong)
        check('legal', present(text, '9417-1978') and 'deposito legal' in text)
    elif index == 4:
        parts = scopes(text, ['live god', 'live from kcrw'])
        for title, bass, song in [('live god', 'colin greenwood', 'as the waters cover the sea'), ('live from kcrw', r'martyn p\.? casey', 'jack the ripper')]:
            part = parts[title]
            check(title + '_bass', property_matches(part, r'bass(?:\s+(?:player|credit))?|bassist', bass, r'([a-z .]+?)\s+(?:is\s+)?(?:credited\s+)?(?:on|plays?)\s+bass'))
            check(title + '_closer', property_matches(part, r'(?:the )?(?:final|last|closing)\s+(?:track(?:\s+(?:on\s+)?side[ -]d)?|side[ -]d\s+track)|side[ -]d\s+(?:closer|closing track|final track|last track)', song, rf'({song})\s+(?:closes|ends)\s+side[ -]d'))
        durations = re.findall(r'\b\d{1,2}:\d{2}\b', parts['live from kcrw'])
        check('closer_duration', bool(durations) and all(d == '6:11' for d in durations))
        check('duration_binding', bool(re.search(r'(?:duration|runs?|lasts?|time).{0,20}6:11|jack the ripper\s*[(,:-]?\s*6:11', parts['live from kcrw']))
              and not any(negated(c) for c in clauses(parts['live from kcrw']) if '6:11' in c))
        check('no_invented_duration', not re.search(r'\b\d{1,2}:\d{2}\b', parts['live god']))
    elif index == 5:
        check('release_artist', named_pair(text, 'kelly blue', 'wynton kelly'))
        check('seller', bool(re.search(r"(?:seller\s*(?::|is)?|sold by)\s+kosmische\b|kosmische's\s+kelly blue", text)) and not re.search(r'(?:seller\s*(?::|is)|sold by)\s+(?!kosmische\b)\w+', text))
        prices = re.findall(r'(?:\busd\b|us\$|\$)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:usd\b|us\$)', text)
        check('usd_price', bool(prices) and all(float(a or b) == 8.27 for a, b in prices))
        check('price_polarity', not re.search(r'\bnot\s+(?:usd\s*|us\$|\$)?8\.27|8\.27\s*(?:usd)?\s*(?:is not|isn\x27t)', text))
        check('label_catalogs', catalog_assertions(text, ['smj-6114', 'srs-6059'], r'label\s+'))
        check('legacy_catalogs', catalog_assertions(text, ['12-298', 'rlp 12-298'], r'(?:legacy|original)\s+(?:us\s+)?')
              and bool(re.search(r'(?<!rlp )(?<!\w)12-298(?!\w)', text)))
        check('catalog_groups', bool(re.search(r'(?:legacy|original)\s+(?:us\s+)?(?:catalog|cat|numbers)', text)))
    elif index == 6:
        parts = scopes(text, ['lonely avenue', 'jeff beck'])
        # The self-titled fourth album repeats its name for the artist: retain
        # the full labelled entry rather than splitting it at the second name.
        third = parts['lonely avenue']
        fourth = parts['jeff beck']
        check('third_identity', named_pair(third, 'lonely avenue', 'the boulevard of broken dreams orchestra'))
        check('fourth_identity', named_pair(fourth, 'jeff beck', 'jeff beck'))
        check('countries_catalogs', present(third, 'netherlands') and catalog_assertions(third, ['30-90342']) and present(fourth, 'italy') and catalog_assertions(fourth, ['igda 1063/64']))
        check('comparison', bool(re.search(r'lonely avenue.{0,85}(?:3\s+(?:more|extra)\s+tracks|more tracks.{0,20}\b3\b)', text, re.S)))
        check('no_reversed_comparison', not re.search(r'\b(?:\d+\s+(?:more|extra)\s+tracks|more tracks)', fourth))
        check('counts_if_given', all(n in (13, 3) for n in count_assertions(third)) and all(n in (10, 3) for n in count_assertions(fourth)))
    return checks
