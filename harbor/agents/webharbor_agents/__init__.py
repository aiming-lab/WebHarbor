"""WebHarbor-in-Harbor custom agents.

Three harness agents backed by one shared browser inside the task container:

  BrowserUseWebHarbor  GUI/text harness on the browser-use SDK
  OpenCodeWebHarbor    OpenCode CLI harness with live observation capture
  OpenWebRLWebHarbor   OpenWebRL browser_env turn-level harness

All three drive the container's shared chromium (CDP 9222), run as the agent user
(``[agent] user = "ubuntu"``), and leave verifier evidence under /logs/agent.

Run with:
  harbor run -p <dataset> -a webharbor_agents.browseruse:BrowserUseWebHarbor -m <model>
  harbor run -p <dataset> -a webharbor_agents.opencode_webharbor:OpenCodeWebHarbor -m <model>
  harbor run -p <dataset> -a webharbor_agents.openwebrl:OpenWebRLWebHarbor -m <model>

Import path resolution requires this package on PYTHONPATH.
"""

from webharbor_agents.browseruse import BrowserUseWebHarbor
from webharbor_agents.opencode_webharbor import OpenCodeWebHarbor
from webharbor_agents.openwebrl import OpenWebRLWebHarbor

__all__ = ["BrowserUseWebHarbor", "OpenCodeWebHarbor", "OpenWebRLWebHarbor"]
