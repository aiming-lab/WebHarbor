#!/usr/bin/env python3
"""Positive and adversarial regression tests for every GitHub verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact trajectory shape and the ground-truth answer the
served mirror pages yield (recorded during the reviewer's Playwright audit of
the running container — see the worker's audit evidence), and the adversarial
cases prove the verifiers reject no-op runs, recall shortcuts, wrong answers,
foreign task ids, broken run packages, and DB writes.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB --no_llm True
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because the
repository tracks no instance assets; set WH_CONTAINER to point at the site's
container when it is not the default wh-ver-github.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
REPO_ROOT = SITE_DIR.parent.parent
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://127.0.0.1:41006"
TASKS = list(range(41))

# minimal valid PNG (the package gate requires the referenced files to exist)
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080200000090"
    "7753de0000000c4944415408d763f8cfc0f01f0005050201ede0a2f40000"
    "000049454e44ae426082"
)


# task -> (navigation paths a compliant trajectory must contain, model answer)
POSITIVE = {
    0: (["/search?q=climate+change+data+visualization&sort=stars",
         "/climate-viz/climate-change-dashboard"],
        "The most-starred project related to climate change data visualization is "
        "climate-viz/climate-change-dashboard, an interactive dashboard built on "
        "D3.js, with 12.8k stars."),
    1: (["/search?q=machine+learning+decision+trees+language%3Apython+updated%3A%3E2024-05-13",
         "/forest-ai/xgboost-trees"],
        "forest-ai/xgboost-trees — gradient boosted decision trees for Python ML "
        "pipelines — is the Python ML decision-trees repository updated within the "
        "last 2 days (updated 1 day ago, 2.1k stars)."),
    2: (["/trending?l=Python"],
        "tensorflow/tensorflow tops the trending Python repositories with 185.0k "
        "stars."),
    3: (["/pricing"],
        "Enterprise includes 48 GB more GitHub Packages storage than Team "
        "(50 GB vs 2 GB)."),
    4: (["/search?q=language%3Ajavascript+created%3A%3E2024-04-15&has_readme=1&sort=stars",
         "/big-js-fresh/turbo-front"],
        "The most popular JavaScript repository created in the last 30 days with a "
        "README is big-js-fresh/turbo-front (5.4k stars), a fresh front-end framework "
        "whose card notes the full README."),
    5: (["/search?q=language%3Apython+updated%3A%3E2024-05-13+stars%3A%3E%3D500&sort=stars"],
        "tensorflow/tensorflow (185.0k stars) is a Python repository updated in the "
        "past 2 days with at least 500 stars."),
    6: (["/search?q=cryptocurrency+wallet+updated%3A%3E2024-04-15",
         "/cryptolab/crypto-wallet/contributors"],
        "cryptolab/crypto-wallet (9.4k stars, updated 5 days ago) — the top three "
        "contributors are satoshi-fan, blockchain-dev and wallet-maintainer."),
    7: (["/search?q=albert", "/google-research/albert/commits",
         "/google-research/albert/commit/68a2c92"],
        "The most recent commit (68a2c92, 'fix: handle empty input sequence in "
        "tokenization') changed 14 files including tokenization.py, modeling.py and "
        "requirements.txt (+737/−166)."),
    8: (["/search?q=vuex", "/vuejs-vuex/vuex/releases"],
        "Vuex's latest stable release is v4.1.0, published on 2022-06-23."),
    9: (["/search?q=created%3A%3E2024-05-08+stars%3A%3E%3D50&sort=stars",
         "/gaming-fresh/pixel-art-editor-fresh"],
        "gaming-fresh/pixel-art-editor-fresh — a brand-new in-browser pixel art "
        "editor, written in TypeScript with 5.0k stars — was created 4 days ago "
        "(within the last week) and has well over 50 stars."),
    10: (["/features/copilot"],
         "Copilot Individual costs $100 USD per year ($10/month). Features: code "
         "completion in your IDE, Copilot Chat in IDE and on GitHub.com, chat on "
         "GitHub Mobile, access to GPT-4o and Claude models, code review and "
         "explanation, pull request summaries, and third-party model extensions."),
    11: (["/search?q=climate+change+created%3A2023-01-01..2023-01-31",
          "/eco-2023/climate-tracker"],
         "eco-2023/climate-tracker — a Python climate change tracker for tracking "
         "emissions and global temperature anomalies — was started in January 2023."),
    12: (["/electron/electron/releases"],
         "electron/electron's latest release is v29.1.4, published on 2024-03-12."),
    13: (["/trending", "/topics/machine-learning"],
         "The top-trending Machine Learning project is tensorflow/tensorflow with "
         "185.0k stars."),
    14: (["/microsoft/vscode/contributors"],
         "The top three contributors of microsoft/vscode are bpasero (Benjamin "
         "Pasero), jrieken (Johannes Rieken), and joaomoreno (João Moreno)."),
    15: (["/search?q=quantum+computing+updated%3A%3E2024-05-08+stars%3A%3E%3D50",
          "/qsim-fast/quantum-state-simulator"],
         "qsim-fast/quantum-state-simulator (C++, 2.7k stars, updated 3 days ago) is "
         "a high-performance quantum computing state-vector simulator with GPU "
         "support."),
    16: (["/skills"],
         "There are 4 courses under the 'First day on GitHub' heading."),
    17: (["/search?q=language%3Ac%2B%2B+updated%3A%3E2024-05-08+stars%3A%3E%3D500&sort=updated",
          "/electron/electron"],
         "electron/electron (C++, 112.0k stars, updated just now) builds "
         "cross-platform desktop apps with JavaScript, HTML, and CSS."),
    18: (["/search?q=image+processing&sort=stars", "/imgproc/opencv-next"],
         "imgproc/opencv-next is the most starred image processing toolkit on "
         "GitHub with 78.0k stars — an open source computer vision and image "
         "processing library."),
    19: (["/search?q=language%3Apython+topic%3Aweb-scraping+stars%3A%3E100&sort=updated",
          "/reddit-scrape/reddit-web-scraper-py"],
         "The most recently updated Python repository tagged web-scraping with over "
         "100 stars is reddit-scrape/reddit-web-scraper-py, updated 3 hours ago "
         "(1.4k stars) — a Python web scraping library for Reddit comments, posts, "
         "and user history."),
    20: (["/features/copilot/faq"],
         "Copilot Chat is available in GitHub Mobile on iOS and Android for all "
         "paid Copilot subscribers."),
    21: (["/resources", "/resources/security"],
         "GitHub Advanced Security is a suite of tools built into the developer "
         "workflow. It runs on every pull request: code scanning analyzes code for "
         "200+ vulnerability classes with CodeQL, secret scanning detects leaked "
         "tokens, and dependency review flags vulnerable packages."),
    22: (["/search?q=natural+language+processing+language%3Aruby+updated%3A%3E2024-05-08",
          "/ruby-nlp/rnlp"],
         "ruby-nlp/rnlp (Ruby, 1.8k stars, updated 4 days ago) is a Ruby natural "
         "language processing library with tokenizer, stemmer, and POS tagger."),
    23: (["/ohmyzsh/ohmyzsh/wiki", "/ohmyzsh/ohmyzsh/wiki/themes"],
         "Set ZSH_THEME=\"agnoster\" in your ~/.zshrc, then reload the shell with "
         "source ~/.zshrc or open a new terminal. Note that agnoster is a powerline "
         "theme that requires a Powerline-compatible font."),
    24: (["/angular/angular/issues?q=is:closed"],
         "The last three issues closed on angular/angular are #100 'Router: infinite "
         "loop on guard redirect', #101 'Forms: reactive form not marking as dirty', "
         "and #102 'Compiler: template type checker crash on generic'."),
    25: (["/search?q=virtual+reality+updated%3A%3E2024-05-05+stars%3A%3E%3D200",
          "/vrlab/webvr-framework"],
         "vrlab/webvr-framework (JavaScript, 8.2k stars, updated 4 days ago) is a "
         "virtual reality framework for WebVR/WebXR applications; its main objective "
         "is enabling web developers to build immersive VR experiences in the "
         "browser."),
    26: (["/skills", "/skills/resolve-merge-conflicts"],
         "In the Resolve merge conflicts course, learners identify when and why "
         "merge conflicts happen, resolve simple merge conflicts with the GitHub "
         "web editor, edit files and commit changes to finish a pull request, and "
         "mark conflicts as resolved and complete a pull request merge."),
    27: (["/search?q=language%3Aruby+updated%3A%3E2024-05-12+stars%3A%3E%3D1000&sort=stars",
          "/ruby-core/fast-ruby"],
         "ruby-core/fast-ruby (4.2k stars, updated 1 day ago) is a community-driven "
         "collection of Ruby performance tips."),
    28: (["/search?q=language%3Ajavascript+created%3A%3E2023-12-29&sort=stars"],
         "The most starred JavaScript repositories created after 2023-12-29 are "
         "mar24-js/edge-runtime-js (7.2k stars), feb24-js/shadcn-fork-fresh (6.8k), "
         "and big-js-fresh/turbo-front (5.4k)."),
    29: (["/pricing"],
         "There is no difference in the maximum number of private repositories: "
         "both the Free and Pro plans include unlimited private repositories."),
    30: (["/search?q=blockchain+technology+updated%3A%3E2024-04-30",
          "/blockchain-lab/blockchain-technology/contributors"],
         "blockchain-lab/blockchain-technology (Go, 18.0k stars, updated 3 days ago) "
         "— the top five contributors are chain-dev-1, chain-dev-2, chain-dev-3, "
         "chain-dev-4, and chain-dev-5."),
    31: (["/tensorflow/tensorflow/commits", "/tensorflow/tensorflow/commit/ae4bfcf"],
         "The last commit ae4bfcf 'perf(xla): optimize matmul kernel for NVIDIA "
         "Hopper GPUs' changed 11 files — including matmul_utils.cc, matmul_test.cc, "
         "RELEASE.md, math_ops.py, optimizer.py — with +510 additions and −147 "
         "deletions in total."),
    32: (["/search?q=game+development+language%3Ac%23+stars%3A%3E%3D150&sort=created",
          "/godot-cs/godot-csharp-starter"],
         "godot-cs/godot-csharp-starter (C#, 1.2k stars) is the latest — most "
         "recently created — C# game development repository above 150 stars. Its "
         "main features: scene management, player controller, and networked "
         "multiplayer."),
    33: (["/customer-stories"],
         "The two stories on the Customer Stories page are Mercedes-Benz "
         "(accelerates software delivery with GitHub) and Shopify (scales "
         "developer productivity with GitHub Copilot)."),
    34: (["/search?q=protein+prediction&sort=forks", "/deepmind/alphafold"],
         "deepmind/alphafold has the highest number of forks among protein "
         "prediction projects: 2.2k forks (12.0k stars) — the open source "
         "implementation of the AlphaFold v2 inference pipeline."),
    35: (["/facebook/react/releases"],
         "React's latest release is v18.3.1, published on 2024-04-26."),
    36: (["/search?q=ai+agriculture+created%3A2022-01-01..2022-12-31",
          "/agritech/ai-agriculture-platform"],
         "agritech/ai-agriculture-platform — written in Python, an AI platform for "
         "precision agriculture with crop disease detection and yield prediction — "
         "was created in 2022."),
    37: (["/features/copilot"],
         "The three features on the Copilot product page are code completion, "
         "Copilot Chat, and pull request summaries."),
    38: (["/search?q=cybersecurity&sort=stars", "/secops/metasploit-framework-next"],
         "secops/metasploit-framework-next is the most popular cybersecurity "
         "repository by stars: 32.0k — the world's most used penetration testing "
         "framework."),
    39: (["/trending/developers?since=monthly"],
         "Ranked first among trending developers this month is Evan You "
         "(yyx990803), whose popular repository is vuejs/vue (208.0k stars)."),
    40: (["/register", "/signup/check?email=test123@gmail.com"],
         "test123@gmail.com does not already exist on GitHub — the email is "
         "available, so the address can be used to sign up."),
}

# A plausible-but-wrong answer for the wrong-answer adversarial (every task).
WRONG_ANSWER = ("The requested information is unavailable on GitHub; the search "
                "returned no matching results.")


def make_run(root: Path, task: int, paths, answer, *, task_id=None,
             drop_trajectory=False, break_screenshot=False):
    run = root / f"run_{task}"
    if run.exists():
        shutil.rmtree(run)
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    paths = list(paths)
    for i in range(max(2, len(paths))):
        (shots / f"step_{i:03d}.png").write_bytes(PNG)
    steps = []
    for i, p in enumerate(paths):
        url = p if p.startswith("http") else ORIGIN + p
        steps.append({
            "step": i, "url": url, "url_after": url,
            "action": "click", "action_result": {"success": True},
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i:03d}.png",
        })
    trajectory = {
        "task_id": task_id if task_id is not None else f"GitHub--{task}",
        "task": "fixture", "start_url": ORIGIN + "/",
        "steps": steps, "terminated": True, "termination_reason": "agent_done",
        "final_answer": answer,
        "final_url": steps[-1]["url"] if steps else ORIGIN + "/",
    }
    if not drop_trajectory:
        (run / "trajectory.json").write_text(json.dumps(trajectory),
                                             encoding="utf-8")
    if break_screenshot and steps:
        (shots / "step_000.png").unlink()
    return run


def run_verifier(task: int, run_dir: Path, initial_db: Path, after_db: Path):
    script = VERIFY_DIR / f"verify_{task}.py"
    r = subprocess.run(
        [sys.executable, str(script), "--run_dir", str(run_dir),
         "--initial_db", str(initial_db), "--after_db", str(after_db),
         "--container", "unused-container", "--no_llm", "True"],
        capture_output=True, text=True)
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[:300]}"}
    verdict["returncode"] = r.returncode
    return verdict


SEED_DB = None


def seed_db(tmp: Path) -> Path:
    global SEED_DB
    if SEED_DB is None:
        SEED_DB = verify_lib.fetch_db(
            __import__("os").environ.get("WH_CONTAINER", "wh-ver-github"),
            "instance_seed")
    db = tmp / "seed_copy.db"
    shutil.copy2(SEED_DB, db)
    return db


class VerifierTests(unittest.TestCase):
    def execute(self, task, *, answer=None, paths=None, task_id=None,
                drop_trajectory=False, break_screenshot=False, mutate=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            if mutate:
                with sqlite3.connect(after) as connection:
                    mutate(connection)
                    connection.commit()
            good_paths, good_answer = POSITIVE[task]
            run = make_run(root, task,
                           paths if paths is not None else good_paths,
                           answer if answer is not None else good_answer,
                           task_id=task_id, drop_trajectory=drop_trajectory,
                           break_screenshot=break_screenshot)
            return run_verifier(task, run, initial, after)

    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task)
                self.assertTrue(result["pass"], f"task {task}: {result}")

    def test_noop_run_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"], answer="")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)
                self.assertEqual(result.get("reason"), "final_answer_nonempty")

    def test_shortcut_correct_answer_without_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"])
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_wrong_answer_after_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, answer=WRONG_ANSWER)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertNotEqual(result.get("reason"), "final_answer_nonempty")
                self.assertNotEqual(result.get("reason"), "db_state")

    def test_foreign_task_replay_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, task_id="GitHub--999")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_missing_trajectory_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, drop_trajectory=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_missing_screenshot_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, break_screenshot=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_database_write_fails_read_only_check(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(
                    task,
                    mutate=lambda db: db.execute(
                        "UPDATE repository SET stars_count = stars_count + 1 "
                        "WHERE id = 1"))
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "db_state")


class TaskSpecificTests(unittest.TestCase):
    """Content adversarials for representative verifier groups."""

    def execute(self, task, *, answer=None, paths=None, mutate=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            if mutate:
                with sqlite3.connect(after) as connection:
                    mutate(connection)
                    connection.commit()
            good_paths, good_answer = POSITIVE[task]
            run = make_run(root, task,
                           paths if paths is not None else good_paths,
                           answer if answer is not None else good_answer)
            return run_verifier(task, run, initial, after)

    def test_task6_repo_page_contributor_path_passes(self):
        # real-run shape (amazon-acceptor D1 lesson): search -> repo page (whose
        # sidebar grid lists the contributors) -> done, without the /contributors
        # page; the correct top-three identities must carry the identification.
        result = self.execute(6, paths=[
            "/search?q=cryptocurrency+wallet+pushed%3A%3E2024-04-15",
            "/cryptolab/crypto-wallet"], answer=(
            "Project: cryptolab/crypto-wallet — an open-source multi-chain "
            "cryptocurrency wallet, updated 5 days ago (within the past 30 days). "
            "Top three contributors: satoshi-fan (420 commits), blockchain-dev "
            "(310 commits), wallet-maintainer (245 commits)."))
        self.assertTrue(result["pass"], result)

    def test_task6_repo_page_wrong_contributors_fails(self):
        result = self.execute(6, paths=[
            "/search?q=cryptocurrency+wallet+pushed%3A%3E2024-04-15",
            "/cryptolab/crypto-wallet"], answer=(
            "Project: cryptolab/crypto-wallet. Top three contributors: "
            "crypto-contributor, satoshi-fan and blockchain-dev."))
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_top3_contributors")

    def test_task30_repo_page_contributor_path_passes(self):
        result = self.execute(30, paths=[
            "/search?q=blockchain+technology+updated%3A%3E2024-04-30",
            "/blockchain-lab/blockchain-technology"], answer=(
            "blockchain-lab/blockchain-technology (Go, 18.0k stars, updated 3 days "
            "ago). Top five contributors: chain-dev-1, chain-dev-2, chain-dev-3, "
            "chain-dev-4, chain-dev-5."))
        self.assertTrue(result["pass"], result)

    def test_task7_repo_page_jump_passes(self):
        # real-run shape: repo page -> latest-commit detail (no commits list);
        # the detail page carries the changed files, the answer check pins them.
        result = self.execute(7, paths=[
            "/search?q=albert", "/google-research/albert",
            "/google-research/albert/commit/68a2c922e8861049c2f2d173d58012933cd3011e"],
            answer=("Most recent commit: 68a2c922e8861049c2f2d173d58012933cd3011 — "
                    "'fix: handle empty input sequence in tokenization' (May 11, "
                    "2024). Changed files (14; +737/−166 total): modeling.py, "
                    "run_classifier.py, tokenization.py, requirements.txt, "
                    "optimization.py."))
        self.assertTrue(result["pass"], result)

    def test_task31_repo_page_jump_passes(self):
        result = self.execute(31, paths=[
            "/tensorflow/tensorflow", "/tensorflow/tensorflow/commit/ae4bfcf"],
            answer=("The last commit ae4bfcf changed 11 files — matmul_utils.cc, "
                    "matmul_test.cc, RELEASE.md, math_ops.py — with +510 additions "
                    "and −147 deletions in total."))
        self.assertTrue(result["pass"], result)

    def test_task8_offsite_shortcut_fails_at_the_gate(self):
        # the real task-8 shortcut run shape: the agent navigated to the real
        # github.com; the run package gate must reject it structurally.
        result = self.execute(8, paths=["https://github.com/vuejs/vuex/releases/tag/v4.0.2"],
                              answer=("The latest stable release of Vuex is v4.0.2, "
                                      "published on June 17, 2021."))
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "run_package_valid")

    def test_task8_decoy_repo_release_fails(self):
        # the designed decoy: vuejs/vuex carries a fake higher version; a run
        # that stops there and reports the decoy release must FAIL
        result = self.execute(8, paths=["/vuejs/vuex/releases"],
                              answer=("The latest stable Vuex release is v4.9.21, "
                                      "published on February 23, 2024."))
        self.assertFalse(result["pass"], result)
        self.assertIn(result.get("reason"), ("nav_official_vuex", "answer_version"))

    def test_task8_repo_page_path_passes(self):
        # the real successful run shape: decoy releases -> repo page (note) ->
        # official repo page, whose sidebar shows the latest release
        result = self.execute(8, paths=[
            "/vuejs/vuex/releases/latest", "/vuejs/vuex", "/vuejs-vuex/vuex"],
            answer=("The latest stable Vuex release is v4.1.0, published on "
                    "June 23, 2022."))
        self.assertTrue(result["pass"], result)

    def test_task0_react_false_positive_rejected(self):
        # facebook/react tops the star-sorted search but is not about climate
        # change data visualization; the dashboard anchor must reject it.
        result = self.execute(0, answer=(
            "The project with the most stars in the search results is "
            "facebook/react with 228k stars."))
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_names_most_starred_climate_project")

    def test_task0_wrong_star_count_fails(self):
        result = self.execute(0, answer=(
            "climate-viz/climate-change-dashboard is the most starred project "
            "with 9.5k stars."))
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_cits_stars")

    def test_task8_vuex_wrong_version_fails(self):
        result = self.execute(8, answer="Vuex's latest stable release is v4.0.2, published 2021-06-30.")
        self.assertFalse(result["pass"], result)
        self.assertIn(result.get("reason"), ("answer_version", "answer_date"))

    def test_task12_electron_wrong_release_fails(self):
        result = self.execute(12, answer="electron's latest release is v29.1.3, released 2024-03-05.")
        self.assertFalse(result["pass"], result)

    def test_task24_open_issues_fails(self):
        # listing open issues instead of the last three closed must FAIL
        result = self.execute(24, answer=(
            "The last three issues are 'Performance: change detection slow on "
            "long ngFor with track-by', 'Build: ng build --watch leaks file "
            "handles on Linux', and 'Service Worker: precache fails for files "
            "> 50MB'."))
        self.assertFalse(result["pass"], result)

    def test_task30_wrong_contributor_set_fails(self):
        result = self.execute(30, answer=(
            "The top five contributors are satoshi-fan, blockchain-dev, "
            "wallet-maintainer, crypto-contributor and chain-dev-1."))
        self.assertFalse(result["pass"], result)

    def test_task31_wrong_totals_fails(self):
        result = self.execute(31, answer=(
            "The last commit changed 11 files including matmul_utils.cc and "
            "RELEASE.md, with +293 additions and −97 deletions."))
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_totals")

    def test_task34_second_most_forked_fails(self):
        result = self.execute(34, answer=(
            "openfold-team/openfold-pipeline has the highest number of forks "
            "with 720 forks."))
        self.assertFalse(result["pass"], result)

    def test_task38_second_most_starred_fails(self):
        result = self.execute(38, answer=(
            "secret-pals/cybersecurity-secret-scanner is the most popular "
            "cybersecurity repo with 19.0k stars."))
        self.assertFalse(result["pass"], result)

    def test_task40_existing_email_answer_fails(self):
        # claiming the address is already registered is the wrong way round
        result = self.execute(40, answer=(
            "test123@gmail.com is already registered — the email cannot be "
            "used to sign up."))
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_email_available")


class Task40DbTests(unittest.TestCase):
    """Task 40 (sign-up check): the only allowed DB delta is a new user row
    whose email is the queried one; every other write must FAIL."""

    def execute_with_mutation(self, task, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            with sqlite3.connect(after) as connection:
                mutate(connection)
                connection.commit()
            run = make_run(root, task, *POSITIVE[task])
            return run_verifier(task, run, initial, after)

    def test_task40_allows_user_row_for_queried_email(self):
        def add_user(db):
            db.execute(
                "INSERT INTO user (username, email, password_hash, name, plan, "
                "created_at) VALUES ('test123', 'test123@gmail.com', 'x', "
                "'Test User', 'free', '2024-05-15 12:00:00')")
        result = self.execute_with_mutation(40, add_user)
        self.assertTrue(result["pass"], result)

    def test_task40_rejects_user_row_for_other_email(self):
        def add_other(db):
            db.execute(
                "INSERT INTO user (username, email, password_hash, name, plan, "
                "created_at) VALUES ('someone', 'other@gmail.com', 'x', "
                "'Someone', 'free', '2024-05-15 12:00:00')")
        result = self.execute_with_mutation(40, add_other)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "db_state")

    def test_task40_rejects_star_write(self):
        def add_star(db):
            db.execute("INSERT INTO star (user_id, repo_id, created_at) "
                      "VALUES (1, 685, '2024-05-15 12:00:00')")
        result = self.execute_with_mutation(40, add_star)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "db_state")


class ContractTests(unittest.TestCase):
    def test_task_file_carries_verifier_and_rubric_for_every_task(self):
        rows = [json.loads(line) for line in
                (SITE_DIR / "tasks.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 41)
        self.assertEqual([row["id"] for row in rows],
                         [f"GitHub--{i}" for i in TASKS])
        for row in rows:
            self.assertEqual(
                sorted(row.keys()),
                sorted(["web_name", "id", "ques", "web", "upstream_url",
                        "verifier_path", "judge_rubric"]), row["id"])
            self.assertEqual(
                row["verifier_path"],
                f"sites/github/verify/verify_{row['id'].split('--')[1]}.py")
            self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."),
                            row["id"])
            self.assertNotIn("answer", row)
            repo_file = REPO_ROOT / row["verifier_path"]
            self.assertTrue(repo_file.is_file(), row["verifier_path"])

    def test_verifier_scripts_exist_and_are_deterministic(self):
        for task in TASKS:
            script = VERIFY_DIR / f"verify_{task}.py"
            self.assertTrue(script.is_file(), script)
            source = script.read_text()
            self.assertNotIn("urllib.request", source)   # no LLM/network calls
            self.assertNotIn("requests.post", source)
            self.assertIn(f"'GitHub--{task}'", source)

    def test_verify_lib_run_package_gate_rejects_broken_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            run = make_run(root, 0, *POSITIVE[0])
            verdict = run_verifier(0, run, initial, initial)
            self.assertTrue(verdict["pass"], verdict)
            (run / "trajectory.json").unlink()
            verdict = run_verifier(0, run, initial, initial)
            self.assertFalse(verdict["pass"], verdict)
            self.assertEqual(verdict.get("reason"), "run_package_valid")


if __name__ == "__main__":
    unittest.main()
