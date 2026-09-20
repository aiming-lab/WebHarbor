"""Conservative, deterministic fact extraction for natural financial answers.

This supports labelled prose, bullets and simple Markdown tables, not arbitrary
natural-language entailment. Unbound values are rejected instead of guessed.
Reference facts stay in reviewer code, never in the agent-facing task file.
"""

import math
import re


ENTITIES = {
    "ibov": r"ibovespa|ibov",
    "nvda": r"nvidia(?: corp)?|nvda",
    "hon": r"honeywell(?: international)?|hon",
    "lmt": r"lockheed(?: martin)?|lmt",
    "rtx": r"rtx|raytheon",
    "mpc": r"marathon petroleum(?: corp)?|mpc",
    "f": r"ford(?: motor)?(?: co)?|f",
    "ma": r"mastercard(?: inc)?|ma",
    "so": r"southern(?: company| co)?|so",
    "o": r"realty income(?: corp)?|o",
}
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
NUMBER = re.compile(
    r"(?<![\w.])(?P<currency>\$|usd\s*)?(?P<number>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)"
    r"\s*(?P<unit>billion|million|trillion|bn|[bmtk]|percent(?:age)?|%|usd|dollars?|jpy|yen)?"
    r"(?!\w|\.\d)",
    re.I,
)
NEGATIVE = re.compile(
    r"\b(?:not|never|no longer|incorrect|wrong|obsolete|ignore|reference|"
    r"isn't|isnt|didn't|didnt|wasn't|wasnt)\b"
)


def normalize(text):
    text = text.casefold().replace("−", "-").replace("–", "-").replace("’", "'")
    text = re.sub(r"[*`]", "", text)
    for word, number in [
        ("twenty-six", "26"),
        ("twenty six", "26"),
        ("five", "5"),
        ("nine", "9"),
        ("fourteen", "14"),
    ]:
        text = re.sub(r"\b" + word + r"\b", number, text)
    return text


def sentences(text):
    # Decimal points and thousands separators remain inside a claim.
    return [
        s.strip()
        for s in re.split(r";|\n|(?<!\d)\.(?!\d)|(?<=\d)\.(?!\d)", text)
        if s.strip()
    ]


def date_ok(text, year, month, day=None):
    """Accept named-month, ISO and day-first dates; reject conflicting dates."""
    dates = []
    month_pattern = r"(jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)"
    patterns = (
        [
            (
                rf"\b{month_pattern}\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b",
                "mdy",
            ),
            (
                rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{month_pattern}[,]?\s+(20\d{{2}})\b",
                "dmy",
            ),
            (r"\b(20\d{2})-(\d{2})-(\d{2})\b", "iso"),
        ]
        if day
        else [
            (rf"\b{month_pattern}\s+(20\d{{2}})\b", "my"),
            (r"\b(20\d{2})-(\d{2})\b", "ym"),
        ]
    )
    for pattern, order in patterns:
        for match in re.finditer(pattern, text):
            g = match.groups()
            if order == "mdy":
                value = (int(g[2]), MONTHS[g[0][:3]], int(g[1]))
            elif order == "dmy":
                value = (int(g[2]), MONTHS[g[1][:3]], int(g[0]))
            elif order == "iso":
                value = tuple(map(int, g))
            elif order == "my":
                value = (int(g[1]), MONTHS[g[0][:3]], None)
            else:
                value = (int(g[0]), int(g[1]), None)
            clause = next((s for s in sentences(text) if match.group() in s), "")
            dates.append((value, bool(NEGATIVE.search(clause))))
    return bool(dates) and all(
        value == (year, month, day) and not neg for value, neg in dates
    )


def numbers(clause):
    masked = re.sub(
        r"\b(?:jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)\s+\d{1,2},?\s+20\d{2}\b|\b20\d{2}-\d{2}(?:-\d{2})?\b",
        lambda m: " " * len(m.group()),
        clause,
    )
    for match in NUMBER.finditer(masked):
        raw = match["number"].replace(",", "")
        value = float(raw)
        # Years and the range name are context, not the requested measurement.
        if 2020 <= value <= 2030 and "." not in raw:
            continue
        if clause[match.end() :].startswith(("-week", "-wk")):
            continue
        unit = (match["unit"] or "").lower()
        scale = {
            "k": 1e3,
            "m": 1e6,
            "million": 1e6,
            "b": 1e9,
            "bn": 1e9,
            "billion": 1e9,
            "t": 1e12,
            "trillion": 1e12,
        }.get(unit, 1)
        kind = (
            "percent"
            if unit in ("%", "percent", "percentage")
            else "jpy"
            if unit in ("jpy", "yen")
            else "money"
            if match["currency"] or scale != 1 or unit in ("usd", "dollar", "dollars")
            else "number"
        )
        yield match, value * scale, kind


def facts(text, labels):
    """Attach measurements to their nearest named property/entity in a clause.

    Multiple entities/properties in the same clause compete for each value;
    a number cannot silently be reused for both sides of a comparison.
    """
    result = {key: [] for key in labels}
    clauses = [
        (i, part)
        for i, sentence in enumerate(sentences(text))
        for part in re.split(r",\s+(?!\d{3}\b)|\b(?:and|versus|vs\.?)\b", sentence)
    ]
    last_sentence, previous_anchors, previous_negative = None, [], False
    for sentence_id, clause in clauses:
        if sentence_id != last_sentence:
            previous_anchors, previous_negative = [], False
        last_sentence = sentence_id
        anchors = sorted(
            (m.start(), m.end(), key)
            for key, pattern in labels.items()
            for m in re.finditer(r"\b(?:" + pattern + r")\b", clause)
        )
        if anchors:
            previous_anchors = [(0, 0, anchors[-1][2])]
            previous_negative = bool(NEGATIVE.search(clause))
        elif re.match(r"\s*(?:at|with|of|is|are|:|\|)", clause):
            anchors = previous_anchors
        for match, value, kind in numbers(clause):
            candidates = []
            for start, end, key in anchors:
                gap = (
                    clause[end : match.start()]
                    if end <= match.start()
                    else clause[match.end() : start]
                )
                distance = max(start - match.end(), match.start() - end, 0)
                if distance <= 100 and not re.search(r"[;\n]", gap):
                    candidates.append((distance, start, end, key))
            if not candidates:
                continue
            _, start, end, key = min(candidates)
            # Limit polarity to this fact's phrase. A separate "not X" clause
            # does not negate a correct statement about Y.
            previous = max(
                [
                    a[1]
                    for a in anchors
                    if a[1] <= min(start, match.start()) and a[2] != key
                ]
                or [0]
            )
            context = clause[previous : max(end, match.end())]
            result[key].append(
                (value, kind, previous_negative or bool(NEGATIVE.search(context)))
            )
    return result


def values_ok(extracted, key, expected, kind="number"):
    values = extracted.get(key, [])
    tolerance = 0.005 if abs(expected) < 1e6 else 5e6
    return bool(values) and all(
        not negative
        and value_kind == kind
        and math.isclose(value, expected, rel_tol=0, abs_tol=tolerance)
        for value, value_kind, negative in values
    )


def bound(text, labels, expected):
    found = facts(text, labels)
    return all(
        values_ok(found, key, value, kind) for key, (value, kind) in expected.items()
    )


def entity_value(text, entity, value, kind="percent"):
    return bound(text, ENTITIES, {entity: (value, kind)})


def ranked(text, entity, rank):
    claims = []
    for clause in sentences(text):
        entities = [
            (m.start(), m.end(), key)
            for key, pattern in ENTITIES.items()
            for m in re.finditer(r"\b(?:" + pattern + r")\b", clause)
        ]
        for match in re.finditer(rank, clause):
            if not entities:
                continue
            start, end, key = min(
                entities, key=lambda x: max(x[0] - match.end(), match.start() - x[1], 0)
            )
            claims.append(
                key == entity
                and not NEGATIVE.search(
                    clause[min(start, match.start()) : max(end, match.end())]
                )
            )
    return bool(claims) and all(claims)


def answer_ok(index, answer):
    text = normalize(answer)
    if not text.strip():
        return False
    if re.search(r"[€£]|\b(?:eur|euros?|gbp|pounds?)\b", text):
        return False
    if index == 0:
        return bound(
            text,
            {
                "count": r"index(?:es)?|indices",
                "high": r"(?:day )?high",
                "low": r"(?:day )?low",
            },
            {
                "count": (5, "number"),
                "high": (187092.70, "number"),
                "low": (184438.47, "number"),
            },
        ) and ranked(text, "ibov", r"\bhighest\b")
    if index == 1:
        return date_ok(text, 2026, 10, 4) and bound(
            text,
            {"dividend": r"quarterly dividend|dividend per quarter"},
            {"dividend": (0.44, "money")},
        )
    if index == 2:
        return (
            bound(
                text,
                {"count": r"(?:key )?moments?", "drop": r"drop|fell|fall|decline"},
                {"count": (9, "number"), "drop": (3.5, "percent")},
            )
            and bool(re.search(r"biggest|largest|steepest", text))
            and bool(re.search(r"one.day|single.day", text))
            and "months" in text
        )
    if index == 3:
        return bound(
            text,
            {"high": r"(?:52.week )?high", "low": r"(?:52.week )?low"},
            {"high": (299489.06, "money"), "low": (110249.89, "money")},
        )
    if index == 4:
        # Currency suffixes bind the quantities; the rate must specify direction.
        amounts = [v for _, v, kind in numbers(text) if kind == "jpy"]
        rate = re.search(
            r"(?:1\s*(?:usd|us dollar)\s*(?:=|is|equals)|(?:rate|per usd|per us dollar))[^;\n]*",
            text,
        )
        return (
            len(amounts) == 2
            and sorted(amounts) == [161.8704, 404676.0]
            and bool(rate)
            and not NEGATIVE.search(text)
        )
    if index == 5:
        return (
            date_ok(text, 2026, 7, 24)
            and bool(re.search(r"\bsouth china morning post\b", text))
            and not NEGATIVE.search(text)
        )
    if index == 6:
        ratings = re.findall(r"\b(strong buy|strong sell|hold|buy|sell)\b", text)
        return (
            ratings == ["hold"]
            and not NEGATIVE.search(text)
            and bound(
                text,
                {
                    "count": r"(?:analyst )?ratings?",
                    "target": r"average (?:price )?target|mean (?:price )?target",
                },
                {"count": (14, "number"), "target": (104.21, "money")},
            )
        )
    if index in (7, 8, 9):
        labels = {
            "revenue": r"(?:annual |quarterly )?revenue",
            "margin": r"(?:net profit |profit )?margin",
            "assets": r"(?:total )?assets",
            "liabilities": r"(?:total )?liabilities",
        }
        expected = {
            7: {"revenue": (98.36e9, "money"), "margin": (22.77, "percent")},
            8: {"assets": (506.63e9, "money"), "liabilities": (385.10e9, "money")},
            9: {"revenue": (182.60e9, "money")},
        }[index]
        period = (
            date_ok(text, 2026, 6)
            if index in (7, 8)
            else bool(re.search(r"\b2025\b", text))
        )
        return period and bound(text, labels, expected)
    if index == 10:
        if NEGATIVE.search(text):
            return False
        values = [v for _, v, kind in numbers(text) if kind == "percent"]
        if re.search(r"\b(?:fell|fall|drop|decline|decreased|down)\b", text):
            values = [-abs(v) for v in values]
        return bool(values) and all(
            math.isclose(v, -18.57, abs_tol=0.005) for v in values
        )
    if index in (11, 14, 15, 16, 17):
        entity, value, kind = {
            11: ("mpc", 12.69, "percent"),
            14: ("f", 32.19, "number"),
            15: ("ma", 2.03, "percent"),
            16: ("so", 3.41, "percent"),
            17: ("o", 4.49, "percent"),
        }[index]
        # Count and top-N qualifiers should not be attached to the entity value.
        clean = re.sub(
            r"\b(?:top|largest)\s+\d+\b|\b\d+\s+(?:most active )?(?:companies|stocks)\b",
            "",
            text,
        )
        count_ok = index != 15 or bound(
            text, {"count": r"companies"}, {"count": (26, "number")}
        )
        return (
            count_ok
            and entity_value(clean, entity, value, kind)
            and ranked(
                text,
                entity,
                r"\blowest\b" if index == 14 else r"\b(?:largest|highest)\b",
            )
        )
    if index == 12:
        return date_ok(text, 2025, 6) and bound(
            text, {"surprise": r"(?:eps )?surprise"}, {"surprise": (9.08, "percent")}
        )
    if index == 13:
        return bound(
            text,
            ENTITIES,
            {
                "hon": (16.47, "number"),
                "lmt": (22.45, "number"),
                "rtx": (26.97, "number"),
            },
        ) and ranked(text, "hon", r"\blowest\b")
    if index == 18:
        return bound(
            text,
            {"total": r"total (?:gain|return)|growth ideas", "nvda": ENTITIES["nvda"]},
            {"total": (33.23, "percent"), "nvda": (121.64, "percent")},
        ) and ranked(text, "nvda", r"\blargest\b")
    if index == 19:
        # Creation amounts belong to the state check, not the reported results.
        return bound(
            text,
            {"value": r"(?:position )?market value", "gain": r"(?:percentage )?gain"},
            {"value": (9203, "money"), "gain": (22.71, "percent")},
        )
    raise ValueError(f"Unknown task: {index}")
