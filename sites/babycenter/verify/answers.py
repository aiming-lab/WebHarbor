"""Typed, entity-bound answer contracts; reviewer-only expected facts.

Tasks explicitly request JSON so a count cannot be satisfied by a stray number
about another entity. Text fields accept short equivalent descriptions, not
arbitrary prose containing the right keywords. Navigation/state are independent.
"""

import json
import re
import unicodedata
from datetime import datetime


def norm(value):
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value))
        .casefold()
        .replace("β", "beta")
        .replace("–", "-")
        .replace("—", "-"),
    ).strip()


def parse_answer(value):
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)

    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError(f"duplicate answer key: {k}")
            result[k] = v
        return result

    data = json.loads(
        text,
        object_pairs_hook=unique,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
    )
    if not isinstance(data, dict):
        raise ValueError("Expected one JSON object")
    return data


def integer(value, expected):
    return type(value) in (int, float) and value == expected


def date_value(value, expected):
    if not isinstance(value, str):
        return False
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%B %d %Y"):
        try:
            if datetime.strptime(value.strip(), fmt).date().isoformat() == expected:
                return True
        except ValueError:
            pass
    return False


def words(value, expected):
    return isinstance(value, str) and norm(value).rstrip(".") == norm(expected).rstrip(
        "."
    )


def number_range(value, low, high):
    if isinstance(value, list):
        return len(value) == 2 and integer(value[0], low) and integer(value[1], high)
    if isinstance(value, str):
        return bool(
            re.fullmatch(
                rf"(?:between )?{low}\s*(?:-|to|and)\s*{high}(?: weeks)?", norm(value)
            )
        )
    return False


def affirmative(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 600:
        return False
    return not re.search(
        r"\b(?:not|no|never|cannot|can't|isn't|doesn't|wrong|incorrect|reference)\b",
        norm(value),
    )


def fact(value, *patterns):
    return affirmative(value) and all(re.search(p, norm(value)) for p in patterns)


def motor2(value):
    return fact(
        value,
        r"\bhead\b",
        r"\b(?:steady|control|hold|holds|holding|lift|lifts|raise|raises)\b",
    ) and (
        re.search(r"\b(?:steady|chest|sitting|seated|prone)\b", norm(value)) is not None
    )


def motor6(value):
    return (
        fact(value, r"\bsit(?:s|ting)?\b", r"\b(?:support|supported|assistance|help)\b")
        and "without" not in norm(value)
        and "unsupported" not in norm(value)
    )


def other_motor6(value):
    return (
        motor6(value)
        or fact(
            value, r"\bstand(?:s|ing)?\b", r"\b(?:help|assistance|supported|support)\b"
        )
        or fact(
            value,
            r"\bpass(?:es|ing)?\b|\btransfer(?:s|ring)?\b",
            r"\bobjects?\b",
            r"\bhands\b",
        )
        or fact(value, r"\broll", r"\bfront\b", r"\bback\b")
    )


def sample_method(value):
    return fact(
        value, r"\bneedle\b", r"\bultrasound\b", r"\bguid", r"\bamniotic[ -]fluid\b"
    )


def screening(value):
    if not affirmative(value):
        return False
    return bool(
        re.fullmatch(
            r"(?:an? )?(?:abdominal (?:and/or|or) transvaginal |abdominal |transvaginal )?ultrasound(?: (?:scan|screening))?\.?|(?:maternal )?(?:blood(?:/serum)?|serum)(?: (?:testing|test|screening))?\.?",
            norm(value),
        )
    )


KEYS = [
    "cycles due_date_difference_days",
    "raking_month raking_description raking_other_motor month_2_motor",
    "serum_markers ultrasound_measurement amniocentesis_type amniocentesis_sample_method",
    "screening_component amniocentesis_sample_method",
    "week_18_scan_window week_20_blood_test week_30_rem_max_percent",
    "rem_starts_week rem_max_percent growth_plateau_week saved_total",
    "month_2_motor month_6_sitting month_7_sitting month_10_grasp",
    "night_waking_reason thread_replies",
    "solids_author solids_replies sleep_author sleep_replies reply_difference",
    "pregnancy_week saved_total saved_types preterm_before_week scan_window_weeks",
    "saved_title saved_total",
    "removed_title preterm_before_week saved_total remaining_type scan_window_weeks",
    "display_name",
    "stage due_date baby_birthdate pregnancy_week",
    "display_name email pregnancy_week guide_week",
]


def check_answer(task, answer, judge):
    try:
        a = parse_answer(answer)
    except (ValueError, TypeError) as exc:
        judge.check("answer_json", False, str(exc))
        return
    judge.check("answer_fields", set(a) == set(KEYS[task].split()), repr(sorted(a)))

    def check(key, fn):
        try:
            passed = fn(a.get(key))
        except (TypeError, ValueError, AttributeError):
            passed = False
        judge.check("answer_" + key, bool(passed), repr(a.get(key)))

    def num(key, n):
        check(key, lambda v: integer(v, n))

    if task == 0:

        def cycles(rows):
            if not isinstance(rows, list) or len(rows) != 2:
                return False
            for cycle, due in ((28, "2026-11-27"), (31, "2026-11-30")):
                hits = [
                    r
                    for r in rows
                    if isinstance(r, dict) and integer(r.get("cycle_days"), cycle)
                ]
                if len(hits) != 1 or set(hits[0]) != {
                    "cycle_days",
                    "due_date",
                    "guide_week",
                }:
                    return False
                if not date_value(hits[0]["due_date"], due) or not integer(
                    hits[0]["guide_week"], 13
                ):
                    return False
            return True

        check("cycles", cycles)
        num("due_date_difference_days", 3)
    elif task == 1:
        num("raking_month", 6)
        check(
            "raking_description",
            lambda v: fact(
                v, r"\bfingers?\b", r"\brak", r"\b(?:pick|collect|gather|grab)"
            ),
        )
        check("raking_other_motor", other_motor6)
        check("month_2_motor", motor2)
    elif task == 2:

        def markers(v):
            if not isinstance(v, list):
                return False
            aliases = {
                "free beta-hcg": "free beta hcg",
                "free beta hcg": "free beta hcg",
                "papp-a": "papp a",
                "papp a": "papp a",
                "intact or beta hcg": "intact or beta hcg",
                "intact hcg": "intact hcg",
                "beta hcg": "beta hcg",
                "beta-hcg": "beta hcg",
                "h-hcg": "h hcg",
                "h hcg": "h hcg",
                "hyperglycosylated hcg": "h hcg",
            }
            values = [aliases.get(norm(x)) for x in v if isinstance(x, str)]
            return (
                len(values) == len(v)
                and len(values) == len(set(values))
                and set(values)
                in (
                    {"free beta hcg", "papp a", "intact or beta hcg", "h hcg"},
                    {"free beta hcg", "papp a", "intact hcg", "beta hcg", "h hcg"},
                )
            )

        check("serum_markers", markers)
        check(
            "ultrasound_measurement",
            lambda v: (
                norm(v)
                in {
                    "nuchal translucency",
                    "nuchal translucency (nt)",
                    "nt",
                    "nuchal translucency measurement",
                }
            ),
        )
        check(
            "amniocentesis_type",
            lambda v: (
                fact(v, r"\binvasive\b", r"\bdiagnos")
                and not re.search(r"non[ -]?invasive", norm(v))
            ),
        )
        check("amniocentesis_sample_method", sample_method)
    elif task == 3:
        check("screening_component", screening)
        check("amniocentesis_sample_method", sample_method)
    elif task == 4:
        check("week_18_scan_window", lambda v: number_range(v, 18, 22))
        check(
            "week_20_blood_test",
            lambda v: (
                norm(v)
                in {
                    "quad",
                    "quad test",
                    "quad blood test",
                    "second-trimester quad blood test",
                    "quadruple test",
                }
            ),
        )
        num("week_30_rem_max_percent", 80)
    elif task == 5:
        for key, n in (
            ("rem_starts_week", 30),
            ("rem_max_percent", 80),
            ("growth_plateau_week", 37),
            ("saved_total", 4),
        ):
            num(key, n)
    elif task == 6:
        check("month_2_motor", motor2)
        check("month_6_sitting", motor6)
        check(
            "month_7_sitting",
            lambda v: fact(
                v,
                r"\bsit(?:s|ting)?\b",
                r"\bwithout (?:the )?support(?: of (?:the )?hands)?\b|\bunsupported\b|\bindependent(?:ly)?\b",
            ),
        )
        check("month_10_grasp", lambda v: fact(v, r"\bpincer\b", r"\bgrasp\b|\bgrip\b"))
    elif task == 7:
        check(
            "night_waking_reason",
            lambda v: fact(
                v,
                r"\bfeed",
                r"\bfrequen|\boften\b",
                r"\bsids\b|sudden infant death syndrome",
                r"\bprotect|\breduc.*risk",
            ),
        )
        num("thread_replies", 64)
    elif task == 8:
        check("solids_author", lambda v: words(v, "PriyaC"))
        check("sleep_author", lambda v: words(v, "SamK"))
        for key, n in (
            ("solids_replies", 22),
            ("sleep_replies", 64),
            ("reply_difference", 42),
        ):
            num(key, n)
    elif task == 9:
        num("pregnancy_week", 18)
        num("saved_total", 2)
        num("preterm_before_week", 37)
        check(
            "saved_types",
            lambda v: (
                isinstance(v, list)
                and len(v) == 2
                and {norm(x) for x in v} == {"article", "week"}
            ),
        )
        check("scan_window_weeks", lambda v: number_range(v, 18, 22))
    elif task == 10:
        check("saved_title", lambda v: words(v, "Approaches to infant sleep"))
        num("saved_total", 3)
    elif task == 11:
        check(
            "removed_title",
            lambda v: words(v, "How births are classified by gestational age"),
        )
        num("preterm_before_week", 37)
        num("saved_total", 1)
        check("remaining_type", lambda v: words(v, "week"))
        check("scan_window_weeks", lambda v: number_range(v, 18, 22))
    elif task == 12:
        check("display_name", lambda v: v == "Alice Harper")
    elif task == 13:
        check("stage", lambda v: v == "Planning for birth")
        check("due_date", lambda v: date_value(v, "2026-09-18"))
        check("baby_birthdate", lambda v: v is None)
        num("pregnancy_week", 24)
    elif task == 14:
        check("display_name", lambda v: v == "Jordan Lee")
        check("email", lambda v: v == "jordan.lee@example.test")
        num("pregnancy_week", 11)
        num("guide_week", 10)
