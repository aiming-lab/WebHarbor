#!/usr/bin/env python3
"""Site self-check for the cambridge_dictionary deterministic verifiers.

Builds synthetic run packages on disk (trajectory.json + screenshots/) and asserts
the grading contract of all 43 verifiers (merriam_webster/ikea exemplar style,
run with: uv run pytest sites/cambridge_dictionary/verify/test_verifiers.py):

  positive      — a well-formed package that satisfies the task contract must PASS
                  (deterministic checks only: --no_llm True)
  no_op         — homepage-only, empty answer, clean package must FAIL (exit 1)
  tamper_nav    — correct answer but a trajectory that never opened the required
                  page (shortcut / fabricated navigation) must FAIL (exit 1)
  wrong_answer  — navigation intact but a content-adversarial final answer must FAIL
  run_package   — a package missing trajectory.json or screenshots must FAIL closed

Notes:
  * LLM-anchored checks are skipped under --no_llm; the LLM-enabled adversarial
    matrix (fabricated quiz scores / fabricated German UI / wrong provider claims)
    is exercised live and recorded under the reviewer evidence directory.
  * The synthetic ground truth below mirrors the live-mirror audit (see
    audit/cambridge_audit.json); it is test data, not the grading key.
"""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
AGENT_DEMO = VERIFY_DIR.parents[2] / "agent_demo"
BASE = "http://localhost:41012"
# The verifiers import simpleArgParser, a dependency of the agent_demo project:
# always run them with the agent_demo venv interpreter (also correct when the
# suite itself is executed by `uv run pytest` from an ephemeral overlay env).
VENV_PY = AGENT_DEMO / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable


# --------------------------------------------------------------------------- helpers

def tiny_png(path):
    """Write a valid 1x1 PNG (the screenshot content is irrelevant to the
    deterministic checks; the package gate only requires step_*.png files)."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"\x00\xff\x00\x00")
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def load_module(n):
    spec = importlib.util.spec_from_file_location(
        f"verify_{n}", VERIFY_DIR / f"verify_{n}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_package(root, task_id, steps, final_answer, screenshots=2,
                  with_trajectory=True, with_screenshots=True):
    run_dir = Path(root) / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    if with_trajectory:
        traj = {
            "task": f"task {task_id}",
            "task_id": task_id,
            "start_url": BASE + "/",
            "model": "test",
            "max_steps": 15,
            "steps": steps,
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": final_answer,
            "success_self_report": True,
            "judge_rubric": "",
            "verifier_path": f"sites/cambridge_dictionary/verify/verify_{task_id.split('--')[1]}.py",
        }
        (run_dir / "trajectory.json").write_text(
            json.dumps(traj, ensure_ascii=False), encoding="utf-8")
    if with_screenshots:
        shots = run_dir / "screenshots"
        shots.mkdir(exist_ok=True)
        for i in range(screenshots):
            tiny_png(shots / f"step_{i:03d}.png")
    return run_dir


def run_verifier(n, run_dir, no_llm=True):
    cmd = [PY, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir)]
    if no_llm:
        cmd += ["--no_llm", "True"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(AGENT_DEMO))
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[-300:]}"}
    return r.returncode, verdict


def step(url, url_after=None, action="click", params=None, dom=""):
    return {"step": 0, "url": url, "url_after": url_after or url,
            "title": "title", "thought": "", "action": action,
            "params": params or {}, "observed_text": dom,
            "observed_text_before": dom, "observed_text_after": dom,
            "screenshot_before": "step_000.png", "screenshot_after": "step_001.png"}


# ------------------------------------------------------------------ per-task packages

def word_dom(mod):
    uk = getattr(mod, "IPA_UK", "")
    us = getattr(mod, "IPA_US", "")
    defs = getattr(mod, "DEF_ANY", ["The quality of being able to continue over a period of time."])
    exs = getattr(mod, "EX_ANY", ["The long-term sustainability of the project is in doubt."])
    headword = getattr(mod, "HEADWORD", "") or getattr(mod, "WORD", "")
    dom = (f"Meaning of\n{headword}\nin English\n"
           f"{headword}\nnoun\nuk\n{uk}\nus\n{us}\n"
           + "\n".join(defs) + "\n" + "\n".join(exs))
    return dom


def positive_package(n, mod):
    """(steps, final_answer) for a well-formed PASS package of task n."""
    # thesaurus article/entry tasks
    if hasattr(mod, "SYNONYMS"):
        nav_path = ("to-behave-well" if "behave" in mod.SYNONYMS[0]
                    else "feel-giddy")
        url = f"{BASE}/thesaurus/articles/{nav_path}"
        dom = ("Thesaurus\n" + nav_path.replace("-", " ")
               + "\nSynonyms and related words\n" + "\n".join(mod.SYNONYMS))
        return [step(BASE + "/", url, "click", dom=dom)], ", ".join(mod.SYNONYMS)
    # translate-provider task
    if hasattr(mod, "PROVIDER_LINE"):
        url = f"{BASE}/translate?src=english&q=sustainability&dst=chinese-simplified"
        dom = ("Translate\nTranslate words and phrases into many languages. "
               + mod.PROVIDER_LINE + "\ntrans result 可持续性")
        return ([step(BASE + "/", url, "click", dom=dom),
                 step(url, url, "input", {"text": "sustainability"}, dom=dom)],
                "The translation was provided by Microsoft.")
    # quiz tasks
    if hasattr(mod, "QUIZ_NAVS"):
        url = BASE + mod.QUIZ_NAVS[0]
        dom = ("Plus\nQuiz\n5 questions\nQuiz Complete!\nYour score:\n/ 5\n"
               "Excellent! Great vocabulary knowledge.")
        return [step(BASE + "/plus", url, "click", dom=dom)], "Final score: 5/5."
    # word scramble task
    if hasattr(mod, "TARGET"):
        url = BASE + "/plus/word-scramble"
        dom = ("Word Scramble\nUnscramble the letters to find the correct word. "
               f"Clue:\nThe subject matter of a conversation or discussion.\n"
               f"{mod.SCRAMBLED}\nCorrect! Well done!")
        return ([step(BASE + "/plus", url, "click", dom=dom),
                 step(url, url, "input", {"text": mod.TARGET}, dom=dom)],
                f"Unscrambled {mod.SCRAMBLED} as '{mod.TARGET}'.")
    # shop task
    if hasattr(mod, "ITEMS"):
        url = BASE + "/shop"
        names = ["Cambridge Advanced Learner's Dictionary (4th Edition)",
                 "Cambridge Learner's Dictionary (4th Edition)",
                 "Cambridge Thesaurus"]
        dom = "Cambridge Dictionary Shop\n" + "\n".join(names) + "\nGBP 35.00"
        return [step(BASE + "/", url, "click", dom=dom)], "; ".join(names)
    # language-switch task
    if hasattr(mod, "TARGET_LANG"):
        dom = ("Cambridge\nWörterbuch\nFinden Sie das perfekte Wort\n"
               "Im Cambridge Wörterbuch suchen\nWort des Tages")
        return ([step(BASE + "/", BASE + "/", "select_dropdown",
                      {"text": "Deutsch"}, dom=dom)],
                "Homepage converted to Deutsch: Cambridge Wörterbuch.")
    # grammar tasks
    if hasattr(mod, "DOM_PROBE"):
        url = BASE + mod.NAV
        dom = f"Grammar\n{mod.TITLE}\n{mod.DOM_PROBE}\nExample sentences shown on the page."
        return [step(BASE + "/", url, "click", dom=dom)], mod.GT
    # word-family tasks (entry lookups incl. translations/multi-sense/count)
    nav = getattr(mod, "NAV", None) or getattr(mod, "ENTRY_NAV")
    url = BASE + nav
    dom = word_dom(mod)
    if hasattr(mod, "RELATED"):          # euphoria word/phrase/idiom
        dom += "\nSMART Vocabulary: related words and phrases\n" + \
               "\n".join(mod.RELATED)
        answer = ("Related word: euphoric; related phrase: sense of euphoria; "
                  "idiom: on cloud nine.")
        return [step(BASE + "/", url, "click", dom=dom)], answer
    if hasattr(mod, "DEF_TEXT"):        # unblemished count
        dom += "\n" + mod.DEF_TEXT
        return [step(BASE + "/", url, "click", dom=dom)], \
            "The dictionary gives 1 meaning for unblemished: " + mod.DEF_TEXT
    if hasattr(mod, "SPANISH"):
        return [step(BASE + "/", url, "click", dom=dom)], \
            "The Spanish translation of ephemeral is efímero."
    if hasattr(mod, "CHINESE"):
        return [step(BASE + "/", url, "click", dom=dom)], \
            "The Chinese translation of nostalgia is 怀旧."
    if hasattr(mod, "SENSE1_ANY"):      # harmony two senses
        return [step(BASE + "/", url, "click", dom=dom)], \
            ("Two meanings: 1) A situation in which people are peaceful and agree "
             "with each other, or when things seem right or suitable together. "
             "2) The combination of musical notes played or sung at the same time "
             "to give a pleasing effect.")
    return [step(BASE + "/", url, "click", dom=dom)], mod.GT


def wrong_answer(n, mod):
    """Content-adversarial final answers: plausible prose, wrong facts, and
    (for every family) missing the required content fragments."""
    if hasattr(mod, "SYNONYMS"):
        return ("The thesaurus suggests: run fast, jump high, sit down, "
                "walk slowly, stand up, talk quietly.")
    if hasattr(mod, "PROVIDER_LINE"):
        return "The translation was provided by Google Translate."
    if hasattr(mod, "QUIZ_NAVS"):
        # NOTE: under --no_llm the fabricated-score variant is not deterministic
        # (the score digit is not in the DOM repr); the nav-tamper variant below
        # is this family's deterministic content adversarial in this suite, and
        # the fabricated-score case is run LLM-enabled in the live matrix.
        return "Final score: 3/5."
    if hasattr(mod, "TARGET"):
        return "The scrambled letters spell the word 'master'."
    if hasattr(mod, "ITEMS"):
        return ("The shop sells: Oxford English Dictionary, Longman Dictionary, "
                "Collins Cobuild Dictionary.")
    if hasattr(mod, "TARGET_LANG"):
        return "Done."   # no German/Deutsch confirmation at all
    if hasattr(mod, "DOM_PROBE"):
        return ("The page explains that the past continuous is formed with was/"
                "were + the base verb, e.g. 'She was go home yesterday'.")
    if hasattr(mod, "RELATED"):
        return "Related word: sad; related phrase: feeling down; idiom: under the weather."
    if hasattr(mod, "DEF_TEXT"):
        return "The dictionary gives 4 meanings for this word, all technical."
    if hasattr(mod, "SPANISH"):
        return "The Spanish translation of ephemeral is eterno."
    if hasattr(mod, "CHINESE"):
        return "The Chinese translation of nostalgia is 怀旧之情满满."  # wrong token
    if hasattr(mod, "SENSE1_ANY"):
        return ("Meaning 1: a type of garden flower. Meaning 2: a kind of "
                "musical instrument.")
    if n == 13:
        return "word: happy; phrase: very happy; idiom: over the moon."
    if n == 8:
        return ("Meaning 1: a type of fish. Meaning 2: a kitchen tool. "
                "Meaning 3: a unit of weight.")
    if n == 17:
        return "There are twelve meanings listed on the page."
    if n == 6:
        return "Chinese: 环保, French: écologie."
    if n == 16:
        return ("Cryptocurrency means a paper contract, pronounced /ˈpeɪpə/, "
                "e.g. 'The paper was signed.'")
    return ("The word means something entirely different: a kind of tropical "
            "fruit, pronounced /ˈfruːt/, example: 'Lorem ipsum dolor sit amet.'")


def tampered_steps(n, mod, steps):
    """Rewrite every recorded URL to the homepage — right answer, wrong pages."""
    home = BASE + "/"
    out = []
    for s in steps:
        s2 = dict(s)
        s2["url"] = home
        s2["url_after"] = home
        s2["observed_text"] = "Cambridge Dictionary homepage"
        s2["observed_text_before"] = "Cambridge Dictionary homepage"
        s2["observed_text_after"] = "Cambridge Dictionary homepage"
        out.append(s2)
    return out


class VerifierContractTests(unittest.TestCase):
    TASK_IDS = [f"Cambridge Dictionary--{n}" for n in range(43)]

    def run_case(self, n, steps, answer, **kw):
        with tempfile.TemporaryDirectory() as root:
            run_dir = write_package(root, f"Cambridge Dictionary--{n}",
                                     steps, answer, **kw)
            return run_verifier(n, run_dir)

    def assert_pass(self, n, code, verdict, label):
        self.assertEqual(code, 0,
            f"task {n} {label}: expected PASS exit 0, got {code}: {verdict}")
        self.assertTrue(verdict.get("pass"),
            f"task {n} {label}: expected pass=true: {verdict}")

    def assert_fail(self, n, code, verdict, label, expect_reason=None):
        self.assertNotEqual(code, 0,
            f"task {n} {label}: expected FAIL exit 1, got 0: {verdict}")
        self.assertFalse(verdict.get("pass"),
            f"task {n} {label}: expected pass=false: {verdict}")
        if expect_reason:
            self.assertEqual(verdict.get("reason"), expect_reason)

    # ------------------------------------------------------------- the matrix

    def test_01_positive_packages_pass(self):
        for n in range(43):
            mod = load_module(n)
            steps, answer = positive_package(n, mod)
            with self.subTest(task=n):
                code, verdict = self.run_case(n, steps, answer)
                self.assert_pass(n, code, verdict, "positive")

    def test_02_noop_packages_fail(self):
        noop_dom = ("Cambridge Dictionary\nFind the perfect word\n"
                    "The Cambridge Dictionary. Trusted by learners around the world.")
        for n in range(43):
            with self.subTest(task=n):
                steps = [step(BASE + "/", BASE + "/", "navigate", {}, dom=noop_dom)]
                code, verdict = self.run_case(n, steps, "")
                self.assert_fail(n, code, verdict, "no-op")

    def test_03_shortcut_nav_tamper_fails(self):
        for n in range(43):
            mod = load_module(n)
            steps, answer = positive_package(n, mod)
            with self.subTest(task=n):
                code, verdict = self.run_case(n, tampered_steps(n, mod, steps), answer)
                self.assert_fail(n, code, verdict, "nav-tamper")

    def test_04_wrong_answer_fails(self):
        for n in range(43):
            mod = load_module(n)
            if hasattr(mod, "QUIZ_NAVS"):
                # the fabricated quiz score is not deterministically decidable
                # (the digit is not in the DOM); use the nav-tamper adversarial
                # here and the LLM-enabled fabricated-score case in the live matrix
                steps, answer = positive_package(n, mod)
                code, verdict = self.run_case(n, tampered_steps(n, mod, steps), answer)
                self.assert_fail(n, code, verdict, "quiz-adversarial")
                continue
            steps, _ = positive_package(n, mod)
            with self.subTest(task=n):
                code, verdict = self.run_case(n, steps, wrong_answer(n, mod))
                self.assert_fail(n, code, verdict, "wrong-answer")

    def test_05_run_package_gate_fails_closed(self):
        n, mod = 0, load_module(0)
        steps, answer = positive_package(0, mod)
        # missing trajectory.json
        with tempfile.TemporaryDirectory() as root:
            run_dir = write_package(root, "Cambridge Dictionary--0",
                                    steps, answer, with_trajectory=False)
            code, verdict = run_verifier(0, run_dir)
            self.assert_fail(0, code, verdict, "missing-trajectory",
                             expect_reason="run_package_invalid")
        # missing screenshots
        with tempfile.TemporaryDirectory() as root:
            run_dir = write_package(root, "Cambridge Dictionary--0",
                                    steps, answer, with_screenshots=False)
            code, verdict = run_verifier(0, run_dir)
            self.assert_fail(0, code, verdict, "missing-screenshots",
                             expect_reason="run_package_invalid")
        # empty steps list
        with tempfile.TemporaryDirectory() as root:
            run_dir = write_package(root, "Cambridge Dictionary--0", [], answer)
            code, verdict = run_verifier(0, run_dir)
            self.assert_fail(0, code, verdict, "empty-steps",
                             expect_reason="run_package_invalid")
        # wrong task id graded by this verifier
        with tempfile.TemporaryDirectory() as root:
            run_dir = write_package(root, "Cambridge Dictionary--7", steps, answer)
            code, verdict = run_verifier(0, run_dir)
            self.assert_fail(0, code, verdict, "wrong-task-id",
                             expect_reason="task_id_matches")

    def test_06_non_mirror_upstream_navigation_does_not_count(self):
        """Navigating to the real upstream site must NOT satisfy the nav check."""
        n, mod = 0, load_module(0)
        upstream = "https://dictionary.cambridge.org/dictionary/english/sustainability"
        dom = word_dom(mod)
        steps = [step(BASE + "/", upstream, "navigate", {}, dom=dom)]
        code, verdict = self.run_case(n, steps, mod.GT)
        self.assert_fail(n, code, verdict, "upstream-nav")


if __name__ == "__main__":
    unittest.main(verbosity=2)
