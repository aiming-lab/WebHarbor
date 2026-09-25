"""Deterministic checks for the revised read-only IMDb tasks.

Answers are derived from the run's initial snapshot, never from an old run or
the live site. The routes required below are named in the questions; alternative
entry routes and either order of unrelated lookups remain valid.
"""

from decimal import Decimal, InvalidOperation
import json
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit

from answer_checks import (amount_values, entity_texts, has_number,
                           mentions, money_field, normalize)
from verify_lib import VerificationError


READ_TASKS = {0, 2, 7, 9, 10, 12, 14}


def _require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def _one(db, sql, parameters=()):
    rows = db.execute(sql, parameters).fetchall()
    _require(len(rows) == 1, "The initial snapshot does not identify one required entity")
    return dict(rows[0])


def _named_title(run, name, year):
    return _one(run.initial, "SELECT * FROM titles WHERE primary_title=? AND year=?", (name, year))


def _title_path(title):
    return "/title/" + title["tt_id"]


def _names(title):
    names = [title["primary_title"]]
    original = title.get("original_title")
    if original and original not in names:
        names.append(original)
    # Ordinary English often omits the initial article when naming a film.
    if names[0].startswith("The "):
        names.append(names[0][4:])
    return names


def _paragraph_answer(answer, entities):
    """Attach continuation lines to a single-entity heading, retaining tables."""
    lines = answer.splitlines()
    output = []
    active = None
    for line in lines:
        if not line.strip() or "|" in line:
            active = None
            output.append(line)
            continue
        found = [key for key, names in entities.items() if any(mentions(line, name) for name in names)]
        if len(found) == 1:
            active = found[0]
            output.append(line)
        elif not found and active is not None:
            output.append(entities[active][0] + ": " + line)
        else:
            active = None
            output.append(line)
    return "\n".join(output)


def _fact_prefix_lines(answer, entities):
    """Keep explicit rank/type prefixes with the following movie in prose."""
    names = sorted({normalize(name) for aliases in entities.values() for name in aliases}, key=len, reverse=True)
    rank = r"(?:#\s*\d+\b|rank(?:ed)?\s*(?::|=|is)?\s*(?:#|no\.?\s*)?\s*\d+\b|(?:first|third)[- ]ranked\b)"
    rank_prefix = rank + r"\s*(?:(?:movie|film)\s*)?[:=-]?\s*"
    type_prefix = (r"(?:(?:highest[- ]rated|top(?:[- ]rated)?)\s+)?(?:crime\s+)?"
                   r"(?:movies?|films?|tv[- ]series|television(?: series)?|series|shows?)\s*[:=-]\s*")
    heading = re.compile(r"(?<!\w)(?:(?:" + rank_prefix + "|" + type_prefix + r"))?(?:"
                         + "|".join(re.escape(name) for name in names) + r")(?!\w)")
    output = []
    for line in normalize(answer).splitlines():
        found = [key for key, aliases in entities.items() if any(mentions(line, name) for name in aliases)]
        if "|" in line or len(found) < 2:
            output.append(line)
            continue
        matches = list(heading.finditer(line))
        # Keep the first entity's leading context; later explicit prefixes move
        # with their entity. Consume full names so aliases cannot split them.
        starts = [0] + [match.start() for match in matches[1:]]
        output.extend(line[start:end] for start, end in zip(starts, starts[1:] + [len(line)]))
    return "\n".join(output)


def _bindings(answer, titles):
    entities = {title["id"]: _names(title) for title in titles}
    answer = _fact_prefix_lines(answer, entities)
    answer = _paragraph_answer(answer, entities)
    texts = entity_texts(answer, entities)
    group = None
    for line in answer.splitlines():
        label = re.match(r"^\s*[#* -]*(movies?|films?|tv(?: series)?|television|series|shows?)\s*:", normalize(line))
        if label:
            group = label.group(1)
        elif not line.strip():
            group = None
        if group:
            for key, names in entities.items():
                if any(mentions(line, name) for name in names):
                    texts[key] += "\nGroup: " + group
    return texts


def _task_texts(run, titles):
    # Other named catalog entities terminate a block even when they are not
    # winners. Their facts must not be inherited by the required entity.
    catalog = [dict(row) for row in run.initial.execute("SELECT * FROM titles")]
    named = _reported_titles(run.answer, catalog)
    entities = {title["id"]: title for title in titles + named}
    return _bindings(run.answer, list(entities.values()))


def _money(text, field, value, allow_unlabeled=False):
    _require(value is not None, "A required catalog amount is missing")
    # A separate comparison sentence need not repeat the supporting amount.
    parts = re.split(r"[\n;]|(?<=[.!?])\s+(?=[A-Z])", text)
    facts = "\n".join(part for part in parts if amount_values(part))
    return bool(facts) and money_field(facts, field, value, allow_unlabeled)


def _rating(text, value):
    if value is None:
        return False
    text = normalize(text)
    labels = re.findall(r"\brating\s*(?:\([^)]*\))?\s*(?:[:=]|is|of|at)?\s*(\d+(?:\.\d+)?)", text)
    fractions = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*/\s*10\b", text)
    explicit = labels + fractions
    if explicit:
        return all(Decimal(number) == Decimal(str(value)) for number in explicit)
    return has_number(text, value)


def _runtime(text, value, difference=None):
    if value is None:
        return False
    text = normalize(text)
    measured = []
    for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b", text):
        if re.search(r"\b(?:longer|shorter)\b[^.;\n]*\bby\s*$", text[:match.start()]):
            if difference is None or Decimal(match.group(1)) != Decimal(str(difference)):
                return False
        else:
            measured.append(match.group(1))
    labeled = re.findall(r"\bruntime\s*(?:\([^)]*\))?\s*(?:[:=]|is|of)?\s*(\d+(?:\.\d+)?)", text)
    values = measured + labeled
    return bool(values) and all(Decimal(number) == Decimal(str(value)) for number in values)


def _directors(run, title):
    rows = run.initial.execute(
        "SELECT DISTINCT p.id, p.name FROM credits c JOIN persons p ON p.id=c.person_id "
        "WHERE c.title_id=? AND c.role='director'", (title["id"],)).fetchall()
    _require(bool(rows), "A required director credit is missing")
    return [dict(row) for row in rows]


def _person_mentioned(text, person):
    if mentions(text, person["name"]):
        return True
    # Surnames are a conventional short form; do not invent other aliases.
    surname = person["name"].split()[-1]
    return len(surname) > 2 and mentions(text, surname)


def _all_directors(run, text, title):
    directors = _directors(run, title)
    if not all(_person_mentioned(text, person) for person in directors):
        return False
    # Only explicit director assertions restrict additional names. Mentioning
    # another filmmaker in a comparison or a negative explanation is valid.
    people = [dict(row) for row in run.initial.execute("SELECT id, name FROM persons")]
    expected = {person["id"] for person in directors}
    clauses = re.split(r"[;\n]|(?<=[.!?])\s+", normalize(text))
    for clause in clauses:
        assertion = re.search(r"\b(?:directed by|directors?\s*(?:are|is|:|=))\s*(.*)", clause)
        if not assertion:
            continue
        names = re.split(r"\b(?:while|whereas|but|unlike|rather than|compared (?:to|with)|"
                         r"worldwide|budget|opening|rating)\b", assertion.group(1))[0]
        matches = [(match.start(), match.end(), person) for person in people
                   for match in re.finditer(r"(?<!\w)" + re.escape(normalize(person["name"])) + r"(?!\w)", names)]
        matches.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]["id"] not in expected))
        remaining, end = names, -1
        for start, stop, person in matches:
            if start < end:
                continue
            end = stop
            if person["id"] not in expected and mentions(names, person["name"]):
                return False
            # Full names own their spans: Quentin in Quentin Tarantino must
            # not be interpreted as the surname of Caroline Quentin.
            remaining = remaining[:start] + " " * (stop - start) + remaining[stop:]
        for member in re.split(r",|\band\b|&", remaining):
            member = member.strip(" .:-()")
            if not member or any(normalize(person["name"].split()[-1]) == member for person in directors):
                continue
            if re.search(r"\b(?:not|neither|isn't|rather|than|in|as|for|with|the|a|an|also|who|which|"
                         r"was|is|are|has|his|her|their|screenplay|written|produced)\b", member):
                continue
            # A plainly listed additional name is still false when that name
            # is absent from this catalog. Descriptive prose is not a name list.
            if re.fullmatch(r"[a-z][a-z.'-]*(?:\s+[a-z][a-z.'-]*){0,4}", member):
                return False
    return True


METRICS = {
    "runtime": r"\b(?:runtime|length|longer|shorter|longest|shortest)\b",
    "rating": r"\b(?:ratings?|rated|rating-wise|score)\b",
    "worldwide": r"\b(?:worldwide|global|gross|box office)\b",
}


def _comparison(answer, entities, values, metric, single_metric=False):
    """Check an explicit directional or tie statement, including winner tables.

    The routine records every recognized comparison for this metric, so an
    explicitly reversed winner cannot be rescued by a later correct sentence.
    Numeric supporting rows alone do not stand in for the requested conclusion.
    """
    expected = max(values, key=values.get)
    tied = len(set(values.values())) == 1
    source = normalize(answer)
    entities = {key: [normalize(name) for name in names] for key, names in entities.items()}
    patterns = {key: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r")(?!\w)")
                for key, names in entities.items()}

    def hits(text):
        found = [(m.start(), m.end(), key) for key, pattern in patterns.items() for m in pattern.finditer(text)]
        found.sort(key=lambda hit: (hit[0], -(hit[1] - hit[0])))
        result = []
        for hit in found:
            if not result or hit[0] >= result[-1][1]:
                result.append(hit)
        return result

    claims = []
    blocks = re.split(r"[\n;]|(?<=[.!?])\s+(?=[a-z])|,\s+(?!\d)|\b(?:while|whereas|but)\b", source)
    entity_pattern = "|".join(re.escape(name) for names in entities.values() for name in names)
    blocks = [part for block in blocks for part in re.split(r"\band\s+(?=(?:" + entity_pattern + r")\b)", block)]
    # Table cells under named entity columns become entity-bound metric lines.
    bound = entity_texts(source, entities)
    for key, block in bound.items():
        for line in block.splitlines():
            if re.search(METRICS[metric], line) and re.search(r"\b(?:winner|wins|higher|larger|longer)\b", line):
                if not hits(line):
                    blocks.append(entities[key][0] + " " + line)
    table_has_winner_header = any("|" in line and re.search(r"\b(?:winner|higher|longer|larger)\b", line)
                                  for line in source.splitlines())
    for block in blocks:
        relevant = re.search(METRICS[metric], block) is not None
        both = metric in {"rating", "worldwide"} and re.search(r"\b(?:wins? (?:on )?both|higher in both|both comparisons|wins? both categories)\b", block)
        if not relevant and not both and not single_metric:
            continue
        found = hits(block)
        negated = bool(re.search(r"\b(?:not|isn't|is not|neither)\b", block))
        tie = re.search(r"\b(?:tied?|equal|same)\b", block)
        if tie and not re.search(r"\b(?:higher|larger|longer|lower|smaller|shorter)\b", block):
            claims.append((negated, "tie"))
            continue
        comparisons = list(re.finditer(r"\b(higher|larger|longer|greater|highest|largest|longest|lower|smaller|shorter|wins?|winner|more)\b", block))
        subject = None
        for index, comparative in enumerate(comparisons):
            prefix = block[comparisons[index - 1].end() if index else 0:comparative.start()]
            suffix = block[comparative.end():comparisons[index + 1].start() if index + 1 < len(comparisons) else len(block)]
            if comparative.group() in {"highest", "largest", "longest"} and re.search(
                    r"\b(?:below|behind|lower than|smaller than|shorter than)\s+(?:the\s+)?$", prefix):
                continue
            applicable = bool(re.search(METRICS[metric], comparative.group() + suffix))
            if not applicable and not any(re.search(pattern, suffix) for pattern in METRICS.values()):
                applicable = bool(re.search(METRICS[metric], prefix))
            if not found:
                continue
            before = [hit for hit in found if hit[1] <= comparative.start()]
            after = [hit for hit in found if hit[0] >= comparative.end()]
            if comparative.group() in {"winner", "wins", "win"} and after and not before:
                subject = after[0][2]
            elif subject is None:
                subject = before[-1][2] if before else after[0][2] if after else None
            if not (applicable or both or single_metric):
                continue
            winner = subject
            if comparative.group() in {"lower", "smaller", "shorter"}:
                others = [key for key in values if key != subject]
                winner = others[0] if len(others) == 1 else None
            if winner is not None:
                claims.append((negated, winner))
        if not comparisons and table_has_winner_header and "|" in block and len({hit[2] for hit in found}) == 1:
            claims.append((negated, found[0][2]))
    expected = "tie" if tied else expected
    return any(not negative for negative, _ in claims) and all(
        (claim != expected if negative else claim == expected) for negative, claim in claims)


def _query_value(query, key, default=None, converter=str):
    values = query.get(key)
    if values is None:
        return default
    try:
        parsed = [converter(value) for value in values]
    except (ValueError, InvalidOperation):
        return object()
    if not parsed or any(value != parsed[0] for value in parsed):
        return object()
    return parsed[0]


def _advanced_query(query, genre, years=None):
    if _query_value(query, "title_type") != "movie" or _query_value(query, "sort") != "rating":
        return False
    if query.get("genre") != [genre]:
        return False
    if _query_value(query, "rating_min", converter=Decimal) != Decimal("8.5"):
        return False
    for index, key in enumerate(("year_from", "year_to")):
        if years is None:
            if query.get(key) not in (None, [""]):
                return False
        elif _query_value(query, key, converter=int) != years[index]:
            return False
    return True


def _advanced_visit(run, genre, years=None):
    return any(_advanced_query(parse_qs(urlsplit(url).query, keep_blank_values=True), genre, years)
               for url in run.visit_urls("/search/title"))


def _genre_titles(run, genre, limit=None):
    sql = ("SELECT DISTINCT t.* FROM titles t JOIN title_genre tg ON tg.title_id=t.id "
           "JOIN genres g ON g.id=tg.genre_id WHERE g.slug=? ORDER BY t.rating_avg DESC")
    if limit is not None:
        sql += " LIMIT " + str(int(limit))
    return [dict(row) for row in run.initial.execute(sql, (genre,))]


def _highest(titles):
    usable = [title for title in titles if title["rating_avg"] is not None]
    _require(bool(usable), "No rated titles satisfy the required candidate set")
    best = max(title["rating_avg"] for title in usable)
    return [title for title in usable if title["rating_avg"] == best]


def _report_year_rating(run, titles):
    texts = _task_texts(run, titles)
    for title in titles:
        text = texts[title["id"]]
        _require(text and mentions(text, title["primary_title"]), "A required movie or series title is missing")
        _require(title["year"] is not None and has_number(text, title["year"]), "A title's release/start year is missing or incorrect")
        _require(_rating(text, title["rating_avg"]), "A title's IMDb rating is missing or incorrect")


def _advanced_result_ids(run, query):
    """Evaluate the visible search result set, including its 100-row limit."""
    clauses, parameters = [], []
    first = lambda key, default="": query.get(key, [default])[0]
    if first("title_type"):
        clauses.append("t.title_type=?")
        parameters.append(first("title_type"))
    for key, column, operator, convert in (("year_from", "year", ">=", int),
                                            ("year_to", "year", "<=", int),
                                            ("rating_min", "rating_avg", ">=", float)):
        try:
            value = convert(first(key))
        except (ValueError, TypeError):
            continue
        if value:
            clauses.append(f"t.{column}{operator}?")
            parameters.append(value)
    genres = query.get("genre", [])
    if genres:
        slots = ",".join("?" for _ in genres)
        clauses.append("t.id IN (SELECT tg.title_id FROM title_genre tg JOIN genres g ON g.id=tg.genre_id "
                       f"WHERE g.slug IN ({slots}) GROUP BY tg.title_id HAVING COUNT(g.id)=?)")
        parameters.extend(genres)
        parameters.append(len(genres))
    order = {"rating": "t.rating_avg DESC", "votes": "t.num_votes DESC", "year": "t.year DESC",
             "box_office": "t.box_office_world DESC"}.get(first("sort"), "t.popularity_rank ASC NULLS LAST")
    sql = "SELECT t.id FROM titles t"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    return {row[0] for row in run.initial.execute(sql + " ORDER BY " + order + " LIMIT 100", parameters)}


def _search_result_ids(run, query):
    """Mirror the existing public title-search ranking without importing Flask."""
    stop_words = set("the a an in on at to for of and or is it by with this that from about into as be are was were".split())
    tokens = [word for word in re.split(r"\W+", query.lower()) if len(word) > 1 and word not in stop_words]
    if not tokens:
        return set()
    hits = []
    for row in run.initial.execute("SELECT * FROM titles"):
        title = dict(row)
        genres = " ".join(row[0] for row in run.initial.execute(
            "SELECT g.name FROM genres g JOIN title_genre tg ON tg.genre_id=g.id WHERE tg.title_id=?", (title["id"],)))
        people = " ".join(row[0] for row in run.initial.execute(
            "SELECT p.name FROM credits c JOIN persons p ON p.id=c.person_id WHERE c.title_id=? ORDER BY c.id LIMIT 8", (title["id"],)))
        text = " ".join((title["primary_title"], title.get("original_title") or "", str(title["year"] or ""),
                         genres, people, title.get("plot_short") or "")).lower()
        score = sum(token in text for token in tokens)
        if score:
            hits.append((score, title.get("num_votes") or 0, title["id"]))
    hits.sort(key=lambda hit: (-hit[0], -hit[1]))
    return {hit[2] for hit in hits[:50]}


def _rating_page_seen(run, title):
    if run.visited(_title_path(title)):
        return True
    if title.get("top_rank") is not None and run.visited("/chart/top" if title["title_type"] == "movie" else "/chart/toptv"):
        return True
    if run.visited("/"):
        homepage_queries = (
            "SELECT id FROM titles WHERE top_rank IS NOT NULL ORDER BY top_rank LIMIT 10",
            "SELECT id FROM titles WHERE popularity_rank IS NOT NULL ORDER BY popularity_rank LIMIT 8",
            "SELECT id FROM titles WHERE year IN (2024,2025,2026) ORDER BY year DESC, rating_avg DESC LIMIT 8",
        )
        if any(title["id"] in {row[0] for row in run.initial.execute(sql)} for sql in homepage_queries):
            return True
    for path, column, limit, descending in (("/chart/boxoffice", "box_office_us", 50, True),
                                            ("/chart/moviemeter", "popularity_rank", 100, False)):
        if run.visited(path):
            ids = {row[0] for row in run.initial.execute(
                f"SELECT id FROM titles WHERE {column} IS NOT NULL ORDER BY {column} {'DESC' if descending else 'ASC'} LIMIT ?", (limit,))}
            if title["id"] in ids:
                return True
    for event in run.events:
        path, query = event["path"].rstrip("/"), event["query"]
        if path.startswith("/genre/"):
            if any(row["id"] == title["id"] for row in _genre_titles(run, path.split("/")[-1], 60)):
                return True
        if path.startswith("/name/"):
            row = run.initial.execute("SELECT known_for_json FROM persons WHERE nm_id=?", (path.split("/")[-1],)).fetchone()
            if row:
                try:
                    known = json.loads(row[0] or "[]")
                except (ValueError, TypeError):
                    known = []
                if title["tt_id"] in known:
                    return True
        if path in {"/find", "/search"} and _query_value(query, "s", "all") in {"all", "tt"}:
            search = query.get("q", [""])[0]
            if title["id"] in _search_result_ids(run, search):
                return True
        if path == "/search/title":
            if title["id"] in _advanced_result_ids(run, query):
                return True
    return False


def _check_0(run):
    _require(run.visited("/chart/top"), "The Top 250 Movies chart was not visited")
    titles = [_one(run.initial, "SELECT * FROM titles WHERE title_type='movie' AND top_rank=?", (rank,)) for rank in (1, 3)]
    texts = _task_texts(run, titles)
    difference = abs(titles[0]["runtime_min"] - titles[1]["runtime_min"])
    for rank, title in zip((1, 3), titles):
        _require(run.visited(_title_path(title)), "A ranked movie's title information was not visited")
        text = texts[title["id"]]
        _require(_runtime(text, title["runtime_min"], difference), "A ranked movie's runtime or explicit difference is missing or incorrect")
        _require(title["mpaa_rating"] and mentions(text, title["mpaa_rating"]), "A ranked movie's MPAA classification is missing or incorrect")
        reported_ranks = re.findall(r"(?:\brank(?:ed)?\s*(?::|=|is)?\s*(?:#|no\.?\s*)?|#)\s*(\d+)\b", normalize(text))
        word_ranks = re.findall(r"\b(first|third)[- ]ranked\b", normalize(text))
        reported_ranks += [{"first": "1", "third": "3"}[word] for word in word_ranks]
        _require(all(int(value) == rank for value in reported_ranks), "A movie is bound to the wrong chart rank")
    _require(_comparison(run.answer, {t["id"]: _names(t) for t in titles},
                         {t["id"]: t["runtime_min"] for t in titles}, "runtime"), "The longer-runtime comparison is missing or incorrect")
    return ["Movie chart and both title pages visited; runtime, MPAA and comparison match"]


def _check_2(run):
    _require(run.visited("/chart/boxoffice"), "The catalog domestic box-office chart was not visited")
    title = _one(run.initial, "SELECT * FROM titles WHERE box_office_us IS NOT NULL ORDER BY box_office_us DESC LIMIT 1")
    _require(title["title_type"] == "movie", "The first catalog chart entry is not a movie")
    _require(run.visited(_title_path(title)), "The chart winner's title page was not visited")
    _require(_money(_task_texts(run, [title])[title["id"]], "budget", title["budget"], True), "The chart winner's production budget is missing or incorrect")
    return ["Catalog cumulative-domestic chart winner and title-page budget match"]


def _check_7(run):
    person = _one(run.initial, "SELECT * FROM persons WHERE name=?", ("Christopher Nolan",))
    _require(run.visited("/name/" + person["nm_id"]), "Christopher Nolan's Director filmography was not visited")
    titles = [dict(row) for row in run.initial.execute(
        "SELECT DISTINCT t.* FROM titles t JOIN credits c ON c.title_id=t.id "
        "WHERE c.person_id=? AND c.role='director' AND t.title_type='movie'", (person["id"],))]
    best = _highest(titles)
    _report_year_rating(run, best)
    catalog = [dict(row) for row in run.initial.execute("SELECT * FROM titles")]
    mentioned = _reported_titles(run.answer, catalog)
    texts = _task_texts(run, best)
    for title in mentioned:
        if title["id"] in {row["id"] for row in best}:
            continue
        text = texts[title["id"]]
        numeric_rating = re.search(r"\brating\s*(?:[:=]|is|of|at)?\s*\d|\d(?:\.\d+)?\s*/\s*10", text)
        if numeric_rating:
            _require(_rating(text, title["rating_avg"]), "An additional movie or series is assigned an incorrect rating")
        clauses = re.split(r"[;\n]|\b(?:but|while|whereas)\b", text)
        extra_winner = any(re.search(r"\b(?:tied?|highest|winner)\b", clause)
                           and not re.search(r"\b(?:not|isn't|is not|doesn't|does not)\b", clause)
                           for clause in clauses)
        _require(not extra_winner, "An extra title is incorrectly reported as a highest-rating tie")
    _require(all(_rating_page_seen(run, title) for title in best), "A winning movie's rating lacks a relevant on-site listing or detail visit")
    return ["Director filmography used; all highest-rated movie ties include title, year and rating"]


def _reported_titles(answer, titles):
    """Recognize catalog title names in answer order, resolving prefix titles."""
    text = normalize(answer)
    matches = []
    for title in titles:
        for name in _names(title):
            for match in re.finditer(r"(?<!\w)" + re.escape(normalize(name)) + r"(?!\w)", text):
                if mentions(text[max(0, match.start() - 35):match.end()], name):
                    matches.append((match.start(), match.end(), title))
    matches.sort(key=lambda match: (match[0], -(match[1] - match[0])))
    selected, last_end, ids = [], -1, set()
    for start, end, title in matches:
        if start < last_end:
            continue
        last_end = end
        if title["id"] not in ids:
            selected.append(title)
            ids.add(title["id"])
    return selected


def _no_extra_winners(run, winners):
    """Reject explicit false winners without banning discussion of losers.

    Winner-list headings apply until a blank line or another section heading.
    Individual assertions also cover ordinary highest/tied/winner wording.
    This deliberately does not try to interpret every natural-language claim.
    """
    catalog = [dict(row) for row in run.initial.execute("SELECT * FROM titles")]
    expected = {title["id"] for title in winners}
    extra = [title for title in _reported_titles(run.answer, catalog) if title["id"] not in expected]
    if not extra:
        return
    claim = r"\b(?:highest(?:[- ]rated)?|top[- ]rated|winners?|leaders?|tied?)\b"
    excluded = r"\b(?:not|isn't|is not|neither|below|lower|outside|excluded|runner-up)\b"
    texts = _task_texts(run, winners)
    for title in extra:
        clauses = re.split(r"[;\n]|\b(?:but|while|whereas)\b", normalize(texts[title["id"]]))
        _require(not any(re.search(claim, part) and not re.search(excluded, part) for part in clauses),
                 "An extra title is incorrectly reported as a highest-rating winner")
    heading = re.compile(r"^\s*[#* -]*(?:highest(?:[- ]rated)?(?: (?:matches|movies|films|titles|results))?"
                         r"|top(?:[- ]rated)? (?:movies|films|tv series|series|titles|results)"
                         r"|(?:joint )?(?:winners|leaders))\s*:")
    active = False
    for raw in run.answer.splitlines():
        line = normalize(raw)
        named = _reported_titles(line, catalog)
        if heading.match(line):
            active = True
        elif not line.strip() or (not named and line.rstrip().endswith(":")):
            active = False
        if active and not re.search(excluded, line):
            _require(all(title["id"] in expected for title in named),
                     "A highest-rating results list includes a title outside the winning set")


def _check_9(run):
    _require(_advanced_visit(run, "drama"), "Advanced search lacks the specified Movie, Drama, minimum-rating or rating-sort constraints")
    candidates = [title for title in _genre_titles(run, "drama")
                  if title["title_type"] == "movie" and title["rating_avg"] is not None and title["rating_avg"] >= 8.5]
    _require(len(candidates) >= 3, "Fewer than three titles match the task in the initial snapshot")
    catalog = [dict(row) for row in run.initial.execute("SELECT * FROM titles")]
    selected = _reported_titles(run.answer, catalog)
    _require(len(selected) == 3, "The answer must identify exactly three catalog titles")
    eligible = {title["id"] for title in candidates}
    _require(all(title["id"] in eligible for title in selected), "A reported title does not match the required filters")
    cutoff = candidates[2]["rating_avg"]
    mandatory = {title["id"] for title in candidates if title["rating_avg"] > cutoff}
    _require(mandatory <= {title["id"] for title in selected} and all(title["rating_avg"] >= cutoff for title in selected),
             "The answer omits a title above the third-place cutoff or includes a lower-rated title")
    _require([title["rating_avg"] for title in selected] == sorted((title["rating_avg"] for title in selected), reverse=True),
             "The three titles are not in descending rating order")
    return ["Specified Advanced search submitted; three titles satisfy rank order and cutoff-tie policy"]


def _check_10(run):
    _require(_advanced_visit(run, "crime", (1990, 1999)), "Advanced search lacks the specified Movie, Crime, inclusive years, minimum rating or rating-sort constraints")
    candidates = [title for title in _genre_titles(run, "crime")
                  if title["title_type"] == "movie" and title["year"] is not None and 1990 <= title["year"] <= 1999
                  and title["rating_avg"] is not None and title["rating_avg"] >= 8.5]
    best = _highest(candidates)
    _no_extra_winners(run, best)
    texts = _task_texts(run, best)
    for title in best:
        _require(run.visited(_title_path(title)), "A highest-rated result's title page containing worldwide gross was not visited")
        text = texts[title["id"]]
        _require(_all_directors(run, text, title), "A highest-rated movie's director credit is missing or incorrectly bound")
        _require(_money(text, "worldwide", title["box_office_world"], True), "A highest-rated movie's worldwide gross is missing or incorrectly bound")
    return ["All Advanced search constraints observed; all highest-rating ties bind directors and worldwide gross"]


def _check_12(run):
    _require(run.visited("/genre/crime"), "The Crime genre page was not visited")
    candidates = _genre_titles(run, "crime", 60)
    movies = _highest([title for title in candidates if title["title_type"] == "movie"])
    series = _highest([title for title in candidates if title["title_type"] == "tvSeries"])
    _no_extra_winners(run, movies + series)
    _report_year_rating(run, movies + series)
    texts = _task_texts(run, movies + series)
    for titles, pattern in ((movies, r"\b(?:movies?|films?)\b"), (series, r"\b(?:tv|television|series|shows?)\b")):
        _require(all(re.search(pattern, texts[title["id"]]) for title in titles), "The highest-rated titles are not identified as movie versus TV series")
    entities = {"movie": ["movie", "movies", "film", "films"] + [name for title in movies for name in _names(title)],
                "series": ["TV", "TV series", "television", "series", "show"] + [name for title in series for name in _names(title)]}
    # These colon labels identify winners within each already-checked group;
    # they do not assert that both groups beat the other group's top rating.
    comparison_answer = re.sub(
        r"\b(?:highest[- ]rated|top(?:[- ]rated)?)\s+(?:crime\s+)?"
        r"(?=(?:movies?|films?|tv[- ]series|television(?: series)?|series|shows?)\s*:)",
        "", normalize(run.answer))
    _require(_comparison(comparison_answer, entities, {"movie": movies[0]["rating_avg"], "series": series[0]["rating_avg"]}, "rating", single_metric=True),
             "The movie-versus-series top-rating comparison is missing or incorrect")
    return ["Crime genre visited; both type groups, complete top ties, years, ratings and group comparison match"]


def _check_14(run):
    titles = [_named_title(run, name, year) for name, year in (("The Dark Knight", 2008), ("Inception", 2010))]
    texts = _task_texts(run, titles)
    for title in titles:
        _require(run.visited(_title_path(title)), "One compared movie's title page was not visited")
        text = texts[title["id"]]
        _require(_rating(text, title["rating_avg"]), "A compared movie's rating is missing or incorrectly bound")
        _require(_money(text, "worldwide", title["box_office_world"]), "A compared movie's worldwide gross is missing or incorrectly bound")
    entities = {title["id"]: _names(title) for title in titles}
    for metric, field in (("rating", "rating_avg"), ("worldwide", "box_office_world")):
        _require(_comparison(run.answer, entities, {title["id"]: title[field] for title in titles}, metric),
                 "The " + metric + " comparison is missing or incorrect")
    return ["Both movie pages visited; ratings and worldwide grosses bind correctly and both comparisons match"]


def check_read_task(number, run):
    """Return short evidence descriptions, or raise VerificationError."""
    _require(number in READ_TASKS, "Unsupported read-only task number")
    _require(bool(run.answer.strip()), "The run has no final answer")
    run.assert_unchanged()
    try:
        result = globals()["_check_" + str(number)](run)
    except (sqlite3.Error, KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise VerificationError("The supplied snapshot or answer lacks required task data") from error
    return result + ["All business tables are unchanged"]
