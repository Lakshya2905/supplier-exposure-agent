"""What the browser actually painted, asserted against what was declared.

Four defects have shipped that every other test in this suite was happy with,
and they are one failure rather than four: **a declaration is not a painted
pixel**. Nothing that reads this repository can tell the two apart, so this
module reads `getComputedStyle` off a running page instead.

Each class below is named for the defect it would have caught. That is
deliberate: a regression suite whose tests are named after mechanisms tells a
reader what broke, and one named after mechanisms nobody remembers tells them
nothing.

The app is served once and all four surfaces are measured in one browser
session, so the whole module costs one boot rather than one per assertion.
"""
import re
import unittest
from pathlib import Path

from tests import rendered
from tests.rendered import playwright_or_skip

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "review_app.py").read_text().split(
    'CONSOLE_CSS = """', 1)[1].split('"""', 1)[0]
ROOT_BLOCK = CSS.split(":root {", 1)[1].split("}", 1)[0]
TOKENS = dict(re.findall(r"(--[a-z-]+):\s*(#[0-9A-Fa-f]{6})", ROOT_BLOCK))

playwright_or_skip()   # decides skip-versus-fail before anything is served


def rgb(hex_colour):
    text = hex_colour.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def parse(value):
    numbers = re.findall(r"[\d.]+", value or "")
    return tuple(int(float(n)) for n in numbers[:3]) if len(numbers) >= 3 else None


def luminance(channels):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(one, other):
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def token(name):
    return rgb(TOKENS[name])


class RenderedPage(unittest.TestCase):
    """One browser session for the whole module."""

    readings = None

    @classmethod
    def setUpClass(cls):
        if RenderedPage.readings is None:
            RenderedPage.readings = rendered.collect()
        cls.readings = RenderedPage.readings

    def surfaces(self):
        return self.readings.items()


class TestWhatWasDeclaredIsWhatIsPainted(RenderedPage):
    """The link colour, and the two ramp steps that were never painted.

    Streamlit styles its own anchors and headings at a specificity these element
    rules lose to. The stylesheet was right, a test agreed with the stylesheet,
    and the page disagreed with both.
    """

    EXPECTED = {
        "h1": "--text-title",
        "h2": "--text-section",
        "finding": "--text-primary",
        "note": "--text-note",
        "caption": "--text-caption",
        "link": "--accent",
        "summary": "--accent",
    }

    def test_each_named_element_is_painted_in_the_token_it_declares(self):
        for surface, probe in self.surfaces():
            for element, name in self.EXPECTED.items():
                sample = probe["named"].get(element)
                if not sample:
                    continue      # not every surface renders every element
                with self.subTest(surface=surface, element=element):
                    self.assertEqual(
                        parse(sample["colour"]), token(name),
                        f"{element} on {surface} is painted "
                        f"{sample['colour']} where {name} declares "
                        f"{TOKENS[name]}; something is winning the cascade")

    def test_the_scan_reached_the_elements_it_claims_to_check(self):
        # Guards the whole class against passing because every sample was None,
        # which is how a rendered check dies quietly.
        found = {element for _s, probe in self.surfaces()
                 for element, sample in probe["named"].items() if sample}
        self.assertGreaterEqual(len(found), 5, f"only reached {found}")


class TestEveryPaintedTextColourIsARampStep(RenderedPage):
    """The generic form of the heading defect.

    Six tokens are declared. If the page paints a seventh, either a rule is
    losing the cascade or somebody added a colour without adding a step, and
    from the source those two look identical.
    """

    def is_chrome(self, colour):
        """Streamlit's own controls, drawn at a fraction of the theme colour.

        Expressed as "a translucent ramp step" rather than as a literal, because
        the literal was `rgba(227, 230, 232, 0.6)` and stopped matching the
        moment the substrate changed, while the thing it exempted had not moved.
        The sidebar collapse chevron is chrome, not content.
        """
        if "rgba" not in colour or colour.endswith(", 1)"):
            return False
        return parse(colour) in self.ramp()

    def ramp(self):
        return {token(name) for name in
                ("--text-title", "--text-primary", "--text-body", "--text-note",
                 "--text-caption", "--text-section", "--accent")}

    def test_no_surface_paints_a_colour_outside_the_ramp(self):
        ramp = self.ramp()
        for surface, probe in self.surfaces():
            for colour, samples in probe["painted"].items():
                if self.is_chrome(colour):
                    continue
                with self.subTest(surface=surface, colour=colour):
                    self.assertIn(
                        parse(colour), ramp,
                        f"{colour} is painted on {surface} by {samples} and is "
                        f"not a declared step")

    def test_the_title_and_section_steps_reach_the_screen(self):
        """The specific thing that was false for months.

        Both were declared, both were correct, and neither was ever painted.
        Asserting the ramp is a subset of what is painted is the direction that
        catches it; the test above only catches the reverse.
        """
        painted = {parse(colour) for _s, probe in self.surfaces()
                   for colour in probe["painted"]}
        for name in ("--text-title", "--text-section"):
            with self.subTest(step=name):
                self.assertIn(token(name), painted,
                              f"{name} is declared and never painted")


class TestColourIsNeverTheOnlyCueOnScreen(RenderedPage):
    """WCAG 1.4.1, measured rather than read out of the stylesheet.

    The CSS test asserts the pairing in the rule. This asserts it in the pixel,
    which is where the link defect lived: the underline was winning while the
    colour was losing, so half the contract held and the source said both did.
    """

    def test_everything_painted_in_the_accent_carries_a_second_cue(self):
        accent = token("--accent")
        for surface, probe in self.surfaces():
            for element in probe["accentish"]:
                if parse(element["colour"]) != accent:
                    continue
                with self.subTest(surface=surface, tag=element["tag"],
                                  text=element["text"]):
                    self.assertTrue(
                        element["hasCue"],
                        f"{element['tag']} {element['text']!r} on {surface} is "
                        f"accent-coloured and neither it nor the control it "
                        f"sits in carries an underline, border or outline, so "
                        f"colour is its only cue")

    def test_something_is_actually_accent_coloured(self):
        accent = token("--accent")
        painted = [element for _s, probe in self.surfaces()
                   for element in probe["accentish"]
                   if parse(element["colour"]) == accent]
        self.assertTrue(painted, "nothing is accent-coloured, so the class "
                                 "above asserted nothing")


class TestEveryFieldHasAVisibleBoundaryOnScreen(RenderedPage):
    """The name box on Confirm, which a decision cannot be recorded without.

    Every field drew its border in the same colour as its own fill. WCAG 1.4.11
    asks 3:1 for the boundary of a UI component, against BOTH the component and
    what is behind it.
    """

    NON_TEXT_CONTRAST = 3.0

    def fields(self):
        return [(surface, field) for surface, probe in self.surfaces()
                for field in probe["fields"]]

    def test_the_scan_found_the_fields(self):
        self.assertTrue(self.fields(),
                        "no text input or select was found on any surface, so "
                        "the assertions below check nothing")

    def test_every_boundary_clears_three_to_one_against_its_own_fill(self):
        for surface, field in self.fields():
            with self.subTest(surface=surface, sidebar=field["inSidebar"]):
                measured = contrast(parse(field["border"]), parse(field["fill"]))
                self.assertGreaterEqual(
                    measured, self.NON_TEXT_CONTRAST,
                    f"a field boundary is {measured:.2f}:1 against its own "
                    f"fill, so the box has no edge")

    def test_every_boundary_clears_three_to_one_against_the_surface(self):
        for surface, field in self.fields():
            with self.subTest(surface=surface, sidebar=field["inSidebar"]):
                measured = contrast(parse(field["border"]),
                                    parse(field["behind"]))
                self.assertGreaterEqual(measured, self.NON_TEXT_CONTRAST)

    def test_no_field_draws_a_zero_width_border(self):
        # A 3:1 colour on a 0px border is a boundary nobody can see, and the
        # ratio test would pass on it.
        for surface, field in self.fields():
            with self.subTest(surface=surface):
                self.assertNotIn(field["width"], ("0px", ""))


class TestNoLargeAreaIsPaintedAColourNobodyDeclared(RenderedPage):
    """The generic form of the map's white slab, restated.

    `geo.bgcolor` defaults to `#fff` and is covered by neither `paper_bgcolor`
    nor `plot_bgcolor`, so the largest element on the page had a white
    background and no stylesheet could reach it.

    THE FIRST VERSION OF THIS TEST ASKED WHETHER ANYTHING LARGE WAS LIGHT, which
    was a defect only while the page was dark, and would have had to be deleted
    or inverted the moment the substrate moved. What is actually wrong is a large
    area painted a colour the design never declared, and that survives the
    substrate change because the declared set moves with it.
    """

    #: Read from the stylesheet and the theme rather than listed here, so a new
    #: surface does not have to be remembered in two places.
    def declared(self):
        surfaces = set(TOKENS.values())
        for match in re.finditer(r"background(?:-color)?:\s*(#[0-9A-Fa-f]{6})",
                                 CSS):
            surfaces.add(match.group(1).upper())
        config = (ROOT / ".streamlit" / "config.toml").read_text()
        for match in re.finditer(r'"(#[0-9A-Fa-f]{6})"', config):
            surfaces.add(match.group(1).upper())
        return {rgb(colour) for colour in surfaces}

    def test_every_large_background_is_a_declared_surface(self):
        allowed = self.declared()
        for surface, probe in self.surfaces():
            for slab in probe["slabs"]:
                with self.subTest(surface=surface,
                                  element=slab["testid"] or slab["tag"]):
                    self.assertIn(
                        parse(slab["value"]), allowed,
                        f"{slab['testid'] or slab['tag']} on {surface} paints "
                        f"{slab['value']} over {slab['area']}px2, and that "
                        f"colour is in neither the stylesheet nor the theme")

    def test_the_scan_saw_some_backgrounds(self):
        found = sum(len(probe["slabs"]) for _s, probe in self.surfaces())
        self.assertGreater(found, 0, "no large background was measured at all")


class TestTheMapDrawsTheWholeWorld(RenderedPage):
    """`showland` and `showcountries` default to off under a choropleth.

    Nineteen filled countries floated in an empty rectangle: no Africa, no South
    America, no Australia, no Russia. A map missing four continents is not a
    stylistic choice, it says the world ends at the edge of the dataset.
    """

    def geos(self):
        return [(surface, geo) for surface, probe in self.surfaces()
                for geo in probe["geos"]]

    def test_a_geo_subplot_exists_to_check(self):
        self.assertTrue(self.geos(), "no map was found on any surface")

    def test_the_base_geography_is_drawn(self):
        for surface, geo in self.geos():
            with self.subTest(surface=surface):
                self.assertTrue(geo["showland"], "land is switched off")
                self.assertTrue(geo["showcountries"])
                self.assertGreater(geo["landPaths"], 0,
                                   "showland is on and no land was drawn")

    def test_the_subplot_paints_no_background_of_its_own(self):
        for surface, geo in self.geos():
            with self.subTest(surface=surface):
                colour = parse(geo["bgcolor"]) or rgb(geo["bgcolor"])
                self.assertLess(
                    luminance(colour), 0.5,
                    f"the geo subplot paints {geo['bgcolor']} behind the map")

    def test_the_regions_are_actually_filled(self):
        for surface, geo in self.geos():
            with self.subTest(surface=surface):
                self.assertGreater(geo["filled"], 0)

    def test_india_is_still_drawn_from_its_own_geometry(self):
        """Plotly's built-in IND stops near 35.5N, so the claimed territory is
        supplied as a second trace. A map that fell back to one trace is a map
        that lost it, and it would render as a smaller India rather than as an
        error."""
        for surface, geo in self.geos():
            with self.subTest(surface=surface):
                self.assertEqual(geo["traces"], 2)
                self.assertEqual(geo["customGeometry"], 1)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
