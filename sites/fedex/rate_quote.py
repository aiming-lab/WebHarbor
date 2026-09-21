"""Issue and verify signed rate-estimate request facts.

The signing key below is a public integrity tag, not a credential. It exists so a
rate-estimate link can be reopened without re-submitting the form, and so a
verifier can confirm from a recorded trajectory that the requested lane, weight
and package type were really submitted. Nothing secret depends on it: every price
is recomputed server-side from the seeded `service_levels` rows, and the token
carries no identity, permission or state. It must stay stable across processes
(the site and its verifiers are separate processes), which is why it is a module
constant rather than the per-process `SECRET_KEY`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
from dataclasses import asdict, dataclass


SIGNING_KEY = b"webharbor-fedex-rate-quote-v1"

# Bounds mirrored from the application so a token cannot carry a value the form
# would have rejected.
MIN_WEIGHT_LB = 0.1
MAX_WEIGHT_LB = 1000.0
VALID_STATES = frozenset({
    "CA", "WA", "TX", "FL", "NY", "GA", "IL", "PA",
    "MA", "CO", "AZ", "OR", "NC", "OH", "MI", "VA", "DC",
})
VALID_PACKAGE_TYPES = frozenset({"Envelope", "Box", "Tube", "Pak", "Freight pallet"})


@dataclass(frozen=True)
class QuoteRequest:
    origin_state: str
    destination_state: str
    weight_lb: float
    package_type: str


def issue_quote_token(quote: QuoteRequest) -> str:
    payload = json.dumps(asdict(quote), sort_keys=True, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(SIGNING_KEY, encoded, hashlib.sha256).hexdigest().encode()
    return (encoded + b"." + signature).decode()


def verify_quote_token(token: str) -> QuoteRequest | None:
    """Return the decoded request, or None when the token is unusable.

    A token is rejected when its signature does not match, when its payload is not
    the expected object shape, or when its values fall outside the bounds the form
    itself enforces.
    """
    if not isinstance(token, str) or not token or len(token) > 400:
        return None
    try:
        encoded, supplied_signature = token.encode().rsplit(b".", 1)
        expected_signature = hmac.new(SIGNING_KEY, encoded, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        padding = b"=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if not isinstance(payload, dict):
            return None
        origin_state = str(payload["origin_state"])
        destination_state = str(payload["destination_state"])
        package_type = str(payload["package_type"])
        weight_lb = float(payload["weight_lb"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if origin_state not in VALID_STATES or destination_state not in VALID_STATES:
        return None
    if package_type not in VALID_PACKAGE_TYPES:
        return None
    if not math.isfinite(weight_lb) or not MIN_WEIGHT_LB <= weight_lb <= MAX_WEIGHT_LB:
        return None
    return QuoteRequest(
        origin_state=origin_state,
        destination_state=destination_state,
        weight_lb=weight_lb,
        package_type=package_type,
    )
