"""Grade each required outcome against the same recorded session and frozen fixture."""
import hashlib
import importlib
import json
import sqlite3
from pathlib import Path
from verify_lib import Judge, load_run, parse_args


def fixture_hashes(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {table: hashlib.sha256(json.dumps(
            [dict(row) for row in con.execute('SELECT * FROM "' + table + '" ORDER BY 1')],
            sort_keys=True, separators=(',', ':')).encode()).hexdigest() for table in tables}


def grade(number):
    args = parse_args()
    config = json.loads(Path(__file__).with_name('review_components.json').read_text())
    components = config.get(str(number), [number])
    site = Path(__file__).resolve().parents[1].name
    prefix = {'flightaware': 'FlightAware', 'chronicle_jobs': 'Chronicle Jobs', 'dillards': 'Dillards'}[site]
    expected_id = f'{prefix}--{number}'
    j = Judge(expected_id)
    t = load_run(args.run_dir)
    j.check('trajectory_task_matches', t.get('task_id') == expected_id, 'recorded task must match the requested task')
    expected = json.loads(Path(__file__).with_name('reviewed_seed.json').read_text())
    try:
        j.check('reviewed_initial_fixture', fixture_hashes(args.initial_db) == expected,
                'initial snapshot matches the reviewed seed tables')
        if not args.after_db or not Path(args.after_db).is_file():
            raise ValueError('saved after.db snapshot is required')
    except (OSError, ValueError, TypeError, sqlite3.Error) as error:
        j.check('snapshot_package', False, str(error))
        j.emit()
    if site == 'flightaware':
        from grade import TASKS, STATEFUL
        for component in components:
            final = args.after_db if component in STATEFUL or not set(components) & STATEFUL else args.initial_db
            TASKS[component](j, t, args.initial_db, final)
    elif site == 'dillards':
        from grade import grade as check
        for component in components:
            partial = check(component, emit=False, task_id=expected_id)
            j.check('outcome_' + str(component), partial.ok, partial.reason)
            j.evidence.extend(partial.evidence)
    else:
        from verify_lib import validate_snapshot_contract
        try:
            validate_snapshot_contract(args.initial_db, args.after_db)
        except (OSError, ValueError, sqlite3.Error) as error:
            j.check('snapshot_contract', False, str(error))
        for component in components:
            module = importlib.import_module('verify_' + str(component))
            component_t = dict(t, task_id=f'{prefix}--{component}')
            module.run_checks(j, component_t, args.initial_db, args.after_db)
    j.emit()
