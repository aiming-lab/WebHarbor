#!/usr/bin/env python3
"""NVIDIA repair002: explicit, read-only stdlib grading contract.

No application import, network, model or default database is used. Exit 0/1 means a
valid PASS/FAIL; exit 2 is malformed/unavailable infrastructure.

The CLI accepts the same three/five arguments as every other site verifier in this
repository (`--run_dir`, optional `--initial_db`, optional `--after_db`, optional
`--container`, optional `--no_llm`), so `agent_demo/eval_judge.py --verifier True`
can drive it unchanged: when the two database paths are omitted they are fetched
from the running container named by `--container` (default `$WH_CONTAINER` or
`wh-review`). Trajectories are accepted in both the production recorder shape
(`agent_demo/agent.py`: `task`/`start_url`, no `query`, no `task.json`, no
`final_url`) and the explicit shape (`query`, `task.json`, `final_url`).
"""
import argparse
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit

SITE = Path(__file__).resolve().parent.parent
TABLES = {
    'users': 'id email password_hash name company country newsletter_opt_in created',
    'products': 'id slug name category series tagline description price_usd image release_year in_stock is_featured architecture cuda_cores tensor_cores rt_cores memory_gb memory_type memory_bandwidth boost_clock_ghz tdp_watts interface recommended_psu_watts',
    'articles': 'id slug title category author published excerpt body image read_minutes',
    'drivers': 'id product_series branch version os released size_mb highlights download_count',
    'newsletter': 'id email topic',
    'reviews': 'id product_id user_id rating title body created',
    'cart_items': 'id user_id product_id quantity',
    'orders': 'id user_id created status total_usd',
    'wishlist_items': 'id user_id product_id',
    'order_items': 'id order_id product_id name price_usd quantity',
}


class InfraError(Exception):
    """Inputs cannot support a task verdict."""


class TaskFailure(Exception):
    """Well-formed evidence does not meet the task."""


def require(condition, reason):
    if not condition:
        raise TaskFailure(reason)


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise InfraError('duplicate JSON keys')
    return result


def load_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream, object_pairs_hook=unique_object,
                         parse_constant=lambda value: (_ for _ in ()).throw(InfraError('nonfinite JSON')))


def snapshot(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise InfraError('database must be an explicit regular file')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as con:
        con.execute('PRAGMA query_only=ON')
        if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise InfraError('SQLite integrity_check failed')
        if con.execute('PRAGMA foreign_key_check').fetchall():
            raise InfraError('SQLite foreign_key_check failed')
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if names != set(TABLES):
            raise InfraError('unexpected/missing database tables')
        schema = con.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        con.row_factory = sqlite3.Row
        data = {}
        for name, columns in TABLES.items():
            actual = {r['name'] for r in con.execute(f'PRAGMA table_info("{name}")')}
            if actual != set(columns.split()):
                raise InfraError(f'{name}: unexpected/missing columns')
            rows = [dict(r) for r in con.execute(f'SELECT * FROM "{name}" ORDER BY id')]
            if any(type(r['id']) is not int for r in rows):
                raise InfraError(f'{name}: invalid primary key')
            data[name] = rows
        return data, schema


def canonical_task(number):
    # This remains local to the site even when the entire repository is staged.
    tasks = [json.loads(line, object_pairs_hook=unique_object) for line in
             (SITE / 'tasks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    ids = [t.get('id') for t in tasks]
    if len(ids) != len(set(ids)):
        raise InfraError('duplicate canonical task IDs')
    matches = [t for t in tasks if t.get('id') == f'NVIDIA--{number}']
    if len(matches) != 1:
        raise InfraError('canonical task missing')
    return matches[0]


def canonical_task_by_id(task_id):
    tasks = [json.loads(line, object_pairs_hook=unique_object) for line in
             (SITE / 'tasks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    matches = [t for t in tasks if t.get('id') == task_id]
    if len(matches) != 1:
        raise InfraError(f'unknown task id: {task_id!r}')
    return matches[0]


DB_KINDS = {'initial_db': 'instance_seed', 'after_db': 'instance'}


def resolve_database(kind, explicit, container, workdir):
    """Return a readable DB path: explicit path, else `docker cp` from the container.

    This mirrors the fallback every other site verifier in this repository uses, so
    `agent_demo/eval_judge.py --verifier True` (which forwards only --run_dir) works.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise InfraError(f'{kind} is not a readable file: {explicit}')
        return str(path)
    if shutil.which('docker') is None:
        raise InfraError(f'{kind} missing and no docker CLI for the container fallback')
    remote = f"{container}:/opt/WebSyn/nvidia/{DB_KINDS[kind]}/nvidia.db"
    local = str(Path(workdir) / f'{DB_KINDS[kind]}.db')
    result = subprocess.run(['docker', 'cp', remote, local], capture_output=True, text=True)
    if result.returncode != 0 or not Path(local).is_file():
        raise InfraError(f"{kind} missing and 'docker cp {remote}' failed: "
                         f"{result.stderr.strip()[:160] or 'no output'}")
    return local


SCREENSHOT_MIN_WIDTH = 320
SCREENSHOT_MIN_HEIGHT = 200
SCREENSHOT_MAX_BYTES = 8 * 1024 * 1024
SCREENSHOT_KEYS = ('screenshot_before', 'screenshot_after', 'screenshot', 'screenshot_path')
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
_PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def png_dimensions(path):
    """Structural PNG validation using only the standard library.

    Checks the signature, every chunk CRC, the IHDR fields, zlib-decompresses the
    IDAT stream and verifies the decompressed scanline length, so a truncated,
    hand-written or renamed file cannot pass as a screenshot.
    """
    import binascii
    import struct
    import zlib
    data = Path(path).read_bytes()
    if len(data) < 33 or not data.startswith(_PNG_SIGNATURE):
        raise InfraError(f'screenshot is not a PNG: {Path(path).name}')
    offset = len(_PNG_SIGNATURE)
    idat = bytearray()
    header = None
    saw_end = False
    while offset < len(data):
        if offset + 8 > len(data):
            raise InfraError(f'truncated PNG chunk header: {Path(path).name}')
        length, kind = struct.unpack('>I4s', data[offset:offset + 8])
        end = offset + 12 + length
        if length > SCREENSHOT_MAX_BYTES or end > len(data):
            raise InfraError(f'truncated PNG chunk: {Path(path).name}')
        payload = data[offset + 8:offset + 8 + length]
        stored = struct.unpack('>I', data[offset + 8 + length:end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != stored:
            raise InfraError(f'PNG chunk CRC mismatch: {Path(path).name}')
        if kind == b'IHDR':
            if length != 13:
                raise InfraError(f'invalid IHDR length: {Path(path).name}')
            header = struct.unpack('>IIBBBBB', payload)
        elif kind == b'IDAT':
            idat += payload
        elif kind == b'IEND':
            saw_end = True
        offset = end
    if header is None or not saw_end or not idat:
        raise InfraError(f'PNG lacks IHDR/IDAT/IEND: {Path(path).name}')
    width, height, depth, color, compression, filter_method, interlace = header
    if color not in _PNG_CHANNELS or depth not in (1, 2, 4, 8, 16):
        raise InfraError(f'unsupported PNG colour type/depth: {Path(path).name}')
    if compression != 0 or filter_method != 0 or interlace not in (0, 1):
        raise InfraError(f'unsupported PNG encoding: {Path(path).name}')
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise InfraError(f'PNG IDAT is not decodable: {Path(path).name}: {exc}') from exc
    if interlace == 0:
        stride = width * _PNG_CHANNELS[color] * depth // 8
        expected = height * (1 + stride)
        if len(raw) != expected:
            raise InfraError(f'PNG scanline length mismatch: {Path(path).name}')
    if width < SCREENSHOT_MIN_WIDTH or height < SCREENSHOT_MIN_HEIGHT:
        raise InfraError(f'screenshot smaller than {SCREENSHOT_MIN_WIDTH}x{SCREENSHOT_MIN_HEIGHT}: '
                         f'{Path(path).name} is {width}x{height}')
    return width, height


def screenshot_files(run_dir, steps):
    """Referenced screenshots when the trajectory names them, else the run's PNG set."""
    referenced = []
    for word in steps:
        for key in SCREENSHOT_KEYS:
            value = word.get(key)
            if isinstance(value, str) and value.strip():
                name = value.strip()
                if name not in referenced:
                    referenced.append(name)
    if referenced:
        return referenced, True
    run_dir = Path(run_dir)
    names = []
    for base in (run_dir / 'screenshots', run_dir):
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if path.is_file() and path.suffix.casefold() == '.png' and path.name not in names:
                names.append(path.name)
        if names:
            break
    return names, False


def validate_screenshots(run_dir, steps):
    """Bind the verdict to real, decodable browser screenshots (repair002, H3).

    A trajectory without usable screenshots is an unverifiable run: INFRA, not a
    task FAIL. Named screenshot files must exist (that is the trajectory binding);
    an unnamed run must still carry at least one valid PNG per step, capped at two.
    """
    run_dir = Path(run_dir)
    names, referenced = screenshot_files(run_dir, steps)
    if not names:
        raise InfraError('run_dir has no screenshots: a browser run must provide PNG evidence')
    valid = []
    for name in names:
        candidate = Path(name)
        if candidate.is_absolute() or '..' in candidate.parts:
            raise InfraError(f'screenshot reference must stay inside run_dir: {name!r}')
        resolved = run_dir / candidate
        if not resolved.is_file():
            resolved = run_dir / 'screenshots' / candidate.name
        if not resolved.is_file():
            raise InfraError(f'referenced screenshot is missing: {name!r}')
        if resolved.stat().st_size > SCREENSHOT_MAX_BYTES:
            raise InfraError(f'screenshot exceeds {SCREENSHOT_MAX_BYTES} bytes: {candidate.name}')
        png_dimensions(resolved)
        valid.append(candidate.name)
    if not referenced:
        needed = max(1, min(len(steps), 2))
        if len(valid) < needed:
            raise InfraError(f'expected at least {needed} screenshots for {len(steps)} steps, found {len(valid)}')
    return valid


def parse_url(value):
    if not isinstance(value, str) or not value:
        raise InfraError('trajectory URL must be a nonempty string')
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise InfraError('invalid trajectory URL') from exc
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise InfraError('invalid absolute HTTP trajectory URL')
    return url, (url.scheme, url.hostname, port or (443 if url.scheme == 'https' else 80))


class Context:
    def __init__(self, number, args):
        self.number = number
        self.canonical = canonical_task(number)
        # task.json is optional: the production recorder does not write it. When it
        # is present it must match the canonical row exactly (no silent旧题/旧rubric).
        task_json = Path(args.run_dir) / 'task.json'
        if task_json.exists():
            self.task = load_json(task_json)
            if self.task != self.canonical:
                raise InfraError('task.json differs from this verifier revision/task')
        else:
            self.task = self.canonical
        self.trajectory = load_json(Path(args.run_dir) / 'trajectory.json')
        t = self.trajectory
        if not isinstance(t, dict):
            raise InfraError('trajectory must be a JSON object')
        if t.get('task_id') != self.task['id']:
            raise InfraError('trajectory task_id does not match the requested task')
        if t.get('task_id') != self.canonical['id']:
            raise InfraError('trajectory task_id does not match this verifier')
        # Accept either the explicit `query` key or the production recorder's `task`
        # key; when the value is present it must equal the canonical question.
        for key in ('query', 'task'):
            if key in t and t[key] != self.canonical['ques']:
                raise InfraError(f'trajectory {key} does not match the canonical question')
        if not isinstance(t.get('steps'), list):
            raise InfraError('trajectory steps must be a list')
        if not isinstance(t.get('final_answer'), str):
            raise InfraError('trajectory final_answer must be a string')
        self.answer = t['final_answer']
        self.screenshots = validate_screenshots(args.run_dir, t['steps'])
        self.pages = []
        self.origins = set()
        for index, step in enumerate(t['steps']):
            if not isinstance(step, dict) or type(step.get('step')) is not int or step['step'] != index:
                raise InfraError('steps must have consecutive integer step indices')
            if 'query' in step and step['query'] != self.canonical['ques']:
                raise InfraError('step query mismatch')
            if 'task' in step and step['task'] != self.canonical['ques']:
                raise InfraError('step task mismatch')
            if not any(k in step for k in ('url', 'url_before', 'url_after')):
                raise InfraError('step lacks a URL')
            for field in ('url_before', 'url', 'url_after'):
                if field in step:
                    self.add_page(step[field])
        self.final = None
        if t.get('final_url') is not None:
            self.final = self.add_page(t['final_url'])
            self.final_source = 'final_url'
        else:
            # Documented fallback: the production recorder writes no final_url, so the
            # page the run stopped on is the last recorded step URL (url_after when the
            # recorder measures it, else the step's own url).
            last = None
            for step in t['steps']:
                value = step.get('url_after') or step.get('url')
                if value:
                    last = value
            if last:
                self.final = self.add_page(last)
                self.final_source = 'last_step_url'
        self.before, schema = snapshot(resolve_database('initial_db', args.initial_db, args.container, args._workdir))
        self.after, after_schema = snapshot(resolve_database('after_db', args.after_db, args.container, args._workdir))
        if schema != after_schema:
            raise InfraError('before/after schema mismatch')

    def add_page(self, value):
        url, origin = parse_url(value)
        self.origins.add(origin)
        page = (unquote(url.path).rstrip('/') or '/', parse_qs(url.query, keep_blank_values=True))
        self.pages.append(page)
        return page

    def same_site(self):
        """All recorded pages must belong to one loopback origin.

        Runtime port mapping and loopback host spelling are harness details, so
        `localhost`, `127.0.0.1` and `[::1]` on the same port are treated as the
        same host (repair002, M9); the port itself must stay constant within a run,
        and non-loopback hosts or browser boundary events still fail.
        """
        if self.trajectory.get('boundary_events'):
            return False
        ports = {port for _, _, port in self.origins}
        if len(ports) > 1:
            return False
        return all(host in ('localhost', '127.0.0.1', '::1') for _, host, _ in self.origins)

    def product(self, slug):
        rows = [r for r in self.before['products'] if r['slug'] == slug]
        if len(rows) != 1:
            raise InfraError(f'missing/ambiguous product: {slug}')
        return rows[0]

    def detail(self, slug):
        return any(path == '/products/' + slug for path, _ in self.pages)

    def compare(self, slugs):
        # Match app.py precedence exactly: nonempty getlist('product') wins
        # over the first legacy ids value. Both contain slugs, never DB IDs.
        for path, query in self.pages:
            if path != '/compare':
                continue
            values = query.get('product') or query.get('ids', [''])[0].split(',')
            selected = {value.strip() for value in values if value.strip()}
            if set(slugs) <= selected:
                return True
        return False

    def specs(self, slug):
        return self.detail(slug) or self.compare([slug])

    def buying(self, slug=None):
        for path, _ in self.pages:
            if path == '/where-to-buy' or (slug and path == '/where-to-buy/' + slug):
                return True
        return False

    def listing(self, category=None, series=None):
        for path, q in self.pages:
            if path == '/products':
                if q.get('q', [''])[0].strip():
                    continue  # A narrowed search is not evidence of an entire candidate set.
                if q.get('category', [''])[0] not in ('', category):
                    continue
                if q.get('series', [''])[0] not in ('', series):
                    continue
                return True
            if series and path == '/geforce/graphics-cards/' + series.split()[1] + '-series':
                return True
        return False


def row_counter(rows, ignore=()):
    return Counter(tuple((k, row[k]) for k in sorted(row) if k not in ignore) for row in rows)


def preserved(ctx, except_table=None):
    for table in TABLES:
        if table == except_table:
            continue
        if table == 'drivers':
            # A read task may harmlessly press the simulated Download button.
            require(row_counter(ctx.before[table], ('download_count',)) ==
                    row_counter(ctx.after[table], ('download_count',)), 'driver records changed')
            old = {r['id']: r['download_count'] for r in ctx.before[table]}
            require(all(type(r['download_count']) is int and r['download_count'] >= (old[r['id']] or 0)
                        for r in ctx.after[table]), 'driver download counter regressed')
        else:
            require(row_counter(ctx.before[table]) == row_counter(ctx.after[table]),
                    f'unrequested {table} mutation')


def delta(ctx, table):
    old = {r['id']: r for r in ctx.before[table]}
    new = {r['id']: r for r in ctx.after[table]}
    added = [new[i] for i in new.keys() - old.keys()]
    removed = [old[i] for i in old.keys() - new.keys()]
    modified = [i for i in old.keys() & new.keys() if old[i] != new[i]]
    return added, removed, modified


def bool_value(value):
    return str(value).casefold() in {'1', 'true', 'yes', 'on'}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InfraError(message)


def run(number):
    task_id = f'NVIDIA--{number}'
    code = 2
    with tempfile.TemporaryDirectory(prefix='nvidia-verifier-') as workdir:
        try:
            parser = Parser(description=__doc__)
            parser.add_argument('--run_dir', required=True)
            parser.add_argument('--initial_db', default='')
            parser.add_argument('--after_db', default='')
            parser.add_argument('--container', default=os.environ.get('WH_CONTAINER', 'wh-review'))
            parser.add_argument('--no_llm', nargs='?', const=True, default=False, type=bool_value)
            parser.add_argument('--_workdir', default=workdir, help=argparse.SUPPRESS)
            args = parser.parse_args()
            ctx = Context(number, args)
            require(ctx.same_site(), 'off-origin navigation or browser boundary violation')
            from predicates import grade
            evidence = grade(ctx)
            result = {'task_id': task_id, 'pass': True, 'reason': 'Required facts/state verified', 'evidence': evidence}
            code = 0
        except TaskFailure as exc:
            result = {'task_id': task_id, 'pass': False, 'reason': str(exc), 'evidence': []}
            code = 1
        except Exception as exc:
            # Input errors and unexpected verifier faults are infrastructure, never
            # a normal task FAIL. Keep stdout a single parseable JSON object.
            result = {'task_id': task_id, 'pass': False, 'reason': f'INFRA_ERROR: {exc}', 'evidence': [], 'error': 'INFRA_ERROR'}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return code
