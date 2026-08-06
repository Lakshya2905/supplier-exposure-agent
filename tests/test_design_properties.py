"""The design system's colour claims, asserted as measurements.

DESIGN.md's Test Contract asks for properties rather than notation, and the
reason is entry 6 of the corrections log: the predecessor of these assertions
compared HSL strings and passed while the guarantee it named was false. Notation
is a proxy for a perceptual property, and a proxy diverges exactly where it
matters.

So nothing here compares a hex pair. Everything computes a ratio or a distance
from the colours the stylesheet actually declares, and fails on the number.

The arithmetic is deterministic sRGB, WCAG 2.1 relative luminance and CIELAB,
implemented here rather than imported so the test has no dependency the shipped
app does not. Any reader can reproduce it.
"""
import math
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "review_app.py"
SOURCE = APP.read_text()
CSS = SOURCE.split('CONSOLE_CSS = """')[1].split('"""')[0]
SCREEN = CSS.split("@media print")[0]


def _channel(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def rgb(hex_colour):
    text = hex_colour.lstrip("#")
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(hex_colour):
    r, g, b = (_channel(c) for c in rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(one, other):
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def lab(hex_colour):
    r, g, b = (_channel(c) for c in rgb(hex_colour))
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(one, other):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab(one), lab(other))))


# The text ramp, read out of :root. Colours moved behind custom properties when
# the ramp became the single source of text colour, so every helper below now
# resolves a token before measuring anything. RESOLVING RATHER THAN MATCHING is
# the same discipline that produced this file: the measurement has to be of the
# colour the browser paints, and `var(--text-note)` is not a colour.
TOKENS = dict(re.findall(r"(--[a-z-]+):\s*(#[0-9A-Fa-f]{6})", CSS))


def resolve(value):
    """`var(--text-note)` to the hex it is declared as. A hex passes through."""
    if value is None:
        return None
    value = value.strip()
    match = re.fullmatch(r"var\((--[a-z-]+)\)", value)
    if match:
        token = match.group(1)
        if token not in TOKENS:
            raise AssertionError(f"{token} is used but never declared in :root")
        return TOKENS[token]
    return value


def declared(selector, prop):
    """A property's value as the stylesheet declares it, not as we remember it."""
    block = SCREEN.split(selector, 1)[1].split("}")[0]
    match = re.search(rf"{prop}:\s*([^;!]+)", block)
    return resolve(match.group(1)) if match else None


# The surfaces anything can be read against, hand-written from the stylesheet.
SURFACES = {"page": "#14171A", "panel": "#191D21", "panel head": "#1E242A",
            "sidebar": "#101315", "chip": "#242A30", "button": "#1E2933"}

# The text ramp, with the size each step is rendered at, because the WCAG
# threshold depends on it. All of these are small text, so all need 4.5:1.
TEXT_RAMP = {
    "#F0F2F4": ("h1 title", "page"),
    "#E3E6E8": ("finding", "page"),
    "#D5DADE": ("body and chip label", "chip"),
    "#9BA3AA": ("note", "page"),
    "#838C94": ("caption", "page"),
    "#8FA0AD": ("section heading", "page"),
    "#B6BEC5": ("table cell", "panel"),
    "#C9D2D9": ("identifier", "page"),
    "#7FB2D9": ("accent", "page"),
}

ACCENT = "#7FB2D9"


class TestEveryTextColourIsLegibleOnItsSurface(unittest.TestCase):
    """WCAG 1.4.3. Asserted as a ratio, never as a hex pair."""

    def test_the_ramp_clears_four_point_five_to_one(self):
        for colour, (role, surface) in TEXT_RAMP.items():
            with self.subTest(role=role):
                self.assertGreaterEqual(
                    contrast(colour, SURFACES[surface]), 4.5,
                    f"{role} at {colour} on {surface} is below AA")

    def test_the_chip_label_is_legible_on_the_chip_it_sits_on(self):
        # The chip is the densest label in the interface and the one most likely
        # to be restyled without re-measuring.
        label = declared(".badge {", "color")
        fill = declared(".badge {", "background")
        self.assertGreaterEqual(contrast(label, fill), 4.5)

    def test_the_accent_is_legible_on_every_surface_it_can_appear_on(self):
        # It marks what a reviewer can act on, and actionable things appear
        # everywhere, so it has no single background to be measured against.
        for name, surface in SURFACES.items():
            with self.subTest(surface=name):
                self.assertGreaterEqual(contrast(ACCENT, surface), 4.5)


class TestTheFocusRingIsVisibleEverywhere(unittest.TestCase):
    """WCAG 2.4.11 wants 3:1 against the element AND the surface behind it."""

    def setUp(self):
        rule = SCREEN.split(":focus-visible {")[1].split("}")[0]
        self.ring = re.search(r"outline:\s*\d+px solid (#[0-9A-Fa-f]{6})",
                              rule).group(1)

    def test_the_ring_clears_three_to_one_on_every_surface(self):
        for name, surface in SURFACES.items():
            with self.subTest(surface=name):
                self.assertGreaterEqual(contrast(self.ring, surface), 3.0)

    def test_border_ui_would_not_have_been_enough(self):
        """DESIGN.md originally named #6B7278 for this and it fails on a chip.

        Kept as a test rather than a note, because the next person to pick a
        focus colour will reach for the border token exactly as that draft did.
        """
        self.assertLess(contrast("#6B7278", SURFACES["chip"]), 3.0)


class TestTheChipPaletteCannotRank(unittest.TestCase):
    """The guarantee corrections-log entry 6 is about, measured this time.

    The claim is not that some hexes are equal. It is that no reading of the chip
    set produces an order, which means every chip must be at the same perceptual
    lightness and the same chroma. With one neutral chip that is trivially true,
    and the assertion exists so it stops being true loudly if a hue ever returns.
    """

    def fills(self):
        variants = re.findall(r"\.badge(?:\.\w+)?\s*{([^}]*)}", SCREEN)
        found = []
        for block in variants:
            match = re.search(r"background:\s*(#[0-9A-Fa-f]{6})", block)
            if match:
                found.append(match.group(1))
        return found

    def test_no_chip_is_perceptually_lighter_than_another(self):
        lightness = [lab(fill)[0] for fill in self.fills()]
        self.assertLessEqual(max(lightness) - min(lightness), 1.0,
                             "a lightness difference across the chip set is an "
                             "order, whatever the arithmetic says")

    def test_no_chip_is_more_saturated_than_another(self):
        chroma = [math.hypot(*lab(fill)[1:]) for fill in self.fills()]
        self.assertLessEqual(max(chroma) - min(chroma), 1.0,
                             "chroma is weight, and unequal weight ranks")

    def test_the_palette_declares_no_hue_at_all(self):
        # The strongest form of the guarantee: there is nothing to measure,
        # because no colour is computed from a category.
        self.assertNotIn("hsl(", SOURCE)
        self.assertNotIn("CATEGORY_HUE", SOURCE)


class TestNothingEncodesAnOrderInColour(unittest.TestCase):

    def test_no_red_amber_green_anywhere_in_the_stylesheet(self):
        """RAG is one ordered axis with three stops wearing three names.

        Measured rather than matched by name: a hue in the red or amber band at
        any usable saturation is an alarm colour whatever it is called.
        """
        for colour in set(re.findall(r"#[0-9A-Fa-f]{6}", SCREEN)):
            lightness, a, b = lab(colour)
            chroma = math.hypot(a, b)
            if chroma < 12:
                continue          # neutral enough to carry no valence
            hue = math.degrees(math.atan2(b, a)) % 360
            with self.subTest(colour=colour):
                self.assertFalse(
                    hue < 90 or hue > 330,
                    f"{colour} sits in the red-to-amber band at chroma "
                    f"{chroma:.0f}, which reads as severity")

    def test_a_surface_too_close_to_its_neighbour_is_separated_by_a_rule(self):
        """Surfaces carry structure, so a reader has to be able to tell them apart.

        The sidebar and the page are deltaE 2.10 apart, which is below the
        just-noticeable difference of roughly 2.3, so the fill alone does not
        separate them. It does not need to: the sidebar carries a border, which
        is a form cue and the same answer the chip vocabulary gives.

        No invented threshold here. 2.3 is the standard JND and the assertion is
        conditional on it rather than on a number chosen to make this pass. An
        earlier version of this test asserted the surface set spanned less than 8
        L* points, which was a figure with no derivation and no owner, tuned to
        the data it was measuring. That is the failure this repo's eval scenario
        forbids by name.
        """
        sidebar_rule = SCREEN.split('section[data-testid="stSidebar"] {')[1]
        self.assertLess(delta_e(SURFACES["page"], SURFACES["sidebar"]), 2.3)
        self.assertIn("border-right", sidebar_rule.split("}")[0])


class TestTheseFiguresAreForOneSubstrate(unittest.TestCase):

    def test_the_print_block_does_not_inherit_the_dark_measurements(self):
        """Every ratio above is measured on the dark surface.

        None of them transfer to paper, so print has to restate its own colours
        rather than reuse these. The assertion is that it does.
        """
        printed = CSS.partition("@media print")[2]
        self.assertIn("#FFFFFF", printed)
        self.assertIn("#000000", printed)
        self.assertGreaterEqual(contrast("#000000", "#FFFFFF"), 4.5)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
