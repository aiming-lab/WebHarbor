# WebHarbor on Harbor

This directory packages the WebHarbor benchmark for the [Harbor](https://github.com/harbor-framework/harbor) evaluation framework. It contains the three agent harnesses used in the paper (OpenWebRL, browser-use GUI, and OpenCode), the per-site container images, and the adapter that turns the WebHarbor sites into Harbor task directories.

The 3,518 ready-made Harbor tasks are published on Hugging Face as [`ChilleD/WebHarbor-Tasks`](https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks). Every task pins a per-site image `wildawm/webharbor:<site>-v1` on Docker Hub, so running the benchmark needs no local build.

## Quickstart

```bash
git clone https://github.com/aiming-lab/WebHarbor --depth 1 && cd WebHarbor/harbor
# the agents use the Harbor 0.24 agent API; 0.25 removed harbor.agents.model_connection
uv tool install harbor==0.24.0   
# GUI harness (browser-use SDK, vision, last 3 screenshots) on the test split
PYTHONPATH=agents OPENAI_BASE_URL=<endpoint> OPENAI_API_KEY=<key> \
  harbor run --repo https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks -d webharbor-test@1.0 \
  -a webharbor_agents.browseruse:BrowserUseWebHarbor -m openai/<model> \
  --ak mode=vision --ak last_k=3 -n 4 -y
```

The model endpoint must be reachable from inside the task container: for a server on the Docker host, use the bridge gateway (for example `http://172.17.0.1:<port>/v1`), not `localhost`.

> ! ⚠️ Docker Hub rate-limits anonymous pulls (about 100 per 6 hours per IP), so run `docker login` before running many sites on one machine.

## Datasets

`ChilleD/WebHarbor-Tasks` holds one registry (`registry.json`) with five datasets; every task directory is stored once under `tasks/`, and each dataset lists the tasks it contains.

| Dataset                    | Tasks | Contents                                                     |
| -------------------------- | ----: | ------------------------------------------------------------ |
| `webharbor@1.0`            | 3,518 | all tasks on all 153 sites                                   |
| `webharbor-train@1.0`      | 2,288 | RL training tasks on 123 sites excluding all 15 WebVoyager sites and 15 held-out sites |
| `webharbor-test@1.0`       |   306 | held-out test set, two tasks per site                        |
| `webharbor-webvoyager@1.0` |   643 | all tasks on the 15 WebVoyager sites                         |
| `webharbor-unused@1.0`     |   311 | tasks in no other split, on 15 held-out sites                |

## Harnesses

`agents/webharbor_agents/` holds three Harbor agents; Harbor imports them through `PYTHONPATH=agents`. Each runs its in-container script from `harness/` as the unprivileged `ubuntu` user, and all three attach over CDP to one Chromium that the site entrypoint starts.

| Agent           | Import path                                             | Notes                                                        |
| --------------- | ------------------------------------------------------- | ------------------------------------------------------------ |
| browser-use GUI | `webharbor_agents.browseruse:BrowserUseWebHarbor`       | browser-use 0.11.13 SDK. `--ak mode=vision` (screenshots) or `mode=text` (DOM). `--ak last_k=3` keeps the last K screenshots. |
| OpenCode        | `webharbor_agents.opencode_webharbor:OpenCodeWebHarbor` | opencode 1.17.7 with Playwright MCP 0.0.78 registered as the `browser` server. A screenshot is captured after every tool call. |
| OpenWebRL       | `webharbor_agents.openwebrl:OpenWebRLWebHarbor`         | The exact OpenWebRL GUI web agent harness. Sampling: temperature 0.6, top-p 0.95, top-k 20; 50 steps. Use `--ak api_mode=chat_completions` for exact prompt serialization. **WebHarbor-4B used this harness for benchmarking.** |

```bash
# OpenCode
PYTHONPATH=agents OPENAI_BASE_URL=<endpoint> OPENAI_API_KEY=<key> \
  harbor run --repo https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks -d webharbor-test@1.0 \
  -a webharbor_agents.opencode_webharbor:OpenCodeWebHarbor -m openai/<model> -y

# OpenWebRL policy served behind a Chat Completions endpoint
PYTHONPATH=agents OPENAI_BASE_URL=<endpoint> OPENAI_API_KEY=<key> \
  harbor run --repo https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks -d webharbor-test@1.0 \
  -a webharbor_agents.openwebrl:OpenWebRLWebHarbor -m openai/<model> --ak api_mode=chat_completions -y
```

The browser-use and OpenCode agents can give a text-only policy an external vision model through `--ak vision_enabled=true` with `--ak vision_base_url=... --ak vision_model=... --ak vision_api_key=...`. The vision key defaults to `OPENAI_API_KEY`.

## Verification

Each task's `tests/test.sh` runs as root in the same container after the agent finishes:

1. `tests/build_trajectory.py` rebuilds the WebHarbor run directory:
   - the steps visited, from the root-owned access log;
   - `initial.db` and `after.db`;
   - the final answer and termination status, from `/logs/agent`;
   - harness screenshots, attached to steps by timestamp.
2. The site's own `verify_<n>.py`, unchanged from this repository, checks the run directory. `tests/` carries that verifier, the helper and data files it uses, and the site's `tasks.jsonl`. `test.sh` copies them to `/opt/WebSyn/<site>/verify/` and `/opt/WebSyn/<site>/tasks.jsonl`, the same layout as `sites/<site>/` here, and runs the verifier from there. Verifiers that read the site databases with `docker cp` or `docker exec` get a stand-in `docker` command that does the same thing inside the container.
3. The verdict goes to `/logs/verifier/reward.json`: `reward` (1/0) plus pass/fail check counts.


### Agent Judge (agent-as-a-judge)

The verifier gives the official reward. To also audit each trial with an Agent Judge, run with `--verifier webharbor_agents.judge_verifier:JudgeVerifier`. After `tests/test.sh` has produced the reward, the judge runs opencode in the same container, before the container is released. It reads the task, the task's reviewer-authored rubric (`judge_rubric` in `tests/tasks.jsonl`), the trajectory, the final answer and the screenshots. It can also inspect the verifier and its verdict, the seed and final databases and the site code. It returns `agent_success`, `agent_failed` or `task_error` (an environment defect, never an agent mistake) with a confidence, a short explanation, the facts it checked and whether it disagrees with the verifier. The judge never changes the verifier reward.

```bash
# any OpenAI-compatible endpoint the task containers can reach; gpt-5.6-sol is the default judge
export WEBHARBOR_JUDGE_BASE_URL=xxxxx
export WEBHARBOR_JUDGE_API_KEY=xxxxx
PYTHONPATH=agents OPENAI_BASE_URL=<endpoint> OPENAI_API_KEY=<key> \
  harbor run --repo https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks -d webharbor-test@1.0 \
  -a webharbor_agents.openwebrl:OpenWebRLWebHarbor -m openai/<model> --ak api_mode=chat_completions \
  --verifier webharbor_agents.judge_verifier:JudgeVerifier --verifier-timeout-multiplier 8 -y
```

The judge runs inside the verifier phase, so `--verifier-timeout-multiplier 8` raises the 300 s verifier timeout to cover its 1,500 s budget. Each trial directory then holds `judge/verdict.json`, `judge/scene_manifest.json` (judge model, timing and the verifier reward it audited) and the material the judge read. A judge failure is written to `judge/judge_error.json` and leaves the reward unchanged.

| Variable | Default | Meaning |
| --- | --- | --- |
| `WEBHARBOR_JUDGE_BASE_URL` | none (required) | OpenAI-compatible endpoint for the judge |
| `WEBHARBOR_JUDGE_API_KEY` | none (required) | key for that endpoint |
| `WEBHARBOR_JUDGE_MODEL` | `gpt-5.6-sol` | judge model |
| `WEBHARBOR_JUDGE_VISION_MODEL` | the judge model | model that reads screenshots. The default judge reads them natively; set a vision model here for a text-only judge, with `WEBHARBOR_JUDGE_VISION_BASE_URL` and `WEBHARBOR_JUDGE_VISION_API_KEY` if it is served elsewhere |
| `WEBHARBOR_JUDGE_REASONING_EFFORT` | `high` | reasoning effort sent with each judge request |
| `WEBHARBOR_JUDGE_TIMEOUT` | `1500` | judge budget in seconds |
| `WEBHARBOR_JUDGES` | `verifier+agent` | `verifier` skips the judge |
