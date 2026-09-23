"""Supervisor wrapper for one Flask site.

Why this exists: Werkzeug's threaded serve_forever() doesn't honor SIGTERM
(installs / shadows handlers, blocks in C-level select). We can't kill Flask
cleanly via SIGTERM. So we run Flask as a child subprocess of this thin
supervisor, and the supervisor itself is the PID that control_server tracks.
SIGTERM to the supervisor → supervisor SIGKILLs the child → exits.
The supervisor's main loop is os.waitpid() which IS interruptible by signals.

Usage: python3 /opt/site_runner.py <site_name> <port>
"""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path


PID_DIR = Path('/tmp/websyn_pids')


def _process_start_time(pid: int) -> int:
    data = Path(f'/proc/{pid}/stat').read_bytes()
    fields_after_comm = data[data.rindex(b')') + 2:].split()
    return int(fields_after_comm[19])


def _write_pid_record(site: str, port: int) -> dict:
    pid = os.getpid()
    if os.getpgid(pid) != pid:
        raise RuntimeError(f'site supervisor {pid} is not its process-group leader')
    record = {'pid': pid, 'start_time': _process_start_time(pid), 'site': site, 'port': port}
    PID_DIR.mkdir(parents=True, exist_ok=True)
    destination = PID_DIR / f'{site}.pid'
    temporary = PID_DIR / f'.{site}.{pid}.pid.tmp'
    temporary.write_text(json.dumps(record, sort_keys=True) + '\n')
    os.replace(temporary, destination)
    return record


def main():
    site = sys.argv[1]
    port = int(sys.argv[2])

    # Make this supervisor the session leader so kill_site can SIGKILL the
    # whole process group (supervisor + Flask child) via os.killpg(pid).
    # subprocess.Popen(..., start_new_session=True) already does this when
    # control_server spawns us, but websyn_start.sh's `exec ... &` doesn't,
    # so we self-reparent here. OSError is fine — already a leader.
    try:
        os.setsid()
    except OSError:
        pass

    _write_pid_record(site, port)
    child = None
    try:
        child = subprocess.Popen(
            ['python3', '-c',
             f"from app import app; "
             f"app.run(host='0.0.0.0', port={port}, "
             f"debug=False, use_reloader=False, threaded=True)"],
            cwd=f'/opt/WebSyn/{site}',
        )

        def shutdown(signum, frame):
            try:
                child.kill()  # SIGKILL — Flask won't shut down gracefully anyway
            except ProcessLookupError:
                pass
            os._exit(0)

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        rc = child.wait()
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
        # Keep the identity record after exit. The control plane needs the
        # original process-group ID to prove that no orphan worker survives
        # before it may reset storage or start a replacement.
    sys.exit(rc)


if __name__ == '__main__':
    main()
