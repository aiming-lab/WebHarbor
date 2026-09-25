"""Small, deterministic keyword ranking over database-backed content."""
import re


def terms(text):
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return [word[:-3] + 'y' if word.endswith('ies') else
            word[:-1] if word.endswith('s') and not word.endswith('ss') else word
            for word in words]


def ranked(records, query, fields):
    wanted = set(terms(query))
    if not wanted:
        return []
    matches = []
    for record in records:
        tokens = [set(terms(getattr(record, field) or '')) for field in fields]
        if not wanted <= set().union(*tokens):
            continue
        score = sum(len(wanted & group) * weight
                    for group, weight in zip(tokens, (8, 3, 1)))
        if terms(query) == terms(getattr(record, fields[0]) or ''):
            score += 30
        matches.append((score, record))
    # Stable input order breaks ties (updated date, then id at the call site).
    return [record for _, record in sorted(matches, key=lambda pair: -pair[0])]
