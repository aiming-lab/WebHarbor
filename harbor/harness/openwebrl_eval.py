#!/opt/opencode-web/bin/python
"""OpenWebRL-compatible WebHarbor evaluation harness.

This runner reproduces the OpenWebRL browser policy loop:
- browser_env response format and exact system prompt/tool schemas;
- turn-level interaction;
- latest-one-screenshot model context;
- tool feedback included as <tool_response>;
- 30 browser steps;
- temperature 0.6, top-p 0.95, top-k 20;
- maximum response 4096 tokens and maximum input context 32768 tokens.

The agent passes the <user_request> text (by default the task description that
the WebHarbor RL parquet uses as the intent) and decides the assistant
"<think>\\n" prefill from the checkpoint chat template, following OpenWebRL's
ensure_prompt_ends_with_visible_thinking_tag: OpenWebRL-4B-SFT and the
WebHarbor RL checkpoints already end their generation prompt with <think>, so
their requests carry no prefill.

It attaches Playwright to the WebHarbor task container's shared Chromium over
CDP, gives every page the 1280x1000 viewport of OpenWebRL's own browser
context, and writes the normal browseruse-style verifier evidence under
/logs/agent, plus openwebrl_history.json and openwebrl_config.json.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import importlib.resources
import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from openwebrl_runtime.feedback_utils import (
    DEFAULT_BROWSER_TOOL_RESPONSE_MAX_CHARS,
    truncate_feedback_text,
)
from openwebrl_runtime.policy_api import run_policy_api_step
from openwebrl_runtime.prompt_adapter import (
    IMAGE_PLACEHOLDER,
    VISIBLE_THINKING_PREFILL,
    native_chat_extra_body,
    prepare_native_chat_context,
    render_native_tool_system_prompt,
    restore_visible_thinking_prefill,
)
from openwebrl_runtime.web_env import WebEnv

AGENT_DIR = Path(os.environ.get("OWRL_AGENT_DIR", "/logs/agent"))
TOOL_CALL_RE = re.compile(r"<tool_call>\n(.*?)\n</tool_call>", re.DOTALL)


@dataclass
class ToolCall:
    name: str
    parameters: Any


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_resources() -> tuple[str, list[dict[str, Any]]]:
    package = importlib.resources.files("openwebrl_runtime")
    policy = package.joinpath("system_prompt_browser_env.md").read_text(encoding="utf-8")
    tools = json.loads(package.joinpath("tool_list.json").read_text(encoding="utf-8"))
    return policy, tools


def parse_tool_calls(
    response: str,
    valid_tools: set[str] | None = None,
) -> tuple[list[ToolCall], str | None]:
    """Reproduce SGLang 0.5.6's Qwen25 non-streaming tool parser."""
    matches = TOOL_CALL_RE.findall(response or "")
    if not matches:
        return [], None
    calls: list[ToolCall] = []
    for raw in matches:
        try:
            item = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        items = item if isinstance(item, list) else [item]
        for action in items:
            if not isinstance(action, dict):
                continue
            name = action.get("name")
            if not name or (valid_tools is not None and name not in valid_tools):
                continue
            parameters = action.get("parameters") or action.get("arguments", {})
            calls.append(ToolCall(name=name, parameters=parameters))
    return calls, None


def response_usage(raw: dict[str, Any]) -> dict[str, Any]:
    usage = raw.get("usage")
    return dict(usage) if isinstance(usage, dict) else {}


def prompt_tokens_from_usage(raw: dict[str, Any]) -> int | None:
    usage = response_usage(raw)
    for key in ("prompt_tokens", "input_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            return value
    return None


def action_result_text(call: ToolCall) -> str:
    name = call.name
    params = call.parameters if isinstance(call.parameters, dict) else {}
    if name == "click":
        return f"Clicked at {params.get('point_2d')}"
    if name == "write":
        return f"Typed {str(params.get('message', ''))!r}"
    if name == "press_keys":
        return f"Pressed keys {params.get('keys')}"
    if name == "scroll":
        return f"Scrolled {params.get('direction')} by {params.get('amount')}"
    if name == "wait":
        return f"Waited for {params.get('seconds')} seconds"
    if name == "done":
        return str(params.get("response", ""))
    if name == "goto_url":
        return f"Navigated to {params.get('url')}"
    if name == "go_back":
        return "Navigated back"
    if name == "drag":
        return f"Dragged from {params.get('start_point_2d')} to {params.get('end_point_2d')}"
    if name == "hover":
        return f"Hovered at {params.get('point_2d')}"
    if name == "new_tab":
        return "Opened a new tab"
    if name == "switch_tab":
        return f"Switched to tab {params.get('tab_index')}"
    if name == "close_tab":
        return "Closed the current tab"
    return str(name)


def done_response(calls: list[ToolCall]) -> str | None:
    for call in calls:
        if call.name == "done" and isinstance(call.parameters, dict):
            return str(call.parameters.get("response", ""))
    return None


def native_request(
    messages: list[dict[str, Any]],
    images: list[str],
    context_num_screenshots: int,
    assistant_prefill: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Request messages of one turn: latest screenshots only, plus the <think> prefill message when it is enabled."""
    request_messages, request_images = prepare_native_chat_context(
        messages,
        images,
        context_num_screenshots,
    )
    if not assistant_prefill:
        # The checkpoint template already ends its generation prompt with <think>; a prefill message would double it.
        request_messages = request_messages[:-1]
    return request_messages, request_images


def request_extra_body(raw: str, assistant_prefill: bool) -> dict[str, Any]:
    body = json.loads(native_chat_extra_body(raw))
    if not assistant_prefill:
        # Without a trailing assistant message the request is a plain generation prompt.
        body.pop("continue_final_message")
    return body


def render_observation(observation: dict[str, Any]) -> tuple[str, str]:
    screen_size = observation.get("screen_size") or ["", ""]
    tabs = observation.get("all_tab_url") or []
    active_index = next((tab.get("index") for tab in tabs if tab.get("active")), None)
    lines = ["<observation>", f"screen size: {screen_size[0]} x {screen_size[1]}"]
    if active_index is not None:
        lines.append(f"Current tab: {active_index}")
        lines.append("Available tabs:")
        for tab in tabs:
            suffix = " (active)" if tab.get("active") else ""
            title = f" - {tab.get('title', '')}" if tab.get("title") else ""
            lines.append(f"- Tab {tab.get('index', '')}{suffix}: {tab.get('url', '')}{title}")
    else:
        lines.append(f"url: {observation.get('active_tab_url', '')}")
    screenshot = observation.get("screenshot")
    if not isinstance(screenshot, (bytes, bytearray)):
        raise TypeError(f"Screenshot must be bytes, got {type(screenshot)}")
    lines.extend(["screenshot:", IMAGE_PLACEHOLDER, "</observation>"])
    image = "data:image/png;base64," + base64.b64encode(bytes(screenshot)).decode("ascii")
    return "\n".join(lines), image


class CDPWebEnv(WebEnv):
    """OpenWebRL WebEnv action semantics on the existing task Chromium."""

    def __init__(self, *, cdp_url: str, **kwargs):
        super().__init__(**kwargs)
        self.cdp_url = cdp_url
        self._listener_installed = False

    async def _initialize_context(
        self,
        enable_recording: bool = False,
        start_url: str = "about:blank",
        auth_info: dict | None = None,
    ) -> None:
        if self.playwright is None:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser_type = self.playwright.chromium
            self.browser = await self.browser_type.connect_over_cdp(self.cdp_url)
        if not self.browser.contexts:
            raise RuntimeError("CDP Chromium has no browser context")
        self.context = self.browser.contexts[0]
        self.context.set_default_timeout(self.timeout)

        pages = list(self.context.pages)
        if not pages:
            pages = [await self.context.new_page()]
        self.page = pages[0]
        for stale_page in pages[1:]:
            try:
                await stale_page.close()
            except Exception:
                pass
        await self.page.set_viewport_size({"width": self.css_width, "height": self.css_height})

        start_urls = start_url.split(" |AND| ")
        for index, url in enumerate(start_urls):
            page = self.page if index == 0 else await self.context.new_page()
            for attempt in range(self.max_retries):
                try:
                    await page.goto(url, timeout=self.init_navigation_timeout)
                    await page.wait_for_load_state("domcontentloaded")
                    break
                except Exception as exc:
                    if attempt >= self.max_retries - 1:
                        raise EnvironmentError(
                            f"Failed to navigate to {url} after {self.max_retries} attempts: {exc}"
                        ) from exc
                    await asyncio.sleep(2)
        self.page = self.context.pages[0]
        await self.page.bring_to_front()
        if not self._listener_installed:
            self.setup_global_page_listener()
            self.context.on("page", self._size_new_page)
            self._listener_installed = True
        self.setup_dialog_interceptor()
        await asyncio.sleep(2)

    async def _apply_viewport(self, page) -> None:
        # OpenWebRL's own browser context sizes every page; pages opened in the attached CDP context start without a viewport (780x437 headless window).
        viewport = {"width": self.css_width, "height": self.css_height}
        if page is not None and not page.is_closed() and page.viewport_size != viewport:
            await page.set_viewport_size(viewport)

    def _size_new_page(self, page) -> None:
        async def size() -> None:
            try:
                await self._apply_viewport(page)
            except Exception as exc:  # the page can close before it is sized; observations size it again
                print(f"[openwebrl] new page viewport failed: {exc}", file=sys.stderr)

        asyncio.ensure_future(size())

    async def get_screenshot(self):
        await self._apply_viewport(self.page)
        return await super().get_screenshot()

    async def get_screen_size(self):
        await self._apply_viewport(self.page)
        return await super().get_screen_size()

    async def exit(self) -> None:
        # Disconnect Playwright without closing the shared browser; the Harbor verifier still needs its storage state after the agent process exits.
        if self.playwright is not None:
            await self.playwright.stop()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None


async def ensure_renderable_observation(
    env: CDPWebEnv,
    observation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Recover from a new chrome-error tab when WebEnv.step returns an empty observation."""
    if observation and isinstance(observation.get("screenshot"), (bytes, bytearray)):
        return observation
    if env.context is None:
        raise RuntimeError("browser observation has no screenshot and no browser context")

    candidates = [
        page
        for page in reversed(env.context.pages)
        if not page.is_closed() and not page.url.startswith("chrome-error://")
    ]
    candidates.sort(key=lambda page: not page.url.startswith(("http://localhost:", "http://127.0.0.1:")))
    errors: list[str] = []
    for page in candidates:
        try:
            env.page = page
            await page.bring_to_front()
            screenshot = await env.get_screenshot()
            if not isinstance(screenshot, (bytes, bytearray)):
                raise TypeError(f"Screenshot must be bytes, got {type(screenshot)}")
            try:
                a11ytree = await env.get_a11ytree()
            except Exception:
                a11ytree = None
            return {
                "screenshot": bytes(screenshot),
                "a11ytree": a11ytree,
                "screen_size": await env.get_screen_size(),
                "all_tab_url": await env.get_all_tab_urls(),
                "active_tab_url": await env.get_active_tab_url(),
                "page_title": await env.get_page_title(),
            }
        except Exception as exc:
            errors.append(f"{page.url}: {type(exc).__name__}: {exc}")
    raise RuntimeError(
        "browser observation has no screenshot and recovery failed: " + "; ".join(errors)
    )


class EvidenceRecorder:
    def __init__(self, agent_dir: Path, evidence_last_k: int):
        self.agent_dir = agent_dir
        self.evidence_last_k = evidence_last_k
        self.step_urls: list[dict[str, Any]] = []
        self.state_urls: list[str] = []
        self.step_results: list[list[str]] = []
        self.extracted_content: list[str] = []
        self.screenshots: list[tuple[float, bytes]] = []
        self.final_answer = ""
        self.done = False
        self.current_url = ""
        self.current_title = ""
        self.current_ts = time.time()

    def _update_state(self, observation: dict[str, Any], ts: float) -> None:
        url = observation.get("active_tab_url")
        if isinstance(url, str) and url:
            self.current_url = url
        title = observation.get("page_title")
        self.current_title = title.strip() if isinstance(title, str) else ""
        self.current_ts = ts

    def record_reset(self, observation: dict[str, Any]) -> None:
        ts = time.time()
        shot = observation.get("screenshot")
        if isinstance(shot, (bytes, bytearray)) and shot:
            self.screenshots.append((ts, bytes(shot)))
        self._update_state(observation, ts)

    def record_step(self, calls: list[ToolCall], observation: dict[str, Any]) -> None:
        results = [action_result_text(call) for call in calls if call.name != "done"]
        should_record = bool(results) or not self.state_urls or self.state_urls[-1] != self.current_url
        if should_record:
            index = len(self.step_urls)
            self.step_urls.append(
                {
                    "step": index,
                    "url": self.current_url,
                    "title": self.current_title,
                    "ts": self.current_ts,
                }
            )
            self.state_urls.append(self.current_url)
            self.step_results.append(results)
            self.extracted_content.extend(results)
        answer = done_response(calls)
        if answer is not None:
            self.final_answer = answer
            self.done = True
        ts = time.time()
        shot = observation.get("screenshot")
        if isinstance(shot, (bytes, bytearray)) and shot:
            self.screenshots.append((ts, bytes(shot)))
        self._update_state(observation, ts)

    def write(
        self,
        *,
        actual_reason: str,
        turns: list[dict[str, Any]],
        config: dict[str, Any],
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        shot_dir = self.agent_dir / "screenshots"
        shot_dir.mkdir(parents=True, exist_ok=True)
        for stale in shot_dir.glob("step_*.png"):
            stale.unlink(missing_ok=True)

        numbered = [(index, ts, png) for index, (ts, png) in enumerate(self.screenshots)]
        if self.evidence_last_k > 0:
            numbered = numbered[-self.evidence_last_k :]
        manifest: list[dict[str, Any]] = []
        for index, ts, png in numbered:
            name = f"step_{index:03d}.png"
            (shot_dir / name).write_bytes(png)
            manifest.append({"file": name, "ts": float(ts)})
        (self.agent_dir / "screenshot_manifest.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in manifest), encoding="utf-8"
        )

        verifier_reason = "agent_done" if self.done else "max_steps"
        final_answer = self.final_answer if self.done else ""
        (self.agent_dir / "final_answer.txt").write_text(final_answer, encoding="utf-8")
        (self.agent_dir / "termination.json").write_text(
            json.dumps(
                {
                    "terminated": True,
                    "termination_reason": verifier_reason,
                    "success_self_report": self.done,
                    "openwebrl_termination_reason": actual_reason,
                },
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
        history = {
            "harness": "openwebrl",
            "mode": "vision",
            "is_done": self.done,
            "termination_reason": verifier_reason,
            "openwebrl_termination_reason": actual_reason,
            "step_urls": self.step_urls,
            "extracted_content": self.extracted_content,
            "step_results": self.step_results,
            "state_urls": self.state_urls,
        }
        (self.agent_dir / "browseruse_history.json").write_text(
            json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        retained_indices = {index for index, _, _ in numbered}
        structured_turns = copy.deepcopy(turns)
        for turn in structured_turns:
            # Terminal policy failures can stop before tool parsing. Preserve a stable trajectory schema without modifying the raw response.
            turn.setdefault("tool_calls", [])
            turn.setdefault("tool_responses", [])
            for index_key, path_key in (
                ("screenshot_before_index", "screenshot_before"),
                ("screenshot_after_index", "screenshot_after"),
            ):
                index = turn.pop(index_key, None)
                if isinstance(index, int) and index in retained_indices:
                    turn[path_key] = f"screenshots/step_{index:03d}.png"
        structured_history = {
            "schema_version": 1,
            "harness": "openwebrl",
            "config": config,
            "termination_reason": actual_reason,
            "success_self_report": self.done,
            "final_answer": final_answer,
            "turns": structured_turns,
        }
        if messages is not None:
            # Text conversation with screenshot placeholders (system, then user/assistant per turn); every request can be rebuilt from it.
            structured_history["messages"] = messages
        (self.agent_dir / "openwebrl_history.json").write_text(
            json.dumps(structured_history, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        (self.agent_dir / "openwebrl_trajectory.jsonl").write_text(
            "".join(json.dumps(turn, ensure_ascii=False) + "\n" for turn in structured_turns),
            encoding="utf-8",
        )
        (self.agent_dir / "openwebrl_config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )


async def dump_browser_state(env: CDPWebEnv) -> None:
    if env.context is None:
        return
    try:
        state = await env.context.storage_state()
        (AGENT_DIR / "browser-state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        print(f"[openwebrl] browser-state dump failed: {exc}", file=sys.stderr)


async def run(instruction: str) -> int:
    policy, tools = load_resources()
    native_policy = render_native_tool_system_prompt(policy, tools)
    valid_tools = {
        tool["function"]["name"]
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict)
    }

    max_steps = env_int("OWRL_MAX_STEPS", 30)
    context_num_screenshots = env_int("OWRL_CONTEXT_NUM_SCREENSHOTS", 1)
    max_response_len = env_int("OWRL_MAX_RESPONSE_LEN", 4096)
    max_context = env_int("OWRL_MAX_CONTEXT", 32768)
    max_parse_failures = env_int("OWRL_MAX_CONSECUTIVE_PARSE_FAILURES", 3)
    request_timeout = env_float("OWRL_REQUEST_TIMEOUT", 300.0)
    evidence_last_k = env_int("OWRL_EVIDENCE_LAST_K", 0)
    require_usage = env_bool("OWRL_REQUIRE_USAGE", True)
    assistant_prefill = env_bool("OWRL_ASSISTANT_PREFILL", True)
    extra_body = request_extra_body(os.environ.get("OWRL_EXTRA_BODY_JSON", ""), assistant_prefill)
    start_url = os.environ["OWRL_START_URL"]

    config = {
        "harness": "openwebrl",
        "browser_response_format_mode": "browser_env",
        "browser_include_tool_response": 1,
        "turn_level": True,
        "max_steps": max_steps,
        "context_num_screenshots": context_num_screenshots,
        "temperature": env_float("OWRL_TEMPERATURE", 0.6),
        "top_p": env_float("OWRL_TOP_P", 0.95),
        "top_k": env_int("OWRL_TOP_K", 20),
        "max_response_len": max_response_len,
        "max_context": max_context,
        "viewport": {"width": 1280, "height": 1000, "dpr": 1},
        "coordinate_scale": 1000,
        "api_mode": os.environ.get("OWRL_API_MODE", "chat_completions"),
        "api_model": os.environ["OWRL_MODEL"],
        "prompt_serialization": "openwebrl_native",
        "user_request": os.environ.get("OWRL_USER_REQUEST_SOURCE", "instruction"),
        "assistant_prefill": VISIBLE_THINKING_PREFILL if assistant_prefill else "",
        "assistant_prefill_mode": os.environ.get("OWRL_ASSISTANT_PREFILL_MODE", "think"),
        "chat_template_source": os.environ.get("OWRL_CHAT_TEMPLATE_SOURCE", ""),
        "chat_template_sha256": os.environ.get("OWRL_CHAT_TEMPLATE_SHA256", ""),
        "api_tools_transport": False,
        "extra_body": extra_body,
        "usage_required_for_context_check": require_usage,
        "evidence_last_k": evidence_last_k,
    }
    if config["api_mode"] != "chat_completions":
        raise ValueError("exact OpenWebRL prompt serialization requires api_mode=chat_completions")
    sampling_params = {
        "temperature": config["temperature"],
        "top_p": config["top_p"],
        "top_k": config["top_k"],
        "max_new_tokens": max_response_len,
    }
    api_args = SimpleNamespace(
        policy_api_mode=config["api_mode"],
        policy_api_base=os.environ.get("OWRL_BASE_URL", ""),
        policy_api_url=os.environ.get("OWRL_API_URL", ""),
        policy_api_model=config["api_model"],
        policy_api_key_file="",
        policy_api_key_env="OWRL_API_KEY",
        policy_api_concurrency=1,
        policy_api_max_retries=env_int("OWRL_API_MAX_RETRIES", 3),
        policy_api_extra_body_json=json.dumps(extra_body),
    )

    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    recorder = EvidenceRecorder(AGENT_DIR, evidence_last_k)
    env = CDPWebEnv(
        cdp_url=os.environ.get("OWRL_CDP_URL", "http://127.0.0.1:9222"),
        width=1280,
        height=1000,
        dpr=1,
        max_retries=3,
        wait_timeout=10000,
        screenshot_timeout=30000,
        start_url=start_url,
        resize_output_coords=True,
        resize_scale=1000,
        image_patch_size=32,
        tool_list=tools,
        policy=policy,
        explicitly_allowed_ports=[],
    )
    messages: list[dict[str, Any]] = []
    images: list[str] = []
    turns: list[dict[str, Any]] = []
    actual_reason = "max_steps_exhausted"
    consecutive_parse_failures = 0
    observation: dict[str, Any] | None = None

    try:
        observation, _ = await env.reset()
        observation = await ensure_renderable_observation(env, observation)
        recorder.record_reset(observation)
        observation_text, image = render_observation(observation)
        messages = [
            {"role": "system", "content": native_policy},
            {
                "role": "user",
                "content": f"<user_request>\n{instruction}\n</user_request>\n\n{observation_text}",
            },
        ]
        images.append(image)

        for step in range(max_steps):
            turn: dict[str, Any] = {
                "turn_index": step,
                "url_before": observation.get("active_tab_url") if observation else "",
                "page_title_before": observation.get("page_title") if observation else "",
                "screenshot_before_index": len(recorder.screenshots) - 1,
            }
            try:
                request_messages, request_images = native_request(
                    messages,
                    images,
                    context_num_screenshots,
                    assistant_prefill,
                )
                result = await asyncio.wait_for(
                    run_policy_api_step(
                        api_args,
                        messages=request_messages,
                        image_data=request_images,
                        tools_info=[],
                        sampling_params=sampling_params,
                        max_images=context_num_screenshots,
                    ),
                    timeout=request_timeout,
                )
            except asyncio.TimeoutError:
                actual_reason = "policy_request_timeout"
                turn["error"] = f"policy request exceeded {request_timeout}s"
                turns.append(turn)
                break
            except Exception as exc:
                actual_reason = "policy_api_error"
                turn["error"] = f"{type(exc).__name__}: {exc}"
                turns.append(turn)
                break

            response_text = restore_visible_thinking_prefill(result.text)
            usage = response_usage(result.raw)
            prompt_tokens = prompt_tokens_from_usage(result.raw)
            turn.update(
                {
                    "response": response_text,
                    "finish_type": result.finish_type,
                    "usage": usage,
                    "prompt_tokens": prompt_tokens,
                }
            )
            messages.append({"role": "assistant", "content": response_text})

            if prompt_tokens is None and require_usage:
                actual_reason = "context_usage_unavailable"
                turn["error"] = "policy response did not report prompt/input token usage"
                turns.append(turn)
                break
            if prompt_tokens is not None and prompt_tokens > max_context:
                actual_reason = "max_context_exceeded"
                turn["error"] = f"input context {prompt_tokens} exceeds {max_context}"
                turns.append(turn)
                break
            if result.finish_type == "length":
                actual_reason = "generation_length_limit"
                turns.append(turn)
                break
            if result.finish_type == "abort":
                actual_reason = "generation_abort"
                turns.append(turn)
                break

            calls, parse_error = parse_tool_calls(response_text, valid_tools)
            turn["tool_calls"] = [
                {"name": call.name, "arguments": copy.deepcopy(call.parameters)} for call in calls
            ]
            if parse_error or not calls:
                consecutive_parse_failures += 1
                turn["parse_error"] = parse_error or "no tool calls"
                turns.append(turn)
                if consecutive_parse_failures >= max_parse_failures:
                    actual_reason = "consecutive_parse_failures"
                    break
                feedbacks = [
                    "Failed to parse tool calls from the response. Please try again with correct format."
                ]
            else:
                consecutive_parse_failures = 0
                actions = [
                    {"name": call.name, "args": call.parameters} for call in calls
                ]
                observation, _, terminated, _, info = await env.step(actions)
                observation = await ensure_renderable_observation(env, observation)
                recorder.record_step(calls, observation)
                feedbacks = [
                    truncate_feedback_text(
                        item.get("tool_response", ""),
                        DEFAULT_BROWSER_TOOL_RESPONSE_MAX_CHARS,
                    )
                    for item in info.get("tool_responses", [])
                ]
                turn["tool_responses"] = feedbacks
                turn["url_after"] = observation.get("active_tab_url")
                turn["page_title_after"] = observation.get("page_title")
                turn["screenshot_after_index"] = len(recorder.screenshots) - 1
                turns.append(turn)
                if terminated:
                    actual_reason = "task_completed"
                    break

            if observation is None:
                raise RuntimeError("observation unavailable after model turn")
            observation_text, image = render_observation(observation)
            feedback = "<tool_response>\n" + "\n".join(feedbacks) + "\n\n"
            feedback += observation_text + "\n</tool_response>"
            messages.append({"role": "user", "content": feedback})
            images.append(image)

        await dump_browser_state(env)
    except asyncio.CancelledError:
        actual_reason = "rollout_timeout"
        turns.append({"error": "overall rollout timeout"})
        raise
    except Exception as exc:
        actual_reason = "harness_error"
        turns.append({"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
        (AGENT_DIR / "harness_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print(traceback.format_exc(), file=sys.stderr)
    finally:
        recorder.write(actual_reason=actual_reason, turns=turns, config=config, messages=messages)
        try:
            await env.exit()
        except Exception as exc:
            print(f"[openwebrl] CDP disconnect failed: {exc}", file=sys.stderr)

    print(
        f"[openwebrl] done reason={actual_reason} turns={len(turns)} "
        f"answer_len={len(recorder.final_answer)} screenshots={len(recorder.screenshots)}",
        file=sys.stderr,
    )
    return 0


async def run_with_timeout(instruction: str) -> int:
    timeout = env_float("OWRL_ROLLOUT_TIMEOUT", 1500.0)
    try:
        return await asyncio.wait_for(run(instruction), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"[openwebrl] rollout exceeded {timeout}s", file=sys.stderr)
        return 0


def main() -> int:
    instruction = os.environ.get("OWRL_INSTRUCTION", "")
    instruction_file = os.environ.get("OWRL_INSTRUCTION_FILE", "")
    if not instruction and instruction_file:
        instruction = Path(instruction_file).read_text(encoding="utf-8")
    if not instruction:
        print("OWRL_INSTRUCTION or OWRL_INSTRUCTION_FILE is required", file=sys.stderr)
        return 2
    required = ("OWRL_MODEL", "OWRL_START_URL")
    missing = [name for name in required if not os.environ.get(name)]
    if not os.environ.get("OWRL_BASE_URL") and not os.environ.get("OWRL_API_URL"):
        missing.append("OWRL_BASE_URL or OWRL_API_URL")
    if missing:
        print("missing environment: " + ", ".join(missing), file=sys.stderr)
        return 2
    return asyncio.run(run_with_timeout(instruction))


if __name__ == "__main__":
    raise SystemExit(main())
