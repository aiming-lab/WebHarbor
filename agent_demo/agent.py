import asyncio
import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from browser_use import Browser, Tools
import simpleArgParser as sap


@dataclass
class AgentArgs:
    task: str = ""
    url: str = ""
    tasks_file: str = ""
    task_id: str = ""
    out_dir: str = "./runs/agent"
    max_steps: int = 15
    model: str = ""          # agent LLM model id (env: JUDGE_MODEL if unset)
    api_key: str = ""        # env: OPENAI_API_KEY
    api_base: str = ""       # env: OPENAI_BASE_URL
    headless: bool = True     # only used when MW_CDP_URL is unset (CDP takes priority)
    history_window: int = 5
    dom_char_limit: int = 12000
    judge_rubric: str = ""   # carried into trajectory.json for the LLM judge
    verifier_path: str = ""  # carried into trajectory.json for the verifier mode

    def post_process(self):
        if self.tasks_file:
            path = Path(self.tasks_file)
            if not path.exists():
                raise SystemExit(f"tasks file not found: {path}")
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if self.task_id:
                row = next((r for r in rows if r.get("id") == self.task_id), None)
                if row is None:
                    raise SystemExit(f"task_id {self.task_id!r} not in {path}")
            else:
                row = rows[0]
            self.task = self.task or row.get("ques", "")
            self.url = self.url or row.get("web", "")
            self.task_id = self.task_id or row.get("id", "")
            self.judge_rubric = row.get("judge_rubric", "")
            self.verifier_path = row.get("verifier_path", "")
        if not self.task or not self.url:
            raise SystemExit("provide --tasks_file [--task_id ID] or both --task and --url")


SYSTEM_PROMPT = """You are a web agent driving a real browser. Each turn you receive:
  1. a DOM tree of the current page, where [N] are clickable element indices;
  2. a screenshot of the same page.

You respond with EXACTLY one JSON object describing one action. No prose, no
fences, no extra text. Schema:

  {"thought": "<short reasoning>", "action": "<name>", "params": { ... }}

Valid actions and their params:
  click       {"index": <int>}
  input       {"index": <int>, "text": "<str>"}
  scroll      {"down": <bool>, "pages": <float>}
  navigate    {"url": "<str>"}
  go_back     {}
  done        {"text": "<final answer or summary>", "success": <bool>}

Rules:
- Use indices that appear in the DOM tree below; do not invent them.
- If the task asks for an answer (e.g. "what is X"), write it in done.text.
- Stop with done as soon as the task is complete or clearly impossible.
"""


def build_messages(task, url, title, dom_text, screenshot_b64, history,
                   history_window, dom_char_limit):
    if len(dom_text) > dom_char_limit:
        dom_text = dom_text[:dom_char_limit] + f"\n... (truncated, full length {len(dom_text)})"

    history_lines = []
    for h in history[-history_window:]:
        history_lines.append(
            f"  step {h['step']}: action={h['action']} params={h.get('params', {})} "
            f"thought={h['thought'][:120]}"
        )
    history_block = "\n".join(history_lines) if history_lines else "  (none)"

    user_text = (
        f"TASK:\n{task}\n\n"
        f"CURRENT URL: {url}\n"
        f"PAGE TITLE: {title}\n\n"
        f"DOM:\n{dom_text}\n\n"
        f"PREVIOUS ACTIONS:\n{history_block}\n\n"
        f"Respond with one JSON action."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            ],
        },
    ]


def parse_action_json(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    start = s.find("{")
    if start < 0:
        raise ValueError(f"no JSON in response: {raw[:200]!r}")
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start : i + 1])
    raise ValueError(f"unterminated JSON in response: {raw[:200]!r}")


def build_action_model(tools, action_name, params):
    AM = tools.registry.create_action_model()
    return AM(**{action_name: params})


async def execute(tools, browser, name, params):
    am = build_action_model(tools, name, params)
    return await tools.act(am, browser_session=browser)


def save_screenshot_b64(b64, path):
    Path(path).write_bytes(base64.b64decode(b64))


async def run(args):
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    api_base = args.api_base or os.environ.get("OPENAI_BASE_URL", "")
    model = args.model or os.environ.get("JUDGE_MODEL", "")
    if not api_key:
        raise SystemExit("API key missing: set --api_key or OPENAI_API_KEY")
    if not api_base:
        raise SystemExit("API base missing: set --api_base or OPENAI_BASE_URL")
    if not model:
        raise SystemExit("model missing: set --model or JUDGE_MODEL")
    args.model = model

    print(f"task_id={args.task_id or '<inline>'}  url={args.url}\n  ques: {args.task}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shots = out / "screenshots"
    shots.mkdir(exist_ok=True)

    client = OpenAI(base_url=api_base, api_key=api_key)

    # Connect to an externally-launched headless Chrome via CDP when MW_CDP_URL is
    # set. browser-use's own Browser() launcher can hang on some hosts (watchdog
    # timeout on BrowserStartEvent); a persistent CDP chrome avoids that and lets
    # many agents run concurrently with cookie isolation (one chrome per agent).
    cdp_url = os.environ.get("MW_CDP_URL", "")
    if cdp_url:
        browser = Browser(cdp_url=cdp_url)
    else:
        browser = Browser(headless=args.headless)
    await browser.start()
    tools = Tools()

    try:
        await browser.navigate_to(args.url)

        state = await browser.get_browser_state_summary(include_screenshot=True)
        save_screenshot_b64(state.screenshot, shots / "step_000.png")

        trajectory = {
            "task": args.task,
            "task_id": args.task_id,
            "start_url": args.url,
            "model": args.model,
            "max_steps": args.max_steps,
            "steps": [],
            "terminated": False,
            "termination_reason": None,
            "final_answer": None,
            "judge_rubric": args.judge_rubric,
            "verifier_path": args.verifier_path,
        }

        for step_idx in range(args.max_steps):
            dom_text = state.dom_state.llm_representation()
            messages = build_messages(
                task=args.task,
                url=state.url,
                title=state.title,
                dom_text=dom_text,
                screenshot_b64=state.screenshot,
                history=trajectory["steps"],
                history_window=args.history_window,
                dom_char_limit=args.dom_char_limit,
            )

            resp = client.chat.completions.create(model=args.model, messages=messages)
            raw = resp.choices[0].message.content or ""
            try:
                action = parse_action_json(raw)
            except Exception as e:
                print(f"[step {step_idx}] FAILED to parse LLM reply: {e}", file=sys.stderr)
                trajectory["terminated"] = True
                trajectory["termination_reason"] = f"parse_error: {e}"
                trajectory["raw_reply"] = raw
                break

            name = action.get("action", "")
            params = action.get("params", {}) or {}
            thought = action.get("thought", "")

            step_log = {
                "step": step_idx,
                "url": state.url,
                "title": state.title,
                "thought": thought,
                "action": name,
                "params": params,
                "screenshot_before": f"step_{step_idx:03d}.png",
                "screenshot_after": f"step_{step_idx + 1:03d}.png",
            }
            trajectory["steps"].append(step_log)
            print(f"[step {step_idx}] {name} {params}  // {thought[:80]}")

            if name == "done":
                trajectory["terminated"] = True
                trajectory["termination_reason"] = "agent_done"
                trajectory["final_answer"] = params.get("text", "")
                trajectory["success_self_report"] = bool(params.get("success", False))
                final_state = await browser.get_browser_state_summary(include_screenshot=True)
                save_screenshot_b64(final_state.screenshot, shots / f"step_{step_idx + 1:03d}.png")
                break

            try:
                result = await execute(tools, browser, name, params)
                step_log["action_result"] = {
                    "is_done": getattr(result, "is_done", None),
                    "success": getattr(result, "success", None),
                    "error": getattr(result, "error", None),
                    "extracted_content": (getattr(result, "extracted_content", None) or "")[:500],
                }
            except Exception as e:
                step_log["action_result"] = {"error": f"{type(e).__name__}: {e}"}
                print(f"[step {step_idx}] action failed: {e}", file=sys.stderr)

            state = await browser.get_browser_state_summary(include_screenshot=True)
            save_screenshot_b64(state.screenshot, shots / f"step_{step_idx + 1:03d}.png")
        else:
            trajectory["termination_reason"] = "max_steps"

        traj_path = out / "trajectory.json"
        traj_path.write_text(json.dumps(trajectory, indent=2))
        print(f"\nWrote {traj_path}")
        print(f"  steps: {len(trajectory['steps'])}")
        print(f"  screenshots: {len(list(shots.glob('step_*.png')))}")
        print(f"  terminated: {trajectory['terminated']} ({trajectory['termination_reason']})")
        if trajectory.get("final_answer"):
            print(f"  final_answer: {trajectory['final_answer'][:300]}")

        return trajectory
    finally:
        await browser.stop()


def main():
    args = sap.parse_args(AgentArgs)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
