"""OpenAI-compatible policy-model backends for browser evaluation.

Supports Chat Completions (``/v1/chat/completions``) and Responses
(``/v1/responses``). The browser harness continues to use its XML tool-call
format internally; native API function calls are converted to that format so
all existing parsing, environment actions, trajectory saving and judges remain
unchanged.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx


_IMAGE_PLACEHOLDER = "<|vision_start|><|image_pad|><|vision_end|>"
_MODE_ALIASES = {
    "chat-completion": "chat_completions",
    "chat-completions": "chat_completions",
    "chat_completion": "chat_completions",
    "chat_completions": "chat_completions",
    "responses": "responses",
    "response": "responses",
    "sglang": "sglang",
}
_CLIENTS: dict[tuple[str, int], httpx.AsyncClient] = {}


@dataclass
class PolicyAPIResult:
    text: str
    finish_type: str
    raw: dict[str, Any]


def normalize_policy_api_mode(value: str) -> str:
    normalized = _MODE_ALIASES.get((value or "sglang").strip().lower())
    if normalized is None:
        raise ValueError(
            f"Unknown policy API mode {value!r}; use sglang, chat_completions, or responses."
        )
    return normalized


def resolve_policy_api_url(args: Any) -> str:
    explicit = (getattr(args, "policy_api_url", "") or "").strip()
    if explicit:
        return explicit

    base = (getattr(args, "policy_api_base", "") or "").strip().rstrip("/")
    if not base:
        raise ValueError("External policy API mode requires --policy-api-base or --policy-api-url.")

    mode = normalize_policy_api_mode(getattr(args, "policy_api_mode", "sglang"))
    route = "/chat/completions" if mode == "chat_completions" else "/responses"
    if base.endswith(route):
        return base
    return base + route


def resolve_policy_api_key(args: Any) -> str:
    key_file = (getattr(args, "policy_api_key_file", "") or "").strip()
    if key_file:
        with open(os.path.expanduser(key_file)) as f:
            return f.read().strip()

    key_env = (getattr(args, "policy_api_key_env", "") or "").strip()
    return os.environ.get(key_env, "").strip() if key_env else ""


def _json_object(value: str, label: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be a JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object, got {type(parsed).__name__}.")
    return parsed


def _tool_call_xml(name: str, arguments: Any) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            pass
    return "<tool_call>\n" + json.dumps(
        {"name": name, "arguments": arguments}, ensure_ascii=False
    ) + "\n</tool_call>"


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for part in content:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "".join(chunks)


def _native_tool_calls_to_xml(tool_calls: Any) -> list[str]:
    if not isinstance(tool_calls, list):
        return []
    calls: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        name = function.get("name")
        if not name:
            continue
        calls.append(_tool_call_xml(name, function.get("arguments", {})))
    return calls


def _message_with_images(
    message: dict[str, Any],
    occurrence_start: int,
    keep_occurrences: set[int],
    occurrence_images: dict[int, str],
    mode: str,
) -> tuple[dict[str, Any], int]:
    role = message.get("role", "user")
    content = message.get("content", "")
    if not isinstance(content, str):
        content = _text_from_content(content)

    if role == "tool":
        # Canonical browser_env history represents environment feedback as a
        # user-side <tool_response> block and does not retain OpenAI call IDs.
        content = f"<tool_response>\n{content}\n</tool_response>"
        role = "user"

    pieces = content.split(_IMAGE_PLACEHOLDER)
    occurrence = occurrence_start
    parts: list[dict[str, Any]] = []
    for index, text in enumerate(pieces):
        if text:
            part_type = "text" if mode == "chat_completions" else "input_text"
            parts.append({"type": part_type, "text": text})
        if index == len(pieces) - 1:
            continue
        if occurrence in keep_occurrences and occurrence in occurrence_images:
            image_url = occurrence_images[occurrence]
            if mode == "chat_completions":
                parts.append({"type": "image_url", "image_url": {"url": image_url}})
            else:
                parts.append({"type": "input_image", "image_url": image_url})
        occurrence += 1

    output = {"role": role}
    if mode == "chat_completions" and not any(
        p.get("type") == "image_url" for p in parts
    ):
        output["content"] = "".join(p.get("text", "") for p in parts)
    else:
        output["content"] = parts or [
            {"type": "text" if mode == "chat_completions" else "input_text", "text": ""}
        ]
    return output, occurrence


def build_policy_messages(
    messages: list[dict[str, Any]],
    image_data: list[str],
    max_images: int,
    mode: str,
) -> tuple[list[dict[str, Any]], str]:
    """Convert harness messages to OpenAI multimodal messages.

    Tool-result messages are represented as user text because the harness uses
    textual XML tool calls internally and does not retain OpenAI tool_call_ids.
    Only the latest ``max_images`` screenshot placeholders receive image data;
    older placeholders are removed while their observation text remains.
    """
    total_occurrences = sum(
        str(message.get("content", "")).count(_IMAGE_PLACEHOLDER)
        for message in messages
    )
    usable = min(max(max_images, 0), len(image_data), total_occurrences)
    keep_occurrences = set(range(total_occurrences - usable, total_occurrences))
    image_offset = max(total_occurrences - len(image_data), 0)
    occurrence_images = {
        occurrence: image_data[occurrence - image_offset]
        for occurrence in range(image_offset, total_occurrences)
        if occurrence - image_offset < len(image_data)
    }

    converted: list[dict[str, Any]] = []
    instructions: list[str] = []
    occurrence = 0
    for message in messages:
        if mode == "responses" and message.get("role") == "system":
            instructions.append(_text_from_content(message.get("content", "")))
            occurrence += str(message.get("content", "")).count(_IMAGE_PLACEHOLDER)
            continue
        converted_message, occurrence = _message_with_images(
            message,
            occurrence,
            keep_occurrences,
            occurrence_images,
            mode,
        )
        converted.append(converted_message)
    return converted, "\n\n".join(x for x in instructions if x)


def _responses_tools(tools_info: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools_info or []:
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict) or not function.get("name"):
            continue
        converted.append(
            {
                "type": "function",
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return converted


def _sampling_payload(sampling_params: dict[str, Any], mode: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if sampling_params.get("temperature") is not None:
        payload["temperature"] = sampling_params["temperature"]
    if sampling_params.get("top_p") is not None:
        payload["top_p"] = sampling_params["top_p"]
    # top_k is an OpenAI-compatible server extension (SGLang/vLLM), required
    # by the unified benchmark-eval decoding standard.
    if sampling_params.get("top_k") is not None:
        payload["top_k"] = sampling_params["top_k"]
    max_tokens = sampling_params.get("max_new_tokens")
    if max_tokens is not None:
        payload["max_tokens" if mode == "chat_completions" else "max_output_tokens"] = max_tokens
    if mode == "chat_completions":
        if sampling_params.get("presence_penalty") is not None:
            payload["presence_penalty"] = sampling_params["presence_penalty"]
        if sampling_params.get("repetition_penalty") not in (None, 1.0):
            # Non-standard but accepted by several OpenAI-compatible servers.
            payload["repetition_penalty"] = sampling_params["repetition_penalty"]
        if sampling_params.get("stop"):
            payload["stop"] = sampling_params["stop"]
    return payload


def _extract_chat_result(data: dict[str, Any]) -> PolicyAPIResult:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"Chat Completions response has no choices: {str(data)[:500]}")
    choice = choices[0]
    message = choice.get("message") or {}
    text = _text_from_content(message.get("content"))
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip() and "<think>" not in text:
        text = f"<think>\n{reasoning.strip()}\n</think>\n{text}"
    calls = _native_tool_calls_to_xml(message.get("tool_calls"))
    if calls:
        text = (text.rstrip() + "\n" if text.strip() else "") + "\n".join(calls)
    if not text.strip():
        raise ValueError(f"Chat Completions response has no text or tool calls: {str(data)[:500]}")

    finish_reason = choice.get("finish_reason") or "stop"
    finish_type = "length" if finish_reason == "length" else (
        "abort" if finish_reason in {"content_filter", "error"} else "stop"
    )
    return PolicyAPIResult(text=text, finish_type=finish_type, raw=data)


def _extract_responses_result(data: dict[str, Any]) -> PolicyAPIResult:
    text_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    call_chunks: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "function_call" and item.get("name"):
                call_chunks.append(_tool_call_xml(item["name"], item.get("arguments", {})))
            elif item_type == "reasoning":
                summary = item.get("summary") or []
                if isinstance(summary, list):
                    reasoning_chunks.extend(
                        str(part.get("text", "")) for part in summary if isinstance(part, dict)
                    )
            elif item_type == "message":
                content = item.get("content") or []
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                            text_chunks.append(str(part.get("text", "")))

    if not text_chunks and isinstance(data.get("output_text"), str):
        text_chunks.append(data["output_text"])
    text = "".join(text_chunks)
    if reasoning_chunks and "<think>" not in text:
        reasoning = "\n".join(x for x in reasoning_chunks if x)
        if reasoning:
            text = f"<think>\n{reasoning}\n</think>\n{text}"
    if call_chunks:
        text = (text.rstrip() + "\n" if text.strip() else "") + "\n".join(call_chunks)
    if not text.strip():
        raise ValueError(f"Responses API response has no text or function calls: {str(data)[:500]}")

    status = data.get("status") or "completed"
    incomplete_reason = (data.get("incomplete_details") or {}).get("reason")
    if status == "incomplete" and incomplete_reason == "max_output_tokens":
        finish_type = "length"
    elif status in {"failed", "cancelled", "incomplete"}:
        finish_type = "abort"
    else:
        finish_type = "stop"
    return PolicyAPIResult(text=text, finish_type=finish_type, raw=data)


async def run_policy_api_step(
    args: Any,
    messages: list[dict[str, Any]],
    image_data: list[str],
    tools_info: list[dict[str, Any]],
    sampling_params: dict[str, Any],
    max_images: int,
) -> PolicyAPIResult:
    mode = normalize_policy_api_mode(getattr(args, "policy_api_mode", "sglang"))
    if mode == "sglang":
        raise ValueError("run_policy_api_step is only for external OpenAI-compatible modes.")

    url = resolve_policy_api_url(args)
    model = (getattr(args, "policy_api_model", "") or "").strip()
    if not model:
        raise ValueError("External policy API mode requires --policy-api-model.")

    api_messages, instructions = build_policy_messages(messages, image_data, max_images, mode)
    payload: dict[str, Any] = {"model": model}
    payload.update(_sampling_payload(sampling_params, mode))
    if mode == "chat_completions":
        payload["messages"] = api_messages
        if tools_info:
            payload["tools"] = tools_info
            payload["tool_choice"] = "auto"
    else:
        payload["input"] = api_messages
        if instructions:
            payload["instructions"] = instructions
        response_tools = _responses_tools(tools_info)
        if response_tools:
            payload["tools"] = response_tools
            payload["tool_choice"] = "auto"

    payload.update(
        _json_object(
            getattr(args, "policy_api_extra_body_json", "") or "",
            "--policy-api-extra-body-json",
        )
    )

    api_key = resolve_policy_api_key(args)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    concurrency = max(int(getattr(args, "policy_api_concurrency", 64) or 64), 1)
    client_key = (url, concurrency)
    client = _CLIENTS.get(client_key)
    if client is None:
        client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
            timeout=httpx.Timeout(None),
            trust_env=False,
        )
        _CLIENTS[client_key] = client

    max_retries = max(int(getattr(args, "policy_api_max_retries", 3) or 3), 1)
    for attempt in range(max_retries):
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 429 or response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"Policy API transient HTTP {response.status_code}: {response.text[:1000]}",
                    request=response.request,
                    response=response,
                )
            if response.status_code >= 400:
                raise ValueError(
                    f"Policy API HTTP {response.status_code} at {url}: {response.text[:2000]}"
                )
            data = response.json()
            return _extract_chat_result(data) if mode == "chat_completions" else _extract_responses_result(data)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            if attempt >= max_retries - 1:
                raise RuntimeError(
                    f"Policy API request failed after {max_retries} attempts ({url}): {exc}"
                ) from exc
            await asyncio.sleep(min(2 ** attempt, 8))

    raise RuntimeError("Policy API retry loop exited unexpectedly.")
