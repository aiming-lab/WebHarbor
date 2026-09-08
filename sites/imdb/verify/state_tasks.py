"""Offline checks for IMDb tasks 15–17, using exact snapshot differences.

Indexed native clicks do not identify their DOM control in trajectory.json.
For those actions, a local source page, a nonfailed action, the exact database
change and a subsequent local observation are checked together. Screenshot
authenticity and the causal integrity of an evidence package remain external
review responsibilities; a success flag or answer alone never proves a write.
"""

from datetime import datetime
import re
import sqlite3
from urllib.parse import urlsplit

from answer_checks import entity_texts, has_number, mentions, normalize
from verify_lib import VerificationError


STATE_TASKS = {15, 16, 17}
FAILURE_STATES = {"failed", "error", "interrupted", "cancelled", "canceled", "pending", "started"}


def _require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def _row(db, sql, parameters):
    rows = db.execute(sql, parameters).fetchall()
    _require(len(rows) == 1, "The initial snapshot does not identify one required entity")
    return dict(rows[0])


def _user(run, email):
    return _row(run.initial, "SELECT * FROM users WHERE email=?", (email,))


def _title_path(title):
    return "/title/" + title["tt_id"]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for part in value.values():
            yield from _strings(part)
    elif isinstance(value, (list, tuple)):
        for part in value:
            yield from _strings(part)


def _params(step):
    return step.get("params") if isinstance(step.get("params"), dict) else {}


def _action_ok(step):
    """Native success=None is unknown, but can be corroborated by state/pages."""
    status = step.get("status")
    if status is not None and (not isinstance(status, str) or status in FAILURE_STATES):
        return False
    result = step.get("action_result")
    if result is not None and not isinstance(result, dict):
        return False
    result = result or {}
    if step.get("error") or result.get("error") or result.get("success") is False:
        return False
    if result.get("success") is not None and not isinstance(result["success"], bool):
        return False
    return isinstance(step.get("action_result"), dict) or status == "completed"


def _control_text(step):
    params = _params(step)
    keys = ("selector", "locator", "target", "button", "role", "name", "label")
    if normalize(step.get("action", "")) in {"click", "submit"}:
        keys += ("text",)
    return normalize(" ".join(part for key in keys for part in _strings(params.get(key))))


def _interaction(step):
    action = normalize(step.get("action", "")).replace("_", "")
    if action in {"click", "submit"}:
        return True
    if action in {"press", "presskey", "presskeys", "keypress", "key"}:
        return any(re.search(r"\b(?:enter|return)\b", normalize(text)) for text in _strings(_params(step)))
    return False


def _control_matches(run, step, operation, title=None):
    """Check explicit control descriptions; native DOM indices stay valid."""
    text = _control_text(step)
    if not text:
        return True
    for address in re.findall(r"https?://[^\s\"'\]]+", text):
        try:
            source, target = urlsplit(run.trajectory["start_url"]), urlsplit(address)
            if (target.scheme, target.hostname, target.port or 80) != (source.scheme, source.hostname, source.port or 80):
                return False
        except ValueError:
            return False
    if title:
        explicit = re.findall(r"/title/([^/\s\"'\]?]+)/(?:watchlist|rate|review)\b", text)
        if any(tt_id != title["tt_id"] for tt_id in explicit):
            return False
    if re.search(r"\b(?:cancel|add to watchlist|logout|log out|sign out)\b", text):
        return False
    action = normalize(step.get("action", ""))
    if action in {"press", "press_key", "press_keys", "keypress", "key", "submit"}:
        return True
    if re.search(r"\b(?:combobox|textbox|textarea|select)\b", text) and "button" not in text:
        return False
    if re.search(r"(?:^|\s)(?:input|a)\[", text) and not re.search(r"button|submit", text):
        return False
    patterns = {"login": r"sign in|log ?in|submit", "remove": r"remove|watchlist|submit",
                "rate": r"rate|rating|submit", "review": r"post|review|submit"}
    return bool(re.search(patterns[operation], text))


def _before_events(run):
    return {event["step_index"]: event for event in run.events if event["phase"] == "before"}


def _logout_observed(run, position, index, step):
    """A POST logout control can end a login; viewing its URL cannot."""
    control = _control_text(step)
    if not _interaction(step) or not re.search(r"\b(?:logout|log out|sign out)\b", control):
        return False
    method = normalize(_params(step).get("method", ""))
    if method and method != "post":
        return False
    if re.search(r"(?:^|\s)a\[", control):
        return False
    result = step.get("action_result") or {}
    if str(result.get("status_code", "")).startswith(("4", "5")):
        return False
    if result.get("success") is True or step.get("status") == "completed":
        return True
    # Native unknown outcomes need an observation already available at this
    # point in the trajectory; never use a page beyond the caller's boundary.
    return any(event["step_index"] < index and
               (event["step_index"] > position or
                (event["step_index"] == position and event["phase"] == "after"))
               for event in run.events)


def _login_before(run, index, email):
    before = _before_events(run)
    typed_email, active_email = None, None
    for position, step in enumerate(run.trajectory["steps"][:index]):
        event = before.get(position)
        if not event or not _action_ok(step):
            continue
        path = event["path"].rstrip("/")
        if _logout_observed(run, position, index, step):
            active_email = None
        if path != "/login":
            continue
        action = normalize(step.get("action", "")).replace("_", "")
        if action in {"input", "fill", "type", "inputtext", "fillform"}:
            emails = [match.group().lower() for text in _strings(_params(step))
                      for match in re.finditer(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text)]
            if emails:
                typed_email = emails[-1]
        if _interaction(step) and _control_matches(run, step, "login"):
            active_email = typed_email
    return active_email == email.lower()


def _after_page(run, index, paths, email=None):
    return any(event["path"].rstrip("/") in paths
               and (event["step_index"] > index or (event["step_index"] == index and event["phase"] == "after"))
               and (email is None or _login_before(run, event["step_index"] + (event["phase"] == "after"), email))
               for event in run.events)


def _recorded_fields_agree(run, index, path, expected):
    """Known form values must agree; opaque native indices are not guessed."""
    before = _before_events(run)
    values = {}
    for position, step in enumerate(run.trajectory["steps"][:index]):
        event = before.get(position)
        if not event or event["path"].rstrip("/") != path:
            values.clear()
            continue
        if not _action_ok(step):
            continue
        action = normalize(step.get("action", "")).replace("_", "")
        if action in {"navigate", "goto", "goback", "reload", "refresh"}:
            values.clear()
        if action not in {"input", "fill", "type", "inputtext", "select", "selectoption", "selectdropdownoption", "fillform"}:
            continue
        params = _params(step)
        value = params.get("value", params.get("text", params.get("values")))
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if value is None:
            continue
        control = _control_text(step)
        identified = False
        for field in expected:
            if re.search(r"\b" + field + r"\b", control) or (field == "body" and "your review" in control):
                values[field] = str(value).strip()
                identified = True
        # A native index can omit the field name while recording the actual
        # new value. A unique required value corroborates that correction.
        if not identified:
            matched = [field for field, wanted in expected.items() if str(value).strip() == str(wanted).strip()]
            if len(matched) == 1:
                values[matched[0]] = str(value).strip()
    return all(value == str(expected[field]).strip() for field, value in values.items())


def _mutation_step(run, user, title, operation, source_paths, confirm_paths, watchlist=False, fields=None):
    before = _before_events(run)
    for index, step in enumerate(run.trajectory["steps"]):
        event = before.get(index)
        if not event or event["path"].rstrip("/") not in source_paths:
            continue
        if not (_action_ok(step) and _interaction(step) and _control_matches(run, step, operation, title)):
            continue
        if not _login_before(run, index, user["email"]):
            continue
        if watchlist and not any(e["path"].rstrip("/") == "/list/watchlist" and e["step_index"] <= index
                                 and _login_before(run, e["step_index"] + (e["phase"] == "after"), user["email"])
                                 for e in run.events):
            continue
        if fields and not _recorded_fields_agree(run, index, event["path"].rstrip("/"), fields):
            continue
        if _after_page(run, index, confirm_paths, user["email"] if operation != "review" else None):
            return index
    raise VerificationError("No matching local signed-in action and subsequent confirmation page were recorded")


def _only_change(run, table):
    changes = run.diff_tables()
    _require(set(changes) == {table}, "Expected exactly one business table to change: " + table)
    change = changes[table]
    _require(not change["schema_changed"], "A business table's schema changed")
    return change


def _new_system_fields(row):
    valid_id = isinstance(row.get("id"), int) and row["id"] > 0
    try:
        datetime.fromisoformat(row.get("created_at", ""))
    except (ValueError, TypeError):
        return False
    return valid_id


def _target_text(run, title, name_optional=False, answer=None):
    """Bind continuation lines while respecting other named catalog titles."""
    answer = run.answer if answer is None else answer
    catalog = [dict(row) for row in run.initial.execute("SELECT id, primary_title FROM titles")]
    candidates = []
    source = normalize(answer)
    for row in catalog:
        name = normalize(row["primary_title"])
        for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", source):
            candidates.append((match.start(), match.end(), row))
    candidates.sort(key=lambda match: (match[0], -(match[1] - match[0])))
    named, end = {}, -1
    for start, stop, row in candidates:
        if start >= end:
            named[row["id"]] = row
            end = stop
    if not named and name_optional:
        return answer
    entities = {key: [row["primary_title"]] for key, row in named.items()}
    entities.setdefault(title["id"], [title["primary_title"]])
    lines, active = [], None
    for line in answer.splitlines():
        matches = [key for key, names in entities.items() if any(mentions(line, name) for name in names)]
        if "|" in line or not line.strip():
            active = None
        elif len(matches) == 1:
            active = matches[0]
        elif len(matches) > 1:
            active = None
        elif active is not None:
            line = entities[active][0] + ": " + line
        lines.append(line)
    return entity_texts("\n".join(lines), entities)[title["id"]]


def _confirmation(text, operation):
    text = normalize(text)
    if operation == "remove":
        invalid = r"not removed|not deleted|wasn't removed|still (?:in|on)|remains? (?:in|on)"
        positive = r"\b(?:removed|deleted|absent|no longer|not (?:in|on)|isn't (?:in|on)|does not appear)\b"
    elif operation == "rate":
        invalid = r"not (?:saved|rated|updated|confirmed)|failed|could not|couldn't"
        positive = r"\b(?:rated|saved|updated|set|confirmed|verified|shows?|displayed|appears?)\b"
    else:
        invalid = r"not (?:visible|posted|submitted|listed|shown)|does not appear|doesn't appear|failed|could not|couldn't"
        positive = r"\b(?:visible|appears?|listed|shown|confirmed|verified|present)\b"
    return not re.search(invalid, text) and bool(re.search(positive, text))


def _rating_answer(text, expected, required):
    text = normalize(text)
    text = re.sub(r"\b(?:imdb|global)\s+rating\s*(?:is|of|:)?\s*\d+(?:\.\d+)?(?:\s*/\s*10)?", "", text)
    reported = re.findall(r"(?<!\d)(\d+(?:\.\d+)?)\s*/\s*10\b|\brating\s*(?:is|of|:)?\s*(\d+(?:\.\d+)?)", text)
    return (not required or has_number(text, expected)) and all(float(left or right) == expected for left, right in reported)


def _personal_rating_answer(text, previous, expected=8):
    """Check Task 16's explicit old values separately from its saved value."""
    text = normalize(text)
    score = r"(?P<score>\d+(?:\.\d+)?)(?:\s*/\s*10\b)?(?!\w|\.\d|\s*/\s*\d)"
    text = re.sub(r"\b(?:imdb|global)\s+rating\s*(?:is|of|:)?\s*\d+(?:\.\d+)?(?:\s*/\s*10)?", "", text)
    historical = (
        r"\bfrom\s+",
        r"\b(?:it\s+)?was\s+",
        r"\b(?:previously|originally|initially)\s+(?:rated\s+)?",
        r"\b(?:previous|prior|old|initial)\s+(?:personal\s+)?rating\s*(?:(?:was|of|is)\s+|[:=]\s*)?",
    )
    for prefix in historical:
        matches = []
        pattern = prefix + score
        if prefix == historical[0]:
            pattern += r"(?=\s+to\s+\d)"
        for match in re.finditer(pattern, text):
            clause = re.split(r"[.;,\n(]|\b(?:and|but)\b", text[:match.start()])[-1]
            if prefix == historical[1] and re.search(r"\b(?:current|now|currently|saved|new)\b", clause):
                continue
            matches.append(match)
        if any(previous is None or float(match["score"]) != previous for match in matches):
            return False
        for match in reversed(matches):
            text = text[:match.start()] + " " + text[match.end():]

    # A selection condition is not a claim that the new rating has been saved.
    # A negated *current* rating, however, directly contradicts the result.
    eligibility = r"\b(?:other than|not)\s+" + score
    for match in re.finditer(eligibility, text):
        preceding = re.split(r"[.;\n]", text[:match.start()])[-1]
        if (float(match["score"]) != expected or previous == expected
                or re.search(r"\b(?:now|currently|saved|new)\b", preceding)):
            return False
    text = re.sub(eligibility, " ", text)

    # Read both /10 notation and ordinary numeric update clauses. History was
    # checked against the initial snapshot above, rather than silently ignored.
    current = [float(match[1]) for match in re.finditer(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*/\s*10\b", text)]
    labels = (r"\b(?:rating|rated|now|currently|to|shows?)\s*"
              r"(?:(?:is|of|was|now|currently|at|to)\s+|[:=]\s*)?")
    current.extend(float(match["score"]) for match in re.finditer(labels + score, text))
    return bool(current) and all(value == expected for value in current)


def _personal_rating_text(run, title):
    # Normalize only unambiguous update/year phrases before entity binding.
    # Otherwise the catalog series "From" can split a numeric rating change.
    score = r"\d+(?:\.\d+)?(?:\s*/\s*10\b)?"
    transition = r"\bfrom\s+(" + score + r")\s+to\s+(" + score + r")(?!\w|\.\d|\s*/\s*\d)"
    answer = re.sub(transition, r"previously \1; now \2", run.answer, flags=re.I)
    if normalize(title["primary_title"]) != "from":
        year = r"\bfrom\s+" + re.escape(str(title["year"])) + r"\b"
        answer = re.sub(year, "released in " + str(title["year"]), answer, flags=re.I)
    return _target_text(run, title, answer=answer)


def _watchlist_titles(run, user):
    return [dict(row) for row in run.initial.execute(
        "SELECT t.* FROM titles t JOIN watchlist_items w ON w.title_id=t.id WHERE w.user_id=?", (user["id"],))]


def _genres(run, title):
    return {row[0] for row in run.initial.execute(
        "SELECT g.slug FROM genres g JOIN title_genre tg ON tg.genre_id=g.id WHERE tg.title_id=?", (title["id"],))}


def _check_15(run):
    user = _user(run, "bob.c@test.com")
    candidates = [title for title in _watchlist_titles(run, user) if title["title_type"] == "tvSeries"
                  and title["year"] is not None and _genres(run, title) & {"sci-fi", "fantasy"}]
    _require(bool(candidates), "Bob has no qualifying series in the initial Watchlist")
    title = min(candidates, key=lambda item: (item["year"], item["primary_title"].casefold()))
    original = _row(run.initial, "SELECT * FROM watchlist_items WHERE user_id=? AND title_id=?", (user["id"], title["id"]))
    change = _only_change(run, "watchlist_items")
    _require(change["before"] == [original] and change["after"] == [], "The Watchlist delta is not exactly the selected Bob entry's deletion")
    pages = {"/list/watchlist", _title_path(title)}
    _mutation_step(run, user, title, "remove", pages, pages, watchlist=True)
    text = _target_text(run, title)
    _require(text and has_number(text, title["year"]), "The removed title or its start year is missing or incorrect")
    genres = _genres(run, title)
    aliases = {"sci-fi": ("sci-fi", "sci fi", "science fiction", "science-fiction", "scifi"), "fantasy": ("fantasy",)}
    for genre, names in aliases.items():
        stated = any(mentions(text, name) for name in names)
        _require(stated == (genre in genres), "The removed series' qualifying genres are missing or incorrect")
    _require(_confirmation(text, "remove"), "The answer does not confirm the selected series is absent")
    return ["Bob's initial Watchlist rule selects the deleted series; exactly that entry was removed",
            "Local removal and subsequent confirmation observed; title, year and qualifying genres match"]


def _check_16(run):
    user = _user(run, "carol.d@test.com")
    ratings = {row["title_id"]: dict(row) for row in run.initial.execute("SELECT * FROM user_ratings WHERE user_id=?", (user["id"],))}
    candidates = [title for title in _watchlist_titles(run, user) if title["title_type"] == "movie"
                  and title["year"] is not None and "crime" in _genres(run, title)
                  and ratings.get(title["id"], {}).get("rating") != 8]
    _require(bool(candidates), "Carol has no qualifying movie in the initial Watchlist")
    title = min(candidates, key=lambda item: (-item["year"], item["primary_title"].casefold()))
    old = ratings.get(title["id"])
    change = _only_change(run, "user_ratings")
    if old:
        expected = dict(old, rating=8)
        _require(change["before"] == [old] and change["after"] == [expected], "The rating update must change only the selected row's rating, preserving its ID and timestamp")
    else:
        _require(not change["before"] and len(change["after"]) == 1, "Expected one new personal rating and no deleted ratings")
        row = change["after"][0]
        _require(set(row) == {"id", "user_id", "title_id", "rating", "created_at"}
                 and row["user_id"] == user["id"] and row["title_id"] == title["id"] and row["rating"] == 8
                 and _new_system_fields(row), "The inserted personal rating has incorrect fields")
    _mutation_step(run, user, title, "rate", {_title_path(title)}, {"/list/ratings"}, watchlist=True, fields={"rating": 8})
    text = _personal_rating_text(run, title)
    _require(text and has_number(text, title["year"])
             and _personal_rating_answer(text, old.get("rating") if old else None),
             "The rated title, release year, previous rating or personal 8/10 result is missing or incorrect")
    _require(_confirmation(text, "rate"), "The answer does not confirm the personal-rating result")
    return ["Carol's initial eligible Watchlist selects the rated movie; only its personal rating changed to 8",
            "Local rating action followed by My ratings observed; reported title and year match"]


def _reported_review_headlines(text, title_name):
    text = normalize(text).translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    headlines = re.findall(r"\b(?:headline|review(?: titled| called)?)\s*(?:is|:)?\s*[\"']([^\"']+)[\"']", text)
    # A rating label or the named movie can start a separate clause. Arbitrary
    # words after a conjunction, comma or parenthesis remain part of the value.
    metadata = (r"(?:,\s*(?:and\s+)?|\s+(?:and|with)\s+)"
                r"(?=(?:(?:a|the|my|review)\s+)?rating\b|rated\b|"
                r"(?:(?:the|my|new)\s+)*review\s+(?:is|was|appears|appeared)\b)"
                r"|\s*\((?=\d+(?:\.\d+)?\s*/\s*10\s*\))"
                r"|\s+(?:for|on)\s+(?=" + re.escape(normalize(title_name)) + r"\b)")
    for match in re.finditer(r"\bheadline\s*(?P<introducer>is\s+|[:=]\s*)?(?P<value>[^.;\n|]+)", text):
        reported = match.group("value").strip()
        # "The headline and 10/10 rating displayed" refers to an existing field.
        # Explicit values such as "Headline: and beyond" must still be checked.
        if not match.group("introducer") and re.match(r"(?:and|with|for|on)\b", reported):
            continue
        quoted = re.match(r"[\"']([^\"']+)[\"']", reported)
        reported = quoted.group(1) if quoted else re.split(metadata, reported, maxsplit=1)[0]
        reported = reported.strip(" \"'“”")
        if reported not in {"as requested", "correct", "unchanged", "exactly as requested"}:
            headlines.append(reported)
    return headlines


def _check_17(run):
    user = _user(run, "alice.j@test.com")
    title = _row(run.initial, "SELECT * FROM titles WHERE primary_title=? AND year=?", ("Interstellar", 2014))
    change = _only_change(run, "reviews")
    _require(not change["before"] and len(change["after"]) == 1, "Expected exactly one new review, without modifying old reviews")
    review = change["after"][0]
    _require(set(review) == {"id", "title_id", "user_id", "rating", "headline", "body", "helpful_count", "created_at", "is_seed"}, "The new review has unexpected fields")
    _require(review["user_id"] == user["id"] and review["title_id"] == title["id"]
             and review["headline"] == "Brilliant sci-fi epic" and review["rating"] == 10
             and isinstance(review["body"], str) and bool(review["body"].strip())
             and review["helpful_count"] == 0 and review["is_seed"] == 0 and _new_system_fields(review),
             "The new review does not match the required author, movie, headline, rating or review fields")
    _mutation_step(run, user, title, "review", {_title_path(title) + "/review"}, {_title_path(title) + "/reviews"},
                   fields={"rating": 10, "headline": review["headline"], "body": review["body"]})
    text = _target_text(run, title, name_optional=True)
    _require(text and _confirmation(text, "review"), "The answer does not confirm the new review appears")
    _require(_rating_answer(text, 10, False), "The answer reports a different review rating")
    headlines = _reported_review_headlines(text, title["primary_title"])
    _require(all(headline == "brilliant sci-fi epic" for headline in headlines), "The answer reports a different review headline")
    return ["Exactly one new Alice review matches the required Interstellar headline, rating and nonempty body",
            "Local review submission followed by that movie's reviews page observed; no other business table changed"]


def check_state_task(number, run):
    """Return concise evidence strings, or raise VerificationError."""
    _require(number in STATE_TASKS, "Unsupported state task number")
    _require(isinstance(run.answer, str) and bool(run.answer.strip()), "The run has no final answer")
    try:
        return {15: _check_15, 16: _check_16, 17: _check_17}[number](run)
    except (sqlite3.Error, KeyError, TypeError, ValueError) as error:
        raise VerificationError("The supplied snapshots or trajectory lack required state-task data") from error
