"""Offline grading for tasks 24–27; no live DB, network or app imports.

URL/control evidence corroborates the exact snapshot delta. It cannot replace
external review of screenshot authenticity or prove unrecorded transient writes.
"""
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import hmac
import re
import sqlite3

from answer_checks import has_number, mentions, normalize
from read_tasks import _task_texts, _runtime
from state_tasks import (_action_ok, _control_text, _interaction, _locator_nodes,
                         _params, _recorded_fields_agree, _reported_review_headlines)
from verify_lib import VerificationError, _local_url


STATE_TASKS = {24, 25, 26, 27}
PASSWORD = "TestPass123!"
NEW_EMAIL = "weekend.viewer@test.com"


def _require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def verify_password(encoded, password):
    """Verify bounded Werkzeug scrypt/PBKDF2 encodings, never plaintext.

    The current app produces scrypt:32768:8:1 with a 64-byte digest. PBKDF2
    sha256/sha512 support also covers ordinary Werkzeug historical encodings.
    Explicit memory/work limits keep malicious evidence from exhausting a judge.
    """
    if not isinstance(encoded, str) or not isinstance(password, str):
        return False
    try:
        password_size = len(password.encode("utf-8"))
    except UnicodeError:
        return False
    if len(encoded) > 512 or password_size > 4096:
        return False
    return _verify_password(encoded, password)


def _submitted_password_matches(user, recorded):
    """Accept the recorder's exact safe placeholder when the snapshot agrees.

    Authentication still requires a successful same-origin transition away
    from the login/register page.  For a redacted field, validate the account's
    stored hash against the task-supplied password instead of treating the
    placeholder itself as a credential.
    """
    if verify_password(user["password_hash"], recorded):
        return True
    return (recorded in {"[SUPPLIED PASSWORD]", "[REDACTED]"}
            and verify_password(user["password_hash"], PASSWORD))


@lru_cache(maxsize=64)
def _verify_password(encoded, password):
    try:
        method, salt, digest = encoded.split("$")
        if not re.fullmatch(r"[A-Za-z0-9]{1,64}", salt):
            return False
        if not re.fullmatch(r"[0-9a-f]+", digest):
            return False
        parameters = method.split(":")
        if parameters[0] == "scrypt" and len(parameters) == 4:
            n, r, p = map(int, parameters[1:])
            if (n < 2 or n & (n - 1) or n > 32768 or not 1 <= r <= 8
                    or not 1 <= p <= 4 or n * r * p > 1048576 or len(digest) != 128):
                return False
            actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=n, r=r, p=p,
                                    dklen=64, maxmem=64 * 1024 * 1024).hex()
        elif parameters[0] == "pbkdf2" and len(parameters) == 3:
            algorithm, iterations = parameters[1], int(parameters[2])
            if algorithm not in {"sha256", "sha512"} or not 1 <= iterations <= 2000000:
                return False
            if len(digest) != {"sha256": 64, "sha512": 128}[algorithm]:
                return False
            actual = hashlib.pbkdf2_hmac(algorithm, password.encode(), salt.encode(), iterations).hex()
        else:
            return False
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError, OverflowError, MemoryError):
        return False


def _observed_destination(run, index):
    """Only this action's valid after URL or the immediate next before URL."""
    raw = run.trajectory["steps"][index].get("url_after")
    if raw is not None:
        parsed = _local_url(raw)
        if not parsed or parsed[1] != run._origin:
            return None
    for phase, position in (("after", index), ("before", index + 1)):
        events = [e for e in run.events if e["step_index"] == position and e["phase"] == phase]
        if events:
            return events[0]["path"].rstrip("/") or "/"
    return None


def _form_values(run, index, path):
    values = {}
    for step in run.trajectory["steps"][:index]:
        parsed = _local_url(step.get("url"))
        if not parsed or parsed[1] != run._origin or parsed[0].path.rstrip("/") != path:
            values.clear()
            continue
        if not _action_ok(step):
            continue
        action = normalize(step.get("action", "")).replace("_", "")
        if action in {"goto", "navigate", "reload", "refresh", "goback"}:
            values.clear()
        if action not in {"fill", "input", "type", "inputtext", "select", "selectoption", "fillform"}:
            continue
        params = _params(step)
        value = params.get("value", params.get("text", params.get("values")))
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if not isinstance(value, str):
            continue
        control = _control_text(step)
        field = next((f for f in ("email", "password", "name")
                      if re.search(r"\b" + f + r"\b", control)), None)
        # Native DOM indices may omit field labels; recognize only these direct
        # input values, never arbitrary recursive metadata or locator ancestors.
        if field is None:
            if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()):
                field = "email"
            elif value == PASSWORD:
                field = "password"
            elif value == "Weekend Viewer":
                field = "name"
        if field:
            values[field] = value if field == "password" else value.strip()
    if "email" in values:
        values["email"] = values["email"].lower()
    return values


def _control(run, step, operation, title=None):
    if not _action_ok(step) or not _interaction(step):
        return False
    result = step.get("action_result") or {}
    if str(result.get("status_code", "")).startswith(("4", "5")):
        return False
    nodes = list(_locator_nodes(step))
    text = _control_text(step, include_ancestors=True)
    for address in re.findall(r"https?://[^\s\"'\]]+", text):
        parsed = _local_url(address)
        if not parsed or parsed[1] != run._origin:
            return False
    if title:
        for node in nodes:
            if "has_link" in node and normalize(node["has_link"]) != normalize(title["primary_title"]):
                return False
        for tt_id, endpoint in re.findall(r"/title/([^/\s\"'\]?]+)/(watchlist|rate|review)\b", text):
            if tt_id != title["tt_id"] or endpoint != ("watchlist" if operation == "add" else operation):
                return False
    leaf = _control_text(step)
    if re.search(r"\b(cancel|remove|delete|details)\b", leaf) or "−" in leaf:
        return False
    if operation == "logout":
        if normalize(_params(step).get("method", "post")) != "post":
            return False
    elif re.search(r"\blog\s*out\b|\bsign out\b", leaf):
        return False
    if not leaf:
        if operation == "logout":
            return False
        index = nodes[-1].get("index")
        return type(index) is int and index >= 0
    if normalize(nodes[-1].get("role", "")) == "link" or re.match(r"a\[", leaf):
        return False
    patterns = {"add": r"add to watchlist|\+\s*watchlist|\bwatchlist\b",
                "rate": r"\brate\b|\brating\b", "login": r"sign in|log ?in",
                "register": r"create (?:your )?(?:imdb )?account|register|sign up",
                "logout": r"log ?out|sign out"}
    if re.search(patterns[operation], leaf):
        if operation == "add" and re.search(r"(?:^|\s)-\s*watchlist", leaf):
            return False
        return True
    if operation == "logout":
        # A generic submit (including a rating save) is never a logout.
        return False
    # Form submit and Enter are valid without a human-readable button label.
    return (normalize(step.get("action", "")) in {"submit", "press", "presskey", "press_key", "keypress"}
            or bool(re.search(r"button\[type=.?(?:submit)", leaf)))


class _Authentication:
    def __init__(self, run):
        self.before, self.after, self.transitions = [], [], []
        users = {row["email"].lower(): dict(row) for row in run.initial.execute("SELECT * FROM users")}
        initial_emails = set(users)
        after_users = {row["email"].lower(): dict(row) for row in run.after.execute("SELECT * FROM users")}
        active = None
        before_events = {e["step_index"]: e for e in run.events if e["phase"] == "before"}
        for i, step in enumerate(run.trajectory["steps"]):
            self.before.append(active)
            event = before_events.get(i)
            destination = _observed_destination(run, i)
            if event and destination and _action_ok(step):
                path = event["path"].rstrip("/")
                logout = _control(run, step, "logout") or _opaque_logout(run, i)
                if active and logout and destination in {"/", "/login"}:
                    self.transitions.append((i, "logout", active))
                    active = None
                elif active is None and path in {"/login", "/register"} and destination not in {"/login", "/register", "/logout"}:
                    operation = "login" if path == "/login" else "register"
                    if _control(run, step, operation):
                        fields = _form_values(run, i, path)
                        email = fields.get("email")
                        user = users.get(email) if operation == "login" else after_users.get(email)
                        if (operation == "register" and (email in initial_emails or not user
                                or fields.get("name") != user["name"])):
                            user = None
                        if user and _submitted_password_matches(user, fields.get("password")):
                            if operation == "register":
                                users[email] = user
                            active = email
                            self.transitions.append((i, operation, email))
            self.after.append(active)

    def owner(self, event):
        return (self.before if event["phase"] == "before" else self.after)[event["step_index"]]


def _opaque_logout(run, index):
    """Corroborate an indexed logout through the app's guarded auth forms.

    A numeric click alone is insufficient. It must leave for home and the next
    distinct observed route must be login/register, which this app will not
    render for an authenticated user. Known GET/HEAD and error outcomes fail.
    This remains dependent on authentic page observations, like indexed writes.
    """
    step = run.trajectory["steps"][index]
    leaf = list(_locator_nodes(step))[-1]
    ancestors = _control_text(step, include_ancestors=True)
    for address in re.findall(r"https?://[^\s\"'\]]+", ancestors):
        parsed = _local_url(address)
        if not parsed or parsed[1] != run._origin:
            return False
    for target in re.findall(r"action=[\"']([^\"']+)", ancestors):
        if target != "/logout" and not (target.startswith("http://") and _local_url(target)
                                        and _local_url(target)[0].path == "/logout"):
            return False
    if (_control_text(step) or type(leaf.get("index")) is not int or leaf["index"] < 0
            or not _action_ok(step) or not _interaction(step)
            or normalize(_params(step).get("method", "post")) != "post"
            or str((step.get("action_result") or {}).get("status_code", "")).startswith(("4", "5"))
            or _observed_destination(run, index) not in {"/", "/login", "/register"}):
        return False
    for event in run.events:
        if event["step_index"] <= index:
            continue
        path = event["path"].rstrip("/") or "/"
        if path != "/":
            return path in {"/login", "/register"}
    return False


def _authentication(run):
    if not hasattr(run, "_expansion_authentication"):
        run._expansion_authentication = _Authentication(run)
    return run._expansion_authentication


def authenticated_before(run, position, email):
    """Identity after steps[:position]; an after event uses step_index + 1."""
    if not isinstance(position, int) or not 0 <= position <= len(run.trajectory["steps"]):
        return False
    auth = _authentication(run)
    return position > 0 and auth.after[position - 1] == email.lower()


def _pages(run, email, paths, before=None, after=None):
    auth = _authentication(run)
    return [e for e in run.events if e["path"].rstrip("/") in paths
            and (email is None or auth.owner(e) == email)
            and (before is None or 2 * e["step_index"] + (e["phase"] == "after") < 2 * before)
            and (after is None or 2 * e["step_index"] + (e["phase"] == "after") > 2 * after)]


def _rows(db, sql, parameters=()):
    return [dict(r) for r in db.execute(sql, parameters)]


def _user(run, email):
    users = _rows(run.initial, "SELECT * FROM users WHERE email=?", (email,))
    _require(len(users) == 1, "Initial snapshot does not identify the required user")
    return users[0]


def _title_path(title):
    return "/title/" + title["tt_id"]


def _schema(db):
    return sorted(tuple(r) for r in db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


def _insertions(run, expected):
    _require(_schema(run.initial) == _schema(run.after), "Business schema or indexes changed")
    changes = run.diff_tables()
    wanted = {table for table, rows in expected.items() if rows}
    _require(set(changes) == wanted, "Database changed outside the exact allowed insertion set")
    for table, specifications in expected.items():
        if not specifications:
            continue
        change = changes[table]
        _require(not change["schema_changed"] and not change["before"], "Existing business rows changed or disappeared")
        timestamp = "added_at" if table == "watchlist_items" else "created_at"
        supplied = []
        for row in change["after"]:
            _require(type(row.get("id")) is int and row["id"] > 0, "Invalid new row identity")
            try:
                datetime.fromisoformat(row[timestamp])
            except (ValueError, TypeError, KeyError):
                raise VerificationError("Invalid new row timestamp") from None
            expected_fields = set(specifications[0]) | {"id", timestamp}
            _require(set(row) == expected_fields, "Unexpected fields in a new row")
            supplied.append(tuple(sorted((key, row[key]) for key in specifications[0])))
        wanted_rows = [tuple(sorted(row.items())) for row in specifications]
        _require(Counter(supplied) == Counter(wanted_rows), "New rows do not match the required complete user/title/value set")


def _write(run, user, title, operation, used=None):
    auth = _authentication(run)
    used = used if used is not None else set()
    for event in run.events:
        i = event["step_index"]
        path = event["path"].rstrip("/")
        if event["phase"] != "before" or i in used or auth.before[i] != user["email"]:
            continue
        if path != _title_path(title) and not (operation == "add" and path in {
                "/chart/top", "/chart/toptv", "/chart/moviemeter", "/chart/boxoffice"}):
            continue
        step = run.trajectory["steps"][i]
        if not _control(run, step, operation, title):
            continue
        if not _pages(run, user["email"], {"/list/watchlist" if operation == "add" else "/list/ratings"}, after=i):
            continue
        used.add(i)
        return i
    raise VerificationError("Missing local authenticated action and subsequent owned-list confirmation")


def _answer_texts(run, titles):
    # Preserve common category prefixes before the next entity; use the existing
    # calibrated title/table bindings for the remaining prose and continuations.
    answer = re.sub(r"\b((?:was|is|were)(?:\s+also)?\s+)already saved\b(?!\s*\(\d{4}\))",
                    r"\1already present", run.answer, flags=re.I)
    answer = answer.replace("，", ", ").replace("。", "\n")
    answer = re.sub(r"(\d+(?:\.\d+)?)\s*分钟", r"\1 minutes", answer)
    answer = re.sub(r";\s*|(?=\b(?:Already saved|Already present|Added|Existing)\s*:)", "\n", answer)
    class AnswerView:
        pass
    view = AnswerView()
    view.initial, view.answer = run.initial, answer
    return _task_texts(view, titles)


def _report(run, titles, runtime=False):
    _require(bool(run.answer.strip()), "The answer is empty")
    texts = _answer_texts(run, titles)
    for title in titles:
        text = texts[title["id"]]
        _require(text and has_number(text, title["year"]), "The answer omits or misbinds a required title/year")
        if runtime:
            _require(_runtime(text, title["runtime_min"]), "The answer omits or misstates a runtime")
    return texts


def _watchlist_ids(run, user):
    return {r[0] for r in run.initial.execute("SELECT title_id FROM watchlist_items WHERE user_id=?", (user["id"],))}


def _watchlist_movies(run, user):
    return _rows(run.initial, "SELECT t.* FROM titles t JOIN watchlist_items w ON w.title_id=t.id "
                 "WHERE w.user_id=? AND t.title_type='movie'", (user["id"],))


def _saved_rows(user, titles):
    return [{"user_id": user["id"], "title_id": t["id"]} for t in titles]


def _filtered_search(run):
    for event in run.events:
        if event["path"].rstrip("/") != "/search/title":
            continue
        query = event["query"]
        try:
            correct = query.get("title_type") == ["movie"] and query.get("genre") == ["sci-fi"]
            correct &= all(query.get(key) and all(convert(v) == wanted for v in query[key])
                           for key, wanted, convert in (("year_from", 1960, int), ("year_to", 1989, int),
                                                        ("rating_min", Decimal(8), Decimal)))
            if correct:
                return True
        except (InvalidOperation, ValueError):
            pass
    return False


def _type_evidence(run, title, before):
    if _pages(run, None, {_title_path(title)}, before=before):
        return True
    chart = "/chart/top" if title["title_type"] == "movie" else "/chart/toptv"
    if title.get("top_rank") is not None and _pages(run, None, {chart}, before=before):
        return True
    # Confirm that this title is actually in a type-filtered result set, not
    # merely that some unrelated Movie query was opened.
    genres = {}
    for row in run.initial.execute("SELECT tg.title_id,g.slug FROM title_genre tg JOIN genres g ON g.id=tg.genre_id"):
        genres.setdefault(row[0], set()).add(row[1])
    catalog = _rows(run.initial, "SELECT * FROM titles WHERE title_type=?", (title["title_type"],))
    for event in _pages(run, None, {"/search/title"}, before=before):
        q = event["query"]
        if q.get("title_type") != [title["title_type"]]:
            continue
        try:
            if any(len(set(q.get(key, []))) > 1 for key in ("year_from", "year_to", "rating_min", "sort")):
                continue
            lo, hi = [int(q.get(key, [""])[0]) if q.get(key, [""])[0] else None
                      for key in ("year_from", "year_to")]
            minimum = Decimal(q.get("rating_min", ["0"])[0] or "0")
            if not minimum.is_finite() or any(v is not None and not 1 <= v <= 9999 for v in (lo, hi)):
                continue
            wanted_genres = q.get("genre", [])
            if len(set(wanted_genres)) != len(wanted_genres):
                continue
            matches = [t for t in catalog if (lo is None or t["year"] is not None and t["year"] >= lo)
                       and (hi is None or t["year"] is not None and t["year"] <= hi)
                       and (not minimum or t["rating_avg"] is not None and Decimal(str(t["rating_avg"])) >= minimum)
                       and set(wanted_genres) <= genres.get(t["id"], set())]
            sort = q.get("sort", ["popularity"])[0]
            field = {"rating": "rating_avg", "votes": "num_votes", "year": "year", "box_office": "box_office_world"}.get(sort)
            if field:
                matches.sort(key=lambda t: (t.get(field) is not None, t.get(field) or 0), reverse=True)
            else:
                matches.sort(key=lambda t: (t.get("popularity_rank") is None, t.get("popularity_rank") or 0))
            if title["id"] in {t["id"] for t in matches[:100]}:
                return True
        except (ValueError, TypeError, InvalidOperation):
            continue
    return False


def _check24(run):
    user = _user(run, "david.k@test.com")
    titles = _rows(run.initial, "SELECT DISTINCT t.* FROM titles t JOIN title_genre tg ON tg.title_id=t.id "
                   "JOIN genres g ON g.id=tg.genre_id WHERE t.title_type='movie' AND g.slug='sci-fi' "
                   "AND t.year BETWEEN 1960 AND 1989 AND t.rating_avg>=8 AND t.runtime_min<=120")
    titles = [t for t in titles if t["id"] not in _watchlist_ids(run, user)]
    _require(titles, "Initial catalog has no missing qualifying movies")
    _require(_filtered_search(run), "Required Advanced search constraints were not observed")
    _insertions(run, {"watchlist_items": _saved_rows(user, titles)})
    used = set()
    first = min(_write(run, user, t, "add", used) for t in titles)
    _require(_pages(run, user["email"], {"/list/watchlist"}, before=first), "Missing initial David Watchlist evidence")
    _report(run, titles, runtime=True)
    return ["Complete filtered movie set added to David's Watchlist; existing rows and other tables preserved"]


def _check25(run):
    bob, david = _user(run, "bob.c@test.com"), _user(run, "david.k@test.com")
    rated = _rows(run.initial, "SELECT t.* FROM titles t JOIN user_ratings r ON r.title_id=t.id "
                  "WHERE r.user_id=? AND r.rating=10", (bob["id"],))
    movies = [t for t in rated if t["title_type"] == "movie"]
    saved = _watchlist_ids(run, david)
    added, existing = [t for t in movies if t["id"] not in saved], [t for t in movies if t["id"] in saved]
    _require(added, "Initial data has no missing recommendations")
    _insertions(run, {"watchlist_items": _saved_rows(david, added)})
    used = set()
    first = min(_write(run, david, t, "add", used) for t in added)
    _require(_pages(run, bob["email"], {"/list/ratings"}, before=first), "Bob's personal-rating source was not observed")
    _require(_pages(run, david["email"], {"/list/watchlist"}, before=first), "David's initial Watchlist was not observed")
    # Title types can also be distinguished through type-filtered search or
    # movie/TV charts. No universal detail-page detour is imposed.
    for title in rated:
        _require(_type_evidence(run, title, first), "Missing on-site movie versus TV type evidence")
    texts = _report(run, movies)
    for title in added:
        text = texts[title["id"]]
        contradictory = re.search(r"\b(?:was |is |were )?already (?:saved|present|in)\b|\bexisting (?:entry|item|recommendation)\b", text)
        if contradictory:
            prefix = text[max(0, contradictory.start() - 15):contradictory.start()]
            _require(re.search(r"\b(?:not|wasn't|isn't)\s*$", prefix),
                     "The answer labels a newly added recommendation as already present")
    for title in existing:
        text = texts[title["id"]]
        # Remove the title itself before looking for status: a title may happen
        # to contain 'Already Saved', as in the adversarial synthetic fixture.
        name = re.escape(normalize(title["primary_title"]))
        text = re.sub(name + r"(?=\s*(?:\(\d{4}\)|\|))", " ", text)
        _require(re.search(r"\balready\b|\b(?:existing|kept|unchanged|previously saved)\b", text),
                 "The answer does not identify the already-saved recommendation")
        _require(not re.search(r"\bnewly (?:added|saved)\b", text), "The answer says an existing recommendation was newly saved")
        for claim in re.finditer(r"\b(?:added|saved|copied)\s+(?:it\s+)?again\b|\bre-?added\b", text):
            prefix = text[max(0, claim.start() - 25):claim.start()]
            _require(re.search(r"\b(?:not|never|didn't|did not|wasn't|was not)\s*$", prefix),
                     "The answer says an existing recommendation was added again")
    return ["Bob's movie recommendations deduplicated into David's owned Watchlist; source state preserved"]


def _check26(run):
    alice = _user(run, "alice.j@test.com")
    rated = {r[0] for r in run.initial.execute("SELECT title_id FROM user_ratings WHERE user_id=?", (alice["id"],))}
    titles = [t for t in _watchlist_movies(run, alice) if t["id"] not in rated]
    _require(titles, "Initial source queue is empty")
    _require(not run.initial.execute("SELECT 1 FROM users WHERE email=?", (NEW_EMAIL,)).fetchone(), "New account already existed initially")
    users = _rows(run.after, "SELECT * FROM users WHERE email=?", (NEW_EMAIL,))
    _require(len(users) == 1, "The requested new account was not created exactly once")
    user = users[0]
    _require(user["name"] == "Weekend Viewer" and verify_password(user["password_hash"], PASSWORD),
             "New account name or working credentials do not match")
    _insertions(run, {"users": [{k: user[k] for k in ("email", "name", "password_hash")}],
                      "watchlist_items": _saved_rows(user, titles)})
    auth = _authentication(run)
    registrations = [i for i, op, email in auth.transitions if op == "register" and email == NEW_EMAIL]
    _require(len(registrations) == 1, "Missing successful registration provenance")
    registered = registrations[0]
    for path in ("/list/watchlist", "/list/ratings"):
        _require(_pages(run, alice["email"], {path}, before=registered), "Missing Alice source-set evidence")
    used = set()
    for title in titles:
        _require(_write(run, user, title, "add", used) > registered, "Save predates new-account registration")
    relogins = [i for i, op, email in auth.transitions if op == "login" and email == NEW_EMAIL and i > registered
                and any(max(used) < j < i and action == "logout" and owner == NEW_EMAIL
                        for j, action, owner in auth.transitions)]
    _require(any(_pages(run, NEW_EMAIL, {"/list/watchlist"}, after=max(i, max(used))) for i in relogins),
             "Missing real new-account logout/relogin and final owned Watchlist confirmation")
    _report(run, titles)
    return ["One new account has valid requested credentials and exactly the source-derived queue; reauthentication observed"]


def _check27(run):
    alice = _user(run, "alice.j@test.com")
    ratings = {r[0] for r in run.initial.execute("SELECT title_id FROM user_ratings WHERE user_id=?", (alice["id"],))}
    candidates = []
    for title in _watchlist_movies(run, alice):
        if title["id"] in ratings:
            continue
        reviews = _rows(run.initial, "SELECT * FROM reviews WHERE user_id=? AND title_id=? AND rating IS NOT NULL",
                        (alice["id"], title["id"]))
        candidates.extend((title, review) for review in reviews)
    _require(len(candidates) == 1, "Initial data does not identify one movie and one scored Alice review")
    title, review = candidates[0]
    score = review["rating"]
    _require(type(score) is int and 1 <= score <= 10, "Source review score is invalid")
    _insertions(run, {"user_ratings": [{"user_id": alice["id"], "title_id": title["id"], "rating": score}]})
    index = _write(run, alice, title, "rate")
    _require(_recorded_fields_agree(run, index, _title_path(title), {"rating": score}), "Recorded personal score contradicts source review")
    for path in ("/list/watchlist", "/list/ratings"):
        _require(_pages(run, alice["email"], {path}, before=index), "Missing initial saved-versus-rated evidence")
    source_paths = {_title_path(title) + "/reviews"}
    featured = run.initial.execute("SELECT id FROM reviews WHERE title_id=? "
                                   "ORDER BY is_seed DESC,helpful_count DESC LIMIT 3", (title["id"],)).fetchall()
    if review["id"] in {r[0] for r in featured}:
        source_paths.add(_title_path(title))
    _require(_pages(run, None, source_paths, before=index), "Missing visible source-review page")
    text = _report(run, [title])[title["id"]]
    _require(mentions(text, review["headline"]), "The answer omits the source review headline")
    explicit = _reported_review_headlines(text, title["primary_title"])
    _require(all(h == normalize(review["headline"]) for h in explicit), "The answer reports a different source headline")
    text = normalize(text)
    for user in _rows(run.initial, "SELECT id,name FROM users WHERE id!=?", (alice["id"],)):
        name = re.escape(normalize(user["name"]))
        _require(not re.search(r"\b(?:by|author\s*[:=]?)\s+" + name + r"\b|\b" + name + r"'s review\b", text),
                 "The answer attributes the source review to another author")
    global_score = re.compile(r"\b(?:imdb|global)\s+(?:rating|score)\s*(?:is|of|:|=)?\s*(\d+(?:\.\d+)?)(?:\s*/\s*10)?")
    for match in global_score.finditer(text):
        _require(Decimal(match[1]) == Decimal(str(title["rating_avg"])), "The answer contradicts the displayed global score")
    text = global_score.sub(" ", text)
    fractions = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:/|out of)\s*10\b", text)
    labels = re.findall(r"\b(?:rating|score|rated)\s*(?:(?:i|saved|set|is|of|was|now|currently|to|at)\s+){0,5}[:=]?\s*(\d+(?:\.\d+)?)", text)
    _require(fractions or labels, "The answer does not report the saved personal score")
    _require(all(Decimal(n) == score for n in fractions + labels), "The answer contradicts the source/saved score")
    return ["Alice's own review supplies the missing personal score; original reviews and all other state preserved"]


def check_expansion_state_task(number, run):
    _require(number in STATE_TASKS, "Unsupported expansion state task")
    _require(run.trajectory.get("task_id") == f"IMDb--{number}", "Task replay does not match this checker")
    try:
        return {24: _check24, 25: _check25, 26: _check26, 27: _check27}[number](run)
    except sqlite3.Error as error:
        raise VerificationError("Frozen database lacks the required task data") from error
