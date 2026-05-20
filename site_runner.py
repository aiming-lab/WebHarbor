"""Supervisor wrapper for one Flask site.

Why this exists: Werkzeug's threaded serve_forever() doesn't honor SIGTERM
(installs / shadows handlers, blocks in C-level select). We can't kill Flask
cleanly via SIGTERM. So we run Flask as a child subprocess of this thin
supervisor, and the supervisor itself is the PID that control_server tracks.
SIGTERM to the supervisor → supervisor SIGKILLs the child → exits.
The supervisor's main loop is os.waitpid() which IS interruptible by signals.

Usage: python3 /opt/site_runner.py <site_name> <port>
"""
import os
import signal
import subprocess
import sys


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

    base_dir = '/opt/WebSyn' if os.path.exists('/opt/WebSyn') else '/home/winterandchaiyun/misc/WebHarbor/sites'
    child = subprocess.Popen(
        ['python3', '-c',
         f"from app import app; "
         f"app.run(host='0.0.0.0', port={port}, "
         f"debug=False, use_reloader=False, threaded=True)"],
        cwd=f'{base_dir}/{site}',
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
    sys.exit(rc)


if __name__ == '__main__':
    main()
