"""Bounded, deterministic claim checks for Amtrak answers, not a prose template.

Sentences, bullets and Markdown tables are normalized into local claims. Values
are bound to nearby property/entity labels and all extracted claims for a field
must agree. This is deliberately not a general natural-language entailment model;
unrecognized/ambiguous claims fail with a named checkpoint, never guessed facts.
"""

from __future__ import annotations

import re
from datetime import datetime
from answer_contract import number, normalized

WORDS = r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand"
STATIONS = {
    "VAN": r"vancouver|van",
    "SEA": r"seattle|sea",
    "PDX": r"portland|pdx",
    "EUG": r"eugene(?:-springfield)?|eug",
    "ANA": r"anaheim|ana",
    "SBA": r"santa barbara|sba",
    "DEN": r"denver|den",
    "CHI": r"chicago|chi",
    "SLO": r"san luis obispo|slo",
    "LAX": r"los angeles|lax",
    "SAN": r"san diego|san",
}
NEGATIVE = r"\b(?:not|never|incorrect|wrong|isn't|is not|doesn't|does not|don't|do not|ignore|skip|neither|no)\b"
REFERENCE = r"\b(?:reference|ref\.?|unrelated|example|support id|another train)\b"
MONEY = r"(?<![\w.])(?:\$\s*|usd\s*)?\d+(?:\.\d{1,2})?(?:\s*(?:dollars|usd))?(?![\w.])"


def clean(text):
    text = str(text).replace("’", "'").replace("**", "").replace("`", "")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    pattern = rf"\b(?:{WORDS})(?:(?:[ -]+(?:and[ -]+)?)(?:{WORDS}))*\b"

    def numeric(match):
        try:
            return str(int(number(match.group())))
        except ValueError:
            return match.group()

    text = re.sub(pattern, numeric, text, flags=re.I)
    # Common paired comparison, with positional binding made explicit internally.
    text = re.sub(
        r"(?i)\b(saver|flexible|business|value)\s+and\s+(saver|flexible|business|value)\s+(?:cost|are|fares are|prices are)\s+(\$?\d+(?:\.\d+)?)\s+and\s+(\$?\d+(?:\.\d+)?)(?:\s+dollars)?\s*,?\s*respectively",
        lambda m: f"{m[1]} costs {m[3]}; {m[2]} costs {m[4]}",
        text,
    )
    return text


def table_rows(text):
    """Interpret ordinary tables by their header labels, not a required schema."""
    lines = text.splitlines()
    header = None
    output = []
    for line in lines:
        if "|" not in line:
            output.append(line)
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]+", c or "-") for c in cells):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) != len(header):
            output.append(line)
            continue
        output.extend(
            f"{cells[0]} {label}: {value}."
            for label, value in zip(header[1:], cells[1:])
        )
    return "\n".join(output)


def clauses(text):
    text = table_rows(clean(text)).casefold()
    # Preserve decimal points, dates and numeric grouping. Lists of station codes
    # are checked separately before clause splitting.
    return [
        s.strip(" -*|")
        for s in re.split(
            r"(?<!\d)\.(?!\d)|(?<=\d)\.(?!\d)|[;!\n]|\b(?:but|whereas|while|versus|vs\.?|and)\b|,(?!\s*\d{4}\b)",
            text,
        )
        if s.strip(" -*|")
    ]


def sentences(text):
    return [
        s.strip()
        for s in re.split(
            r"(?<!\d)\.(?!\d)|(?<=\d)\.(?!\d)|[;\n!]", clean(text).casefold()
        )
        if s.strip()
    ]


def positive(text):
    return not re.search(NEGATIVE + "|" + REFERENCE, text)


def labels(text, aliases):
    return list(re.finditer(r"\b(?:" + aliases + r")\b", text, re.I))


def numeric_claims(text, rules, kind="money"):
    """Assign a value only to a local named property, never to global keywords."""
    found = {key: [] for key in rules}
    for clause in clauses(text):
        if re.search(REFERENCE, clause):
            continue
        if (
            kind == "count"
            and "balance" in rules
            and re.search(r"\b(?:more|difference|minus|ahead|lead)\b", clause)
        ):
            continue
        anchors = [
            (m, key) for key, alias in rules.items() for m in labels(clause, alias)
        ]
        if not anchors:
            continue
        pattern = MONEY if kind == "money" else r"(?<![\w.:])\d+(?![\w.:])"
        for value in re.finditer(pattern, clause):
            if kind == "money" and not re.search(r"\$|usd|dollars|\.", value.group()):
                # Bare integers are prices only next to a fare/price/cost label.
                if not re.search(
                    r"fare|price|cost|total|extra|upgrade|increase|difference", clause
                ):
                    continue
            distances = [
                (max(m.start() - value.end(), value.start() - m.end(), 0), key, m)
                for m, key in anchors
            ]
            distance, key, anchor = min(distances, key=lambda item: item[0])
            if distance > 70:
                continue
            tail = clause[value.end() :]
            foreign_money = bool(re.search(r"[€£¥]\s*$", clause[: value.start()]))
            wrong_unit = (
                re.match(
                    r"\s*(?:points?|minutes?|hours?|credits?|euros?|eur|gbp)\b", tail
                )
                if kind == "money"
                else re.search(r"[$€£¥]\s*$", clause[: value.start()])
            )
            if foreign_money or wrong_unit:
                found[key].append(None)
                continue
            between = clause[
                min(value.end(), anchor.end()) : max(value.start(), anchor.start())
            ]
            if re.search(r"\b(?:reference|for another|not)\b", between):
                continue
            if kind == "count" and re.search(r"\d|\btrain\b", between):
                continue
            # A negated field does not assert the requested value. Preserve a
            # wrong affirmative value elsewhere so contradictions still fail.
            if not positive(clause):
                found[key].append(None)
                continue
            try:
                found[key].append(number(value.group()))
            except ValueError:
                found[key].append(None)
    return found


def agrees(values, expected):
    return bool(values) and all(
        v is not None and abs(v - expected) < 1e-6 for v in values
    )


def mention(text, value, aliases=None):
    matches = [c for c in clauses(text) if labels(c, aliases or re.escape(str(value)))]
    return (
        bool(matches)
        and any(positive(c) for c in matches)
        and not any(
            re.search(
                r"\b(?:not|incorrect|wrong)\s+(?:the\s+)?" + re.escape(str(value)), c
            )
            for c in matches
        )
    )


def date_claim(text, expected):
    dates = []
    months = r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    pattern = rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|(?:{months})\s+\d{{1,2}}(?:,?\s+\d{{4}})?|\d{{1,2}}\s+(?:{months})(?:\s+\d{{4}})?)\b"
    for sentence in sentences(text):
        if re.search(REFERENCE, sentence):
            continue
        for match in re.finditer(pattern, sentence, re.I):
            raw = match.group().replace(",", "")
            for fmt in (
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%m/%d/%y",
                "%B %d %Y",
                "%b %d %Y",
                "%d %B %Y",
                "%d %b %Y",
                "%B %d",
                "%b %d",
                "%d %B",
                "%d %b",
            ):
                try:
                    value = datetime.strptime(raw, fmt)
                    if "%Y" not in fmt and "%y" not in fmt:
                        value = value.replace(year=int(expected[:4]))
                    dates.append(
                        value.strftime("%Y-%m-%d") if positive(sentence) else None
                    )
                    break
                except ValueError:
                    continue
    return all_equal(dates, expected)


def single_price(text, expected):
    values = []
    for clause in clauses(text):
        if re.search(REFERENCE, clause):
            continue
        for match in re.finditer(MONEY, clause):
            raw = match.group()
            if re.search(r"\$|usd|dollars|\.", raw):
                wrong_unit = re.match(
                    r"\s*(?:points?|minutes?|hours?|credits?|euros?|eur|gbp)\b",
                    clause[match.end() :],
                ) or re.search(r"[€£¥]\s*$", clause[: match.start()])
                values.append(
                    number(raw) if positive(clause) and not wrong_unit else None
                )
    return agrees(values, expected)


def fare_price(text, expected, family):
    rules = {
        name: re.escape(name)
        for name in (
            "saver",
            "value",
            "flexible",
            "business",
            "roomette",
            "bedroom",
            "family bedroom",
        )
    }
    values = numeric_claims(text, rules)
    return (
        agrees(values[family], expected)
        if values[family]
        else single_price(text, expected)
    )


def train_number(text, expected):
    values = []
    for c in clauses(text):
        if re.search(REFERENCE, c):
            continue
        for m in re.finditer(
            r"\b(?:train(?: number)?|acela(?: express)?|california zephyr)\s*[:#]?\s*(\d+)\b",
            c,
        ):
            values.append(m[1] if positive(c) else None)
    return all_equal(values, str(expected))


def station_claims(text, codes):
    # Explicit contrast entails the negative property on the contrasted station.
    text = clean(text)
    for code, alias in STATIONS.items():
        text = re.sub(
            r"(?i)unlike\s+(?:" + alias + r")(?:\s*\(" + code + r"\))?\s*,",
            f"{code} does not support checked baggage; ",
            text,
        )
    result = {code: [] for code in codes}
    inherited = bool(re.search(r"checked[- ]?\s*(?:baggage|bags?)\s*:", text, re.I))
    for clause in clauses(text):
        if re.search(REFERENCE, clause):
            continue
        baggage = re.search(
            r"checked[- ]?\s*(?:baggage|bags?)|carry[- ]?on[- ]only", clause
        )
        if not baggage and not (
            inherited and re.search(r"\b(?:yes|no|available|unavailable)\b", clause)
        ):
            continue
        negative = bool(
            re.search(
                r"\b(?:no|not|unavailable|without|lacks?|neither|doesn't|isn't)\b|carry[- ]?on[- ]only",
                clause,
            )
        )
        affirmative = bool(
            re.search(
                r"available|supports?|offers?|accepts?|has|yes|can check|checked baggage at",
                clause,
            )
        )
        if not negative and not affirmative:
            continue
        for code in codes:
            if labels(clause, STATIONS.get(code, code)):
                result[code].append(not negative)
    return result


def stop_order(text, expected):
    # Only the listed sequence counts; baggage assertions elsewhere may repeat codes.
    text = clean(text).upper()
    pattern = (
        r"\b[A-Z]{3}\b(?:\s*(?:,|→|->|–|—|\bTO\b|\bTHEN\b|\bAND\b)\s*\b[A-Z]{3}\b)+"
    )
    lists = list(re.finditer(pattern, text))
    relevant = [m for m in lists if len(re.findall(r"\b[A-Z]{3}\b", m.group())) >= 3]
    return bool(relevant) and all(
        re.findall(r"\b[A-Z]{3}\b", m.group()) == expected
        and not re.search(
            r"\b(?:NOT|INCORRECT|WRONG)\b", re.split(r"[.;\n]", text[: m.start()])[-1]
        )
        for m in relevant
    )


def time_claims(text, rules):
    result = {key: [] for key in rules}
    for clause in clauses(text):
        if re.search(REFERENCE, clause):
            continue
        anchors = [
            (m, key) for key, alias in rules.items() for m in labels(clause, alias)
        ]
        for match in re.finditer(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b", clause
        ):
            hour, minute, suffix = match.groups()
            if minute is None and suffix is None:
                continue
            if not anchors:
                continue
            key = min(
                anchors,
                key=lambda a: max(
                    a[0].start() - match.end(), match.start() - a[0].end(), 0
                ),
            )[1]
            hour = int(hour)
            minute = int(minute or 0)
            if suffix:
                hour = hour % 12 + (12 if suffix.startswith("p") else 0)
            result[key].append(f"{hour:02}:{minute:02}" if positive(clause) else None)
    return result


def all_equal(values, expected):
    return bool(values) and all(v == expected for v in values)


def policy_next_step(text):
    candidates = [c for c in sentences(text) if re.search(r"fare|pricing", c)]

    def correct(c):
        return (
            positive(c)
            and re.search(r"review|check|read|consult|look at", c)
            and re.search(r"before|prior to", c)
            and re.search(r"book|reserv", c)
            and re.search(r"sleeper|sleeping room|sleeping accommodation", c)
            and re.search(r"tight|limited time|short on time", c)
        )

    return bool(candidates) and all(correct(c) for c in candidates)


def cutoff(text, expected):
    relevant = [
        c
        for c in clauses(text)
        if re.search(r"baggage|bags|cutoff|cut-off|check-in", c)
    ]
    values = []
    for c in relevant:
        for m in re.finditer(r"\b(\d+)\s*[- ]?(?:minutes?|mins?)\b", c):
            values.append(int(m[1]) if positive(c) else None)
    return agrees(values, expected)


def refund_claims(text):
    result = {"saver": [], "flexible": []}
    current = None
    for clause in clauses(text):
        names = [name for name in result if labels(clause, name)]
        if len(names) == 1:
            current = names[0]
        if not re.search(r"refund|credit|payment|money back|cash", clause):
            continue
        if current is None or len(names) > 1:
            continue
        if current == "saver":
            correct = (
                re.search(r"credit", clause)
                and re.search(r"only", clause)
                and re.search(r"after", clause)
                and re.search(r"cancell?ation window|cancell?ation period", clause)
                and not re.search(
                    r"not.*credit|before.*window|cash refund|refundable.*payment",
                    clause,
                )
            )
        else:
            correct = (
                re.search(r"refund|money back|return", clause)
                and re.search(r"payment", clause)
                and re.search(r"placeholder|original|demo|local", clause)
                and not re.search(
                    r"not refundable|non.?refundable|credit only|no refund|no money back",
                    clause,
                )
            )
        result[current].append(bool(correct))
    return result


def checks(n, text, expected):
    """Return named outcomes; navigation, fixture and DB checks live elsewhere."""
    text = clean(text)
    result = {}

    def add(key, passed):
        result[key] = bool(passed)

    def quantities(rules):
        actual = numeric_claims(text, rules)
        for key in rules:
            add(key, agrees(actual[key], expected[key]))

    def identity(key):
        add(key, mention(text, expected[key]))

    if "route" in expected:
        identity("route")
    if n == 0:
        add("train", train_number(text, expected["train"]))
        durations = []
        for c in clauses(text):
            if re.search(r"on.?board|reference|another train", c):
                continue
            for m in re.finditer(
                r"\b(\d+)\s*(?:h|hr|hrs|hours?)\s*(?:(\d+)\s*(?:m|min|mins|minutes?))?\b|\b(\d+)\s*(?:minutes?|mins?)\b",
                c,
            ):
                value = int(m[1]) * 60 + int(m[2] or 0) if m[1] else int(m[3])
                durations.append(value if positive(c) else None)
        add("total_minutes", agrees(durations, expected["total_minutes"]))
    if n in (1, 2, 3, 4, 12):
        key = next(k for k in expected if k.endswith("_usd"))
        family = {2: "business", 3: "value", 4: "roomette", 12: "flexible"}.get(n)
        add(
            key,
            (
                fare_price(text, expected[key], family)
                if family
                else single_price(text, expected[key])
            ),
        )
        if n == 2:
            add("business_fare", mention(text, "Business"))
        if n == 3:
            add("value_fare", mention(text, "Value"))
        if n == 4:
            identity("room")
    if n in (5, 6):
        if n == 5:
            identity("booking_code")
            add("origin", mention(text, "CHI", STATIONS["CHI"]))
        add("departure_date", date_claim(text, expected["departure_date"]))
        current = (
            "current_flexible_total_usd" if n == 5 else "current_business_total_usd"
        )
        quantities(
            {
                "recorded_total_usd": r"recorded|original|existing|paid|booked",
                current: r"current|new quote|flexible|business|today",
                "increase_usd": r"increase|difference|more|higher|extra",
            }
        )
    if n == 7:
        # Person names scope the metrics until the next named account. Repeated
        # names in tables/bullets naturally yield multiple independently checked facts.
        scopes = {"alice": [], "bob": []}
        source = normalized(table_rows(text))
        matches = list(
            re.finditer(r"\b(alice|bob)(?:\s+jordan|\s+carter)?(?:\x27s)?\b", source)
        )
        for i, m in enumerate(matches):
            scopes[m[1]].append(
                source[
                    m.end() : (
                        matches[i + 1].start() if i + 1 < len(matches) else len(source)
                    )
                ]
            )
        rules = {
            "balance": r"balance|rewards points|points(?!\s*(?:ytd|year|this year))",
            "ytd": r"(?:points\s*)?ytd|year.to.date|this year",
            "status_credits": r"status credits?",
        }
        for person in scopes:
            actual = numeric_claims("; ".join(scopes[person]), rules, kind="count")
            for key in rules:
                add(person + "_" + key, agrees(actual[key], expected[person][key]))
        difference = numeric_claims(
            text,
            {"difference": r"difference|more(?: rewards)? points|ahead|minus|lead"},
            kind="count",
        )["difference"]
        add(
            "balance_difference", agrees(difference, expected["alice_minus_bob_points"])
        )
    if n == 8:
        identity("preferred_station")
    if n in (9, 14):
        add("ordered_stops", stop_order(text, expected["ordered_stops"]))
    if n in (9, 11, 14):
        wanted = (
            expected["checked_baggage"]
            if n != 11
            else {"DEN": expected["checked_baggage"]}
        )
        actual = station_claims(text, list(wanted))
        for code, value in wanted.items():
            add("baggage_" + code, all_equal(actual[code], value))
    if n == 10:
        add("next_step", policy_next_step(text))
        identity("room")
        add("extra_usd", single_price(text, expected["extra_usd"]))
    if n == 11:
        values = numeric_claims(
            text, {"advisory_track": r"track(?: number)?"}, kind="count"
        )
        add(
            "advisory_track",
            agrees(values["advisory_track"], expected["advisory_track"]),
        )
        add("westbound_train", train_number(text, expected["westbound_train"]))
    if n in (11, 15):
        rules = {"departure_time": r"depart(?:s|ure)?(?: time)?|leaves?|departure"}
        if n == 15:
            rules["baggage_deadline"] = r"deadline|latest|check.in|by"
        actual = time_claims(text, rules)
        for key in rules:
            add(key, all_equal(actual[key], expected[key]))
    if n == 13:
        quantities(
            {
                "saver_usd": r"saver",
                "flexible_usd": r"flexible",
                "upgrade_usd": r"upgrad(?:e|ing)|difference|extra|more|increase",
            }
        )
    if n in (14, 15):
        add("cutoff_minutes", cutoff(text, expected["cutoff_minutes"]))
    if n == 15:
        add("train", train_number(text, expected["train"]))
        policies = [
            c for c in sentences(text) if re.search(r"baggage|bags|cutoff|cut-off", c)
        ]
        add(
            "policy_scope",
            any(
                positive(c)
                and re.search(r"long.distance", c)
                and re.search(r"staffed", c)
                and re.search(r"before|prior|cutoff|cut-off", c)
                and not re.search(r"after.*depart", c)
                for c in policies
            ),
        )
    if n == 16:
        identity("article_title")
        identity("category")
        quantities(
            {
                "saver_usd": r"saver",
                "flexible_usd": r"flexible",
                "upgrade_usd": r"upgrad(?:e|ing)|difference|extra|more|increase",
            }
        )
        refunds = refund_claims(text)
        for fare in refunds:
            add(fare + "_refund", all_equal(refunds[fare], True))
    if n == 17:
        identity("booking_code")
    return result
