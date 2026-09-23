from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_lib import is_local_url, paths_in_order  # noqa: E402
from answers import fact, integer, norm  # noqa: E402


def test_phrase_accepts_punctuation_and_case_but_rejects_negation() -> None:
    assert norm("Free β-hCG") == norm("free beta-hCG")
    assert fact("A deliberate pincer grasp.", r"pincer grasp")
    assert not fact("It is not a pincer grasp.", r"pincer grasp")


def test_number_requires_the_bound_json_value() -> None:
    assert integer(3, 3)
    assert not integer("There are 30 items. Reference 3.", 3)
    assert not integer(True, 1)


def test_url_and_order_checks_fail_closed() -> None:
    assert is_local_url("http://127.0.0.1:41042/account")
    assert not is_local_url("https://example.com/account")
    trajectory = {
        "start_url": "http://localhost:40026/",
        "steps": [
            {
                "url": "http://localhost:40026/login",
                "url_after": "http://localhost:40026/account",
            },
            {"url": "http://localhost:40026/account"},
        ],
    }
    assert paths_in_order(trajectory, ["/login", "/account"])
    assert not paths_in_order(trajectory, ["/account", "/login"])
