"""End-to-end positive and adversarial tests for every Discogs verifier."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import bcrypt
from pathlib import Path
from test_answer_checks import GOOD

REGISTRATION_HASH = bcrypt.hashpw(b"discogs2026", bcrypt.gensalt(rounds=4)).decode()


VERIFY_DIR = Path(__file__).resolve().parent
SEED_DB = VERIFY_DIR.parent / "instance_seed" / "discogs.db"
BASE_URL = "http://localhost:40029"
# Grading must not depend on which host port the operator published the mirror on;
# the repository's own guide runs the same image on 41000+. These alternates are used
# to prove the verifiers accept any single loopback origin and still reject a
# trajectory that wanders off one.
ALT_ORIGIN = "http://127.0.0.1:41029"
# Each verifier is a short local SQLite job, but this suite is often run on a machine
# that is busy building or serving other environments. The cap exists to catch a hung
# verifier, not to benchmark the host, so it is generous and tunable.
VERIFIER_TIMEOUT = int(os.environ.get("WHR_VERIFIER_TIMEOUT", "180"))
FOREIGN_ORIGIN = "https://attacker.invalid"


def rewrite_origin(steps: list[dict], new_origin: str, old: str = BASE_URL) -> list[dict]:
    """Re-host every recorded URL in `steps` on `new_origin`."""
    moved = []
    for step in steps:
        copy = dict(step)
        for key in ("url", "url_after"):
            if copy.get(key):
                copy[key] = copy[key].replace(old, new_origin)
        moved.append(copy)
    return moved


def navigate(path: str, *, origin: str = BASE_URL) -> dict:
    return {"url": f"{origin}{path}", "action": "navigate", "params": {}}


def input_text(path: str, text: str, index: int = 1) -> dict:
    return {
        "url": f"{BASE_URL}{path}",
        "action": "input",
        "params": {"index": index, "text": text},
    }


def click_to(path: str, destination: str, text: str = "") -> dict:
    return {
        "url": f"{BASE_URL}{path}",
        "url_after": f"{BASE_URL}{destination}",
        "action": "click",
        "params": {"text": text} if text else {"index": 1},
    }


def next_id(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(
        f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}"
    ).fetchone()[0]


def user_id(connection: sqlite3.Connection, username: str) -> int:
    return connection.execute(
        "SELECT id FROM users WHERE username=?", (username,)
    ).fetchone()[0]


def release_id(connection: sqlite3.Connection, discogs_id: int) -> int:
    return connection.execute(
        "SELECT id FROM releases WHERE discogs_id=?", (discogs_id,)
    ).fetchone()[0]


class VerifierTests(unittest.TestCase):
    maxDiff = None

    def run_verifier(
        self,
        task: int,
        steps: list[dict],
        answer: str,
        mutate=None,
        *,
        task_id: str | None = None,
        include_snapshots: bool = True,
        base_url: str = BASE_URL,
        env: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory(prefix=f"discogs-verify-{task}-") as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            run_dir.mkdir()
            command = [
                sys.executable,
                str(VERIFY_DIR / f"verify_{task}.py"),
                "--run_dir",
                str(run_dir),
                "--no_llm",
                "true",
            ]
            if include_snapshots:
                initial = root / "initial_state.db"
                after = root / "after_state.db"
                shutil.copy2(SEED_DB, initial)
                shutil.copy2(SEED_DB, after)
                if mutate:
                    connection = sqlite3.connect(after)
                    try:
                        mutate(connection)
                        connection.commit()
                    finally:
                        connection.close()
                command.extend(["--initial_db", str(initial), "--after_db", str(after)])
            trajectory = {
                "task_id": task_id or f"Discogs--{task}",
                "start_url": f"{base_url}/",
                "steps": steps,
                "final_url": (
                    steps[-1].get("url_after", steps[-1].get("url"))
                    if steps
                    else f"{base_url}/"
                ),
                "final_answer": answer,
            }
            (run_dir / "trajectory.json").write_text(
                json.dumps(trajectory), encoding="utf-8"
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=VERIFIER_TIMEOUT,
                check=False,
                env={**os.environ, **env} if env else None,
            )
            try:
                verdict = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                self.fail(
                    f"task {task} emitted invalid JSON: stdout={result.stdout!r} "
                    f"stderr={result.stderr!r}: {error}"
                )
            return result.returncode, verdict

    @staticmethod
    def mutate_collection_add(connection: sqlite3.Connection) -> None:
        uid = user_id(connection, "alice_crate")
        rid = release_id(connection, 3376357)
        connection.execute(
            """INSERT INTO collection_items
               (id,user_id,release_id,folder,media_condition,sleeve_condition,notes,added_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                next_id(connection, "collection_items"),
                uid,
                rid,
                "Vinyl",
                "Near Mint (NM or M-)",
                "Near Mint (NM or M-)",
                "",
                "2026-09-12 09:00:00",
            ),
        )
        connection.execute(
            "UPDATE releases SET have_count=have_count+1 WHERE id=?", (rid,)
        )

    @staticmethod
    def mutate_wantlist_add(connection: sqlite3.Connection) -> None:
        uid = user_id(connection, "bob_vinyl")
        rid = release_id(connection, 11554424)
        connection.execute(
            """INSERT INTO wantlist_items
               (id,user_id,release_id,min_grade,notes,added_at)
               VALUES(?,?,?,?,?,?)""",
            (
                next_id(connection, "wantlist_items"),
                uid,
                rid,
                "Very Good (VG)",
                "",
                "2026-09-12 09:00:00",
            ),
        )
        connection.execute(
            "UPDATE releases SET want_count=want_count+1 WHERE id=?", (rid,)
        )

    @staticmethod
    def mutate_list_create(connection: sqlite3.Connection) -> None:
        lid = next_id(connection, "lists")
        connection.execute(
            """INSERT INTO lists
               (id,user_id,title,description,is_public,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                lid,
                user_id(connection, "dave_techno"),
                "Jazz Reissue Reference",
                "Compare these two reissues before the next listening session.",
                1,
                "2026-09-12 09:00:00",
            ),
        )
        for position, comment, discogs_id in (
            (1, "1966 US stereo edition", 3376357),
            (2, "2007 Japan CD edition", 2379219),
        ):
            connection.execute(
                """INSERT INTO list_items
                   (id,list_id,release_id,artist_id,label_id,comment,position)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    next_id(connection, "list_items"),
                    lid,
                    release_id(connection, discogs_id),
                    None,
                    None,
                    comment,
                    position,
                ),
            )

    @staticmethod
    def mutate_listing_add(connection: sqlite3.Connection) -> None:
        uid = user_id(connection, "bob_vinyl")
        rid = release_id(connection, 5741659)
        connection.execute(
            """INSERT INTO listings
               (id,user_id,release_id,media_condition,sleeve_condition,comments,
                price,currency,shipping_from,allow_offers,status,posted_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                next_id(connection, "listings"),
                uid,
                rid,
                "Very Good Plus (VG+)",
                "Near Mint (NM or M-)",
                "Clean Spanish reissue; play-graded.",
                42.0,
                "GBP",
                "United Kingdom",
                1,
                "For Sale",
                "2026-09-12 09:00:00",
            ),
        )
        connection.execute("UPDATE users SET is_seller=1 WHERE id=?", (uid,))
        connection.execute(
            "UPDATE releases SET num_for_sale=num_for_sale+1 WHERE id=?", (rid,)
        )

    @staticmethod
    def mutate_forum_post(connection: sqlite3.Connection) -> None:
        connection.execute(
            """INSERT INTO posts(id,thread_id,user_id,body,created_at)
               VALUES(?,?,?,?,?)""",
            (
                next_id(connection, "posts"),
                12,
                user_id(connection, "carol_jazz"),
                "For acoustic jazz, I prefer MC for the extra detail in cymbals and upper mids.",
                "2026-09-12 09:00:00",
            ),
        )

    @staticmethod
    def mutate_registration(connection: sqlite3.Connection) -> None:
        connection.execute(
            """INSERT INTO users
               (id,username,email,password_hash,location,real_name,bio,avatar_seed,
                joined_at,is_seller,seller_rating,seller_feedback_count)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                next_id(connection, "users"),
                "craterunner99",
                "craterunner99@test.com",
                REGISTRATION_HASH,
                "Portland, USA",
                "Casey Runner",
                "Digging since 2010.",
                "craterunner99",
                "2026-09-12 09:00:00",
                0,
                0.0,
                0,
            ),
        )

    @staticmethod
    def mutate_collection_remove(connection: sqlite3.Connection) -> None:
        rid = release_id(connection, 20271358)
        connection.execute(
            "DELETE FROM collection_items WHERE user_id=? AND release_id=?",
            (user_id(connection, "alice_crate"), rid),
        )
        connection.execute(
            "UPDATE releases SET have_count=have_count-1 WHERE id=?", (rid,)
        )

    @staticmethod
    def mutate_rating_review(connection: sqlite3.Connection) -> None:
        uid = user_id(connection, "dave_techno")
        rid = release_id(connection, 35846581)
        connection.execute(
            "INSERT INTO ratings(id,user_id,release_id,value,created_at) VALUES(?,?,?,?,?)",
            (next_id(connection, "ratings"), uid, rid, 4, "2026-09-12 09:00:00"),
        )
        connection.execute(
            """INSERT INTO reviews(id,user_id,release_id,body,rating,helpful,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (
                next_id(connection, "reviews"),
                uid,
                rid,
                "The live arrangements reward a focused listen from start to finish.",
                4,
                0,
                "2026-09-12 09:00:00",
            ),
        )
        connection.execute(
            "UPDATE releases SET avg_rating=4.0,rating_count=1 WHERE id=?", (rid,)
        )

    def positive_case(self, task: int) -> tuple[list[dict], str, object | None]:
        cases = {
            0: (
                [navigate("/release/8031582"), navigate("/release/3376357")],
                "The 1966 edition prints durations. Its catalog numbers are 242 and RS 9242; Well, You Needn't is 11:24.",
                None,
            ),
            1: (
                [navigate("/release/7852399"), navigate("/release/7251385")],
                "The 1986 CD edition, catalog CP32-5244, contains Bellarosa with a displayed duration of 4:15.",
                None,
            ),
            2: (
                [navigate("/release/4337598"), navigate("/release/2379219")],
                "The Japan 2007 edition has 7 numbered tracks; its catalog number is UCCO-9038 and Joe Tarantino is credited for digital remastering.",
                None,
            ),
            3: (
                [navigate("/release/9732909"), navigate("/release/8837214")],
                "Release 9732909 lists the extra Impuesto de lujo entry Num. 6649. "
                "The other edition is release 8837214. Both editions share "
                "Deposito Legal B. 9417-1978.",
                None,
            ),
            4: (
                [navigate("/release/35846581")],
                "Colin Greenwood is credited on bass; the final side-D track is As The Waters Cover The Sea.",
                None,
            ),
            5: (
                [
                    navigate(
                        "/marketplace?currency=USD&media=Near+Mint+%28NM+or+M-%29&sort=price_asc"
                    ),
                    navigate("/release/19878259"),
                ],
                "Kelly Blue by Wynton Kelly is sold by kosmische for 8.27 USD; the catalog numbers are SMJ-6114 and SRS-6059.",
                None,
            ),
            6: (
                [navigate("/lists"), navigate("/list/3"), navigate("/release/4627265")],
                "The fourth release is Jeff Beck by Jeff Beck, from Italy, catalog IGDA 1063/64.",
                None,
            ),
            7: (
                [navigate("/login"), navigate("/release/3376357")],
                "Added the requested edition to the Vinyl folder with Near Mint media condition.",
                self.mutate_collection_add,
            ),
            8: (
                [navigate("/login"), navigate("/release/11554424")],
                "Added the requested edition to bob_vinyl's wantlist with Very Good minimum grade.",
                self.mutate_wantlist_add,
            ),
            9: (
                [
                    navigate("/login"),
                    navigate("/release/3376357"),
                    navigate("/release/2379219"),
                    navigate("/list/new"),
                ],
                "Created the public list and added both editions in the requested order.",
                self.mutate_list_create,
            ),
            10: (
                [navigate("/login"), navigate("/release/5741659"), navigate("/sell")],
                "Listed the requested release with the specified sale details.",
                self.mutate_listing_add,
            ),
            11: (
                [
                    navigate("/forum/vinyl"),
                    navigate("/thread/12"),
                    navigate("/login"),
                    navigate("/thread/12"),
                ],
                "Posted the exact reply to the requested thread.",
                self.mutate_forum_post,
            ),
            12: (
                [
                    navigate("/register"),
                    navigate("/settings"),
                    click_to("/settings", "/", "Log out"),
                    navigate("/login"),
                    input_text("/login", "craterunner99", 1),
                    input_text("/login", "discogs2026", 2),
                    click_to("/login", "/"),
                ],
                "Registered, updated the profile, signed out, and logged back in.",
                self.mutate_registration,
            ),
            13: (
                [
                    navigate("/login"),
                    navigate("/user/alice_crate/collection?folder=Vinyl"),
                ],
                "Removed the specified edition and confirmed it is absent from the Vinyl folder.",
                self.mutate_collection_remove,
            ),
            14: (
                [navigate("/login"), navigate("/release/35846581")],
                "Saved the 4-star rating and exact 4-star review.",
                self.mutate_rating_review,
            ),
        }
        steps, answer, mutate = cases[task]
        if task in GOOD:
            answer = GOOD[task]
        if task == 4:
            steps.append(navigate("/release/5138247"))
        if task == 6:
            steps.insert(2, navigate("/release/8468154"))
        if task == 12:
            steps.append(navigate("/settings"))
        return steps, answer, mutate

    def test_all_positive_cases_pass(self) -> None:
        for task in range(15):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_all_no_op_runs_fail(self) -> None:
        for task in range(15):
            with self.subTest(task=task):
                code, verdict = self.run_verifier(task, [navigate("/")], "")
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_wrong_task_identity_fails_all(self) -> None:
        for task in range(15):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(
                    task, steps, answer, mutate, task_id="Discogs--999"
                )
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_correct_outcome_without_navigation_fails_all(self) -> None:
        for task in range(15):
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, [], answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_read_only_wrong_answers_fail(self) -> None:
        for task in range(7):
            with self.subTest(task=task):
                steps, _, _ = self.positive_case(task)
                code, verdict = self.run_verifier(
                    task, steps, "I compared the pages, but every requested value is different."
                )
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_foreign_origin_path_spoof_fails_all(self) -> None:
        for task in range(15):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                spoofed = rewrite_origin(steps, FOREIGN_ORIGIN)
                code, verdict = self.run_verifier(task, spoofed, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_alternate_loopback_port_is_accepted(self) -> None:
        """A run published on another host port grades exactly like the default one."""
        for task in range(15):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                moved = rewrite_origin(steps, ALT_ORIGIN)
                code, verdict = self.run_verifier(
                    task, moved, answer, mutate, base_url=ALT_ORIGIN
                )
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_mixed_origin_trajectory_fails_all(self) -> None:
        """A run that wanders onto a second local origin must not grade.

        Dropping the hard-coded port is what makes this test the real control: any one
        loopback origin is accepted, but a trajectory that straddles two of them is
        stitched together from different services and is rejected. Appending the extra
        origin works for every task, including the ones whose path is a single step.
        """
        for task in range(15):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                mixed = steps + rewrite_origin(steps[-1:], ALT_ORIGIN)
                code, verdict = self.run_verifier(task, mixed, answer, mutate)
                self.assertNotEqual(0, code, verdict)
                self.assertFalse(verdict["pass"], verdict)
                self.assertEqual("single_origin", verdict["reason"], verdict)

    def test_expected_origin_pin_is_enforced_when_set(self) -> None:
        """WHR_EXPECTED_ORIGIN lets a grader pin one origin without hard-coding it."""
        steps, answer, mutate = self.positive_case(0)
        code, verdict = self.run_verifier(
            0, steps, answer, mutate, env={"WHR_EXPECTED_ORIGIN": BASE_URL}
        )
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

        code, verdict = self.run_verifier(
            0, steps, answer, mutate, env={"WHR_EXPECTED_ORIGIN": ALT_ORIGIN}
        )
        self.assertNotEqual(0, code, verdict)
        self.assertFalse(verdict["pass"], verdict)
        self.assertEqual("origin_matches_expected", verdict["reason"])

    def test_state_tasks_require_frozen_snapshots(self) -> None:
        for task in range(7, 15):
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(
                    task, steps, answer, include_snapshots=False
                )
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_read_only_tasks_require_frozen_snapshots(self) -> None:
        for task in range(7):
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(
                    task, steps, answer, include_snapshots=False
                )
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_state_tasks_reject_self_report_when_database_is_unchanged(self) -> None:
        for task in range(7, 15):
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_state_tasks_reject_unrelated_extra_changes(self) -> None:
        for task in range(7, 15):
            with self.subTest(task=task):
                steps, answer, positive_mutation = self.positive_case(task)

                def mutate(connection, positive_mutation=positive_mutation):
                    positive_mutation(connection)
                    connection.execute(
                        "UPDATE users SET bio='Unrequested mutation' WHERE username='alice_crate'"
                    )

                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_counter_tasks_reject_extra_release_mutations(self) -> None:
        for task in (7, 8, 10, 13, 14):
            with self.subTest(task=task):
                steps, answer, positive_mutation = self.positive_case(task)

                def mutate(connection, positive_mutation=positive_mutation):
                    positive_mutation(connection)
                    connection.execute(
                        "UPDATE releases SET have_count=have_count+1 WHERE discogs_id=8031582"
                    )

                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_state_tasks_reject_wrong_objects(self) -> None:
        def collection_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_collection_add(connection)
            connection.execute(
                "UPDATE collection_items SET release_id=? WHERE id=(SELECT MAX(id) FROM collection_items)",
                (release_id(connection, 8031582),),
            )

        def wantlist_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_wantlist_add(connection)
            connection.execute(
                "UPDATE wantlist_items SET release_id=? WHERE id=(SELECT MAX(id) FROM wantlist_items)",
                (release_id(connection, 8031582),),
            )

        def list_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_list_create(connection)
            connection.execute(
                "UPDATE lists SET user_id=? WHERE id=(SELECT MAX(id) FROM lists)",
                (user_id(connection, "alice_crate"),),
            )

        def listing_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_listing_add(connection)
            connection.execute(
                "UPDATE listings SET release_id=? WHERE id=(SELECT MAX(id) FROM listings)",
                (release_id(connection, 9732909),),
            )

        def post_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_forum_post(connection)
            connection.execute(
                "UPDATE posts SET thread_id=1 WHERE id=(SELECT MAX(id) FROM posts)"
            )

        def registration_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_registration(connection)
            connection.execute(
                "UPDATE users SET username='wrong_runner' WHERE id=(SELECT MAX(id) FROM users)"
            )

        def removal_wrong(connection: sqlite3.Connection) -> None:
            original = connection.execute(
                "SELECT * FROM collection_items WHERE user_id=? AND release_id=?",
                (
                    user_id(connection, "alice_crate"),
                    release_id(connection, 20271358),
                ),
            ).fetchone()
            self.mutate_collection_remove(connection)
            connection.execute(
                """INSERT INTO collection_items
                   (id,user_id,release_id,folder,media_condition,sleeve_condition,notes,added_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                tuple(original),
            )
            connection.execute(
                "UPDATE releases SET have_count=have_count+1 WHERE discogs_id=20271358"
            )
            other = connection.execute(
                """SELECT ci.id,r.id FROM collection_items ci
                   JOIN releases r ON r.id=ci.release_id
                   WHERE ci.user_id=? AND r.discogs_id<>20271358 LIMIT 1""",
                (user_id(connection, "alice_crate"),),
            ).fetchone()
            connection.execute("DELETE FROM collection_items WHERE id=?", (other[0],))
            connection.execute(
                "UPDATE releases SET have_count=have_count-1 WHERE id=?", (other[1],)
            )

        def rating_wrong(connection: sqlite3.Connection) -> None:
            self.mutate_rating_review(connection)
            wrong = release_id(connection, 1845)
            connection.execute(
                "UPDATE ratings SET release_id=? WHERE id=(SELECT MAX(id) FROM ratings)",
                (wrong,),
            )
            connection.execute(
                "UPDATE reviews SET release_id=? WHERE id=(SELECT MAX(id) FROM reviews)",
                (wrong,),
            )

        mutations = {
            7: collection_wrong,
            8: wantlist_wrong,
            9: list_wrong,
            10: listing_wrong,
            11: post_wrong,
            12: registration_wrong,
            13: removal_wrong,
            14: rating_wrong,
        }
        for task, mutate in mutations.items():
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_read_only_tasks_reject_database_mutation(self) -> None:
        def mutate(connection: sqlite3.Connection) -> None:
            connection.execute(
                "UPDATE users SET bio='Unrequested mutation' WHERE username='alice_crate'"
            )

        for task in range(7):
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_schema_mutation_fails(self) -> None:
        def mutate(connection: sqlite3.Connection) -> None:
            connection.execute("CREATE TABLE injected_state(id INTEGER PRIMARY KEY)")

        steps, answer, _ = self.positive_case(0)
        code, verdict = self.run_verifier(0, steps, answer, mutate)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_read_only_answers_cannot_negate_the_required_facts(self) -> None:
        cases = {
            0: "The answer is not 1966, not 242 or RS 9242, and Well, You Needn't is not 11:24.",
            1: "It is not the 1986 CD CP32-5244; Bellarosa is not 4:15.",
            2: "The Japan 2007 UCCO-9038 release does not have 7 tracks and Joe Tarantino is not credited.",
            4: "Colin Greenwood is not the bass player, and the last track is not As The Waters Cover The Sea.",
            5: "Kelly Blue by Wynton Kelly is not the USD 8.27 kosmische listing; SMJ-6114 and SRS-6059 are wrong.",
        }
        for task, answer in cases.items():
            with self.subTest(task=task):
                steps, _, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_task_zero_requires_both_distinct_catalog_numbers(self) -> None:
        steps, _, _ = self.positive_case(0)
        answer = "The 1966 edition uses RS 9242, and Well, You Needn't is 11:24."
        code, verdict = self.run_verifier(0, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_task_three_rejects_swapped_identifier_binding(self) -> None:
        steps, _, _ = self.positive_case(3)
        # Every requested token is present, but the extra identifier is attached to the
        # wrong edition. The binding check must still reject it.
        answer = (
            "Release 8837214 lists the extra Impuesto de lujo entry Num. 6649. "
            "The other edition is release 9732909. Both editions share "
            "Deposito Legal B. 9417-1978."
        )
        code, verdict = self.run_verifier(3, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_task_three_rejects_results_page_only_facts(self) -> None:
        steps, _, _ = self.positive_case(3)
        # The format descriptors are readable from the search results page, so an answer
        # built only from them no longer satisfies the task.
        answer = (
            "Release 9732909 is the Dolby System edition; release 8837214 is the "
            "Repress. They share D 57.352 and D-57352."
        )
        code, verdict = self.run_verifier(3, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_forum_task_requires_return_to_thread_after_login(self) -> None:
        steps, answer, mutate = self.positive_case(11)
        code, verdict = self.run_verifier(task=11, steps=steps[:-1], answer=answer, mutate=mutate)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_registration_task_requires_new_credentials_and_login_success(self) -> None:
        steps, answer, mutate = self.positive_case(12)
        for shortened in (steps[:4], steps[:-1]):
            with self.subTest(step_count=len(shortened)):
                code, verdict = self.run_verifier(12, shortened, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_read_only_natural_equivalent_phrasings_pass(self) -> None:
        alternatives = {
            0: "It is the 1966 release. The two catalogue identifiers are RS 9242 and 242, and ‘Well, You Needn’t’ runs 11 minutes 24 seconds (11:24).",
            2: "Japan's 2007 UCCO-9038 version is the one with seven tracks; digital remastering is credited to Joe Tarantino.",
            3: "The extra Impuesto de lujo line, Num. 6649, is printed on release 9732909. "
               "Release 8837214 stops at two identifiers. Both carry Deposito Legal B. 9417-1978.",
            5: "At US$8.27, kosmische's Kelly Blue by Wynton Kelly was cheapest. The label catalog numbers are SRS-6059 plus SMJ-6114. Legacy US catalog numbers: 12-298 and RLP 12-298.",
        }
        for task, answer in alternatives.items():
            with self.subTest(task=task):
                steps, _, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_registration_requires_a_usable_matching_hash(self):
        for value in ('invalid-hash', bcrypt.hashpw(b'wrong-password', bcrypt.gensalt(rounds=4)).decode()):
            with self.subTest(value=value):
                def corrupt(connection):
                    self.mutate_registration(connection)
                    connection.execute("UPDATE users SET password_hash=? WHERE username='craterunner99'", (value,))
                steps, answer, _ = self.positive_case(12)
                code, verdict = self.run_verifier(12, steps, answer, corrupt)
                self.assertNotEqual(0, code, verdict)
                self.assertIn('password_authenticates', verdict['reason'])


if __name__ == "__main__":
    unittest.main()
