"""CLI entry point shared by AKC task-specific verifier scripts."""

import json
from pathlib import Path
import sqlite3

from task_checks import READ_TASKS, check_read_task, check_state_task
from verify_lib import RunEvidence, VerificationError, emit_result, parse_args


def main(number, argv=None):
    args = parse_args(argv)
    task_id = f"AKC--{number}"
    try:
        task_file = Path(__file__).resolve().parent.parent / "tasks.jsonl"
        rows = [json.loads(line) for line in task_file.read_text().splitlines() if line.strip()]
        matching = [row for row in rows if row.get("id") == task_id]
        if len(matching) != 1:
            raise VerificationError("The task must occur exactly once in tasks.jsonl")
        with RunEvidence(args.run_dir, task_id, matching[0]["ques"],
                         initial_db=args.initial_db, after_db=args.after_db) as run:
            evidence = check_read_task(number, run) if number in READ_TASKS else check_state_task(number, run)
        return emit_result(task_id, True, "Task requirements satisfied by the supplied run", evidence)
    except VerificationError as error:
        return emit_result(task_id, False, str(error))
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        return emit_result(task_id, False,
                           f"Cannot validate the supplied artifacts ({type(error).__name__})")
