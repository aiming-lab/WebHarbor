"""Grading-contract tests for the FedEx task set.

No task answer appears in this file. Every expected value is derived from the
seed through `verify/ground_truth.py`, the same module the verifiers use, and
every answer string is composed from those derived values at run time. That keeps
the suite from becoming a second copy of the answer key while still proving:

* each task's target derives from the seed, and derives uniquely;
* a correct run recorded in the schema `agent_demo/agent.py` actually writes
  passes the real `verify_N.py` entry point;
* degraded runs fail: contradictory answers, answer-only runs, foreign origins,
  missing or forged screenshots, a wrong task id, and state that did not change;
* the navigation contract binds the query the task asks for, so shortcut
  navigation does not earn credit.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
VERIFY = SITE_ROOT / "verify"
for path in (str(SITE_ROOT), str(VERIFY)):
    if path not in sys.path:
        sys.path.insert(0, path)

from PIL import Image  # noqa: E402

from ground_truth import TASK_COUNT, task_ground_truth  # noqa: E402
from rate_quote import QuoteRequest, issue_quote_token  # noqa: E402

PORT = 40024
ORIGIN = f"http://localhost:{PORT}"
PASSWORD = "TestPass123!"


def build_seed() -> Path:
    """Return a seed database built from tracked source."""
    shipped = SITE_ROOT / "instance_seed" / "fedex.db"
    if shipped.is_file():
        return shipped
    directory = Path(tempfile.mkdtemp(prefix="fedex-contract-seed-"))
    work = directory / "fedex"
    shutil.copytree(SITE_ROOT, work, symlinks=True,
                    ignore=shutil.ignore_patterns("instance", "instance_seed", "__pycache__"))
    environment = dict(os.environ)
    environment.pop("WEBSYN_SKIP_BOOTSTRAP", None)
    environment["PYTHONHASHSEED"] = "0"
    subprocess.run([sys.executable, "seed_data.py"], cwd=work, env=environment,
                   check=True, capture_output=True, timeout=900)
    target = directory / "fedex.db"
    shutil.copy2(work / "instance_seed" / "fedex.db", target)
    return target


SEED = build_seed()


def money(value: float) -> str:
    return f"${value:,.2f}"


def compose_answer(task: int, truth: dict) -> str:
    """Compose the answer a correct run would give, from derived values only."""
    kind = truth["kind"]
    if kind == "tracking_exception":
        return (f"The latest exception on {truth['target']} was recorded in {truth['location_label']}, "
                f"caused by {truth['record_status_summary'].rstrip('.').lower()}.")
    if kind == "delivered_comparison":
        requirement = ("a signature is required" if truth["signature"]["signature_required"]
                       else "no signature is required")
        return f"{truth['delivered']} is the package that is already delivered, and {requirement}."
    if kind == "exception_guide":
        return (f"Record the {truth['field_one']} and the {truth['field_two']}; "
                f"{truth['address_review_status']} means address details are under review.")
    if kind == "rate_cheapest":
        return (f"The cheapest displayed service is {truth['cheapest']['name']}, at "
                f"{money(truth['cheapest']['price'])}.")
    if kind == "rate_most_expensive":
        return (f"The most expensive displayed service is {truth['most_expensive']['name']}, at "
                f"{money(truth['most_expensive']['price'])}.")
    if kind == "rate_fastest_vs_cheapest":
        return (f"The fastest option is {truth['fastest']['name']} and the cheapest is "
                f"{truth['cheapest']['name']}; the difference is "
                f"{money(truth['fastest_minus_cheapest'])}.")
    if kind == "invoice_for_delivered_lane":
        return (f"{truth['invoice_number']} is the invoice for shipment {truth['shipment_code']} "
                f"delivered to {truth['destination_city']}, {truth['destination_state']}.")
    if kind == "claim_by_status":
        return (f"The claim waiting for more information is {truth['claim_number']} "
                f"(status Info requested), tracking number {truth['tracking_number']}.")
    if kind == "claim_by_type":
        return (f"The damage review claim is {truth['claim_number']}, tracking number "
                f"{truth['tracking_number']}.")
    if kind == "pickup_by_status":
        return (f"The pickup marked Ready for driver is {truth['confirmation_code']}, window "
                f"{truth['time_window']}.")
    if kind == "shipment_list_by_status":
        listing = "; ".join(f"{code} to {city}" for code, city in truth["pairs"])
        return f"The shipments marked Out for delivery are {listing}."
    if kind == "location_note":
        return f"The {truth['name']} summary note reads: {truth['note']}."
    if kind == "weather_guide_and_eta":
        return (f"The latest exception on {truth['target']} is timestamped {truth['event_time']}, and "
                f"the Current ETA is {truth['estimated_delivery'].lower()}, so there is no confirmed "
                f"delivery date.")
    if kind == "location_hours":
        return f"The {truth['name']} posts hours of {truth['hours']}."
    if kind == "final_handoff":
        return (f"{truth['target']} is delivered; its final timeline handoff was in "
                f"{truth['final_city']}, {truth['final_state']}.")
    if kind == "create_shipment":
        return f"The generated tracking number is {truth['expectation']['tracking_number']}."
    if kind == "schedule_pickup":
        return f"The confirmation code is {truth['expectation']['confirmation_code']}."
    raise AssertionError(f"unhandled ground-truth kind {kind!r}")


def contradict_answer(task: int, truth: dict) -> str:
    """Compose an answer that names the right values and then retracts them."""
    kind = truth["kind"]
    if kind == "tracking_exception":
        return f"{truth['location_label']} had the exception, but weather did not cause it."
    if kind == "delivered_comparison":
        return (f"{truth['delivered']} is delivered, but its signature is optional and not required.")
    if kind == "exception_guide":
        return (f"Record the {truth['field_one']} and the {truth['field_two']}; "
                f"{truth['address_review_status']} means no address review is needed.")
    if kind == "rate_cheapest":
        return (f"{truth['cheapest']['name']} costs {money(truth['cheapest']['price'])}, but it is not "
                f"the cheapest option.")
    if kind == "rate_most_expensive":
        return (f"{truth['most_expensive']['name']} costs {money(truth['most_expensive']['price'])}, "
                f"but it is not the most expensive option.")
    if kind == "rate_fastest_vs_cheapest":
        return (f"The fastest is {truth['fastest']['name']} and the cheapest is "
                f"{truth['cheapest']['name']}, difference {money(truth['fastest_minus_cheapest'])}. "
                f"In fact {truth['fastest']['name']} is slower.")
    if kind == "invoice_for_delivered_lane":
        return f"{truth['invoice_number']} is unrelated to the {truth['destination_city']} shipment."
    if kind == "claim_by_status":
        return f"{truth['claim_number']} and {truth['tracking_number']} are not waiting for more information."
    if kind == "claim_by_type":
        return f"{truth['claim_number']} and {truth['tracking_number']} concern billing, not damage review."
    if kind == "pickup_by_status":
        return (f"{truth['confirmation_code']}, {truth['time_window']}, is cancelled rather than "
                f"Ready for driver.")
    if kind == "shipment_list_by_status":
        listing = "; ".join(f"{code} {city}" for code, city in truth["pairs"])
        return f"{listing}. None are Out for delivery."
    if kind == "location_note":
        return f"The note is not {truth['note']}."
    if kind == "weather_guide_and_eta":
        return (f"{truth['event_time']}: the ETA is pending, yet it is a guaranteed delivery date "
                f"and delivery is confirmed.")
    if kind == "location_hours":
        return f"The posted hours are not {truth['hours']}."
    if kind == "final_handoff":
        competing = next(iter(truth["competing_cities"]), "Memphis")
        return (f"It is delivered. {truth['final_city']}, {truth['final_state']} was only the origin; "
                f"the final handoff was {competing}.")
    if kind == "create_shipment":
        return f"{truth['expectation']['tracking_number']} was not generated."
    if kind == "schedule_pickup":
        return f"{truth['expectation']['confirmation_code']} was not scheduled."
    raise AssertionError(f"unhandled ground-truth kind {kind!r}")


def required_paths(task: int, truth: dict) -> list[str]:
    """Return the URLs a correct run visits, in order."""
    kind = truth["kind"]
    if kind == "tracking_exception":
        return [f"{ORIGIN}/track/results?numbers={truth['target']}", f"{ORIGIN}/tracking/{truth['target']}"]
    if kind == "delivered_comparison":
        return ([f"{ORIGIN}/track/results?numbers={', '.join(truth['numbers'])}",
                 f"{ORIGIN}/tracking/{truth['delivered']}"])
    if kind == "exception_guide":
        return [f"{ORIGIN}/support?q={truth['search_query']}", f"{ORIGIN}/support/{truth['slug']}"]
    if kind in ("rate_cheapest", "rate_most_expensive", "rate_fastest_vs_cheapest"):
        return [f"{ORIGIN}/rate-estimate"]
    if kind == "invoice_for_delivered_lane":
        return [f"{ORIGIN}/account/shipments", f"{ORIGIN}/invoices"]
    if kind in ("claim_by_status", "claim_by_type"):
        return [f"{ORIGIN}/claims"]
    if kind == "pickup_by_status":
        return [f"{ORIGIN}/account"]
    if kind == "shipment_list_by_status":
        return [f"{ORIGIN}/account/shipments"]
    if kind == "location_note":
        if truth["search_query"]:
            return [f"{ORIGIN}/locations?q={truth['search_query']}", f"{ORIGIN}/locations/{truth['slug']}"]
        return [f"{ORIGIN}/locations", f"{ORIGIN}/locations/{truth['slug']}"]
    if kind == "weather_guide_and_eta":
        return [f"{ORIGIN}/search?q={truth['search_query']}", f"{ORIGIN}/support/{truth['slug']}",
                f"{ORIGIN}/tracking/{truth['target']}"]
    if kind == "location_hours":
        return [f"{ORIGIN}/search?q={truth['search_query']}", f"{ORIGIN}/locations/{truth['slug']}"]
    if kind == "final_handoff":
        return [f"{ORIGIN}/track/results?numbers={truth['target']}", f"{ORIGIN}/tracking/{truth['target']}"]
    if kind == "create_shipment":
        return [f"{ORIGIN}/ship", f"{ORIGIN}/ship/service", f"{ORIGIN}/ship/review",
                f"{ORIGIN}/ship/confirmation"]
    if kind == "schedule_pickup":
        return [f"{ORIGIN}/pickup", f"{ORIGIN}/account"]
    raise AssertionError(f"unhandled ground-truth kind {kind!r}")


def login_steps(task: int, truth: dict) -> list[dict]:
    """Return recorder-shaped steps that sign in to the task's account."""
    from ground_truth import BENCHMARK_ACCOUNTS
    email = BENCHMARK_ACCOUNTS.get(task)
    if not email:
        return []
    return [
        {"url": f"{ORIGIN}/login", "action": "input", "params": {"index": 4, "text": email}},
        {"url": f"{ORIGIN}/login", "action": "input", "params": {"index": 5, "text": PASSWORD}},
        {"url": f"{ORIGIN}/login", "action": "click", "params": {"index": 6},
         "lands_on": f"{ORIGIN}/account"},
    ]


def quote_steps(truth: dict) -> list[dict]:
    """Return recorder-shaped steps that submit the requested rate form."""
    if "origin_state" not in truth:
        return []
    token = issue_quote_token(QuoteRequest(truth["origin_state"], truth["destination_state"],
                                           truth["weight_lb"], truth["package_type"]))
    return [{"url": f"{ORIGIN}/rate-estimate", "action": "click", "params": {"index": 9},
             "lands_on": f"{ORIGIN}/rate-estimate?quote={token}"}]


def make_screenshots(directory: Path, count: int) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    names = []
    for index in range(count):
        name = f"step_{index:03d}.png"
        Image.new("RGB", (1280, 800), (247, 244, 251)).save(directory / name)
        names.append(name)
    return names


def build_trajectory(task: int, truth: dict, run_dir: Path, answer: str | None = None,
                     origin: str = ORIGIN, screenshots: bool = True,
                     with_login: bool = True, with_quote: bool = True) -> dict:
    """Write a run directory in the schema agent_demo/agent.py produces."""
    shots = run_dir / "screenshots"
    paths = required_paths(task, truth)
    if origin != ORIGIN:
        paths = [path.replace(ORIGIN, origin) for path in paths]
    raw_steps: list[dict] = []
    if with_login:
        for step in login_steps(task, truth):
            entry = dict(step)
            if origin != ORIGIN:
                entry["url"] = entry["url"].replace(ORIGIN, origin)
                if "lands_on" in entry:
                    entry["lands_on"] = entry["lands_on"].replace(ORIGIN, origin)
            raw_steps.append(entry)
    if with_quote:
        for step in quote_steps(truth):
            entry = dict(step)
            if origin != ORIGIN:
                entry["url"] = entry["url"].replace(ORIGIN, origin)
                entry["lands_on"] = entry["lands_on"].replace(ORIGIN, origin)
            raw_steps.append(entry)
    for index, url in enumerate(paths):
        if raw_steps and raw_steps[-1].get("lands_on") == url:
            continue
        raw_steps.append({"url": url, "action": "click", "params": {"index": index + 1}})

    # Expand the plan into recorder-shaped steps. The recorder stores the URL the
    # browser was on before each action, so a navigation shows up as the *next*
    # step's url rather than as a field on the clicking step.
    expanded: list[dict] = []
    for position, raw in enumerate(raw_steps):
        expanded.append(raw)
        landing = raw.get("lands_on")
        if not landing:
            continue
        following = raw_steps[position + 1] if position + 1 < len(raw_steps) else None
        if following is not None and following.get("url") == landing:
            continue
        expanded.append({"url": landing, "action": "click", "params": {"index": 0}})

    names = make_screenshots(shots, len(expanded) + 2) if screenshots else []

    steps = []
    for index, raw in enumerate(expanded):
        step = {
            "step": index,
            "url": raw["url"],
            "title": "FedEx",
            "thought": "follow the task",
            "action": raw["action"],
            "params": raw["params"],
        }
        if screenshots:
            step["screenshot_before"] = names[index]
            step["screenshot_after"] = names[index + 1]
        step["action_result"] = {
            "is_done": False,
            "success": True,
            "error": None,
            "extracted_content": "Clicked" if raw["action"] == "click" else "Typed",
        }
        steps.append(step)

    final_step = {
        "step": len(steps),
        "url": expanded[-1]["url"] if expanded else origin,
        "title": "FedEx",
        "thought": "report the answer",
        "action": "done",
        "params": {"text": answer if answer is not None else compose_answer(task, truth),
                   "success": True},
    }
    if screenshots:
        final_step["screenshot_before"] = names[len(steps)]
        final_step["screenshot_after"] = names[len(steps) + 1]
    steps.append(final_step)

    trajectory = {
        "task": f"FedEx--{task}", "task_id": f"FedEx--{task}", "start_url": f"{origin}/",
        "model": "contract-test", "max_steps": 40, "steps": steps, "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer if answer is not None else compose_answer(task, truth),
        "success_self_report": True, "judge_rubric": "",
        "verifier_path": f"sites/fedex/verify/verify_{task}.py",
    }
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
    return trajectory


def run_verifier(task: int, run_dir: Path, initial_db: Path | None, after_db: Path | None) -> dict:
    command = [sys.executable, str(VERIFY / f"verify_{task}.py"), "--run_dir", str(run_dir),
               "--no_llm", "true"]
    if initial_db:
        command += ["--initial_db", str(initial_db)]
    if after_db:
        command += ["--after_db", str(after_db)]
    environment = dict(os.environ, WH_VERIFIER_SITE_PORTS=str(PORT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(command, capture_output=True, text=True, timeout=300, env=environment,
                            cwd=str(VERIFY))
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"pass": None, "reason": "unparseable", "exit": result.returncode,
                "stderr": result.stderr[-400:]}


class GradingContractTests(unittest.TestCase):
    """Each task is exercised through its real verify_N.py entry point."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = Path(tempfile.mkdtemp(prefix="fedex-contract-"))
        cls.truths = {task: task_ground_truth(SEED, task) for task in range(TASK_COUNT)}

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def case_dir(self, task: int, name: str) -> Path:
        directory = self.workspace / f"task_{task}" / name
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True)
        return directory

    def snapshots(self, directory: Path, mutate=None) -> tuple[Path, Path]:
        initial = directory / "initial.db"
        after = directory / "after.db"
        shutil.copy2(SEED, initial)
        shutil.copy2(SEED, after)
        if mutate:
            with sqlite3.connect(after) as connection:
                mutate(connection)
        return initial, after

    def test_targets_are_unique_and_derivable(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                truth = self.truths[task]
                self.assertTrue(truth["kind"])
                self.assertTrue(compose_answer(task, truth))
                self.assertTrue(contradict_answer(task, truth))

    def test_correct_run_passes(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "correct")
                mutate = None
                if self.truths[task]["kind"] == "create_shipment":
                    mutate = apply_shipment_creation(self.truths[task]["expectation"])
                elif self.truths[task]["kind"] == "schedule_pickup":
                    mutate = apply_pickup_creation(self.truths[task]["expectation"])
                initial, after = self.snapshots(directory, mutate)
                build_trajectory(task, self.truths[task], directory)
                verdict = run_verifier(task, directory, initial, after)
                self.assertTrue(verdict.get("pass"),
                                f"a correct run must pass: {json.dumps(verdict, indent=2)[:1600]}")

    def test_contradictory_answer_fails(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "contradiction")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory,
                                 answer=contradict_answer(task, self.truths[task]))
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"),
                              f"a self-contradicting answer must not earn credit: {verdict}")

    def test_answer_without_navigation_fails(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "answer_only")
                initial, after = self.snapshots(directory)
                trajectory = build_trajectory(task, self.truths[task], directory)
                trajectory["steps"] = [trajectory["steps"][-1]]
                (directory / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_foreign_origin_fails(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "foreign_origin")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory,
                                 origin="https://www.fedex.example.invalid")
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_wrong_port_fails(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "wrong_port")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory,
                                 origin=f"http://localhost:{PORT + 1}")
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_missing_screenshots_fail(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "no_screenshots")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory, screenshots=False)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertEqual("screenshots_decode", verdict.get("reason"))

    def test_forged_screenshot_fails(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "forged_screenshot")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory)
                first = sorted((directory / "screenshots").glob("*.png"))[0]
                first.write_text("this is not a png")
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertEqual("screenshots_decode", verdict.get("reason"))

    def test_wrong_task_id_fails(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "wrong_task_id")
                initial, after = self.snapshots(directory)
                trajectory = build_trajectory(task, self.truths[task], directory)
                trajectory["task_id"] = f"FedEx--{(task + 1) % TASK_COUNT}"
                (directory / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertEqual("task_id_matches", verdict.get("reason"))

    def test_missing_database_snapshots_fail_closed(self) -> None:
        for task in range(TASK_COUNT):
            with self.subTest(task=task):
                directory = self.case_dir(task, "missing_db")
                build_trajectory(task, self.truths[task], directory)
                initial = directory / "initial.db"
                shutil.copy2(SEED, initial)
                verdict = run_verifier(task, directory, initial, None)
                self.assertIs(False, verdict.get("pass"))
                self.assertTrue(verdict.get("infra_error"))
                self.assertEqual("database_unavailable", verdict.get("reason"))

    def test_malformed_trajectory_fails_closed_without_traceback(self) -> None:
        for payload in ("{not json", "[]", '{"steps": "nope"}', '{"steps": [1,2]}'):
            with self.subTest(payload=payload):
                directory = self.case_dir(0, "malformed")
                (directory / "trajectory.json").write_text(payload)
                initial = directory / "initial.db"
                after = directory / "after.db"
                shutil.copy2(SEED, initial)
                shutil.copy2(SEED, after)
                verdict = run_verifier(0, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertTrue(verdict.get("infra_error"))
                self.assertIsNone(verdict.get("stderr"))

    def test_login_tasks_require_the_requested_account(self) -> None:
        from ground_truth import BENCHMARK_ACCOUNTS
        for task, email in sorted(BENCHMARK_ACCOUNTS.items()):
            with self.subTest(task=task):
                directory = self.case_dir(task, "no_login")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory, with_login=False)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertIn("signed_in_requested_account",
                              [line.split("]")[1].split(":")[0].strip()
                               for line in verdict.get("evidence", []) if line.startswith("[FAIL]")])
                self.assertNotEqual(email, "unused")

    def test_other_account_credentials_do_not_satisfy_login(self) -> None:
        from ground_truth import BENCHMARK_ACCOUNTS
        task = 6
        directory = self.case_dir(task, "wrong_account")
        initial, after = self.snapshots(directory)
        build_trajectory(task, self.truths[task], directory)
        data = json.loads((directory / "trajectory.json").read_text())
        for step in data["steps"]:
            if step.get("params", {}).get("text") == BENCHMARK_ACCOUNTS[task]:
                step["params"]["text"] = "alice.j@test.com"
        (directory / "trajectory.json").write_text(json.dumps(data, indent=2))
        verdict = run_verifier(task, directory, initial, after)
        self.assertIs(False, verdict.get("pass"))

    def test_rate_tasks_require_the_requested_quote(self) -> None:
        for task in (3, 4, 17):
            with self.subTest(task=task):
                directory = self.case_dir(task, "no_quote")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory, with_quote=False)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_rate_tasks_reject_a_different_quote(self) -> None:
        for task in (3, 4, 17):
            with self.subTest(task=task):
                directory = self.case_dir(task, "wrong_quote")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory)
                wrong = issue_quote_token(QuoteRequest("NY", "NY", 1.0, "Envelope"))
                data = json.loads((directory / "trajectory.json").read_text())
                rewritten = 0
                for step in data["steps"]:
                    url = step.get("url", "")
                    if url.startswith(f"{ORIGIN}/rate-estimate?quote="):
                        step["url"] = f"{ORIGIN}/rate-estimate?quote={wrong}"
                        rewritten += 1
                self.assertLessEqual(1, rewritten, "no signed quote step to degrade")
                (directory / "trajectory.json").write_text(json.dumps(data, indent=2))
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_shortcut_navigation_does_not_earn_credit(self) -> None:
        """Reaching the detail page directly must not satisfy a search-bound task."""
        cases = {
            0: f"{ORIGIN}/track/results?numbers=FDX000000000",
            1: f"{ORIGIN}/track/results?numbers=FDX000000000",
            9: f"{ORIGIN}/locations?q=Miami",
            14: f"{ORIGIN}/search?q=anything-else",
            16: f"{ORIGIN}/track/results?numbers=NOT-THE-PACKAGE",
            2: f"{ORIGIN}/support?q=invoices",
            11: f"{ORIGIN}/search?q=invoices",
        }
        for task, shortcut in cases.items():
            with self.subTest(task=task):
                directory = self.case_dir(task, "shortcut")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory)
                data = json.loads((directory / "trajectory.json").read_text())
                replaced = False
                for step in data["steps"]:
                    url = step.get("url", "")
                    if url.startswith(f"{ORIGIN}/track/results") or url.startswith(f"{ORIGIN}/locations?") \
                            or url.startswith(f"{ORIGIN}/search?") or url.startswith(f"{ORIGIN}/support?"):
                        step["url"] = shortcut
                        replaced = True
                self.assertTrue(replaced, f"no search step to degrade for task {task}")
                (directory / "trajectory.json").write_text(json.dumps(data, indent=2))
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"),
                              f"shortcut navigation must not pass task {task}: {verdict}")

    def test_read_only_tasks_reject_any_state_change(self) -> None:
        read_only = [task for task in range(TASK_COUNT)
                     if self.truths[task]["kind"] not in ("create_shipment", "schedule_pickup")]
        self.assertEqual(16, len(read_only))
        for task in read_only:
            with self.subTest(task=task):
                directory = self.case_dir(task, "state_changed")
                initial, after = self.snapshots(
                    directory, lambda connection: connection.execute(
                        "UPDATE users SET city='Tampered' WHERE id=1"))
                build_trajectory(task, self.truths[task], directory)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertEqual("state_read_only", verdict.get("reason"))

    def test_state_tasks_reject_an_unchanged_database(self) -> None:
        for task in (12, 13):
            with self.subTest(task=task):
                directory = self.case_dir(task, "state_unchanged")
                initial, after = self.snapshots(directory)
                build_trajectory(task, self.truths[task], directory)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_state_tasks_reject_unrelated_writes(self) -> None:
        for task, table in ((12, "claims"), (13, "search_logs")):
            with self.subTest(task=task):
                directory = self.case_dir(task, "unrelated_write")
                initial, after = self.snapshots(directory)
                with sqlite3.connect(after) as connection:
                    if table == "claims":
                        # Any existing tracking number satisfies the foreign key; it is
                        # read from the snapshot so this file restates no graded value.
                        parent = connection.execute(
                            "SELECT tracking_number FROM tracking_records ORDER BY id LIMIT 1"
                        ).fetchone()
                        connection.execute(
                            "INSERT INTO claims (claim_number,user_id,tracking_number,claim_type,"
                            "amount,status,opened_on,note) VALUES "
                            "('CLM-9999',1,?,'Missing package',1.0,'Closed','2026-06-04','x')",
                            (parent[0],))
                    else:
                        connection.execute(
                            "INSERT INTO search_logs (query,search_type,created_on) "
                            "VALUES ('tampered','global','2026-06-04')")
                build_trajectory(task, self.truths[task], directory)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))

    def test_state_tasks_reject_a_stale_seed_version(self) -> None:
        for task in (12, 13):
            with self.subTest(task=task):
                directory = self.case_dir(task, "stale_seed")
                initial, after = self.snapshots(directory)
                with sqlite3.connect(initial) as connection:
                    connection.execute("UPDATE seed_metadata SET value='fedex-source-v1'")
                build_trajectory(task, self.truths[task], directory)
                verdict = run_verifier(task, directory, initial, after)
                self.assertIs(False, verdict.get("pass"))
                self.assertTrue(verdict.get("infra_error"))
                self.assertEqual("initial_snapshot_invalid", verdict.get("reason"))


def apply_shipment_creation(expectation: dict):
    """Write the rows a correct shipment flow produces, using derived values."""

    def mutate(connection: sqlite3.Connection) -> None:
        from shipping_rules import DEMO_SHIPMENT_LABEL
        user_id = connection.execute("SELECT id FROM users WHERE lower(email)=lower(?)",
                                     (expectation["user_email"],)).fetchone()[0]
        connection.execute(
            """INSERT INTO shipments (shipment_code, tracking_number, user_id, service_slug,
                   package_type, package_weight, origin_city, origin_state, destination_city,
                   destination_state, recipient_name, declared_value, total_cost, fulfillment_mode,
                   pickup_location_slug, pickup_window, status, created_on, invoice_number,
                   reference_label)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (expectation["shipment_code"], expectation["tracking_number"], user_id,
             expectation["service_slug"], expectation["package_type"], expectation["package_weight"],
             expectation["origin_city"], expectation["origin_state"], expectation["destination_city"],
             expectation["destination_state"], expectation["recipient_name"],
             expectation["declared_value"], expectation["total_cost"], expectation["fulfillment_mode"],
             expectation["pickup_location_slug"], expectation["pickup_window"], expectation["status"],
             expectation["created_on"], expectation["invoice_number"], DEMO_SHIPMENT_LABEL))
        shipment_id = connection.execute("SELECT id FROM shipments WHERE shipment_code=?",
                                         (expectation["shipment_code"],)).fetchone()[0]
        connection.execute(
            """INSERT INTO tracking_records (tracking_number, shipment_id, user_id, recipient_name,
                   sender_name, origin_city, origin_state, destination_city, destination_state,
                   service_slug, package_type, weight_lb, status_stage, status_summary, ship_date,
                   estimated_delivery, latest_scan, package_count, signature_required,
                   dropoff_location_slug)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (expectation["tracking_number"], shipment_id, user_id, expectation["recipient_name"],
             expectation["sender_name"], expectation["origin_city"], expectation["origin_state"],
             expectation["destination_city"], expectation["destination_state"],
             expectation["service_slug"], expectation["package_type"], expectation["package_weight"],
             expectation["status"], expectation["status_summary"], expectation["created_on"],
             expectation["estimated_delivery"], expectation["status"], expectation["package_count"],
             expectation["signature_required"], expectation["pickup_location_slug"]))
        record_id = connection.execute("SELECT id FROM tracking_records WHERE tracking_number=?",
                                       (expectation["tracking_number"],)).fetchone()[0]
        for event in expectation["timeline"]:
            connection.execute(
                """INSERT INTO tracking_events (tracking_record_id, sequence, event_time,
                       location_label, status_label, details)
                   VALUES (?,?,?,?,?,?)""",
                (record_id, event["sequence"], event["event_time"], event["location_label"],
                 event["status_label"], event["details"]))
        connection.execute(
            """INSERT INTO invoices (invoice_number, user_id, shipment_id, billed_on, due_date,
                   amount, status)
               VALUES (?,?,?,?,?,?,?)""",
            (expectation["invoice_number"], user_id, shipment_id, expectation["invoice_billed_on"],
             expectation["invoice_due_date"], expectation["total_cost"], "Open"))

    return mutate


def apply_pickup_creation(expectation: dict):
    """Write the rows a correct pickup flow produces, using derived values."""

    def mutate(connection: sqlite3.Connection) -> None:
        user_id = connection.execute("SELECT id FROM users WHERE lower(email)=lower(?)",
                                     (expectation["user_email"],)).fetchone()[0]
        location_id = connection.execute("SELECT id FROM locations WHERE slug=?",
                                        (expectation["location_slug"],)).fetchone()[0]
        connection.execute(
            """INSERT INTO pickup_requests (confirmation_code, user_id, location_id, slot_date,
                   time_window, package_count, status, created_on)
               VALUES (?,?,?,?,?,?,?,?)""",
            (expectation["confirmation_code"], user_id, location_id, expectation["slot_date"],
             expectation["time_window"], expectation["package_count"], expectation["status"],
             expectation["created_on"]))
        connection.execute("UPDATE pickup_slots SET remaining_capacity=? WHERE id=?",
                           (expectation["capacity_after"], expectation["slot_id"]))

    return mutate


if __name__ == "__main__":
    unittest.main()
