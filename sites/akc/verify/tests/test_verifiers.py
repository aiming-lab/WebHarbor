from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlencode


SITE_DIR = Path(__file__).resolve().parents[2]
VERIFY_DIR = SITE_DIR / "verify"
TASKS = {
    row["id"]: row
    for row in (json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text().splitlines())
}
READ_TASKS = list(range(8)) + [12]
STATE_TASKS = [8, 9, 10, 11]


def create_seed(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE user (
          id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL,
          display_name TEXT NOT NULL, password_hash TEXT NOT NULL, household TEXT,
          activity_level TEXT, experience TEXT
        );
        CREATE TABLE breed (
          id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          "group" TEXT NOT NULL, size TEXT NOT NULL, energy INTEGER NOT NULL,
          grooming INTEGER NOT NULL, trainability INTEGER NOT NULL,
          good_with_children INTEGER NOT NULL, apartment_score INTEGER NOT NULL,
          life_expectancy TEXT NOT NULL, height TEXT NOT NULL, weight TEXT NOT NULL,
          temperament TEXT NOT NULL, overview TEXT NOT NULL, care TEXT NOT NULL,
          exercise TEXT NOT NULL
        );
        CREATE TABLE article (
          id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          category TEXT NOT NULL, author TEXT NOT NULL, read_minutes INTEGER NOT NULL,
          summary TEXT NOT NULL, body TEXT NOT NULL
        );
        CREATE TABLE event (
          id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          event_type TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL,
          starts_on TEXT NOT NULL, venue TEXT NOT NULL, description TEXT NOT NULL
        );
        CREATE TABLE saved_breed (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, breed_id INTEGER NOT NULL, note TEXT
        );
        CREATE TABLE event_registration (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, event_id INTEGER NOT NULL,
          dog_name TEXT NOT NULL, class_name TEXT NOT NULL
        );
    """)
    users = [
        (1, "alice_j", "alice.j@test.com", "Alice Johnson", "scrypt:alice", "Apartment", "Moderate", "First-time owner"),
        (2, "bob_c", "bob.c@test.com", "Bob Chen", "scrypt:bob", "House with yard", "High", "Sports competitor"),
    ]
    db.executemany("INSERT INTO user VALUES (?,?,?,?,?,?,?,?)", users)
    breeds = [
        (1, "cavalier-king-charles-spaniel", "Cavalier King Charles Spaniel", "Toy", "Small", 3, 3, 4, 5, 5, "12-15 years", "12-13 in", "13-18 lb", "Affectionate, gentle, graceful"),
        (2, "boston-terrier", "Boston Terrier", "Non-Sporting", "Small", 3, 1, 4, 5, 5, "11-13 years", "15-17 in", "12-25 lb", "Friendly, bright, amusing"),
        (3, "golden-retriever", "Golden Retriever", "Sporting", "Large", 4, 4, 5, 5, 3, "10-12 years", "21.5-24 in", "55-75 lb", "Intelligent, friendly, devoted"),
        (4, "border-collie", "Border Collie", "Herding", "Medium", 5, 3, 5, 4, 1, "12-15 years", "18-22 in", "30-55 lb", "Affectionate, smart, energetic"),
        (5, "great-dane", "Great Dane", "Working", "Large", 3, 2, 3, 4, 2, "7-10 years", "28-32 in", "110-175 lb", "Friendly, patient, dependable"),
        (6, "whippet", "Whippet", "Hound", "Medium", 4, 1, 3, 4, 4, "12-15 years", "18-22 in", "25-40 lb", "Affectionate, playful, calm"),
        (7, "papillon", "Papillon", "Toy", "Small", 4, 3, 5, 4, 5, "14-16 years", "8-11 in", "5-10 lb", "Alert, friendly, happy"),
        (8, "shih-tzu", "Shih Tzu", "Toy", "Small", 2, 5, 3, 4, 5, "10-18 years", "9-10.5 in", "9-16 lb", "Affectionate, playful, outgoing"),
    ]
    db.executemany(
        "INSERT INTO breed VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [row + ("overview", "care", "exercise") for row in breeds],
    )
    db.executemany("INSERT INTO article VALUES (?,?,?,?,?,?,?,?)", [
        (1, "agility-training-introduction", "Introduction to Agility Training", "Sports", "Mina Brooks", 5, "summary", "body"),
        (2, "questions-to-ask-your-potential-breeder", "Questions You Can Ask Your Potential Breeder", "Puppy Information", "Randa Kriss", 3, "summary", "body"),
    ])
    db.executemany("INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?)", [
        (1, "canine-good-citizen-test-ny", "Canine Good Citizen Test", "Training", "New York", "NY", "2026-06-27", "Riverside Training Hall", "description"),
        (2, "puppy-training-webinar", "Puppy Training Webinar", "Education", "Online", "US", "2026-06-03", "AKC Virtual Classroom", "description"),
    ])
    db.executemany("INSERT INTO saved_breed VALUES (?,?,?,?)", [
        (1, 1, 1, "Saved profile breed"),
        (2, 2, 4, "Saved profile breed"),
    ])
    db.commit()
    db.close()


def positive_case(number):
    cases = {
        0: (["/breeds?group=Toy&size=Small", "/breeds/cavalier-king-charles-spaniel"],
            "Cavalier King Charles Spaniel: life expectancy 12-15 years; weight 13-18 lb."),
        1: (["/breed-selector?home=apartment&energy=3&grooming=1&children=5", "/breeds/boston-terrier"],
            "Boston Terrier is first; life expectancy 11-13 years."),
        2: (["/compare?breed=border-collie&breed=golden-retriever"],
            "Golden Retriever: energy 4/5.\nBorder Collie: energy 5/5 and has the higher rating."),
        3: (["/login", "/account", "/breeds/cavalier-king-charles-spaniel"],
            "Cavalier King Charles Spaniel has a 12-15 years life expectancy."),
        4: (["/search?q=agility", "/articles/agility-training-introduction"],
            "Introduction to Agility Training is by Mina Brooks and is a 5 min read."),
        5: (["/events?type=Training", "/events/canine-good-citizen-test-ny"],
            "Canine Good Citizen Test is at Riverside Training Hall on June 27, 2026."),
        6: (["/articles?category=Puppy+Information", "/articles/questions-to-ask-your-potential-breeder"],
            "Questions You Can Ask Your Potential Breeder is by Randa Kriss and is a 3 min read."),
        7: (["/breeds?group=Working&q=patient", "/breeds/great-dane"],
            "Great Dane: weight 110-175 lb; life expectancy 7-10 years."),
        8: (["/login", "/account", "/events/puppy-training-webinar", "/account"],
            "Registered Scout for Puppy Training Webinar in Canine Good Citizen."),
        9: (["/login", "/account", "/account"], "Alice Johnson activity is now Low."),
        10: (["/login", "/account", "/breeds/whippet"], "Whippet was saved to Bob Chen's profile."),
        11: (["/register", "/account"], "Created the Morgan Reed owner profile."),
        12: (["/compare?breed=shih-tzu&breed=cavalier-king-charles-spaniel&breed=papillon"],
             "Cavalier King Charles Spaniel: trainability 4/5.\nPapillon: trainability 5/5 and is highest.\nShih Tzu: trainability 3/5."),
    }
    return cases[number]


def positive_params(number):
    if number == 3:
        return {0: {"email": "alice.j@test.com", "password": "TestPass123!"}}
    if number == 8:
        return {
            0: {"email": "alice.j@test.com", "password": "TestPass123!"},
            2: {"dog_name": "Scout", "class_name": "Canine Good Citizen"},
        }
    if number == 9:
        return {
            0: {"email": "alice.j@test.com", "password": "TestPass123!"},
            2: {"activity_level": "Low"},
        }
    if number == 10:
        return {0: {"email": "bob.c@test.com", "password": "TestPass123!"}}
    if number == 11:
        return {0: {"display_name": "Morgan Reed", "username": "morgan_reed",
                    "email": "morgan.r@test.com", "password": "TrailDog42!",
                    "household": "House with yard", "activity": "High",
                    "experience": "Experienced owner"}}
    return {}


def correct_mutation(number, db):
    if number == 8:
        db.execute("INSERT INTO event_registration VALUES (1,1,2,'Scout','Canine Good Citizen')")
    elif number == 9:
        db.execute("UPDATE user SET activity_level='Low' WHERE id=1")
    elif number == 10:
        db.execute("INSERT INTO saved_breed VALUES (3,2,6,'')")
    elif number == 11:
        db.execute("INSERT INTO user VALUES (3,'morgan_reed','morgan.r@test.com','Morgan Reed',"
                   "'scrypt:morgan','House with yard','High','Experienced owner')")


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.seed = self.root / "seed.db"
        create_seed(self.seed)

    def tearDown(self):
        self.temp.cleanup()

    def make_run(self, number, *, urls=None, answer=None, mutation=None, extra_mutation=None,
                 params=None, question=None):
        run = self.root / f"run-{number}-{len(list(self.root.glob('run-*')))}"
        run.mkdir()
        shutil.copy2(self.seed, run / "initial.db")
        shutil.copy2(self.seed, run / "after.db")
        positive_urls, positive_answer = positive_case(number)
        urls = positive_urls if urls is None else urls
        answer = positive_answer if answer is None else answer
        params_by_index = positive_params(number)
        if params:
            params_by_index.update(params)
        steps = []
        for index, path in enumerate(urls):
            steps.append({
                "step": index,
                "url": "http://localhost:40040" + path,
                "action": "click",
                "params": params_by_index.get(index, {}),
                "action_result": {"success": True, "error": None},
            })
        task = TASKS[f"AKC--{number}"]
        trajectory = {
            "task_id": task["id"],
            "task": question if question is not None else task["ques"],
            "start_url": task["web"],
            "steps": steps,
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": answer,
        }
        (run / "trajectory.json").write_text(json.dumps(trajectory))
        if mutation or extra_mutation:
            db = sqlite3.connect(run / "after.db")
            if mutation:
                mutation(db)
            if extra_mutation:
                extra_mutation(db)
            db.commit()
            db.close()
        return run

    def verify(self, number, run):
        result = subprocess.run(
            [sys.executable, str(VERIFY_DIR / f"verify_{number}.py"), "--run_dir", str(run)],
            capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode == 0, payload["pass"], result.stderr)
        return payload

    def test_all_positive_cases_pass(self):
        for number in range(13):
            with self.subTest(number=number):
                mutation = (lambda db, n=number: correct_mutation(n, db)) if number in STATE_TASKS else None
                self.assertTrue(self.verify(number, self.make_run(number, mutation=mutation))["pass"])

    def test_read_tasks_reject_knowledge_shortcuts(self):
        for number in READ_TASKS:
            with self.subTest(number=number):
                run = self.make_run(number, urls=["/"], params={})
                self.assertFalse(self.verify(number, run)["pass"])

    def test_read_tasks_reject_wrong_answers(self):
        for number in READ_TASKS:
            with self.subTest(number=number):
                self.assertFalse(self.verify(number, self.make_run(number, answer="A plausible but wrong answer."))["pass"])

    def test_comparisons_reject_misbound_values_and_winner(self):
        wrong_answers = {
            2: "Golden Retriever: energy 5/5 and higher.\nBorder Collie: energy 4/5.",
            12: "Cavalier King Charles Spaniel: trainability 5/5 and highest.\n"
                "Papillon: trainability 4/5.\nShih Tzu: trainability 3/5.",
        }
        for number, answer in wrong_answers.items():
            with self.subTest(number=number):
                self.assertFalse(self.verify(number, self.make_run(number, answer=answer))["pass"])

    def test_exact_filter_tasks_reject_extra_narrowing(self):
        for number in [0, 1, 2, 4, 5, 6, 7, 12]:
            with self.subTest(number=number):
                urls, _ = positive_case(number)
                narrowed = list(urls)
                narrowed[0] += "&extra=shortcut" if "?" in narrowed[0] else "?extra=shortcut"
                self.assertFalse(self.verify(number, self.make_run(number, urls=narrowed))["pass"])

    def test_exact_filter_tasks_accept_blank_native_form_fields(self):
        cases = {
            0: "/breeds?q=&group=Toy&size=Small",
            5: "/events?type=Training&state=",
            7: "/breeds?q=patient&group=Working&size=",
        }
        for number, submitted_url in cases.items():
            with self.subTest(number=number):
                urls, _ = positive_case(number)
                submitted = list(urls)
                submitted[0] = submitted_url
                self.assertTrue(self.verify(number, self.make_run(number, urls=submitted))["pass"])

    def test_read_tasks_reject_any_business_write(self):
        def collateral(db):
            db.execute("INSERT INTO saved_breed VALUES (9,1,6,'collateral')")

        for number in READ_TASKS:
            with self.subTest(number=number):
                self.assertFalse(self.verify(number, self.make_run(number, mutation=collateral))["pass"])

    def test_state_tasks_reject_noop(self):
        for number in STATE_TASKS:
            with self.subTest(number=number):
                self.assertFalse(self.verify(number, self.make_run(number))["pass"])

    def test_state_tasks_reject_wrong_account_or_value(self):
        wrong = {
            8: lambda db: db.execute("INSERT INTO event_registration VALUES (1,2,2,'Scout','Canine Good Citizen')"),
            9: lambda db: db.execute("UPDATE user SET activity_level='Low' WHERE id=2"),
            10: lambda db: db.execute("INSERT INTO saved_breed VALUES (3,1,6,'')"),
            11: lambda db: db.execute("INSERT INTO user VALUES (3,'morgan_reed','morgan.r@test.com','Morgan Reed','scrypt:morgan','House with yard','Moderate','Experienced owner')"),
        }
        for number in STATE_TASKS:
            with self.subTest(number=number):
                self.assertFalse(self.verify(number, self.make_run(number, mutation=wrong[number]))["pass"])

    def test_state_tasks_reject_collateral_writes(self):
        def collateral(db):
            db.execute("INSERT INTO saved_breed VALUES (20,1,6,'collateral')")

        for number in STATE_TASKS:
            with self.subTest(number=number):
                run = self.make_run(
                    number,
                    mutation=lambda db, n=number: correct_mutation(n, db),
                    extra_mutation=collateral,
                )
                self.assertFalse(self.verify(number, run)["pass"])

    def test_state_tasks_reject_failed_recorded_actions(self):
        failed_step = {8: 2, 9: 2, 10: 2, 11: 0}
        for number in STATE_TASKS:
            with self.subTest(number=number):
                run = self.make_run(number, mutation=lambda db, n=number: correct_mutation(n, db))
                trajectory_path = run / "trajectory.json"
                trajectory = json.loads(trajectory_path.read_text())
                trajectory["steps"][failed_step[number]]["action_result"] = {
                    "success": False, "error": "recorded failure"
                }
                trajectory_path.write_text(json.dumps(trajectory))
                self.assertFalse(self.verify(number, run)["pass"])

    def test_compare_query_order_is_a_valid_alternative(self):
        alternatives = {
            2: ["/compare?" + urlencode([("breed", "golden-retriever"), ("breed", "border-collie")])],
            12: ["/compare?" + urlencode([("breed", "papillon"), ("breed", "shih-tzu"),
                                           ("breed", "cavalier-king-charles-spaniel")])],
        }
        for number, urls in alternatives.items():
            with self.subTest(number=number):
                self.assertTrue(self.verify(number, self.make_run(number, urls=urls))["pass"])

    def test_foreign_origin_and_stale_question_fail_closed(self):
        run = self.make_run(4)
        trajectory_path = run / "trajectory.json"
        trajectory = json.loads(trajectory_path.read_text())
        trajectory["steps"][0]["url"] = "https://www.akc.org/search/?q=agility"
        trajectory_path.write_text(json.dumps(trajectory))
        self.assertFalse(self.verify(4, run)["pass"])

        stale = self.make_run(0, question="An obsolete task question")
        self.assertFalse(self.verify(0, stale)["pass"])


if __name__ == "__main__":
    unittest.main()
