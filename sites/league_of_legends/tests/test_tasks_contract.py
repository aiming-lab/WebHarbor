"""Task contract checks for sites/league_of_legends/tasks.jsonl.

A contributor's tasks.jsonl carries ONLY the task definition per row:
web_name, id, ques, web, upstream_url. Ground truth (verifier_path,
judge_rubric) is appended later by the reviewer's grading contract — rows in
the merged tree therefore carry exactly those two extra keys, while answer
material must never live in this agent-facing file.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
GRADING_KEYS = {"verifier_path", "judge_rubric"}  # appended by the review contract
ALLOWED_KEYS = REQUIRED_KEYS | GRADING_KEYS
FORBIDDEN_KEYS = {"answer", "answers", "expected"}
WEB_NAME = "League of Legends"
PORT = 40089
UPSTREAM = "https://www.leagueoflegends.com/"


def read_rows():
    assert TASKS.exists(), f"missing {TASKS}"
    rows = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_rows_have_exactly_the_basic_keys():
    rows = read_rows()
    assert 25 <= len(rows) <= 35, f"expected ~30 tasks, found {len(rows)}"
    for index, row in enumerate(rows):
        keys = set(row)
        assert REQUIRED_KEYS <= keys, f"row {index} missing keys: {REQUIRED_KEYS - keys}"
        extra = keys - ALLOWED_KEYS
        assert not extra, f"row {index} carries unexpected keys: {extra}"
        leaked = keys & FORBIDDEN_KEYS
        assert not leaked, f"row {index} leaks answer keys: {leaked}"


def test_grading_keys_are_all_or_nothing():
    """verifier_path/judge_rubric are appended to every row or to none."""
    rows = read_rows()
    with_grading = [r for r in rows if GRADING_KEYS <= set(r)]
    assert len(with_grading) in (0, len(rows)), \
        f"grading keys appended to only {len(with_grading)} of {len(rows)} rows"
    for row in with_grading:
        assert row["verifier_path"] == f"sites/league_of_legends/verify/verify_{int(row['id'].rsplit('--', 1)[1])}.py"
        assert row["judge_rubric"].strip()


def test_ids_are_unique_and_sequential():
    rows = read_rows()
    ids = [row["id"] for row in rows]
    assert len(set(ids)) == len(ids), "duplicate task ids"
    for index, row in enumerate(rows):
        assert row["id"] == f"{WEB_NAME}--{index}", f"row {index} id {row['id']!r}"


def test_web_and_upstream_urls():
    rows = read_rows()
    for index, row in enumerate(rows):
        assert row["web"] == f"http://localhost:{PORT}/", f"row {index} web {row['web']!r}"
        assert row["upstream_url"] == UPSTREAM, f"row {index} upstream {row['upstream_url']!r}"
        assert row["web_name"] == WEB_NAME


def test_questions_are_nonempty_and_specific():
    rows = read_rows()
    login_boilerplate = re.compile(
        r"Sign in with the demo account \(email: [a-z.]+@test\.com, password: TestPass123!\)")
    for index, row in enumerate(rows):
        question = row["ques"]
        assert len(question) >= 60, f"row {index} question too short: {question!r}"
        assert any(word in question.lower() for word in ("report", "explain", "compare", "identify", "give", "list", "create", "change", "remove", "add", "save", "which", "what", "how", "name")), f"row {index} lacks an ask"
        if "demo account" in question:
            assert login_boilerplate.search(question), \
                f"row {index} references demo account without credentials"
            assert re.search(r"email: [a-z.]+@test\.com, password: TestPass123!", question), \
                f"row {index} missing demo credentials"


def test_task_functional_breadth():
    """Tasks must cover the site's full feature surface."""
    rows = read_rows()
    joined = " ".join(row["ques"].lower() for row in rows)
    areas = {
        "roster selection": "roster",
        "roster search": "search",
        "champion detail": "champion page",
        "skins": "skin",
        "patch notes": "patch",
        "news research": "article",
        "account favorites": "favorite",
        "bookmarks": "bookmark",
        "profile management": "summoner name",
        "signup": "create a new account",
        "how-to-play": "how to play",
    }
    missing = [name for name, needle in areas.items() if needle not in joined]
    assert not missing, f"tasks miss functional areas: {missing}"


def test_no_answer_leak_in_questions():
    """Questions must not embed the ground-truth answer for detail facts."""
    answers = [
        "18 / 16.5 / 15 / 13.5 / 12",  # patch 26.19 Aatrox cooldowns
        "The ASU Team",                # /dev: Modernizing the Monk author
        "Hounds' Pursuit",             # Naafiri R ability name
        "RadiantViper is",             # profile edit expected state
        "bonus attack damage, ability power",  # Baron Nashor reward
    ]
    joined = " ".join(row["ques"] for row in read_rows())
    for answer in answers:
        assert answer not in joined, f"answer leaked in a question: {answer!r}"
