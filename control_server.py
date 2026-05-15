"""WebSyn control plane on :8101.

Endpoints:
    GET  /health             -> per-site PID + alive status
    POST /reset/<site>       -> SIGTERM site, restore instance/ from instance_seed/, respawn
    POST /reset-all          -> reset every site in parallel
    POST /restart/<site>     -> just respawn (no DB wipe) -- bonus, useful for code reload

PID tracking: each site's PID lives at /tmp/websyn_pids/<site>.pid. websyn_start.sh
writes the initial PIDs; this server overwrites them on respawn.
"""
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, jsonify

SITES = [
    'allrecipes', 'amazon', 'apple', 'arxiv', 'bbc_news', 'booking',
    'github', 'google_flights', 'google_map', 'google_search',
    'huggingface', 'wolfram_alpha', 'cambridge_dictionary',
    'coursera', 'espn', 'carmax',
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

# We tried graceful SIGTERM. Werkzeug's threaded serve_forever() doesn't
# honor it. Since /reset wipes instance/ next anyway, in-flight transactions
# are about to be discarded — graceful shutdown has no value here. SIGKILL
# directly via process group (site_runner.py runs setsid → its pgid == pid).
REAP_GRACE_SECS = 5.0

app = Flask(__name__)


def site_port(site: str) -> int:
    return BASE_PORT + SITES.index(site)


def pid_path(site: str) -> Path:
    return PID_DIR / f'{site}.pid'


def read_pid(site: str):
    try:
        return int(pid_path(site).read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_alive(pid) -> bool:
    """True iff a runnable / sleeping process with this PID exists.
    Returns False for zombies and missing PIDs — that is what the poll
    loops in kill_site need."""
    if not pid:
        return False
    try:
        with open(f'/proc/{pid}/stat', 'rb') as f:
            data = f.read()
        # /proc/<pid>/stat: "<pid> (<comm>) <state> ..."  comm may contain
        # spaces or parens, so split on the LAST ')'.
        rparen = data.rindex(b')')
        state = data[rparen + 2:rparen + 3]
        return state not in (b'Z', b'X')
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return False


def kill_site(site: str, reap_grace: float = REAP_GRACE_SECS):
    pid = read_pid(site)
    if not pid:
        return
    # SIGKILL the whole process group (supervisor + Flask child). Without
    # killpg the Flask child would re-parent to init and keep the port.
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    # If we own a Popen for this supervisor, wait()+reap so it doesn't
    # linger as a zombie. (Supervisors started at boot via websyn_start.sh
    # aren't tracked here; we still adopted them as children via container
    # init, but Python won't reap them — they stay zombies until container
    # exit. That's harmless: is_alive() correctly reports them as dead.)
    proc = _site_procs.pop(site, None)
    if proc is not None:
        try:
            proc.wait(timeout=reap_grace)
        except subprocess.TimeoutExpired:
            pass
    # Belt-and-suspenders: confirm the supervisor is actually dead before
    # returning, even when we don't own the Popen. is_alive() looks at
    # /proc state and returns False for zombies, so this loop exits in ms.
    deadline = time.time() + reap_grace
    while time.time() < deadline:
        if not is_alive(pid):
            return
        time.sleep(0.01)


def reset_db(site: str):
    inst = Path(WEBSYN_DIR) / site / 'instance'
    seed = Path(WEBSYN_DIR) / site / 'instance_seed'
    if inst.exists():
        shutil.rmtree(inst)
    shutil.copytree(seed, inst)


def start_site(site: str) -> int:
    port = site_port(site)
    log = open(f'/tmp/websyn_{site}.log', 'a', buffering=1)
    log.write(f'\n[control-server] respawn at {time.strftime("%F %T")}\n')
    # Run Flask under /opt/site_runner.py supervisor — see that file for
    # the rationale. start_new_session=True is redundant with the supervisor's
    # own setsid() but harmless and gives us a session leader from the very
    # first instant.
    proc = subprocess.Popen(
        ['python3', '/opt/site_runner.py', site, str(port)],
        stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _site_procs[site] = proc
    pid_path(site).write_text(str(proc.pid))
    return proc.pid


def wait_ready(site: str, timeout: float = 30.0) -> bool:
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
        reset_db(site)
        pid = start_site(site)
        ready = wait_ready(site)
    return {'site': site, 'pid': pid, 'ready': ready}


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
    sites = {}
    all_ok = True
    for s in SITES:
        pid = read_pid(s)
        alive = is_alive(pid)
        sites[s] = {'pid': pid, 'alive': alive, 'port': site_port(s)}
        if not alive:
            all_ok = False
    return jsonify({'ok': all_ok, 'sites': sites}), (200 if all_ok else 503)


@app.route('/reset/<site>', methods=['POST'])
def reset_site(site):
    if site not in SITES:
        return jsonify({'error': f'unknown site: {site}',
                        'valid_sites': SITES}), 404
    result = reset_one(site)
    return jsonify(result), (200 if result['ready'] else 503)


@app.route('/reset-all', methods=['POST'])
def reset_all():
    with ThreadPoolExecutor(max_workers=len(SITES)) as ex:
        results = list(ex.map(reset_one, SITES))
    out = {r['site']: r for r in results}
    ok = all(r['ready'] for r in results)
    return jsonify({'ok': ok, 'sites': out}), (200 if ok else 503)


@app.route('/restart/<site>', methods=['POST'])
def restart_site(site):
    if site not in SITES:
        return jsonify({'error': f'unknown site: {site}'}), 404
    result = restart_one(site)
    return jsonify(result), (200 if result['ready'] else 503)


if __name__ == '__main__':
    port = int(os.environ.get('CONTROL_PORT', 8101))
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    app.run(host='0.0.0.0', port=port, debug=False,
            use_reloader=False, threaded=True)
