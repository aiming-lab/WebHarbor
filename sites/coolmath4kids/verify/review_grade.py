"""Grade expanded tasks using their independent, outcome-specific component checks.

A component is a coherent request (catalog comparison, policy lookup, etc.).
All required components must pass on the same real trajectory and snapshots.
Answers remain ordinary prose; no component labels or special format required.
"""
import hashlib
import json
from pathlib import Path
from grade import grade as grade_component
from verify_lib import Judge, parse_args, rows, resolve_db


def grade(number):
    components = json.loads(Path(__file__).with_name('review_components.json').read_text())
    numbers = components.get(str(number), [number])
    result = None
    for component in numbers:
        partial = grade_component(component, emit=False)
        if result is None:
            result = partial
        else:
            result.check('component_' + str(component), partial.ok, partial.reason)
            result.evidence.extend(partial.evidence)
    args = parse_args()
    before = rows(args.initial_db or resolve_db(None, args.container, "instance_seed"))
    expected = json.loads(Path(__file__).with_name('reviewed_seed.json').read_text())
    actual = {t: hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
              for t, v in (before or {}).items()}
    result.check('reviewed_initial_fixture', actual == expected,
                 'initial snapshot matches the reviewed immutable seed tables')
    result.emit()
