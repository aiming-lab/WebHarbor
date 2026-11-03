"""Exact OpenWebRL browser_env prompt serialization over SGLang Chat Completions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

IMAGE_PLACEHOLDER = "<|vision_start|><|image_pad|><|vision_end|>"
SCREENSHOT_PLACEHOLDER = "screenshot:\n" + IMAGE_PLACEHOLDER
VISIBLE_THINKING_PREFILL = "<think>\n"


def checkpoint_chat_template(source: str) -> tuple[str, str]:
    """Return (chat template, location) from a checkpoint dir or the local Hugging Face cache snapshot of a model id."""
    path = Path(source).expanduser()
    if not path.is_dir():
        cache = Path(
            os.environ.get("HF_HUB_CACHE")
            or Path(os.environ.get("HF_HOME", "~/.cache/huggingface")).expanduser() / "hub"
        ).expanduser()
        snapshots = sorted(
            cache.glob(f"models--{source.replace('/', '--')}/snapshots/*"),
            key=lambda item: item.stat().st_mtime,
        )
        if not snapshots:
            raise FileNotFoundError(f"no checkpoint dir or Hugging Face cache snapshot for {source!r}")
        path = snapshots[-1]
    if (path / "chat_template.jinja").is_file():
        return (path / "chat_template.jinja").read_text(encoding="utf-8"), str(path / "chat_template.jinja")
    for name in ("chat_template.json", "tokenizer_config.json"):
        if (path / name).is_file():
            template = json.loads((path / name).read_text(encoding="utf-8")).get("chat_template")
            if isinstance(template, str):
                return template, str(path / name)
    raise FileNotFoundError(f"no chat template under {path}")


def generation_prompt_ends_with_think(chat_template: str) -> bool:
    """Render the template's generation prompt the way Hugging Face does and test whether it already opens <think>."""
    from jinja2.exceptions import TemplateError
    from jinja2.ext import loopcontrols
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    def raise_exception(message: str):
        raise TemplateError(message)

    environment = ImmutableSandboxedEnvironment(
        trim_blocks=True, lstrip_blocks=True, extensions=[loopcontrols]
    )
    environment.globals["raise_exception"] = raise_exception
    rendered = environment.from_string(chat_template).render(
        messages=[{"role": "user", "content": "probe"}],
        add_generation_prompt=True,
        tools=None,
    )
    return rendered.rstrip().endswith("<think>")


def apply_visible_thinking_prefill(prompt_text: str) -> str:
    """OpenWebRL's ensure_prompt_ends_with_visible_thinking_tag for browser_env: keep a trailing <think>, else append one."""
    stripped = prompt_text.rstrip()
    if stripped.endswith("<think>"):
        return stripped + "\n"
    return f"{stripped}\n{VISIBLE_THINKING_PREFILL}"


def render_native_tool_system_prompt(policy: str, tools: list[dict[str, Any]]) -> str:
    """Inline the checkpoint's wrapped tool block for exact OpenWebRL tokenization."""
    tool_block = (
        "# Tools\n\n"
        "You may call one or more functions to assist with the user query.\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n"
        "<tools>"
    )
    tool_block += "".join("\n" + json.dumps(tool) for tool in tools)
    tool_block += (
        "\n</tools>\n\n"
        "For each function call, return a json object with function name and arguments within "
        "<tool_call></tool_call> XML tags:\n"
        "<tool_call>\n"
        '{"name": <function-name>, "arguments": <args-json-object>}\n'
        "</tool_call>"
    )
    return policy + "\n\n" + tool_block


def prepare_native_chat_context(
    messages: list[dict[str, Any]],
    images: list[str],
    max_screenshots: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Match OpenWebRL turn-level screenshot filtering and assistant prefill."""
    screenshot_indices = [
        index
        for index, message in enumerate(messages)
        if message.get("role") == "user"
        and isinstance(message.get("content"), str)
        and SCREENSHOT_PLACEHOLDER in message["content"]
    ]
    keep_indices = set(screenshot_indices[-max_screenshots:])
    filtered: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        copied = dict(message)
        if index in screenshot_indices and index not in keep_indices:
            copied["content"] = copied["content"].replace(SCREENSHOT_PLACEHOLDER, "")
        filtered.append(copied)

    remaining_images = sum(
        str(message.get("content", "")).count(IMAGE_PLACEHOLDER)
        for message in filtered
    )
    if remaining_images > len(images):
        raise ValueError(
            f"prompt has {remaining_images} screenshot placeholders but only {len(images)} images"
        )
    selected_images = images[-remaining_images:] if remaining_images else []
    filtered.append({"role": "assistant", "content": VISIBLE_THINKING_PREFILL})
    return filtered, selected_images


def native_chat_extra_body(raw: str) -> str:
    """Set the SGLang fields required by OpenWebRL's native serialized prompt."""
    body = json.loads(raw) if raw else {}
    if not isinstance(body, dict):
        raise ValueError("OWRL_EXTRA_BODY_JSON must be a JSON object")
    required = {
        "continue_final_message": True,
        "skip_special_tokens": False,
    }
    for key, value in required.items():
        if key in body and body[key] != value:
            raise ValueError(f"OWRL_EXTRA_BODY_JSON {key} must be {value!r}")
        body[key] = value
    template_kwargs = body.get("chat_template_kwargs") or {}
    if not isinstance(template_kwargs, dict):
        raise ValueError("OWRL_EXTRA_BODY_JSON chat_template_kwargs must be an object")
    if "enable_thinking" in template_kwargs and template_kwargs["enable_thinking"] is not False:
        raise ValueError("OWRL_EXTRA_BODY_JSON chat_template_kwargs.enable_thinking must be false")
    template_kwargs["enable_thinking"] = False
    body["chat_template_kwargs"] = template_kwargs
    return json.dumps(body)


def restore_visible_thinking_prefill(response: str) -> str:
    if response.lstrip().startswith("<think>"):
        return response
    return VISIBLE_THINKING_PREFILL + response
