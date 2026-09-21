"""Generated-asset gate for the WebMD Doctor mirror (317 PNGs)."""
from __future__ import annotations

import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


def test_generated_asset_inventory_verifies():
    sys.path.insert(0, str(SITE))
    try:
        import check_generated_assets

        assert check_generated_assets.verify() == 317
    finally:
        sys.path.pop(0)
