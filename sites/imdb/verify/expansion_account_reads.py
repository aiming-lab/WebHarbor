"""Read-only account comparisons; synthetic account state is the source.

These checks never open a live database or change historical task graders.
Navigation proves access to the relevant account and fact pages; the frozen
snapshots determine membership, attribution and the complete allowed result.
"""

from collections import defaultdict
from decimal import Decimal
import re

from answer_checks import entity_texts, has_date, has_number, mentions, normalize
from read_tasks import (_all_directors, _bindings, _names, _one,
                        _reported_titles, _require, _runtime, _title_path)
from verify_lib import VerificationError


ACCOUNT_READ_TASKS = {21, 22}


def _account(run, email):
    return _one(run.initial, "SELECT * FROM users WHERE email=?", (email,))


def _account_page(run, user, path):
    # Shared only by the new task family. Existing 15–17 remain unchanged.
    from expansion_state_tasks import authenticated_before
    return any(event["path"].rstrip("/") == path
               and authenticated_before(run, event["step_index"] +
                                        (event["phase"] == "after"), user["email"])
               for event in run.events)


def _source_lists(run, user):
    for path in ("/list/watchlist", "/list/ratings"):
        _require(_account_page(run, user, path),
                 "The two source lists were not observed under the required account")


def _account_catalog(run, user):
    return [dict(row) for row in run.initial.execute(
        "SELECT DISTINCT t.* FROM titles t WHERE t.title_type='movie' AND "
        "(EXISTS (SELECT 1 FROM watchlist_items w WHERE w.title_id=t.id AND w.user_id=?) "
        "OR EXISTS (SELECT 1 FROM user_ratings r WHERE r.title_id=t.id AND r.user_id=?))",
        (user["id"], user["id"]))]


def _owner_blocks(answer, users):
    """Accept owner columns, inline owner labels and ordinary owner sections."""
    aliases = {user["id"]: [user["name"], user["email"], user["name"].split()[0]]
               for user in users}
    output = entity_texts(answer, aliases)
    sections = {key: [] for key in aliases}
    active = None
    for line in answer.splitlines():
        text = normalize(line).strip("#* -:")
        headings = [key for key, names in aliases.items() if any(
            re.fullmatch(re.escape(normalize(name)) +
                         r"(?:'s)?(?:\s+(?:account|movies|films|results|recommendations))?", text)
            for name in names)]
        if len(headings) == 1:
            active = headings[0]
            continue
        if active is not None:
            other = [key for key, names in aliases.items() if key != active
                     and any(mentions(line, name) for name in names)]
            if other:
                active = None
            else:
                sections[active].append(line)
    return {key: output[key] + "\n" + "\n".join(sections[key]) for key in aliases}


def _language(text):
    """Normalize field labels/units only; catalog names remain the evidence keys."""
    text = normalize(text).replace("。", ".").replace("；", ";").replace("，", ",")
    text = re.sub(r"(\d{4})年(\d{1,2})月(\d{1,2})日",
                  lambda m: f"{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}", text)
    labels = {"重复影评标题": "repeated headline", "重复评论标题": "repeated headline",
              "重复标题": "repeated headline", "相同标题": "repeated headline",
              "影评标题": "headline", "评论标题": "headline",
              "个人评分": "personal rating", "影评评分": "review score", "评论评分": "review score",
              "评论日期": "review date", "影评日期": "review date", "发布日期": "review date",
              "有帮助人数": "helpful count", "有用票数": "helpful count", "有用数": "helpful count",
              "有帮助": "helpful", "作者": "author", "账号": "account", "账户": "account",
              "导演": "director", "片长": "runtime", "时长": "runtime", "分钟": " minutes ",
              "小时": " hours ", "片名": "film", "电影": "film", "年份": "year",
              "日期": "date", "评分": "score"}
    for old, new in labels.items():
        text = text.replace(old, " " + new + " ")
    return text


def _score(text, expected):
    text = _language(text)
    # Explicit global-score clauses do not describe the requested personal/review score.
    number = r"\d+(?:\.\d+)?"
    scale = r"(?:\s*(?:/|out of)\s*10)?"
    text = re.sub(r"\b(?:imdb|global)\s+(?:rating|score)\s*(?:[:=]|is|of|was)?\s*"
                  + number + scale, "", text)
    text = re.sub(r"满分\s*10\s*分", "", text)
    values = re.findall(r"(?<![\w.])(" + number + r")\s*(?:/|out of)\s*10\b", text)
    values += re.findall(r"\b(?:rating|score|rated)\s*(?:[:=]|is|of|was)?\s*(?:rated\s*)?("
                         + number + r")(?![A-Za-z0-9_]|\.\d)", text)
    return bool(values) and all(Decimal(value) == Decimal(str(expected)) for value in values)


def _runtime_units(text, expected):
    text = _language(text)
    hours = r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b)?"
    text = re.sub(hours, lambda m: f"{Decimal(m[1]) * 60 + Decimal(m[2] or '0')} minutes", text)
    return _runtime(text, expected)


_EXCLUSION = r"\b(?:excluded|does not qualify|not eligible|already (?:saved|in)|below|not included)\b|不符合|不计入|不包括|排除|已在"


def _table_lines(answer):
    """Yield ordinary lines and labelled Markdown rows without merging rows."""
    headers = None
    for line in _language(answer).splitlines():
        if "|" not in line:
            headers = None
            yield line, {}
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if re.fullmatch(r"[| :\-]+", line.strip()):
            continue
        if any(cell in {"author", "review author", "posted by", "film", "movie", "film title", "title"}
               for cell in cells):
            headers = cells
            continue
        if headers:
            _require(len(cells) == len(headers), "A result table has an incomplete row")
            fields = dict(zip(headers, cells))
            yield "; ".join(f"{h}: {c}" for h, c in fields.items()), fields
        else:
            yield line, {}


def _exclude_extra_titles(text, candidates, expected):
    for line, fields in _table_lines(text):
        named = _reported_titles(line, candidates)
        if re.search(_EXCLUSION, line):
            continue
        _require(all(title["id"] in expected for title in named),
                 "An ineligible movie is reported as part of the result")
        # A labelled movie cell or an explicit inclusion is a result assertion,
        # including when the invented name is absent from the frozen catalog.
        labelled = re.search(r"\b(?:film|movie|film title|title)\s*:\s*([^;|]+)", line)
        if labelled and not fields:
            fields = {"film": labelled[1]}
        for key in ("film", "movie", "film title", "title"):
            if key in fields:
                matches = _reported_titles(fields[key], candidates)
                _require(len(matches) == 1 and matches[0]["id"] in expected,
                         "A reported film is outside the qualifying result")
        explicit = re.search(r"(?:\b(?:also )?include\s+(.+?)\s+as a qualifying (?:movie|film)\b|(?:也?包括|新增结果)\s*[:：]?\s*(.+))", line)
        if explicit:
            matches = _reported_titles(explicit[1] or explicit[2], candidates)
            _require(bool(matches) and all(title["id"] in expected for title in matches),
                     "An explicit qualifying result is not in the required set")


def _check_21(run):
    users = [_account(run, email) for email in ("alice.j@test.com", "bob.c@test.com")]
    blocks = _owner_blocks(_language(run.answer), users)
    for user in users:
        _source_lists(run, user)
        candidates = [dict(row) for row in run.initial.execute("SELECT * FROM titles")]
        selected = [dict(row) for row in run.initial.execute(
            "SELECT t.*, r.rating AS personal_rating FROM user_ratings r "
            "JOIN titles t ON t.id=r.title_id WHERE r.user_id=? AND r.rating>=9 "
            "AND t.title_type='movie' AND NOT EXISTS (SELECT 1 FROM watchlist_items w "
            "WHERE w.user_id=r.user_id AND w.title_id=r.title_id)", (user["id"],))]
        _require(bool(selected), "The initial account has no qualifying movie")
        text = blocks[user["id"]]
        _require(bool(text.strip()), "Results are not attributed to the required account")
        bindings = _bindings(text, candidates)
        _exclude_extra_titles(text, candidates, {title["id"] for title in selected})
        for title in selected:
            facts = bindings[title["id"]]
            _require(any(mentions(facts, name) for name in _names(title)),
                     "A qualifying title is missing or assigned to the wrong account")
            _require(_score(facts, title["personal_rating"]),
                     "The personal score is missing or does not match its owner and movie")
            _require(_runtime_units(facts, title["runtime_min"]),
                     "A qualifying movie's runtime is missing or incorrect")
            _require(_all_directors(run, facts, title),
                     "A qualifying movie's director credits are missing or incorrect")
            path = _title_path(title)
            _require(run.visited(path) or run.visited(path + "/fullcredits"),
                     "A reported movie's director facts lack a relevant on-site visit")
    return ["Both accounts' own initial ratings-minus-Watchlist sets match the attributed results",
            "Personal ratings, runtimes and director credits match; account data is unchanged"]


def _review_groups(run, candidates):
    groups = defaultdict(list)
    for title in candidates:
        for row in run.initial.execute(
                "SELECT r.*, u.name AS author FROM reviews r JOIN users u ON u.id=r.user_id "
                "WHERE r.title_id=?", (title["id"],)):
            review = dict(row)
            groups[(title["id"], review["headline"])].append(review)
    return {key: reviews for key, reviews in groups.items()
            if len({review["user_id"] for review in reviews}) > 1}


def _helpful(text, expected):
    text = normalize(text)
    values = re.findall(r"\bhelpful(?:ness)?(?:\s+(?:count|votes))?\s*[:=]?\s*(\d[\d,]*)", text)
    # Keep the reverse form on one line. ``\s`` also spans newlines and can
    # otherwise misread the day from a preceding ISO date as a helpful count.
    values += re.findall(r"(?<![\w.])(\d[\d,]*)[\t ]+(?:people[\t ]+)?"
                         r"(?:found[\t ]+(?:this|it)[\t ]+)?helpful\b", text)
    return bool(values) and all(int(value.replace(",", "")) == expected for value in values)


def _review_date(text, expected):
    if not has_date(text, expected):
        return False
    # A second, conflicting ISO date cannot rescue a wrong row attribution.
    return all(value == str(expected)[:10] for value in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))


def _headline(text):
    match = re.search(r"\b(?:(?:repeated|shared|review)\s+)?headline\s*(?::|=|is)\s*(.+?)(?:;|$)", text)
    if not match:
        match = re.search(r'["“]([^"”]+)["”]', text)
    if not match:
        return None
    return match[1].strip().rstrip(".").strip(' \"“”‘’')


def _author_aliases(run):
    aliases = defaultdict(set)
    for row in run.initial.execute("SELECT id,name FROM users"):
        for name in (row["name"], row["name"].split()[0]):
            aliases[normalize(name)].add(row["id"])
    return {name: next(iter(ids)) for name, ids in aliases.items() if len(ids) == 1}


def _review_records(run, candidates):
    """Keep explicit (movie, headline) scope and each review row's multiplicity.

    A heading may supply common film/year/headline fields. Author tables and
    author-led prose supply records; unknown explicit authors still make a
    record and fail matching instead of being silently discarded.
    """
    aliases = _author_aliases(run)
    names = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    author_start = re.compile(r"^(?:[-*]\s*)?(?:by\s+)?(" + names
                              + r")(?!\w)(?:\s*[:,-]\s*|\s*$)")
    rows, declared = [], set()
    title, year, headline, active = None, None, None, None

    def flush():
        nonlocal active
        if active is not None:
            rows.append(active)
            active = None

    def lines():
        # Several author-led records may share one paragraph. Field continuation
        # lines remain part of the active author instead of becoming authors.
        boundary = re.compile(r"(?<!\w)(?:by\s+)?(?:" + names + r")(?!\w)\s*:")
        for line, fields in _table_lines(run.answer):
            starts = list(boundary.finditer(line)) if not fields else []
            if len(starts) < 2:
                yield line, fields
                continue
            if starts[0].start():
                yield line[:starts[0].start()], {}
            for i, match in enumerate(starts):
                stop = starts[i + 1].start() if i + 1 < len(starts) else len(line)
                yield line[match.start():stop], {}

    for line, fields in lines():
        if not line.strip():
            continue
        if re.search(_EXCLUSION, line):
            flush()
            continue
        named = _reported_titles(line, candidates)
        row_title = next((fields[key] for key in ("film", "movie", "film title", "title") if key in fields), None)
        if row_title is not None:
            named = _reported_titles(row_title, candidates)
            _require(len(named) == 1, "A review group names an unknown or ambiguous movie")
        new_headline = _headline(line)
        if named or new_headline is not None:
            flush()
        if named:
            _require(len(named) == 1, "A review record mixes movie groups")
            if title is not None and title != named[0]["id"]:
                headline, year = None, None
            title = named[0]["id"]
            year_text = fields.get("year", "")
            if not year_text:
                for alias in _names(named[0]):
                    adjacent = re.search(re.escape(normalize(alias)) + r"\s*[(\[]?\s*(\d{4})\b", line)
                    if adjacent:
                        year_text = adjacent[1]
                        break
            year_match = re.fullmatch(r"\s*(\d{4})\s*", year_text)
            if year_match:
                year = int(year_match[1])
        if new_headline is not None:
            headline = new_headline
        if title is not None and headline is not None and (named or new_headline is not None):
            declared.add((title, headline))
        author = next((fields[key] for key in ("author", "review author", "posted by") if key in fields), None)
        if author is None:
            labelled = re.search(r"\b(?:author|posted by)\s*:\s*([^;]+)", line)
            leading = author_start.match(line)
            if labelled:
                author = labelled[1].strip().rstrip(".")
            elif leading:
                author = leading[1]
            elif ":" in line and not named:
                prefix, detail = line.split(":", 1)
                prefix = prefix.strip().lstrip("-*").strip()
                reserved = re.match(
                    r"^(?:(?:personal|review)\s+)?(?:score|rating|date|helpful(?: count)?)$",
                    prefix,
                )
                if (re.search(r"\b(?:score|rated|rating)\b", detail)
                        and not reserved and len(prefix.split()) <= 8
                        and not re.search(r"[.!?;]", prefix)):
                    # An unknown explicitly named prose reviewer is still a
                    # row.  Sentence-style summaries before a colon are not.
                    author = prefix
        if author is not None:
            flush()
            _require(title is not None and headline is not None,
                     "A review row lacks its movie and headline scope")
            active = {"group": (title, headline), "year": year,
                      "author_id": aliases.get(normalize(author)), "text": line}
            if fields:
                flush()
        elif active is not None:
            active["text"] += "\n" + line
    flush()
    return rows, declared


def _check_22(run):
    user = _account(run, "alice.j@test.com")
    _source_lists(run, user)
    candidates = _account_catalog(run, user)
    groups = _review_groups(run, candidates)
    _require(bool(groups), "The initial account catalog has no multi-author duplicate headline")
    canonical = {(title, normalize(headline).rstrip(".")): reviews for (title, headline), reviews in groups.items()}
    all_titles = [dict(row) for row in run.initial.execute("SELECT * FROM titles")]
    _exclude_extra_titles(run.answer, all_titles, {key[0] for key in groups})
    rows, declared = _review_records(run, all_titles)
    _require(declared == set(canonical), "The reported duplicate-headline groups are incomplete or incorrect")
    for key, reviews in canonical.items():
        title = next(title for title in candidates if title["id"] == key[0])
        _require(run.visited(_title_path(title) + "/reviews"),
                 "The review rows and publication dates lack an on-site review-page visit")
        reported = [row for row in rows if row["group"] == key]
        _require(len(reported) == len(reviews), "A matching review row is missing or extra")
        remaining = list(reviews)
        for row in reported:
            _require(row["year"] == title["year"], "A review group has a missing or wrong movie year")
            matching = [review for review in remaining if review["user_id"] == row["author_id"]
                        and _score(row["text"], review["rating"])
                        and _review_date(row["text"], review["created_at"])
                        and _helpful(row["text"], review["helpful_count"])]
            _require(bool(matching), "A review's author, score, date or helpful count is missing or misattributed")
            remaining.remove(matching[0])
    return ["Alice's two initial lists define the audited movie union",
            "Every multi-author duplicate headline and its author-bound review facts match; business data is unchanged"]


def check_account_read_task(number, run):
    _require(number in ACCOUNT_READ_TASKS, "Unsupported account read task number")
    _require(bool(run.answer.strip()), "The final answer is empty")
    run.assert_unchanged()
    return {21: _check_21, 22: _check_22}[number](run)
