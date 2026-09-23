"""Bounded English fact checks for AMAZON JOBS verifiers.

Each predicate accepts paraphrase within a fixed envelope and rejects
contradictions. They are deterministic token/regex checks against frozen
ground truth, never open-ended semantic understanding.
"""
import re

from verify_lib import affirms, affirm_number, contains_count, norm


# T4: which team has more open jobs — Devices and Services (71) over Ads (31).
def devices_wins(text):
    """The answer names Devices and Services as the team with more open jobs.

    Rejects answers that crown Amazon Ads instead: a clause is an Ads-wins claim
    when 'amazon ads' precedes the comparative (more/higher/larger/bigger)
    inside that same clause. 'Devices and Services has more: 71 vs 31 for
    Amazon Ads' keeps Ads after the comparative and is accepted.
    """
    if not text or not affirms(text, "devices and services"):
        return False
    low = norm(text)
    comparative = re.compile(r"\b(more|higher|larger|bigger)\b")
    for clause in re.split(r"[.;\n]", low):
        m_ads = re.search(r"amazon ads", clause)
        m_cmp = comparative.search(clause)
        if m_ads and m_cmp and m_ads.start() < m_cmp.start():
            return False
    return True


# T9: design systems experience asked by job 10384384.
def scalable_design_systems(text):
    """The answer reports the scalable design systems experience requirement."""
    if not text:
        return False
    low = norm(text)
    if "design system" not in low:
        return False
    return "scalable" in low or "scale" in low


# T10: which New York UX job mentions a degree, and in which field.
def elevated_mentions_degree(text):
    """The answer names the UX Designer, Elevated Shopping Experience job."""
    if not text:
        return False
    low = norm(text)
    return ("elevated shopping" in low) or ("ux designer, elevated" in low) \
        or ("elevated shopping experience" in low)


def degree_field(text):
    """The answer names design and/or human-computer interaction (HCI)."""
    if not text:
        return False
    low = norm(text)
    hits = 0
    if re.search(r"\bdesign\b", low):
        hits += 1
    if "human-computer interaction" in low or "human computer interaction" in low or re.search(r"\bhci\b", low):
        hits += 1
    return hits >= 1


# T18: what the FAQ answer says to use and filter by.
def uses_this_site(text):
    """The answer says Amazon encourages using this (search) site/website."""
    if not text:
        return False
    low = norm(text)
    return bool(re.search(r"\b(this|the|search) (web ?site|site|website|portal)\b", low)
                or "amazon.jobs" in low or "this site" in low)


def filter_dims(text, minimum=2):
    """At least `minimum` of the four filter dimensions are named."""
    if not text:
        return 0
    low = norm(text)
    hits = 0
    if "location" in low:
        hits += 1
    if "business categor" in low or "business unit" in low or "team" in low:
        hits += 1
    if "job categor" in low or "job category" in low:
        hits += 1
    if "keyword" in low:
        hits += 1
    return hits >= minimum


# T26: which email preferences remain enabled after turning off Job recommendations.
def application_updates_remain(text):
    """Application updates is affirmed as the remaining enabled preference."""
    return affirms(text, "application updates")


def job_recommendations_still_on(text):
    """True when the answer wrongly claims Job recommendations is enabled/on.

    The comparative scan stops at commas: 'Job recommendations emails, the
    remaining enabled preference is Application updates' is NOT a claim that
    Job recommendations is on.
    """
    if not text:
        return False
    low = norm(text)
    return bool(re.search(r"job recommendations?[^,.;\n]{0,70}\b(enabled|turned on|switched on|remains?|still on|is on|stays on)\b", low)
                or re.search(r"\b(enabled|turned on|switched on|still on|is on)\b[^,.;\n]{0,50}job recommendations?", low))


def newsletter_claimed_on(text):
    """True when the answer wrongly claims the Amazon Newsletter is enabled."""
    if not text:
        return False
    low = norm(text)
    return bool(re.search(r"newsletter[^,.;\n]{0,70}\b(enabled|turned on|switched on|remains?|still on|is on|stays on)\b", low)
                or re.search(r"\b(enabled|turned on|switched on|still on|is on)\b[^,.;\n]{0,50}newsletter", low))


# T28: zero alerts remain.
def zero_alerts(text):
    """The answer reports no remaining job alerts (0 / zero / none)."""
    if not text:
        return False
    if affirm_number(text, 0):
        return True
    low = norm(text)
    if re.search(r"\b(zero|none)\b", low):
        return True
    return bool(re.search(r"no (job )?alerts? (remain|left|are|is|were)", low)
                 or re.search(r"(remain|left|are|is|were) no (job )?alerts", low)
                 or re.search(r"no (remaining|remaining) (job )?alerts", low))


# T23: the withdrawn Assessment application's job title.
def au_cx_title(text):
    """The answer names the Senior Product Manager, AU Customer Experience (CX) Improvement role."""
    if not text or "customer experience" not in norm(text):
        return False
    low = norm(text)
    return bool("au customer" in low or "cx improvement" in low or re.search(r"\bau\b", low)
                or "( cx )" in low or re.search(r"\bcx\b", low))


# T17: the team handling AWS global infrastructure.
def ais_team(text):
    """The answer names the AWS Infrastructure Services (AIS) team."""
    if not text or "infrastructure services" not in norm(text):
        return False
    low = norm(text)
    return "aws" in low or re.search(r"\bais\b", low)


# T6: company name shown in the Job ID line of job 10552766.
def adci_company(text):
    """The answer names the ADCI hiring company (ADCI - Karnataka - A66)."""
    if not text:
        return False
    return "adci" in norm(text)


# T21: homepage employee story.
def xiaole_story(text):
    """The answer names Xiaole, her Engineer role, and Beijing."""
    if not text:
        return False
    low = norm(text)
    return ("xiaole" in low and "beijing" in low
            and ("engineer" in low))
