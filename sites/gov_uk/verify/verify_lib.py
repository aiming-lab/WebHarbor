#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for GOV.UK task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page. Many GOV.UK answers (Personal Allowance,
     VAT rate, State Pension) are real-world facts a frontier model already knows,
     so a correct answer with NO matching navigation is a memory-recall shortcut
     and FAILs — the navigation evidence is what makes these navigation tasks.
  2. Answer check: token / regex containment against frozen ground truth.
  3. LLM utility (text match) is used only as an anchored secondary check where
     free-form wording is brittle; it is given the ground truth and told never to
     use its own knowledge. Skipped entirely under --no_llm.

This site is read-only (no auth, no writes), so there is no DB after-state check.

Input signature (per task):
  --run_dir DIR   agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --no_llm        skip LLM-based checks (run deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import json, os, re, sys, urllib.request
from pathlib import Path
from dataclasses import dataclass

SITE = "gov_uk"

# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text())
    traj["_run_dir"] = d
    return traj

def step_urls(traj):
    return [s.get("url", "") for s in traj.get("steps", [])]

def navigated_to(traj, substr, times=1):
    """Deterministic: at least `times` trajectory steps have a URL containing substr."""
    return sum(1 for u in step_urls(traj) if substr in u) >= times

def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)

def final_answer(traj):
    return (traj.get("final_answer") or "").strip()

# ---------------------------------------------------------------- deterministic answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()

def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)

def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)

def _strip_thousands(text):
    """Collapse thousands separators between digits: '82,000' -> '82000'."""
    return re.sub(r"(?<=\d),(?=\d)", "", (text or ""))

def _num_present(text, num):
    """True if numeric string `num` appears as a STANDALONE number — not a fragment
    of a larger integer ('100' in '1000'), not a decimal fragment ('20' in '221.20'),
    and not extended by more decimals ('221' in '221.20'). Thousands separators are
    collapsed first so '82,000' matches '82000'."""
    t = _strip_thousands(text)
    return re.search(rf"(?<![\d.]){re.escape(num)}(?!\d)(?!\.\d)", t) is not None

def has_int(text, value):
    return _num_present(text, str(value))

def has_percent(text, value):
    """True if `value`% appears as a standalone rate (tolerating '20%', '20 %',
    '20 per cent', '20 percent'); rejects '120%' where the digits are only a substring."""
    t = norm(text)
    return bool(re.search(rf"(?<![\d.]){value}\s*(?:%|per ?cent)", t))

def has_money(text, amount):
    """True if the £ amount appears as a standalone number, tolerating a missing £,
    an inserted space, and thousands separators. Rejects substring matches such as
    '£100' in '£1000' or '£221.20' in '£1,221.20'."""
    bare = amount.lstrip("£").replace(",", "").strip()
    return _num_present(norm(text), bare)

def has_day_month(text, day, month):
    """True if a '<day> <month>' date appears in a common ordering/abbreviation:
    '31 January', '31st January', 'January 31', '31 Jan' all match (day=31, month='January')."""
    t = norm(text)
    mon = month.casefold()
    monpat = rf"(?:{mon}|{mon[:3]})"
    dd = rf"{day}(?:st|nd|rd|th)?"
    return bool(re.search(rf"\b{dd}\s+{monpat}\b", t) or re.search(rf"\b{monpat}\s+{dd}\b", t))

# ---------------------------------------------------------------- shared LLM utility (anchored)
# Unified LLM config, same env vars as agent.py / eval_judge.py:
#   OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL
import simpleArgParser as sap

# When --no_llm is set (via Judge), the llm_* helpers short-circuit so verifiers
# that call them directly still make ZERO LLM calls.
_NO_LLM = False


def _llm_config():
    return (os.environ.get("OPENAI_API_KEY", ""),
            os.environ.get("OPENAI_BASE_URL", ""),
            os.environ.get("JUDGE_MODEL", ""))


def _chat(messages, max_tokens=512):
    """One LLM call against the configured OpenAI-compatible endpoint. Returns text or None."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None  # no LLM configured -> callers treat as non-PASS
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None  # caller treats None as a non-PASS; never raises

def _verdict(out):
    if not out:
        return None, "[llm unavailable]"   # unconfigured / unreachable -> skip, don't fail-close
    s = out.strip()
    return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    """Anchored secondary check. Returns (verdict, text) where verdict is:
      True  -> LLM confirms the answer is consistent with the ground truth,
      False -> LLM actively contradicts it (a real reply starting FAIL),
      None  -> LLM unavailable/unconfigured -> caller SKIPS (deterministic layer decides).
    The model is anchored on the ground truth and told NOT to use its own knowledge,
    so it can only reject on a genuine contradiction, never fail-close on absence."""
    if _NO_LLM:
        return None, "[skipped: --no_llm]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)

# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)   # gate the llm_* helpers at the source
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        # LLM checks are secondary: skipped under --no_llm, and skipped when the
        # LLM was unavailable (cond is None) so a missing LLM never fails an
        # otherwise-correct answer. A real LLM reply (True/False) still gates.
        if llm and (self.no_llm or cond is None):
            self.evidence.append(f"[SKIP] {name}: {evidence or '(--no_llm or llm unavailable)'}")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name   # record the FIRST failing check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)

def parse_args():
    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)
