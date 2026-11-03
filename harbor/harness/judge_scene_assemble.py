#!/usr/bin/env python3
"""Assemble the Agent Judge scene inside a live trial sandbox.

Runs in-sandbox (stdlib only) right after the official site verification.
Reads the trial's live artifacts and writes the judge workspace layout that
JUDGE_INSTRUCTION expects:

  /workspace/judge/
    organized_trajectory.jsonl   unified steps (harness-agnostic)
    final_answer.txt
    images/                       copies of /logs/agent/screenshots/*.png
    prompts/                     task.md + rubric.md (uploaded by the host)
    verifier/                    the verifier scripts (/tests) + verdict outputs
    verifier_verdict.json        the recorded layer-1 verdict
    after_state_marker           AVAILABLE: live after-DB + pristine seed in place
    output/                      judge writes verdict.json here

Sources (all inside the same sandbox):
  /logs/agent/                   trajectory.json (OpenCode), openwebrl_history.json
                                 (OpenWebRL), or browseruse_history.json (browser-use),
                                 plus final_answer.txt and screenshots/
  /logs/verifier/                reward.json, verifier_verdict.json, after.db, ...
  /tests/                        the site verifier scripts (uploaded by harbor)
  /opt/WebSyn/<site>/            site code, instance (live after-state DB),
                                 instance_seed (pristine seed DB)

Usage (in-sandbox): python3 judge_scene_assemble.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

LOGS = Path("/logs")
JUDGE = Path("/workspace/judge")


def build_oc_steps(traj_path: Path) -> list[dict]:
    t = json.loads(traj_path.read_text())
    steps = []
    for s in t.get("steps", []):
        calls = s.get("tool_calls") or []
        action = None
        params: dict = {}
        for c in calls:
            fname = str(c.get("function_name", ""))
            if fname.startswith("browser_"):
                action = fname.replace("browser_browser_", "")
                a = c.get("arguments")
                if isinstance(a, str):
                    try:
                        a = json.loads(a)
                    except Exception:
                        a = {}
                params = a if isinstance(a, dict) else {}
                break
        observed_url, observed_head = "", ""
        obs = s.get("observation") or {}
        results = obs.get("results") if isinstance(obs, dict) else None
        if isinstance(results, list):
            for r in results:
                c = str((r or {}).get("content", "") if isinstance(r, dict) else "")
                if c.startswith("### Page"):
                    m = re.search(r"Page URL:\s*(\S+)", c)
                    observed_url = m.group(1) if m else ""
                    observed_head = c[:700]
                    break
        steps.append({
            "step": len(steps) + 1,
            "action": action or "think",
            "url": observed_url or (str(params.get("url") or "") if action == "navigate" else ""),
            "thought_or_summary": str(s.get("message", ""))[:400],
            "observed_head": observed_head,
            "screenshot": None,
        })
    return steps


def build_openwebrl_steps(hist_path: Path) -> list[dict]:
    history = json.loads(hist_path.read_text())
    steps = []
    for turn in history.get("turns", []):
        calls = turn.get("tool_calls") or []
        names = [str(call.get("name") or "") for call in calls if isinstance(call, dict)]
        response = str(turn.get("response") or "")
        think = re.search(r"<think>\s*(.*?)\s*</think>", response, re.DOTALL)
        summary = " ".join((think.group(1) if think else response).split())[:1000]
        tool_responses = [str(value) for value in (turn.get("tool_responses") or [])]
        steps.append({
            "step": int(turn.get("turn_index", len(steps))) + 1,
            "harness": "openwebrl",
            "action": "+".join(name for name in names if name) or "think",
            "tool_calls": calls,
            "tool_responses": tool_responses,
            "url": str(turn.get("url_before") or turn.get("url_after") or ""),
            "url_after": str(turn.get("url_after") or ""),
            "thought_or_summary": summary,
            "observed_head": "\n".join(tool_responses)[:1200],
            "screenshot": turn.get("screenshot_before"),
            "screenshot_after": turn.get("screenshot_after"),
            "usage": turn.get("usage") or {},
            "error": turn.get("error") or turn.get("parse_error"),
        })
    return steps


def build_gui_steps(hist_path: Path) -> list[dict]:
    h = json.loads(hist_path.read_text())
    urls = [s.get("url", "") for s in h.get("step_urls", [])]
    ecs = [str(e) for e in (h.get("extracted_content") or [])]
    n = max(len(urls), len(ecs))
    steps = []
    last_url = ""
    for i in range(n):
        u = urls[i] if i < len(urls) else last_url
        if u:
            last_url = u
        steps.append({
            "step": i + 1,
            "action": "gui_step",
            "url": u,
            "thought_or_summary": (ecs[i][:400] if i < len(ecs) else ""),
            "observed_head": "",
            "screenshot": None,
        })
    return steps


def main() -> int:
    agent = LOGS / "agent"
    (JUDGE / "prompts").mkdir(parents=True, exist_ok=True)
    (JUDGE / "output").mkdir(parents=True, exist_ok=True)

    traj_oc = agent / "trajectory.json"
    traj_openwebrl = agent / "openwebrl_history.json"
    traj_gui = agent / "browseruse_history.json"
    if traj_oc.is_file():
        steps = build_oc_steps(traj_oc)
        harness = "opencode"
    elif traj_openwebrl.is_file():
        steps = build_openwebrl_steps(traj_openwebrl)
        harness = "openwebrl"
    elif traj_gui.is_file():
        steps = build_gui_steps(traj_gui)
        history = json.loads(traj_gui.read_text())
        harness = str(history.get("harness") or "browseruse")
    else:
        print("SCENE_ERROR: no trajectory.json, openwebrl_history.json, or browseruse_history.json under /logs/agent", flush=True)
        return 1

    shots_dir = agent / "screenshots"
    shots = sorted(shots_dir.glob("step_*.png")) if shots_dir.is_dir() else []
    if not shots and shots_dir.is_dir():
        shots = sorted(shots_dir.glob("*.png"))
    img_dir = JUDGE / "images"
    img_dir.mkdir(exist_ok=True)
    for i, st in enumerate(steps):
        preferred = st.get("screenshot")
        source = shots_dir / Path(str(preferred)).name if preferred else None
        if source is None or not source.is_file():
            source = shots[i] if i < len(shots) else None
        if source is not None:
            dst = img_dir / source.name
            if not dst.is_file():
                try:
                    shutil.copy2(source, dst)
                except Exception:
                    pass
            st["screenshot"] = str(dst)
        after = st.get("screenshot_after")
        after_source = shots_dir / Path(str(after)).name if after else None
        if after_source is not None and after_source.is_file():
            after_dst = img_dir / after_source.name
            if not after_dst.is_file():
                try:
                    shutil.copy2(after_source, after_dst)
                except Exception:
                    pass
            st["screenshot_after"] = str(after_dst)
    # copy any screenshots beyond the step count too (full evidence set)
    for s in shots[len(steps):]:
        dst = img_dir / s.name
        if not dst.is_file():
            try:
                shutil.copy2(s, dst)
            except Exception:
                pass

    with open(JUDGE / "organized_trajectory.jsonl", "w") as f:
        for st in steps:
            f.write(json.dumps(st, ensure_ascii=False) + "\n")

    fa = agent / "final_answer.txt"
    (JUDGE / "final_answer.txt").write_text(
        fa.read_text(errors="replace") if fa.is_file() else "(none)")

    # verifier scripts + recorded verdict outputs
    vdst = JUDGE / "verifier"
    if vdst.exists():
        shutil.rmtree(vdst)
    tests = Path("/tests")
    if tests.is_dir():
        shutil.copytree(tests, vdst)
    else:
        vdst.mkdir(exist_ok=True)
    vlog = LOGS / "verifier"
    if vlog.is_dir():
        for p in sorted(vlog.iterdir()):
            if p.is_file():
                try:
                    shutil.copy2(p, vdst / p.name)
                except Exception:
                    pass
    vv = vlog / "verifier_verdict.json"
    if vv.is_file():
        shutil.copyfile(vv, JUDGE / "verifier_verdict.json")

    # after-state marker: the live site tree is present in this sandbox
    site = os.environ.get("WH_SITE", "")
    live = Path(f"/opt/WebSyn/{site}/instance") if site else None
    seed = Path(f"/opt/WebSyn/{site}/instance_seed") if site else None
    if live and live.is_dir():
        (JUDGE / "after_state_marker").write_text(
            "AVAILABLE (live in-sandbox: /opt/WebSyn/%s/instance; seed at "
            "/opt/WebSyn/%s/instance_seed)" % (site, site))
    else:
        (JUDGE / "after_state_marker").write_text("UNAVAILABLE")

    print("SCENE_OK harness=%s steps=%d screenshots=%d site=%s after_state=%s"
          % (harness, len(steps), len(shots), site, bool(live and live.is_dir())),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
