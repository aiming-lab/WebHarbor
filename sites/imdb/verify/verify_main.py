"""CLI entry point shared by the IMDb task-specific verifier scripts."""

import json
from pathlib import Path
import sqlite3

from read_tasks import READ_TASKS, check_read_task
from verify_lib import RunEvidence, VerificationError, emit_result, parse_args


def main(number, argv=None):
    args = parse_args(argv)
    task_id = f"IMDb--{number}"
    try:
        rows = [json.loads(line) for line in
                (Path(__file__).resolve().parent.parent / "tasks.jsonl").read_text().splitlines()
                if line.strip()]
        matching = [row for row in rows if row.get("id") == task_id]
        if len(matching) != 1:
            raise VerificationError("The task must occur exactly once in the candidate task file")
        with RunEvidence(args.run_dir, task_id, matching[0]["ques"],
                         initial_db=args.initial_db, after_db=args.after_db) as run:
            if number in READ_TASKS:
                evidence = check_read_task(number, run)
            elif number in {15, 16, 17}:
                from state_tasks import check_state_task
                evidence = check_state_task(number, run)
            elif number in {18, 19, 20, 23}:
                from expansion_catalog_reads import check_catalog_read_task
                evidence = check_catalog_read_task(number, run)
            elif number in {21, 22}:
                from expansion_account_reads import check_account_read_task
                evidence = check_account_read_task(number, run)
            elif number in {24, 25, 26, 27}:
                from expansion_state_tasks import check_expansion_state_task
                evidence = check_expansion_state_task(number, run)
            else:
                raise VerificationError("Unsupported task number")
        return emit_result(task_id, True, "Task requirements satisfied by the supplied run", evidence)
    except VerificationError as error:
        return emit_result(task_id, False, str(error))
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        # Do not expose database rows, credentials or private filesystem paths.
        return emit_result(task_id, False, f"Cannot validate the supplied artifacts ({type(error).__name__})")
