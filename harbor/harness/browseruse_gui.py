#!/opt/opencode-web/bin/python
"""WebHarbor GUI harness: browser-use SDK agent loop, runs in-container as ubuntu.

Two observation modes:
  - vision (default): the policy model receives page screenshots natively.
  - text: the policy model receives HTML/accessibility-tree state only
    (browser-use use_vision=False).

Evidence written under WHB_AGENT_DIR (default /logs/agent):
  final_answer.txt               the agent's final answer text
  termination.json               {"terminated", "termination_reason"}
  screenshots/step_<n>.png       per-step browser screenshots, pruned to the
                                 last WHB_LAST_K images (default 3)
  screenshot_manifest.jsonl      one line per retained screenshot {file, ts}
  browseruse_history.json         per-step urls + extracted content + done flag

Environment:
  WHB_MODEL       required, e.g. "gpt-4o-mini"
  WHB_BASE_URL    required, OpenAI-compatible endpoint
  WHB_API_KEY     required
  WHB_START_URL   required, e.g. http://localhost:40021/
  WHB_MODE        vision | text (default vision)
  WHB_LAST_K      keep last K screenshots (default 3)
  WHB_MAX_STEPS   browser-use step budget (default 50)
  WHB_TIMEOUT     per-step timeout seconds (default 180)
  WHB_AGENT_DIR   evidence dir (default /logs/agent)

Usage: browseruse_gui.py "<instruction>"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

AGENT_DIR = Path(os.environ.get("WHB_AGENT_DIR", "/logs/agent"))
SCREENSHOT_DIR_NAME = "screenshots"


class DescribePageParams(BaseModel):
    """Params for the optional describe_page action (WHB_DESCRIBE=1).

    Defined at module level so pydantic can resolve the action-model union
    that browser-use builds for the LLM tool-calling schema.
    """

    question: str = Field(
        default="",
        description="Focused question about what to look for on the page "
        "(colors, images, layout, text rendered as graphics).",
    )


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class ScreenshotKeeper:
    """Capture per-step screenshots, keep only the last K."""

    def __init__(self, session, keep: int):
        self.session = session
        self.keep = max(1, keep)
        self.shot_dir = AGENT_DIR / SCREENSHOT_DIR_NAME
        self.shot_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = AGENT_DIR / "screenshot_manifest.jsonl"
        self.manifest_path.touch(exist_ok=True)
        self.counter = 0
        self.urls: list[dict] = []

    async def capture(self, browser_state=None) -> None:
        """Save one screenshot for the current step.

        Prefers the screenshot browser-use already captured for this step
        (BrowserStateSummary.screenshot, base64): no extra CDP call, so it
        cannot contend with the agent loop. Falls back to an explicit
        session.take_screenshot when the state carries none.
        """
        import base64

        self.counter += 1
        name = f"step_{self.counter}.png"
        target = self.shot_dir / name
        encoded = getattr(browser_state, "screenshot", None) if browser_state is not None else None
        if encoded:
            try:
                payload = encoded.split(",", 1)[1] if encoded.startswith(("data:", "data:")) else encoded
                target.write_bytes(base64.b64decode(payload))
            except Exception:
                encoded = None
        if not encoded:
            try:
                await self.session.take_screenshot(path=str(target))
            except Exception as exc:  # screenshot failure must not kill the loop
                sys.stderr.write(f"[harness] screenshot failed: {exc}\n")
                return
        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"file": name, "ts": round(time.time(), 3)}) + "\n")
        self._prune()

    def _prune(self) -> None:
        entries = [json.loads(l) for l in self.manifest_path.read_text().splitlines() if l.strip()]
        retained = entries[-self.keep:]
        stale = {e["file"] for e in entries} - {e["file"] for e in retained}
        for name in stale:
            (self.shot_dir / name).unlink(missing_ok=True)
        self.manifest_path.write_text(
            "".join(json.dumps(e) + "\n" for e in retained), encoding="utf-8"
        )


async def main() -> int:
    # Early diagnostics: Harbor's exec may swallow stderr; persist to a file.
    try:
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        debug = AGENT_DIR / "harness_debug.log"
        present = [
            k
            for k in ("WHB_MODEL", "WHB_BASE_URL", "WHB_API_KEY", "WHB_START_URL")
            if os.environ.get(k)
        ]
        with debug.open("a", encoding="utf-8") as f:
            f.write(f"argv_len={len(sys.argv)} env_present={present}\n")
    except Exception:
        pass
    instruction = sys.argv[1] if len(sys.argv) > 1 else ""
    if not instruction:
        sys.stderr.write("usage: browseruse_gui.py <instruction>\n")
        (AGENT_DIR / "harness_error.txt").write_text("missing instruction argument", encoding="utf-8")
        return 2
    for required in ("WHB_MODEL", "WHB_BASE_URL", "WHB_API_KEY", "WHB_START_URL"):
        if not os.environ.get(required):
            sys.stderr.write(f"harness: {required} is required\n")
            (AGENT_DIR / "harness_error.txt").write_text(f"missing env {required}", encoding="utf-8")
            return 2

    from browser_use import Agent, BrowserProfile, BrowserSession
    from browser_use.llm.openai.chat import ChatOpenAI
    import re as _re

    _JSON_FENCE = _re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", _re.DOTALL)

    class FenceSafeChatOpenAI(ChatOpenAI):
        """ChatOpenAI tolerant of markdown-fenced JSON responses.

        With dont_force_structured_output, claude-style backends wrap the
        JSON in ```json fences; browser-use 0.11.13 validates via
        output_format.model_validate_json inside ainvoke and rejects the
        fenced text (Invalid JSON at line 1 column 1). Strip the fence at the
        validator for the duration of the call.
        """

        @staticmethod
        def _strip_fence(text):
            if isinstance(text, str):
                match = _JSON_FENCE.match(text)
                if match:
                    return match.group(1)
            return text

        async def ainvoke(self, messages, output_format=None, **kwargs):
            if output_format is None:
                return await super().ainvoke(messages, output_format=None, **kwargs)
            model_class = output_format
            base_validator = model_class.model_validate_json  # bound classmethod

            def _validate_json(text, **validate_kwargs):
                cleaned = FenceSafeChatOpenAI._strip_fence(text)
                return base_validator(cleaned, **validate_kwargs)

            model_class.model_validate_json = staticmethod(_validate_json)
            try:
                return await super().ainvoke(messages, output_format=output_format, **kwargs)
            finally:
                del model_class.model_validate_json

    mode = os.environ.get("WHB_MODE", "vision").strip().lower()
    if mode not in ("vision", "text"):
        sys.stderr.write(f"harness: unknown WHB_MODE {mode!r} (vision|text)\n")
        return 2
    last_k = env_int("WHB_LAST_K", 3)
    max_steps = env_int("WHB_MAX_STEPS", 50)
    step_timeout = env_int("WHB_TIMEOUT", 180)

    force_structured = os.environ.get("WHB_FORCE_STRUCTURED_OUTPUT", "1") not in ("0", "false", "no")
    llm = FenceSafeChatOpenAI(
        model=os.environ["WHB_MODEL"],
        base_url=os.environ["WHB_BASE_URL"],
        api_key=os.environ["WHB_API_KEY"],
        timeout=float(env_int("WHB_LLM_TIMEOUT", 120)),
        # OpenAI-only sampling defaults (temperature=0.2, frequency_penalty=0.3)
        # are rejected by many OpenAI-compatible backends (anthropic rejects
        # frequency_penalty; claude-5.x rejects temperature != 1). Default all
        # sampling knobs off; opt in via WHB_TEMPERATURE / WHB_FREQUENCY_PENALTY.
        temperature=(float(os.environ["WHB_TEMPERATURE"]) if os.environ.get("WHB_TEMPERATURE") else None),
        frequency_penalty=(float(os.environ["WHB_FREQUENCY_PENALTY"]) if os.environ.get("WHB_FREQUENCY_PENALTY") else None),
        # Forced structured output (response_format) works on most backends
        # (gpt-4o*, claude-4.x) but claude-5.x rejects the deprecated
        # `output_format` field; set WHB_FORCE_STRUCTURED_OUTPUT=0 to convey
        # the schema in the system prompt instead.
        dont_force_structured_output=not force_structured,
        add_schema_to_system_prompt=not force_structured,
    )
    # Attach to the container's shared chromium daemon (CDP 9222, owned by the
    # agent user). All harness channels - browser-use SDK, browser-use CLI,
    # playwright-mcp - drive this single browser instance.
    cdp_url = os.environ.get("WHB_CDP_URL", "http://127.0.0.1:9222")
    profile = BrowserProfile(cdp_url=cdp_url)
    session = BrowserSession(browser_profile=profile)
    keeper = ScreenshotKeeper(session, last_k)

    async def on_step(browser_state, agent_output, step_id) -> None:
        page = getattr(browser_state, "url", None) if browser_state is not None else None
        title = ""
        raw_title = getattr(browser_state, "title", None) if browser_state is not None else None
        if isinstance(raw_title, str) and raw_title.strip():
            title = raw_title.strip()
        else:
            try:
                current = await keeper.session.get_current_page()
                title = str(await current.title() or "").strip()
            except Exception:
                title = ""
        keeper.urls.append({"step": step_id, "url": str(page or ""), "title": title})
        await keeper.capture(browser_state)

    answer_dir_suffix = (
        "\n\nWhen the task is complete, call the done action and put the full final "
        "answer (every requested fact) in the done text. You must interact only "
        f"with {os.environ['WHB_START_URL']} - do not open any other website."
    )

    # Optional describe_page action (adapted from wildawm-evaluation's
    # describe_image MCP tool): when WHB_DESCRIBE=1, the agent gets a custom
    # action that screenshots the current page and asks an external vision
    # model to describe it, so text-only policy models can query visual state.
    describe_tools = None
    if os.environ.get("WHB_DESCRIBE", "0") == "1":
        from browser_use import Tools
        from browser_use.agent.views import ActionResult

        describe_dir = AGENT_DIR / "describe"
        describe_dir.mkdir(parents=True, exist_ok=True)
        describe_counter = 0
        DESCRIBE_SCRIPT = "/opt/webharbor-harness/describe_image_mcp.py"

        describe_tools = Tools()

        @describe_tools.action(
            "Describe the current page with an external vision model. Use when "
            "you need visual details that the DOM text does not show.",
            param_model=DescribePageParams,
        )
        async def describe_page(params: DescribePageParams, browser_session):
            nonlocal describe_counter
            describe_counter += 1
            shot_path = describe_dir / f"page_{describe_counter}.png"
            try:
                await browser_session.take_screenshot(path=str(shot_path), full_page=False)
            except Exception as exc:
                return ActionResult(error=f"describe_page screenshot failed: {exc}")
            describe_env = dict(os.environ)
            describe_env.update({
                "AWM_VISION_BASE_URL": os.environ.get(
                    "WHB_VISION_BASE_URL", "https://api.openai.com/v1"),
                "AWM_VISION_API_KEY": os.environ.get(
                    "WHB_VISION_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
                "AWM_VISION_MODEL": os.environ.get(
                    "WHB_VISION_MODEL", "qwen3.6-35b-a3b"),
                "AWM_VISION_FALLBACK_BASE_URL": "",
                "AWM_VISION_FALLBACK_MODEL": "",
            })
            try:
                import subprocess as _sp
                proc = await asyncio.to_thread(
                    _sp.run,
                    ["/opt/opencode-web/bin/python", DESCRIBE_SCRIPT,
                     str(shot_path), params.question],
                    capture_output=True,
                    text=True,
                    timeout=200,
                    env=describe_env,
                )
            except Exception as exc:
                return ActionResult(error=f"describe_page vision call failed: {exc}")
            description = (proc.stdout or "").strip()
            if proc.returncode != 0 or not description:
                detail = (proc.stderr or "")[-300:] or description
                return ActionResult(error=f"describe_image error: {detail}")
            return ActionResult(extracted_content=f"[vision description of the current page]\n{description}")

    agent_kwargs = dict(
        task=instruction + answer_dir_suffix,
        llm=llm,
        browser_session=session,
        use_vision=(mode == "vision"),
        register_new_step_callback=on_step,
        max_failures=3,
    )
    if describe_tools is not None:
        agent_kwargs["tools"] = describe_tools
        agent_kwargs["task"] = (
            agent_kwargs["task"]
            + "\n\nYou are a text-only agent, but an external vision model is "
            "available through the describe_page action: call it with a focused "
            "question to get a visual description of the current page (colors, "
            "images, layout, text rendered as graphics)."
        )
    agent = Agent(**agent_kwargs)

    termination_reason = "agent_done"
    try:
        history = await asyncio.wait_for(
            agent.run(max_steps=max_steps), timeout=max_steps * step_timeout
        )
    except asyncio.TimeoutError:
        history = None
        termination_reason = "timeout"
    except Exception as exc:
        sys.stderr.write(f"[harness] agent run failed: {exc}\n")
        history = None
        termination_reason = "error"

    final_answer = ""
    is_done = False
    extracted: list[str] = []
    step_results: list[list[str]] = []
    state_urls: list[str] = []
    if history is not None:
        final_answer = history.final_result() or ""
        is_done = bool(history.is_done())
        try:
            content = history.extracted_content
            extracted = content() if callable(content) else list(content or [])
        except Exception:
            extracted = []
        try:
            # Per-step ground truth for the trajectory builder: each history
            # item is one browser-use step; h.result holds that step's action
            # results; history.urls() the per-step pre-state URLs.
            for h in history.history:
                step_results.append(
                    [r.extracted_content for r in (h.result or []) if r and r.extracted_content]
                )
            state_urls = [str(u) if u is not None else "" for u in (history.urls() or [])]
        except Exception:
            step_results, state_urls = [], []
        if not is_done:
            termination_reason = "max_steps"
    else:
        termination_reason = termination_reason if termination_reason != "agent_done" else "error"

    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    (AGENT_DIR / "final_answer.txt").write_text(final_answer, encoding="utf-8")
    # WebHarbor verifiers gate some tasks on success_self_report (the demo
    # agent reported success at its "done" action). browser-use's is_done flag
    # is the equivalent self-report.
    (AGENT_DIR / "termination.json").write_text(
        json.dumps({
            "terminated": True,
            "termination_reason": termination_reason,
            "success_self_report": bool(is_done and termination_reason == "agent_done"),
        }) + "\n",
        encoding="utf-8",
    )
    # Some verifiers (cvs, us-doj) read Playwright browser-state.json from the
    # run dir for cart ownership and selected-store cookies. Attach to the
    # shared chromium over CDP and dump storage_state, best effort.
    try:
        import subprocess as _sp
        target = AGENT_DIR / "browser-state.json"
        script = (
            "import asyncio, json\n"
            "from playwright.async_api import async_playwright\n"
            "async def main():\n"
            "    async with async_playwright() as p:\n"
            "        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')\n"
            "        ctx = browser.contexts[0] if browser.contexts else None\n"
            "        if not ctx: raise SystemExit(3)\n"
            "        state = await ctx.storage_state()\n"
            f"        open({str(target)!r}, 'w').write(json.dumps(state))\n"
            "asyncio.run(main())\n"
        )
        out = _sp.run(
            ["/opt/opencode-web/bin/python", "-c", script],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0 or not target.is_file():
            sys.stderr.write(
                f"[harness] browser-state dump failed rc={out.returncode}: "
                f"{(out.stderr or '')[-200:]}\n")
    except Exception as exc:
        sys.stderr.write(f"[harness] browser-state dump failed: {exc}\n")
    try:
        (AGENT_DIR / "browseruse_history.json").write_text(
            json.dumps(
                {
                    "mode": mode,
                    "last_k_images": last_k,
                    "is_done": is_done,
                    "termination_reason": termination_reason,
                    "step_urls": keeper.urls,
                    "extracted_content": extracted,
                    "step_results": step_results,
                    "state_urls": state_urls,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        sys.stderr.write(f"[harness] history dump failed: {exc}\n")
    try:
        await session.stop()
    except Exception:
        pass
    sys.stderr.write(
        f"[harness] done: reason={termination_reason} answer_len={len(final_answer)} "
        f"screenshots_retained={len(list((AGENT_DIR / SCREENSHOT_DIR_NAME).glob('*.png')))}\n"
    )
    return 0


def _run() -> int:
    try:
        return asyncio.run(main())
    except SystemExit as exc:  # argparse etc.
        return int(exc.code or 0)
    except BaseException:
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        try:
            AGENT_DIR.mkdir(parents=True, exist_ok=True)
            (AGENT_DIR / "harness_error.txt").write_text(tb, encoding="utf-8")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(_run())
