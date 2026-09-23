"""Navigation-layer tests; full evidence/state checks run separately."""

import json
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SITE / "verify"))
import answers
import state_checks
import verify_lib as verifier

SOURCES = {
    0: ["/due-date-calculator", "/pregnancy/week-13"],
    1: ["/baby/month-6", "/baby/month-2"],
    2: ["/articles/prenatal-screening-explained", "/articles/amniocentesis"],
    4: ["/pregnancy/week-18", "/pregnancy/week-20", "/pregnancy/week-30"],
    5: ["/pregnancy/week-30", "/articles/fetal-growth-rate"],
    6: ["/baby/month-2", "/baby/month-6", "/baby/month-7", "/baby/month-10"],
    8: ["/community/starting-solids-allergens", "/community/newborn-night-wakings"],
    9: ["/articles/how-births-are-classified", "/pregnancy/week-18"],
    11: ["/articles/how-births-are-classified", "/pregnancy/week-18"],
}


@pytest.fixture
def navigation_only(monkeypatch):
    # Deliberately isolate navigation. Positive answers, screenshots, schema,
    # state deltas and negative controls have separate full-evaluator coverage.
    monkeypatch.setattr(verifier, "check_common", lambda *args: "{}")
    monkeypatch.setattr(answers, "check_answer", lambda *args: None)
    monkeypatch.setattr(state_checks, "check_state", lambda *args: None)


def trajectory(task, paths):
    base = "http://localhost:40038"
    steps = [{"url": base + path, "action": "navigate", "params": {}} for path in paths]
    if task == 0:
        for step in steps:
            if step["url"].endswith("/due-date-calculator"):
                step["observed_text"] = "November 27, 2026; November 30, 2026"
    final = steps[-1]["url"] if steps else base
    if task in (5, 9, 11):
        steps.insert(
            0,
            {
                "url": base + "/login",
                "action": "input",
                "params": {"text": "alice.j@test.com"},
            },
        )
        final = base + "/account"
    return {
        "start_url": base,
        "steps": steps,
        "final_url": final,
        "final_observed_text": "Alice Johnson alice.j@test.com",
    }


def passes(task, run):
    judge = verifier.Judge(f"BabyCenter--{task}")
    verifier.run_checks(task, judge, run, "unused-in-navigation-test", "unused")
    return all(item["pass"] for item in judge.evidence)


@pytest.mark.parametrize("task", SOURCES)
def test_expanded_tasks_allow_alternate_routes(navigation_only, task):
    paths = SOURCES[task] if task == 0 else list(reversed(SOURCES[task]))
    # No fixed searches, filters, index pages, or duplicate shared-guide visit.
    assert passes(task, trajectory(task, paths))


@pytest.mark.parametrize("task", SOURCES)
def test_expanded_tasks_still_require_every_source(navigation_only, task):
    for missing in SOURCES[task]:
        assert not passes(
            task, trajectory(task, [p for p in SOURCES[task] if p != missing])
        )


def test_calculator_still_requires_both_observed_results(navigation_only):
    run = trajectory(0, SOURCES[0])
    run["steps"][0]["observed_text"] = "November 27, 2026"
    assert not passes(0, run)


@pytest.mark.parametrize(
    "task,paths",
    [
        (
            3,
            [
                "/articles/first-second-third-trimester-screen",
                "/articles/amniocentesis",
            ],
        ),
        (7, ["/articles/infant-sleep-approaches", "/community/newborn-night-wakings"]),
    ],
)
def test_explicit_filter_search_tasks_keep_their_requirements(
    navigation_only, task, paths
):
    assert not passes(task, trajectory(task, paths))


def test_compact_prompts_keep_visible_answer_contracts():
    tasks = [
        json.loads(line) for line in (SITE / "tasks.jsonl").read_text().splitlines()
    ]
    for i, task in enumerate(tasks):
        goal, formatting = task["ques"].rsplit("\n\n", 1)
        assert formatting.startswith("JSON only;")
        for key in answers.KEYS[i].split():
            assert key in formatting
        if i in SOURCES:
            assert len(goal.split("\n\n")[0].split()) <= 55
    assert "month_6_other_motor" not in tasks[1]["ques"]
    assert "raking_other_motor" in tasks[1]["ques"]
