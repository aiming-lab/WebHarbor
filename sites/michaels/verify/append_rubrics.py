#!/usr/bin/env python3
"""Rubrics are maintained alongside the reviewed prompts in tasks.jsonl.

Validate that every task has its reviewer contract; do not overwrite refinements.
"""
import json
from pathlib import Path
if __name__ == '__main__':
    tasks = [json.loads(line) for line in (Path(__file__).resolve().parents[1] / 'tasks.jsonl').read_text().splitlines()]
    assert all(t.get('judge_rubric') and t.get('verifier_path') for t in tasks)
    print(f'{len(tasks)} reviewer contracts present')
