#!/usr/bin/env python3
"""Self-check suite for the Allrecipes grading contract (45 verifiers).

Run from the agent_demo project:

    cd agent_demo
    uv run --with pytest python -m pytest ../sites/allrecipes/verify/test_verifiers.py

The suite never touches the network, the LLM, or the database. It exercises
every verifier against SYNTHETIC run packages built from the verifier's own
hardcoded ground truth:

  positive       a run that navigated to a qualifying page and reports the
                  on-page facts -> the verifier MUST emit PASS (exit 0)
  no-op          a run that only opened the homepage with an empty answer
                  -> the verifier MUST FAIL (exit 1)
  shortcut       a correct answer but no on-site navigation for it
                  -> the verifier MUST FAIL
  wrong content  a qualifying page opened but the answer commits to a wrong
                  recipe / wrong facts -> the verifier MUST FAIL
  tampered run   a run package missing screenshots, or a run dir without
                  trajectory.json -> the verifier MUST FAIL

Every case runs the real verifier script as a subprocess (the same entry point
eval_judge.py uses) and asserts on both its JSON verdict and its exit code.
"""
import base64
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent
PY = sys.executable

# 1x1 transparent PNG: screenshots are required to EXIST by the run gate; their
# pixels are never graded (these verifiers are deterministic text/URL graders).
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

TASK_IDS = [f"Allrecipes--{n}" for n in range(45)]
EXTRAS = {
    "Allrecipes--0": "title_only", "Allrecipes--1": "title_only",
    "Allrecipes--2": "title_only", "Allrecipes--3": "title_only",
    "Allrecipes--4": "title_only", "Allrecipes--5": "ing6",
    "Allrecipes--6": "title_only", "Allrecipes--7": "ing6_dirs2",
    "Allrecipes--8": "ing4", "Allrecipes--9": "ing4_prep_cook",
    "Allrecipes--10": "special_10", "Allrecipes--11": "title_only",
    "Allrecipes--12": "ing6", "Allrecipes--13": "iron_nut",
    "Allrecipes--14": "title_only", "Allrecipes--15": "ing4_dirs2",
    "Allrecipes--16": "rc_ing3", "Allrecipes--17": "special_17",
    "Allrecipes--18": "title_only", "Allrecipes--19": "ing4_prep_cook",
    "Allrecipes--20": "calories", "Allrecipes--21": "ing4_total",
    "Allrecipes--22": "avocado_nutrition", "Allrecipes--23": "ing3",
    "Allrecipes--24": "prep_servings", "Allrecipes--25": "ing5_prep_total",
    "Allrecipes--26": "ing5_cook_dirs2", "Allrecipes--27": "ing4_prep_dirs2",
    "Allrecipes--28": "ing4_prep_cook", "Allrecipes--29": "grilled_fish",
    "Allrecipes--30": "smoothie", "Allrecipes--31": "paella",
    "Allrecipes--32": "stew_first5", "Allrecipes--33": "carbs_nut",
    "Allrecipes--34": "salmon_seasoning", "Allrecipes--35": "meatball_meat",
    "Allrecipes--36": "apple_maxtemp", "Allrecipes--37": "greek_salad",
    "Allrecipes--38": "ratatouille", "Allrecipes--39": "sushi",
    "Allrecipes--40": "special_40", "Allrecipes--41": "special_41",
    "Allrecipes--42": "title_only", "Allrecipes--43": "title_only",
    "Allrecipes--44": "special_44",
}


def load_ground_truth(task_id):
    n = task_id.split("--")[1]
    spec = importlib.util.spec_from_file_location(
        f"verify_{n}", VERIFY_DIR / f"verify_{n}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.GROUND_TRUTH


def make_run(root, name, steps, answer, with_screenshots=True,
             with_trajectory=True):
    d = Path(root) / name
    (d / "screenshots").mkdir(parents=True, exist_ok=True)
    if with_screenshots:
        (d / "screenshots" / "step_000.png").write_bytes(PNG)
        (d / "screenshots" / "step_001.png").write_bytes(PNG)
    if with_trajectory:
        traj = {
            "task": "synthetic", "task_id": "x",
            "start_url": "http://localhost:41000/",
            "steps": steps, "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": answer,
            "final_url": steps[-1].get("url_after") or steps[-1].get("url", ""),
        }
        (d / "trajectory.json").write_text(json.dumps(traj))
    return str(d)


def run_verifier(task_id, run_dir, extra=("--no_llm", "True")):
    n = task_id.split("--")[1]
    cmd = [PY, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", run_dir]
    cmd += list(extra)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(proc.stdout)
    except Exception:
        verdict = {"pass": False, "parse_error": proc.stdout[-400:],
                   "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


def home_steps():
    return [{"step": 0, "url": "http://localhost:41000/",
             "url_after": "http://localhost:41000/",
             "action": "navigate", "params": {}}]


def nav_steps(slug):
    u = f"http://localhost:41000/recipe/{slug}"
    return [
        {"step": 0, "url": "http://localhost:41000/",
         "url_after": "http://localhost:41000/search?q=test", "action": "navigate",
         "params": {}},
        {"step": 1, "url": "http://localhost:41000/search?q=test",
         "url_after": u, "action": "click", "params": {}},
        {"step": 2, "url": u, "url_after": u, "action": "done", "params": {}},
    ]


# ---------------------------------------------------------------- answer builders

def facts_answer(task_id, row, idx=0):
    kind = EXTRAS[task_id]
    title = row["title"]
    ing = lambda k: ", ".join(row["ingredients"][:k])
    if kind == "title_only":
        return f"{title} is the recipe that satisfies every constraint."
    if kind == "ing6":
        return f"{title}: shopping list — {ing(8)}."
    if kind == "ing6_dirs2":
        steps = ". ".join(row["steps"][:3])
        return f"{title} — ingredients: {ing(8)}. Steps: {steps}."
    if kind == "ing4_dirs2":
        steps = ". ".join(row["steps"][:3])
        return f"{title} — ingredients: {ing(6)}. Steps: {steps}."
    if kind == "ing4":
        return f"{title} — main ingredients: {ing(5)}."
    if kind == "ing3":
        return f"{title} — primary ingredients: {ing(4)}."
    if kind == "ing4_prep_cook":
        return (f"{title} — ingredients: {ing(6)}. "
                f"Prep time {row['prep']}, cook time {row['cook']}.")
    if kind == "ing4_total":
        return (f"{title} — ingredients: {ing(6)}. "
                f"Total time {row['total']} "
                f"(prep {row['prep']}, cook {row['cook']}).")
    if kind == "rc_ing3":
        return (f"{title} — it has {row['review_count']} reviews. "
                f"Main ingredients: {ing(4)}.")
    if kind == "iron_nut":
        nut = row["nutrition"]
        return (f"{title} — Nutrition Facts per serving: "
                f"Calories {nut.get('CALORIES')}, Fat {nut.get('FAT')}, "
                f"Protein {nut.get('PROTEIN')}, Iron {nut.get('IRON')}.")
    if kind == "calories":
        return f"{title} — {row['calories']} calories per serving."
    if kind == "avocado_nutrition":
        nut = row["nutrition"]
        return (f"{title} — nutrition per serving: "
                f"{nut.get('CALORIES')} calories, {nut.get('FAT')} fat, "
                f"{nut.get('CARBS')} carbs.")
    if kind == "prep_servings":
        return f"{title} — prep time {row['prep']}, servings {row['servings']}."
    if kind == "ing5_prep_total":
        return (f"{title} — shopping list: {ing(7)}. "
                f"Prep time {row['prep']}, total time {row['total']}.")
    if kind == "ing5_cook_dirs2":
        steps = ". ".join(row["steps"][:3])
        return (f"{title} — ingredients: {ing(7)}. Cook time {row['cook']}. "
                f"Steps: {steps}.")
    if kind == "ing4_prep_dirs2":
        steps = ". ".join(row["steps"][:3])
        return (f"{title} — ingredients: {ing(6)}. Prep time {row['prep']}. "
                f"Instructions: {steps}.")
    if kind == "grilled_fish":
        return (f"{title} — a Mediterranean-style grilled fish with olives. "
                f"Ingredients: {ing(6)}. Cooked by grilling. "
                f"Total time {row['total']}.")
    if kind == "smoothie":
        steps = ". ".join(row["steps"][:3])
        return (f"{title} — vegan smoothie bowl with banana and spinach leaves. "
                f"Ingredients: {ing(6)}. Prep time {row['prep']}. Steps: {steps}.")
    if kind == "paella":
        steps = ". ".join(row["steps"][:3])
        return (f"{title} — seafood paella with shrimp and mussels. "
                f"Ingredients: {ing(7)}. Total time {row['total']}. Steps: {steps}.")
    if kind == "stew_first5":
        first5 = ", ".join(row["first5"])
        return f"{title} — slow cooker beef stew. Cooking time {row['cook']}. First five ingredients: {first5}."
    if kind == "carbs_nut":
        nut = row["nutrition"]
        return (f"{title} — Nutrition Facts: {nut.get('CALORIES')} calories, "
                f"Total Carbohydrate {nut.get('TOTAL CARBOHYDRATE')}.")
    if kind == "salmon_seasoning":
        return (f"{title} — primary seasoning lemon and dill; "
                f"estimated cooking time {row['cook']} (total {row['total']}).")
    if kind == "meatball_meat":
        return (f"{title} — made with ground beef; "
                f"overall cooking time {row['cook']} (total {row['total']}).")
    if kind == "apple_maxtemp":
        return (f"{title} — the maximum temperature mentioned in the Directions "
                f"is {row['max_oven_temp']} degrees F.")
    if kind == "greek_salad":
        return (f"{title} — the primary cheese is feta; the dressing is a red "
                f"wine vinegar and olive oil dressing with oregano.")
    if kind == "ratatouille":
        return (f"{title} — vegetables: eggplant, zucchini, bell pepper, "
                f"tomatoes, onion. Overall cooking time {row['cook']} "
                f"(total {row['total']}).")
    if kind == "sushi":
        nut = row["nutrition"]
        return (f"{title} — main ingredients: {', '.join(row['ingredients'][:6])}. "
                f"Nutrition Facts: {nut.get('CALORIES')} calories, "
                f"{nut.get('CARBS')} carbs. Storage: store refrigerated in an "
                f"airtight container and eat within 24 hours.")
    raise AssertionError(f"unknown extras kind {kind} for {task_id}")


def special_positive(task_id, root):
    if task_id == "Allrecipes--10":
        steps = [
            {"step": 0, "url": "http://localhost:41000/",
             "url_after": "http://localhost:41000/collections/popular-1960s",
             "action": "navigate", "params": {}},
            {"step": 1, "url": "http://localhost:41000/collections/popular-1960s",
             "url_after": "http://localhost:41000/collections/popular-1960s",
             "action": "done", "params": {}},
        ]
        ans = ("The second recipe in The Most Popular Recipes of the 1960s "
               "collection is Chicken à la King, with a prep time of 15 mins "
               "and a total time of 40 mins.")
        return make_run(root, f"pos-{task_id}", steps, ans)
    if task_id == "Allrecipes--17":
        run_dir = make_run(root, f"pos-{task_id}",
                           nav_steps("easy-vegetarian-spinach-lasagna"),
                           "placeholder")
        # rewrite the answer with the real review fragments
        traj_path = Path(run_dir) / "trajectory.json"
        traj = json.loads(traj_path.read_text())
        traj["final_answer"] = (
            "Easy Vegetarian Spinach Lasagna — the latest review says: "
            "\"Made this last night — my whole family loved it. The spinach "
            "filling was perfect, and the top was golden and bubbly. Will "
            "definitely make again!\"")
        traj_path.write_text(json.dumps(traj))
        return run_dir
    if task_id == "Allrecipes--40":
        steps = [
            {"step": 0, "url": "http://localhost:41000/",
             "url_after": "http://localhost:41000/about", "action": "navigate",
             "params": {}},
            {"step": 1, "url": "http://localhost:41000/about",
             "url_after": "http://localhost:41000/about", "action": "done",
             "params": {}},
        ]
        ans = ("The Allrecipes Allstars are a passionate community of home "
               "cooks and food content creators, including Chef John and "
               "Nicole McLaughlin, who test recipes and share inspiration.")
        return make_run(root, f"pos-{task_id}", steps, ans)
    if task_id == "Allrecipes--41":
        steps = [
            {"step": 0, "url": "http://localhost:41000/",
             "url_after": "http://localhost:41000/dinners", "action": "navigate",
             "params": {}},
            {"step": 1, "url": "http://localhost:41000/dinners",
             "url_after": "http://localhost:41000/dinners", "action": "done",
             "params": {}},
        ]
        gt = load_ground_truth(task_id)
        titles = gt[0]["recommended"][:3]
        ans = "Recommended dinner recipes: " + "; ".join(titles) + "."
        return make_run(root, f"pos-{task_id}", steps, ans)
    if task_id == "Allrecipes--44":
        steps = [
            {"step": 0, "url": "http://localhost:41000/",
             "url_after": "http://localhost:41000/occasions", "action": "navigate",
             "params": {}},
            {"step": 1, "url": "http://localhost:41000/occasions",
             "url_after": "http://localhost:41000/occasions", "action": "done",
             "params": {}},
        ]
        gt = load_ground_truth(task_id)
        ans = "Holiday recipe sections: " + ", ".join(gt[0]["occasions"][:8]) + "."
        return make_run(root, f"pos-{task_id}", steps, ans)
    raise AssertionError(task_id)


def build_positive(task_id, root):
    kind = EXTRAS[task_id]
    if kind.startswith("special"):
        return special_positive(task_id, root)
    gt = load_ground_truth(task_id)
    row = gt[0]
    run_dir = make_run(root, f"pos-{task_id}", nav_steps(row["slug"]),
                       "placeholder")
    traj_path = Path(run_dir) / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["final_answer"] = facts_answer(task_id, row)
    traj_path.write_text(json.dumps(traj))
    return run_dir


def build_wrong_content(task_id, root):
    """A qualifying page opened, but the answer commits to the wrong thing."""
    kind = EXTRAS[task_id]
    gt = load_ground_truth(task_id)
    if kind.startswith("special") or len(gt) < 2:
        # single-target tasks: open the right page, answer with wrong facts
        if task_id == "Allrecipes--10":
            steps = [
                {"step": 0, "url": "http://localhost:41000/",
                 "url_after": "http://localhost:41000/collections/popular-1960s",
                 "action": "navigate", "params": {}},
                {"step": 1, "url": "http://localhost:41000/collections/popular-1960s",
                 "url_after": "http://localhost:41000/collections/popular-1960s",
                 "action": "done", "params": {}},
            ]
            ans = ("The second recipe in the 1960s collection is Swedish "
                   "Meatballs with a prep time of 5 mins and total time of "
                   "25 mins.")
            return make_run(root, f"wrong-{task_id}", steps, ans)
        if task_id == "Allrecipes--40":
            steps = [
                {"step": 0, "url": "http://localhost:41000/",
                 "url_after": "http://localhost:41000/about", "action": "navigate",
                 "params": {}},
                {"step": 1, "url": "http://localhost:41000/about",
                 "url_after": "http://localhost:41000/about", "action": "done",
                 "params": {}},
            ]
            ans = "The Allrecipes Allstars are a great community of cooks."
            return make_run(root, f"wrong-{task_id}", steps, ans)
        if task_id == "Allrecipes--41":
            steps = [
                {"step": 0, "url": "http://localhost:41000/",
                 "url_after": "http://localhost:41000/dinners", "action": "navigate",
                 "params": {}},
                {"step": 1, "url": "http://localhost:41000/dinners",
                 "url_after": "http://localhost:41000/dinners", "action": "done",
                 "params": {}},
            ]
            ans = ("Recommended dinner recipes: Chocolate Chip Cookies; "
                   "Banana Bread; Greek Salad.")
            return make_run(root, f"wrong-{task_id}", steps, ans)
        if task_id == "Allrecipes--44":
            steps = [
                {"step": 0, "url": "http://localhost:41000/",
                 "url_after": "http://localhost:41000/occasions", "action": "navigate",
                 "params": {}},
                {"step": 1, "url": "http://localhost:41000/occasions",
                 "url_after": "http://localhost:41000/occasions", "action": "done",
                 "params": {}},
            ]
            ans = "Holiday sections: Christmas, Thanksgiving, Easter."
            return make_run(root, f"wrong-{task_id}", steps, ans)
        if task_id == "Allrecipes--17":
            return make_run(root, f"wrong-{task_id}",
                            nav_steps("easy-vegetarian-spinach-lasagna"),
                            "Easy Vegetarian Spinach Lasagna — the latest "
                            "review says it was terrible and nobody liked "
                            "it.")
        if task_id == "Allrecipes--6":
            # single qualifying recipe: open it, but answer with a
            # near-miss non-qualifying recipe (rating 3.8 < four stars)
            return make_run(root, f"wrong-{task_id}",
                            nav_steps("vegetarian-zucchini-lasagna"),
                            "Roasted Veggie Lasagna is the vegetarian lasagna "
                            "with a four-star rating and over 500 reviews.")
        if task_id == "Allrecipes--16":
            return make_run(root, f"wrong-{task_id}",
                            nav_steps("award-winning-soft-chocolate-chip-cookies"),
                            "Chewy Chocolate Chip Cookies is the five-star "
                            "rated chocolate chip cookie recipe; it has 1759 "
                            "reviews and main ingredients butter, sugar, "
                            "flour, chocolate chips.")
        if task_id == "Allrecipes--34":
            return make_run(root, f"wrong-{task_id}",
                            nav_steps("simple-baked-salmon-with-lemon"),
                            "Baked Salmon with Garlic Butter is the baked "
                            "salmon; primary seasoning garlic and parsley, "
                            "cooking time 49 mins.")
        row = gt[0]
        ans = f"{row['title']} — wrong facts: 9999 reviews, 1 minute prep."
        return make_run(root, f"wrong-{task_id}", nav_steps(row["slug"]), ans)
    # multi-candidate: open candidate A, name candidate B (never opened)
    opened_row, named_row = gt[0], gt[1]
    ans = f"{named_row['title']} is the recipe that satisfies every constraint."
    return make_run(root, f"wrong-{task_id}", nav_steps(opened_row["slug"]), ans)


# ---------------------------------------------------------------- test cases

@pytest.fixture(scope="module")
def tmp_root(tmp_path_factory):
    return tmp_path_factory.mktemp("allrecipes_runs")


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_verifier_contract(tmp_root, task_id):
    # 1. positive: qualifying navigation + on-page facts -> PASS
    pos = build_positive(task_id, tmp_root)
    rc, verdict = run_verifier(task_id, pos)
    assert rc == 0 and verdict.get("pass") is True, \
        f"positive case must PASS: rc={rc} verdict={verdict}"

    # 2. no-op: homepage only, empty answer -> FAIL
    noop = make_run(tmp_root, f"noop-{task_id}", home_steps(), "")
    rc, verdict = run_verifier(task_id, noop)
    assert rc == 1 and verdict.get("pass") is False, \
        f"no-op case must FAIL: rc={rc} verdict={verdict}"

    # 3. shortcut: correct answer, no qualifying navigation -> FAIL
    kind = EXTRAS[task_id]
    if kind.startswith("special"):
        # correct textual answer, but the required page was never opened
        pos_dir = Path(pos)
        traj = json.loads((pos_dir / "trajectory.json").read_text())
        traj["steps"] = home_steps()
        traj["final_url"] = "http://localhost:41000/"
        shortcut = make_run(tmp_root, f"shortcut-{task_id}", home_steps(),
                            traj["final_answer"])
    else:
        gt = load_ground_truth(task_id)
        answer = facts_answer(task_id, gt[0])
        shortcut = make_run(tmp_root, f"shortcut-{task_id}", home_steps(), answer)
    rc, verdict = run_verifier(task_id, shortcut)
    assert rc == 1 and verdict.get("pass") is False, \
        f"shortcut case must FAIL: rc={rc} verdict={verdict}"

    # 4. wrong content: qualifying page opened, answer commits to the wrong
    #    recipe / wrong facts -> FAIL
    wrong = build_wrong_content(task_id, tmp_root)
    rc, verdict = run_verifier(task_id, wrong)
    assert rc == 1 and verdict.get("pass") is False, \
        f"wrong-content case must FAIL: rc={rc} verdict={verdict}"

    # 5. tampered run package: trajectory references the recipe but the
    #    screenshots are missing -> FAIL
    kind = EXTRAS[task_id]
    if kind.startswith("special"):
        steps = home_steps()
    else:
        steps = nav_steps(load_ground_truth(task_id)[0]["slug"])
    tampered = make_run(tmp_root, f"tampered-{task_id}", steps, "whatever answer",
                       with_screenshots=False)
    rc, verdict = run_verifier(task_id, tampered)
    assert rc == 1 and verdict.get("pass") is False, \
        f"tampered package must FAIL: rc={rc} verdict={verdict}"

    # 6. missing trajectory -> FAIL
    missing = make_run(tmp_root, f"missing-{task_id}", home_steps(), "answer",
                       with_trajectory=False)
    rc, verdict = run_verifier(task_id, missing)
    assert rc == 1 and verdict.get("pass") is False, \
        f"missing trajectory must FAIL: rc={rc} verdict={verdict}"


def test_tasks_jsonl_contract():
    tasks = VERIFY_DIR.parent / "tasks.jsonl"
    rows = [json.loads(l) for l in tasks.read_text().splitlines() if l.strip()]
    assert len(rows) == 45
    for row in rows:
        assert list(row.keys()) == ["web_name", "id", "ques", "web",
                                    "upstream_url", "verifier_path",
                                    "judge_rubric"], row["id"]
        assert "answer" not in row, f"answer key leaked in {row['id']}"
        n = row["id"].split("--")[1]
        assert row["verifier_path"] == f"sites/allrecipes/verify/verify_{n}.py"
        assert (VERIFY_DIR / f"verify_{n}.py").is_file(), row["verifier_path"]
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS."), row["id"]
        assert len(row["judge_rubric"]) > 80, row["id"]
