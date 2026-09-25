"""Bounded English fact checks; no network calls or prescribed answer format.

Accept sentences, bullets, table-like text and common equivalents. These are
conservative task-specific rules, not a general semantic judge. Regression tests
cover polarity, property binding, units, sibling values and contradictions.
"""
import re


def clean(text):
    return re.sub(r'\s+', ' ', text.casefold().replace('’', "'").replace('–', '-')).strip()


def clauses(text):
    return [s.strip() for s in re.split(r'(?<!\d)[.!?;\n]+|[.!?;\n]+(?!\d)|\bbut\b|\bhowever\b', text.casefold()) if s.strip()]


def positive(text, pattern):
    """An asserted label may not also be explicitly denied anywhere."""
    found = False
    for c in clauses(text):
        for m in re.finditer(pattern, c, re.I):
            before, after = c[max(0, m.start()-55):m.start()], c[m.end():m.end()+65]
            if re.search(r"\b(?:not|never|neither|nor|wrong|incorrect)\b[^,]*$", before):
                return False
            if re.match(r"\s*(?:is|are|was|does|has)?\s*(?:not|n't|incorrect|wrong|false)\b", after):
                return False
            found = True
    return found


def highlights(text):
    return sum(positive(text, p) for p in [
        r'fast downloads and uploads', r'mobile and desktop access', r'file and folder links?'
    ]) >= 2


def recovery(text):
    groups = [r'(?:support|help[ -]?desk|customer service)', r'(?:teammates?|team members?|colleagues?|co-workers?|coworkers?)']
    for group in groups:
        relevant = [c for c in clauses(text) if re.search(group, c)]
        # Bare recipients directly answer "who should you not share with?".
        if not relevant:
            return False
        for c in relevant:
            if re.search(r'\b(?:share|give|send|provide|receive|disclose|reveal)\b', c):
                forbidden = re.search(r"\b(?:not|never|neither|nor|nobody|no one|don't|do not|shouldn't|mustn't|cannot|can't|avoid)\b", c)
                if not forbidden:
                    return False
            if re.search(r'\b(?:safe|allowed|okay|ok) to share', c):
                return False
    return True


def business_winner(text):
    t = clean(text)
    if not positive(text, r'\bbusiness pro\b'):
        return False
    # Reject explicit opposite comparisons, including a named winner followed
    # by the expected plan only as a losing comparison/reference.
    if re.search(r'pro ii\b[^.;\n]{0,35}(?:more|greater|larger|most)\b', t):
        return False
    if re.search(r'business pro\b[^.;\n]{0,20}(?:fewer|less|smaller|loses)\b', t):
        return False
    # Numeric statements are optional, but if provided they must be attached to
    # the correct plan. An unrelated 5 is never evidence for a required count.
    for name, expected in [('business pro', '5'), ('pro ii', '1')]:
        for c in clauses(text):
            for m in re.finditer(r'\b'+name+r"\b(?:\s*[|:=(]|\s+(?:includes?|has|with|offers?|supports?|provides?|users?\s*:))\s*(\d+|one|five)\b", c):
                value={'one':'1','five':'5'}.get(m[1],m[1])
                if value != expected:
                    return False
    # The task asks for the winning plan, not necessarily both numeric counts.
    return True


def old_vendor(text):
    identity_text = re.sub(r"does not have|doesn't have", 'lacks', text, flags=re.I)
    identity_text = re.sub(r"(?:is not|isn't|not) enabled", 'disabled', identity_text, flags=re.I)
    if not positive(identity_text, r'\b(?:old )?vendor ftp\b'):
        return False
    for c in clauses(text):
        if '2fa' in c or 'two-factor' in c or 'two factor' in c:
            if re.search(r'\b(?:enabled|on|active)\b', c) and not re.search(r"\b(?:not|no|without|off|disabled|doesn't|isn't)\b", c):
                return False
    return True


def package_version(text, version):
    if not positive(text, r'\bmega pass chrome(?: browser)?(?: extension)?\b'):
        return False
    versions=[]
    # A version label, adjacent table cell or ordinary "v1.2.3" form is accepted.
    for c in clauses(text):
        versions += re.findall(r'\b(?:version|release|v)(?:\s+(?:is|shown|listed|displayed|number))*\s*[:|=-]?\s*(\d+\.\d+(?:\.\d+)*)', c)
        if 'mega pass chrome' in c and not re.search(r'\b(?:reference|ticket|issue|example)\b',c):
            versions += re.findall(r'(?<![\d.])(\d+\.\d+(?:\.\d+)*)(?![\d.])',c)
    # DOM/table output puts the value on the next line.
    versions += re.findall(r'\bversion(?:\s+(?:is|shown|listed|displayed|number))*\s*[:|=-]?\s*(\d+\.\d+(?:\.\d+)*)',text.casefold())
    return bool(versions) and all(v==version for v in versions) and positive(text,re.escape(version))


def checksum_answer(text, checksum):
    if not positive(text, re.escape(checksum)):
        return False
    values=re.findall(r'\bsha256-[a-z0-9-]+',text.casefold())
    return values and all(v==checksum.casefold() for v in values)


def disconnect(text):
    patterns = [
        r'\b(?:disconnect|isolate|unplug)\s+(?:the |your |any )?(?:affected|infected|compromised)\s+(?:device|computer|machine|system)\b',
        r'\b(?:take|put|bring)\s+(?:the |your )?(?:affected|infected|compromised)\s+(?:device|computer|machine|system)\s+offline\b',
        r'\b(?:affected|infected|compromised)\s+(?:device|computer|machine|system)\s+(?:should |must )?(?:be |is )?(?:disconnected|isolated|taken offline)\b',
    ]
    if not any(positive(text,p) for p in patterns):
        return False
    for c in clauses(text):
        if re.search(r'\b(?:keep|leave)\b.*\b(?:affected|infected|compromised)\b.*\b(?:connected|online)\b',c):
            return False
        if re.search(r'\brestore\b.*\b(?:first|before (?:disconnect|isolat))',c):
            return False
    return True


def ticket_request(text):
    t=clean(text)
    if re.search(r"\b(?:don't|do not|no longer|never)\b.{0,35}\b(?:need|want|help|estimat)\w*",t):
        return False
    return all(re.search(p,t) for p in [r'\bs4\b',r'\b(?:egress|outbound (?:data|traffic)|data transfer)\b',r'\b(?:quarter\w*|three.month)\b',r'\barchives?\b',r'\b(?:estimat\w*|calculat\w*|forecast\w*|budget\w*)\b',r'\b(?:help|guidance|assist\w*|please|could|can|need|how)\b'])
