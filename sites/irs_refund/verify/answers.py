"""Task-specific natural-answer checks, without an LLM or output template.

Supported: short answers, named prose, bullets and simple year/stage tables.
This is a bounded parser, not arbitrary linguistic inference: implicit discourse,
sarcasm and double negation are outside its contract. Tests cover both accepted
paraphrases and rejected contradictory/negated assertions.
"""
import re


def norm(text):
    text = str(text or '').casefold().replace('’', "'").replace('–', '-').replace('—', ';')
    for old, new in {"isn't": 'is not', "aren't": 'are not', "doesn't": 'does not',
                     "don't": 'do not', "hasn't": 'has not', "haven't": 'have not',
                     "can't": 'cannot', "won't": 'will not'}.items():
        text = text.replace(old, new)
    return re.sub(r'[ \t]+', ' ', text).strip()


NEG = r'\b(?:not|no|never|neither|without|cannot|wrong|incorrect|ignore|skip)\b'
UNCERTAIN = r'\b(?:maybe|perhaps|unsure|uncertain|guess|cannot tell)\b'


def facts(text, patterns):
    """Return (named value, asserted polarity) for explicit mentions.

    Each mention is scoped to its clause and adjacent value mentions, so e.g.
    "split deposit, not paper check" differs from "not split deposit".
    "not only" is additive, not a denial.
    """
    text = norm(text)
    text = re.sub(r'\bnot only\b', 'also', text)
    pattern = '|'.join(f'(?P<V{i}>{p})' for i, p in enumerate(patterns.values()))
    names = list(patterns)
    text = re.sub(pattern, lambda m: f' VALUE{int(m.lastgroup[1:])} ', text)
    found = []
    for clause in re.split(r'[.!?;\n,]+|\b(?:but|while|whereas|and)\b', text):
        mentions = list(re.finditer(r'VALUE(\d+)', clause))
        for i, m in enumerate(mentions):
            prefix = clause[mentions[i-1].end() if i else 0:m.start()]
            suffix = clause[m.end():mentions[i+1].start() if i+1<len(mentions) else len(clause)]
            negative = bool(re.search(NEG, prefix))
            # A trailing negation before the next value belongs to that value.
            if i+1 == len(mentions):
                negative |= bool(re.search(r'\b(?:is|are|was|were|does|do|has|have|will)\s+(?:\w+\s+){0,2}(?:not|never)\b|\b(?:not needed|not required|incorrect|wrong)\b', suffix))
            found.append((names[int(m[1])], not negative))
    return found


def one_value(text, patterns, wanted):
    fs = facts(text, patterns)
    return (wanted, True) in fs and not any(
        (name == wanted and not positive) or (name != wanted and positive)
        for name, positive in fs
    )


DELIVERY = {
    'split': r'\bsplit[ -]deposit\b|\bsplit\b[^.;\n]{0,70}\b(?:multiple|two|several)\s+(?:bank\s+)?accounts\b',
    'paper': r'\bpaper\s+che(?:ck|que)\b|\bmailed\s+che(?:ck|que)\b',
    'direct': r'\bdirect[ -]deposit\b',
}
STAGES = {'received': r'\breturn received\b|\b(?:return|filing)\b.{0,25}\b(?:was|been|is) received\b',
          'approved': r'\b(?:refund )?approved\b|\bapproval\b',
          'sent': r'\b(?:refund )?sent\b|\bdispatched\b|\bissued\b',
          'processing': r'\bprocessing\b',
          'identity': r'\bidentity[ -]verification\b|\bidentity\s+(?:check|review)\b',
          'offset': r'\boffset\s+review\b',
          'math': r'\bmath\s+(?:error|review)\b'}


def comparison(text):
    t = norm(text)
    t = re.sub(r'\b(?:earlier|older|prior[ -]year|previous[ -]year)\b', '2024', t)
    t = re.sub(r'\b(?:newer|later|current[ -]year)\b', '2025', t)
    if t.strip(' .') == '2024':
        return True
    winner = False
    assignments = {}
    subject = None
    for clause in re.split(r'[.;!\n]+|\b(?:while|whereas|but|and)\b', t):
        years = list(re.finditer(r'\b202[45]\b', clause))
        if years:
            subject = years[0].group()
        if re.search(r'\b(?:further|farther|ahead|more advanced|more progress)\b', clause):
            # The first year is the comparative subject, not an arbitrary token.
            if subject != '2024' or re.search(NEG, clause):
                return False
            winner = True
        if len(years) > 1:
            # Support a plain table/header-free "2024: sent / 2025: approved".
            parts = [(m.group(), clause[m.end():years[j+1].start() if j+1<len(years) else len(clause)]) for j,m in enumerate(years)]
        else:
            parts = [(subject, clause)]
        for year, words in parts:
            if year is None:
                continue
            fs = facts(words, {'sent': STAGES['sent'], 'approved': STAGES['approved']})
            for stage, positive in fs:
                expected = 'sent' if year == '2024' else 'approved'
                if (positive and stage != expected) or (not positive and stage == expected):
                    return False
                if positive:
                    assignments[year] = stage
    return winner or assignments == {'2024': 'sent', '2025': 'approved'}


def amended(text):
    t = norm(text)
    standard = r'(?:standard|ordinary|regular|unamended|non[ -]amended)'
    longer = r'(?:longer|more time|slower)'
    shorter = r'(?:shorter|less time|faster|sooner)'
    # Check both comparative directions; a reversed or denied claim fails.
    if re.search(r'\b(?:not|never)\b[^.;]{0,30}' + longer, t):
        return False
    if re.search(standard + r'[^.;]*' + longer + r'[^.;]*\bamended\b', t):
        return False
    if re.search(r'\bamended\b[^.;]*' + shorter + r'[^.;]*' + standard, t):
        return False
    return bool(re.search(r'\bamended\b[^.;]*' + longer + r'[^.;]*' + standard, t)
                or re.search(standard + r'[^.;]*' + shorter + r'[^.;]*\bamended\b', t))


def guest_history(text):
    t = norm(text)
    if re.fullmatch(r'no[.! ]*', t):
        return True
    if re.search(r'\b(?:no|without|not need(?:ed)?)\b[^.;]{0,25}\b(?:account|sign[ -]?in|log[ -]?in)\b', t):
        return False
    denied = False
    for clause in re.split(r'[.;!\n]+|\bbut\b', t):
        if re.search(r'\b(?:guest|anonymous)\b', clause) and re.search(r'\b(?:sav\w*|retain\w*|stor\w*|keep\w*)\b', clause):
            if not re.search(NEG, clause):
                return False
            denied = True
    return denied or (bool(re.match(r'^no\b', t)) and bool(re.search(r'\b(?:account|sign in|log in|signed in)\b', t)))


def amount(text):
    t = norm(text).replace(',', '')
    t = re.sub(r'\bnine hundred (?:and )?eighty\b', '980', t)
    if re.fullmatch(r'980(?:\.00)?[.! ]*', t):
        return True
    hits = []
    for clause in re.split(r'[;!\n]+|(?<!\d)\.(?!\d)|\bbut\b', t):
        money = list(re.finditer(r'(?:\$|\busd\s*)(\d+(?:\.\d+)?)|\b(\d+(?:\.\d+)?)\s*(?:dollars|usd)\b', clause))
        if not money and re.search(r'\b(?:refund|amount|paper[ -]check)\b', clause) and not re.search(r'\b(?:reference|id|code)\b', clause):
            money = list(re.finditer(r'\b(\d+(?:\.\d+)?)\b', clause))
        for m in money:
            value = float(next(g for g in m.groups() if g is not None))
            positive = not bool(re.search(NEG, clause[:m.start()]))
            if (positive and value != 980) or (not positive and value == 980):
                return False
            if positive:
                hits.append(value)
    return bool(hits)


def answer_ok(task, answer):
    t = norm(answer)
    if not t or re.search(UNCERTAIN, t):
        return False
    if task in {0, 13, 17}:
        return one_value(t, DELIVERY, 'paper' if task == 17 else 'split')
    if task in {1, 6}:
        return one_value(t, STAGES, 'identity')
    if task == 2:
        fs = facts(t, {'approved': STAGES['approved'], 'sent': STAGES['sent']})
        return ('approved', True) in fs and ('approved', False) not in fs and ('sent', True) not in fs
    if task == 3:
        return one_value(t, STAGES, 'received')
    if task == 4:
        return amended(t)
    if task == 5:
        fields = {'checklist': r'\bchecklist\b', 'address': r'\b(?:address|mailing details)\b',
                  'contact': r'\bcontact\s+(?:preference|method)\b'}
        fs = facts(t, fields)
        return all((k, True) in fs for k in fields) and not any(not p for _,p in fs)
    if task == 7:
        return comparison(t)
    if task == 8:
        # The saved DB, not the wording of a self-report, proves this state task.
        return True
    if task == 9:
        return one_value(t, {'00000': r'(?<!\d)00000(?!\d)', 'other': r'(?<!\d)(?!00000)\d{5}(?!\d)'}, '00000')
    if task == 10:
        # "ZIP is incorrect" is a positive mismatch claim, not a denied ZIP.
        zip_wrong = bool(re.search(r'\b(?:zip(?: code)?|postal code)\b[^.;]{0,35}\b(?:incorrect|wrong|does not match|mismatch|invalid)\b', t))
        zip_right = bool(re.search(r'\b(?:zip(?: code)?|postal code)\b[^.;]{0,25}\b(?:is correct|is right|matches|is not incorrect|is not wrong)\b', t))
        other_wrong = bool(re.search(r'\b(?:refund amount|last four(?: digits)?|filing status|tax year)\b[^.;]{0,30}\b(?:incorrect|wrong|mismatch|does not match)\b', t))
        short = bool(re.fullmatch(r'(?:the )?(?:zip(?: code)?|postal code)[.! ]*', t))
        return (zip_wrong or short) and not zip_right and not other_wrong
    if task in {11, 14}:
        wanted = 'id' if task == 11 else 'sp'
        return one_value(t, {'id': r'\bid[ -]?221\b', 'sp': r'\bsp[ -]?177\b',
                             'other': r'\b(?!id[ -]?221\b|sp[ -]?177\b)[a-z]{2}[ -]?\d{3}\b'}, wanted)
    if task == 12:
        fs = facts(t, {'photo': r'\bphoto[ -]?id\s+name\b|\bname\s+on\s+(?:the\s+)?(?:synthetic\s+)?photo[ -]?id\b',
                       'zip': r'\b(?:stored\s+)?mailing\s+(?:zip|postal)(?: code)?\b',
                       'contact': r'\b(?:preferred\s+)?contact\s+(?:method|preference)\b'})
        return any(p for _,p in fs) and not any(not p for _,p in fs)
    if task == 15:
        return guest_history(t)
    if task == 16:
        return amount(t)
    raise ValueError(f'unknown task {task}')
