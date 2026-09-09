"""Per-site health probe (optional, called by control_server)."""
def health():
    return {"ok": True, "site": "ted", "paths": ["/", "/talks", "/search", "/events"]}
