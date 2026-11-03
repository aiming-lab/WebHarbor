"""Browser-use SDK harness agent for WebHarbor-in-Harbor tasks.

Executes /opt/webharbor-harness/browseruse_gui.py inside the task container
as the agent user. Modes:
  vision (default): the policy model receives page screenshots natively.
  text:             the policy model receives HTML/accessibility-tree state.
Both keep the last ``last_k`` step screenshots (default 3) as verifier
evidence.
"""

from __future__ import annotations

import os
import shlex
from typing import Any, override

from pydantic import Field

from harbor.agents.base import BaseAgent
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.agents.options import AgentOptions
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class BrowserUseOptions(AgentOptions):
    """User-facing kwargs (``--ak``)."""

    mode: str = Field(
        default="vision", description="Observation mode: vision | text."
    )
    last_k: int = Field(
        default=3, description="Keep the last K step screenshots (default 3)."
    )
    max_steps: int = Field(
        default=50, description="browser-use step budget."
    )
    step_timeout: int = Field(
        default=180, description="Per-step timeout seconds."
    )
    base_url: str | None = Field(
        default=None,
        description="OpenAI-compatible endpoint. Defaults to OPENAI_BASE_URL.",
    )
    api_key: str | None = Field(
        default=None, description="Endpoint API key. Defaults to OPENAI_API_KEY."
    )
    vision_enabled: bool = Field(
        default=False,
        description="Register the describe_page action so the text-only policy "
        "model can ask an external vision model about the current page "
        "(default False).",
    )
    vision_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible endpoint of the external vision model.",
    )
    vision_model: str = Field(
        default="qwen3.6-35b-a3b",
        description="External vision model name for describe_page.",
    )
    vision_api_key: str = Field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""),
        description="API key for the external vision model endpoint.",
    )


class BrowserUseWebHarbor(BaseAgent):
    options_model = BrowserUseOptions
    # Pass host OPENAI_* connection envs straight through to the harness exec.
    MODEL_CONNECTION = ModelConnectionSpec(passthrough=True)
    HARNESS_COMMAND = "/opt/opencode-web/bin/python /opt/webharbor-harness/browseruse_gui.py"

    @staticmethod
    @override
    def name() -> str:
        return "browseruse-webharbor"

    @override
    def version(self) -> str:
        return "0.1.0"

    def _endpoint(self) -> tuple[str, str]:
        options: BrowserUseOptions = self.options  # type: ignore[assignment]
        conn = self.model_connection
        base_url = options.base_url or conn.env.get("OPENAI_BASE_URL") or conn.base_url or ""
        api_key = options.api_key or conn.env.get("OPENAI_API_KEY") or conn.api_key or ""
        if not base_url or not api_key:
            raise ValueError(
                "browseruse-webharbor needs an OpenAI-compatible endpoint: pass "
                "--ak base_url=... --ak api_key=... or export OPENAI_BASE_URL / OPENAI_API_KEY"
            )
        return base_url, api_key

    def _bare_model(self) -> str:
        if not self.model_name:
            raise ValueError("browseruse-webharbor requires --model")
        if "/" in self.model_name:
            return self.model_name.split("/", 1)[1]
        return self.model_name

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        probe = await environment.exec(
            command=(
                "test -r /opt/webharbor-harness/browseruse_gui.py && "
                "test -r /opt/webharbor-harness/describe_image_mcp.py"
            ),
            timeout_sec=10,
        )
        if probe.return_code != 0:
            raise RuntimeError(
                "browseruse harness files are missing from the task image; rebuild "
                "the shared base image with image/build_harness_base.sh"
            )

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        options: BrowserUseOptions = self.options  # type: ignore[assignment]
        if options.mode not in ("vision", "text"):
            raise ValueError(f"mode must be vision|text, got {options.mode!r}")
        base_url, api_key = self._endpoint()

        import re

        start_url_match = re.search(r"https?://localhost:\d+/", instruction)
        if not start_url_match:
            raise ValueError(
                "instruction must contain the site URL (http://localhost:<port>/); "
                "the adapter writes it into instruction.md"
            )
        force_structured = os.environ.get("WEBHARBOR_FORCE_STRUCTURED_OUTPUT", "1")
        env: dict[str, str] = {
            "WHB_START_URL": start_url_match.group(0),
            "WHB_FORCE_STRUCTURED_OUTPUT": force_structured,
            "WHB_MODEL": self._bare_model(),
            "WHB_BASE_URL": base_url,
            "WHB_API_KEY": api_key,
            "WHB_MODE": options.mode,
            "WHB_LAST_K": str(max(1, options.last_k)),
            "WHB_MAX_STEPS": str(options.max_steps),
            "WHB_TIMEOUT": str(options.step_timeout),
            "WHB_CDP_URL": os.environ.get("WEBHARBOR_CDP_URL", "http://127.0.0.1:9222"),
            "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers",
            "BROWSER_USE_CONFIG_DIR": "/state/browser-use/config",
        }
        if options.vision_enabled:
            env["WHB_DESCRIBE"] = "1"
            env["WHB_VISION_BASE_URL"] = options.vision_base_url
            env["WHB_VISION_MODEL"] = options.vision_model
            env["WHB_VISION_API_KEY"] = options.vision_api_key
        command = f"{self.HARNESS_COMMAND} {shlex.quote(instruction)}"
        timeout = options.max_steps * options.step_timeout + 600
        result = await environment.exec(
            command=command, env=env, timeout_sec=timeout, cwd="/workspace"
        )
        if result.return_code != 0:
            output_tail = ((result.stdout or "") + (result.stderr or ""))[-2500:]
            raise RuntimeError(
                f"browseruse harness exited {result.return_code}.\n"
                f"env keys: {sorted(env)}\n"
                f"--- output tail ---\n{output_tail}"
            )
