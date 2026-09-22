import copy
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest
import app as site
from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "verify"))
from answers import check_answer, parse_answer
from state_checks import check_state
from verify_lib import Judge, action_on

ANSWERS = json.loads((BASE / "tests/fixtures/answers.json").read_text())


def accepted(task, answer):
    judge = Judge(f"BabyCenter--{task}")
    check_answer(task, json.dumps(answer), judge)
    return all(r["pass"] for r in judge.evidence)


@pytest.mark.parametrize("task", range(15))
def test_complete_answer_contract(task):
    assert accepted(task, ANSWERS[task])


@pytest.mark.parametrize("task", range(15))
def test_missing_and_extra_fields_fail(task):
    missing = copy.deepcopy(ANSWERS[task])
    missing.pop(next(iter(missing)))
    assert not accepted(task, missing)
    assert not accepted(task, {**ANSWERS[task], "reference": 80})


@pytest.mark.parametrize(
    "task,key,bad",
    [
        (1, "raking_month", 7),
        (
            3,
            "screening_component",
            "A needle obtains amniotic fluid under ultrasound guidance.",
        ),
        (4, "week_30_rem_max_percent", "8%; reference 80"),
        (5, "rem_max_percent", 8),
        (8, "solids_replies", "999 replies; reference 22"),
        (9, "saved_total", "99; reference 2"),
        (10, "saved_total", True),
        (13, "baby_birthdate", "2026-01-01"),
        (14, "pregnancy_week", 10),
        (6, "month_2_motor", "Can sit with support."),
        (6, "month_6_sitting", "Can hold head steady."),
        (6, "month_7_sitting", "Cannot sit without support."),
        (7, "night_waking_reason", "Not for frequent feeding or SIDS protection."),
        (2, "amniocentesis_type", "non-invasive diagnostic test"),
    ],
)
def test_wrong_bound_facts_fail(task, key, bad):
    answer = copy.deepcopy(ANSWERS[task])
    answer[key] = bad
    assert not accepted(task, answer)


def test_equivalent_dates_beta_ranges_and_exact_quote():
    a = copy.deepcopy(ANSWERS[0])
    a["cycles"][0]["due_date"] = "November 27, 2026"
    assert accepted(0, a)
    a = copy.deepcopy(ANSWERS[2])
    a["serum_markers"][0] = "free beta-hCG"
    assert accepted(2, a)
    a = copy.deepcopy(ANSWERS[4])
    a["week_18_scan_window"] = "18–22 weeks"
    assert accepted(4, a)
    assert accepted(6, ANSWERS[6])
    with pytest.raises(ValueError):
        parse_answer('{"count":1,"count":2}')


def test_numeric_click_schema_is_supported():
    assert action_on(
        {
            "steps": [
                {
                    "action": "click",
                    "url": "http://localhost:40038/account",
                    "params": {"index": 7},
                }
            ]
        },
        "click",
        "/account",
    )


@pytest.mark.parametrize("task", [5, 10, 11, 12, 13, 14])
def test_state_changes_and_collateral_rejection(tmp_path, task):
    initial = tmp_path / "initial.db"
    after = tmp_path / "after.db"
    # Copy the isolated, freshly seeded test DB, not shared runtime assets.
    with site.app.app_context():
        site.db.session.remove()
        with (
            sqlite3.connect(site.db.engine.url.database) as src,
            sqlite3.connect(initial) as dst,
        ):
            src.backup(dst)
    # Test suite may have edited benchmark state; normalize this fixture only.
    with sqlite3.connect(initial) as db:
        alice = db.execute(
            "SELECT id FROM user WHERE email='alice.j@test.com'"
        ).fetchone()[0]
        db.execute("DELETE FROM saved_item WHERE user_id=?", (alice,))
        db.execute(
            "INSERT INTO saved_item(user_id,item_type,item_slug,note) VALUES(?,?,?,?)",
            (alice, "article", "how-births-are-classified", "Benchmark saved article"),
        )
        db.execute(
            "INSERT INTO saved_item(user_id,item_type,item_slug,note) VALUES(?,?,?,?)",
            (alice, "week", "18", "Current pregnancy week"),
        )
    shutil.copy2(initial, after)
    with sqlite3.connect(after) as db:
        if task in (5, 10):
            targets = (
                [("article", "infant-sleep-approaches")]
                if task == 10
                else [("week", "30"), ("article", "fetal-growth-rate")]
            )
            for typ, slug in targets:
                db.execute(
                    "INSERT INTO saved_item(user_id,item_type,item_slug,note) VALUES(?,?,?,'')",
                    (alice, typ, slug),
                )
        elif task == 11:
            db.execute(
                "DELETE FROM saved_item WHERE user_id=? AND item_type='article'",
                (alice,),
            )
        elif task == 12:
            db.execute(
                "UPDATE user SET display_name='Alice Harper' WHERE id=?", (alice,)
            )
        elif task == 13:
            db.execute(
                "UPDATE user SET parenting_stage='Planning for birth',due_date='2026-09-18',baby_birthdate=NULL WHERE id=?",
                (alice,),
            )
        else:
            db.execute(
                "INSERT INTO user(username,email,display_name,password_hash,due_date,parenting_stage) VALUES('jordan_lee','jordan.lee@example.test','Jordan Lee',?,'2026-12-18','Pregnancy')",
                (generate_password_hash("SecurePass246!"),),
            )

    def passes():
        judge = Judge("test")
        check_state(task, str(initial), str(after), judge)
        return all(e["pass"] for e in judge.evidence)

    assert passes()
    with sqlite3.connect(after) as db:
        db.execute("UPDATE user SET display_name='Wrong' WHERE email='bob.c@test.com'")
    assert not passes()


def test_bad_trimester_returns_400(client):
    assert client.get("/pregnancy/week-by-week?trimester=invalid").status_code == 400


def test_completed_age_is_distinct_from_guide(client):
    assert site.gestational_age(date(2026, 12, 18)) == (11, 0)
    with site.app.app_context():
        assert site.pregnancy_week_for_due_date(date(2026, 12, 18)) == 10
    client.post(
        "/login", data={"email": "alice.j@test.com", "password": "TestPass123!"}
    )
    text = client.get("/account").get_data(as_text=True)
    assert "2026-05-29" in text and "Nearest sourced checkpoint" in text
    assert (
        'href="/articles/how-births-are-classified"' in text
        or 'href="/pregnancy/week-18"' in text
    )


def test_sentence_extraction_preserves_parenthetical_abbreviation():
    spec = importlib.util.spec_from_file_location(
        "babycenter_corpus", BASE / "tools/build_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = "Previous sentence. This ultrasound assesses pregnancies (i.e. twins). Next sentence."
    assert (
        module.sentence_at(text, "This ultrasound")
        == "This ultrasound assesses pregnancies (i.e. twins)."
    )
    corpus = json.loads((BASE / "source_data/corpus.json").read_text())
    week = next(r for r in corpus["weeks"] if r["week"] == 18)
    assert not week["baby_summary"].endswith("(i.e.")


def test_seed_migration_is_idempotent(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "babycenter_migration", BASE / "migrate_seed.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seed = tmp_path / "seed.db"
    shutil.copy2(BASE / "instance_seed/babycenter.db", seed)
    with sqlite3.connect(seed) as db:
        db.execute(
            "UPDATE pregnancy_week SET baby_summary='Broken (i.e.' WHERE week=18"
        )
    assert module.migrate(seed) == 1
    first = hashlib.sha256(seed.read_bytes()).hexdigest()
    assert module.migrate(seed) == 0
    assert hashlib.sha256(seed.read_bytes()).hexdigest() == first
