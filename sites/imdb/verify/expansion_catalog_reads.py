"""Snapshot-derived checks for the four new catalog read tasks.

Only supplied offline evidence is used. Constructed parser tests are not browser
execution evidence. Existing task parsers and their contracts stay unchanged.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itertools import combinations
import re
import sqlite3

from answer_checks import displayed_money, entity_texts, money_field, normalize
from read_tasks import _names, _one, _paragraph_answer, _require
from verify_lib import VerificationError


CATALOG_READ_TASKS = {18, 19, 20, 23}
TOKEN = re.compile(r"\bfilmkey(\d+)\b")
EXCLUSION = re.compile(r"\b(?:not (?:a |an )?(?:winner|eligible|selected|included)|"
                       r"excluded|does not qualify|doesn't qualify|non[- ]qualifying|"
                       r"runner[- ]up|lower than|rather than|unlike)\b")


def _catalog(run):
    return [dict(row) for row in run.initial.execute("SELECT * FROM titles")]


def _masked(answer, titles):
    """Resolve longer title aliases first (Toy Story 3 must not become Toy Story)."""
    text = normalize(answer)
    aliases = {}
    for title in titles:
        for name in _names(title):
            aliases.setdefault(normalize(name), title["id"])
            if "·" in name:
                for separator in ("-", " "):
                    aliases.setdefault(normalize(name.replace("·", separator)), title["id"])
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(
        re.escape(name) for name in sorted(aliases, key=len, reverse=True)) + r")(?!\w)")
    return pattern.sub(lambda m: "filmkey" + str(aliases[m.group()]), text)


def _ids(text):
    return list(dict.fromkeys(int(match.group(1)) for match in TOKEN.finditer(text)))


def _lines(text):
    """Expose ordinary Markdown table headers to the same field parsers as prose."""
    lines = text.splitlines()
    result, i = [], 0
    while i < len(lines):
        if i + 1 < len(lines) and "|" in lines[i] and re.fullmatch(r"[| :\-]+", lines[i + 1].strip()):
            headers = [v.strip() for v in lines[i].strip().strip("|").split("|")]
            i += 2
            while i < len(lines) and "|" in lines[i]:
                cells = [v.strip() for v in lines[i].strip().strip("|").split("|")]
                if len(cells) != len(headers):
                    break
                for header, cell in zip(headers, cells):
                    if re.fullmatch(r"(?:(?:first|second|earlier|later) )?(?:movie|film|title)", header):
                        _require(bool(_ids(cell)), "An unknown title is asserted in a result table")
                result.append("; ".join(h + ": " + c for h, c in zip(headers, cells)))
                i += 1
        else:
            result.append(lines[i])
            i += 1
    return result


def _answer(run, titles, answer=None):
    masked = _masked(run.answer if answer is None else answer, titles)
    lines = _lines(masked)
    aliases = {title["id"]: ["filmkey" + str(title["id"])] for title in titles}
    facts = entity_texts(_paragraph_answer("\n".join(lines), aliases), aliases)
    return lines, facts


def _no_extra_results(lines, expected):
    for line in lines:
        extra = set(_ids(line)) - expected
        _require(not extra or bool(EXCLUSION.search(line)),
                 "An ineligible title is reported as part of the result")
        if not _ids(line) and not EXCLUSION.search(line):
            unknown_row = re.search(r"^[\w .'-]+:\s*.*\b(?:budget|opening|worldwide|domestic|release date)\b.*\d", line)
            _require(not unknown_row, "A factual result row does not identify a catalog movie")


def _details(run, title):
    _require(run.visited("/title/" + title["tt_id"]),
             "A required detail-only fact lacks a local title-page observation")


def _credits(run, nm_id, role):
    person = _one(run.initial, "SELECT * FROM persons WHERE nm_id=?", (nm_id,))
    titles = [dict(row) for row in run.initial.execute(
        "SELECT DISTINCT t.* FROM titles t JOIN credits c ON c.title_id=t.id "
        "WHERE c.person_id=? AND c.role=? AND t.title_type='movie'", (person["id"], role))]
    _require(bool(titles), "The initial snapshot has no movies for the required credit role")
    return person, titles


def _credit_seen(run, person, title, role):
    path = "/title/" + title["tt_id"]
    if run.visited("/name/" + person["nm_id"]) or run.visited(path + "/fullcredits"):
        return True
    if not run.visited(path):
        return False
    if role == "director":
        return True  # All Director credits are visible on a title detail page.
    visible = run.initial.execute(
        "SELECT person_id FROM credits WHERE title_id=? AND role='actor' "
        "ORDER BY CASE WHEN billing_order IS NULL OR billing_order=0 THEN 999 "
        "ELSE billing_order END, id LIMIT 15", (title["id"],)).fetchall()
    return person["id"] in {row[0] for row in visible}


def _money(text, field, raw):
    _require(raw is not None and raw > 0, "A required amount is absent from the snapshot")
    # The new questions explicitly calculate from display precision. Passing
    # this value to the old helper permits equivalent units, not raw precision.
    text = re.sub(r"\bgross us\s*(?:&|and)\s*canada\b", "domestic gross", text)
    text = re.sub(r"(^|[;\n])\s*us\s*(?:&|and)\s*canada\s*:", r"\1domestic gross:", text)
    return money_field(text, field, int(displayed_money(raw)))


def _percent(text, expected):
    values = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:%|percent\b)", text)
    for clause in text.split(";"):
        if ":" in clause:
            label, value = clause.split(":", 1)
            if re.search(r"%|\b(?:percentage|percent|ratio|share)\b", label):
                values += re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", value)
    return bool(values) and all(Decimal(value) == expected for value in values)


def _percentage(numerator, denominator):
    _require(denominator > 0, "The percentage denominator must be positive")
    return (numerator / denominator * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _winners(lines, expected):
    """Recognize an explicit maximum statement or a table Winner=yes column."""
    found = set()
    active = False
    cue = re.compile(r"\b(?:winners?|highest|largest|greatest|maximum|leaders?)\b|"
                     r"(?:并列)?(?:最高|最大)(?:为|的是)?")
    for line in lines:
        if not line.strip():
            active = False
            continue
        table = re.search(r"\bwinner\s*:\s*(yes|no|true|false)\b", line)
        if table:
            if table.group(1) in {"yes", "true"}:
                found.update(_ids(line))
            continue
        if re.fullmatch(r"[ #*-]*(?:joint )?(?:winners?|highest|largest|maximum|leaders?)\s*:", line):
            active = True
            continue
        for clause in re.split(r"\b(?:whereas|while|but|unlike|rather than|compared (?:to|with))\b", line):
            if EXCLUSION.search(clause):
                continue
            if active or cue.search(clause):
                ids = _ids(clause)
                _require(bool(ids), "A maximum assertion does not identify a catalog movie")
                found.update(ids)
                if re.match(r"[ #*-]*(?:joint )?(?:winners?|leaders?|maximum)\s*:", clause):
                    tail = clause.split(":", 1)[1]
                    tail = TOKEN.sub("", tail)
                    tail = re.sub(r"\d+(?:\.\d+)?\s*(?:%|percent)?", "", tail)
                    tail = re.sub(r"\b(?:and|both|all|with|at|a|the|share|percentage|of|tied|are|is)\b", "", tail)
                    _require(not re.search(r"[a-z]", tail), "An unknown extra winner is asserted")
    _require(found == expected, "The explicit maximum set is missing, partial or incorrect")


def _amount_rows(run, selected, fields, percentages):
    catalog = _catalog(run)
    lines, facts = _answer(run, catalog)
    _no_extra_results(lines, {t["id"] for t in selected})
    for title in selected:
        _details(run, title)
        text = facts[title["id"]]
        _require(bool(text), "A required movie row is omitted")
        for label, column in fields:
            _require(_money(text, label, title[column]), "A displayed amount is missing, swapped or bound to the wrong movie")
        _require(_percent(text, percentages[title["id"]]),
                 "A displayed-value percentage is missing or incorrect")
    maximum = max(percentages.values())
    _winners(lines, {key for key, value in percentages.items() if value == maximum})


def _check_19(run):
    director, directing = _credits(run, "nm0000229", "director")
    actor, acting = _credits(run, "nm0000158", "actor")
    selected = [title for title in acting if title["id"] in {t["id"] for t in directing}]
    _require(bool(selected), "The initial role intersection is empty")
    percentages = {}
    for title in selected:
        percentages[title["id"]] = _percentage(displayed_money(title["box_office_opening"]),
                                                 displayed_money(title["budget"]))
        _require(_credit_seen(run, director, title, "director") and _credit_seen(run, actor, title, "actor"),
                 "The shared movie's required credit roles lack relevant local observations")
    _amount_rows(run, selected, (("budget", "budget"), ("opening", "box_office_opening")), percentages)
    return ["Complete Director/Actor intersection, displayed amounts, percentages and maximum set match"]


def _check_20(run):
    actor, selected = _credits(run, "nm0000138", "actor")
    percentages = {}
    for title in selected:
        world, domestic = displayed_money(title["box_office_world"]), displayed_money(title["box_office_us"])
        _require(world >= domestic >= 0, "The snapshot's gross values cannot define the requested remainder")
        percentages[title["id"]] = _percentage(world - domestic, world)
        _require(_credit_seen(run, actor, title, "actor"), "An Actor credit lacks a relevant local observation")
    _amount_rows(run, selected, (("domestic", "box_office_us"), ("worldwide", "box_office_world")), percentages)
    return ["Complete Actor movie catalog, paired displayed grosses, remainder percentages and all maxima match"]


def _number_field(text, labels):
    values = []
    pattern = r"\b(?:" + labels + r")\b(?:\s*\([^)]*\))?\s*(?::|=|is|of)?\s*(\d+(?:\.\d+)?)"
    values += [Decimal(v) for v in re.findall(pattern, text)]
    return values


def _runtime(text):
    values = []
    hours = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b(?:\s*(\d+)\s*(?:minutes?|mins?|m)\b)?")
    for match in hours.finditer(text):
        values.append(Decimal(match.group(1)) * 60 + Decimal(match.group(2) or 0))
    text = hours.sub("", text)
    values += [Decimal(v) for v in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b", text)]
    values += _number_field(text, r"runtime|length")
    return values


def _pair_blocks(lines):
    blocks, active = [], None
    for line in lines:
        ids = _ids(line)
        explicit_pair = (re.search(r"\b(?:(?:best|optimal|closest|shortest|minimum) )?pairs?\s*(?::|is|are)\s*\S", line)
                         and not line.rstrip().endswith(":"))
        if (len(ids) >= 2 or explicit_pair) and not EXCLUSION.search(line):
            if active is not None:
                blocks.append(active)
            active = line
        elif active is not None and not ids and line.strip():
            active += "; " + line
        else:
            if active is not None:
                blocks.append(active)
            active = None
    if active is not None:
        blocks.append(active)
    return blocks


def _double_feature_text(answer):
    """Normalize equivalent Task 18 fields, without translating film identity."""
    text = normalize(answer).replace("。", "\n")
    # Chinese prose has no word boundary before/after an English title or unit.
    text = re.sub(r"(?<=[a-z0-9])(?=[\u3400-\u9fff])|(?<=[\u3400-\u9fff])(?=[a-z0-9])", " ", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*分钟", r"\1 minutes", text)
    text = re.sub(r"(?:评分合计|评分总和|评分之和|评分总计|总评分)\s*[:：]?", "summed rating ", text)
    text = re.sub(r"(?:合计|总时长|时长合计)\s*[:：]?\s*(?=\d+(?:\.\d+)?\s*minutes)", "combined runtime ", text)
    text = re.sub(r"\bimdb\s*(?=\d)", "imdb rating ", text)
    text = text.replace("不符合", " excluded ")
    return text


def _double_feature_blocks(lines):
    """Bind separate totals only when the answer identifies exactly one pair.

    A two-row table and its following totals already identify a program; the
    question does not require a repeated same-line pair label. With several
    programs, retain explicit pair-local binding and reject ambiguous totals.
    """
    relevant = [line for line in lines if not EXCLUSION.search(line)]
    blocks = _pair_blocks(relevant)
    members = set(key for line in relevant for key in _ids(line))
    if len(members) == 2 and all(set(_ids(block)) == members for block in blocks):
        return ["; ".join(relevant)]
    return blocks


def _check_18(run):
    eligible = [dict(row) for row in run.initial.execute(
        "SELECT DISTINCT t.* FROM titles t JOIN title_genre tg ON tg.title_id=t.id "
        "JOIN genres g ON g.id=tg.genre_id WHERE g.slug='animation' AND t.title_type='movie' "
        "AND t.year<=2010 AND t.mpaa_rating IN ('G','PG') AND t.runtime_min IS NOT NULL "
        "AND t.rating_avg IS NOT NULL")]
    feasible = [(a, b) for a, b in combinations(eligible, 2) if a["runtime_min"] + b["runtime_min"] <= 190]
    _require(bool(feasible), "The snapshot has no feasible double feature")
    rating = lambda t: Decimal(f'{t["rating_avg"]:.1f}')
    maximum = max(rating(a) + rating(b) for a, b in feasible)
    optimal = {frozenset((a["id"], b["id"])): (a, b) for a, b in feasible if rating(a) + rating(b) == maximum}
    selected_ids = set().union(*optimal)
    selected = [t for t in eligible if t["id"] in selected_ids]
    lines, facts = _answer(run, _catalog(run), _double_feature_text(run.answer))
    _no_extra_results(lines, selected_ids)
    for title in selected:
        _details(run, title)
        text = "; ".join(clause for clause in re.split(r"[;\n]", facts[title["id"]])
                          if not re.search(r"\b(?:total|combined|summed|sum|together)\b", clause))
        scores = _number_field(text, r"(?:imdb )?rating|score")
        scores += [Decimal(v) for v in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*/\s*10\b", text)]
        _require(bool(scores) and all(v == rating(title) for v in scores), "A selected movie's displayed rating is missing or incorrect")
        runtimes = _runtime(text)
        _require(bool(runtimes) and all(v == title["runtime_min"] for v in runtimes), "A selected movie's runtime is missing or incorrect")
        classifications = re.findall(r"(?<!\w)(?:pg-13|not rated|unrated|pg|g|r|nc-17)(?!\w)", text)
        _require(bool(classifications) and all(v == title["mpaa_rating"].lower() for v in classifications),
                 "A selected movie's MPAA classification is missing or incorrect")
    reported = set()
    for block in _double_feature_blocks(lines):
        if not re.search(r"\b(?:pair|total|combined|summed|sum|together|best|optimal)\b", block):
            continue
        pair = frozenset(_ids(block))
        _require(pair in optimal and len(pair) == 2, "An extra, non-optimal or invalid pair is asserted")
        a, b = optimal[pair]
        runtime = []
        for clause in block.split(";"):
            if re.search(r"\b(?:(?:combined|total|pair) runtime|(?:combined|total) (?:time|minutes))\b", clause):
                value = re.sub(r"\b(?:combined|total|pair) (?:runtime|time|minutes)\b", "runtime", clause)
                runtime += _runtime(value)
        if not runtime:
            runtime = [Decimal(v) for v in re.findall(r"\b(?:together|total|combined)\s*[:=,]?\s*(\d+)\s*(?:minutes?|mins?)", block)]
        scores = _number_field(block, r"(?:summed|combined|total) (?:imdb )?rating|rating sum|sum(?: of (?:the )?ratings)?")
        _require(bool(runtime) and all(v == a["runtime_min"] + b["runtime_min"] for v in runtime), "A pair's combined runtime is missing or incorrect")
        _require(bool(scores) and all(v == maximum for v in scores), "A pair's summed rating is missing or incorrect")
        reported.add(pair)
    _require(reported == set(optimal), "The complete optimal pair set is not reported")
    return ["Snapshot-derived feasible pairs, complete optimum set and all film/pair facts match"]


MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
DATES = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|" + MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+" + MONTHS + r"[,]?\s+\d{4})\b")


def _dates(text):
    found = []
    for match in DATES.finditer(text):
        value = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", match.group()).replace(",", "").replace("sept ", "sep ")
        parsed = None
        for fmt in ("%Y-%m-%d", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
            try:
                parsed = datetime.strptime(value, fmt).date()
                break
            except ValueError:
                continue
        _require(parsed is not None, "An invalid full release date is asserted")
        found.append(parsed)
    return found


def _check_23(run):
    actor, titles = _credits(run, "nm0000158", "actor")
    dates = {t["id"]: date.fromisoformat(t["release_date"]) for t in titles}
    ordered = sorted(titles, key=lambda t: (dates[t["id"]], t["id"]))
    _require(len(ordered) >= 2, "A release timeline needs at least two movies")
    minimum = min((dates[b["id"]] - dates[a["id"]]).days for a, b in zip(ordered, ordered[1:]))
    lines, facts = _answer(run, _catalog(run))
    _no_extra_results(lines, set(dates))
    timeline_lines = [line for line in lines if not re.search(r"\b(?:closest|shortest|minimum|gap|interval|pair)\b", line)]
    aliases = {title["id"]: ["filmkey" + str(title["id"])] for title in titles}
    timeline_facts = entity_texts(_paragraph_answer("\n".join(timeline_lines), aliases), aliases)
    sequence = []
    for title in titles:
        _details(run, title)
        _require(_credit_seen(run, actor, title, "actor"), "An Actor timeline credit lacks a local observation")
        # Timeline rows provide date ownership. Pair summaries need not repeat
        # dates already bound to those exact titles in the complete timeline.
        row_dates = _dates(timeline_facts[title["id"]])
        _require(bool(row_dates) and all(d == dates[title["id"]] for d in row_dates),
                 "A movie's full release date is absent, conflicting or misattributed")
    for line in timeline_lines:
        if _dates(line):
            sequence += [key for key in _ids(line) if key in dates and key not in sequence]
    _require(set(sequence) == set(dates) and [dates[i] for i in sequence] == sorted(dates.values()),
             "The complete movie timeline is not chronological")
    # Same-date films can appear in either order. Adjacency follows the valid
    # reported timeline, rather than imposing an unrequested ID tie-breaker.
    expected = {frozenset((a, b)) for a, b in zip(sequence, sequence[1:])
                if (dates[b] - dates[a]).days == minimum}
    reported = set()
    for block in _pair_blocks(lines):
        if not re.search(r"\b(?:days?|gap|interval|closest|shortest|minimum)\b", block):
            continue
        pair = frozenset(_ids(block))
        _require(pair in expected, "A non-minimal or extra release pair is asserted")
        values = [int(v) for v in re.findall(r"(?<![\w.])(\d+)\s*(?:calendar )?days?\b", block)]
        values += [int(v) for v in re.findall(r"\b(?:gap|days|interval)(?:\s*\((?:calendar )?days?\))?\s*[:=]?\s*(\d+)\b", block)]
        _require(bool(values) and all(v == minimum for v in values), "A minimum gap is absent or incorrect")
        repeated = _dates(block)
        _require(not repeated or repeated == [dates[i] for i in _ids(block)], "A repeated pair date conflicts with its timeline")
        reported.add(pair)
    _require(reported == expected, "One or more tied minimum adjacent pairs are missing")
    return ["Complete chronological Actor timeline and every tied minimum calendar-day interval match"]


def check_catalog_read_task(number, run):
    """Return concise evidence descriptions, or fail closed on invalid input."""
    _require(number in CATALOG_READ_TASKS, "Unsupported catalog read task number")
    _require(bool(run.answer.strip()), "The run has no final answer")
    run.assert_unchanged()
    try:
        result = {18: _check_18, 19: _check_19, 20: _check_20, 23: _check_23}[number](run)
    except (sqlite3.Error, KeyError, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as error:
        raise VerificationError("The supplied snapshot or answer lacks valid required task data") from error
    return result + ["All business tables are unchanged"]
