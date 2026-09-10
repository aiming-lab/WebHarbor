#!/usr/bin/env python3
"""Shared deterministic verifier for BoardGameGeek tasks."""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import parse_qs, urlparse


PASSWORD = "TestPass123!"
KNOWN_GAME_SUBPAGES = {"ratings", "credits", "expansions", "forums"}


@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str | None
    after_db: str | None
    no_llm: bool


def _bool_value(value: str) -> bool:
    return str(value).casefold() in {"1", "true", "yes", "on"}


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default="")  # compatibility with agent_demo
    parser.add_argument("--no_llm", nargs="?", const=True, default=False, type=_bool_value)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    initial = args.initial_db or str(run_dir / "initial.db")
    after = args.after_db or str(run_dir / "after.db")
    return VerifyArgs(
        run_dir=str(run_dir),
        initial_db=initial if Path(initial).is_file() else None,
        after_db=after if Path(after).is_file() else None,
        no_llm=bool(args.no_llm),
    )


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    data = json.loads((Path(run_dir) / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trajectory.json must be a JSON object")
    return data


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def plain_html(value: Any) -> str:
    return normalize_text(html.unescape(re.sub(r"<[^>]+>", " ", str(value or ""))))


def final_answer(trajectory: dict[str, Any]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for value in [trajectory.get("start_url")]:
        if value:
            urls.append(str(value))
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url_before", "url", "url_after"):
            value = str(step.get(key) or "")
            if value and (not urls or value != urls[-1]):
                urls.append(value)
    final = str(trajectory.get("final_url") or "")
    if final and (not urls or final != urls[-1]):
        urls.append(final)
    return urls


def _is_loopback(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def is_target_url(url: str, trajectory: dict[str, Any]) -> bool:
    parsed = urlparse(str(url or ""))
    start = urlparse(str(trajectory.get("start_url") or ""))
    return bool(
        parsed.scheme in {"http", "https"}
        and start.scheme == parsed.scheme
        and parsed.hostname
        and start.hostname
        and _is_loopback(parsed.hostname)
        and _is_loopback(start.hostname)
        and parsed.port == start.port
    )


def normalized_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def query_matches(url: str, expected: dict[str, str]) -> bool:
    observed = parse_qs(urlparse(url).query)
    return all(
        normalize_text((observed.get(key) or [""])[0]) == normalize_text(value)
        for key, value in expected.items()
    )


def target_urls(trajectory: dict[str, Any]) -> list[str]:
    return [url for url in trajectory_urls(trajectory) if is_target_url(url, trajectory)]


def visited_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    return any(normalized_path(url) == expected for url in target_urls(trajectory))


def visited_query(trajectory: dict[str, Any], path: str, expected: dict[str, str]) -> bool:
    wanted = normalized_path(path)
    return any(
        normalized_path(url) == wanted and query_matches(url, expected)
        for url in target_urls(trajectory)
    )


def _game_path_matches(path: str, bgg_id: int, subpage: str | None = None) -> bool:
    parts = normalized_path(path).strip("/").split("/")
    if len(parts) < 2 or parts[0] != "boardgame" or parts[1] != str(bgg_id):
        return False
    if subpage is None:
        return len(parts) == 2 or (
            len(parts) == 3 and parts[2] not in KNOWN_GAME_SUBPAGES
        )
    return (len(parts) == 3 and parts[2] == subpage) or (
        len(parts) == 4 and parts[3] == subpage
    )


def visited_game(trajectory: dict[str, Any], bgg_id: int, subpage: str | None = None) -> bool:
    return any(
        _game_path_matches(url, bgg_id, subpage) for url in target_urls(trajectory)
    )


def visited_entity(trajectory: dict[str, Any], prefix: str, bgg_id: int) -> bool:
    for url in target_urls(trajectory):
        parts = normalized_path(url).strip("/").split("/")
        if len(parts) in {2, 3} and parts[:2] == [prefix, str(bgg_id)]:
            return True
    return False


def ordered(trajectory: dict[str, Any], predicates: Sequence[Callable[[str], bool]]) -> bool:
    urls = target_urls(trajectory)
    cursor = 0
    for predicate in predicates:
        for index in range(cursor, len(urls)):
            if predicate(urls[index]):
                cursor = index + 1
                break
        else:
            return False
    return True


def path_predicate(path: str, query: dict[str, str] | None = None) -> Callable[[str], bool]:
    expected_path = normalized_path(path)
    expected_query = query or {}
    return lambda url: normalized_path(url) == expected_path and query_matches(url, expected_query)


def game_predicate(bgg_id: int, subpage: str | None = None) -> Callable[[str], bool]:
    return lambda url: _game_path_matches(url, bgg_id, subpage)


def transition_pairs(trajectory: dict[str, Any]):
    steps = trajectory.get("steps") or []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        current = str(step.get("url") or step.get("url_before") or "")
        if not is_target_url(current, trajectory):
            continue
        following = str(step.get("url_after") or "")
        if not following and index + 1 < len(steps) and isinstance(steps[index + 1], dict):
            following = str(
                steps[index + 1].get("url")
                or steps[index + 1].get("url_before")
                or ""
            )
        if following and is_target_url(following, trajectory):
            yield normalize_text(step.get("action")), current, following


def submitted_from(trajectory: dict[str, Any], predicate: Callable[[str], bool]) -> bool:
    return any(
        action in {"click", "press", "submit"} and predicate(current)
        for action, current, _ in transition_pairs(trajectory)
    )


def input_values(trajectory: dict[str, Any], predicate: Callable[[str], bool] | None = None) -> list[str]:
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if normalize_text(step.get("action")) not in {"input", "fill", "type", "select"}:
            continue
        url = str(step.get("url") or step.get("url_before") or "")
        if not is_target_url(url, trajectory) or (predicate and not predicate(url)):
            continue
        params = step.get("params") or {}
        if not isinstance(params, dict):
            continue
        value = params.get("text", params.get("value", params.get("option", params.get("label"))))
        if value is not None:
            values.append(str(value))
    return values


def entered_exact(trajectory: dict[str, Any], value: str, predicate: Callable[[str], bool] | None = None) -> bool:
    expected = normalize_text(value)
    return any(normalize_text(item) == expected for item in input_values(trajectory, predicate))


def entered_contains(trajectory: dict[str, Any], value: str, predicate: Callable[[str], bool] | None = None) -> bool:
    expected = normalize_text(value)
    return any(expected in normalize_text(item) for item in input_values(trajectory, predicate))


def login_submitted_as(trajectory: dict[str, Any], username: str) -> bool:
    predicate = path_predicate("/login")
    return (
        visited_path(trajectory, "/login")
        and entered_exact(trajectory, username, predicate)
        and entered_exact(trajectory, PASSWORD, predicate)
        and submitted_from(trajectory, predicate)
    )


NEGATIONS = {"not", "no", "never", "without", "isn't", "isnt", "wasn't", "wasnt", "didn't", "didnt"}


def _negated_at(text: str, start: int) -> bool:
    clause = re.split(r"[.!?;:\n]+|\b(?:and|but|however|instead)\b", text[:start])[-1]
    return any(word in NEGATIONS for word in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", clause))


def affirmative_contains(value: Any, expected: Any) -> bool:
    text = normalize_text(value)
    needle = normalize_text(expected)
    matches = list(re.finditer(re.escape(needle), text)) if needle else []
    return bool(matches and not _negated_at(text, matches[-1].start()))


def contains_all(value: Any, expected: Iterable[Any]) -> bool:
    return all(affirmative_contains(value, item) for item in expected)


def number_matches(value: Any, expected: float, tolerance: float = 0.005) -> bool:
    text = normalize_text(value)
    for match in re.finditer(r"(?<![a-z0-9])\d[\d,]*(?:\.\d+)?(?![a-z0-9])", text):
        observed = float(match.group(0).replace(",", ""))
        if abs(observed - float(expected)) <= tolerance and not _negated_at(text, match.start()):
            return True
    return False


def number_bound_to(value: Any, expected: float, labels: Sequence[str], tolerance: float = 0.005, distance: int = 100) -> bool:
    text = normalize_text(value)
    for match in re.finditer(r"(?<![a-z0-9])\d[\d,]*(?:\.\d+)?(?![a-z0-9])", text):
        observed = float(match.group(0).replace(",", ""))
        if abs(observed - float(expected)) > tolerance or _negated_at(text, match.start()):
            continue
        window = text[max(0, match.start() - distance):match.end() + distance]
        if any(normalize_text(label) in window for label in labels):
            return True
    return False


def claims_heavier(value: Any, winner: str, loser: str) -> bool:
    text = normalize_text(value)
    return (
        affirmative_contains(text, winner)
        and affirmative_contains(text, loser)
        and any(word in text for word in ("heavier", "higher", "more complex", "greater"))
    )


def db_rows(path: str, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def row_dicts(path: str, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db_rows(path, sql, params)]


def table_rows(path: str, table: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_rows(path, f'SELECT * FROM "{table}" ORDER BY rowid')]


def table_names(path: str) -> list[str]:
    return [
        str(row["name"])
        for row in db_rows(
            path,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
    ]


def changed_tables(initial: str, after: str) -> set[str]:
    if table_names(initial) != table_names(after):
        return {"<schema>"}
    return {
        table
        for table in table_names(initial)
        if table_rows(initial, table) != table_rows(after, table)
    }


def rows_by_id(path: str, table: str) -> dict[int, tuple[Any, ...]]:
    return {int(row[0]): tuple(row) for row in db_rows(path, f'SELECT * FROM "{table}" ORDER BY id')}


class Judge:
    def __init__(self, task_number: int):
        self.task_id = f"BoardGameGeek--{task_number}"
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "") -> bool:
        self.evidence.append(f"[{'PASS' if condition else 'FAIL'}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return bool(condition)

    def emit(self) -> None:
        print(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "pass": self.passed,
                    "reason": self.reason,
                    "evidence": self.evidence,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(0 if self.passed else 1)


def _require_common(judge: Judge, task_number: int, trajectory: dict[str, Any], args: VerifyArgs) -> tuple[str, str] | None:
    answer = final_answer(trajectory)
    judge.check("task_id_matches", trajectory.get("task_id") == judge.task_id, repr(trajectory.get("task_id")))
    judge.check("final_answer_nonempty", bool(answer), repr(answer))
    judge.check("start_url_is_target", is_target_url(str(trajectory.get("start_url") or ""), trajectory), repr(trajectory.get("start_url")))
    readable = bool(args.initial_db and args.after_db)
    judge.check("databases_readable", readable, f"initial={args.initial_db} after={args.after_db}")
    return (args.initial_db, args.after_db) if readable else None


def _read_only(judge: Judge, initial: str, after: str) -> None:
    changes = changed_tables(initial, after)
    judge.check("read_only_database_unchanged", not changes, repr(changes))


def _answer_numbers(judge: Judge, answer: str, facts: Sequence[tuple[float, Sequence[str], float]]) -> None:
    for number, labels, tolerance in facts:
        judge.check(
            f"answer_{normalize_text(labels[0]).replace(' ', '_')}",
            number_bound_to(answer, number, labels, tolerance),
            repr(answer),
        )


def _verify_read_task(task: int, trajectory: dict[str, Any], answer: str, initial: str, judge: Judge) -> None:
    if task == 0:
        game = row_dicts(initial, "SELECT * FROM games WHERE overall_rank=1")[0]
        designers = row_dicts(initial, "SELECT p.name FROM people p JOIN game_designers gd ON gd.person_id=p.id WHERE gd.game_id=?", (game["id"],))
        judge.check("browse_then_rank_one_detail", ordered(trajectory, [path_predicate("/browse/boardgame"), game_predicate(game["bgg_id"])]), game["name"])
        judge.check("answer_game_and_all_designers", contains_all(answer, [game["name"], *[row["name"] for row in designers]]), repr(answer))
    elif task == 1:
        game = row_dicts(initial, "SELECT * FROM games WHERE name='Gloomhaven'")[0]
        judge.check("search_then_game_detail", ordered(trajectory, [path_predicate("/search", {"q": "Gloomhaven"}), game_predicate(game["bgg_id"])]), game["name"])
        _answer_numbers(judge, answer, [(game["avg_rating"], ("average", "rating"), 0.005), (game["weight"], ("weight", "complexity"), 0.005), (game["num_ratings"], ("voters", "ratings"), 0.0)])
    elif task == 2:
        game = row_dicts(initial, "SELECT * FROM (SELECT * FROM games WHERE subtype='boardgame' ORDER BY weight DESC LIMIT 100) WHERE overall_rank BETWEEN 1 AND 100 ORDER BY weight DESC LIMIT 1")[0]
        judge.check("weight_sorted_first_page", visited_query(trajectory, "/browse/boardgame", {"sort": "weight", "dir": "desc"}), "sort=weight&dir=desc")
        judge.check("answer_game_and_weight", affirmative_contains(answer, game["name"]) and number_bound_to(answer, game["weight"], ("weight", "complexity"), 0.005), repr(answer))
    elif task == 3:
        game = row_dicts(initial, "SELECT g.* FROM games g JOIN game_mechanics gm ON gm.game_id=g.id JOIN mechanics m ON m.id=gm.mechanic_id WHERE m.name='Worker Placement' AND g.overall_rank>0 ORDER BY g.overall_rank LIMIT 1")[0]
        designers = row_dicts(initial, "SELECT p.name FROM people p JOIN game_designers gd ON gd.person_id=p.id WHERE gd.game_id=?", (game["id"],))
        judge.check("mechanism_then_game_detail", ordered(trajectory, [path_predicate("/boardgamemechanic"), lambda url: normalized_path(url).startswith("/boardgamemechanic/2082"), game_predicate(game["bgg_id"])]), game["name"])
        judge.check("answer_game_and_designers", contains_all(answer, [game["name"], *[row["name"] for row in designers]]), repr(answer))
    elif task == 4:
        count = db_rows(initial, "SELECT COUNT(*) n FROM collections c JOIN users u ON u.id=c.user_id WHERE u.username='alice_j' AND c.own=1")[0]["n"]
        judge.check("login_then_owned_collection", login_submitted_as(trajectory, "alice_j") and ordered(trajectory, [path_predicate("/login"), path_predicate("/collection/alice_j")]), "alice_j")
        judge.check("answer_owned_count", number_bound_to(answer, count, ("owned", "collection", "games"), 0.0), repr(answer))
    elif task == 7:
        latest_year = db_rows(initial, "SELECT MAX(year_published) year FROM games WHERE featured=1")[0]["year"]
        game = row_dicts(initial, "SELECT * FROM games WHERE featured=1 AND year_published=? AND overall_rank>0 ORDER BY overall_rank LIMIT 1", (latest_year,))[0]
        judge.check("hot_page_visited", visited_path(trajectory, "/hotness") or visited_path(trajectory, "/hot"), "hotness alias accepted")
        judge.check("answer_latest_year_and_highest_ranked_game", affirmative_contains(answer, game["name"]) and number_matches(answer, latest_year, 0.0), repr(answer))
    elif task == 8:
        data = row_dicts(
            initial,
            """
            SELECT l.id list_id,l.title,i.position,g.name,g.bgg_id,g.weight
            FROM geeklists l
            JOIN geeklist_items i ON i.list_id=l.id
            JOIN games g ON g.id=i.game_id
            WHERE l.title='Best Cooperative Games' AND i.position=7
            """,
        )[0]
        judge.check(
            "target_list_then_seventh_game_detail",
            ordered(
                trajectory,
                [path_predicate(f"/geeklist/{data['list_id']}"), game_predicate(data["bgg_id"])],
            ),
            f"{data['title']} #7 = {data['name']}",
        )
        judge.check(
            "answer_seventh_game_and_weight",
            affirmative_contains(answer, data["name"])
            and number_bound_to(answer, data["weight"], ("weight", "complexity"), 0.005),
            repr(answer),
        )
    elif task == 10:
        games = {row["name"]: row for row in row_dicts(initial, "SELECT name,bgg_id,weight FROM games WHERE name IN ('Brass: Birmingham','Ark Nova')")}
        judge.check("both_game_pages_visited", visited_game(trajectory, games["Brass: Birmingham"]["bgg_id"]) and visited_game(trajectory, games["Ark Nova"]["bgg_id"]), "both details")
        judge.check("answer_identifies_heavier_game", claims_heavier(answer, "Brass: Birmingham", "Ark Nova"), repr(answer))
    elif task == 11:
        publisher = row_dicts(initial, "SELECT * FROM publishers WHERE name='Z-Man Games'")[0]
        count = db_rows(initial, "SELECT COUNT(*) n FROM game_publishers WHERE publisher_id=?", (publisher["id"],))[0]["n"]
        judge.check("publisher_index_then_detail", ordered(trajectory, [path_predicate("/boardgamepublisher"), lambda url: normalized_path(url).startswith(f"/boardgamepublisher/{publisher['bgg_id']}")]), publisher["name"])
        judge.check("answer_publisher_count", number_bound_to(answer, count, ("games", "listed", "catalog"), 0.0), repr(answer))
    elif task == 12:
        game = row_dicts(initial, "SELECT g.* FROM games g JOIN game_mechanics gm ON gm.game_id=g.id JOIN mechanics m ON m.id=gm.mechanic_id WHERE m.name='Action Points' AND g.overall_rank>0 ORDER BY g.overall_rank LIMIT 1")[0]
        judge.check("mechanisms_then_action_points", ordered(trajectory, [path_predicate("/boardgamemechanic"), lambda url: normalized_path(url).startswith("/boardgamemechanic/2001")]), "Action Points")
        judge.check("answer_game_and_rank", affirmative_contains(answer, game["name"]) and number_bound_to(answer, game["overall_rank"], ("rank", "#"), 0.0), repr(answer))
    elif task == 14:
        game = row_dicts(initial, "SELECT * FROM games WHERE name='Wingspan'")[0]
        top = row_dicts(initial, "SELECT u.username,r.num_thumbs FROM ratings r JOIN users u ON u.id=r.user_id WHERE r.game_id=? ORDER BY r.num_thumbs DESC,r.value DESC LIMIT 1", (game["id"],))[0]
        judge.check("detail_then_helpful_ratings", ordered(trajectory, [game_predicate(game["bgg_id"]), lambda url: _game_path_matches(url, game["bgg_id"], "ratings") and query_matches(url, {"sort": "thumbs"})]), game["name"])
        judge.check("answer_user_and_thumbs", affirmative_contains(answer, top["username"]) and number_bound_to(answer, top["num_thumbs"], ("thumb", "helpful"), 0.0), repr(answer))
    elif task == 16:
        data = row_dicts(initial, "SELECT l.id,l.title,g.name FROM geeklists l JOIN geeklist_items i ON i.list_id=l.id JOIN games g ON g.id=i.game_id WHERE l.title='Top 50 Heaviest Games of the Last Decade' AND i.position=1")[0]
        judge.check("geeklists_then_target_list", ordered(trajectory, [path_predicate("/geeklists"), path_predicate(f"/geeklist/{data['id']}")]), data["title"])
        judge.check("answer_first_entry", affirmative_contains(answer, data["name"]), repr(answer))
    elif task == 17:
        count = db_rows(initial, "SELECT COUNT(DISTINCT p.game_id) n FROM plays p JOIN users u ON u.id=p.user_id WHERE u.username='david_k'")[0]["n"]
        judge.check("login_then_plays", login_submitted_as(trajectory, "david_k") and ordered(trajectory, [path_predicate("/login"), path_predicate("/plays/david_k")]), "david_k")
        judge.check("answer_distinct_game_count", number_bound_to(answer, count, ("distinct", "games"), 0.0), repr(answer))
    elif task == 18:
        designer = row_dicts(initial, "SELECT * FROM people WHERE name='Vital Lacerda'")[0]
        game = row_dicts(initial, "SELECT g.* FROM games g JOIN game_designers gd ON gd.game_id=g.id WHERE gd.person_id=? ORDER BY g.avg_rating DESC LIMIT 1", (designer["id"],))[0]
        judge.check("designer_index_then_detail", ordered(trajectory, [path_predicate("/boardgamedesigner"), lambda url: normalized_path(url).startswith(f"/boardgamedesigner/{designer['bgg_id']}")]), designer["name"])
        judge.check("answer_highest_average_game", affirmative_contains(answer, game["name"]), repr(answer))
    elif task == 19:
        user = row_dicts(initial, "SELECT * FROM users WHERE lower(username) LIKE '%mike%' OR lower(real_name) LIKE '%mike%' ORDER BY username ASC LIMIT 1")[0]
        count = db_rows(initial, "SELECT COUNT(*) n FROM geeklists WHERE author_id=?", (user["id"],))[0]["n"]
        judge.check("user_search_then_first_profile", ordered(trajectory, [lambda url: normalized_path(url) == "/search" and query_matches(url, {"q": "mike", "type": "user"}), path_predicate(f"/user/{user['username']}")]), user["username"])
        judge.check("answer_username_and_geeklist_count", affirmative_contains(answer, user["username"]) and number_bound_to(answer, count, ("geeklists", "authored"), 0.0), repr(answer))
    elif task == 20:
        game = row_dicts(initial, "SELECT * FROM games WHERE name='Twilight Struggle'")[0]
        count = db_rows(initial, "SELECT COUNT(*) n FROM game_links WHERE game_id=? AND kind='expansion'", (game["id"],))[0]["n"]
        judge.check("detail_then_expansions", ordered(trajectory, [game_predicate(game["bgg_id"]), game_predicate(game["bgg_id"], "expansions")]), game["name"])
        judge.check("answer_expansion_count", number_bound_to(answer, count, ("expansions", "listed"), 0.0), repr(answer))
    else:
        raise ValueError(f"unsupported read task {task}")


def _verify_task_5(trajectory: dict[str, Any], answer: str, initial: str, after: str, judge: Judge) -> None:
    game = row_dicts(initial, "SELECT * FROM games WHERE name='Brass: Birmingham'")[0]
    user = row_dicts(initial, "SELECT * FROM users WHERE username='bob_c'")[0]
    game_path = game_predicate(game["bgg_id"])
    judge.check("login_and_rating_flow", login_submitted_as(trajectory, "bob_c") and ordered(trajectory, [path_predicate("/login"), game_path]) and entered_exact(trajectory, "9.5", game_path) and submitted_from(trajectory, game_path), "bob_c -> Brass -> submit")
    before = row_dicts(initial, "SELECT * FROM ratings WHERE user_id=? AND game_id=?", (user["id"], game["id"]))
    now = row_dicts(after, "SELECT * FROM ratings WHERE user_id=? AND game_id=?", (user["id"], game["id"]))
    judge.check("rating_was_new", before == [], repr(before))
    exact = len(now) == 1 and now[0]["value"] == 9.5 and len(plain_html(now[0]["review_html"])) >= 8
    sentence_marks = re.findall(r"[.!?]+(?:\s|$)", plain_html(now[0]["review_html"])) if now else []
    judge.check("one_sentence_rating_saved", exact and len(sentence_marks) <= 1, repr(now))
    after_game = row_dicts(after, "SELECT * FROM games WHERE id=?", (game["id"],))[0]
    expected = (game["avg_rating"] * game["num_ratings"] + 9.5) / (game["num_ratings"] + 1)
    judge.check("aggregate_updated_once", after_game["num_ratings"] == game["num_ratings"] + 1 and abs(after_game["avg_rating"] - expected) < 1e-12, f"expected={expected} after={after_game['avg_rating']}")
    judge.check("only_rating_and_game_changed", changed_tables(initial, after) == {"games", "ratings"}, repr(changed_tables(initial, after)))


def _verify_task_6(trajectory: dict[str, Any], answer: str, initial: str, after: str, judge: Judge) -> None:
    game = row_dicts(initial, "SELECT DISTINCT g.* FROM games g JOIN game_mechanics gm ON gm.game_id=g.id JOIN mechanics m ON m.id=gm.mechanic_id WHERE g.subtype='boardgame' AND g.minplayers=2 AND g.maxplayers=2 AND g.overall_rank>0 AND m.name IN ('Deck Construction','Deck, Bag, and Pool Building') ORDER BY g.overall_rank LIMIT 1")[0]
    user = row_dicts(initial, "SELECT * FROM users WHERE username='carol_d'")[0]
    judge.check("login_and_both_mechanism_pages", login_submitted_as(trajectory, "carol_d") and visited_entity(trajectory, "boardgamemechanic", 3004) and visited_entity(trajectory, "boardgamemechanic", 2664), "both mechanism categories")
    game_path = game_predicate(game["bgg_id"])
    judge.check("target_game_opened_and_submitted", visited_game(trajectory, game["bgg_id"]) and submitted_from(trajectory, game_path), game["name"])
    before = row_dicts(initial, "SELECT * FROM collections WHERE user_id=? AND game_id=?", (user["id"], game["id"]))
    now = row_dicts(after, "SELECT * FROM collections WHERE user_id=? AND game_id=?", (user["id"], game["id"]))
    exact = len(now) == 1 and now[0]["wishlist"] == 1 and now[0]["wishlist_priority"] == 1
    judge.check("must_have_wishlist_added", before == [] and exact, repr(now))
    judge.check("only_collections_changed", changed_tables(initial, after) == {"collections"}, repr(changed_tables(initial, after)))


def _verify_task_9(trajectory: dict[str, Any], answer: str, initial: str, after: str, judge: Judge) -> None:
    user = row_dicts(initial, "SELECT * FROM users WHERE username='david_k'")[0]
    title = "My COIN Series Picks"
    description = "Light, deep, and historical."
    form = path_predicate("/geeklist/new")
    judge.check("login_and_new_list_form", login_submitted_as(trajectory, "david_k") and ordered(trajectory, [path_predicate("/login"), form]) and entered_exact(trajectory, title, form) and entered_exact(trajectory, description, form) and submitted_from(trajectory, form), "exact title and description")
    before_ids = {row["id"] for row in row_dicts(initial, "SELECT * FROM geeklists")}
    after_rows = row_dicts(after, "SELECT * FROM geeklists ORDER BY id")
    created = [row for row in after_rows if row["id"] not in before_ids]
    exact = len(created) == 1 and created[0]["author_id"] == user["id"] and created[0]["title"] == title and plain_html(created[0]["description_html"]) == normalize_text(description) and created[0]["num_items"] == 0
    judge.check("one_exact_geeklist_created", exact, repr(created))
    judge.check("created_list_opened", len(created) == 1 and visited_path(trajectory, f"/geeklist/{created[0]['id']}"), repr(created))
    judge.check("only_geeklists_changed", changed_tables(initial, after) == {"geeklists"}, repr(changed_tables(initial, after)))


def _verify_task_13(trajectory: dict[str, Any], answer: str, initial: str, after: str, judge: Judge) -> None:
    user = row_dicts(initial, "SELECT * FROM users WHERE username='alice_j'")[0]
    entry = row_dicts(initial, "SELECT c.*,g.bgg_id,g.name FROM collections c JOIN games g ON g.id=c.game_id WHERE c.user_id=? AND c.own=1 ORDER BY c.updated_at DESC LIMIT 1", (user["id"],))[0]
    collection_seen = visited_query(trajectory, "/collection/alice_j", {"sort": "recent"})
    game_path = game_predicate(entry["bgg_id"])
    judge.check("login_recent_collection_remove_flow", login_submitted_as(trajectory, "alice_j") and collection_seen and ordered(trajectory, [path_predicate("/login"), lambda url: normalized_path(url) == "/collection/alice_j" and query_matches(url, {"sort": "recent"}), game_path]) and submitted_from(trajectory, game_path), entry["name"])
    before = rows_by_id(initial, "collections")
    now = rows_by_id(after, "collections")
    judge.check("only_most_recent_entry_removed", entry["id"] in before and entry["id"] not in now and len(now) == len(before) - 1 and all(row == now.get(row_id) for row_id, row in before.items() if row_id != entry["id"]), entry["name"])
    judge.check("only_collections_changed", changed_tables(initial, after) == {"collections"}, repr(changed_tables(initial, after)))


def _verify_task_15(trajectory: dict[str, Any], answer: str, initial: str, after: str, judge: Judge) -> None:
    user = row_dicts(initial, "SELECT * FROM users WHERE username='bob_c'")[0]
    eligible = row_dicts(initial, "SELECT t.*,f.id forum_id FROM threads t JOIN forums f ON f.id=t.forum_id WHERE f.title='Recommendations' AND t.is_pinned=0 AND t.is_locked=0 AND (lower(t.subject) LIKE '%2 player%' OR lower(t.subject) LIKE '%two-player%')")
    eligible_ids = {row["id"] for row in eligible}
    visited_ids = {row["id"] for row in eligible if visited_path(trajectory, f"/thread/{row['id']}")}
    chosen = next(iter(visited_ids), None)
    predicate = path_predicate(f"/thread/{chosen}") if chosen else lambda _url: False
    judge.check("login_forum_open_thread_flow", login_submitted_as(trajectory, "bob_c") and visited_path(trajectory, "/forums") and visited_path(trajectory, "/forum/3") and bool(visited_ids), repr(eligible_ids))
    judge.check("reply_phrase_entered_and_submitted", chosen is not None and entered_contains(trajectory, "7 Wonders Duel", predicate) and submitted_from(trajectory, predicate), repr(chosen))
    before_ids = {row["id"] for row in row_dicts(initial, "SELECT * FROM posts")}
    new_posts = [row for row in row_dicts(after, "SELECT * FROM posts") if row["id"] not in before_ids]
    exact = len(new_posts) == 1 and new_posts[0]["thread_id"] in eligible_ids and new_posts[0]["author_id"] == user["id"] and "7 wonders duel" in plain_html(new_posts[0]["body_html"])
    judge.check("one_exact_reply_saved", exact, repr(new_posts))
    if exact:
        tid = new_posts[0]["thread_id"]
        before_thread = row_dicts(initial, "SELECT * FROM threads WHERE id=?", (tid,))[0]
        after_thread = row_dicts(after, "SELECT * FROM threads WHERE id=?", (tid,))[0]
        before_forum = row_dicts(initial, "SELECT * FROM forums WHERE id=?", (before_thread["forum_id"],))[0]
        after_forum = row_dicts(after, "SELECT * FROM forums WHERE id=?", (before_thread["forum_id"],))[0]
        judge.check("thread_and_forum_counts_incremented", after_thread["num_posts"] == before_thread["num_posts"] + 1 and after_forum["num_posts"] == before_forum["num_posts"] + 1, f"thread={before_thread['num_posts']}->{after_thread['num_posts']} forum={before_forum['num_posts']}->{after_forum['num_posts']}")
    judge.check("only_forum_reply_tables_changed", changed_tables(initial, after) == {"forums", "posts", "threads"}, repr(changed_tables(initial, after)))


def run_task(task_number: int) -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    judge = Judge(task_number)
    databases = _require_common(judge, task_number, trajectory, args)
    if databases:
        initial, after = databases
        if task_number == 5:
            _verify_task_5(trajectory, answer, initial, after, judge)
        elif task_number == 6:
            _verify_task_6(trajectory, answer, initial, after, judge)
        elif task_number == 9:
            _verify_task_9(trajectory, answer, initial, after, judge)
        elif task_number == 13:
            _verify_task_13(trajectory, answer, initial, after, judge)
        elif task_number == 15:
            _verify_task_15(trajectory, answer, initial, after, judge)
        else:
            _verify_read_task(task_number, trajectory, answer, initial, judge)
            _read_only(judge, initial, after)
    judge.emit()
