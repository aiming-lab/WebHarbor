"""Deterministic Y Combinator grading against frozen runs and explicit DB snapshots.

Ground truth is derived from the frozen initial snapshot rather than copied into
this file, so a verifier fails loudly if the seed it is graded against is not the
one the task was written for. The recorder is trusted to report browser
observations honestly; screenshot checks validate packaging, not pixels.

Input contract: see verify/README.md.
"""
from __future__ import annotations

import argparse
from datetime import date
import ipaddress
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image

SITE = "y_combinator"
PREFIX = "Y Combinator"

TABLES = {"user", "company", "company_news", "founder", "staff", "blog_post",
          "library_article", "library_carousel", "carousel_articles", "bookmark",
          "launch", "launch_vote", "faq", "legal_document", "static_page", "home_block"}

# Tasks that are expected to change persistent state, and the tables they may touch.
STATEFUL = {
    8: {"bookmark"},
    9: {"launch_vote", "launch"},
    10: {"user"},
}


# ------------------------------------------------------------------ text

def norm(value):
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text)
    return re.sub(r"\s+", " ", text).strip()


def words(value):
    return re.sub(r"[^\w]+", " ", norm(value)).strip()


def phrase(text, expected):
    return bool(re.search(r"(?<!\w)" + re.escape(words(expected)) + r"(?!\w)", words(text)))


def answer_clauses(text):
    # Preserve sentence boundaries before stripping punctuation; decimal points
    # and filename extensions are not sentence boundaries.
    normalized = re.sub(r"\b(jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\.\s", r"\1 ", norm(text))
    return re.split(r"[!?;\n]+|\.(?:\s+|$)|\b(?:but|however|instead|rather than)\b", normalized)


def negated(text):
    return bool(re.search(
        r"\b(?:not|no|never|without|isn't|wasn't|aren't|weren't|isnt|wasnt|incorrect|fewer than|less than)\b",
        norm(text)))


def affirmative_phrase(text, expected):
    """A phrase that appears only inside a negation is not an assertion of it."""
    matching = [clause for clause in answer_clauses(text) if phrase(clause, expected)]
    return bool(matching) and not negated(matching[-1])


def number_values(text):
    """Numbers in the answer, including grouped and million/thousand notation."""
    text = norm(text)
    found = set()
    for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(million|thousand|m\b|k\b)?", text):
        amount = float(match[1])
        amount *= {"million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}.get(match[2], 1)
        found.add(amount)
    return found


def has_number(text, value):
    return any(not negated(clause) and float(value) in number_values(clause)
               for clause in answer_clauses(text))


def has_year(text, year):
    return any(not negated(clause) and str(int(year)) in re.findall(r"\b(?:18|19|20)\d{2}\b", clause)
               for clause in answer_clauses(text))


def has_date(text, value):
    expected_date = date.fromisoformat(value[:10])
    year, month, day = expected_date.year, expected_date.month, expected_date.day
    # English month names are explicit so grading does not depend on host locale.
    months = ("January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December")
    month_name = months[month - 1]
    patterns = [rf"{year}-{month:02d}-{day:02d}"]
    for name in (month_name, month_name[:3]):
        patterns.extend([rf"{name}\.?\s+0?{day}(?:st|nd|rd|th)?[,]?\s+{year}",
                         rf"0?{day}(?:st|nd|rd|th)?\s+{name}\.?[,]?\s+{year}"])
    pattern = r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)"
    return any(not negated(clause) and re.search(pattern, clause, re.I)
               for clause in answer_clauses(text))


def claims_larger(text, company, other):
    """Match an explicit comparison without treating mere name presence as one."""
    for clause in answer_clauses(text):
        if negated(clause) or not phrase(clause, company):
            continue
        normalized = words(clause)
        marker = re.search(r"\b(?:larger|bigger|largest|biggest|more staff|more employees|exceeds|smaller|fewer staff|fewer employees)\b", normalized)
        if marker is None:
            continue
        mentions = sorted((match.start(), name) for name in (company, other)
                          for match in re.finditer(r"(?<!\w)" + re.escape(words(name)) + r"(?!\w)", normalized))
        preceding = [item for item in mentions if item[0] < marker.start()]
        subject = (preceding[-1] if preceding else mentions[0])[1]
        smaller_claim = marker.group() in {"smaller", "fewer staff", "fewer employees"}
        if (subject == company) != smaller_claim:
            return True
    return False


def duration_stated(text, seconds):
    """Accept 14:49, "14 minutes 49 seconds", or the raw second count."""
    minutes, remainder = divmod(int(seconds), 60)
    if re.search(rf"(?<!\d){minutes}\s*:\s*{remainder:02d}(?!\d)", norm(text)):
        return True
    if re.search(rf"(?<!\d){minutes}\s*(?:min|minute|minutes|m)\b[^\d]{{0,12}}{remainder}\s*(?:sec|second|seconds|s)\b",
                 norm(text)):
        return True
    return has_number(text, seconds)


# ------------------------------------------------------------------ trajectory

def loopback(host):
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def local_url(url, trajectory):
    if not isinstance(url, str):
        return False
    try:
        target, start = urlsplit(url), urlsplit(trajectory.get("start_url", ""))
        return (target.scheme == start.scheme == "http" and loopback(start.hostname)
                and loopback(target.hostname) and target.port == start.port
                and not target.username and not target.password)
    except ValueError:
        return False


def recorded_urls(trajectory):
    values = []
    if trajectory.get("start_url"):
        values.append(trajectory["start_url"])
    for step in trajectory.get("steps", []):
        if not isinstance(step, dict):
            continue
        for key in ("url_before", "url", "url_after"):
            value = step.get(key)
            if value and (not values or value != values[-1]):
                values.append(value)
    if trajectory.get("final_url"):
        values.append(trajectory["final_url"])
    return values


def urls(trajectory):
    for value in recorded_urls(trajectory):
        if local_url(value, trajectory):
            yield value


def visited(trajectory, path):
    wanted = path.rstrip("/") or "/"
    return any(unquote(urlsplit(url).path).rstrip("/") == wanted for url in urls(trajectory))


def visited_prefix(trajectory, prefix):
    return any(unquote(urlsplit(url).path).startswith(prefix) for url in urls(trajectory))


def query_matches(url, expected):
    params = parse_qs(urlsplit(url).query, keep_blank_values=True)
    for key, value in expected.items():
        observed = params.get(key)
        if observed is None or len(observed) != 1 or norm(observed[0]) != norm(value):
            return False
    return True


def visited_query(trajectory, path, expected):
    wanted = path.rstrip("/") or "/"
    return any(unquote(urlsplit(url).path).rstrip("/") == wanted and query_matches(url, expected)
               for url in urls(trajectory))


# ------------------------------------------------------------------ snapshots

def snapshot(path):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != TABLES:
            raise ValueError(f"Unexpected Y Combinator database schema: {sorted(tables)}")
        if list(connection.execute("PRAGMA foreign_key_check")):
            raise ValueError("Foreign-key integrity failed")
        data = {}
        for table in sorted(tables):
            rows = [dict(row) for row in connection.execute('SELECT * FROM "' + table + '"')]
            if table == "carousel_articles":
                data[table] = {(row["carousel_id"], row["article_id"]): row for row in rows}
            else:
                data[table] = {row["id"]: row for row in rows}
        return data


def schema_snapshot(path):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()


def only_new(before, after, table):
    return [row for key, row in after[table].items() if key not in before[table]]


def rows(data, table, **filters):
    out = []
    for row in data[table].values():
        if all(row.get(key) == value for key, value in filters.items()):
            out.append(row)
    return out


def one(data, table, **filters):
    found = rows(data, table, **filters)
    if len(found) != 1:
        raise ValueError(f"expected exactly one {table} matching {filters}, found {len(found)}")
    return found[0]


def user_id(data, email):
    found = [row["id"] for row in data["user"].values() if norm(row["email"]) == norm(email)]
    return found[0] if len(found) == 1 else None


def unique_extreme(candidates, key, reverse=False):
    """The extreme value must be unambiguous, or the task is not well posed."""
    usable = [row for row in candidates if row.get(key) is not None]
    if len(usable) < 2:
        raise ValueError(f"not enough rows with {key} to compare")
    ordered = sorted(usable, key=lambda row: row[key], reverse=reverse)
    if ordered[0][key] == ordered[1][key]:
        raise ValueError(f"ambiguous extreme for {key}")
    return ordered[0]


# ------------------------------------------------------------------ ground truth

def carousel_articles_of(before, name):
    carousel = one(before, "library_carousel", name=name)
    ids = [key[1] for key in before["carousel_articles"] if key[0] == carousel["id"]]
    return [before["library_article"][article_id] for article_id in ids]


def expected(task, before):
    """Derive each task's answer from the frozen initial state."""
    if task == 0:
        return {"company": one(before, "company", slug="ginkgo-bioworks")}
    if task == 1:
        pool = rows(before, "company", industry="Fintech", stage="Growth", status="Public")
        return {"pool": pool, "company": unique_extreme(pool, "team_size", reverse=True)}
    if task == 2:
        hits = [row for row in before["company"].values()
                if "warehouses" in norm(" ".join(filter(None, [row["name"], row["one_liner"],
                                                              row["long_description"]])))]
        founded = [row for row in hits if row["year_founded"] == 2020]
        if len(founded) != 1:
            raise ValueError("warehouses search does not have exactly one 2020 company")
        return {"pool": hits, "company": founded[0]}
    if task == 3:
        pool = rows(before, "company", industry="Industrials", status="Public")
        return {"pool": pool, "company": unique_extreme(pool, "team_size")}
    if task == 4:
        founder = one(before, "founder", slug="chad-rigetti")
        return {"founder": founder, "company": before["company"][founder["company_id"]]}
    if task == 5:
        pool = carousel_articles_of(before, "Hard Tech")
        return {"pool": pool, "article": unique_extreme(pool, "view_count", reverse=True)}
    if task == 6:
        pool = [row for row in before["launch"].values()
                if "2026-08-25" <= (row["created_at"] or "")[:10] <= "2026-08-27"]
        launch = unique_extreme(pool, "vote_count", reverse=True)
        return {"pool": pool, "launch": launch,
                "company": one(before, "company", slug=launch["company_slug"])}
    if task == 7:
        return {"post": one(before, "blog_post", slug="diana-hu-managing-partner"),
                "company": "Escher Reality", "batch": "S17", "acquirer": "Niantic"}
    if task == 8:
        return {"article": one(before, "library_article", slug="4D-yc-s-essential-startup-advice"),
                "email": "alice.j@test.com"}
    if task == 9:
        return {"launch": one(before, "launch",
                              slug="SUZ-gamgee-personalised-mrna-cancer-vaccines-for-dogs"),
                "email": "bob.m@test.com"}
    if task == 10:
        return {"email": "nina.patel@test.com"}
    if task == 11:
        return {"faq": one(before, "faq", question="How much do you invest?")}
    if task == 12:
        return {"document": one(before, "legal_document", group="doc_links",
                                title="SAFE: Valuation Cap, no Discount")}
    if task == 13:
        person = one(before, "staff", slug="jessica-livingston")
        bio = norm(person["bio"] or "")
        if "founders at work" not in bio or "vp of marketing" not in bio or "adams harkness" not in bio:
            raise ValueError("Jessica Livingston profile no longer contains the task facts")
        return {"person": person, "book": "Founders at Work",
                "previous_role": "VP of marketing", "previous_employer": "Adams Harkness"}
    if task == 14:
        first = one(before, "company", slug="codecademy")
        second = one(before, "company", slug="panorama-education")
        return {"companies": [first, second],
                "larger": unique_extreme([first, second], "team_size", reverse=True)}
    if task == 15:
        return {"pool": rows(before, "company", industry="Education", status="Acquired")}
    if task == 16:
        matches = [row for row in before["library_article"].values()
                   if "karpathy" in norm(row["title"])]
        if len(matches) != 1:
            raise ValueError("expected exactly one library article naming Karpathy")
        return {"article": matches[0]}
    if task == 17:
        pool = rows(before, "company", industry="Government")
        founded = [row for row in pool if row["year_founded"] == 2026]
        if len(founded) != 1:
            raise ValueError("expected exactly one Government company founded in 2026")
        return {"pool": pool, "company": founded[0]}
    raise ValueError(f"unknown task {task}")


# ------------------------------------------------------------------ checks

class Checks:
    def __init__(self, task):
        self.task = task
        self.results = []

    def check(self, name, condition, detail=""):
        self.results.append({"check": name, "pass": bool(condition), "detail": detail})

    def result(self):
        failures = [item["check"] for item in self.results if not item["pass"]]
        return {"task_id": f"{PREFIX}--{self.task}", "pass": not failures,
                "reason": "; ".join(failures) if failures else "All applicable checks passed",
                "evidence": self.results}


def package_checks(judge, trajectory, run_dir):
    steps = trajectory.get("steps")
    raw_urls = recorded_urls(trajectory)
    judge.check("task_identity", trajectory.get("task_id") == f"{PREFIX}--{judge.task}")
    judge.check("local_ui_evidence", isinstance(steps, list) and bool(steps) and bool(raw_urls))
    judge.check("same_origin_navigation",
                bool(raw_urls) and all(local_url(url, trajectory) for url in raw_urls))
    judge.check("final_answer", isinstance(trajectory.get("final_answer"), str)
                and bool(trajectory["final_answer"].strip()))
    judge.check("completed_run", trajectory.get("terminated") is True
                and trajectory.get("termination_reason") in {"agent_done", "guided_done"})
    judge.check("successful_actions", isinstance(steps, list) and bool(steps)
                and all(isinstance(step, dict)
                        and step.get("action_result", {}).get("success") is True
                        for step in steps))
    screenshots = Path(run_dir).resolve() / "screenshots"
    valid = isinstance(steps, list) and bool(steps)
    referenced = []
    for step in steps or []:
        if not isinstance(step, dict):
            valid = False
            continue
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            if not isinstance(name, str) or Path(name).name != name:
                valid = False
                continue
            referenced.append(name)
            path = screenshots / name
            try:
                if path.resolve().parent != screenshots or path.stat().st_size < 1000:
                    valid = False
                    continue
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    valid &= image.format == "PNG" and image.width >= 320 and image.height >= 200
            except (OSError, ValueError, SyntaxError):
                valid = False
    valid &= bool(referenced)
    judge.check("step_screenshot_package", valid)


def state_checks(judge, trajectory, before, after, facts):
    task = judge.task
    allowed = STATEFUL.get(task, set())
    judge.check("same_table_set", before.keys() == after.keys())
    for table in sorted(before.keys() | after.keys()):
        if table not in before or table not in after:
            continue
        if table not in allowed:
            judge.check("unchanged_" + table, before[table] == after[table])

    if task == 8:
        uid = user_id(after, facts["email"])
        judge.check("target_account", uid is not None)
        judge.check("login_workflow", visited(trajectory, "/login"))
        new = only_new(before, after, "bookmark")
        judge.check("one_new_bookmark", len(new) == 1)
        judge.check("bookmark_binding",
                    len(new) == 1 and new[0]["user_id"] == uid
                    and new[0]["article_id"] == facts["article"]["id"])
        judge.check("no_bookmark_removed",
                    all(after["bookmark"].get(key) == row for key, row in before["bookmark"].items()))
        judge.check("bookmarks_page_seen", visited(trajectory, "/library/bookmarks"))
    elif task == 9:
        uid = user_id(after, facts["email"])
        launch = facts["launch"]
        judge.check("target_account", uid is not None)
        judge.check("login_workflow", visited(trajectory, "/login"))
        new = only_new(before, after, "launch_vote")
        judge.check("one_new_vote", len(new) == 1)
        judge.check("vote_binding",
                    len(new) == 1 and new[0]["user_id"] == uid and new[0]["launch_id"] == launch["id"])
        judge.check("no_vote_removed",
                    all(after["launch_vote"].get(key) == row for key, row in before["launch_vote"].items()))
        judge.check("vote_count_incremented",
                    after["launch"].get(launch["id"]) == {**launch, "vote_count": launch["vote_count"] + 1})
        judge.check("same_launch_rows", before["launch"].keys() == after["launch"].keys())
        for key, row in before["launch"].items():
            if key != launch["id"]:
                judge.check(f"launch_untouched_{key}", after["launch"].get(key) == row)
    elif task == 10:
        judge.check("registration_workflow", visited(trajectory, "/register"))
        new = only_new(before, after, "user")
        judge.check("one_registered_account", len(new) == 1)
        judge.check("registered_email",
                    len(new) == 1 and norm(new[0]["email"]) == norm(facts["email"]))
        judge.check("newsletter_subscribed", len(new) == 1 and bool(new[0]["newsletter"]))
        password_ok = False
        if len(new) == 1:
            try:
                import bcrypt
                password_ok = bcrypt.checkpw(b"TestPass123!", new[0]["password"].encode())
            except (ImportError, ValueError, AttributeError):
                password_ok = False
        judge.check("registered_password", password_ok)
        for key, row in before["user"].items():
            judge.check(f"user_untouched_{key}", after["user"].get(key) == row)
    else:
        judge.check("read_only_task", all(before[table] == after[table] for table in before))


def navigation_checks(judge, trajectory, facts):
    task = judge.task
    if task == 0:
        judge.check("biology_search_used", visited_query(trajectory, "/companies", {"q": "biology"}))
        judge.check("company_page_opened", visited(trajectory, f"/companies/{facts['company']['slug']}"))
    elif task in {1, 3}:
        judge.check("directory_used", visited(trajectory, "/companies"))
        judge.check("candidates_opened",
                    all(visited(trajectory, f"/companies/{row['slug']}") for row in facts["pool"]))
    elif task == 2:
        judge.check("warehouses_search_used", visited_query(trajectory, "/companies", {"q": "warehouses"}))
        judge.check("candidates_opened",
                    all(visited(trajectory, f"/companies/{row['slug']}") for row in facts["pool"]))
    elif task == 4:
        judge.check("quantum_search_used", visited_query(trajectory, "/founders", {"q": "quantum"}))
        # Founder permalinks deliberately redirect to the company profile that
        # carries the founder bio and the requested company facts.
        judge.check("founder_company_profile_opened",
                    visited(trajectory, f"/companies/{facts['company']['slug']}"))
    elif task == 5:
        judge.check("library_used", visited(trajectory, "/library"))
        judge.check("collection_articles_opened",
                    all(visited(trajectory, f"/library/{row['slug']}") for row in facts["pool"]))
    elif task == 6:
        judge.check("launches_used", visited(trajectory, "/launches"))
        judge.check("company_page_opened", visited(trajectory, f"/companies/{facts['company']['slug']}"))
    elif task == 7:
        judge.check("post_opened", visited(trajectory, f"/blog/{facts['post']['slug']}"))
    elif task == 8:
        judge.check("article_opened", visited(trajectory, f"/library/{facts['article']['slug']}"))
    elif task == 9:
        judge.check("launch_opened", visited(trajectory, f"/launches/{facts['launch']['slug']}"))
    elif task == 10:
        judge.check("subscribe_page_used", visited(trajectory, "/subscribe"))
    elif task == 11:
        judge.check("faq_opened", visited(trajectory, "/faq"))
    elif task == 12:
        judge.check("safe_page_opened", visited(trajectory, "/safe") or visited(trajectory, "/documents"))
    elif task == 13:
        judge.check("people_directory_used", visited(trajectory, "/people"))
        judge.check("profile_opened", visited(trajectory, f"/people/{facts['person']['slug']}"))
    elif task == 14:
        judge.check("both_companies_opened",
                    all(visited(trajectory, f"/companies/{row['slug']}") for row in facts["companies"]))
    elif task == 15:
        judge.check("directory_used", visited(trajectory, "/companies"))
        judge.check("results_opened",
                    all(visited(trajectory, f"/companies/{row['slug']}") for row in facts["pool"]))
    elif task == 16:
        judge.check("software_search_used", visited_query(trajectory, "/library", {"q": "software"}))
        judge.check("article_opened", visited(trajectory, f"/library/{facts['article']['slug']}"))
    elif task == 17:
        judge.check("directory_used", visited(trajectory, "/companies"))
        judge.check("candidates_opened",
                    all(visited(trajectory, f"/companies/{row['slug']}") for row in facts["pool"]))


def answer_checks(judge, trajectory, facts):
    text = trajectory.get("final_answer") or ""
    task = judge.task

    def company_named(row):
        return affirmative_phrase(text, row["name"])

    if task == 0:
        company = facts["company"]
        judge.check("team_size", has_number(text, company["team_size"]))
        judge.check("year_founded", has_year(text, company["year_founded"]))
        judge.check("location", affirmative_phrase(text, company["location"]))
    elif task == 1:
        company = facts["company"]
        judge.check("company_identified", company_named(company))
        judge.check("team_size", has_number(text, company["team_size"]))
        judge.check("location", phrase(text, company["location"]))
        for other in facts["pool"]:
            if other["id"] != company["id"]:
                judge.check(f"not_claimed_{other['slug']}", not affirmative_phrase(
                    text, f"{other['name']} has the larger team"))
    elif task == 2:
        company = facts["company"]
        judge.check("company_identified", company_named(company))
        judge.check("batch", phrase(text, company["batch"]))
        judge.check("team_size", has_number(text, company["team_size"]))
    elif task == 3:
        company = facts["company"]
        judge.check("company_identified", company_named(company))
        judge.check("team_size", has_number(text, company["team_size"]))
        judge.check("year_founded", has_year(text, company["year_founded"]))
    elif task == 4:
        judge.check("company_identified", company_named(facts["company"]))
        judge.check("team_size", has_number(text, facts["company"]["team_size"]))
        judge.check("industry", phrase(text, facts["company"]["industry"]))
        judge.check("location", affirmative_phrase(text, facts["company"]["location"]))
    elif task == 5:
        article = facts["article"]
        judge.check("article_identified", affirmative_phrase(text, article["title"]))
        judge.check("view_count", has_number(text, article["view_count"]))
        judge.check("duration", duration_stated(text, article["duration_seconds"]))
    elif task == 6:
        company = facts["company"]
        judge.check("location", phrase(text, company["location"]))
        judge.check("team_size", has_number(text, company["team_size"]))
        judge.check("group_partner", affirmative_phrase(text, company["group_partner"]))
    elif task == 7:
        judge.check("founded_company", affirmative_phrase(text, facts["company"]))
        judge.check("batch", phrase(text, facts["batch"]) or phrase(text, "summer 2017"))
        judge.check("acquirer", affirmative_phrase(text, facts["acquirer"]))
    elif task == 8:
        judge.check("bookmark_confirmed", affirmative_phrase(text, facts["article"]["title"]))
    elif task == 9:
        judge.check("resulting_count", has_number(text, facts["launch"]["vote_count"] + 1))
    elif task == 10:
        judge.check("subscription_confirmed", phrase(text, "subscribed") or phrase(text, "subscribe"))
    elif task == 11:
        judge.check("amount", has_number(text, 500000))
        judge.check("category", phrase(text, facts["faq"]["category"]))
    elif task == 12:
        judge.check("file_name", phrase(text, facts["document"]["filename"]))
    elif task == 13:
        person = facts["person"]
        judge.check("name", affirmative_phrase(text, person["name"]))
        judge.check("title", phrase(text, person["title"]))
        judge.check("section", phrase(text, person["group"]))
        judge.check("book", affirmative_phrase(text, facts["book"]))
        judge.check("previous_role", phrase(text, facts["previous_role"]))
        judge.check("previous_employer", affirmative_phrase(text, facts["previous_employer"]))
    elif task == 14:
        larger = facts["larger"]
        smaller = next(row for row in facts["companies"] if row != larger)
        judge.check("larger_identified", affirmative_phrase(text, larger["name"]))
        judge.check("comparison_not_reversed", not claims_larger(text, smaller["name"], larger["name"]))
        for row in facts["companies"]:
            judge.check(f"team_size_{row['slug']}", has_number(text, row["team_size"]))
            judge.check(f"batch_{row['slug']}", phrase(text, row["batch"]))
    elif task == 15:
        for row in facts["pool"]:
            judge.check(f"named_{row['slug']}", affirmative_phrase(text, row["name"]))
            judge.check(f"batch_{row['slug']}", phrase(text, row["batch"]))
            judge.check(f"team_size_{row['slug']}", has_number(text, row["team_size"]))
    elif task == 16:
        article = facts["article"]
        judge.check("series", phrase(text, article["series"]))
        judge.check("view_count", has_number(text, article["view_count"]))
        judge.check("published", has_date(text, article["created_at"]))
    elif task == 17:
        company = facts["company"]
        judge.check("company_identified", company_named(company))
        judge.check("batch", phrase(text, company["batch"]))
        judge.check("team_size", has_number(text, company["team_size"]))


# ------------------------------------------------------------------ entry

def grade(task, run_dir, initial_db, after_db):
    judge = Checks(task)
    try:
        trajectory = json.loads((Path(run_dir) / "trajectory.json").read_text())
        package_checks(judge, trajectory, run_dir)
        before, after = snapshot(initial_db), snapshot(after_db)
        judge.check("exact_database_schema", schema_snapshot(initial_db) == schema_snapshot(after_db))
        facts = expected(task, before)
        state_checks(judge, trajectory, before, after, facts)
        navigation_checks(judge, trajectory, facts)
        answer_checks(judge, trajectory, facts)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, sqlite3.Error) as error:
        judge.check("valid_inputs", False, f"{type(error).__name__}: {error}")
    return judge.result()


def _bool_value(value):
    return str(value).casefold() in {"1", "true", "yes", "on"}


def main(task):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", help="Explicit live probe only; frozen runs use their own snapshots")
    parser.add_argument("--no_llm", nargs="?", const=True, default=False, type=_bool_value,
                        help="Accepted for harness compatibility; grading is always deterministic")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="y-combinator-verifier-") as temporary:
        try:
            run_dir = Path(args.run_dir)
            frozen = [run_dir / "initial_state" / f"{SITE}.db",
                      run_dir / "after_state" / f"{SITE}.db"]
            paths = [Path(explicit) if explicit else default
                     for explicit, default in zip((args.initial_db, args.after_db), frozen)]
            # Never combine a frozen before state with a later live after state.
            has_frozen_input = (args.initial_db or args.after_db
                                or any(path.parent.exists() for path in frozen))
            if not has_frozen_input and args.container:
                paths = []
                for kind in ("instance_seed", "instance"):
                    destination = Path(temporary) / (kind + ".db")
                    subprocess.run(
                        ["docker", "cp",
                         f"{args.container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db", str(destination)],
                        check=True, capture_output=True, timeout=30)
                    paths.append(destination)
            if not all(path.is_file() for path in paths):
                raise FileNotFoundError("Both initial and after snapshots are required")
            result = grade(task, args.run_dir, *paths)
        except (OSError, subprocess.SubprocessError) as error:
            result = {"task_id": f"{PREFIX}--{task}", "pass": False,
                      "reason": "Database snapshot unavailable", "evidence": [type(error).__name__]}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result["pass"] else 1)
