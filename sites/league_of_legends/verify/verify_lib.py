#!/usr/bin/env python3
"""verify_lib.py — shared deterministic (+ anchored, advisory-only LLM) utilities for
League of Legends task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/merriam_webster/verify/verify_lib.py``, ``sites/chess_com/verify/verify_lib.py``,
``sites/google_shopping/verify/verify_lib.py``, ``sites/imgur/verify/verify_lib.py``,
``sites/instructure/verify/verify_lib.py`` — the direct structural references for this one).

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty final
     answer, every recorded URL on the same loopback origin AND port as ``start_url``,
     every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the on-site
     surfaces the task names (the /champions/ roster with its role / difficulty / sort /
     search query filters, champion detail pages, the /news/ hub with pagination and
     category chips, category listings, the /patch-notes/ index, article pages, the /search
     surface with its q query, /how-to-play/, and the account surfaces: /login, /signup,
     /account, /account/profile). A correct answer with no matching navigation is a
     memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / number matching against frozen ground
     truth that is HARDCODED in each ``verify_N.py`` (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only tasks
     require every table row-identical; stateful tasks require the exact allowed row delta
     and nothing else (a favorite_champions row added or removed for the named benchmark
     user, a bookmark_articles row added, a users profile edit, a new signup user row).
  5. LLM utilities are kept for parity with the other suites. They are anchored on ground
     truth, make one call each, and are NEVER load-bearing: every verdict is decided with
     ``--no_llm True`` and the helpers only add ``[INFO]`` evidence.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-rev-league_of_legends)
  --no_llm True        skip the advisory LLM evidence (verdicts never depend on it)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
# NOTE: no `from __future__ import annotations` here — simpleArgParser reads the dataclass
# field types at runtime and needs real types, not strings.
import atexit
import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

SITE = "league_of_legends"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-rev-league_of_legends")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("abilities", "article_categories", "articles", "bookmark_articles",
          "champions", "favorite_champions", "skins", "users")
SEED_COUNTS = {"abilities": 865, "article_categories": 10, "articles": 424,
               "bookmark_articles": 16, "champions": 173, "favorite_champions": 20,
               "skins": 2118, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/league_of_legends.db.
SCHEMA_SHA256 = "f7dc016587753128f2b80bb4f430ffb75cf3e2b4ef89a8d9dc5babf6389aa681"
# sha256 over every seed row (table-scanonical, ORDER BY all columns). The seed is rebuilt
# deterministically at image-build time (PYTHONHASHSEED-independent per seed_data.py;
# byte-identical double build covered by the site's own pytest).
SEED_ROWS_SHA256 = "78493466d771d2f2bb99a4c158ddf753e59270e541131dd84fd26b4054c981bd"
SEED_USERS = {  # email -> (id, username); identity columns never change
    "alice.j@test.com": (1, "alice_j"),
    "bob.c@test.com": (2, "bob_c"),
    "carol.d@test.com": (3, "carol_d"),
    "david.k@test.com": (4, "david_k"),
}
DEMO_PASSWORD = "TestPass123!"
# champion ids the stateful tasks touch (frozen seed rows)
CHAMPION_IDS = {"milio": 84, "trundle": 140, "aatrox": 1, "naafiri": 88, "zaahen": 166}
# article id of 'League of Legends Patch 26.19 Notes' (frozen seed row)
PATCH_2619_ARTICLE_ID = 133
# per-table delta keys: favorites/bookmarks are unique on (user_id, champion_id/article_id)
PK_COLUMNS = {"favorite_champions": ["user_id", "champion_id"],
              "bookmark_articles": ["user_id", "article_id"]}
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}


# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(traj, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    traj["_run_dir"] = d
    shots_dir = d / "screenshots"
    traj["_shots"] = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))} if shots_dir.is_dir() else {}
    return traj


def trajectory_urls(traj):
    """Every browser URL the recorder wrote: start_url, each step's url (+url_before/url_after), final_url."""
    urls = []
    if traj.get("start_url"):
        urls.append(str(traj["start_url"]))
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url", "url_before", "url_after"):
            if step.get(key):
                urls.append(str(step[key]))
    if traj.get("final_url"):
        urls.append(str(traj["final_url"]))
    return urls


def navigated_to(traj, substr, times=1):
    """At least `times` recorded on-site URLs contain substr."""
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def final_url(traj):
    if traj.get("final_url"):
        return str(traj["final_url"])
    for step in reversed(traj.get("steps") or []):
        if isinstance(step, dict) and step.get("url"):
            return str(step["url"])
    return ""


def normalized_url_path(url):
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def is_site_url(url):
    """HTTP(S) URL on a loopback host (any port: alt-port containers are legitimate)."""
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def site_urls(traj):
    return [u for u in trajectory_urls(traj) if is_site_url(u)]


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def _query_params(url):
    return {k: [unquote(v) for v in vals] for k, vals in
            parse_qs(urlparse(str(url)).query, keep_blank_values=True).items()}


def navigated_to_path_with_params(traj, expected_path, params):
    """Some on-site URL whose path matches AND whose query carries the exact key/value
    pairs (value match is exact after URL-decoding)."""
    expected = normalized_url_path(expected_path)
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        query = _query_params(u)
        if all(str(value) in query.get(key, []) for key, value in params.items()):
            return True
    return False


# ---------------------------------------------------------------- league_of_legends navigation gates
def navigated_champions_listing(traj, params=None):
    """/champions/ visit; when `params` is given the query must carry those exact
    key/value pairs (the exposed role / difficulty / sort / q filter controls)."""
    expected = normalized_url_path("/champions/")
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        if not params:
            return True
        query = _query_params(u)
        if all(str(v) in query.get(k, []) for k, v in params.items()):
            return True
    return False


def navigated_champion(traj, slug):
    """/champions/<slug>/ detail page visit (accepts a list of slugs too)."""
    slugs = slug if isinstance(slug, (list, tuple)) else [slug]
    return any(navigated_to_path(traj, f"/champions/{s}") for s in slugs)


def navigated_article(traj, category, slug):
    return navigated_to_path(traj, f"/news/{category}/{slug}")


def navigated_category(traj, machine_name):
    return navigated_to_path(traj, f"/news/{machine_name}")


def navigated_news_page(traj, page_no):
    """/news/ visit with ?page=<page_no>."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/news":
            continue
        query = _query_params(u)
        if str(page_no) in query.get("page", []):
            return True
    return False


def navigated_patch_notes(traj):
    return navigated_to_path(traj, "/patch-notes")


def navigated_search_with(traj, must_tokens, param="q"):
    """A /search visit whose `param` (q) query contains every `must_tokens` token
    (word-boundary, case-insensitive)."""
    wanted = {normalize_text(t) for t in must_tokens}
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        query = _query_params(u)
        q_values = " ".join(query.get(param, []))
        q_tokens = set(re.findall(r"[a-z0-9]+", normalize_text(q_values)))
        if wanted and wanted.issubset(q_tokens):
            return True
    return False


def search_queries(traj):
    out = []
    for u in site_urls(traj):
        if normalized_url_path(u) == "/search":
            for q in _query_params(u).get("q") or _query_params(u).get("keys") or []:
                out.append(q)
    return out


def input_texts(traj):
    values = []
    for step in traj.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in INPUT_ACTIONS:
            continue
        params = step.get("params")
        if isinstance(params, dict) and params.get("text") is not None:
            values.append(str(params["text"]))
    return values


def entered_identity(traj, *identities):
    wanted = {normalize_text(i) for i in identities}
    return any(normalize_text(v) in wanted for v in input_texts(traj))


# ---------------------------------------------------------------- deterministic answer match
def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace("…", "...")
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text  # suite parity


_NEGATION_WORDS = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt)"


def _match_is_affirmative(text, match):
    # Negation window: a negation word invalidates the match only when it sits within
    # the last three words before it (titles like "No results found" routinely carry
    # 'no' in the same sentence segment).
    before_words = re.split(r"[.!?;:,\n]+|\b(?:but|however|instead)\b", text[: match.start()],
                           flags=re.I)[-1].split()[-3:]
    if any(re.fullmatch(_NEGATION_WORDS, w, re.I) for w in before_words):
        return False
    after = text[match.end():]
    return not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I)


def _affirmative_search(pattern, text, flags=0):
    return any(_match_is_affirmative(text, m) for m in re.finditer(pattern, text, flags))


def answer_equals(final, expected):
    return normalize_text(final) == normalize_text(expected)


def contains_all(text, tokens):
    normalized = normalize_text(text)
    return all(bool(t) and _affirmative_search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", normalized)
               for t in (normalize_text(x) for x in tokens))


def contains_any(text, tokens):
    normalized = normalize_text(text)
    return any(bool(t) and _affirmative_search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", normalized)
               for t in (normalize_text(x) for x in tokens))


def contains_phrase(text, phrase):
    """Whole-word phrase match tolerant of hyphen/space/no-space joins
    ('world ender' == 'world-ender' == 'worldender')."""
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").split()]
    if not words:
        return False
    pattern = r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"
    return _affirmative_search(pattern, normalize_text(text))


def contains_phrase_loose(text, phrase):
    """Like contains_phrase but also tolerant of interleaved punctuation
    ('Subject: Serenity', 'Safeguard / Iron Will', 'Dragon's Rage', 'Ruined King: Gameplay')."""
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").replace(":", " ").split()]
    if not words:
        return False
    pattern = r"(?<!\w)" + r"[\s_\-:,.!?()/|&'\";]*".join(words) + r"(?!\w)"
    return _affirmative_search(pattern, normalize_text(text))


def near_any(text, name, tokens, radius=140):
    """True when every token occurs within +/-radius characters of some
    whole-word occurrence of `name` (entity-scoped deterministic matching)."""
    t = normalize_text(text)
    pat = r"(?<!\w)" + re.escape(normalize_text(name)) + r"(?!\w)"
    wanted = [normalize_text(x) for x in tokens]
    for m in re.finditer(pat, t):
        window = t[max(0, m.start() - radius): m.end() + radius]
        if all(tok and tok in window for tok in wanted):
            return True
    return False


def phrases_in_order(text, phrases):
    """Each phrase present (contains_phrase semantics) AND appearing left-to-right."""
    normalized = normalize_text(text)
    cursor = 0
    for phrase in phrases:
        words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").split()]
        if not words:
            return False
        pattern = r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"
        m = re.search(pattern, normalized[cursor:])
        if not m or not _match_is_affirmative(normalized[cursor:], m):
            return False
        cursor += m.end()
    return True


# ---------------------------------------------------------------- subject-bound matching
# Multi-entity comparison facts (ability names, skin counts, dates, lists, account
# counts, summoner/region values) must stay attached to the subject they belong to.
# A swapped answer — every token present, each bound to the wrong entity — is the
# classic false positive these gates close: an occurrence is MISBOUND when it sits
# nearer a rival subject than its owner, WELL-BOUND when it sits within `radius` of
# its owner and no closer to any rival, and neutral otherwise (summary restatements).
_INF = float("inf")


def _name_spans(text, names):
    """Whole-word occurrence spans of any `names` variant (multi-word, join-
    tolerant: 'Miss Fortune' == 'Miss  Fortune', 'LeeSin' == 'Lee Sin', and
    punctuation-tolerant for titled subjects: 'Ruined King: Gameplay Deep Dive')."""
    if isinstance(names, str):
        names = [names]
    normalized = normalize_text(text)
    spans = []
    for name in names:
        words = [re.escape(w) for w in normalize_text(name).replace("-", " ").replace("_", " ").replace(":", " ").split()]
        if not words:
            continue
        pattern = r"(?<!\w)" + r"[\s_\-:,.!?()/|&'\";]*".join(words) + r"(?!\w)"
        spans.extend(m.span() for m in re.finditer(pattern, normalized))
    return sorted(set(spans))


def _loose_spans(text, phrase):
    """Affirmative occurrence spans of `phrase` (contains_phrase_loose semantics)."""
    normalized = normalize_text(text)
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").replace(":", " ").split()]
    if not words:
        return []
    pattern = r"(?<!\w)" + r"[\s_\-:,.!?()/|&'\";]*".join(words) + r"(?!\w)"
    return [m.span() for m in re.finditer(pattern, normalized)
            if _match_is_affirmative(normalized, m)]


def _count_spans(text, number):
    """Affirmative occurrence spans of an integer (plain, thousands-grouped, or
    English word form)."""
    normalized = normalize_text(text)
    spans = []
    for form in _digit_forms(int(number)):
        pattern = r"(?<![\d.,])" + form + r"(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
        spans.extend(m.span() for m in re.finditer(pattern, normalized)
                     if _match_is_affirmative(normalized, m))
    word = _number_word(int(number))
    if word:
        spans.extend(m.span() for m in re.finditer(rf"\b{word}\b", normalized)
                     if _match_is_affirmative(normalized, m))
    return sorted(set(spans))


def _date_spans(text, iso):
    """Affirmative occurrence spans of a date in any accepted form ('2026-09-22',
    'September 22, 2026', '9/22/2026')."""
    normalized = normalize_text(text)
    y, m, d = str(iso).split("-")
    spans = []
    iso_pattern = rf"(?<![\d-]){re.escape(y)}-{re.escape(m)}-{re.escape(d)}(?![\d-])"
    spans.extend(m.span() for m in re.finditer(iso_pattern, normalized)
                if _match_is_affirmative(normalized, m))
    month_name = next((k for k, v in _MONTHS.items() if v == int(m)), "")
    if month_name:
        month_alts = {"september": "sept?(?:ember)?", "january": "jan(?:uary)?",
                      "april": "apr?(?:il)?", "august": "aug?(?:ust)?"}.get(month_name, month_name)
        name_pattern = rf"\b{month_alts}\.?\s+{int(d)}\s*,?\s+{re.escape(y)}\b"
        spans.extend(m.span() for m in re.finditer(name_pattern, normalized)
                     if _match_is_affirmative(normalized, m))
    numeric = rf"(?<![\d.]){int(m)}/{int(d)}/{re.escape(y)}(?!\.?\d)"
    spans.extend(m.span() for m in re.finditer(numeric, normalized)
                 if _match_is_affirmative(normalized, m))
    return sorted(set(spans))


def _stem_spans(text, stem):
    """Affirmative occurrence spans of a word stem ('delay' -> delay/delays/
    delayed/delaying, but never 'delayed'-unrelated derivations like 'health')."""
    normalized = normalize_text(text)
    pattern = rf"(?<!\w){re.escape(normalize_text(stem))}(?:s|es|ed|d|ing)?(?!\w)"
    return [m.span() for m in re.finditer(pattern, normalized)
            if _match_is_affirmative(normalized, m)]


def _span_gap(fact_span, name_span, mode):
    """Distance between a fact occurrence and a subject occurrence. Overlapping
    (embedded) spans are distance 0. mode='near' is the absolute gap; mode='after'
    only counts subjects that end at or before the fact starts (possessive order:
    'Hwei's W is ...')."""
    fs, fe = fact_span
    ns, ne = name_span
    if ns < fe and fs < ne:
        return 0
    if mode == "after":
        return (fs - ne) if ne <= fs else _INF
    return (ns - fe) if ns >= fe else (fs - ne)


def _fact_binding(text, fact_spans, owner, rivals, radius, mode, allow_misbound,
                  only_if_present, optional_owner):
    """Core subject-binding gate over precomputed fact occurrence spans."""
    owners = _name_spans(text, owner)
    # a fact word embedded in its owner's own name (e.g. 'Primer' inside the
    # Council title) is a mention, not a claim — never counted as an occurrence
    facts = [s for s in fact_spans
             if not any(ns < s[1] and s[0] < ne for ns, ne in owners)]
    if not facts:
        return bool(only_if_present)
    rival_spans = _name_spans(text, rivals)
    well_bound = []
    for span in facts:
        d_own = min((_span_gap(span, o, mode) for o in owners), default=_INF)
        d_riv = min((_span_gap(span, r, mode) for r in rival_spans), default=_INF)
        if d_riv < d_own and d_riv <= radius:
            if not allow_misbound:            # attached to the wrong subject
                return False
        elif d_own <= radius and d_own <= d_riv:
            well_bound.append(span)
    if optional_owner and not owners:       # no label to bind to (e.g. no field label)
        return True
    return bool(well_bound)


def bound_phrase(text, phrase, owner, rivals=(), radius=140, mode="near",
                 allow_misbound=False, only_if_present=False, optional_owner=False):
    """`phrase` must be attached to its `owner` subject (and never nearer to any
    `rivals` subject). mode='after' binds only owners preceding the fact."""
    return _fact_binding(text, _loose_spans(text, phrase), owner, rivals, radius,
                         mode, allow_misbound, only_if_present, optional_owner)


def bound_phrase_any(text, phrases, owner, rivals=(), radius=140, mode="near",
                     allow_misbound=False, only_if_present=False, optional_owner=False):
    """Like bound_phrase over a phrase list: no occurrence may be misbound and at
    least one occurrence must be owner-bound (contains_any + subject binding)."""
    spans = [s for phrase in phrases for s in _loose_spans(text, phrase)]
    return _fact_binding(text, spans, owner, rivals, radius, mode,
                         allow_misbound, only_if_present, optional_owner)


def bound_count(text, number, owner, rivals=(), radius=140, mode="near",
                allow_misbound=False, only_if_present=False, optional_owner=False):
    """`number` must be attached to its `owner` subject (contains_count + binding)."""
    return _fact_binding(text, _count_spans(text, number), owner, rivals, radius,
                         mode, allow_misbound, only_if_present, optional_owner)


def bound_date(text, iso, owner, rivals=(), radius=140, mode="near",
               allow_misbound=False, only_if_present=False, optional_owner=False):
    """A date (any accepted form) must be attached to its `owner` subject."""
    return _fact_binding(text, _date_spans(text, iso), owner, rivals, radius,
                         mode, allow_misbound, only_if_present, optional_owner)


def bound_stem(text, stem, owner, rivals=(), radius=140, mode="near",
               allow_misbound=False, only_if_present=False, optional_owner=False):
    """A word-stem fact ('delay'/'delays'/'delaying') must be attached to `owner`."""
    return _fact_binding(text, _stem_spans(text, stem), owner, rivals, radius,
                         mode, allow_misbound, only_if_present, optional_owner)


def contains_stem(text, stem):
    """Word-stem presence ('persist' matches persisted/persists/persisting)."""
    return bool(_stem_spans(text, stem))


def phrase_excluded_from(text, phrase, owner, rivals=(), radius=140, mode="near"):
    """No affirmative occurrence of `phrase` may be attached to `owner` (nearer to
    it than to any rival, within radius) — the negative half of subject binding:
    a fact owned by rivals must never be attributed to `owner`."""
    owners = _name_spans(text, owner)
    facts = [s for s in _loose_spans(text, phrase)
             if not any(ns < s[1] and s[0] < ne for ns, ne in owners)]
    rival_spans = _name_spans(text, rivals)
    for span in facts:
        d_own = min((_span_gap(span, o, mode) for o in owners), default=_INF)
        d_riv = min((_span_gap(span, r, mode) for r in rival_spans), default=_INF)
        if d_own < d_riv and d_own <= radius:
            return False
    return True


def _segment_bounds(normalized, pos):
    """Sentence segment [start, end) around pos (split on . ! ? and newlines)."""
    boundaries = [m.end() for m in re.finditer(r"[.!?\n]+", normalized)]
    start = max((b for b in boundaries if b <= pos), default=0)
    end = next((b for b in boundaries if b > pos), len(normalized))
    return start, end


def state_count_segment(text, number, owner, rivals=(), must_contain=(),
                        forbid_after=(), radius=140, mode="near"):
    """State-count check with list consistency: `number` must be bound to its
    `owner` (as in bound_count), and the sentence segment of an owner-bound count
    must contain every `must_contain` phrase (the state's membership list) while
    none of the `forbid_after` phrases may appear after the count inside that
    segment (an entity removed from the state must not reappear in its list)."""
    normalized = normalize_text(text)
    owners = _name_spans(text, owner)
    rival_spans = _name_spans(text, rivals)
    for span in _count_spans(text, number):
        d_own = min((_span_gap(span, o, mode) for o in owners), default=_INF)
        d_riv = min((_span_gap(span, r, mode) for r in rival_spans), default=_INF)
        if not (d_own <= radius and d_own <= d_riv):
            continue
        seg_start, seg_end = _segment_bounds(normalized, span[0])
        segment = normalized[seg_start:seg_end]
        if all(_loose_spans(segment, phrase) for phrase in must_contain) and \
                not any(seg_start + s[0] >= span[1] for phrase in forbid_after
                        for s in _loose_spans(segment, phrase)):
            return True
    return False


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
    9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty",
    40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety",
}


def _number_word(n):
    if n in _NUMBER_WORDS:
        return _NUMBER_WORDS[n]
    if 21 <= n <= 99:
        tens, ones = divmod(n, 10)
        return f"{_NUMBER_WORDS[tens * 10]}-{_NUMBER_WORDS[ones]}"
    return None


def _digit_forms(number):
    """'2118' == '2,118' == '2 118' (thousands-group tolerant)."""
    s = str(int(number))
    grouped = ""
    tail = s
    while len(tail) > 3:
        grouped = "," + tail[-3:] + grouped
        tail = tail[:-3]
    grouped = tail + grouped
    return [re.escape(s), re.escape(grouped), re.escape(grouped).replace(r"\,", r"\s?")]


def contains_count(text, number):
    """`number` as a standalone integer (not inside a longer digit run, a decimal, a
    thousands group or an ordinal), tolerant of thousands separators ('2,118' style),
    or as its English word form."""
    normalized = normalize_text(text)
    n = int(number)
    for form in _digit_forms(n):
        pattern = r"(?<![\d.,])" + form + r"(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
        if _affirmative_search(pattern, normalized):
            return True
    word = _number_word(n)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_decimal(text, value):
    """'16.5' as a standalone decimal (patch-note cooldown values)."""
    normalized = normalize_text(text)
    s = str(value)
    pattern = r"(?<![\d.])" + re.escape(s) + r"(?![\d.])"
    return _affirmative_search(pattern, normalized)


def contains_decimal_sequence(text, values):
    """A cooldown ladder like 18 / 16.5 / 15 / 13.5 / 12: every value present AND in the
    given order (slash, comma, or dash separated)."""
    return all(contains_decimal(text, v) for v in values) and phrases_in_order(
        text, [str(v) for v in values])


def contains_date_phrase(text, phrase):
    """'September 22, 2026' == 'September 22 2026' == 'Sept. 22, 2026' == '9/22/2026'
    (month-name and numeric forms)."""
    normalized = normalize_text(text)
    words = normalize_text(phrase).split()
    if len(words) != 3:
        return contains_phrase(text, phrase)
    month, day, year = words
    month_alts = {"september": "sept?(?:ember)?", "january": "jan(?:uary)?",
                  "april": "apr?(?:il)?", "august": "aug?(?:ust)?"}.get(month, month)
    pattern = rf"\b{month_alts}\.?\s+{re.escape(day.rstrip(','))}\s*,?\s+{re.escape(year)}\b"
    if _affirmative_search(pattern, normalized):
        return True
    # numeric m/d/yyyy form (day without leading zero tolerant)
    d = day.lstrip("0")
    numeric = rf"(?<![\d.]){int(month_number(month))}/{int(d)}/{re.escape(year)}(?!=?\.?\d)(?!\.?\d)"
    return _affirmative_search(numeric, normalized)


_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
           "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}


def month_number(month):
    return _MONTHS.get(normalize_text(month), 0)


def contains_iso_date(text, iso):
    """'2026-09-22' == 'September 22, 2026' == '9/22/2026' (ISO, month-name, or numeric)."""
    normalized = normalize_text(text)
    y, m, d = str(iso).split("-")
    if _affirmative_search(rf"(?<![\d-]){re.escape(y)}-{re.escape(m)}-{re.escape(d)}(?![\d-])", normalized):
        return True
    month_name = next((k for k, v in _MONTHS.items() if v == int(m)), "")
    if month_name:
        if contains_date_phrase(text, f"{month_name} {int(d)} {y}"):
            return True
    return _affirmative_search(rf"(?<![\d.]){int(m)}/{int(d)}/{re.escape(y)}(?!\.?\d)", normalized)


def champion_named(text, name):
    """A champion name as a whole word, tolerant of apostrophes, dots, joins, hyphens,
    and possessives ('Vel'Koz'/'Velkoz', 'Dr. Mundo', 'LeeSin', "Sona's")."""
    t = normalize_text(text)
    t = re.sub(r"'s\b", "", t)        # possessives: "Sona's" -> "Sona"
    t = t.replace("'", "")            # "Vel'Koz" -> "VelKoz"
    t = t.replace(".", "")            # "Dr. Mundo" -> "Dr Mundo"
    n = normalize_text(name).replace("'", "").replace(".", "")
    words = [re.escape(w) for w in n.split()]
    if not words:
        return False
    return _affirmative_search(r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)", t)


def champion_count_named(text, names):
    return sum(1 for n in names if champion_named(text, n))


# ---------------------------------------------------------------- DB state
def db_query(db_path, sql, params=()):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state). docker cp -> temp file."""
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    fd, path = tempfile.mkstemp(prefix=f"{SITE}_{kind}_", suffix=".db")
    os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip() or r.stdout.strip()}")
    atexit.register(Path(path).unlink, missing_ok=True)
    return path


def resolve_db(arg, container, kind):
    if arg:
        return str(arg) if Path(arg).is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None  # caller treats None as "unavailable" and fails closed


def table_columns(db_path, table):
    return [row["name"] for row in db_query(db_path, f"PRAGMA table_info({table})")]


def _order_clause(db_path, table):
    cols = table_columns(db_path, table)
    return ",".join(f"[{c}]" for c in cols)


def table_rows(db_path, table):
    """Environment-independent full-table scan (ORDER BY all columns)."""
    order = _order_clause(db_path, table)
    return [tuple(row) for row in db_query(db_path, f"SELECT {order} FROM [{table}] ORDER BY {order}")]


def pk_of(db_path, table):
    cols = PK_COLUMNS.get(table, ["id"])
    present = table_columns(db_path, table)
    return [c for c in cols if c in present] or present[:1]


def rows_by_pk(db_path, table):
    keys = pk_of(db_path, table)
    out = {}
    for row in table_rows(db_path, table):
        cols = table_columns(db_path, table)
        d = dict(zip(cols, row))
        out[tuple(d[k] for k in keys)] = row
    return out


def table_delta(initial_db, after_db, table):
    before, after = rows_by_pk(initial_db, table), rows_by_pk(after_db, table)
    return {
        "added": [after[k] for k in sorted(set(after) - set(before), key=repr)],
        "removed": [before[k] for k in sorted(set(before) - set(after), key=repr)],
        "changed": [(before[k], after[k]) for k in sorted(set(before) & set(after), key=repr)
                    if before[k] != after[k]],
    }


def changed_tables(initial_db, after_db, tables=TABLES):
    return [t for t in tables if table_rows(initial_db, t) != table_rows(after_db, t)]


def row_dict(db_path, table, row):
    return dict(zip(table_columns(db_path, table), row))


def _schema_objects(db_path):
    return [tuple(r) for r in db_query(
        db_path,
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]


def schema_sha256(db_path):
    return hashlib.sha256(json.dumps(_schema_objects(db_path), separators=(",", ":")).encode()).hexdigest()


def rows_digest(db_path, tables=TABLES):
    """Table-scanonical digest over every row (ORDER BY all columns) — environment-independent."""
    h = hashlib.sha256()
    for table in tables:
        for row in table_rows(db_path, table):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def validate_snapshot_contract(initial_db, after_db):
    """Raise ValueError unless both snapshots are genuine league_of_legends databases derived
    from the frozen seed."""
    for db_path in (initial_db, after_db):
        tables = {r["name"] for r in db_query(
            db_path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(TABLES):
            raise ValueError(f"unexpected tables in {db_path}: {sorted(tables)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    observed_hash = schema_sha256(initial_db)
    if observed_hash != SCHEMA_SHA256:
        raise ValueError(f"unsupported league_of_legends schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["username"])
             for r in db_query(initial_db, "SELECT id, username, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen league_of_legends seed: rows digest {digest}")
    # benchmark users keep their identity columns in the after snapshot
    after_users = {r["email"]: (int(r["id"]), r["username"])
                   for r in db_query(after_db, "SELECT id, username, email FROM users")}
    if any(after_users.get(email) and after_users[email] != ident
           for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) league_of_legends database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- league_of_legends-specific state helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def favorites_of(db_path, user_id):
    """[(champion_id, added_date, id)] favorite_champions rows of one user, ordered."""
    return sorted((r["champion_id"], r["added_date"], r["id"]) for r in db_query(
        db_path, "SELECT champion_id, added_date, id FROM favorite_champions WHERE user_id = ?",
        (user_id,)))


def bookmarks_of(db_path, user_id):
    """[(article_id, added_date, id)] bookmark_articles rows of one user, ordered."""
    return sorted((r["article_id"], r["added_date"], r["id"]) for r in db_query(
        db_path, "SELECT article_id, added_date, id FROM bookmark_articles WHERE user_id = ?",
        (user_id,)))


def user_row(db_path, user_id):
    rows = db_query(db_path, "SELECT * FROM users WHERE id = ?", (user_id,))
    return dict(rows[0]) if rows else None


def fav_triples(db_path, user_id=None):
    """Sorted identity rows (user_id, champion_id, added_date) of favorite_champions."""
    if user_id is None:
        return sorted(tuple(r) for r in db_query(
            db_path, "SELECT user_id, champion_id, added_date FROM favorite_champions"))
    return sorted(tuple(r) for r in db_query(
        db_path, "SELECT user_id, champion_id, added_date FROM favorite_champions WHERE user_id = ?",
        (user_id,)))


def bm_triples(db_path, user_id=None):
    """Sorted identity rows (user_id, article_id, added_date) of bookmark_articles."""
    if user_id is None:
        return sorted(tuple(r) for r in db_query(
            db_path, "SELECT user_id, article_id, added_date FROM bookmark_articles"))
    return sorted(tuple(r) for r in db_query(
        db_path, "SELECT user_id, article_id, added_date FROM bookmark_articles WHERE user_id = ?",
        (user_id,)))


def user_triples(db_path):
    """Sorted identity rows (id, username, email) of users."""
    return sorted(tuple(r) for r in db_query(
        db_path, "SELECT id, username, email FROM users"))


def check_set_delta(judge, before, after, expected_added, expected_removed, label, detail=""):
    """Exact-set delta check: added/removed sets must equal the expectation exactly."""
    got_added = [t for t in after if t not in before]
    got_removed = [t for t in before if t not in after]
    ok = sorted(got_added) == sorted(expected_added) and sorted(got_removed) == sorted(expected_removed)
    return judge.check(label, ok,
                       f"expected added={sorted(expected_added)} removed={sorted(expected_removed)}; "
                       f"observed added={got_added} removed={got_removed}{(' ' + detail) if detail else ''}")


def check_favorites_delta(judge, initial_db, after_db, added=(), removed=(), label="favorites_delta_exact"):
    return check_set_delta(judge, fav_triples(initial_db), fav_triples(after_db),
                           added, removed, label)


def check_bookmarks_delta(judge, initial_db, after_db, added=(), removed=(), label="bookmarks_delta_exact"):
    return check_set_delta(judge, bm_triples(initial_db), bm_triples(after_db),
                           added, removed, label)


def check_user_profile_delta(judge, initial_db, after_db, user_id, expected_changes,
                              label="profile_delta_exact"):
    """Exactly `expected_changes` {column: (before, after)} on one user row and no other edits."""
    before, after = user_row(initial_db, user_id), user_row(after_db, user_id)
    diffs = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    return judge.check(label, diffs == expected_changes,
                       f"expected={expected_changes}, observed={diffs}")


# ---------------------------------------------------------------- judge harness
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = bool(no_llm)
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no_llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name  # record the FIRST failing check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def note(self, name, text):
        """Advisory evidence that never affects the verdict (used for the anchored LLM helpers)."""
        self.evidence.append(f"[INFO] {name}: {text}")

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason or "all checks passed",
                          "evidence": self.evidence}, ensure_ascii=False, indent=2))
        sys.exit(0 if self.ok else 1)


def fail_closed(task_id, reason, detail):
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    sys.exit(1)


# ---------------------------------------------------------------- shared checks
def _same_local_origin(url, start_url):
    try:
        observed, start = urlparse(str(url or "")), urlparse(str(start_url or ""))
        return (observed.scheme == start.scheme == "http"
                and observed.hostname is not None and start.hostname is not None
                and not observed.username and not observed.password
                and observed.port == start.port
                and observed.hostname.casefold() == start.hostname.casefold()
                and is_site_url(url))
    except ValueError:
        return False


def _png_decodes(path):
    try:
        from PIL import Image  # available in the agent_demo env (browser-use dependency)
    except ImportError:  # pragma: no cover - fallback when Pillow is absent
        data = Path(path).read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 33 or data[12:16] != b"IHDR":
            return False
        return int.from_bytes(data[16:20], "big") > 0 and int.from_bytes(data[20:24], "big") > 0
    try:
        with Image.open(path) as image:
            image.load()
            return image.format == "PNG" and image.width >= 1 and image.height >= 1
    except Exception:  # noqa: BLE001
        return False


def screenshots_decode(traj):
    root = Path(traj.get("_run_dir") or "")
    steps = traj.get("steps")
    if not root.is_dir() or not isinstance(steps, list) or not steps:
        return False, "run directory or steps are missing"
    checked = 0
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step {index} is not an object"
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            rel = Path(str(name or ""))
            if not name or rel.is_absolute() or ".." in rel.parts:
                return False, f"step {index} has unsafe {key}"
            path = next((p for p in (root / "screenshots" / rel, root / rel) if p.is_file()), None)
            if path is None:
                return False, f"step {index} is missing {key}={name!r}"
            if not _png_decodes(path):
                return False, f"step {index} {key} is not a decodable non-empty PNG"
        checked += 1
    return True, f"decoded {checked} PNG screenshots"


def check_trajectory_identity(judge, traj, task_id, require_answer=True):
    answer = final_answer(traj)
    task_file = Path(__file__).resolve().parents[1] / "tasks.jsonl"
    expected = next(row["ques"] for row in map(json.loads, task_file.read_text().splitlines()) if row["id"] == task_id)
    if traj.get("task_id") == task_id:
        judge.check("trajectory_prompt_matches", traj.get("task") == expected,
                    "trajectory must carry the current task wording")
    if require_answer:
        judge.check("final_answer_nonempty", bool(answer), f"final_answer={answer!r}")
    judge.check("trajectory_task_matches", str(traj.get("task_id") or "").strip() == task_id,
                f"expected_task_id={task_id!r}, observed_task_id={traj.get('task_id')!r}")
    judge.check("trajectory_completed",
                traj.get("terminated") is True and traj.get("termination_reason") == "agent_done",
                f"terminated={traj.get('terminated')!r}, reason={traj.get('termination_reason')!r}")
    steps = traj.get("steps")
    judge.check("trajectory_has_steps", isinstance(steps, list) and bool(steps),
                f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    recorded = trajectory_urls(traj)
    judge.check("all_urls_match_local_origin",
                bool(recorded) and all(_same_local_origin(u, traj.get("start_url", "")) for u in recorded),
                f"start_url={traj.get('start_url')!r}, recorded_urls={recorded!r}")
    ok, evidence = screenshots_decode(traj)
    judge.check("screenshots_decode", ok, evidence)


def check_signed_in_as(judge, traj, email):
    """The named demo account must have been entered on the sign-in page (the mirror
    authenticates by email; the password never needs to appear in the trajectory)."""
    judge.check("visited_signin_page", navigated_to_path(traj, "/login"),
                "required_path=/login")
    judge.check("entered_expected_account_identity",
                entered_identity(traj, email),
                f"expected {email!r} in an input step; "
                f"observed_inputs={input_texts(traj)!r}")


def check_visited_path(judge, traj, name, path):
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_read_only(judge, initial_db, after_db):
    changed = changed_tables(initial_db, after_db)
    return judge.check("read_only_db_unchanged", not changed, f"changed_tables={changed!r}")


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    """Every table outside `allowed` is row-identical before/after."""
    others = tuple(t for t in TABLES if t not in set(allowed))
    changed = changed_tables(initial_db, after_db, others)
    return judge.check("no_collateral_writes", not changed,
                       f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


# ---------------------------------------------------------------- anchored LLM utilities (advisory only)
_NO_LLM = False


def _llm_config():
    return (os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_BASE_URL", ""),
            os.environ.get("JUDGE_MODEL", ""))


def _chat(messages, max_tokens=1024):
    """One LLM call against the configured OpenAI-compatible endpoint. Returns text or None; never raises."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    url = base.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        return None


def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s


def llm_text_match(agent_answer, ground_truth, question):
    """One LLM call anchored on the frozen ground truth (never on model knowledge)."""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    return _verdict(_chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}]))


def advisory_llm_answer(judge, answer, ground_truth, question):
    """Record an [INFO] line from the anchored LLM helper when one is configured. Never load-bearing."""
    if judge.no_llm or not all(_llm_config()):
        return
    ok, why = llm_text_match(answer, ground_truth, question)
    judge.note("llm_answer_consistency_advisory", f"{'PASS' if ok else 'FAIL'}: {why[:200]}")


# ---------------------------------------------------------------- CLI
@dataclass
class VerifyArgs:
    run_dir: str = ""
    initial_db: str = ""
    after_db: str = ""
    container: str = DEFAULT_CONTAINER
    no_llm: bool = False

    def post_process(self):
        if not self.run_dir:
            raise SystemExit("--run_dir is required")
        run = Path(self.run_dir)
        if not self.initial_db and (run / "initial.db").is_file():
            self.initial_db = str(run / "initial.db")
        if not self.after_db and (run / "after.db").is_file():
            self.after_db = str(run / "after.db")


def parse_args():
    try:
        import simpleArgParser as sap  # the agent_demo env; boolean flags take a value: --no_llm True
    except ImportError:  # plain python3 fallback with the same flags
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--run_dir", required=True)
        parser.add_argument("--initial_db", default="")
        parser.add_argument("--after_db", default="")
        parser.add_argument("--container", default=DEFAULT_CONTAINER)
        parser.add_argument("--no_llm", nargs="?", const="True", default="False")
        ns = parser.parse_args()
        args = VerifyArgs(ns.run_dir, ns.initial_db, ns.after_db, ns.container,
                          str(ns.no_llm).strip().lower() in {"1", "true", "yes"})
        args.post_process()
        return args
    return sap.parse_args(VerifyArgs)


def run_verifier(task_id, run_checks):
    """Standard main(): load the run, resolve + validate snapshots, run the task checks, fail closed on error."""
    args = parse_args()
    try:
        traj = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(task_id, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, task_id)
    judge = Judge(task_id, no_llm=args.no_llm)
    try:
        run_checks(judge, traj, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()
