#!/usr/bin/env python3
"""Assemble the verifier run_dir trajectory from root-controlled evidence.

Runs inside tests/test.sh as root (shared verifier mode). Produces
<run_dir>/trajectory.json in the WebHarbor verifier contract (see
agent_demo/agent.py, the reference agent that wrote the original schema):

  {task, task_id, start_url, model, steps: [{step, url, action, params,
   thought, observed_text, extracted_content, screenshot_before,
   screenshot_after, url_after?}], terminated, termination_reason,
   final_answer, final_url, final_observed_text}

Sources (root-owned; the agent cannot forge any of them):
  /var/log/site_access.jsonl              site access log (ground-truth URLs)
  /logs/agent/final_answer.txt            agent's final answer
  /logs/agent/termination.json            harness termination record
  /logs/agent/screenshot_manifest.jsonl   screenshots taken by the harness
  /logs/agent/screenshots/*.png
  /logs/agent/trajectory.json             opencode harness capture (ATIF)
  /logs/agent/browseruse_history.json     GUI harness capture

Steps come from the harness capture (real browser actions/observations as
recorded by the harness code) and every step URL is required to be on the
site origin (the mirror host/port). The access log remains the ground-truth
URL baseline; when the capture is unusable the trajectory falls back to
access-log steps. Screenshots are copied to <run_dir>/screenshots/ so
verifiers can decode them by the names referenced in the steps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ACCESS_LOG = Path(os.environ.get("WH_ACCESS_LOG", "/var/log/site_access.jsonl"))
AGENT_DIR = Path(os.environ.get("WH_AGENT_DIR", "/logs/agent"))

# playwright-mcp tool name -> WebHarbor browser-use action name
OPENCODE_ACTION_MAP = {
    "navigate": "navigate",
    "click": "click",
    "type": "type",
    "fill": "fill",
    "fill_form": "fill",
    "select_option": "select",
    "hover": "hover",
    "press": "press",
    "wait": "wait",
    "snapshot": "snapshot",
    "go_back": "go_back",
    "go_forward": "go_forward",
    "drag": "drag",
    "screenshot": "screenshot",
    "close": "close",
    "resize": "resize",
}

# browser-use extracted_content leading verb -> action name
GUI_VERB_MAP = {
    "clicked": "click",
    "navigated": "navigate",
    "typed": "type",
    "selected": "select",
    "searched": "search",
    "scrolled": "scroll",
    "waited": "wait",
    "pressed": "press",
    "downloaded": "download",
    "switched": "switch_tab",
    "opened": "navigate",
    "found": "found",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def on_origin(url: str, port: int) -> bool:
    try:
        parts = urlsplit(url)
        return (
            parts.scheme in ("http", "https")
            and parts.hostname in ("localhost", "127.0.0.1")
            and (parts.port or 80) == port
        )
    except Exception:
        return False


def access_url(record: dict, port: int) -> str:
    url = f"http://localhost:{port}{record.get('path', '')}"
    if record.get("query"):
        url += f"?{record['query']}"
    return url


def nearest_screenshots(step_ts: float, manifest: list[dict]) -> tuple[str | None, str | None]:
    """Screenshot references for a step, clamped to the capture bounds.

    The WebHarbor verifiers require every step to carry both a
    screenshot_before and a screenshot_after that resolve under the run dir;
    agent.py's reference trajectory always had both (one screenshot per state
    boundary). Clamp to the first/last captured screenshot at the edges.
    """
    if not manifest:
        return None, None
    before = manifest[0]["file"]
    after = manifest[-1]["file"]
    for entry in manifest:
        if float(entry["ts"]) <= step_ts:
            before = entry["file"]
        elif after is None:
            after = entry["file"]
            break
    return before, after


def parse_iso_ts(value) -> float | None:
    if value is None:
        return None
    text = str(value)
    try:
        return float(text)
    except ValueError:
        pass
    try:
        from datetime import datetime, timezone

        text2 = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text2).timestamp()
    except Exception:
        return None


def opencode_action(name: str) -> str:
    base = name
    while base.startswith("browser_"):
        base = base[len("browser_"):]
    return OPENCODE_ACTION_MAP.get(base, base)


def build_opencode_steps(atif: dict, access: list[dict], manifest: list[dict], port: int) -> tuple[list[dict], str]:
    """Steps from the opencode ATIF capture: browser_* tool calls with their
    page snapshots. observed_text comes from the page snapshot (yml) the agent
    read right after acting."""
    steps: list[dict] = []
    last_observed = ""
    for atif_step in atif.get("steps", []):
        ts = parse_iso_ts(atif_step.get("timestamp"))
        calls = atif_step.get("tool_calls") or []
        obs = atif_step.get("observation") or {}
        obs_content = ""
        obs_title = ""
        results = obs.get("results") if isinstance(obs, dict) else None
        if isinstance(results, list):
            for r in results:
                if not isinstance(r, dict):
                    continue
                content = str(r.get("content", ""))
                if not obs_content and ("[ref=" in content or content.startswith("<path>")):
                    obs_content = content
                if not obs_title:
                    tm = re.search(r"Page Title:[ \t]*([^\n]*)", content)
                    if tm:
                        obs_title = tm.group(1).strip()[:300]
        message = atif_step.get("message")
        thought = message if isinstance(message, str) else ""
        for call in calls:
            fname = str(call.get("function_name", ""))
            arguments = call.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {"raw": arguments}
            arguments = arguments if isinstance(arguments, dict) else {}
            if fname.startswith("browser_"):
                url = None
                if opencode_action(fname) == "navigate" and arguments.get("url"):
                    url = str(arguments["url"])
                form_fields = arguments.get("fields")
                if fname.endswith("fill_form") and isinstance(form_fields, list) and form_fields:
                    # One fill_form call types several form fields; emit one
                    # input step per field so params.text carries each typed
                    # value (the original one-action-per-typed-value contract).
                    for field in form_fields:
                        if not isinstance(field, dict):
                            continue
                        steps.append({
                            "_ts": ts,
                            "action": opencode_action(fname),
                            "params": {
                                "text": str(field.get("value") or ""),
                                "element": str(field.get("name") or ""),
                            },
                            "thought": thought,
                            "url_hint": None,
                            "_observed_pending": True,
                            "action_result": {"success": True, "error": None},
                        })
                else:
                    steps.append({
                        "_ts": ts,
                        "action": opencode_action(fname),
                        "params": arguments,
                        "thought": thought,
                        "url_hint": url,
                        "_observed_pending": True,
                        "action_result": {"success": True, "error": None},
                    })
        if obs_content and steps:
            last = steps[-1]
            last["observed_text"] = obs_content
            last["observed_text_after"] = obs_content
            last_observed = obs_content
        if obs_title and steps and not steps[-1].get("title"):
            steps[-1]["title"] = obs_title

    # resolve urls from the access log + navigate hints
    for step in steps:
        hint = step.pop("url_hint", None)
        ts = step.pop("_ts", None)
        step.pop("_observed_pending", None)
        url = hint
        if url is None and ts is not None:
            for record in reversed(access):
                if float(record.get("ts") or 0) <= ts:
                    url = access_url(record, port)
                    break
        if url is None:
            url = access_url(access[0], port) if access else f"http://localhost:{port}/"
        step["url"] = url
        if ts is not None and manifest:
            before, after = nearest_screenshots(ts, manifest)
            if before:
                step["screenshot_before"] = before
            if after:
                step["screenshot_after"] = after
    return steps, last_observed


def gui_action(summary: str) -> str:
    text = summary.strip()
    for prefix in ("🔗", "🔍", "🖱", "⌨️"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            if prefix == "🔗":
                return "navigate"
            if prefix == "🔍":
                return "search"
            if prefix == "🖱":
                return "click"
            if prefix == "⌨️":
                return "type"
    head = text.split(" ")[0].split("\n")[0].lower().strip()
    for verb, action in GUI_VERB_MAP.items():
        if head.startswith(verb):
            return action
    return "action"


def build_gui_steps(history: dict, access: list[dict], manifest: list[dict], port: int) -> tuple[list[dict], str]:
    """Steps from the browser-use GUI capture.

    When the wrapper recorded per-step ground truth (step_results = each
    browser-use step's own action results, state_urls = per-step pre-state
    URLs), one trajectory step is emitted per ACTION: the original agent.py
    contract is one action per step, and on-path typed-credential checks
    (berkeley/webmd-doctor) correlate the typed step with its page URL.
    Typing actions are labeled with the step's END url (the next step's
    pre-state), because a click earlier in the same step may have opened the
    page the typing acts on. Old histories without step_results keep the
    legacy one-step-per-entry i-1 pairing."""
    step_urls = history.get("step_urls") or []
    extracted = [str(e) for e in (history.get("extracted_content") or [])]
    step_results = history.get("step_results") or []
    state_urls = history.get("state_urls") or []
    exact = (
        bool(step_results)
        and bool(state_urls)
        and len(state_urls) == len(step_results)
        and sum(len(r) for r in step_results) == len(extracted)
    )
    steps: list[dict] = []
    n_entries = len(step_results) if exact else len(step_urls)
    for i in range(n_entries):
        entry = step_urls[i] if i < len(step_urls) else {}
        if exact:
            own = [str(e) for e in (step_results[i] or [])]
            start_url = str(state_urls[i] or "")
            end_url = str(state_urls[i + 1] or "") if i + 1 < len(state_urls) else ""
        else:
            own = [extracted[i - 1]] if 0 < i <= len(extracted) else []
            start_url = str(entry.get("url") or "")
            end_url = ""
        title = str(entry.get("title") or "").strip()
        shots = (None, None)
        ts = entry.get("ts")
        if ts is None and manifest:
            ts = manifest[min(i, len(manifest) - 1)]["ts"]
        if ts is not None and manifest:
            shots = nearest_screenshots(float(ts), manifest)
        for summary in own:
            # Page labeling: typed actions act on the page the step STARTED
            # on (verified against berkeley ground truth: the typing happens
            # before any intra-step navigation); explicit navigation ECs carry
            # their own target; other actions take the step's END url (the
            # next step's pre-state).
            act = gui_action(summary) if summary and "final answer" not in summary[:24].lower() else None
            url = start_url
            nav = re.match(r"^[^A-Za-z]*Navigated to (\S+)", summary)
            if nav and on_origin(nav.group(1), port):
                url = nav.group(1)
            elif act in ("input", "type", "fill"):
                url = start_url
            elif end_url and on_origin(end_url, port):
                url = end_url
            if not on_origin(url, port):
                continue
            step = {"url": url}
            if act:
                step["action"] = act
                step["extracted_content"] = summary
            # Original-contract fields: several verifiers read params.text for
            # typed credentials, and the drugs-com protocol gates on
            # params/title/action_result.
            step["params"] = {}
            if step.get("action") in ("input", "type", "fill") and summary:
                tm = re.match(r"^[Tt]yped\s+(['\"])(.*)\1", summary, re.S)
                if tm:
                    step["params"] = {"text": tm.group(2)}
            if title:
                step["title"] = title[:300]
            if step.get("action") and step["action"] != "done":
                step.setdefault("action_result", {"success": True, "error": None})
            if shots[0]:
                step["screenshot_before"] = shots[0]
            if shots[1]:
                step["screenshot_after"] = shots[1]
            steps.append(step)
        if not own and start_url and on_origin(start_url, port):
            placeholder = {"url": start_url, "params": {}}
            if shots[0]:
                placeholder["screenshot_before"] = shots[0]
            if shots[1]:
                placeholder["screenshot_after"] = shots[1]
            steps.append(placeholder)
    return steps, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    port = int(os.environ.get("WH_PORT", "40000"))
    task_id = os.environ.get("WH_TASK_ID", "")
    start_url = os.environ.get("WH_START_URL", f"http://localhost:{port}/")
    task_text = os.environ.get("WH_TASK_QUES", "")
    model = os.environ.get("WHB_MODEL") or os.environ.get("WH_MODEL", "")

    access = load_jsonl(ACCESS_LOG)
    manifest = load_jsonl(AGENT_DIR / "screenshot_manifest.jsonl")

    answer_path = AGENT_DIR / "final_answer.txt"
    final_answer = answer_path.read_text(encoding="utf-8") if answer_path.is_file() else ""

    termination = {"terminated": False, "termination_reason": "missing"}
    term_path = AGENT_DIR / "termination.json"
    if term_path.is_file():
        try:
            termination = json.loads(term_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    steps: list[dict] = []
    final_observed = ""
    capture = "none"
    atif_path = AGENT_DIR / "trajectory.json"
    gui_path = AGENT_DIR / "browseruse_history.json"
    if atif_path.is_file():
        try:
            atif = json.loads(atif_path.read_text(encoding="utf-8"))
            steps, final_observed = build_opencode_steps(atif, access, manifest, port)
            capture = "opencode"
            if not model:
                agent = atif.get("agent") or {}
                model = str(agent.get("model_name") or model)
        except Exception as exc:
            sys.stderr.write(f"[build_trajectory] opencode capture unusable: {exc}\n")
    elif gui_path.is_file():
        try:
            history = json.loads(gui_path.read_text(encoding="utf-8"))
            steps, final_observed = build_gui_steps(history, access, manifest, port)
            capture = "browseruse"
        except Exception as exc:
            sys.stderr.write(f"[build_trajectory] gui capture unusable: {exc}\n")

    if not steps:
        # Fallback: access-log steps (URL ground truth, no action data).
        base_ts = time.time() - 3600.0
        for index, record in enumerate(access):
            url = access_url(record, port)
            step_ts = float(record.get("ts") or base_ts)
            step = {"url": url}
            if manifest:
                before, after = nearest_screenshots(step_ts, manifest)
                if before:
                    step["screenshot_before"] = before
                if after:
                    step["screenshot_after"] = after
            steps.append(step)
        capture = "access_log"

    # keep only on-origin steps (about:blank / off-site states are not valid
    # WebHarbor steps and would trip strict URL checks in the verifiers)
    steps = [s for s in steps if on_origin(str(s.get("url")), port)] or (
        [{"url": start_url}] if on_origin(start_url, port) else []
    )

    for i, step in enumerate(steps):
        step["step"] = i

    final_url = steps[-1]["url"] if steps else start_url

    # agent.py's contract: a run that finished with agent_done ends with a
    # final 'done' step carrying the self-reported answer (verifiers gate on
    # steps[-1].action == "done", e.g. mega's run_complete).
    terminated = bool(termination.get("terminated"))
    reason = str(termination.get("termination_reason", ""))
    if terminated and reason == "agent_done":
        shot = manifest[-1]["file"] if manifest else None
        done_step = {
            "step": len(steps),
            "url": final_url,
            "url_after": final_url,
            "action": "done",
            "params": {"text": final_answer, "success": True},
            "thought": "",
            "observed_text": final_observed,
        }
        if shot:
            done_step["screenshot_before"] = shot
            done_step["screenshot_after"] = shot
        steps.append(done_step)
        final_url = final_url

    # Forward-fill page titles: steps that acted on the current page without
    # producing a titled observation (e.g. element searches) inherit the most
    # recent known title of that same page.
    last_known_title = ""
    for s in steps:
        t = str(s.get("title") or "").strip()
        if t:
            last_known_title = t
        elif last_known_title:
            s["title"] = last_known_title

    if steps:
        steps[-1]["url_after"] = final_url

    trajectory = {
        "task": task_text,
        "task_id": task_id,
        "start_url": start_url,
        "model": model,
        "steps": steps,
        "terminated": bool(termination.get("terminated")),
        "termination_reason": str(termination.get("termination_reason", "")),
        "success_self_report": bool(termination.get("success_self_report", False)),
        "final_answer": final_answer,
        "final_url": final_url,
        "final_observed_text": final_observed,
        "_capture": capture,
    }

    shots_dir = run_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    for entry in manifest:
        source = AGENT_DIR / "screenshots" / entry["file"]
        if source.is_file():
            shutil.copy2(source, shots_dir / entry["file"])

    (run_dir / "trajectory.json").write_text(
        json.dumps(trajectory, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    sys_stats = {
        "capture": capture,
        "steps": len(steps),
        "actions": sum(1 for s in steps if s.get("action")),
        "observed_texts": sum(1 for s in steps if s.get("observed_text")),
        "access_records": len(access),
        "screenshot_records": len(manifest),
        "answer_chars": len(final_answer),
        "terminated": trajectory["terminated"],
    }
    sys.stderr.write(f"[build_trajectory] {sys_stats}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
