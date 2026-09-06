# agent_demo

Minimal ReAct loop (`agent.py`) + LLM-as-judge grader (`eval_judge.py`) for driving and evaluating an agent on any WebHarbor mirror.

## Setup

```bash
cd agent_demo
uv sync                                  # installs deps into .venv
uv run playwright install chromium       # one-time browser download
```

API key + base URL come from env vars (do **not** hardcode them):

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.openai.com/v1   # or your Azure / vLLM endpoint
```

## Run a task

WebHarbor must already be running locally (`docker run -p 8101:8101 -p 40000-40018:40000-40018 battalion7244/webharbor:latest`).

Run a single task from a site's `tasks.jsonl`:

```bash
uv run python agent.py \
  --tasks_file ../sites/google_search/tasks.jsonl \
  --task_id "Google Search--0" \
  --out_dir runs/gs0
```

Omit `--task_id` to pick the first row. Or run an ad-hoc task:

```bash
uv run python agent.py \
  --task "Find Kevin Durant's bio" \
  --url http://localhost:40009/ \
  --out_dir runs/inline
```

Each run writes `trajectory.json` + `screenshots/step_NNN.png` under `--out_dir`.

## Grade a run

```bash
uv run python eval_judge.py --run_dir runs/gs0
```

Writes `eval.json` next to the trajectory with `success`, `confidence`, `rationale`, and `evidence`.
