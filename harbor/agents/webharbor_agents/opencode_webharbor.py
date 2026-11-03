"""OpenCode harness agent for WebHarbor-in-Harbor tasks.

A thin fork of Harbor's built-in OpenCode agent:
  - install() verifies the pinned opencode binary baked into the image
    (1.17.7, sha-pinned at image build) instead of npm-installing one;
  - run() replaces the bare `opencode run` with the in-container wrapper
    /opt/webharbor-harness/opencode_capture.py, which streams the JSON event
    log, captures a browser screenshot after every completed tool call
    (last K retained), and extracts the final answer for the verifier;
  - a stdio playwright-mcp server ("browser") is registered automatically and
    attached to the container's shared chromium over CDP.
"""

from __future__ import annotations

import os
import shlex
from typing import Any, override

from pydantic import Field

from harbor.agents.installed.base import NonZeroAgentExitCodeError, with_prompt_template
from harbor.agents.installed.opencode import OpenCode, OpenCodeOptions
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.task.config import MCPServerConfig

PINNED_OPENCODE_VERSION = "1.17.7"
HARNESS_SCRIPT = "/opt/webharbor-harness/opencode_capture.py"

# Models on the router that accept image inputs natively. These get the
# native-vision screenshot guidance below; models outside the set are
# treated as text-only (external vision via the describe_image MCP when
# vision_enabled).
NATIVE_VISION_MODELS = {
    "o4-mini", "qwen3.6-35b-a3b", "gpt-5.6-sol", "gpt-4o", "gpt-4.1",
    "gpt-6-astra",
}


def _has_native_vision(model_name: str) -> bool:
    bare = model_name.split("/", 1)[-1].strip().lower()
    return bare in NATIVE_VISION_MODELS


class OpenCodeWebHarborOptions(OpenCodeOptions):
    last_k: int = Field(
        default=3, description="Keep the last K observation screenshots (default 3)."
    )
    capture_timeout: int = Field(
        default=20, description="Per-screenshot capture timeout seconds."
    )
    workspace: str = Field(
        default="/workspace", description="opencode working directory in the container."
    )
    timeout_sec: int = Field(
        default=1800, description="Overall opencode run timeout seconds."
    )
    vision_enabled: bool = Field(
        default=True,
        description="Register the vision describe_image MCP server so the "
        "text-only policy model can query an external vision model about "
        "screenshots (default True).",
    )
    vision_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible endpoint of the external vision model.",
    )
    vision_model: str = Field(
        default="qwen3.6-35b-a3b",
        description="External vision model name for describe_image.",
    )
    vision_api_key: str = Field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""),
        description="API key for the external vision model endpoint.",
    )


class OpenCodeWebHarbor(OpenCode):
    options_model = OpenCodeWebHarborOptions

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        # Register the shared-browser playwright-mcp server (stdio) unless the
        # task config already provides one. PLAYWRIGHT_MCP_CDP_ENDPOINT is set
        # in the exec env so it attaches to the container's chromium daemon;
        # --output-dir pins where browser_take_screenshot saves files so the
        # agent can pass the path to vision_describe_image.
        if not any(server.name == "browser" for server in self.mcp_servers):
            self.mcp_servers.append(
                MCPServerConfig(
                    name="browser",
                    transport="stdio",
                    command="playwright-mcp",
                    args=["--output-dir", "/workspace"],
                )
            )

    @staticmethod
    @override
    def name() -> str:
        return "opencode-webharbor"

    @override
    def version(self) -> str:
        return PINNED_OPENCODE_VERSION

    @override
    def _build_register_config_command(self) -> str | None:
        """Same config as the upstream agent, plus an explicit provider apiKey.

        Without a key on the provider, opencode treats the provider as
        unusable and falls back to a registry model match (e.g. an
        anthropic-protocol GLM entry), which sends Messages-API bodies to an
        OpenAI-compatible endpoint. Writing options.apiKey pins the protocol.
        """
        import json as _json
        import shlex as _shlex

        config: dict[str, Any] = {}
        if self.mcp_servers:
            mcp: dict[str, dict[str, Any]] = {}
            for server in self.mcp_servers:
                if server.transport == "stdio":
                    mcp[server.name] = {
                        "type": "local",
                        "command": [server.command] + server.args if server.command else [],
                    }
                else:
                    mcp[server.name] = {"type": "remote", "url": server.url, "oauth": False}
            config["mcp"] = mcp

        if self.model_name and "/" in self.model_name:
            provider, model_id = self.model_name.split("/", 1)
            conn = self.model_connection
            options: dict[str, Any] = {}
            base_url = conn.configured_base_url or conn.base_url or conn.env.get("OPENAI_BASE_URL")
            if base_url:
                options["baseURL"] = base_url
            api_key = conn.api_key or conn.env.get("OPENAI_API_KEY")
            if api_key:
                options["apiKey"] = api_key
            provider_config: dict[str, Any] = {"models": {model_id: {}}}
            if options:
                provider_config["options"] = options
            config["provider"] = {provider: provider_config}
            config["permission"] = {"webfetch": "deny", "websearch": "deny"}

        # vision describe_image MCP server (adapted from wildawm-evaluation):
        # gives the text-only policy model an external vision model for
        # screenshots. Enabled by default; see OpenCodeWebHarborOptions.
        agent_options: OpenCodeWebHarborOptions = self.options  # type: ignore[assignment]
        if agent_options.vision_enabled:
            config.setdefault("mcp", {})["vision"] = {
                "type": "local",
                "command": [
                    "/opt/opencode-web/bin/python",
                    "/opt/webharbor-harness/describe_image_mcp.py",
                ],
                "environment": {
                    "AWM_VISION_BASE_URL": agent_options.vision_base_url,
                    "AWM_VISION_API_KEY": agent_options.vision_api_key,
                    "AWM_VISION_MODEL": agent_options.vision_model,
                    "AWM_VISION_FALLBACK_BASE_URL": "",
                    "AWM_VISION_FALLBACK_MODEL": "",
                    "AWM_DESCRIBE_IMAGE_TIMEOUT": "60",
                    "AWM_DESCRIBE_IMAGE_RETRIES": "3",
                    "AWM_DESCRIBE_IMAGE_MAX_TOKENS": "4096",
                },
                "enabled": True,
                "timeout": 240000,
            }

        if not config:
            return None
        escaped = _shlex.quote(_json.dumps(config, indent=2))
        return f"mkdir -p ~/.config/opencode && echo {escaped} > ~/.config/opencode/opencode.json"

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        # The image ships the pinned binary; verify instead of npm-installing.
        result = await self.exec_as_agent(environment, command="opencode --version")
        observed = (result.stdout or "").strip()
        if result.return_code != 0 or observed != PINNED_OPENCODE_VERSION:
            raise RuntimeError(
                f"opencode {PINNED_OPENCODE_VERSION} must be preinstalled in the "
                f"webharbor image (found: {observed!r}, rc={result.return_code})"
            )

    @override
    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        options: OpenCodeWebHarborOptions = self.options  # type: ignore[assignment]
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        # Same config/skills registration path as the upstream agent.
        env = dict(self.model_connection.env)
        env["OPENCODE_FAKE_VCS"] = "git"
        env["XDG_DATA_HOME"] = (
            self.environment_logs_dir / "opencode" / "xdg-data"
        ).as_posix()
        env["XDG_STATE_HOME"] = (
            self.environment_logs_dir / "opencode" / "xdg-state"
        ).as_posix()

        skills_command = self._build_register_skills_command()
        if skills_command:
            await self.exec_as_agent(environment, command=skills_command, env=env)

        harness_probe = await self.exec_as_agent(
            environment,
            command=(
                "test -r /opt/webharbor-harness/describe_image_mcp.py && "
                "test -r /opt/webharbor-harness/opencode_capture.py"
            ),
            env=env,
        )
        if harness_probe.return_code != 0:
            raise RuntimeError(
                "OpenCode WebHarbor harness files are missing from the task image; "
                "rebuild the shared base image with image/build_harness_base.sh"
            )

        mcp_command = self._build_register_config_command()
        if mcp_command:
            await self.exec_as_agent(environment, command=mcp_command, env=env)

        # Vision guidance: a native-vision model is told it can Read the
        # per-step screenshots; a text-only model is told how to call the
        # external vision MCP.
        if _has_native_vision(self.model_name):
            instruction = (
                instruction
                + "\n\nTool guidance: you have native image input. The harness "
                "saves a screenshot after every completed browser tool call "
                "to /logs/agent/screenshots/step_<N>.png (the file list is in "
                "/logs/agent/screenshot_manifest.jsonl). You can Read any of "
                "these PNG files to view the rendered page (colors, images, "
                "layout, text rendered as graphics)."
            )
        elif options.vision_enabled:
            instruction = (
                instruction
                + "\n\nTool guidance: you are a text-only agent, but an external "
                "vision model is available through the vision_describe_image "
                "tool. To inspect a page visually, take a screenshot with the "
                "browser tool browser_take_screenshot (it saves the file and "
                "returns the path), then call vision_describe_image with that "
                "absolute path and a focused question about what you need to "
                "see (colors, images, layout, text rendered as graphics)."
            )
        import re

        start_url_match = re.search(r"https?://localhost:\d+/", instruction)
        start_url = start_url_match.group(0) if start_url_match else ""
        wrapper_env = {
            "WHB_INSTRUCTION": instruction,
            "AWMEVAL_START_URL": start_url,
            "AWMEVAL_CDP_URL": os.environ.get("WEBHARBOR_CDP_URL", "http://127.0.0.1:9222"),
            "WHB_OUTPUT_FILE": (
                self.environment_logs_dir / self._OUTPUT_FILENAME
            ).as_posix(),
            "WHB_MODEL": self.model_name,
            "WHB_LAST_K": str(max(1, options.last_k)),
            "WHB_CAPTURE_TIMEOUT": str(options.capture_timeout),
            "WHB_WORKSPACE": options.workspace,
            "WHB_AGENT_DIR": self.environment_logs_dir.as_posix(),
            "PLAYWRIGHT_MCP_CDP_ENDPOINT": os.environ.get(
                "WEBHARBOR_CDP_URL", "http://127.0.0.1:9222"
            ),
            "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers",
            "XDG_DATA_HOME": (self.environment_logs_dir / "opencode" / "xdg-data").as_posix(),
            "XDG_STATE_HOME": (self.environment_logs_dir / "opencode" / "xdg-state").as_posix(),
            "BROWSER_USE_CONFIG_DIR": "/state/browser-use/config",
            # Keep every per-step screenshot: the WebHarbor verifiers hash all
            # referenced frames for the shot_frames_distinct gate. The old
            # default of 3 kept only the last three images and made that gate
            # fail even for correct runs.
            "WHB_LAST_K": "999",
            "PATH": "/opt/guards/bin:/opt/opencode-web/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        }
        command = f"/usr/local/bin/python3 {shlex.quote(HARNESS_SCRIPT)}"
        await self.exec_as_agent(
            environment,
            command=command,
            env={**env, **wrapper_env},
            timeout_sec=options.timeout_sec,
        )

        if messages := self._error_messages():
            raise NonZeroAgentExitCodeError(
                "OpenCode emitted error event(s): " + "; ".join(messages[:3])
            )
