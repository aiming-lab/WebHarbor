from __future__ import annotations

import sysconfig
from pathlib import Path


CDP_MARKER = 'os.environ.get("AWMEVAL_CDP_URL")'


def _replace_exact(source: str, old: str, new: str, *, count: int, description: str) -> str:
    if source.count(new) == count and source.count(old) == 0:
        return source
    if source.count(old) != count:
        raise RuntimeError(f"browser-use 0.11.13 {description} source does not match the pinned compatibility patch")
    return source.replace(old, new)


def patch_browser_use(purelib: Path) -> None:
    skill_cli = purelib / "browser_use" / "skill_cli"
    sessions_path = skill_cli / "sessions.py"
    sessions = sessions_path.read_text(encoding="utf-8")
    if CDP_MARKER not in sessions:
        sessions = _replace_exact(sessions, "import logging\n", "import logging\nimport os\n", count=1, description="sessions import")
        sessions = _replace_exact(
            sessions,
            "\t\tbrowser_session = await create_browser_session(browser_mode, headed, profile)\n\t\tawait browser_session.start()\n\n\t\tsession_info = SessionInfo(\n",
            "\t\tbrowser_session = await create_browser_session(browser_mode, headed, profile)\n\t\tawait browser_session.start()\n\t\tif os.environ.get(\"AWMEVAL_CDP_URL\"):\n\t\t\ttabs = await browser_session.get_tabs()\n\t\t\tstart_url = os.environ.get(\"AWMEVAL_START_URL\", \"\")\n\t\t\ttarget = next((tab for tab in tabs if start_url and tab.url == start_url), None)\n\t\t\tif target is None:\n\t\t\t\ttarget = next((tab for tab in tabs if tab.url.startswith((\"http://\", \"https://\"))), None)\n\t\t\tif target is not None:\n\t\t\t\tcdp_session = await browser_session.get_or_create_cdp_session(target.target_id, focus=True)\n\t\t\t\tawait cdp_session.cdp_client.send.Page.navigate(params={\"url\": target.url}, session_id=cdp_session.session_id)\n\n\t\tsession_info = SessionInfo(\n",
            count=1,
            description="session initialization",
        )
        sessions = _replace_exact(
            sessions,
            "\tfrom browser_use.skill_cli.install_config import get_mode_unavailable_error, is_mode_available\n\n\t# Validate mode is available based on installation config\n",
            "\tfrom browser_use.skill_cli.install_config import get_mode_unavailable_error, is_mode_available\n\n\tcdp_url = os.environ.get(\"AWMEVAL_CDP_URL\")\n\tif cdp_url:\n\t\treturn BrowserSession(cdp_url=cdp_url)\n\n\t# Validate mode is available based on installation config\n",
            count=1,
            description="CDP session selection",
        )
    if CDP_MARKER not in sessions:
        raise RuntimeError("browser-use 0.11.13 CDP compatibility patch is missing")
    sessions = _replace_exact(
        sessions,
        'startswith(("http://", "https://"))',
        'startswith(("http://", "https://", "chrome://"))',
        count=1,
        description="session target scheme",
    )
    sessions_path.write_text(sessions, encoding="utf-8")

    browser_commands_path = skill_cli / "commands" / "browser.py"
    browser_commands = browser_commands_path.read_text(encoding="utf-8")
    browser_commands = _replace_exact(
        browser_commands,
        "startswith(('http://', 'https://', 'file://'))",
        "startswith(('http://', 'https://', 'file://', 'chrome://'))",
        count=1,
        description="browser open scheme",
    )
    browser_commands_path.write_text(browser_commands, encoding="utf-8")

    direct_path = skill_cli / "direct.py"
    direct = direct_path.read_text(encoding="utf-8")
    direct = _replace_exact(
        direct,
        "startswith(('http://', 'https://'))",
        "startswith(('http://', 'https://', 'chrome://'))",
        count=4,
        description="direct target scheme",
    )
    direct = _replace_exact(
        direct,
        "startswith(('http://', 'https://', 'file://'))",
        "startswith(('http://', 'https://', 'file://', 'chrome://'))",
        count=1,
        description="direct open scheme",
    )
    direct_path.write_text(direct, encoding="utf-8")


if __name__ == "__main__":
    patch_browser_use(Path(sysconfig.get_paths()["purelib"]))
