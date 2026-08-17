#!/usr/bin/env python3
"""Deterministic grading helpers for the Cookpad benchmark tasks.

Every task requires both a frozen answer and task-specific navigation. Tasks
12 and 13 additionally compare seed and live SQLite databases so that a
self-reported write cannot pass without the requested state transition.
"""
import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


SITE = "cookpad"
TASK_COUNT = 19
STATEFUL_TASKS = {12, 13}


def _alt(*groups):
    """One valid navigation alternative made from required URL groups."""
    return tuple(tuple(group) if isinstance(group, (list, tuple)) else (group,)
                 for group in groups)


NAV_ALTERNATIVES = {
    0: (
        _alt(("/category/breakfast", "/breakfast"), "/recipe/pancakes"),
        _alt("/search", "/recipe/pancakes"),
    ),
    1: (_alt("/search", "q=banana", "/recipe/banana-bread"),),
    2: (_alt("/category/japanese",
             "/recipe/eggplant-lemon-pepper-bowl-japanese-137"),),
    3: (_alt("/search", "q=miso", "/recipe/miso-soup"),),
    4: (
        _alt("/category/asian", (
            "/recipe/creamy-tomato-rice-with-tofu-asian-",
            "/recipe/herb-roasted-rice-with-tofu-asian-",
            "/recipe/miso-butter-rice-with-tofu-asian-",
            "/recipe/lemon-pepper-rice-with-tofu-asian-",
            "/recipe/chili-crisp-rice-with-tofu-asian-",
        )),
        _alt("/search", "q=tofu", (
            "/recipe/creamy-tomato-rice-with-tofu-asian-",
            "/recipe/herb-roasted-rice-with-tofu-asian-",
            "/recipe/miso-butter-rice-with-tofu-asian-",
            "/recipe/lemon-pepper-rice-with-tofu-asian-",
            "/recipe/chili-crisp-rice-with-tofu-asian-",
        )),
    ),
    5: (_alt("/category/desserts", "/recipe/chocolate-chip-cookies"),),
    6: (_alt("/recipe/banana-bread"),),
    7: (_alt("/login", ("/favorites", "/recipe-box")),),
    8: (_alt("/login", "/meal-plan"),),
    9: (_alt("/login", "/shopping-list"),),
    10: (_alt("/help", "q=shopping", "/help/shopping-list-overview"),),
    11: (_alt("/authors/mika-tanaka"),),
    12: (_alt("/login", "/shopping-list"),),
    13: (_alt("/login", "/meal-plan"),),
    14: (_alt("/login", ("/favorites", "/recipe-box")),),
    15: (_alt("/login", "/shopping-list"),),
    16: (_alt("/help", "q=saved", "/help/saving-recipes"),),
    17: (_alt("/recipe/worlds-best-lasagna",
              "/recipe/chocolate-chip-cookies"),),
    18: (_alt("/category/meal-prep",
              "/recipe/chicken-lemon-pepper-bowl-meal-prep-97"),),
}


PASS_ANSWERS = {
    0: "Good Old-Fashioned Pancakes has a total time of 20 minutes.",
    1: "The most-reviewed banana bread was authored by Shelley Albeluhn.",
    2: "Eggplant Lemon Pepper Bowl has a total time of 1 hour.",
    3: "Miso Soup takes 15 minutes and shows 1,820 reviews.",
    4: "Creamy Tomato Rice with Tofu.",
    5: "Chocolate Chip Cookies has 15,600 reviews.",
    6: "Preheat oven to 350 degrees F (175 degrees C). Lightly grease a 9x5-inch loaf pan.",
    7: "The saved recipe is Scallion and Pork Plate.",
    8: "Guacamole is scheduled for Monday breakfast.",
    9: "The first two items are lasagna noodles and ricotta cheese.",
    10: "It is only local to the benchmark mirror; there is no grocery ordering or delivery integration.",
    11: "Chicken Lemon Pepper Bowl is one of the most-reviewed recipes.",
    12: "Created the Cookpad Staples shopping list.",
    13: "Added Waffles to Sunday dinner.",
    14: "Teriyaki Salmon is the first saved recipe shown.",
    15: "The second ingredient is quinoa.",
    16: "You can store notes about substitutions.",
    17: "World's Best Lasagna takes longer.",
    18: "Chicken Lemon Pepper Bowl is the top-reviewed recipe shown.",
}


EXPECTED = {
    0: "Good Old-Fashioned Pancakes; 20 minutes",
    1: "Shelley Albeluhn",
    2: "Eggplant Lemon Pepper Bowl; 1 hour",
    3: "Miso Soup; 15 minutes; 1,820 reviews",
    4: "one qualifying Asian tofu title",
    5: "Chocolate Chip Cookies; 15,600 reviews",
    6: "preheat to 350 F and grease a 9x5-inch loaf pan",
    7: "Scallion and Pork Plate",
    8: "Guacamole",
    9: "lasagna noodles; ricotta cheese",
    10: "local only; no grocery ordering or delivery integration",
    11: "one of the three unique Mika Tanaka titles tied at 130 reviews",
    12: "Cookpad Staples created for Bob, plus matching DB state",
    13: "Waffles in Bob's Sunday dinner slot, plus matching DB state",
    14: "Teriyaki Salmon",
    15: "quinoa",
    16: "substitutions, pantry reminders, or meal prep timing",
    17: "World's Best Lasagna",
    18: "Chicken Lemon Pepper Bowl",
}


def load_run(run_dir):
    return json.loads((Path(run_dir) / "trajectory.json").read_text())


def step_urls(traj):
    return [unquote(str(step.get("url", ""))).casefold()
            for step in traj.get("steps", [])]


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def _navigation_ok(task_index, traj):
    urls = step_urls(traj)
    for alternative in NAV_ALTERNATIVES[task_index]:
        if all(any(any(needle.casefold() in url for needle in group)
                   for url in urls) for group in alternative):
            return True, urls
    return False, urls


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _has_all(text, *tokens):
    value = _norm(text)
    return all(_norm(token) in value for token in tokens)


def _has_any(text, *tokens):
    value = _norm(text)
    return any(_norm(token) in value for token in tokens)


def _numbers(text):
    cleaned = (text or "").replace(",", "")
    return [float(value) for value in re.findall(
        r"(?<![\w.])[-+]?\d+(?:\.\d+)?", cleaned
    )]


def _has_number(text, expected, tolerance=0.005):
    return any(math.isclose(value, expected, abs_tol=tolerance, rel_tol=0)
               for value in _numbers(text))


def answer_ok(task_index, answer):
    if not answer.strip():
        return False
    if task_index == 0:
        return (_has_all(answer, "pancakes") and _has_number(answer, 20))
    if task_index == 1:
        return _has_all(answer, "shelley albeluhn")
    if task_index == 2:
        time_ok = (_has_any(answer, "1 hour", "1 hr")
                   or (_has_number(answer, 60)
                       and _has_any(answer, "minute", "min")))
        return _has_all(answer, "eggplant lemon pepper bowl") and time_ok
    if task_index == 3:
        return (_has_all(answer, "miso soup") and _has_number(answer, 15)
                and _has_number(answer, 1820))
    if task_index == 4:
        titles = (
            "creamy tomato rice with tofu",
            "herb roasted rice with tofu",
            "miso butter rice with tofu",
            "lemon pepper rice with tofu",
            "chili crisp rice with tofu",
        )
        return _has_any(answer, *titles)
    if task_index == 5:
        return (_has_all(answer, "chocolate chip cookies")
                and _has_number(answer, 15600))
    if task_index == 6:
        return (_has_all(answer, "preheat", "grease", "9x5")
                and _has_number(answer, 350))
    if task_index == 7:
        return _has_all(answer, "scallion and pork plate")
    if task_index == 8:
        return _has_all(answer, "guacamole")
    if task_index == 9:
        return _has_all(answer, "lasagna noodles", "ricotta cheese")
    if task_index == 10:
        return (_has_any(answer, "local", "benchmark mirror")
                and _has_any(answer, "grocery ordering", "delivery")
                and _has_any(answer, "no ", "not ", "doesn't", "does not",
                             "without", "only local"))
    if task_index == 11:
        return _has_any(
            answer,
            "chickpea lemon pepper bowl",
            "chicken lemon pepper bowl",
            "eggplant lemon pepper bowl",
        )
    if task_index == 12:
        return _has_all(answer, "cookpad staples")
    if task_index == 13:
        return _has_all(answer, "waffles", "sunday", "dinner")
    if task_index == 14:
        return _has_all(answer, "teriyaki salmon")
    if task_index == 15:
        return _has_all(answer, "quinoa")
    if task_index == 16:
        return _has_any(answer, "substitution", "pantry reminder",
                        "meal prep timing")
    if task_index == 17:
        return (_has_all(answer, "lasagna")
                and _has_any(answer, "longer", "takes more", "more time"))
    if task_index == 18:
        return _has_all(answer, "chicken lemon pepper bowl")
    raise ValueError(f"unknown task index: {task_index}")


def _fetch_db(container, kind):
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    result = subprocess.run(
        ["docker", "cp", source, path], capture_output=True, text=True
    )
    if result.returncode:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    return path


def _resolve_db(path, container, kind):
    return path or _fetch_db(container, kind)


def _query(db_path, sql, params=()):
    if not db_path or not Path(db_path).exists():
        return None
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql, params).fetchall()
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _bob_lists(db_path):
    return _query(
        db_path,
        "SELECT sl.id, sl.name FROM shopping_list sl "
        "JOIN user u ON u.id=sl.user_id "
        "WHERE u.email=? AND lower(sl.name)=lower(?) ORDER BY sl.id",
        ("bob.c@test.com", "Cookpad Staples"),
    )


def _bob_sunday_dinner(db_path):
    return _query(
        db_path,
        "SELECT mpi.id, r.slug FROM meal_plan_item mpi "
        "JOIN user u ON u.id=mpi.user_id "
        "JOIN recipe r ON r.id=mpi.recipe_id "
        "WHERE u.email=? AND mpi.day=? AND mpi.meal_type=? ORDER BY mpi.id",
        ("bob.c@test.com", "sunday", "dinner"),
    )


def _shopping_list_state_ok(initial_db, after_db):
    before = _bob_lists(initial_db)
    after = _bob_lists(after_db)
    ok = before == [] and after is not None and len(after) == 1
    return ok, f"initial={before!r}; after={after!r}"


def _meal_plan_state_ok(initial_db, after_db):
    before = _bob_sunday_dinner(initial_db)
    after = _bob_sunday_dinner(after_db)
    before_slugs = [row[1] for row in before] if before is not None else None
    after_slugs = [row[1] for row in after] if after is not None else None
    ok = (before_slugs == ["shrimp-scampi"]
          and after_slugs == ["waffles"])
    return ok, f"initial={before!r}; after={after!r}"


STATE_CHECKS = {
    12: ("shopping_list_after_state", _shopping_list_state_ok),
    13: ("meal_plan_after_state", _meal_plan_state_ok),
}


def evaluate(task_index, traj, initial_db="", after_db="",
             container="wh-review"):
    if task_index not in NAV_ALTERNATIVES:
        raise ValueError(f"unknown task index: {task_index}")
    answer = final_answer(traj)
    nav_ok, urls = _navigation_ok(task_index, traj)
    checks = [
        ("final_answer_nonempty", bool(answer), f"final={answer!r}"),
        ("required_navigation", nav_ok, f"urls={urls!r}"),
        ("frozen_answer", answer_ok(task_index, answer),
         f"expected={EXPECTED[task_index]}; final={answer!r}"),
    ]
    if task_index in STATEFUL_TASKS:
        initial_db = _resolve_db(initial_db, container, "instance_seed")
        after_db = _resolve_db(after_db, container, "instance")
        name, state_check = STATE_CHECKS[task_index]
        ok, detail = state_check(initial_db, after_db)
        checks.append((name, ok, detail))

    passed = all(ok for _, ok, _ in checks)
    reason = next((name for name, ok, _ in checks if not ok), "")
    evidence = [f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"
                for name, ok, detail in checks]
    return {
        "task_id": f"Cookpad--{task_index}",
        "pass": passed,
        "reason": reason,
        "evidence": evidence,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument(
        "--container", default=os.environ.get("WH_CONTAINER", "wh-review")
    )
    parser.add_argument("--no_llm", nargs="?", const="True", default="False")
    return parser.parse_args()


def main(task_index):
    args = parse_args()
    verdict = evaluate(
        task_index,
        load_run(args.run_dir),
        initial_db=args.initial_db,
        after_db=args.after_db,
        container=args.container,
    )
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict["pass"] else 1)
