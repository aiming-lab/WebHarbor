"""Task contract checks for sites/landwatch/tasks.jsonl.

A contributor's tasks.jsonl carries the task definition per row:
web_name, id, ques, web, upstream_url. The reviewer's grading contract
appends verifier_path + judge_rubric inline (see verify/README.md) — those
keys, when present, must point at the deterministic verifiers. Ground truth
(answer keys) must never live in this agent-facing file.

Depth-redesign round (30 -> 15 tasks): every row is goal-style wording under
100 words with the steps implied, and each task grades a multi-chain surface
(location search, filter funnels, sorts, pagination, detail pages, agent
directory/profile, favorites, saved searches, registration, contact form,
homepage cross-checks, custom range forms).
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
REVIEWER_KEYS = {"verifier_path", "judge_rubric"}
FORBIDDEN_KEYS = {"answer", "answers", "expected"}
WEB_NAME = "LandWatch"
PORT = 40084


def read_rows():
    assert TASKS.exists(), f"missing {TASKS}"
    rows = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_rows_have_exactly_the_basic_keys():
    rows = read_rows()
    assert 15 <= len(rows) <= 25, f"expected 15-25 depth-redesigned tasks, found {len(rows)}"
    for index, row in enumerate(rows):
        keys = set(row)
        assert REQUIRED_KEYS <= keys, f"row {index} missing keys: {REQUIRED_KEYS - keys}"
        assert keys <= REQUIRED_KEYS | REVIEWER_KEYS, (
            f"row {index} carries unexpected keys: {keys - REQUIRED_KEYS - REVIEWER_KEYS}")
        leaked = keys & FORBIDDEN_KEYS
        assert not leaked, f"row {index} leaks grading keys: {leaked}"


def test_reviewer_keys_point_at_the_contract():
    rows = read_rows()
    with_grading = [r for r in rows if REVIEWER_KEYS <= set(r)]
    assert len(with_grading) in (0, len(rows)), "grading keys are all-or-nothing"
    for row in with_grading:
        index = int(row["id"].rsplit("--", 1)[1])
        assert row["verifier_path"] == f"sites/landwatch/verify/verify_{index}.py", row["id"]
        assert (SITE / "verify" / f"verify_{index}.py").is_file(), row["verifier_path"]
        assert row["judge_rubric"], row["id"]


def test_ids_are_unique_and_sequential():
    rows = read_rows()
    ids = [row["id"] for row in rows]
    assert len(set(ids)) == len(ids), "duplicate task ids"
    for index, row in enumerate(rows):
        assert row["id"] == f"{WEB_NAME}--{index}", f"row {index} id {row['id']!r}"


def test_web_and_upstream_urls():
    rows = read_rows()
    for row in rows:
        assert row["web_name"] == WEB_NAME
        assert row["web"] == f"http://localhost:{PORT}/", row["web"]
        assert row["upstream_url"].startswith("https://www.landwatch.com"), row["upstream_url"]


def test_questions_are_goal_style_and_substantial():
    rows = read_rows()
    openings = set()
    for row in rows:
        question = row["ques"]
        words = len(question.split())
        assert 40 <= words <= 100, (
            f"task {row['id']}: goal-style question must be 40-100 words, found {words}")
        lowered = question.lower()
        if "demo account" in lowered or "test.com" in lowered:
            assert "TestPass123!" in question or "LandBuyer2026!" in question, (
                f"{row['id']}: account task missing credentials")
            assert re.search(r"[a-z.]+@test\.com", question), f"{row['id']}: missing email"
        stripped = question[:60]
        assert stripped not in openings, f"duplicate task opening: {stripped!r}"
        openings.add(stripped)
        # goal-style: no mechanical click-by-click instruction chains
        assert not re.search(r"(?i)then click[^.]{0,40}?then click", question), row["id"]


def test_no_answer_like_artifacts():
    rows = read_rows()
    for row in rows:
        assert "```" not in row["ques"], f"{row['id']}: code block in question"
        assert not re.search(r"\bsha256\b", row["ques"].lower()), f"{row['id']}: hash artifact"
        # the frozen seed's headline facts must not be leaked as answers
        for leak in ("$19,400,000", "111 AC In the Heart", "Mac A. Coalson"):
            assert leak not in row["ques"], f"{row['id']}: leaks ground truth {leak!r}"


def test_functional_breadth():
    rows = read_rows()
    joined = " ".join(row["ques"].lower() for row in rows)
    for phrase in ("land for sale", "filter", "sort", "agent", "listing",
                   "price", "acres", "auction", "saved", "favorites"):
        assert phrase in joined, f"no task touches '{phrase}'"
    # every question is a deep multi-chain prompt
    assert all(len(row["ques"]) >= 250 for row in rows), "shallow task wording"


def test_depth_chains_cover_distinct_surfaces():
    """The 15 tasks must spread across distinct functional chains (no clones)."""
    rows = read_rows()
    lowered = [row["ques"].lower() for row in rows]
    checks = {name: (lambda s, needle=needle: needle in s) for name, needle in {
        'location research': 'location search', 'residence filtering': 'residence',
        'auction research': 'auctions', 'region research': 'houston region',
        'broker portfolio': 'broker', 'favorites': 'favorites', 'profile contact': 'phone',
        'new buyer inquiry': 'buyer account', 'featured comparison': 'featured carousel',
        'combined ranges': 'custom ranges'}.items()}
    for name, predicate in checks.items():
        assert any(predicate(s) for s in lowered), f"no task covers {name}"
