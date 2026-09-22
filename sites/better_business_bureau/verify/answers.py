"""Bounded English fact checks for BETTER BUSINESS BUREAU verifiers.

Each predicate accepts paraphrase within a fixed envelope and rejects
contradictions. They are deterministic token/regex checks against frozen
ground truth, never open-ended semantic understanding.
"""
import re

from verify_lib import affirms, affirm_number, contains_count, norm


def _clean(text):
    """Casefold and normalize separator/quote variants so predicates are robust."""
    low = norm(text)
    return low.replace("’", "'").replace("&rsquo;", "'")


# T12: payment methods accepted by Xfinity (Comcast): credit card, debit card,
# bank account (or ACH / bank transfer spellings). All three families required.
def payment_methods(text):
    if not text:
        return False
    low = _clean(text)
    has_credit = bool(re.search(r"credit\s*card", low))
    has_debit = bool(re.search(r"debit\s*card", low))
    has_bank = bool(re.search(r"(\bbank\b.{0,12}\b(account|transfer|draft|payment)\b)|\bach\b|\beft\b|electronic\s*funds", low))
    return has_credit and has_debit and has_bank


# T16: dollar amounts lost across the six Rise Up Youth Foundation reports:
# $700, $1,485, $800, $1,000, $1,000 and $2,000. Every value must be affirmed.
def rise_up_amounts(text):
    if not text:
        return False
    return all(affirm_number(text, n) for n in (700, 1485, 800, 1000, 2000))


# T19: at least three distinct scam types among the gift-card keyword results.
# The frozen result set contains Charity, Romance, Tech Support and Utility.
GIFT_CARD_TYPES = ("charity", "romance", "tech support", "utility")


def gift_card_types(text, minimum=3):
    if not text:
        return False
    low = _clean(text)
    return sum(1 for t in GIFT_CARD_TYPES if re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", low)) >= minimum


# T20: the Report a Scam form's main fields. Count how many of the expected
# field families the answer names; at least 6 of 10 must appear.
REPORT_FIELDS = (
    (r"scam\s*type|type\s*of\s*scam", "scam type"),
    (r"what\s*happened|description|details\s*of\s*(the\s*)?(scam|incident)|what\s*occurred", "what happened/description"),
    (r"\bcity\b", "city"),
    (r"\bstate\b", "state"),
    (r"\bzip\b|\bzip\s*code\b|\bpostal\b", "zip"),
    (r"scammer'?s?\s*phone|phone\s*number", "scammer phone"),
    (r"scammer'?s?\s*email|e-?mail", "scammer email"),
    (r"scammer'?s?\s*(web\s*site|url)|web\s*site", "scammer website"),
    (r"business\s*name|name\s*of\s*(the\s*)?business|company\s*name", "business named in the scam"),
    (r"dollar\s*(amount|value)|amount\s*(lost|of\s*money)|how\s*much\s*(money\s*)?(was\s*)?lost", "dollar amount lost"),
)


def report_form_fields(text, minimum=6):
    if not text:
        return False
    low = _clean(text)
    return sum(1 for pattern, _name in REPORT_FIELDS if re.search(pattern, low)) >= minimum


# T22: physically check the gift card before buying it at a store: run a finger
# over the back / check whether a sticker has been applied on top of the
# barcode; the reason ties to scammers' fraudulent barcode stickers diverting
# the payment to their own account.
def gift_card_check(text):
    if not text:
        return False
    low = _clean(text)
    check_ok = (re.search(r"run\s*your\s*finger", low) or
                re.search(r"(feel|run).{0,30}finger.{0,40}(back|barcode|sticker)", low) or
                re.search(r"sticker.{0,40}(on\s*top\s*of|over).{0,20}barcode", low) or
                re.search(r"check.{0,30}(the\s*)?(sticker|barcode)", low))
    why_ok = (re.search(r"scammer", low) and
              (re.search(r"sticker", low) or re.search(r"barcode", low)) and
              (re.search(r"account", low) or re.search(r"drain", low) or
               re.search(r"(adds?|placed?|applied?|tamper)", low) or
               re.search(r"(money|funds|payment|cash)", low)))
    return bool(check_ok and why_ok)


# T24: the International Torch Awards for Ethics. The announcing organization
# is IABBB (International Association of Better Business Bureaus), and the
# awards celebrate/recognize dedication to ethical business practices and
# promoting trust in the marketplace.
def torch_awards(text):
    if not text:
        return False
    low = _clean(text)
    org_ok = bool(re.search(r"\biabbb\b|international\s+association\s+of\s+better\s+business\s+bureau", low))
    celebrates_ok = bool(re.search(r"ethic", low)) and bool(
        re.search(r"\btrust\b|marketplace|integrity|business\s*practices", low))
    return org_ok and celebrates_ok


# T25: the weight loss scam involves AI-generated deepfake videos of
# celebrities (e.g. Oprah) and alleged physicians/doctors endorsing LipoMax
# (the "pink salt trick") on social media; BBB Scam Tracker received over 170
# reports over the course of two months.
def weight_loss_scam(text):
    if not text:
        return False
    low = _clean(text)
    deepfake_ok = bool(re.search(r"deep[- ]?fake", low))
    video_ok = bool(re.search(r"\bvideo", low))
    lipo_ok = bool(re.search(r"lipomax|pink\s*salt", low))
    reports_ok = bool(affirm_number(text, 170))
    return deepfake_ok and video_ok and lipo_ok and reports_ok


# T28: Alice's scam submission is a Phishing report describing a package
# delivery payment text with a tracking link to a fake courier site asking for
# card details.
def alice_scam_description(text):
    if not text or not affirms(text, "phishing"):
        return False
    low = _clean(text)
    has_channel = bool(re.search(r"\btext\b|\btexts\b|\bsms\b|\bmessage", low))
    has_hook = bool(re.search(r"package|delivery|courier", low))
    has_link_or_payment = bool(re.search(r"link|payment|pay|card", low))
    return has_channel and has_hook and has_link_or_payment


# T29: the confirmation shown after submitting the Car Tender quote request.
def quote_confirmation(text):
    if not text:
        return False
    low = _clean(text)
    return bool(re.search(r"quote\s*request\s*has\s*been\s*sent\s*to\s*the\s*business", low) or
                re.search(r"(request|form)\s*.{0,20}(submitted|sent).{0,40}business", low))


# T10: the warn-review star rating is 1 of 5.
def warn_review_rating(text):
    if not text:
        return False
    low = _clean(text)
    return bool(re.search(r"1\s*(of|out\s*of|/)\s*5|one\s*(of|out\s*of)\s*(5|five)|1\s*star|1-star|★|one\s*star", low))


# T1: both Precision Tune locations with their ratings. NR rating spellings.
def precision_tune_ratings(text):
    if not text:
        return False
    low = _clean(text)
    seattle_nr = bool(re.search(r"seattle.{0,80}(nr|not\s*rated)|\b(nr|not\s*rated).{0,80}seattle", low))
    uplace_bminus = bool(re.search(r"university\s*place.{0,80}b-|b-.{0,80}university\s*place", low))
    return seattle_nr and uplace_bminus


# T9: complaint summary numbers, tolerant of comma separators.
def complaint_summary(text):
    if not text:
        return False
    return affirm_number(text, 26666) and affirm_number(text, 8188)


# T23: gym-membership pre-signing tips from the upstream BBB article:
# determine your fitness goals / know your budget (hidden costs, cancellation
# fees) / figure out your priorities (location, hours, equipment, classes) /
# take a tour / read the contract and cancellation policy / consider online
# and app-based access. At least `minimum` distinct tip families required.
GYM_TIP_FAMILIES = (
    (r"fitness\s*goals?|goals?\s*in\s*advance|consult.{0,30}physician", "fitness goals"),
    (r"\bbudget\b|hidden\s*cost|enrollment\s*fees?|cancellation\s*fees?|monthly\s*fee", "budget"),
    (r"priorit|convenient\s*location|extended\s*hours|variety\s*of\s*(equipment|classes)|location\s*and\s*hours", "priorities"),
    (r"take\s*a\s*tour|tour.{0,40}(in\s*person|gym|equipment|cleanliness)|tour\s*the", "take a tour"),
    (r"read.{0,20}contract|contract\s*(carefully|terms)|cancellation\s*policy|terms\s*and\s*conditions|before\s*signing|dotted\s*line", "contract"),
    (r"check\s*bbb\.org|read.{0,30}(customer\s*)?reviews?|how\s*the\s*business(es)?\s*respond", "check BBB.org"),
    (r"online\s*and\s*app[- ]based|app[- ]based\s*access", "online/app access"),
)


def gym_tips(text, minimum=2):
    if not text:
        return False
    low = _clean(text)
    return sum(1 for pattern, _name in GYM_TIP_FAMILIES if re.search(pattern, low)) >= minimum


# T18: dashboard figures — CA leads, median loss $500, 47.6% lost money.
def dashboard_figures(text):
    if not text:
        return False
    low = _clean(text)
    ca_ok = bool(re.search(r"\bca\b|california", low))
    median_ok = affirm_number(text, 500)
    pct_ok = bool(re.search(r"47\.6|47\.60|47\s*percent|47%", low.replace("%", " percent ")))
    return ca_ok and median_ok and pct_ok
