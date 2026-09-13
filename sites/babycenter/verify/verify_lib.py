#!/usr/bin/env python3
"""Deterministic, fail-closed verifiers for the BabyCenter benchmark tasks."""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sqlite3
import struct
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse


READ_ONLY_TABLES = (
    "user",
    "pregnancy_week",
    "baby_month",
    "article",
    "community_post",
    "saved_item",
)


class Judge:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.evidence: list[dict] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.evidence.append({"check": name, "pass": bool(passed), "detail": detail})

    def emit(self) -> None:
        passed = all(item["pass"] for item in self.evidence)
        failed = [item["check"] for item in self.evidence if not item["pass"]]
        result = {
            "task_id": self.task_id,
            "pass": passed,
            "reason": "all deterministic checks passed" if passed else f"failed checks: {', '.join(failed)}",
            "evidence": self.evidence,
        }
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if passed else 1)


def normalize(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def phrase(text: str, expected: str) -> bool:
    normalized = normalize(text)
    tokens = re.findall(r"[a-z0-9β]+", normalize(expected))
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"\W+".join(map(re.escape, tokens)) + r"(?![a-z0-9])"
    for match in re.finditer(pattern, normalized):
        clause_start = max(normalized.rfind(mark, 0, match.start()) for mark in ".!?;\n") + 1
        clause_end_candidates = [normalized.find(mark, match.end()) for mark in ".!?;\n"]
        clause_end_candidates = [value for value in clause_end_candidates if value >= 0]
        clause_end = min(clause_end_candidates) if clause_end_candidates else len(normalized)
        clause = normalized[clause_start:clause_end]
        if not re.search(r"\b(?:not|no|never|wrong|incorrect|isn't|wasn't|didn't|doesn't)\b", clause):
            return True
    return False


def has_number(text: str, value: int) -> bool:
    words = {1: "one", 2: "two", 3: "three", 10: "ten"}
    return (
        re.search(rf"(?<!\d){value}(?!\d)", normalize(text)) is not None
        or (value in words and phrase(text, words[value]))
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default="wh-review")
    parser.add_argument("--no_llm", nargs="?", const=True, default=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    args.initial_db = args.initial_db or str(run_dir / "initial.db")
    args.after_db = args.after_db or str(run_dir / "after.db")
    return args


def load_run(run_dir: str) -> dict:
    data = json.loads((Path(run_dir) / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trajectory must be an object")
    data["_run_dir"] = str(Path(run_dir))
    return data


def url_path(url: str) -> str:
    return urlparse(str(url or "")).path.rstrip("/") or "/"


def is_local_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def urls(trajectory: dict) -> list[str]:
    found = []
    if trajectory.get("start_url"):
        found.append(str(trajectory["start_url"]))
    for step in trajectory.get("steps") or []:
        for key in ("url", "url_before", "url_after"):
            if step.get(key):
                found.append(str(step[key]))
    if trajectory.get("final_url"):
        found.append(str(trajectory["final_url"]))
    return found


def visited(trajectory: dict, path: str) -> bool:
    return any(is_local_url(url) and url_path(url) == path for url in urls(trajectory))


def visited_query(trajectory: dict, path: str, **expected: str) -> bool:
    for url in urls(trajectory):
        parsed = urlparse(url)
        if not is_local_url(url) or (parsed.path.rstrip("/") or "/") != path:
            continue
        query = parse_qs(parsed.query, keep_blank_values=True)
        if all(normalize((query.get(key) or [""])[0]) == normalize(value) for key, value in expected.items()):
            return True
    return False


def paths_in_order(trajectory: dict, paths: list[str]) -> bool:
    cursor = 0
    for url in urls(trajectory):
        if cursor < len(paths) and is_local_url(url) and url_path(url) == paths[cursor]:
            cursor += 1
    return cursor == len(paths)


def action_on(trajectory: dict, action: str, path: str, value: str | None = None) -> bool:
    for step in trajectory.get("steps") or []:
        if normalize(step.get("action")) != normalize(action) or url_path(step.get("url")) != path:
            continue
        if value is None:
            return True
        params = step.get("params") or {}
        if any(normalize(item) == normalize(value) for item in params.values()):
            return True
    return False


def database_rows(path: str, table: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()


def table_names(path: str) -> list[str]:
    with sqlite3.connect(path) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]


def schema(path: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()


def changed_tables(initial_db: str, after_db: str) -> set[str]:
    names = set(table_names(initial_db)) | set(table_names(after_db))
    return {name for name in names if database_rows(initial_db, name) != database_rows(after_db, name)}


def user_by_email(path: str, email: str) -> tuple | None:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT id,username,email,display_name,password_hash,due_date,baby_birthdate,parenting_stage FROM user WHERE email=?",
            (email,),
        ).fetchone()


def saves_for(path: str, email: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT s.item_type,s.item_slug,s.note FROM saved_item s JOIN user u ON u.id=s.user_id WHERE u.email=? ORDER BY s.item_type,s.item_slug,s.note",
            (email,),
        ).fetchall()


def check_common(judge: Judge, trajectory: dict, task_id: str, initial_db: str, after_db: str) -> str:
    answer = str(trajectory.get("final_answer") or "").strip()
    judge.check("trajectory_identity", trajectory.get("task_id") == task_id, repr(trajectory.get("task_id")))
    judge.check("terminated", trajectory.get("terminated") is True, repr(trajectory.get("termination_reason")))
    judge.check("answer_present", bool(answer), repr(answer))
    observed_urls = urls(trajectory)
    judge.check("local_origin_only", bool(observed_urls) and all(is_local_url(url) for url in observed_urls), repr(observed_urls))
    judge.check("snapshots_exist", Path(initial_db).is_file() and Path(after_db).is_file(), f"{initial_db} {after_db}")
    if Path(initial_db).is_file() and Path(after_db).is_file():
        judge.check("schema_unchanged", schema(initial_db) == schema(after_db), "sqlite_master")
    run_dir = Path(trajectory["_run_dir"])
    declared = set()
    for step in trajectory.get("steps") or []:
        for key in ("screenshot_before", "screenshot_after"):
            if step.get(key):
                declared.add(str(step[key]))
    screenshots_ok = bool(declared)
    dimensions = []
    for name in sorted(declared):
        path = run_dir / "screenshots" / name
        try:
            header = path.read_bytes()[:24]
            if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                raise ValueError("not a PNG")
            width, height = struct.unpack(">II", header[16:24])
            dimensions.append((name, width, height))
            screenshots_ok &= width >= 320 and height >= 240
        except Exception:
            screenshots_ok = False
    judge.check("screenshots_plausible", screenshots_ok, repr(dimensions))
    return answer


def check_read_only(judge: Judge, initial_db: str, after_db: str) -> None:
    changed = changed_tables(initial_db, after_db)
    judge.check("read_only_state", not changed, repr(sorted(changed)))


def check_login(judge: Judge, trajectory: dict) -> None:
    judge.check("alice_email_entered", action_on(trajectory, "input", "/login", "alice.j@test.com"), "login input")
    judge.check("alice_account_opened", visited(trajectory, "/account"), repr(urls(trajectory)))


def check_only_tables(judge: Judge, initial_db: str, after_db: str, expected: set[str]) -> None:
    changed = changed_tables(initial_db, after_db)
    judge.check("exact_changed_tables", changed == expected, f"expected={sorted(expected)} observed={sorted(changed)}")


def check_phrases(judge: Judge, answer: str, name: str, expected: tuple[str, ...]) -> None:
    missing = [item for item in expected if not phrase(answer, item)]
    judge.check(name, not missing, f"missing={missing!r} answer={answer!r}")


def run_checks(task_number: int, judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    task_id = f"BabyCenter--{task_number}"
    answer = check_common(judge, trajectory, task_id, initial_db, after_db)

    if task_number == 0:
        judge.check("calculator_opened", visited(trajectory, "/due-date-calculator"), repr(urls(trajectory)))
        judge.check("last_period_entered", action_on(trajectory, "input", "/due-date-calculator", "2026-02-20"), "2026-02-20")
        judge.check("cycle_entered", action_on(trajectory, "input", "/due-date-calculator", "31"), "31")
        judge.check("calculation_submitted", action_on(trajectory, "click", "/due-date-calculator", "Calculate"), "Calculate")
        judge.check("linked_week_opened", visited(trajectory, "/pregnancy/week-13"), repr(urls(trajectory)))
        judge.check(
            "answer_due_date",
            re.search(r"\bnov(?:ember)?\W+30\W+2026\b", normalize(answer)) is not None,
            repr(answer),
        )
        judge.check("answer_week", phrase(answer, "week 13"), repr(answer))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 1:
        judge.check("raking_search", visited_query(trajectory, "/search", q="raking grasp"), repr(urls(trajectory)))
        judge.check("month_6_opened", visited(trajectory, "/baby/month-6"), repr(urls(trajectory)))
        raking = re.search(r"\bfingers?\b.*\brake\b.*\bpick", normalize(answer)) is not None
        other_motor = any(
            phrase(answer, item)
            for item in (
                "passing objects between hands",
                "passes objects between hands",
                "sit with support",
                "stand with help",
                "roll from both front to back and back to front",
            )
        )
        judge.check("answer_raking_description", raking, repr(answer))
        judge.check("answer_other_motor", other_motor, repr(answer))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 2:
        judge.check("combined_filters", visited_query(trajectory, "/articles", category="Prenatal Testing", trimester="First trimester"), repr(urls(trajectory)))
        judge.check("screening_article_opened", visited(trajectory, "/articles/prenatal-screening-explained"), repr(urls(trajectory)))
        check_phrases(judge, answer, "answer_serum_and_ultrasound", ("free β-hCG", "PAPP-A", "intact or beta hCG", "h-hCG", "nuchal translucency"))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 3:
        judge.check("combined_filters", visited_query(trajectory, "/articles", category="Prenatal Testing", trimester="Second trimester"), repr(urls(trajectory)))
        judge.check("both_articles_in_order", paths_in_order(trajectory, ["/articles/first-second-third-trimester-screen", "/articles/amniocentesis"]), repr(urls(trajectory)))
        component = any(
            phrase(answer, item)
            for item in ("ultrasound", "blood testing", "serum testing", "maternal blood")
        )
        judge.check("answer_noninvasive_component", component, repr(answer))
        check_phrases(judge, answer, "answer_sample_method", ("needle", "ultrasound guidance", "amniotic fluid"))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 4:
        judge.check("week_comparison_path", paths_in_order(trajectory, ["/pregnancy/week-by-week", "/pregnancy/week-18", "/pregnancy/week-by-week", "/pregnancy/week-20"]), repr(urls(trajectory)))
        check_phrases(judge, answer, "answer_week_facts", ("week 18", "18 to 22 weeks", "week 20", "Quad blood test"))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 5:
        judge.check("week_30_path", paths_in_order(trajectory, ["/pregnancy/week-by-week", "/pregnancy/week-30"]), repr(urls(trajectory)))
        judge.check("answer_rem_timing", phrase(answer, "around 30 weeks"), repr(answer))
        judge.check(
            "answer_rem_share",
            has_number(answer, 80) and ("%" in answer or phrase(answer, "percent")),
            repr(answer),
        )
        check_read_only(judge, initial_db, after_db)
    elif task_number == 6:
        judge.check("month_comparison_path", paths_in_order(trajectory, ["/baby/month-by-month", "/baby/month-2", "/baby/month-by-month", "/baby/month-6"]), repr(urls(trajectory)))
        month2 = phrase(answer, "month 2") and (
            phrase(answer, "hold up the head and chest")
            or phrase(answer, "hold head and chest")
            or phrase(answer, "hold head steady")
            or phrase(answer, "hold the head steady")
        )
        month6 = phrase(answer, "month 6") and (
            phrase(answer, "sit with support")
            or phrase(answer, "sit when supported")
            or phrase(answer, "stand with help")
        )
        judge.check("answer_month_2", month2, repr(answer))
        judge.check("answer_month_6", month6, repr(answer))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 7:
        judge.check("sleep_search", visited_query(trajectory, "/search", q="sleep"), repr(urls(trajectory)))
        judge.check("article_then_thread", paths_in_order(trajectory, ["/articles/infant-sleep-approaches", "/search", "/community/newborn-night-wakings"]), repr(urls(trajectory)))
        feed_reason = (
            re.search(r"\bfeed(?:ing)?\b.*\b(?:frequent|often)", normalize(answer))
            or re.search(r"\bfrequent\b.*\bfeed(?:ing)?\b", normalize(answer))
        )
        judge.check("answer_feeding_reason", bool(feed_reason), repr(answer))
        judge.check(
            "answer_sids_reason",
            phrase(answer, "SIDS protection")
            or (phrase(answer, "SIDS") and phrase(answer, "protect")),
            repr(answer),
        )
        judge.check("answer_reply_count", has_number(answer, 64), repr(answer))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 8:
        judge.check("club_filter", visited_query(trajectory, "/community", club="Starting Solids"), repr(urls(trajectory)))
        judge.check("thread_opened", visited(trajectory, "/community/starting-solids-allergens"), repr(urls(trajectory)))
        judge.check("answer_author", phrase(answer, "PriyaC"), repr(answer))
        judge.check("answer_reply_count", has_number(answer, 22), repr(answer))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 9:
        check_login(judge, trajectory)
        judge.check(
            "answer_current_week",
            phrase(answer, "week 18") or phrase(answer, "pregnancy week is 18"),
            repr(answer),
        )
        judge.check("answer_saved_total", has_number(answer, 2) and phrase(answer, "saved items"), repr(answer))
        check_phrases(judge, answer, "answer_saved_types", ("article", "week"))
        check_read_only(judge, initial_db, after_db)
    elif task_number == 10:
        check_login(judge, trajectory)
        judge.check("article_opened", visited(trajectory, "/articles/infant-sleep-approaches"), repr(urls(trajectory)))
        judge.check("save_clicked", action_on(trajectory, "click", "/articles/infant-sleep-approaches", "Save article"), "Save article")
        judge.check("account_after_save", paths_in_order(trajectory, ["/articles/infant-sleep-approaches", "/account"]), repr(urls(trajectory)))
        before, after = saves_for(initial_db, "alice.j@test.com"), saves_for(after_db, "alice.j@test.com")
        added = [row for row in after if row not in before]
        removed = [row for row in before if row not in after]
        judge.check("exact_saved_delta", added == [("article", "infant-sleep-approaches", "")] and not removed, f"added={added!r} removed={removed!r}")
        check_only_tables(judge, initial_db, after_db, {"saved_item"})
        check_phrases(judge, answer, "answer_saved_target", ("Approaches to infant sleep",))
        judge.check(
            "answer_confirms_save",
            any(phrase(answer, item) for item in ("present", "saved", "appears")),
            repr(answer),
        )
        judge.check("answer_new_total", has_number(answer, 3), repr(answer))
    elif task_number == 11:
        check_login(judge, trajectory)
        judge.check("remove_clicked", action_on(trajectory, "click", "/account", "Remove saved article"), repr(trajectory.get("steps")))
        before, after = saves_for(initial_db, "alice.j@test.com"), saves_for(after_db, "alice.j@test.com")
        target = ("article", "how-births-are-classified", "Benchmark saved article")
        added = [row for row in after if row not in before]
        removed = [row for row in before if row not in after]
        judge.check("exact_removed_delta", removed == [target] and not added, f"added={added!r} removed={removed!r}")
        check_only_tables(judge, initial_db, after_db, {"saved_item"})
        judge.check(
            "answer_confirms_removal",
            any(phrase(answer, item) for item in ("article is gone", "removed", "no longer saved")),
            repr(answer),
        )
        judge.check("answer_remaining_total", has_number(answer, 1) and phrase(answer, "saved item"), repr(answer))
        judge.check("answer_remaining_type", phrase(answer, "week item"), repr(answer))
    elif task_number == 12:
        check_login(judge, trajectory)
        judge.check("name_entered", action_on(trajectory, "input", "/account", "Alice Harper"), "Alice Harper")
        judge.check("profile_submitted", action_on(trajectory, "click", "/account", "Update profile"), "Update profile")
        before = user_by_email(initial_db, "alice.j@test.com")
        after = user_by_email(after_db, "alice.j@test.com")
        expected = list(before) if before else []
        if expected:
            expected[3] = "Alice Harper"
        judge.check("exact_profile_delta", after == tuple(expected), f"before={before!r} after={after!r}")
        check_only_tables(judge, initial_db, after_db, {"user"})
        check_phrases(judge, answer, "answer_name", ("Alice Harper",))
    elif task_number == 13:
        check_login(judge, trajectory)
        judge.check("stage_selected", action_on(trajectory, "select_option", "/account", "Planning for birth"), "Planning for birth")
        judge.check("due_date_entered", action_on(trajectory, "input", "/account", "2026-09-18"), "2026-09-18")
        judge.check("tracker_submitted", action_on(trajectory, "click", "/account", "Update tracker"), "Update tracker")
        before = user_by_email(initial_db, "alice.j@test.com")
        after = user_by_email(after_db, "alice.j@test.com")
        expected = list(before) if before else []
        if expected:
            expected[5] = "2026-09-18"
            expected[6] = None
            expected[7] = "Planning for birth"
        judge.check("exact_tracker_delta", after == tuple(expected), f"before={before!r} after={after!r}")
        check_only_tables(judge, initial_db, after_db, {"user"})
        check_phrases(judge, answer, "answer_tracker", ("Planning for birth", "2026-09-18", "week 24"))
    elif task_number == 14:
        judge.check("register_opened", visited(trajectory, "/register"), repr(urls(trajectory)))
        for value in ("Jordan Lee", "jordan.lee@example.test", "2026-12-18"):
            judge.check(f"registration_input_{value}", action_on(trajectory, "input", "/register", value), value)
        judge.check("registration_submitted", action_on(trajectory, "click", "/register", "Create profile"), "Create profile")
        judge.check("account_opened", visited(trajectory, "/account"), repr(urls(trajectory)))
        judge.check("not_preexisting", user_by_email(initial_db, "jordan.lee@example.test") is None, "initial user")
        added_user = user_by_email(after_db, "jordan.lee@example.test")
        judge.check("exact_new_user", bool(added_user) and added_user[2:4] == ("jordan.lee@example.test", "Jordan Lee") and added_user[5:] == ("2026-12-18", None, "Pregnancy"), repr(added_user))
        judge.check("new_user_has_no_saves", saves_for(after_db, "jordan.lee@example.test") == [], repr(saves_for(after_db, "jordan.lee@example.test")))
        check_only_tables(judge, initial_db, after_db, {"user"})
        check_phrases(judge, answer, "answer_registration", ("Jordan Lee", "jordan.lee@example.test", "week 10"))
    else:
        judge.check("known_task", False, str(task_number))


def fail_closed(task_id: str, error: Exception) -> None:
    print(json.dumps({
        "task_id": task_id,
        "pass": False,
        "reason": f"verifier_error: {type(error).__name__}: {error}",
        "evidence": [],
    }))
    raise SystemExit(1)


def main(task_number: int) -> None:
    task_id = f"BabyCenter--{task_number}"
    try:
        args = parse_args()
        trajectory = load_run(args.run_dir)
        judge = Judge(task_id)
        run_checks(task_number, judge, trajectory, args.initial_db, args.after_db)
        judge.emit()
    except SystemExit:
        raise
    except Exception as error:
        fail_closed(task_id, error)
