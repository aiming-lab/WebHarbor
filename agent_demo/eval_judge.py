import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
import simpleArgParser as sap


@dataclass
class JudgeArgs:
    run_dir: str = ""
    out: str = ""
    last_k_screenshots: int = 4
    model: str = ""
    api_key: str = ""
    api_base: str = ""
    # Grading mode (simpleargparser bool -> value flag: --verifier True).
    # False (default): run the LLM-as-judge over the trajectory + last-K screenshots.
    # True: run the task's deterministic verifier (the script at trajectory.verifier_path)
    #       if present; otherwise fall back to the LLM judge with a note.
    verifier: bool = False


# ---------------------------------------------------------------------------
# LLM config — unified env vars (also used by the per-task verifiers):
#   OPENAI_API_KEY  : bearer token for the OpenAI-compatible judge endpoint
#   OPENAI_BASE_URL : base URL of that endpoint
#   JUDGE_MODEL     : model id to use as the LLM judge
# CLI flags override env (simpleargparser precedence: cmd > code > default).
JUDGE_SYSTEM_BASE = """You are a strict grader of web-agent task completion.

You receive:
  - the ORIGINAL TASK (natural language),
  - the agent's full TRAJECTORY (per step: thought + action + params + URL + any
    extracted_content), reproduced in full — do not assume anything is omitted,
  - the agent's final self-reported answer (if any),
  - the LAST K screenshots of the browser, in order. The last image is the
    final state the user would see.

Your job is to decide whether the task was actually completed. Be skeptical.
Common failure modes you must catch:
  - The agent claimed success but the final page does not show the right content.
  - The agent answered with plausible-sounding but wrong information.
  - The agent stopped early (max_steps) without finishing.
  - The agent navigated somewhere unrelated.
  - EMPTY / NO ANSWER: if the task asks for a fact and the agent's final
    self-reported answer is EMPTY (or clearly absent), mark success=false. The
    task is to PRODUCE an answer; navigating to the right page without
    reporting the answer is NOT a completion. (You may still extract the
    visible page content into answer_extracted for diagnostics, but it does not
    rescue an empty self-report.)
  - PRIOR-KNOWLEDGE SHORTCUT: if the agent's answer is correct but the
    trajectory shows NO navigation to the site's relevant page (no step URL
    reaching the mirror for that content), mark success=false. The task is to
    NAVIGATE the site and read the answer off the page, not recall it.
  - For QUIZ tasks success requires the agent navigated to the quiz, answered
    every question, submitted, and reported the score shown on the result page.

Tie-break rules:
  - If the task asks for a fact and done.text contains a value, cross-check it
    against the final screenshot / extracted_content.
  - If the task is navigational ("find the page that ..."), the final screenshot
    must show that page.
  - If the agent performed irreversible actions the task did not ask for,
    mark success=false and explain.

Respond with ONLY this JSON object (no code fence, no prose):

  {
    "success": <true|false>,
    "confidence": <0.0-1.0>,
    "rationale": "<full one-paragraph reasoning citing specific steps/screenshots>",
    "evidence": ["<quote or short paraphrase of supporting signal 1>", "..."],
    "answer_extracted": "<the answer the agent ended up giving, or empty>"
  }
"""

# Appended to JUDGE_SYSTEM_BASE ONLY when the task carries a judge_rubric.
# This block makes the rubric binding: every MUST checkpoint must hold.
JUDGE_SYSTEM_RUBRIC = """
---
ADDITIONAL INSTRUCTIONS — THIS TASK HAS A JUDGE RUBRIC.
A JUDGE RUBRIC listing concrete FACT CHECKPOINTS is included in the evidence
below. You MUST grade against it: verify EVERY checkpoint and treat each MUST
as a hard requirement for success — if any MUST checkpoint is unmet, mark
success=false. In your rationale, explicitly check each rubric checkpoint.

Include an extra field in your JSON response:
  "rubric_checkpoints": {"<checkpoint text 1>": true/false, "...": "..."}
mapping each rubric checkpoint to whether it was satisfied.
"""



def img_payload(path):
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}}


def trajectory_text(traj):
    """Full, untruncated textual rendering of the trajectory.

    NOTHING is truncated here — truncating thoughts / extracted_content / answers
    withers the judge's context and yields inaccurate verdicts. The model gets
    the complete evidence so it can grade accurately.
    """
    lines = []
    lines.append(f"TASK: {traj.get('task', '')}")
    lines.append(f"TASK ID: {traj.get('task_id', '')}")
    lines.append(f"START URL: {traj.get('start_url', '')}")
    rubric = traj.get('judge_rubric', '')
    if rubric:
        lines.append("")
        lines.append("JUDGE RUBRIC — verify EVERY fact checkpoint below:")
        lines.append(rubric)
    lines.append("")
    lines.append(f"TERMINATED: {traj.get('terminated')} ({traj.get('termination_reason')})")
    lines.append(f"AGENT'S FINAL ANSWER (self-report): {traj.get('final_answer', '')!r}")
    lines.append(f"AGENT'S SELF-REPORTED SUCCESS: {traj.get('success_self_report', '<none>')}")
    lines.append("")
    lines.append("STEPS (full, oldest → newest):")
    for s in traj.get("steps", []):
        ar = s.get("action_result") or {}
        line = (
            f"  [step {s['step']}] action={s['action']} params={s.get('params', {})} "
            f"url={s.get('url', '')}\n"
            f"        thought: {s.get('thought', '')}"
        )
        ec = ar.get("extracted_content") or ""
        if ec:
            line += f"\n        extracted_content: {ec}"
        if ar.get("error"):
            line += f"\n        error: {ar['error']}"
        lines.append(line)
    return "\n".join(lines)


def build_messages(traj, screenshot_paths):
    text = trajectory_text(traj)
    user_content = [{"type": "text", "text": text + "\n\nLAST SCREENSHOTS (oldest → newest):"}]
    for p in screenshot_paths:
        user_content.append({"type": "text", "text": f"({p.name})"})
        user_content.append(img_payload(p))
    user_content.append({"type": "text", "text": "Now grade. Respond with the JSON object only."})
    # If/else: the rubric-specific system-prompt block is appended ONLY when this
    # task carries a judge_rubric. Tasks without one (the other 16 sites) get the
    # plain base prompt — no rubric mention, no rubric_checkpoints field.
    system = JUDGE_SYSTEM_BASE
    if traj.get('judge_rubric'):
        system = JUDGE_SYSTEM_BASE + JUDGE_SYSTEM_RUBRIC
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def parse_judge_json(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    start = s.find("{")
    if start < 0:
        raise ValueError(f"no JSON in judge reply: {raw[:200]!r}")
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start : i + 1])
    raise ValueError(f"unterminated JSON in judge reply: {raw[:200]!r}")


def run_verifier(run_dir: Path, traj: dict) -> dict:
    """Run the task's deterministic verifier (mode --verifier True).

    Looks up verifier_path from the trajectory (written by agent.py). Runs the
    verifier under agent_demo's uv project so its simpleArgParser dependency is
    available; forwards all env vars (incl. OPENAI_API_KEY/OPENAI_BASE_URL/
    JUDGE_MODEL for the verifier's LLM utilities). Returns a verdict dict shaped
    like eval.json (the verifier's {task_id,pass,reason,evidence} + meta).
    """
    verifier_path = traj.get("verifier_path", "")
    if not verifier_path:
        return {
            "success": False,
            "confidence": 1.0,
            "rationale": "verifier mode requested but the trajectory has no verifier_path "
                          "(this task/site has no deterministic verifier); falling back is not possible.",
            "evidence": [],
            "answer_extracted": traj.get("final_answer", "") or "",
            "meta": {"mode": "verifier", "verifier_path": None, "run_dir": str(run_dir)},
        }
    vp = Path(verifier_path)
    if not vp.is_absolute():
        # verifier_path is relative to the repo root; resolve from there.
        repo_root = Path(__file__).resolve().parents[1]
        vp = repo_root / vp
    if not vp.exists():
        return {
            "success": False,
            "confidence": 1.0,
            "rationale": f"verifier_path not found: {vp}",
            "evidence": [],
            "answer_extracted": traj.get("final_answer", "") or "",
            "meta": {"mode": "verifier", "verifier_path": str(vp), "run_dir": str(run_dir)},
        }
    # Run under agent_demo/ so `uv` finds the pyproject + simpleArgParser dep.
    agent_demo_dir = Path(__file__).resolve().parent
    cmd = ["uv", "run", "python", str(vp), "--run_dir", str(run_dir)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(agent_demo_dir),
                       env=os.environ.copy())
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {
            "success": False,
            "confidence": 1.0,
            "rationale": f"verifier crashed: {r.stderr[:500] or r.stdout[:500]}",
            "evidence": [],
            "answer_extracted": "",
            "meta": {"mode": "verifier", "verifier_path": str(vp),
                     "run_dir": str(run_dir), "returncode": r.returncode},
        }
    else:
        verdict.setdefault("meta", {})
        verdict["meta"].update({"mode": "verifier", "verifier_path": str(vp),
                                "run_dir": str(run_dir), "returncode": r.returncode})
        # normalize: verifier emits {pass: bool} -> also expose {success: bool}
        if "success" not in verdict and "pass" in verdict:
            verdict["success"] = bool(verdict["pass"])
    return verdict


def main():
    args = sap.parse_args(JudgeArgs)
    if not args.run_dir:
        raise SystemExit("--run_dir is required")

    run_dir = Path(args.run_dir)
    traj = json.loads((run_dir / "trajectory.json").read_text())

    if args.verifier:
        print(f"[verifier mode] task_id={traj.get('task_id','?')} verifier={traj.get('verifier_path','<none>')}")
        verdict = run_verifier(run_dir, traj)
        out_path = Path(args.out) if args.out else run_dir / "eval.json"
        out_path.write_text(json.dumps(verdict, indent=2))
        print(f"wrote {out_path}")
        print(f"  pass: {verdict.get('pass')}  success: {verdict.get('success')}  reason: {verdict.get('reason','')}")
        sys.exit(0 if verdict.get("success") else 1)

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    api_base = args.api_base or os.environ.get("OPENAI_BASE_URL", "")
    model = args.model or os.environ.get("JUDGE_MODEL", "")
    if not api_key:
        raise SystemExit("API key missing: set --api_key or OPENAI_API_KEY")
    if not api_base:
        raise SystemExit("API base missing: set --api_base or OPENAI_BASE_URL")
    if not model:
        raise SystemExit("model missing: set --model or JUDGE_MODEL")

    shots_dir = run_dir / "screenshots"
    all_shots = sorted(shots_dir.glob("step_*.png"))
    if not all_shots:
        raise SystemExit(f"no screenshots in {shots_dir}")
    last_k = all_shots[-args.last_k_screenshots :]
    print(f"judging {len(traj.get('steps', []))} steps with last {len(last_k)} screenshots: "
          f"{[p.name for p in last_k]}")

    client = OpenAI(base_url=api_base, api_key=api_key)
    messages = build_messages(traj, last_k)

    resp = client.chat.completions.create(model=model, messages=messages)
    raw = resp.choices[0].message.content or ""
    try:
        verdict = parse_judge_json(raw)
    except Exception as e:
        verdict = {
            "success": False,
            "confidence": 0.0,
            "rationale": f"judge parse error: {e}",
            "evidence": [],
            "answer_extracted": "",
            "raw_reply": raw,
        }

    verdict["meta"] = {
        "run_dir": str(run_dir),
        "task": traj.get("task", ""),
        "model": model,
        "screenshots_used": [p.name for p in last_k],
        "trajectory_steps": len(traj.get("steps", [])),
    }

    out_path = Path(args.out) if args.out else run_dir / "eval.json"
    out_path.write_text(json.dumps(verdict, indent=2))
    print(f"wrote {out_path}")
    print(f"  success: {verdict.get('success')}  confidence: {verdict.get('confidence')}")
    print(f"  rationale: {verdict.get('rationale', '')}")


if __name__ == "__main__":
    main()
