# OpenWebRL runtime provenance

This directory vendors the OpenWebRL browser policy contract.

| Local file | Source |
| --- | --- |
| `system_prompt_browser_env.md` | `OpenWebRL/openwebrl/env/prompts/system_prompt_browser_env.md` (byte-identical) |
| `tool_list.json` | `OpenWebRL/openwebrl/env/prompts/tool_list.json` (byte-identical) |
| `web_env.py` | `OpenWebRL/openwebrl/env/web_env.py`; only package imports point at this local runtime |
| `feedback_utils.py`, `js.py`, `keyboard.py` | Matching OpenWebRL runtime helpers |
| `policy_api.py` | The OpenAI Chat Completions / Responses adapter of the OpenWebRL browser evaluation suite |

`openwebrl_eval.py` supplies the Harbor-specific integration. It attaches the vendored `WebEnv` action implementation to the task container's existing Chromium over CDP instead of launching another browser. It writes the existing WebHarbor browser evidence contract and keeps all screenshots for the verifier while only the latest screenshot enters the policy context.

The default evaluation configuration is: `browser_env`, tool responses included, turn-level, 30 steps (the in-container default; the Harbor agent passes 50, the WebHarbor RL `BROWSER_MAX_STEPS`), one context screenshot, temperature 0.6, top-p 0.95, top-k 20, maximum response 4096 tokens, and maximum input context 32768 tokens.

Training alignment: the agent passes the task.toml description as the `<user_request>`, the same intent WebHarbor RL training uses, and decides the assistant `<think>\n` prefill on the host from the checkpoint chat template (`prompt_adapter.checkpoint_chat_template` and `generation_prompt_ends_with_think`, following OpenWebRL's `ensure_prompt_ends_with_visible_thinking_tag`). Without a prefill the request is a plain generation prompt: no trailing assistant message and no `continue_final_message`. `CDPWebEnv` gives every page, including new tabs, the 1280x1000 viewport that OpenWebRL's own browser context sets.
