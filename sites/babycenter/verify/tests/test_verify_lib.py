from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_lib import has_number, is_local_url, paths_in_order, phrase  # noqa: E402


def test_phrase_accepts_punctuation_and_case_but_rejects_negation() -> None:
    assert phrase("The result is PAPP-A.", "papp a")
    assert phrase("It is week 18!", "week 18")
    assert not phrase("It is not week 18.", "week 18")


def test_number_accepts_digits_and_common_number_words() -> None:
    assert has_number("There are 3 saved items.", 3)
    assert has_number("There are three saved items.", 3)
    assert not has_number("There are 30 saved items.", 3)


def test_url_and_order_checks_fail_closed() -> None:
    assert is_local_url("http://127.0.0.1:41042/account")
    assert not is_local_url("https://example.com/account")
    trajectory = {
        "start_url": "http://localhost:40026/",
        "steps": [
            {"url": "http://localhost:40026/login", "url_after": "http://localhost:40026/account"},
            {"url": "http://localhost:40026/account"},
        ],
    }
    assert paths_in_order(trajectory, ["/login", "/account"])
    assert not paths_in_order(trajectory, ["/account", "/login"])
