"""Bearer-authenticated WebSyn control plane on :8101.

Set WEBSYN_CONTROL_TOKEN to a secret of at least 32 characters. Startup fails closed when it is absent or too short.

Endpoints:
    GET  /health             -> per-site PID + alive status
    POST /reset/<site>       -> SIGKILL site group, restore instance/ from instance_seed/, respawn
    POST /reset-all          -> reset every site in parallel
    POST /restart/<site>     -> just respawn (no DB wipe) -- bonus, useful for code reload

PID tracking: each site supervisor atomically writes a JSON identity record containing its PID, Linux process start time, site, and port at /tmp/websyn_pids/<site>.pid. Reset validates the complete identity before signaling its process group.
"""
import hmac
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, jsonify, request

SITES = [
    'allrecipes', 'amazon', 'apple', 'arxiv', 'bbc_news', 'booking',
    'github', 'google_flights', 'google_map', 'google_search',
    'huggingface', 'wolfram_alpha', 'cambridge_dictionary',
    'coursera', 'espn', 'merriam_webster', 'ikea', 'phys_org', 'target', 'ted', 'osu', 'rotten_tomatoes', 'compass', 'walmart_careers', 'drugs_com',
]
BASE_PORT = 40000
WEBSYN_DIR = '/opt/WebSyn'
PID_DIR = Path('/tmp/websyn_pids')
PID_DIR.mkdir(parents=True, exist_ok=True)

# Per-site mutex so concurrent /reset, /reset-all, /restart against the same
# site can't race on PID files / instance dir.
_site_locks = {s: threading.Lock() for s in SITES}

# Per-site Popen handles for the supervisor processes that control_server
# spawned itself. Keeping the Popen reference lets us .kill() + .wait() to
# both signal AND reap the process group cleanly. Without it, Python's
# garbage collector eventually wait()s, but until then is_alive(pid) keeps
# returning True for the zombie and our reset loop blocks on a stale poll.
#
# Sites started by websyn_start.sh at boot won't have an entry here until
# their first respawn — kill_site falls back to os.killpg + zombie poll
# for those.
_site_procs: dict = {}
_site_procs_lock = threading.Lock()
_reap_lock = threading.Lock()

# We tried graceful SIGTERM. Werkzeug's threaded serve_forever() doesn't
# honor it. Since /reset wipes instance/ next anyway, in-flight transactions
# are about to be discarded — graceful shutdown has no value here. SIGKILL
# directly via process group (site_runner.py runs setsid → its pgid == pid).
REAP_GRACE_SECS = 5.0

app = Flask(__name__)


def _load_control_token() -> str:
    configured = os.environ.get('WEBSYN_CONTROL_TOKEN')
    if configured is None:
        raise RuntimeError('WEBSYN_CONTROL_TOKEN is required')
    if len(configured) < 32:
        raise RuntimeError('WEBSYN_CONTROL_TOKEN must contain at least 32 characters')
    return configured


CONTROL_TOKEN = _load_control_token()


@app.before_request
def require_control_authentication():
    supplied = request.headers.get('Authorization', '')
    expected = f'Bearer {CONTROL_TOKEN}'
    if not hmac.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8')):
        return jsonify({'error': 'unauthorized'}), 401


def site_port(site: str) -> int:
    return BASE_PORT + SITES.index(site)


def pid_path(site: str) -> Path:
    return PID_DIR / f'{site}.pid'


def read_pid_record(site: str):
    identity_path = pid_path(site)
    if identity_path.is_symlink() or (identity_path.exists() and not identity_path.is_file()):
        return None
    try:
        record = json.loads(identity_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(record, dict) or set(record) != {'pid', 'start_time', 'site', 'port'}:
        return None
    if record.get('site') != site or record.get('port') != site_port(site):
        return None
    if not isinstance(record.get('pid'), int) or record['pid'] <= 1:
        return None
    if not isinstance(record.get('start_time'), int) or record['start_time'] <= 0:
        return None
    return record


def read_pid(site: str):
    record = read_pid_record(site)
    return record['pid'] if record else None


def _process_stat(pid: int):
    try:
        data = Path(f'/proc/{pid}/stat').read_bytes()
        # /proc/<pid>/stat: "<pid> (<comm>) <state> ...". The command may
        # contain spaces or parentheses, so parse fields after the final ')'.
        fields = data[data.rindex(b')') + 2:].split()
        return fields[0], int(fields[19])
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
        return None


def is_alive(pid) -> bool:
    """True iff a non-zombie process with this PID exists."""
    if not pid:
        return False
    status = _process_stat(pid)
    return status is not None and status[0] not in (b'Z', b'X')


def process_matches_site(site: str, record: dict) -> bool:
    """Bind a PID record to the expected live supervisor identity."""
    pid = record['pid']
    status = _process_stat(pid)
    if status is None or status[0] in (b'Z', b'X') or status[1] != record['start_time']:
        return False
    try:
        if os.getpgid(pid) != pid:
            return False
        arguments = Path(f'/proc/{pid}/cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return False
    expected_tail = [b'/opt/site_runner.py', site.encode(), str(site_port(site)).encode()]
    return len(arguments) >= 4 and arguments[-3:] == expected_tail


def wait_for_pid_record(site: str, expected_pid: int, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = read_pid_record(site)
        if record and record['pid'] == expected_pid and process_matches_site(site, record):
            return record
        if not is_alive(expected_pid):
            break
        time.sleep(0.01)
    raise RuntimeError(f'{site} supervisor {expected_pid} did not publish a valid identity record')


def reap_exited_children() -> None:
    """Reap every exited direct child, including re-parented Flask workers."""
    with _reap_lock:
        while True:
            try:
                pid, _status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid <= 0:
                return


def kill_site(site: str, reap_grace: float = REAP_GRACE_SECS):
    record = read_pid_record(site)
    with _site_procs_lock:
        tracked_proc = _site_procs.get(site)
    if record is None:
        if pid_path(site).exists() or pid_path(site).is_symlink():
            raise RuntimeError(f'invalid PID identity record for {site}; refusing to reset')
        if tracked_proc is not None and tracked_proc.poll() is None:
            raise RuntimeError(f'missing PID identity record for live {site} supervisor')
        return
    pid = record['pid']
    if not is_alive(pid):
        pid_path(site).unlink(missing_ok=True)
        reap_exited_children()
        return
    if not process_matches_site(site, record):
        raise RuntimeError(f'PID identity mismatch for {site} supervisor {pid}; refusing to signal')
    # SIGKILL the validated process group (supervisor + Flask child). Without
    # killpg the Flask child would re-parent to init and keep the port.
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    # Reap supervisors created through Popen and boot-time supervisors that
    # became direct children when websyn_start.sh exec'd this control process.
    with _site_procs_lock:
        proc = _site_procs.pop(site, None)
    if proc is not None:
        try:
            proc.wait(timeout=reap_grace)
        except subprocess.TimeoutExpired:
            pass
    reap_exited_children()
    deadline = time.monotonic() + reap_grace
    while time.monotonic() < deadline:
        if not is_alive(pid):
            pid_path(site).unlink(missing_ok=True)
            for _ in range(10):
                reap_exited_children()
                time.sleep(0.01)
            return
        time.sleep(0.01)
    raise RuntimeError(f'failed to stop {site} process group {pid}')


def reset_db(site: str):
    site_dir = Path(WEBSYN_DIR) / site
    inst = site_dir / 'instance'
    seed = site_dir / 'instance_seed'
    if not seed.is_dir() or not any(seed.iterdir()):
        raise RuntimeError(f'missing or empty seed directory for {site}')
    staging = Path(tempfile.mkdtemp(prefix='.instance-reset-', dir=site_dir))
    backup = staging.with_name(staging.name + '-backup')
    shutil.rmtree(staging)
    old_moved = False
    installed = False
    try:
        shutil.copytree(seed, staging)
        if inst.exists():
            inst.rename(backup)
            old_moved = True
        staging.rename(inst)
        installed = True
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if old_moved and backup.exists():
            if inst.exists():
                shutil.rmtree(inst, ignore_errors=True)
            backup.rename(inst)
        raise
    cleanup_error = None
    if installed and backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError as error:
            cleanup_error = f'{type(error).__name__}: {error}'
    return cleanup_error


def start_site(site: str) -> int:
    port = site_port(site)
    log = open(f'/tmp/websyn_{site}.log', 'a', buffering=1)
    log.write(f'\n[control-server] respawn at {time.strftime("%F %T")}\n')
    # Run Flask under /opt/site_runner.py supervisor — see that file for
    # the rationale. start_new_session=True is redundant with the supervisor's
    # own setsid() but harmless and gives us a session leader from the very
    # first instant.
    site_environment = os.environ.copy()
    site_environment.pop('WEBSYN_CONTROL_TOKEN', None)
    pid_path(site).unlink(missing_ok=True)
    try:
        proc = subprocess.Popen(
            ['python3', '/opt/site_runner.py', site, str(port)],
            stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
            env=site_environment,
        )
    finally:
        log.close()
    with _site_procs_lock:
        _site_procs[site] = proc
    try:
        wait_for_pid_record(site, proc.pid)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=REAP_GRACE_SECS)
        with _site_procs_lock:
            _site_procs.pop(site, None)
        raise
    return proc.pid


def wait_ready(site: str, timeout: float = 60.0) -> bool:
    port = site_port(site)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2).read(1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def reset_one(site: str) -> dict:
    with _site_locks[site]:
        kill_site(site)
        try:
            cleanup_error = reset_db(site)
        except Exception:
            pid = start_site(site)
            recovery_ready = wait_ready(site)
            raise RuntimeError(f'reset failed; prior state restart ready={recovery_ready}')
        pid = start_site(site)
        ready = wait_ready(site)
    result = {'site': site, 'pid': pid, 'ready': ready}
    if cleanup_error:
        result['cleanup_warning'] = cleanup_error
    return result


def restart_one(site: str) -> dict:
    """Just respawn — no DB wipe."""
    with _site_locks[site]:
        kill_site(site)
        pid = start_site(site)
        ready = wait_ready(site)
    return {'site': site, 'pid': pid, 'ready': ready,
            'note': 'restart only, DB not reset'}


@app.route('/health')
def health():
    reap_exited_children()

    def status(site):
        record = read_pid_record(site)
        pid = record['pid'] if record else None
        alive = bool(record and process_matches_site(site, record))
        ready = False
        if alive:
            try:
                with urllib.request.urlopen(
                        f'http://127.0.0.1:{site_port(site)}/', timeout=1) as response:
                    ready = response.status < 500
            except Exception:
                ready = False
        return site, {'pid': pid, 'alive': alive, 'ready': ready,
                      'port': site_port(site)}

    with ThreadPoolExecutor(max_workers=len(SITES)) as executor:
        sites = dict(executor.map(status, SITES))
    all_ok = all(item['alive'] and item['ready'] for item in sites.values())
    return jsonify({'ok': all_ok, 'sites': sites}), (200 if all_ok else 503)


@app.route('/reset/<site>', methods=['POST'])
def reset_site(site):
    if site not in SITES:
        return jsonify({'error': f'unknown site: {site}',
                        'valid_sites': SITES}), 404
    try:
        result = reset_one(site)
    except Exception as error:
        return jsonify({'site': site, 'ready': False, 'error': f'{type(error).__name__}: {error}'}), 503
    return jsonify(result), (200 if result['ready'] else 503)


@app.route('/reset-all', methods=['POST'])
def reset_all():
    def reset_with_result(site):
        try:
            return reset_one(site)
        except Exception as error:
            return {
                'site': site,
                'ready': False,
                'error': f'{type(error).__name__}: {error}',
            }

    with ThreadPoolExecutor(max_workers=len(SITES)) as executor:
        results = list(executor.map(reset_with_result, SITES))
    out = {result['site']: result for result in results}
    ok = all(result.get('ready') for result in results)
    return jsonify({'ok': ok, 'partial': not ok, 'sites': out}), (200 if ok else 503)


@app.route('/restart/<site>', methods=['POST'])
def restart_site(site):
    if site not in SITES:
        return jsonify({'error': f'unknown site: {site}'}), 404
    try:
        result = restart_one(site)
    except Exception as error:
        return jsonify({'site': site, 'ready': False, 'error': f'{type(error).__name__}: {error}'}), 503
    return jsonify(result), (200 if result['ready'] else 503)


if __name__ == '__main__':
    if '--stop-sites' in sys.argv:
        failures = []
        for configured_site in SITES:
            try:
                kill_site(configured_site)
            except Exception as error:
                failures.append(f'{configured_site}: {type(error).__name__}: {error}')
        if failures:
            raise SystemExit('failed to stop validated site supervisors: ' + '; '.join(failures))
        raise SystemExit(0)
    port = int(os.environ.get('CONTROL_PORT', 8101))
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    app.run(host='0.0.0.0', port=port, debug=False,
            use_reloader=False, threaded=True)
