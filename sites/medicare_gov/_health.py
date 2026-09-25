"""Per-site health probe (called by control_server)."""


def health():
    return {"ok": True, "site": "medicare_gov"}
