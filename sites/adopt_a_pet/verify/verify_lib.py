#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + (parity-only) LLM utilities for Adopt-a-Pet task verification.

Philosophy: DETERMINISTIC FIRST, fail closed.
  1. Package validation: task id, non-empty final answer, agent_done termination, at least
     one step, every recorded URL on the same loopback origin (host + port) as start_url,
     every referenced screenshot present and decodable as a PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the pages a
     human needs to read the hidden facts (results pages with the task's filters, every
     detail page whose hidden value a comparison depends on, the shelter page, ...).
     Stateful tasks additionally enforce page ORDER (login -> action page -> account).
  3. Answer checks: affirmative token / money / month / phone / e-mail / yes-no matchers
     against frozen ground truth (``ground_truth.py``).
  4. SQLite snapshot contract: initial and after snapshots must both be supplied (explicit
     flags, ``<run_dir>/initial.db`` + ``<run_dir>/after.db``, or ``docker cp`` from
     ``$WH_CONTAINER``). Schema + immutable catalog must be identical and must match the
     frozen catalog; read-only tasks require the mutable tables to be row-identical;
     stateful tasks require EXACT row deltas (no collateral writes, no duplicates).
  5. LLM utilities are kept for API parity with sites/merriam_webster/verify only. No
     verdict depends on them; with ``--no_llm True`` they short-circuit.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: <run_dir>/initial.db, else docker cp instance_seed)
  --after_db PATH    after-state  SQLite DB (default: <run_dir>/after.db,   else docker cp instance)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm True      skip LLM-based checks (deterministic-only; the default verdict path)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.

NOTE: no ``from __future__ import annotations`` here — simpleArgParser reads the
VerifyArgs dataclass annotations at runtime and needs real types, not strings.
"""
import atexit
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_truth as GT  # noqa: E402

SITE = "adopt_a_pet"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

MUTABLE_TABLES = ("user", "favorite", "application", "pet_alert")
IMMUTABLE_TABLES = ("pet", "shelter")
EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "user": ("id", "email", "name", "password_hash"),
    "shelter": ("id", "name", "city", "state", "phone", "email"),
    "pet": ("id", "slug", "name", "species", "breed", "secondary_breed", "sex", "age_group",
            "age_months", "size", "color", "city", "state", "postal", "fee", "image",
            "description", "house_trained", "good_dogs", "good_cats", "good_children", "shelter_id"),
    "favorite": ("id", "user_id", "pet_id"),
    "application": ("id", "user_id", "pet_id", "housing", "experience", "phone", "status"),
    "pet_alert": ("id", "user_id", "species", "breed", "postal", "radius"),
}
INITIAL_COUNTS = {"user": 4, "shelter": 6, "pet": 20, "favorite": 1, "application": 0, "pet_alert": 0}

# Location token sets that make the mirror return EVERY Arizona pet (app.search scores
# "city state postal" token overlap, so any query containing the state token matches all).
AZ_WIDE = ({"az"}, {"arizona"})


# --------------------------------------------------------------------------- #
# CLI / run loading
# --------------------------------------------------------------------------- #
import simpleArgParser as sap  # noqa: E402  (available in agent_demo's uv env)


def parse_args():
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

    args = sap.parse_args(VerifyArgs)
    if not args.run_dir:
        raise SystemExit("--run_dir is required")
    run_dir = Path(args.run_dir)
    if not args.initial_db and (run_dir / "initial.db").is_file():
        args.initial_db = str(run_dir / "initial.db")
    if not args.after_db and (run_dir / "after.db").is_file():
        args.after_db = str(run_dir / "after.db")
    return args


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    d = Path(run_dir)
    data = json.loads((d / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    data["_run_dir"] = str(d.resolve())
    data["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))} if (d / "screenshots").is_dir() else {}
    return data


def final_answer(traj: dict[str, Any]) -> str:
    return str(traj.get("final_answer") or "").strip()


def final_url(traj: dict[str, Any]) -> str:
    if traj.get("final_url"):
        return str(traj["final_url"])
    for step in reversed(traj.get("steps") or []):
        if isinstance(step, dict) and step.get("url"):
            return str(step["url"])
    return ""


def step_urls(traj: dict[str, Any]) -> list[str]:
    return [str(s.get("url", "")) for s in traj.get("steps", []) if isinstance(s, dict)]


def trajectory_urls(traj: dict[str, Any]) -> list[str]:
    """start_url, every step URL (url / url_before / url_after) and final_url, in order."""
    urls: list[str] = []
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


def is_site_url(url: str) -> bool:
    """HTTP(S) on a loopback host, any port (runs use alt ports like 41024 or 45003)."""
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


def site_urls(traj: dict[str, Any]) -> list[str]:
    return [u for u in trajectory_urls(traj) if is_site_url(u)]


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def navigated_to_path(traj: dict[str, Any], expected_path: str) -> bool:
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to(traj: dict[str, Any], substr: str, times: int = 1) -> bool:
    """merriam_webster parity: at least `times` recorded site URLs contain substr."""
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def pet_visited(traj: dict[str, Any], slug: str) -> bool:
    return navigated_to_path(traj, f"/pet/{slug}")


def shelter_visited(traj: dict[str, Any], shelter_id: int) -> bool:
    return navigated_to_path(traj, f"/shelter/{int(shelter_id)}")


def _tokens(text: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_text(text)))


def _query_of(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query, keep_blank_values=True)


def _location_ok(query: dict[str, list[str]], location_any: Sequence[set[str]] | None) -> bool:
    if not location_any:
        return True
    recorded = _tokens(" ".join(query.get("location") or []))
    return any(set(alt) <= recorded for alt in location_any)


def _param_ok(query: dict[str, list[str]], key: str, expected: Any) -> bool:
    values = [normalize_text(v) for v in (query.get(key) or [])]
    if key == "breed":
        return any(normalize_text(expected) in v for v in values)
    if isinstance(expected, (tuple, list, set, frozenset)):
        return any(normalize_text(alt) in values for alt in expected)
    return normalize_text(expected) in values


def search_visits(traj: dict[str, Any]) -> list[str]:
    return [u for u in site_urls(traj) if normalized_url_path(u) == "/search"]


def search_visited(traj: dict[str, Any], location_any: Sequence[set[str]] | None = None, **params: Any) -> bool:
    """Some /search visit carries the requested location tokens AND every exact param.

    ``location_any`` is a list of token sets; the recorded ``location`` value must contain
    every token of at least one set ("Phoenix, AZ" -> {phoenix, az}). ``breed`` is a
    normalized substring; other params (species, sex, age, size, page) are exact values
    (a tuple means any of the alternatives).
    """
    for url in search_visits(traj):
        query = _query_of(url)
        if _location_ok(query, location_any) and all(_param_ok(query, k, v) for k, v in params.items()):
            return True
    return False


def shelters_search_visited(traj: dict[str, Any], q_any: Sequence[set[str]]) -> bool:
    for url in site_urls(traj):
        if normalized_url_path(url) != "/shelters":
            continue
        recorded = _tokens(" ".join(_query_of(url).get("q") or []))
        if any(set(alt) <= recorded for alt in q_any):
            return True
    return False


def trajectory_task_matches(traj: dict[str, Any], task_id: str) -> bool:
    return str(traj.get("task_id") or "").strip() == task_id


def trajectory_input_texts(traj: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for step in traj.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) != "input":
            continue
        params = step.get("params")
        if isinstance(params, dict) and params.get("text") is not None:
            values.append(str(params["text"]))
    return values


def trajectory_input_contains(traj: dict[str, Any], expected_text: str) -> bool:
    expected = normalize_text(expected_text)
    return any(normalize_text(v) == expected for v in trajectory_input_texts(traj))


def trajectory_last_email(traj: dict[str, Any]) -> str:
    emails = [normalize_text(v) for v in trajectory_input_texts(traj)
              if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v.strip())]
    return emails[-1] if emails else ""


def trajectory_emails(traj: dict[str, Any]) -> list[str]:
    return [normalize_text(v) for v in trajectory_input_texts(traj)
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v.strip())]


# --------------------------------------------------------------------------- #
# Text normalization and answer matchers (affirmative, negation-aware)
# --------------------------------------------------------------------------- #
def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def norm(s: Any) -> str:  # merriam_webster parity
    return normalize_text(s)


NEGATION = r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|aren't|arent|neither|nor)\b"


def _match_is_affirmative(text: str, match: re.Match[str]) -> bool:
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead|whereas|while)\b", text[:match.start()], flags=re.I)[-1]
    after = text[match.end():]
    return not re.search(NEGATION, before, re.I) and not re.match(
        r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I)


def _affirmative_search(pattern: str, text: str, flags: int = 0) -> bool:
    return any(_match_is_affirmative(text, m) for m in re.finditer(pattern, text, flags))


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return all(bool(v) and _affirmative_search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", normalized)
               for v in (normalize_text(x) for x in expected))


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return any(bool(v) and _affirmative_search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", normalized)
               for v in (normalize_text(x) for x in expected))


def answer_equals(final: Any, expected: Any) -> bool:
    return normalize_text(final) == normalize_text(expected)


def contains_phrase_loose(text: Any, phrase: Any) -> bool:
    """Phrase match ignoring punctuation (titles quoted with/without '?', quotes, dashes)."""
    def squash(s: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", normalize_text(s)).strip()
    return squash(phrase) in squash(text)


def digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def contains_money(text: Any, amount: int) -> bool:
    """``$165``, ``165 dollars``, ``USD 165``, ``$165.00``; not ``$1650`` or ``165 months``."""
    normalized = normalize_text(text)
    amount = int(amount)
    patterns = [
        rf"(?<![\d.])\$\s*{amount}(?:\.00)?(?![\d])",
        rf"(?<![\d.$]){amount}(?:\.00)?\s*(?:dollars|usd|bucks)\b",
        rf"\busd\s*{amount}(?:\.00)?(?![\d])",
    ]
    return any(_affirmative_search(p, normalized) for p in patterns)


def contains_months(text: Any, months: int) -> bool:
    """``36 months``, ``36-month-old``, ``36 mo``, ``36 mos.``; not ``136 months``."""
    normalized = normalize_text(text)
    months = int(months)
    return _affirmative_search(rf"(?<![\d.]){months}(?![\d])\s*-?\s*(?:months?|mos?)\b\.?", normalized)


def contains_count(text: Any, number: int) -> bool:
    normalized = normalize_text(text)
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    if _affirmative_search(rf"(?<![\d.,$]){int(number)}(?![\d]|[.,]\d)", normalized):
        return True
    word = words.get(int(number))
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_phone(text: Any, phone: str) -> bool:
    """``602-555-0141`` with any separators (dash, dot, space, parentheses) or none."""
    d = digits_only(phone)
    raw = unicodedata.normalize("NFKC", str(text or ""))
    groups = [d[:3], d[3:6], d[6:]] if len(d) == 10 else [d]
    sep = r"[\s.\-()]*"
    pattern = r"(?<!\d)" + sep.join(re.escape(g) for g in groups) + r"(?!\d)"
    return _affirmative_search(pattern, raw)


def contains_email(text: Any, email: str) -> bool:
    return _affirmative_search(r"(?<![\w.])" + re.escape(normalize_text(email)) + r"(?![\w])", normalize_text(text))


YES_WORDS = r"(?:yes|true|y|good|ok|okay|fine|friendly|compatible)"
NO_WORDS = r"(?:no|not|false|n|isn't|is not|doesn't|does not|never|neither|nor|unfriendly|incompatible)"


def stated_yes_no(text: Any, keyword_pattern: str, expected_yes: bool, anchor_name: str | None = None) -> bool:
    """Does the answer state ``keyword`` (e.g. "good with children" / "house-trained") as
    yes (expected_yes=True) or no? Handles "X: Yes", "X - No", "X? No", "not X",
    "she is X", "X and Y: No", "neither X nor Y". With conflicting statements the one
    closest to ``anchor_name`` wins.
    """
    normalized = normalize_text(text)
    verdicts: list[tuple[int, bool | None]] = []
    for m in re.finditer(keyword_pattern, normalized):
        after = normalized[m.end():]
        clause_after = re.split(r"[.;\n!]", after, maxsplit=1)[0]
        head = re.match(rf"\s*[:=\-–—?()\"']*\s*(?:is|was|are|:)?\s*[:=\-–—]?\s*({YES_WORDS}|{NO_WORDS})\b", after)
        verdict: bool | None = None
        if head:
            verdict = bool(re.fullmatch(YES_WORDS, head.group(1)))
        else:
            first = re.search(rf"\b({YES_WORDS}|{NO_WORDS})\b", clause_after)
            if first and re.search(r"\b(?:and|or|,|&)\b|,", clause_after[:first.start()]):
                verdict = bool(re.fullmatch(YES_WORDS, first.group(1)))
            elif first and re.fullmatch(NO_WORDS, first.group(1)):
                verdict = False
            else:
                before = re.split(r"[.;\n!,]|\b(?:but|however|whereas|while|although)\b", normalized[:m.start()])[-1]
                if re.search(NEGATION, before):
                    verdict = False
                else:
                    verdict = True
        verdicts.append((m.start(), verdict))
    values = [v for _, v in verdicts if v is not None]
    if not values:
        return False
    if all(v == values[0] for v in values):
        return values[0] == expected_yes
    if anchor_name:
        anchors = [a.start() for a in re.finditer(re.escape(normalize_text(anchor_name)), normalized)]
        if anchors:
            nearest = min((v for v in verdicts if v[1] is not None),
                          key=lambda item: min(abs(item[0] - a) for a in anchors))
            return nearest[1] == expected_yes
    return expected_yes in values


def _first_name_in(segment: str, names: Sequence[str]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for n in names:
        hit = re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", segment)
        if hit and (best is None or hit.start() < best[0]):
            best = (hit.start(), n)
    return best


def _last_name_in(segment: str, names: Sequence[str]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for n in names:
        for hit in re.finditer(r"(?<!\w)" + re.escape(n) + r"(?!\w)", segment):
            if best is None or hit.start() > best[0]:
                best = (hit.start(), n)
    return best


def name_nearest_keyword(text: Any, keyword_pattern: str, names: Sequence[str]) -> str | None:
    """Which pet does the answer attach to the comparison keyword ("lowest", "cheaper",
    "youngest", ...)? Resolution order inside the keyword's clause:
      1. an explicit assignment after the keyword ("lowest fee is Batman", "lowest: Batman",
         "cheapest ... belongs to Batman");
      2. "<keyword> than/among/of/between ..." -> the name just BEFORE the keyword
         ("Pepper is cheaper than Daisy", "Batman has the lowest fee among ...");
      3. the first name after the keyword, else the last name before it.
    None when the keyword never occurs."""
    normalized = normalize_text(text)
    lowered = [normalize_text(n) for n in names]
    alternation = "|".join(re.escape(n) for n in lowered)
    for m in re.finditer(keyword_pattern, normalized):
        after = re.split(r"[.;\n!]", normalized[m.end():], maxsplit=1)[0]
        before = re.split(r"[.;\n!]", normalized[:m.start()])[-1]
        explicit = re.search(
            rf"(?:\bis|\bwas|\bare|\bwould be|\bbelongs to|\bgoes to|\bis for|:|=|→|->|—|–)\s*"
            rf"(?:the\s+|a\s+)?(?:pet\s+|one\s+|dog\s+|cat\s+|kitten\s+)?(?:is\s+)?(?<!\w)({alternation})(?!\w)", after)
        if explicit:
            return explicit.group(1)
        stripped = re.sub(r"^\s*(?:adoption\s+)?(?:fee|price|cost|age|one|pet|dog|cat)?\s*(?:\([^)]*\))?\s*", "", after)
        if re.match(r"(?:than|among|amongst|of|out of|between|compared|across|between)\b", stripped):
            found = _last_name_in(before, lowered)
            if found:
                return found[1]
        found = _first_name_in(after, lowered)
        if found:
            return found[1]
        found = _last_name_in(before, lowered)
        if found:
            return found[1]
    return None


LOWEST = r"\b(?:lowest|cheapest|least expensive|lower|cheaper|less expensive|minimum|smallest fee|less)\b"
HIGHEST = r"\b(?:highest|most expensive|higher|more expensive|pricier|priciest|costlier|costliest)\b"
YOUNGEST = r"\b(?:youngest|younger)\b"
OLDEST = r"\b(?:oldest|older)\b"


def identifies(text: Any, winner: str, others: Sequence[str], keyword_pattern: str,
               inverse_pattern: str | None = None) -> bool:
    """True when the answer singles out ``winner`` for the comparison. With the keyword
    present the name attached to it must be the winner; with only the inverse keyword
    present ("Daisy is more expensive than Pepper") the attached name must be a loser
    and the winner must be named; with neither, the winner must be the only candidate
    named (a bare report such as "Batman, Chihuahua / Yorkshire Terrier, $165")."""
    names = [winner, *others]
    w = normalize_text(winner)
    normalized = normalize_text(text)
    winner_named = bool(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", normalized))
    nearest = name_nearest_keyword(text, keyword_pattern, names)
    if nearest is not None:
        return nearest == w
    if inverse_pattern:
        nearest = name_nearest_keyword(text, inverse_pattern, names)
        if nearest is not None:
            return nearest != w and winner_named
    if not winner_named:
        return False
    return not any(re.search(r"(?<!\w)" + re.escape(normalize_text(o)) + r"(?!\w)", normalized) for o in others)


_LEAD = r"(?:good with|gets? along with|great with|fine with|friendly with|ok with|okay with)"
_CONN = r"\s*(?:,|and|or|&|/|and with|or with)\s*"
CHILDREN_KW = (_LEAD + r"\s+(?:(?:other dogs|other cats|dogs|cats)" + _CONN + r")*(?:children|kids)\b"
               r"|\bwith (?:children|kids)\b|\b(?:child|kid)[- ]friendly\b")
CATS_KW = (_LEAD + r"\s+(?:(?:other dogs|dogs|children|kids)" + _CONN + r")*(?:other cats|cats)\b"
           r"|\bwith (?:other cats|cats)\b|\bcat[- ]friendly\b")
HOUSE_TRAINED_KW = r"\bhouse[- ]?trained\b|\bhousebroken\b|\bhouse[- ]?broken\b|\bpotty[- ]?trained\b|\btoilet[- ]?trained\b"


# --------------------------------------------------------------------------- #
# Judge harness
# --------------------------------------------------------------------------- #
_NO_LLM = False


class Judge:
    def __init__(self, task_id: str, no_llm: bool = True):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = bool(no_llm)
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []

    @property
    def passed(self) -> bool:
        return self.ok

    def check(self, name: str, cond: Any, evidence: str = "", llm: bool = False) -> bool:
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no_llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason or "all checks passed",
                          "evidence": self.evidence}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.ok else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def _same_local_origin(url: str, start_url: str) -> bool:
    try:
        o, s = urlparse(str(url or "")), urlparse(str(start_url or ""))
        return (o.scheme == s.scheme == "http" and o.hostname is not None and s.hostname is not None
                and not o.username and not o.password and o.port == s.port
                and o.hostname.casefold() == s.hostname.casefold() and is_site_url(url))
    except ValueError:
        return False


def _png_ok(path: Path) -> bool:
    try:
        from PIL import Image  # optional; present in agent_demo's env
        with Image.open(path) as im:
            im.load()
            return im.format == "PNG" and im.width > 0 and im.height > 0
    except ImportError:
        pass
    except Exception:
        return False
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
            return False
        width, height = struct.unpack(">II", head[16:24])
        return width > 0 and height > 0
    except OSError:
        return False


def _screenshots_decode(traj: dict[str, Any]) -> tuple[bool, str]:
    root = Path(str(traj.get("_run_dir") or ""))
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
            path = next((c for c in (root / "screenshots" / rel, root / rel) if c.is_file()), None)
            if path is None:
                return False, f"step {index} is missing {key}={name!r}"
            if not _png_ok(path):
                return False, f"step {index} {key} is not a decodable PNG"
            checked += 1
    return True, f"decoded {checked} PNG screenshots"


def check_trajectory_identity(judge: Judge, traj: dict[str, Any], task_id: str) -> None:
    judge.check("final_answer_nonempty", bool(final_answer(traj)), f"final_answer={final_answer(traj)!r}")
    judge.check("trajectory_task_matches", trajectory_task_matches(traj, task_id),
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
    ok, ev = _screenshots_decode(traj)
    judge.check("screenshots_decode", ok, ev)


def check_visited_path(judge: Judge, traj: dict[str, Any], name: str, path: str) -> bool:
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_visited_pet(judge: Judge, traj: dict[str, Any], slug: str) -> bool:
    return judge.check(f"visited_pet_{slug}", pet_visited(traj, slug), f"required_path=/pet/{slug}")


def check_visited_pets(judge: Judge, traj: dict[str, Any], slugs: Iterable[str]) -> None:
    for slug in slugs:
        check_visited_pet(judge, traj, slug)


def check_search_visited(judge: Judge, traj: dict[str, Any], name: str,
                         location_any: Sequence[set[str]] | None = None, **params: Any) -> bool:
    ok = search_visited(traj, location_any, **params)
    described = f"location~{[sorted(a) for a in location_any] if location_any else 'any'} & {params}"
    return judge.check(name, ok, f"required=/search?{described}; observed_search_urls={search_visits(traj)!r}")


def check_signed_in_as(judge: Judge, traj: dict[str, Any], email: str) -> None:
    judge.check("visited_login_page", navigated_to_path(traj, "/login"), "required_path=/login")
    judge.check("entered_expected_account_email", trajectory_last_email(traj) == normalize_text(email),
                f"expected_email={email!r}, last_entered_email={trajectory_last_email(traj)!r}")


def check_paths_in_order(judge: Judge, traj: dict[str, Any], name: str,
                         requirements: Sequence[tuple[str, dict[str, Any]]]) -> bool:
    """Every (path, params) requirement must be met by recorded site URLs in order."""
    urls = site_urls(traj)
    cursor = 0
    for expected_path, params in requirements:
        expected = normalized_url_path(expected_path)
        for index in range(cursor, len(urls)):
            url = urls[index]
            query = _query_of(url)
            if normalized_url_path(url) == expected and all(_param_ok(query, k, v) for k, v in params.items()):
                cursor = index + 1
                break
        else:
            return judge.check(name, False, f"requirements={requirements!r}, observed={urls!r}")
    return judge.check(name, True, f"requirements={requirements!r}")


# --------------------------------------------------------------------------- #
# SQLite state
# --------------------------------------------------------------------------- #
def db_query(db_path: str | os.PathLike[str], sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    handle, dest = tempfile.mkstemp(prefix=f"{SITE}_{kind}_", suffix=".db")
    os.close(handle)
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    r = subprocess.run(["docker", "cp", src, dest], capture_output=True, text=True)
    if r.returncode:
        Path(dest).unlink(missing_ok=True)
        raise RuntimeError(f"could not copy {src}: {r.stderr.strip() or r.stdout.strip()}")
    atexit.register(Path(dest).unlink, missing_ok=True)
    return dest


def resolve_db(explicit_path: str | None, container: str, kind: str) -> str | None:
    if explicit_path:
        p = Path(explicit_path)
        return str(p) if p.is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


def table_columns(db_path: str, table: str) -> tuple[str, ...]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    return tuple(row["name"] for row in db_query(db_path, f"PRAGMA table_info({table})"))


def table_rows(db_path: str, table: str) -> list[tuple[Any, ...]]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    return [tuple(row) for row in db_query(db_path, f"SELECT * FROM {table} ORDER BY 1")]


def table_dicts(db_path: str, table: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    return [dict(row) for row in db_query(db_path, f"SELECT * FROM {table} ORDER BY 1")]


def _tables(db_path: str) -> set[str]:
    return {row["name"] for row in db_query(
        db_path, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def _schema_objects(db_path: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_query(
        db_path, "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE sql IS NOT NULL "
                 "AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]


def catalog_drift(db_path: str) -> list[str]:
    """Differences between the snapshot's pet/shelter/user rows and ground_truth.py."""
    problems: list[str] = []
    pets = {row["slug"]: row for row in table_dicts(db_path, "pet")}
    if set(pets) != {p["slug"] for p in GT.PETS}:
        problems.append(f"pet slugs differ: {sorted(set(pets) ^ {p['slug'] for p in GT.PETS})}")
    for frozen in GT.PETS:
        row = pets.get(frozen["slug"])
        if not row:
            continue
        for field in GT.PET_FIELDS:
            observed = row.get(field)
            expected = frozen[field]
            if field in ("house_trained", "good_dogs", "good_cats", "good_children"):
                observed = int(bool(observed))
            if observed != expected:
                problems.append(f"pet {frozen['slug']}.{field}: expected {expected!r}, observed {observed!r}")
    shelters = {row["id"]: row for row in table_dicts(db_path, "shelter")}
    for frozen in GT.SHELTERS:
        row = shelters.get(frozen["id"])
        if not row:
            problems.append(f"shelter {frozen['id']} missing")
            continue
        for field in GT.SHELTER_FIELDS:
            if row.get(field) != frozen[field]:
                problems.append(f"shelter {frozen['id']}.{field}: expected {frozen[field]!r}, observed {row.get(field)!r}")
    users = {row["id"]: row for row in table_dicts(db_path, "user")}
    for frozen in GT.USERS:
        row = users.get(frozen["id"])
        if not row or normalize_text(row.get("email")) != frozen["email"] or row.get("name") != frozen["name"]:
            problems.append(f"user {frozen['id']}: expected {frozen!r}, observed {dict(row) if row else None!r}")
    favorites = [(r["id"], r["user_id"], r["pet_id"]) for r in table_dicts(db_path, "favorite")]
    if favorites != GT.SEED_FAVORITES:
        problems.append(f"seed favorites differ: expected {GT.SEED_FAVORITES!r}, observed {favorites!r}")
    return problems


def _validate_snapshot_contract(initial_db: str, after_db: str) -> None:
    expected_tables = set(EXPECTED_COLUMNS)
    if _tables(initial_db) != expected_tables or _tables(after_db) != expected_tables:
        raise ValueError(f"unexpected tables: initial={sorted(_tables(initial_db))}, after={sorted(_tables(after_db))}")
    for table, columns in EXPECTED_COLUMNS.items():
        for db in (initial_db, after_db):
            if table_columns(db, table) != columns:
                raise ValueError(f"unexpected columns for {table}: {table_columns(db, table)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    observed = {t: len(table_rows(initial_db, t)) for t in INITIAL_COUNTS}
    if observed != INITIAL_COUNTS:
        raise ValueError(f"initial database counts differ: expected={INITIAL_COUNTS}, observed={observed}")
    drift = catalog_drift(initial_db)
    if drift:
        raise ValueError("initial snapshot does not match the frozen catalog: " + "; ".join(drift[:5]))
    changed = [t for t in IMMUTABLE_TABLES if table_rows(initial_db, t) != table_rows(after_db, t)]
    if changed:
        raise ValueError(f"immutable catalog tables changed: {changed}")


def resolve_snapshots(args, task_id: str) -> tuple[str, str]:
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db or None, args.container, "instance_seed")
    after_db = resolve_db(args.after_db or None, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial and after adopt_a_pet database snapshots are required "
                    "(--initial_db/--after_db, <run_dir>/initial.db + after.db, or docker cp from $WH_CONTAINER)")
    try:
        _validate_snapshot_contract(str(initial_db), str(after_db))
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def user_row(db_path: str, email: str) -> dict[str, Any] | None:
    rows = db_query(db_path, "SELECT id, email, name, password_hash FROM user WHERE lower(email)=lower(?) ORDER BY id LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def user_id_for_email(db_path: str, email: str) -> int | None:
    row = user_row(db_path, email)
    return int(row["id"]) if row else None


def pet_slug_by_id(db_path: str, pet_id: int) -> str:
    rows = db_query(db_path, "SELECT slug FROM pet WHERE id=?", (int(pet_id),))
    return str(rows[0]["slug"]) if rows else f"<pet {pet_id}>"


def favorite_pairs(db_path: str) -> set[tuple[int, int]]:
    return {(int(r["user_id"]), int(r["pet_id"])) for r in db_query(db_path, "SELECT user_id, pet_id FROM favorite")}


def favorite_slugs(db_path: str, email: str) -> set[str]:
    uid = user_id_for_email(db_path, email)
    if uid is None:
        return set()
    return {pet_slug_by_id(db_path, pid) for (u, pid) in favorite_pairs(db_path) if u == uid}


def describe_favorites(db_path: str) -> list[tuple[str, str]]:
    out = []
    for uid, pid in sorted(favorite_pairs(db_path)):
        rows = db_query(db_path, "SELECT email FROM user WHERE id=?", (uid,))
        out.append((normalize_text(rows[0]["email"]) if rows else f"<user {uid}>", pet_slug_by_id(db_path, pid)))
    return out


def table_delta(initial_db: str, after_db: str, table: str) -> dict[str, list[Any]]:
    before = {int(r["id"]): r for r in table_dicts(initial_db, table)}
    after = {int(r["id"]): r for r in table_dicts(after_db, table)}
    common = before.keys() & after.keys()
    return {"added": [after[k] for k in sorted(after.keys() - before.keys())],
            "removed": [before[k] for k in sorted(before.keys() - after.keys())],
            "changed": [(before[k], after[k]) for k in sorted(common) if before[k] != after[k]]}


def tables_unchanged(initial_db: str, after_db: str, tables: Iterable[str]) -> dict[str, bool]:
    return {t: table_rows(initial_db, t) == table_rows(after_db, t) for t in tables}


def check_tables_unchanged(judge: Judge, initial_db: str, after_db: str, tables: Iterable[str], prefix: str = "") -> None:
    for table, same in tables_unchanged(initial_db, after_db, tables).items():
        judge.check(f"{prefix}{table}_unchanged", same,
                    f"table={table}, initial_rows={len(table_rows(initial_db, table))}, "
                    f"after_rows={len(table_rows(after_db, table))}, identical={same}")


def check_read_only(judge: Judge, initial_db: str, after_db: str) -> None:
    """Read-only tasks: user, favorite, application and pet_alert must be row-identical."""
    check_tables_unchanged(judge, initial_db, after_db, MUTABLE_TABLES, prefix="read_only_")


def check_exact_favorite_delta(judge: Judge, initial_db: str, after_db: str,
                               added: Iterable[tuple[str, str]] = (), removed: Iterable[tuple[str, str]] = ()) -> None:
    """The favorite table must change by EXACTLY the given (email, slug) pairs."""
    def resolve(pairs: Iterable[tuple[str, str]], db: str) -> set[tuple[int, int]]:
        out = set()
        for email, slug in pairs:
            uid = user_id_for_email(db, email)
            out.add((uid if uid is not None else -1, GT.pet(slug)["id"]))
        return out
    before, after = favorite_pairs(initial_db), favorite_pairs(after_db)
    exp_added, exp_removed = resolve(added, after_db), resolve(removed, initial_db)
    judge.check("favorites_added_exactly", after - before == exp_added,
                f"expected_added={sorted(added)!r}, observed_added={[p for p in describe_favorites(after_db) if p not in describe_favorites(initial_db)]!r}")
    judge.check("favorites_removed_exactly", before - after == exp_removed,
                f"expected_removed={sorted(removed)!r}, observed_removed={[p for p in describe_favorites(initial_db) if p not in describe_favorites(after_db)]!r}")
    delta = table_delta(initial_db, after_db, "favorite")
    judge.check("favorites_no_rewritten_rows", not delta["changed"], f"changed={delta['changed']!r}")


def password_matches(stored_hash: Any, password: str) -> bool:
    """Verify a werkzeug ``scrypt:N:r:p$salt$hex`` (or ``pbkdf2:sha256:iters$salt$hex``) hash with stdlib."""
    try:
        method, salt, digest = str(stored_hash or "").split("$", 2)
    except ValueError:
        return False
    try:
        if method.startswith("scrypt:"):
            _, n, r, p = method.split(":")
            computed = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=int(n), r=int(r), p=int(p),
                                      maxmem=132 * 1024 * 1024, dklen=64).hex()
        elif method.startswith("pbkdf2:"):
            parts = method.split(":")
            algo = parts[1]
            iters = int(parts[2]) if len(parts) > 2 else 600000
            computed = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt.encode("utf-8"), iters).hex()
        else:
            return False
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed, digest)


# --------------------------------------------------------------------------- #
# LLM utilities (parity with merriam_webster; never on the verdict path)
# --------------------------------------------------------------------------- #
def _llm_config():
    return os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_BASE_URL", ""), os.environ.get("JUDGE_MODEL", "")


def _chat(messages, max_tokens=1024):
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s


def llm_text_match(agent_answer, ground_truth, question):
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\nDecide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)


def llm_screenshot_shows(shot_path, must_show, question=""):
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    out = _chat([{"role": "user", "content": [
        {"type": "text", "text": f"You are a STRICT binary grader. Only what is VISIBLY rendered in this screenshot counts.\n"
                                 f"Question the page should answer: {question}\nExpected content to verify PRESENCE of: {must_show}\n"
                                 f"PASS only if the expected content is visibly shown. Do NOT use prior knowledge.\n"
                                 f"Line 1: PASS or FAIL. Line 2: quote the visible evidence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
    return _verdict(out)


# --------------------------------------------------------------------------- #
# Verifier entry point shared by verify_N.py
# --------------------------------------------------------------------------- #
def run_verifier(task_id: str, run_checks) -> None:
    """Common main(): load run, resolve snapshots, run checks, emit; any exception fails closed."""
    args = parse_args()
    try:
        traj = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(task_id, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, task_id)
    judge = Judge(task_id, no_llm=True if args.no_llm else True)  # verdicts never depend on an LLM
    try:
        run_checks(judge, traj, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()
