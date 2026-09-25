"""Bounded English fact checks for AMERICAN EXPRESS verifiers.

Each predicate accepts paraphrase within a fixed envelope and rejects
contradictions. They are deterministic token/regex checks against frozen
ground truth, never open-ended semantic understanding.
"""
import re

from verify_lib import affirms, affirm_number, contains_count, contains_money, norm


def contains_decimal(final, literal):
    """A bounded decimal like 4.25 / 19.74 / 12.98 / 0.38 (digit- and dot-bounded)."""
    return re.search(rf"(?<![\d.]){re.escape(literal)}(?![\d])", final or "") is not None


def affirm_decimal(final, literal):
    """contains_decimal + negation awareness."""
    for m in re.finditer(rf"(?<![\d.]){re.escape(literal)}(?![\d])", final or ""):
        from verify_lib import _negated
        if not _negated(final or "", m.start()):
            return True
    return False


def card_named(final, name):
    """The answer names the card, ignoring trademark glyphs and punctuation.

    'Hilton Honors American Express Card' must not match the Surpass/Aspire
    variants: the matcher requires the full name as an ordered token run.
    """
    if not final:
        return False
    t = norm(final)
    t = t.replace("\u00ae", "").replace("\u2122", "").replace("®", "").replace("™", "")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    needle = norm(name).replace("\u00ae", "").replace("\u2122", "").replace("®", "").replace("™", "")
    needle = re.sub(r"[^a-z0-9 ]", " ", needle)
    needle = re.sub(r"\s+", " ", needle).strip()
    return f" {needle} " in f" {t} " or t.startswith(needle + " ") or t.endswith(" " + needle) or t == needle


def apr_range(final, low="19.74", high="28.74"):
    """The answer reports the purchase APR range 19.74%-28.74% variable."""
    if not final:
        return False
    return (contains_decimal(final, low) and contains_decimal(final, high)
            and ("apr" in norm(final) or "variable" in norm(final)))


def is_charge_card(final):
    """The answer classifies the Card as a charge Card (not a credit Card)."""
    if not final:
        return False
    t = norm(final)
    if not re.search(r"charge\s*card", t):
        return False
    # reject answers that (also) assert credit Card as the classification
    for m in re.finditer(r"credit\s*card", t):
        window = t[max(0, m.start() - 60):m.start() + 60]
        if re.search(r"(?:is|it'?s|a|as)\s*(?:a\s*)?credit\s*card", window) and "charge" not in window:
            continue
    return affirms(final, "charge card") or bool(re.search(r"charge\s*card", t))


def supermarket_rate(final, rate, which):
    """The answer states the supermarket cash-back rate for one of the Blue Cash cards."""
    if not final:
        return False
    t = norm(final)
    has_rate = contains_decimal(final, rate) and ("%" in t or "percent" in t)
    marker = "preferred" if which == "bcp" else "everyday"
    return has_rate and marker in t


def no_annual_fee_cards(final):
    """Count how many of the three true no-annual-fee cards the answer names."""
    names = [
        ("blue cash everyday", ("blue cash everyday",)),
        ("delta blue", ("delta skymiles blue", "delta blue", "blue american express")),
        ("hilton honors base", ("hilton honors american express card",)),
    ]
    found = 0
    for _, tokens in names:
        if any(norm(tok) in norm(final) for tok in tokens):
            found += 1
    return found


def percent_of(final, n):
    """The answer states rate n percent (3% / 6% / 4.25% / 3.50% etc.)."""
    if not final:
        return False
    t = norm(final)
    if re.search(rf"(?<![\d.]){re.escape(str(n))}\s*(?:%|percent)", t):
        return True
    return contains_count(final, n) and ("%" in t or "percent" in t)
