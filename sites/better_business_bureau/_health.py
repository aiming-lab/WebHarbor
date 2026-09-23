"""Per-site health probe (optional, called by control_server)."""
def health():
    return {"ok": True, "site": "better_business_bureau"}
