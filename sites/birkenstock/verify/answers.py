"""Bounded English fact checks for BIRKENSTOCK verifiers.

Each predicate accepts paraphrase within a fixed envelope and rejects
contradictions. They are deterministic token/regex checks against frozen
ground truth, never open-ended semantic understanding.
"""
import re

from verify_lib import affirms, affirm_number, contains_count, contains_money, norm


def percent_value(text, n):
    """The answer states the max discount as `n` percent (35 / 35% / -35%)."""
    if not text:
        return False
    t = norm(text)
    if re.search(rf"(?<!\d)[{n}%\-% ]*{n}\s*(?:%|percent)", t):
        return True
    return contains_count(text, n) and ("%" in t or "percent" in t or "off" in t)


def classic_benefits(text):
    """Count distinct CLASSIC-tier benefits named in the answer (>=2 required)."""
    if not text:
        return 0
    t = norm(text)
    found = 0
    if re.search(r"free ground shipping", t) and affirms(text, "free ground shipping"):
        found += 1
    if re.search(r"15% off last chance", t) and affirms(text, "15% off last chance"):
        found += 1
    if re.search(r"(exclusive )?gifts? with purchase", t) and affirms(text, "gifts with purchase"):
        found += 1
    if re.search(r"birthday reward", t) and affirms(text, "birthday reward"):
        found += 1
    if re.search(r"anniversary reward", t) and affirms(text, "anniversary reward"):
        found += 1
    if re.search(r"vip bundles", t) and affirms(text, "vip bundles"):
        found += 1
    return found


def review_points_25(text):
    """25 points for leaving a review."""
    if not text:
        return False
    return contains_count(text, 25) and bool(re.search(r"review", norm(text)))


def sale_items_final(text):
    """Sale items discounted 40% or more are final sale / cannot be returned."""
    if not text:
        return False
    t = norm(text)
    has_40 = bool(re.search(r"(?<!\d)40(?!\d)", text.replace(",", "")))
    final_sale = affirms(text, "final sale") or bool(
        re.search(r"(?:cannot|can't|may not|not able)\s+be\s+returned", t))
    return has_40 and final_sale


def ground_days_2_to_5(text):
    """Ground shipping takes between 2 and 5 business days."""
    if not text:
        return False
    t = norm(text)
    return bool(re.search(r"(?<!\d)2\s*(?:and|to|-|–)\s*5(?!\d)", t)) and "business day" in t


def two_day_cutoff(text):
    """2-day orders must be placed Monday-Friday by 12pm/noon EST to ship same day."""
    if not text:
        return False
    t = norm(text)
    noon = bool(re.search(r"(?:12\s*(?:pm|p\.m\.)|noon)", t))
    est = "est" in t or "eastern" in t
    weekday = ("monday" in t and "friday" in t) or "weekday" in t
    return noon and est and weekday


def toll_free_phone(text):
    """(844) 505-4055 in any common formatting."""
    if not text:
        return False
    digits = re.sub(r"\D", "", text)
    return "8445054055" in digits


def support_hours(text):
    """Phone support Monday-Friday 9am to 9pm EST."""
    if not text:
        return False
    t = norm(text)
    hours = bool(re.search(r"9\s*(?:am|a\.m\.)\s*(?:to|-|–)\s*9\s*(?:pm|p\.m\.)", t))
    weekday = ("monday" in t and "friday" in t) or "weekday" in t
    return hours and weekday


def _binding(text, us, eu):
    """US size range and EU size are associated (either order, close together)."""
    t = norm(text)
    us_forms = {us, us.replace("-", " to "), us.replace("-", "–")}
    eu_v = str(eu)
    for uf in us_forms:
        for m in re.finditer(re.escape(uf), t):
            window = t[max(0, m.start() - 60):m.end() + 60]
            if re.search(rf"(?<!\d){eu_v}(?!\d)", window):
                return True
    return False


def men_size_binding(text, us, eu):
    return _binding(text, us, eu) and ("men" in norm(text))


def women_size_binding(text, us, eu):
    return _binding(text, us, eu) and ("women" in norm(text))
