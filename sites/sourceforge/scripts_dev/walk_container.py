"""Walk the 21 tasks against the running WebHarbor container.

Same walks and step-counting convention as walk_tasks.py, but per-task
state resets go through the control plane (POST /reset/sourceforge with
the bearer token) instead of a local seed copy + dev-server restart, and
the site under test is the container port (default 46093 -> 40094).

Run:  SF_CONTROL=http://127.0.0.1:47093 \
      SF_TOKEN_FILE=/path/to/.control_token \
      python3 scripts_dev/walk_container.py [task_ids ...]
"""
import os
import sys
import time
import urllib.request

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import walk_tasks  # noqa: E402

CONTROL = os.environ.get("SF_CONTROL", "http://127.0.0.1:47093")
TOKEN_FILE = os.environ.get("SF_TOKEN_FILE",
                            "/data/zhaoyang-user-projects/websyn/"
                            "wh-sourceforge-fix-wt/.control_token")


def reset_instance():
    """Reset the container site to the frozen seed via the control plane."""
    token = open(TOKEN_FILE).read().strip()
    req = urllib.request.Request(
        f"{CONTROL}/reset/sourceforge", method="POST",
        headers={"Authorization": f"Bearer {token}"})
    for attempt in range(5):  # the control plane can 503 briefly on races
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
            # wait until the site answers again
            for _ in range(40):
                try:
                    urllib.request.urlopen(f"{walk_tasks.M}/_health", timeout=2).read()
                    return
                except Exception:
                    time.sleep(0.4)
            raise RuntimeError("site did not come back after reset")
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < 4:
                time.sleep(5)
                continue
            raise


def dev_server_ctl(action):
    """The container's site process is managed by the control plane."""
    if action == "stop":
        return
    reset_instance()


if __name__ == "__main__":
    walk_tasks.reset_instance = reset_instance
    walk_tasks.dev_server_ctl = dev_server_ctl
    walk_tasks.main()
