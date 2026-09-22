"""Finite, offline answer contracts for this frozen benchmark fixture.

Ground truth stays reviewer-side. Match asserted concepts, not arbitrary token
overlap; a secondary language-model judge never decides primary correctness.
"""
import re
import unicodedata


def norm(text):
    text = unicodedata.normalize('NFKC', text or '').casefold().replace('’', "'")
    return re.sub(r'\s+', ' ', text).strip()


def has(text, pattern):
    return re.search(r'(?<!\w)(?:' + pattern + r')(?!\w)', norm(text)) is not None


def clauses(text):
    # Keep decimal numbers and U.S. intact. Contrast starts a new assertion.
    text = norm(text).replace('u.s.', 'us').replace('u.s', 'us')
    return [c.strip(' ,:-') for c in re.split(r'[;\n!?]|\.(?!\d)|\b(?:but|whereas|while)\b|,\s*(?=not\b)', text) if c.strip()]


def negated(clause):
    return has(clause, r"not|no|never|neither|isn't|aren't|doesn't|don't|cannot|can't|without")


def positive(text, pattern):
    return any(has(c, pattern) and not negated(c) for c in clauses(text))


def denied(text, pattern):
    return any(has(c, pattern) and negated(c) for c in clauses(text))


def identified(text, pattern):
    return positive(text, pattern) and not denied(text, pattern)


def pairing(text, entity, attribute, other_entity):
    """Attribute and entity must be adjacent in the entity/attribute sequence.

    Accept both 'Fort Point: Golden Gate' and 'Golden Gate: Fort Point', and
    coordinated sentences, but not an attribute assigned to the other tour.
    """
    for clause in clauses(text):
        if negated(clause):
            continue
        tokens = [(m.lastgroup, m.start()) for m in re.finditer(
            f'(?P<entity>{entity})|(?P<other>{other_entity})|(?P<attr>{attribute})', clause)]
        for i, (kind, _) in enumerate(tokens):
            if kind != 'attr':
                continue
            # Prefer the preceding subject; support attribute-first list labels.
            subject = tokens[i - 1][0] if i else (tokens[i + 1][0] if len(tokens) > 1 else None)
            if subject == 'entity':
                return True
    return False


def answer_ok(task, answer):
    if not norm(answer):
        return False
    if task == 0:
        return (identified(answer, r'yosemite creek(?: campground)?')
                and not any(has(c, 'yosemite creek') and has(c, r'closed|unavailable') for c in clauses(answer))
                and not any(has(c, 'porcupine flat') and has(c, r'open|available') and not negated(c) for c in clauses(answer))
                and positive(answer, r'camping|waterfalls?|hiking'))
    if task == 1:
        # Scene categories reflect the actual three images, not three objects
        # in the same ocean-view picnic-table photograph.
        scenes = [r'(?:oak|large|shad\w*) tree|oak[- ]shaded|wooded campsite',
                  r'drakes bay|ocean|sea view|coast|picnic table|bear box',
                  r'shrub[- ]lined|brush[- ]lined|bushes|sheltered campsite']
        return sum(positive(answer, scene) for scene in scenes) >= 2
    if task in (2, 10):
        root = 'inyo national forest' if task == 2 else 'voyageurs national park'
        full = root + (' wilderness permits?' if task == 2 else ' tours?')
        # The parent embedded inside a listing name isn't a separate parent
        # answer. Accept a second root mention or a labelled shortened parent.
        short = 'inyo' if task == 2 else 'voyageurs'
        parent = (sum(len(re.findall(root, c)) for c in clauses(answer) if not negated(c)) >= 2
                  or positive(answer, rf'(?:parent(?: area)?|part of|managed by)\s*[:=-]?\s*{short}(?: national (?:forest|park))?'))
        wrong_parent = any(has(c, r'yellowstone|yosemite|sequoia') and has(c, r'parent|part of|is in|belongs') for c in clauses(answer))
        return identified(answer, full) and parent and not wrong_parent
    if task == 3:
        maritime, fort = r'(?:san francisco|sf) maritime(?: historic park tours)?', r'fort point(?: national historic site tours)?'
        ships, gate = 'historic ships', r'golden gate(?: national recreation area)?'
        return (pairing(answer, maritime, ships, fort) and pairing(answer, fort, gate, maritime)
                and not pairing(answer, fort, ships, maritime) and not pairing(answer, maritime, gate, fort))
    if task == 4:
        return identified(answer, 'hemlock cabin')
    if task == 5:
        return (identified(answer, r'permit(?:s)?')
                and positive(answer, r'island camping|kayaking|lakes?')
                and not positive(answer, r'(?:is|a) campground'))
    if task == 6:
        return (identified(answer, r'ticket(?:s|ed)?(?: reservations?| tours?)?|tour reservations?')
                and not positive(answer, r'campground|campsite|cabin|day[- ]use'))
    if task == 7:
        return all(positive(answer, pattern) for pattern in (
            r'inventory type|type of (?:inventory|reservation|booking)|reservation type',
            r'(?:allowed|permitted|travel) dates?(?: window)?|date window|dates? (?:allowed|permitted)',
            r'agency rules|(?:managing (?:agency|authority)|agency)(?:\x27s)? rules|rules (?:of|from|attached to) (?:the )?(?:agency|reservation)',
        ))
    if task == 8:
        places = ['san francisco maritime', 'fort point', 'golden gate', 'yosemite', 'yellowstone', 'denali', 'cumberland island']
        return sum(identified(answer, p) for p in places) >= 3
    if task == 9:
        return (identified(answer, r'yosemite(?: national park)?(?: site pass)?')
                and not any(has(c, r'denali|grand teton') and has(c, r'additional|extra|fee|note') and not negated(c) for c in clauses(answer)))
    if task == 17:
        return (identified(answer, r'georgia|ga') and not positive(answer, r'florida|california|alaska')
                and positive(answer, r'beach camping|wilderness|wildlife viewing'))
    if task == 18:
        both = identified(answer, 'both') or (identified(answer, 'day use permit') and identified(answer, 'overnight permit'))
        return both and not has(answer, r'only (?:a )?(?:day use|overnight)') and positive(answer, r'canyons?|hiking|wildlife viewing')
    return True  # Stateful answer requirements are derived from the DB delta.
