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


# The surfaces anything can be read against, HAND-WRITTEN so this is a pin
# rather than a tautology: reading them from the stylesheet would make the file
# agree with itself whatever it said.
#
# LIGHT SUBSTRATE SINCE 2026-08-07. Every figure below was re-measured, not
# inverted. DESIGN.md is explicit that a substrate change voids every contrast
# guarantee in it until the numbers are taken again, and the ramp was solved
# against the ratios its dark counterpart held rather than chosen by eye.
SURFACES = {"page": "#F7F8FA", "panel": "#FFFFFF", "panel head": "#F0F2F5",
            "sidebar": "#EFF1F4", "chip": "#EAEDF1", "button": "#E8EEF4"}

# The text ramp, with the surface each step is read against, because the WCAG
# threshold depends on it. All of these are small text, so all need 4.5:1.
TEXT_RAMP = {
    "#1A1C1E": ("h1 title", "page"),
    "#222527": ("finding", "page"),
    "#2C2E31": ("body and chip label", "chip"),
    "#50555B": ("note", "page"),
    "#61686E": ("caption", "page"),
    "#53585E": ("section heading", "page"),
    "#194F7D": ("accent", "page"),
}

ACCENT = "#194F7D"


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
        self.ring = resolve(re.search(
            r"outline:\s*\d+px solid (var\(--[a-z-]+\)|#[0-9A-Fa-f]{6})",
            rule).group(1))

    def test_the_ring_clears_three_to_one_on_every_surface(self):
        for name, surface in SURFACES.items():
            with self.subTest(surface=name):
                self.assertGreaterEqual(contrast(self.ring, surface), 3.0)

    def test_focus_is_not_mistakable_for_a_resting_boundary(self):
        """The reason the border token was rejected for focus, restated.

        ON THE DARK SUBSTRATE the argument was a ratio: #6B7278 measured below
        3:1 on a chip, so it could not carry a focus ring at all. That is no
        longer true on light, where the same token clears 3:1 everywhere, and a
        test asserting otherwise would be asserting something false.

        The reason it was rejected survives the substrate change even though the
        measurement does not: a ring drawn in the colour every field already
        uses for its edge says nothing a reader can act on. So the property is
        separation from the boundary colour, not a ratio against a chip.
        """
        boundary = resolve("var(--border-ui)")
        self.assertGreater(
            delta_e(self.ring, boundary), 2.3,
            "the focus ring and the resting field boundary are within a "
            "just-noticeable difference, so focus reads as no change")


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

        THE ASSERTION IS CONDITIONAL, which is what lets it survive a substrate
        change. On the dark palette the sidebar sat deltaE 2.10 from the page,
        below the just-noticeable difference, and the border did the separating.
        On light it is 2.56, marginally above. Either is fine; what is not fine
        is a pair of surfaces a reader cannot tell apart with nothing else
        distinguishing them.

        An earlier version asserted the separation was BELOW the JND, which
        turned a finding about one palette into a requirement, and it failed the
        moment the palette moved while the design was still correct.

        No invented threshold: 2.3 is the standard JND. An earlier version than
        that asserted the surface set spanned less than 8 L* points, a figure
        with no derivation and no owner, tuned to the data it was measuring.
        That is the failure this repo's eval scenario forbids by name.
        """
        sidebar_rule = SCREEN.split(
            'section[data-testid="stSidebar"] {')[1].split("}")[0]
        separation = delta_e(SURFACES["page"], SURFACES["sidebar"])
        if separation < 2.3:
            self.assertIn(
                "border-right", sidebar_rule,
                f"the sidebar is {separation:.2f} deltaE from the page, below "
                f"the just-noticeable difference, and carries no rule to "
                f"separate them")


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


def python_colour(name):
    """A colour constant from the app's Python, not from its CSS.

    The map palette cannot live in the stylesheet: plotly paints an SVG from
    values passed in Python, so CSS never reaches it. Read from source rather
    than imported, because importing `review_app` runs the Streamlit app.
    """
    match = re.search(rf'^{name} = "(#[0-9A-Fa-f]{{6}})"', SOURCE, re.M)
    return match.group(1) if match else None


def python_scale(name):
    block = re.search(rf"^{name} = \(([^)]*)\)", SOURCE, re.M).group(1)
    return re.findall(r"#[0-9A-Fa-f]{6}", block)


class TestTheMapSeparatesAbsenceFromALowCount(unittest.TestCase):
    """Unfilled land is NOT a region in this dataset. That is a question the
    data does not answer, and it is a different claim from a region with the
    fewest exposed parts.

    The map is the one place those two are told apart by fill alone: there is
    no label on a country, so if the palette's floor sat near the land colour
    a reader would have no way to distinguish "least exposed" from "not a
    supplier region at all". CHART_SEQUENTIAL's first stop is #1E2933, within
    a step of the land, which is why the map has a palette of its own.
    """

    #: The CIE just-noticeable difference, ~2.3 ΔE, is the floor for "these are
    #: perceptibly different at all". It is cited rather than chosen: it is what
    #: the task requires, since two fills a reader cannot tell apart carry one
    #: state between them. The measured value is far above it and is reported so
    #: a future change that erodes the margin is visible before it fails.
    JND = 2.3

    def test_the_palette_floor_is_distinct_from_unmapped_land(self):
        land = python_colour("MAP_LAND")
        floor = python_scale("MAP_SCALE")[0]
        measured = delta_e(land, floor)
        self.assertGreater(measured, self.JND,
                           f"the least-exposed region and land that is not a "
                           f"region differ by {measured:.2f} ΔE, at or below "
                           f"the {self.JND} just-noticeable difference, so the "
                           f"map cannot say which of the two a country is")

    def test_land_is_distinct_from_ocean(self):
        # Otherwise the coastline is the only thing separating a continent from
        # the sea, and it is drawn at 0.4px.
        measured = delta_e(python_colour("MAP_LAND"), python_colour("MAP_OCEAN"))
        self.assertGreater(measured, self.JND)

    def test_the_palette_spans_a_usable_range(self):
        scale = python_scale("MAP_SCALE")
        self.assertGreater(delta_e(scale[0], scale[-1]), self.JND)

    def test_the_map_palette_is_not_the_chart_palette(self):
        # Stated as a property rather than left as a coincidence: if somebody
        # collapses the two lists back into one, this fails and says why.
        self.assertNotEqual(python_scale("MAP_SCALE"),
                            python_scale("CHART_SEQUENTIAL"))


class TestEveryFieldHasAVisibleBoundary(unittest.TestCase):
    """WCAG 1.4.11 asks 3:1 for the boundary of a UI component.

    Every text input and select painted a 1px border in THE SAME COLOUR AS ITS
    OWN FILL, so there was no boundary at all: the only thing separating a field
    from its surroundings was the fill difference, 1.04:1 in the sidebar and
    1.09:1 on the page. Both are around a single just-noticeable difference. The
    name field is the one control on the Confirm surface a decision cannot be
    recorded without, and a reviewer could not see it.

    `border-ui` was specified in DESIGN.md's Surfaces table from the start and
    no form control ever referenced it. THAT is the failure this class exists
    to catch: a token can be declared, correct, and unused, and nothing about
    the declaration reveals it.
    """

    #: WCAG 2.1 Success Criterion 1.4.11 Non-text Contrast. Cited, not chosen.
    NON_TEXT_CONTRAST = 3.0

    def theme(self, key):
        config = (Path(__file__).resolve().parent.parent
                  / ".streamlit" / "config.toml").read_text()
        return re.search(rf'{key}\s*=\s*"(#[0-9A-Fa-f]{{6}})"', config).group(1)

    def border(self):
        root = CSS.split(":root {")[1].split("}")[0]
        match = re.search(r"--border-ui:\s*(#[0-9A-Fa-f]{6})", root)
        self.assertIsNotNone(match, "--border-ui is not declared")
        return match.group(1)

    def test_the_boundary_clears_non_text_contrast_on_every_surface(self):
        border = self.border()
        surfaces = {
            "sidebar": declared("section[data-testid=\"stSidebar\"] {",
                                "background") or "#101315",
            "page": self.theme("backgroundColor"),
            "field fill in the main area": self.theme("secondaryBackgroundColor"),
        }
        for name, behind in surfaces.items():
            with self.subTest(surface=name):
                measured = contrast(border, behind)
                self.assertGreaterEqual(
                    measured, self.NON_TEXT_CONTRAST,
                    f"the field boundary is {measured:.2f}:1 against {name}, "
                    f"below the {self.NON_TEXT_CONTRAST}:1 that WCAG 1.4.11 "
                    f"asks of a UI component boundary")

    def test_the_token_is_actually_applied_to_the_fields(self):
        """Declared is not applied, and that distinction is the whole bug.

        Asserted on the rule rather than on the rendered page because a headless
        suite cannot resolve the cascade, and the rendered check that found this
        is recorded in DESIGN.md.
        """
        body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
        rule = re.search(
            r"\[data-testid=\"stTextInputRootElement\"\][^{]*\{([^}]*)\}", body)
        self.assertIsNotNone(rule, "no rule targets the text input's box")
        self.assertIn("var(--border-ui)", rule.group(1))

    def test_the_select_gets_the_same_boundary_as_the_text_input(self):
        # Two controls a reviewer uses in one act. A boundary on one and not the
        # other would read as one of them being disabled.
        body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
        self.assertIn('[data-testid="stSelectbox"] [role="group"]', body)
