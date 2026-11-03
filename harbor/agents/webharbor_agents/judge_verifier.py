"""Harbor verifier that runs the site's verifier, then an Agent Judge in the same sandbox.

Select it with `harbor run --verifier webharbor_agents.judge_verifier:JudgeVerifier`.

1. The task's own tests/test.sh runs first and produces the official reward, as with the
   default verifier.
2. The Agent Judge then runs opencode inside the same container, before the container is
   released. It reads the task instruction, the reviewer-authored rubric, the normalized
   trajectory, the final answer and the screenshots, and may inspect the verifier code and
   its verdict, the pristine seed database (/opt/WebSyn/<site>/instance_seed), the live
   final database (/opt/WebSyn/<site>/instance) and the site code. It returns
   agent_success, agent_failed or task_error with a confidence, a short explanation, the
   hard facts it verified and whether it disagrees with the verifier.

The judge verdict is an audit signal: it never changes the verifier reward. A judge
failure is recorded in judge/judge_error.json and leaves the reward unchanged.

Outputs in the trial directory:
  judge/verdict.json             the Agent Judge verdict
  judge/scene_manifest.json      judge model, timing and the verifier reward it audited
  judge/agent_stdout.log         tail of the judge's opencode output
  judge/organized_trajectory.jsonl, task.md, rubric.md   the material the judge read
  judge/judge_error.json         only when the judge phase failed

Environment (read on the host that runs `harbor run`):
  WEBHARBOR_JUDGE_BASE_URL       OpenAI-compatible endpoint, reachable from the task container
  WEBHARBOR_JUDGE_API_KEY        key for that endpoint
  WEBHARBOR_JUDGE_MODEL          judge model (default gpt-5.6-sol)
  WEBHARBOR_JUDGE_VISION_MODEL   model that reads screenshots (default: the judge model, which
                                 then reads them natively). Any other model is called through
                                 the describe_image tool, at WEBHARBOR_JUDGE_VISION_BASE_URL and
                                 WEBHARBOR_JUDGE_VISION_API_KEY (default: the judge endpoint and key).
  WEBHARBOR_JUDGE_REASONING_EFFORT  reasoning effort sent with each judge request (default high)
  WEBHARBOR_JUDGE_TIMEOUT        judge budget in seconds (default 1500)
  WEBHARBOR_JUDGES               "verifier+agent" (default) or "verifier" to skip the judge

The judge runs inside the verifier phase, so raise the verifier timeout to cover it, for
example `--verifier-timeout-multiplier 8` (8 x 300 s).
"""
from __future__ import annotations

import json
import os
import shlex
import tempfile
import time
from pathlib import Path

from harbor.models.verifier.result import VerifierResult
from harbor.verifier.verifier import Verifier

_JUDGE_INSTRUCTION = """You are a judge agent. A web-agent trial has finished. Your job: decide the
final verdict for the trial, verify facts yourself, and write the result to
/workspace/judge/output/verdict.json.

Verdict values:
  agent_success  the task goal was achieved per the rubric.
  agent_failed   the agent did not achieve the goal.
  task_error     the task cannot be completed in this environment (concrete
                 evidence: broken route, missing data, structurally impossible
                 evidence chain). Never use task_error for agent mistakes.

Workspace:
  /workspace/judge/prompts/task.md           the task instruction
  /workspace/judge/prompts/rubric.md         the authoritative grading rubric
  /workspace/judge/organized_trajectory.jsonl  steps: action, url, summary,
                                              observed page text, screenshot path
  /workspace/judge/final_answer.txt         the agent's final answer
  /workspace/judge/images/                   all screenshots of the trial
  /workspace/judge/verifier/                 the verifier scripts that produced
                                             the recorded verdict
  /workspace/judge/verifier_verdict.json    the recorded verdict (reference)
  /workspace/judge/after_state_marker       tells whether the after-DB exists

Environment facts:
  - The site code and the pristine seed database are inside this container at
    /opt/WebSyn/<site>/ (instance_seed holds the untouched seed DB).
  - For this trial the after-state database is AVAILABLE (live in-sandbox:
    /opt/WebSyn/<site>/instance; pristine seed at /opt/WebSyn/<site>/instance_seed).
  - The recorded verdict comes from the verifier scripts in
    /workspace/judge/verifier/. Those scripts are deterministic but strict;
    they are known to produce format-related false negatives. You may read
    them, run their checks against the final answer, and judge the answer
    content yourself.

{vision_note}

Method (do all that apply):
  1. Read the task, rubric, final answer, and organized trajectory.
  2. For every fact in the final answer, find support: a screenshot, observed
     page text in the trajectory, the seed database, or the site code. Use
     bash and python (sqlite3, grep) freely.
  3. When the rubric requires specific values, verify them against the seed
     database or site data rather than trusting the answer.
  4. When the recorded verdict is FAIL, decide whether the failure reflects
     wrong content (agent_failed), a verifier format issue with correct
     content (agent_success if the rubric is otherwise satisfied), or an
     environment defect (task_error).
  5. Inspect the site routes/code if you suspect the task is impossible.

Output contract: write exactly this JSON to /workspace/judge/output/verdict.json
{
  "verdict": "agent_success" | "agent_failed" | "task_error",
  "confidence": <integer 0-100>,
  "explanation": "<= 150 words",
  "hard_facts": ["...", "..."],
  "verifier_disagreement": true | false
}

Verify the JSON is valid before finishing. Write the file, then stop."""

_VISION_NOTE_NATIVE = "You have native image input: view screenshots directly with the Read tool."
_VISION_NOTE_TOOL = (
    "You have NO native image input. Do NOT Read PNG files directly. To "
    "inspect a screenshot, use the describe_image tool with the image path; "
    "it returns a text description from an external vision model."
)

_VERDICT_KEYS = {"verdict", "confidence", "explanation", "hard_facts", "verifier_disagreement"}
_VERDICTS = {"agent_success", "agent_failed", "task_error"}


def _settings() -> dict:
    model = os.environ.get("WEBHARBOR_JUDGE_MODEL", "gpt-5.6-sol")
    base_url = os.environ.get("WEBHARBOR_JUDGE_BASE_URL", "")
    api_key = os.environ.get("WEBHARBOR_JUDGE_API_KEY", "")
    return {
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "vision_model": os.environ.get("WEBHARBOR_JUDGE_VISION_MODEL", model),
        "vision_base_url": os.environ.get("WEBHARBOR_JUDGE_VISION_BASE_URL", base_url),
        "vision_api_key": os.environ.get("WEBHARBOR_JUDGE_VISION_API_KEY", api_key),
        "reasoning_effort": os.environ.get("WEBHARBOR_JUDGE_REASONING_EFFORT", "high"),
        "timeout": int(os.environ.get("WEBHARBOR_JUDGE_TIMEOUT", "1500")),
    }


def _validate_verdict(payload: object) -> dict:
    """Check the complete Agent Judge output contract."""
    if not isinstance(payload, dict):
        raise ValueError("verdict payload is not an object")
    if set(payload) != _VERDICT_KEYS:
        raise ValueError(f"verdict keys mismatch: expected={sorted(_VERDICT_KEYS)!r} observed={sorted(payload)!r}")
    if payload["verdict"] not in _VERDICTS:
        raise ValueError(f"invalid verdict: {payload['verdict']!r}")
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValueError(f"invalid confidence: {confidence!r}")
    explanation = payload["explanation"]
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("explanation must be a non-empty string")
    if len(explanation.split()) > 150:
        raise ValueError(f"explanation exceeds 150 words: {len(explanation.split())}")
    facts = payload["hard_facts"]
    if not isinstance(facts, list) or not all(isinstance(f, str) and f.strip() for f in facts):
        raise ValueError("hard_facts must be an array of non-empty strings")
    if not isinstance(payload["verifier_disagreement"], bool):
        raise ValueError("verifier_disagreement must be a boolean")
    return payload


def _rubric_for(task) -> str:
    """The task's judge_rubric, from the site tasks.jsonl that ships in tests/."""
    task_id = str(task.config.metadata.get("upstream_task_id") or "")
    try:
        lines = (Path(task.paths.tests_dir) / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return "(no rubric found)"
    for line in lines:
        if line.strip():
            record = json.loads(line)
            if record.get("id") == task_id:
                rubric = record.get("judge_rubric")
                if isinstance(rubric, (dict, list)):
                    return json.dumps(rubric, indent=1, ensure_ascii=False)
                return rubric or "(no rubric found)"
    return "(no rubric found)"


def _opencode_config(settings: dict) -> str:
    config = {
        "provider": {"openai": {
            "options": {"baseURL": settings["base_url"], "apiKey": settings["api_key"]},
            "models": {settings["model"]: {"options": {"reasoningEffort": settings["reasoning_effort"]}}},
        }},
        "permission": {"webfetch": "deny", "websearch": "deny"},
    }
    if settings["vision_model"] != settings["model"]:
        config["mcp"] = {"vision": {
            "type": "local",
            "command": ["/opt/opencode-web/bin/python", "/opt/webharbor-harness/describe_image_mcp.py"],
            "environment": {
                "AWM_VISION_BASE_URL": settings["vision_base_url"],
                "AWM_VISION_API_KEY": settings["vision_api_key"],
                "AWM_VISION_MODEL": settings["vision_model"],
                "AWM_VISION_FALLBACK_BASE_URL": "",
                "AWM_VISION_FALLBACK_MODEL": "",
                "AWM_DESCRIBE_IMAGE_TIMEOUT": "60",
                "AWM_DESCRIBE_IMAGE_RETRIES": "3",
                "AWM_DESCRIBE_IMAGE_MAX_TOKENS": "4096",
            },
            "enabled": True,
            "timeout": 240000,
        }}
    return json.dumps(config)


class JudgeVerifier(Verifier):
    """Site verification followed by the in-sandbox Agent Judge (failure-isolated)."""

    async def verify(self) -> VerifierResult:
        result = await super().verify()
        if self.step_name is not None:
            return result
        phases = {p.strip().lower() for p in os.environ.get("WEBHARBOR_JUDGES", "verifier+agent").split("+")}
        if "agent" in phases:
            try:
                await self._run_agent_judge(result)
            except Exception as e:  # noqa: BLE001 - the judge must never break the trial
                self._write_judge_file("judge_error.json", {
                    "phase": "agent_judge", "error": f"{type(e).__name__}: {e}", "at": time.time()})
        return result

    def _judge_dir(self) -> Path:
        d = Path(self.trial_paths.trial_dir) / "judge"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _write_judge_file(self, name: str, payload) -> None:
        try:
            p = self._judge_dir() / name
            p.write_text(json.dumps(payload, indent=1, ensure_ascii=False) if isinstance(payload, (dict, list)) else str(payload))
        except Exception:
            pass

    async def _exec(self, cmd: str, timeout_sec: int):
        return await self.environment.exec(cmd, timeout_sec=timeout_sec)

    async def _upload_bytes(self, remote_path: str, payload: bytes) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(payload)
            tmp = f.name
        try:
            await self.environment.upload_file(tmp, remote_path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    async def _download_bytes(self, remote_path: str) -> bytes:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp = f.name
        try:
            await self.environment.download_file(remote_path, Path(tmp))
            return Path(tmp).read_bytes()
        finally:
            Path(tmp).unlink(missing_ok=True)

    async def _run_agent_judge(self, result: VerifierResult) -> None:
        settings = _settings()
        if not settings["base_url"] or not settings["api_key"]:
            raise RuntimeError("set WEBHARBOR_JUDGE_BASE_URL and WEBHARBOR_JUDGE_API_KEY to run the Agent Judge")
        t0 = time.time()
        judge_dir = self._judge_dir()

        # 1. The scene assembler and the vision tool ship in the site image.
        r = await self._exec("test -r /opt/webharbor-harness/judge_scene_assemble.py && "
                             "test -r /opt/webharbor-harness/describe_image_mcp.py", timeout_sec=30)
        if r.return_code != 0:
            raise RuntimeError("judge helpers are missing from the sandbox image")

        # 2. Assemble /workspace/judge from the live trial state, then add the task and rubric.
        r = await self._exec("mkdir -p /workspace/judge && WH_SITE=${WH_SITE} /usr/local/bin/python3 "
                             "/opt/webharbor-harness/judge_scene_assemble.py", timeout_sec=300)
        scene = (r.stdout or "") + (r.stderr or "")
        if "SCENE_OK" not in scene:
            raise RuntimeError(f"scene assembly failed: {scene.strip()[:300]}")
        try:
            instruction_md = self.task.paths.instruction_path.read_text(errors="replace")
        except Exception:
            instruction_md = self.task.paths.task_dir.name
        await self._upload_bytes("/workspace/judge/prompts/task.md", instruction_md.encode())
        await self._upload_bytes("/workspace/judge/prompts/rubric.md", _rubric_for(self.task).encode())
        native = settings["vision_model"] == settings["model"]
        instruction = _JUDGE_INSTRUCTION.replace("{vision_note}", _VISION_NOTE_NATIVE if native else _VISION_NOTE_TOOL)
        await self._upload_bytes("/workspace/judge/prompts/judge_agent.md", instruction.encode())

        # 3. opencode config with the judge endpoint (and the vision tool for a text-only judge),
        #    uploaded as a file so the key never appears on a command line.
        r = await self._exec("mkdir -p /root/.config/opencode", timeout_sec=30)
        if r.return_code != 0:
            raise RuntimeError("could not create the judge opencode config directory")
        await self._upload_bytes("/root/.config/opencode/opencode.json", _opencode_config(settings).encode())
        await self._exec("chmod 600 /root/.config/opencode/opencode.json", timeout_sec=30)

        # 4. Run the judge.
        r = await self._exec(
            f"cd / && export AWM_REASONING_EFFORT={shlex.quote(settings['reasoning_effort'])} && "
            f"timeout {settings['timeout']} opencode run --model openai/{shlex.quote(settings['model'])} "
            '"$(cat /workspace/judge/prompts/judge_agent.md)" '
            "> /workspace/judge/output/agent_stdout.log 2>&1; echo exit=$?; "
            "test -f /workspace/judge/output/verdict.json && echo VERDICT_OK || echo NO_VERDICT",
            timeout_sec=settings["timeout"] + 240)
        out = r.stdout or ""
        verdict_ok = "VERDICT_OK" in out

        # 5. Copy the judge outputs to the trial directory (never the endpoint or key).
        rewards = getattr(result, "rewards", None) or {}
        reward = rewards.get("reward")
        manifest = {
            "judge_model": settings["model"],
            "vision_model": settings["vision_model"],
            "budget_sec": settings["timeout"],
            "wall_sec": round(time.time() - t0, 1),
            "verifier_reward": reward,
            "verifier_pass": bool(reward == 1) if isinstance(reward, (int, float)) else None,
            "scene": scene.strip().splitlines()[-1] if scene.strip() else "",
            "verdict_ok": verdict_ok,
            "exit_line": (out.strip().splitlines() or [""])[-1][:120],
        }
        error = None
        if verdict_ok:
            data = await self._download_bytes("/workspace/judge/output/verdict.json")
            try:
                parsed = _validate_verdict(json.loads(data))
                (judge_dir / "verdict.json").write_bytes(data)
                manifest["verdict"] = parsed["verdict"]
                manifest["confidence"] = parsed["confidence"]
            except Exception as e:
                (judge_dir / "verdict_bad.json").write_bytes(data)
                error = f"invalid verdict JSON: {type(e).__name__}: {e}"
        else:
            error = f"judge produced no verdict ({manifest['exit_line'] or 'no exit detail'})"
        for remote, name in (("/workspace/judge/organized_trajectory.jsonl", "organized_trajectory.jsonl"),
                             ("/workspace/judge/prompts/task.md", "task.md"),
                             ("/workspace/judge/prompts/rubric.md", "rubric.md")):
            try:
                (judge_dir / name).write_bytes(await self._download_bytes(remote))
            except Exception:
                pass
        try:
            log = await self._download_bytes("/workspace/judge/output/agent_stdout.log")
            (judge_dir / "agent_stdout.log").write_bytes(log[-400000:])
        except Exception:
            pass
        self._write_judge_file("scene_manifest.json", manifest)
        if error:
            raise RuntimeError(error)
