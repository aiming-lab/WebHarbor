"""WCAG contrast coverage for the FedEx mirror's real rendered states.

The palette is brand-derived, and two of its original pairings failed contrast:
white on FedEx orange measured 2.936:1 for 16px/700 button labels, which is below
the large-text threshold and so needed 4.5:1, and the focus outline measured
2.490:1 against the purple header, below the 3:1 non-text threshold. The action
orange and the focus ring are therefore chosen for their measured ratios, and this
module recomputes those ratios from the stylesheet so the choice cannot silently
regress.

Ratios use the WCAG 2.1 relative-luminance formula. Thresholds are 4.5:1 for
normal text, 3:1 for large text (24px, or 18.66px at weight 700 and above) and
3:1 for non-text contrast such as a focus indicator or a control boundary.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = SITE_ROOT / "static" / "css" / "main.css"

NORMAL_TEXT = 4.5
LARGE_TEXT = 3.0
NON_TEXT = 3.0


def channel(value: float) -> float:
    value /= 255.0
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = (channel(component) for component in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lighter = max(luminance(first), luminance(second))
    darker = min(luminance(first), luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


def parse_hex(text: str) -> tuple[int, int, int]:
    value = text.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise AssertionError(f"not a 3- or 6-digit hex color: {text!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


class PaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        root = re.search(r":root\{(.*?)\}", cls.css, re.DOTALL)
        assert root is not None, "main.css declares no :root block"
        cls.tokens = {
            name: parse_hex(value)
            for name, value in re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,6})", root.group(1))
        }

    def token(self, name: str) -> tuple[int, int, int]:
        self.assertIn(name, self.tokens, f"main.css declares no {name} token")
        return self.tokens[name]

    def test_action_button_label_contrast(self) -> None:
        """White labels sit on the action orange at 16px/700, which is normal text."""
        surface = self.token("--fedex-orange-action")
        ratio = contrast((255, 255, 255), surface)
        self.assertGreaterEqual(
            ratio, NORMAL_TEXT,
            f"white on --fedex-orange-action is {ratio:.3f}:1, below {NORMAL_TEXT}:1")
        # Hovering darkens the surface, which only raises the ratio; assert that
        # the declared hover treatment cannot invert it.
        self.assertIn("filter:brightness(.95)", self.css,
                      "the button hover rule changed; re-verify its contrast")

    def light_surfaces(self) -> dict[str, tuple[int, int, int]]:
        """Return every light background the stylesheet paints.

        The action orange is used as a text color in the outline button variant,
        so it has to clear 4.5:1 on every surface that variant can land on, not
        just on --surface. Deriving the set from the stylesheet means a newly
        added light panel is covered automatically instead of being missed.
        """
        surfaces = {}
        # A literal hex background.
        for value in re.findall(r"background(?:-color)?:\s*(#[0-9a-fA-F]{3,6})\b", self.css):
            try:
                rgb = parse_hex(value)
            except AssertionError:
                continue
            if luminance(rgb) > 0.5:
                surfaces[value.lower()] = rgb
        # A background expressed through a token, resolved to its hex value. Only
        # declarations that paint a background count: border and outline tokens
        # such as --line are hairlines that no text ever sits on.
        for name in re.findall(r"background(?:-color)?:\s*var\((--[a-z0-9-]+)\)", self.css):
            if name in self.tokens and luminance(self.tokens[name]) > 0.5:
                surfaces[name] = self.tokens[name]
        return surfaces

    def test_action_orange_is_legible_as_text_on_every_light_surface(self) -> None:
        """The outline variant sets the action orange as text, on surfaces other than white."""
        ink = self.token("--fedex-orange-action")
        surfaces = self.light_surfaces()
        self.assertLessEqual(
            4, len(surfaces),
            "expected the stylesheet to declare several light surfaces; the parser may have regressed")
        worst = None
        for name, rgb in sorted(surfaces.items(), key=lambda item: luminance(item[1])):
            ratio = contrast(ink, rgb)
            with self.subTest(surface=name):
                self.assertGreaterEqual(
                    ratio, NORMAL_TEXT,
                    f"--fedex-orange-action as text on {name} is {ratio:.3f}:1, "
                    f"below {NORMAL_TEXT}:1")
            if worst is None or ratio < worst[1]:
                worst = (name, ratio)
        # The border of the outline variant must also identify the control.
        self.assertGreaterEqual(worst[1], NON_TEXT,
                                "the outline border must clear the non-text threshold")

    def test_focus_indicator_contrast_in_both_contexts(self) -> None:
        """The ring appears on the purple header and on white pages, so both must clear 3:1."""
        ring = self.token("--focus-ring")
        for name, background in (("--surface", self.token("--surface")),
                                 ("--fedex-purple", self.token("--fedex-purple")),
                                 ("--fedex-purple-deep", self.token("--fedex-purple-deep"))):
            with self.subTest(against=name):
                ratio = contrast(ring, background)
                self.assertGreaterEqual(
                    ratio, NON_TEXT,
                    f"--focus-ring on {name} is {ratio:.3f}:1, below the {NON_TEXT}:1 "
                    "focus-indicator threshold")

    def test_other_text_pairings_still_pass(self) -> None:
        """The pairs that already passed are pinned so a palette edit cannot break them."""
        white = (255, 255, 255)
        page = self.token("--surface")
        cases = [
            ("--ink on --surface", self.token("--ink"), page, NORMAL_TEXT),
            ("--muted on --surface", self.token("--muted"), page, NORMAL_TEXT),
            ("white on --fedex-purple", white, self.token("--fedex-purple"), NORMAL_TEXT),
            ("white on --fedex-purple-deep", white, self.token("--fedex-purple-deep"), NORMAL_TEXT),
            ("white on --success", white, self.token("--success"), NORMAL_TEXT),
            ("white on --warning", white, self.token("--warning"), NORMAL_TEXT),
            ("white on --danger", white, self.token("--danger"), NORMAL_TEXT),
        ]
        for label, ink, background, threshold in cases:
            with self.subTest(pair=label):
                ratio = contrast(ink, background)
                self.assertGreaterEqual(ratio, threshold,
                                        f"{label} is {ratio:.3f}:1, below {threshold}:1")

    def test_brand_orange_is_restricted_to_decorative_use(self) -> None:
        """The original brand orange may not carry text or identify a control.

        It is kept only where no contrast requirement applies, so this enumerates
        every rule that still references it and pins that set.
        """
        brand = self.token("--fedex-orange")
        action = self.token("--fedex-orange-action")
        self.assertLess(contrast((255, 255, 255), brand), NORMAL_TEXT,
                        "if the brand orange ever clears 4.5:1 this restriction is unnecessary")
        self.assertNotEqual(brand, action, "the accessible action color must differ from the brand accent")

        users = []
        for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", self.css):
            selector, body = rule
            if "var(--fedex-orange)" in body:
                users.append((selector.strip()[:60], body.strip()[:120]))
        self.assertEqual(
            [".form-errors"], [selector for selector, _body in users],
            f"brand orange is used beyond decorative accents: {users}")
        for _selector, body in users:
            self.assertNotIn("color:", body, "brand orange must not be a text color")
            self.assertIn("border-left", body,
                          "brand orange must stay a decorative accent border")

    def test_action_rules_reference_the_accessible_token(self) -> None:
        """The button rules must actually use the accessible token, not merely define it."""
        expectations = {
            r"\.button,button,input\[type=submit\][^{}]*": "background:var(--fedex-orange-action)",
            r"\.button-secondary,\.button-outline[^{}]*": "color:var(--fedex-orange-action)",
            r"\.button-primary[^{}]*": "background:var(--fedex-orange-action)",
        }
        for pattern, expected in expectations.items():
            match = re.search(pattern + r"\{(.*?)\}", self.css, re.DOTALL)
            self.assertIsNotNone(match, f"no rule matches {pattern}")
            self.assertIn(expected, match.group(1),
                          f"{pattern} does not use {expected}: {match.group(1)[:120]}")

    def test_focus_rule_uses_the_focus_ring_token(self) -> None:
        match = re.search(r":focus-visible\{(.*?)\}", self.css, re.DOTALL)
        self.assertIsNotNone(match, "no global :focus-visible rule")
        self.assertIn("var(--focus-ring)", match.group(1))


if __name__ == "__main__":
    unittest.main()
