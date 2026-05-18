"""Simple health probe for the PhET Simulations mirror.

Returned by the /_health endpoint. The control plane only inspects HTTP
status, so any 2xx response with a JSON body is sufficient — the payload
shape mirrors the scaffold default and is also surfaced verbatim to
human reviewers.
"""


def health():
    return {"ok": True, "site": "phet_simulations"}
