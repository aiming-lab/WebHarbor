"""Per-site image references.

Published images are ``[registry/]wildawm/webharbor:<site>[-v<N>]``; locally
built ones are ``webharbor-site-<site>:<tag>``. The merged-image tags
(``latest``, ``all-v<N>``) name no single site. Kept dependency-free so
validation scripts can import it without the Harbor runtime.
"""
from __future__ import annotations

import re


def site_from_image(image: str) -> str | None:
    """Site name from a per-site image reference, or None if it names none."""
    if image.startswith("webharbor-site-") and ":" in image:
        return image[len("webharbor-site-"):].split(":", 1)[0]
    repo, sep, tag = image.rpartition(":")
    if not sep or repo.rsplit("/", 1)[-1] != "webharbor":
        return None
    m = re.fullmatch(r"([a-z0-9_]+?)(?:-v\d+)?", tag)
    if not m or m.group(1) in {"latest", "all"}:
        return None
    return m.group(1)
