"""OpenWebRL browser harness for WebHarbor-in-Harbor evaluation.

The in-container runner uses the exact OpenWebRL browser_env system prompt, tool schema and Playwright coordinate-action semantics of OpenWebRL (vendored in harness/openwebrl_runtime). Defaults are the unified RL-evaluation decoding (turn-level, latest 1 screenshot, temperature 0.6, top-p 0.95, top-k 20, maximum response 4096 tokens, maximum context 32768 tokens) with 50 browser steps, the BROWSER_MAX_STEPS of the WebHarbor RL run, and a 2500 s rollout cap (50 s per step).

Defaults also follow WebHarbor RL training: the <user_request> is the task description that WebHarbor RL training uses as the intent (not the Harbor instruction.md with its local-mirror and answer paragraphs), and the assistant "<think>\\n" prefill is sent only when the checkpoint chat template's generation prompt does not already end with <think> (OpenWebRL ensure_prompt_ends_with_visible_thinking_tag; OpenWebRL-4B-SFT and the WebHarbor RL checkpoints already end with it).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import shlex
import sys
import tomllib
from pathlib import Path
from typing import Literal, override

from pydantic import Field

from harbor.agents.base import BaseAgent
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.agents.options import AgentOptions
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

HARNESS_DIR = Path(__file__).resolve().parents[2] / "harness"
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

from openwebrl_runtime.prompt_adapter import (  # noqa: E402
    checkpoint_chat_template,
    generation_prompt_ends_with_think,
)


def task_description(task_dir: Path) -> str:
    """The RL intent of a task: task.toml [task].description, else instruction.md, as in WebHarbor RL training."""
    data = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    description = (data.get("task") or {}).get("description") or ""
    if not description:
        description = (task_dir / "instruction.md").read_text(encoding="utf-8").strip()
    return description


@functools.lru_cache(maxsize=None)
def template_prefill(source: str) -> tuple[bool, str, str]:
    """(send the <think> prefill, template location, template sha256) for a checkpoint dir or model id."""
    template, location = checkpoint_chat_template(source)
    return (
        not generation_prompt_ends_with_think(template),
        location,
        hashlib.sha256(template.encode("utf-8")).hexdigest(),
    )


class OpenWebRLOptions(AgentOptions):
    api_mode: str = Field(
        default="chat_completions",
        description="Policy endpoint protocol. Exact OpenWebRL serialization requires chat_completions.",
    )
    user_request: Literal["task_description", "instruction"] = Field(
        default="task_description",
        description="Text inside <user_request>: task_description = task.toml [task].description, the WebHarbor RL training intent; instruction = the Harbor instruction.md.",
    )
    assistant_prefill: Literal["auto", "think", "none"] = Field(
        default="auto",
        description="Assistant '<think>\\n' prefill: auto sends it only when the checkpoint chat template's generation prompt lacks <think>.",
    )
    checkpoint: str | None = Field(
        default=None,
        description="Checkpoint dir or Hugging Face model id whose chat template decides assistant_prefill=auto. Defaults to the policy model name.",
    )
    api_url: str | None = Field(
        default=None,
        description="Exact policy endpoint URL; overrides base_url.",
    )
    base_url: str | None = Field(
        default=None,
        description="OpenAI-compatible base URL, usually ending in /v1.",
    )
    api_model: str | None = Field(
        default=None,
        description="Model name sent to the policy endpoint. Defaults to --model without provider prefix.",
    )
    api_key: str | None = Field(
        default=None,
        description="Policy endpoint API key. Defaults to OPENAI_API_KEY.",
    )
    extra_body_json: str = Field(
        default="",
        description="JSON object merged into each policy request.",
    )
    max_steps: int = Field(default=50, description="Maximum browser turns (WebHarbor RL BROWSER_MAX_STEPS).")
    context_num_screenshots: int = Field(
        default=1,
        description="Number of latest screenshots included in model context.",
    )
    temperature: float = Field(default=0.6)
    top_p: float = Field(default=0.95)
    top_k: int = Field(default=20)
    max_response_len: int = Field(default=4096, description="Maximum response tokens per turn.")
    max_context: int = Field(default=32768, description="Maximum input context tokens.")
    max_consecutive_parse_failures: int = Field(default=3)
    request_timeout: int = Field(default=300, description="Policy request timeout seconds.")
    api_max_retries: int = Field(default=3)
    rollout_timeout: int = Field(default=2500, description="Overall harness timeout seconds (50 s per step).")
    evidence_last_k: int = Field(
        default=0,
        description="Verifier screenshots to retain; 0 keeps all, matching WebHarbor RL.",
    )
    require_usage: bool = Field(
        default=True,
        description="Abort if the endpoint omits prompt/input token usage needed for exact context enforcement.",
    )
    cdp_url: str = Field(default="http://127.0.0.1:9222")


class OpenWebRLWebHarbor(BaseAgent):
    options_model = OpenWebRLOptions
    MODEL_CONNECTION = ModelConnectionSpec(passthrough=True)

    @staticmethod
    @override
    def name() -> str:
        return "openwebrl"

    @override
    def version(self) -> str:
        return "0.1.0"

    def _bare_model(self) -> str:
        if not self.model_name:
            raise ValueError("openwebrl requires --model")
        return self.model_name.split("/", 1)[-1]

    def _endpoint(self) -> tuple[str, str, str]:
        options: OpenWebRLOptions = self.options  # type: ignore[assignment]
        connection = self.model_connection
        base_url = (
            options.base_url
            or connection.env.get("OPENAI_BASE_URL")
            or connection.base_url
            or ""
        )
        api_url = options.api_url or ""
        api_key = (
            options.api_key
            or connection.env.get("OPENAI_API_KEY")
            or connection.api_key
            or ""
        )
        if not base_url and not api_url:
            raise ValueError(
                "openwebrl needs an OpenAI-compatible endpoint: pass --ak base_url=..., "
                "--ak api_url=..., or export OPENAI_BASE_URL"
            )
        return base_url, api_url, api_key

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec(
            command=(
                "set -eu; "
                "test -r /opt/webharbor-harness/openwebrl_eval.py; "
                "test -r /opt/webharbor-harness/openwebrl_runtime/system_prompt_browser_env.md; "
                "test -r /opt/webharbor-harness/openwebrl_runtime/tool_list.json; "
                "PYTHONDONTWRITEBYTECODE=1 /opt/opencode-web/bin/python -c "
                "'import httpx, playwright; "
                "import sys; sys.path.insert(0, \"/opt/webharbor-harness\"); "
                "import openwebrl_runtime.web_env, openwebrl_runtime.policy_api'"
            ),
            timeout_sec=60,
        )
        if result.return_code != 0:
            detail = ((result.stdout or "") + (result.stderr or ""))[-2000:]
            raise RuntimeError(
                "openwebrl is not installed in the task image; rebuild the shared "
                "WebHarbor base image with image/build_harness_base.sh and rebuild "
                f"the per-site image. Probe output:\n{detail}"
            )

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        options: OpenWebRLOptions = self.options  # type: ignore[assignment]
        if options.api_mode != "chat_completions":
            raise ValueError(
                f"exact OpenWebRL serialization requires api_mode='chat_completions', got {options.api_mode!r}"
            )
        if options.max_steps <= 0 or options.context_num_screenshots <= 0:
            raise ValueError("max_steps and context_num_screenshots must be positive")
        if options.max_response_len <= 0 or options.max_context <= 0:
            raise ValueError("max_response_len and max_context must be positive")
        if options.extra_body_json:
            parsed = json.loads(options.extra_body_json)
            if not isinstance(parsed, dict):
                raise ValueError("extra_body_json must be a JSON object")

        start_url_match = re.search(r"https?://localhost:\d+/", instruction)
        if not start_url_match:
            raise ValueError(
                "instruction must contain the local site URL http://localhost:<port>/"
            )
        base_url, api_url, api_key = self._endpoint()
        if options.user_request == "task_description":
            user_request = task_description(Path(environment.environment_dir).parent)
        else:
            user_request = instruction
        api_model = options.api_model or self._bare_model()
        template_source = template_sha256 = ""
        if options.assistant_prefill == "auto":
            assistant_prefill, template_source, template_sha256 = template_prefill(
                options.checkpoint or api_model
            )
        else:
            assistant_prefill = options.assistant_prefill == "think"

        env = {
            "OWRL_INSTRUCTION": user_request,
            "OWRL_USER_REQUEST_SOURCE": options.user_request,
            "OWRL_ASSISTANT_PREFILL": "1" if assistant_prefill else "0",
            "OWRL_ASSISTANT_PREFILL_MODE": options.assistant_prefill,
            "OWRL_CHAT_TEMPLATE_SOURCE": template_source,
            "OWRL_CHAT_TEMPLATE_SHA256": template_sha256,
            "OWRL_MODEL": api_model,
            "OWRL_API_MODE": options.api_mode,
            "OWRL_BASE_URL": base_url,
            "OWRL_API_URL": api_url,
            "OWRL_API_KEY": api_key,
            "OWRL_EXTRA_BODY_JSON": options.extra_body_json,
            "OWRL_START_URL": start_url_match.group(0),
            "OWRL_CDP_URL": options.cdp_url,
            "OWRL_AGENT_DIR": self.environment_logs_dir.as_posix(),
            "OWRL_MAX_STEPS": str(options.max_steps),
            "OWRL_CONTEXT_NUM_SCREENSHOTS": str(options.context_num_screenshots),
            "OWRL_TEMPERATURE": str(options.temperature),
            "OWRL_TOP_P": str(options.top_p),
            "OWRL_TOP_K": str(options.top_k),
            "OWRL_MAX_RESPONSE_LEN": str(options.max_response_len),
            "OWRL_MAX_CONTEXT": str(options.max_context),
            "OWRL_MAX_CONSECUTIVE_PARSE_FAILURES": str(options.max_consecutive_parse_failures),
            "OWRL_REQUEST_TIMEOUT": str(options.request_timeout),
            "OWRL_ROLLOUT_TIMEOUT": str(options.rollout_timeout),
            "OWRL_API_MAX_RETRIES": str(options.api_max_retries),
            "OWRL_EVIDENCE_LAST_K": str(options.evidence_last_k),
            "OWRL_REQUIRE_USAGE": "1" if options.require_usage else "0",
            "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = await environment.exec(
            command=(
                "/opt/opencode-web/bin/python "
                + shlex.quote("/opt/webharbor-harness/openwebrl_eval.py")
            ),
            env=env,
            timeout_sec=options.rollout_timeout + 120,
            cwd="/workspace",
        )
        if result.return_code != 0:
            detail = ((result.stdout or "") + (result.stderr or ""))[-3000:]
            raise RuntimeError(
                f"openwebrl harness exited {result.return_code}; env keys={sorted(env)}\n{detail}"
            )
