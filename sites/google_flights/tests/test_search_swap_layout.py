"""Homepage swap-button layout contract (issue #20).

The swap control must sit on the origin/destination seam, not the midpoint of
the whole search row (origin + destination + dates). These checks are static
so they do not need Flask, a seed DB, or a browser.

Run with: python3 -m pytest sites/google_flights/tests -q
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
INDEX = SITE / "templates" / "index.html"
CSS = SITE / "static" / "css" / "main.css"


class _SearchFormParser(HTMLParser):
    """Collect the homepage search-row tree: route group vs dates group."""

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[tuple[str, frozenset[str]]] = []
        self.row_children: list[str] = []
        self.route_children: list[str] = []
        self.dates_inside_route = False
        self._in_row = 0
        self._in_route = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = frozenset((dict(attrs).get("class") or "").split())
        if "search-row" in classes:
            self._in_row += 1
        if "search-route-fields" in classes:
            self._in_route += 1
            if self._in_row == 1:
                self.row_children.append("search-route-fields")
        elif self._in_row == 1 and self._in_route == 0:
            for name in ("search-dates", "search-swap", "search-field-from", "search-field-to"):
                if name in classes:
                    self.row_children.append(name)
        if self._in_route:
            if "search-swap" in classes:
                self.route_children.append("search-swap")
            if "search-field-from" in classes:
                self.route_children.append("from")
            if "search-field-to" in classes:
                self.route_children.append("to")
            if "search-dates" in classes:
                self.dates_inside_route = True
        # Keep a stack only for tags that have end tags so void <input> does not
        # confuse the route/row depth counters.
        if tag not in {"input", "img", "br", "hr", "meta", "link"}:
            self._stack.append((tag, classes))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] != tag:
                continue
            classes = self._stack[i][1]
            if "search-row" in classes:
                self._in_row = max(0, self._in_row - 1)
            if "search-route-fields" in classes:
                self._in_route = max(0, self._in_route - 1)
            del self._stack[i]
            break


def _rule_body(css: str, selector: str) -> str:
    """Return the first `{...}` body for an exact selector (no media-query split)."""
    pattern = re.compile(re.escape(selector) + r"\s*\{([^}]+)\}")
    match = pattern.search(css)
    assert match, f"missing CSS rule for {selector!r}"
    return match.group(1)


def _mobile_block(css: str) -> str:
    match = re.search(r"@media \(max-width:\s*768px\)\s*\{", css)
    assert match, "missing @media (max-width: 768px) block"
    start = match.end()
    depth = 1
    i = start
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return css[start : i - 1]


def test_origin_destination_are_grouped_apart_from_dates():
    parser = _SearchFormParser()
    parser.feed(INDEX.read_text())
    assert parser.row_children == ["search-route-fields", "search-dates"], parser.row_children
    assert parser.route_children == ["from", "search-swap", "to"], parser.route_children
    assert not parser.dates_inside_route


def test_swap_is_positioned_on_the_route_group_seam():
    css = CSS.read_text()
    row = _rule_body(css, ".search-row")
    route = _rule_body(css, ".search-route-fields")
    swap = _rule_body(css, ".search-swap")

    assert "position: relative" not in row
    assert "position: relative" in route
    assert "grid-template-columns" in route
    assert "position: absolute" in swap
    assert "left: 50%" in swap
    assert "top: 50%" in swap


def test_mobile_hides_swap_and_stacks_route_fields():
    mobile = _mobile_block(CSS.read_text())
    assert ".search-swap { display: none; }" in mobile
    assert "flex-direction: column" in mobile
    assert ".search-route-fields" in mobile


if __name__ == "__main__":
    test_origin_destination_are_grouped_apart_from_dates()
    test_swap_is_positioned_on_the_route_group_seam()
    test_mobile_hides_swap_and_stacks_route_fields()
    print("ok")
