"""Three DESIGN.md rules that shipped as prose and nothing enforced.

Each was marked [PARTIAL] with the same shape of gap: the thing was written
down, the code mostly did it, and nothing would notice when it stopped. A rule
in a document that no test reads is a rule that survives exactly as long as the
next person to edit the stylesheet remembers it.

  the text ramp        six tokens specified, twelve colours shipped
  the accent contract  colour was the only cue on links, against WCAG 1.4.1
  equal area           a group's width varied with how many siblings it had
"""
import ast
import re
import unittest
from pathlib import Path

from src.interface import model as view

APP = Path(__file__).resolve().parent.parent / "review_app.py"
SOURCE = APP.read_text()
CSS = SOURCE.split('CONSOLE_CSS = """', 1)[1].split('"""', 1)[0]
# Comments are stripped before every scan below. This file and that stylesheet
# both explain the constructs they forbid, and the corrections log records that
# hazard twice: a system that refuses a concept by name contains the name in its
# refusal, so an unstripped scan fails on its own explanation.
CSS_BODY = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
ROOT_BLOCK = CSS_BODY.split(":root {", 1)[1].split("}", 1)[0]
BELOW_ROOT = CSS_BODY.split(":root {", 1)[1].split("}", 1)[1]

RAMP_TOKENS = ("--text-title", "--text-primary", "--text-body", "--text-note",
               "--text-caption", "--text-section", "--accent", "--text-print")

# A colour set on text, as opposed to a fill or a rule. `background-color` and
# `border-color` end in the same six characters, so the lookbehind is doing real
# work rather than being defensive.
TEXT_COLOUR = re.compile(r"(?<![-\w])color\s*:\s*([^;}\n]+)")


def rule_blocks(css):
    """(selector, body) for every rule, comments already stripped."""
    return [(match.group(1).strip(), match.group(2))
            for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]


class TestTheTextRampIsTheOnlySourceOfTextColour(unittest.TestCase):

    def test_every_ramp_step_is_declared_once_in_root(self):
        for token in RAMP_TOKENS:
            with self.subTest(token=token):
                self.assertEqual(ROOT_BLOCK.count(f"{token}:"), 1)

    def test_no_rule_states_a_text_colour_as_a_literal(self):
        """The failure the type scale already had, in another channel.

        Twelve distinct text colours shipped against six specified tokens, and
        every one of the six extras folded onto a step that already existed,
        which is the evidence that none of them was carrying a distinction.
        """
        literals = [value.strip() for value in TEXT_COLOUR.findall(BELOW_ROOT)
                    if value.strip().startswith("#")]
        self.assertEqual(literals, [], f"off-ramp text colours: {literals}")

    def test_every_text_colour_names_a_ramp_token(self):
        for value in TEXT_COLOUR.findall(BELOW_ROOT):
            value = value.strip()
            if value in ("inherit", "transparent", "currentColor"):
                continue
            with self.subTest(value=value):
                self.assertTrue(
                    any(token in value for token in RAMP_TOKENS),
                    f"{value} is a seventh step nobody declared")

    def test_the_ramp_covers_the_title_and_the_section_label(self):
        # The two ends. A ramp missing either would push a heading onto a body
        # step, which is how the twelve colours started.
        self.assertIn("var(--text-title)", BELOW_ROOT)
        self.assertIn("var(--text-section)", BELOW_ROOT)


class TestACaptionNeverVariesWithTheData(unittest.TestCase):
    """The mechanisable half of the note-versus-caption rule.

    DESIGN.md: `text-note` is a qualification about the DATA, `text-caption` is
    an instruction about the INTERFACE, and "if it would still be true with
    different data, it is a caption". Only one direction of that is checkable:
    a caption that interpolates a computed value is provably about the data, so
    it is provably in the wrong register. The converse is a judgment about
    meaning and is left to review.

    A caption may still name a module-level constant. `ordered by part number`
    is a fact about how this interface lays things out, and it would read the
    same against any dataset.
    """

    MODULES = {"ranking", "view", "gov", "govrender", "st"}

    def captions(self):
        tree = ast.parse(SOURCE)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "caption"
                    and node.args):
                yield node

    def root_of(self, node):
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value if isinstance(node, ast.Attribute) else node.value
        return node.id if isinstance(node, ast.Name) else None

    def test_no_caption_interpolates_a_computed_value(self):
        for call in self.captions():
            for node in ast.walk(call.args[0]):
                if isinstance(node, ast.Call):
                    self.fail(
                        f"review_app.py:{call.lineno}: a caption calls "
                        f"{ast.unparse(node)!r}, so its text varies with the "
                        f"data and it is a note, not a caption")

    def test_no_caption_reads_a_runtime_value(self):
        for call in self.captions():
            argument = call.args[0]
            for node in ([argument] if not isinstance(argument, ast.JoinedStr)
                         else [v.value for v in argument.values
                               if isinstance(v, ast.FormattedValue)]):
                if isinstance(node, ast.Constant):
                    continue
                root = self.root_of(node)
                with self.subTest(line=call.lineno):
                    self.assertIn(
                        root, self.MODULES,
                        f"review_app.py:{call.lineno}: a caption reads "
                        f"{ast.unparse(node)!r}, which is data rather than a "
                        f"constant about the interface")

    def test_the_scan_finds_the_captions_it_is_meant_to_check(self):
        # Guards against the whole class passing because the AST walk matched
        # nothing, which is how a scanning test dies quietly.
        self.assertGreater(len(list(self.captions())), 5)


class TestColourIsNeverTheOnlyCueForActionability(unittest.TestCase):
    """WCAG 1.4.1, and DESIGN.md's accent contract restating it.

    Links carried the accent and nothing else: no underline on screen, only in
    print. On a greyscale screenshot, or to a reader with achromatopsia, they
    were prose.
    """

    AFFORDANCES = ("text-decoration", "border", "outline", "box-shadow")

    def accent_text_rules(self):
        return [(selector, body) for selector, body in rule_blocks(BELOW_ROOT)
                if any("var(--accent)" in value
                       for value in TEXT_COLOUR.findall(body))]

    def test_the_scan_finds_the_accent_rules(self):
        self.assertGreaterEqual(len(self.accent_text_rules()), 3)

    def test_every_accent_element_carries_a_non_colour_affordance(self):
        for selector, body in self.accent_text_rules():
            with self.subTest(selector=selector):
                self.assertTrue(
                    any(affordance in body for affordance in self.AFFORDANCES),
                    f"{selector} is accent-coloured with no underline, caret, "
                    f"bracket or border, so colour is its only cue")

    def test_links_are_underlined_on_screen_and_not_only_in_print(self):
        screen = CSS_BODY.split("@media print", 1)[0]
        link_rule = next(body for selector, body in rule_blocks(screen)
                         if selector.startswith("a,"))
        self.assertIn("underline", link_rule)


class TestNoGroupGetsMoreAreaThanAnother(unittest.TestCase):
    """The equal-area half of the anti-ranking contract.

    The lattice sized each layer to its own group count, so a layer holding one
    group filled the page and a group sharing a layer with two others got a
    third of it. Vertical position carries dominance and is meant to; width
    carried nothing and looked like it carried something.
    """

    def test_one_width_serves_every_layer(self):
        self.assertEqual(view.lattice_width(((1, 2, 3), (4,), (5, 6))), 3)
        self.assertEqual(view.lattice_width(((1,),)), 1)

    def test_an_empty_lattice_does_not_divide_by_zero(self):
        self.assertEqual(view.lattice_width(()), 1)

    def test_the_column_count_does_not_come_from_the_layer(self):
        """Structural, not a count.

        The defect was `st.columns(len(layer))`, which is correct-looking and
        wrong for a reason no rendered figure would reveal.
        """
        body = re.sub(r"#[^\n]*", "", SOURCE)
        self.assertNotIn("st.columns(len(layer))", body)
        self.assertIn("st.columns(width)", body)

    def test_the_real_lattice_has_layers_of_different_sizes(self):
        # Otherwise every layer is the same width by accident and the fix is
        # untested against the case it was written for.
        from src.pipeline import default_data_dir, run, surfaces
        surface = surfaces(run(data_dir=default_data_dir()))[view.EXPOSURE]
        sizes = {len(layer) for layer in surface.layers}
        self.assertGreater(len(sizes), 1)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()


class TestTheChartsOnTheDecisionSurfaces(unittest.TestCase):
    """Charts became permissible on 2026-08-06. Their ORDERINGS did not become
    arbitrary, and the orderings are the part that would regress silently: a
    bar chart sorted the wrong way asserts a ranking in the one place the
    product spent eight stages refusing to compute one.
    """

    @classmethod
    def setUpClass(cls):
        from src.pipeline import default_data_dir, run, surfaces
        from src.interface import dashboard
        cls.dash = dashboard
        cls.result = run(data_dir=default_data_dir())
        cls.surfaces = surfaces(cls.result)

    def test_group_sizes_keep_lattice_order_and_are_not_sorted_by_size(self):
        """The chart sits directly under a lattice that says these groups are
        incomparable. Sorting it by count would contradict that caption, and a
        bar chart is a stronger cue than a caption."""
        sizes = self.dash.group_sizes(self.surfaces[view.EXPOSURE])
        counts = [count for _label, count in sizes]
        self.assertGreater(len(sizes), 2)
        self.assertNotEqual(counts, sorted(counts, reverse=True),
                            "group sizes came back in descending order, so "
                            "either the lattice changed or this is now sorted")

    def test_group_sizes_match_the_lattice_the_page_draws(self):
        expected = [(group.label, len(group.rows))
                    for layer in self.surfaces[view.EXPOSURE].layers
                    for group in layer]
        self.assertEqual(list(self.dash.group_sizes(
            self.surfaces[view.EXPOSURE])), expected)

    def test_the_work_queue_is_ranked_and_that_is_deliberate(self):
        # This surface asks what to go and get, so "which trip settles most" is
        # the question rather than a smuggled conclusion.
        counts = [count for _f, count in
                  self.dash.field_sizes(self.surfaces[view.FIND_OUT])]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_cluster_sizes_carry_their_basis(self):
        """Supplier and region grouping are a COMPLEMENTARY disagreement: both
        can be true at once and no fact settles one against the other. One
        undifferentiated ranking would put them in exactly the relation the
        analysis says they are not in."""
        rows = self.dash.cluster_sizes(self.result.report)
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(len(row), 3)
        self.assertEqual({basis for _k, _s, basis in rows},
                         {"supplier", "region"})

    def test_every_ordering_is_stable_under_a_tie(self):
        # CLAUDE.md: a default ordering must be arbitrary AND stable. Ties are
        # where insertion order silently becomes the tiebreak.
        rows = self.dash.cluster_sizes(self.result.report)
        ties = [(size, key) for key, size, _b in rows]
        self.assertEqual(ties, sorted(ties, key=lambda pair: (-pair[0],
                                                             pair[1])))

    def test_coverage_counts_drop_the_zero_rows(self):
        # A zero-length bar is a row that reads as "nothing here" when the
        # sentence beside it says a threshold is unset, which is not nothing.
        counts = self.dash.coverage_counts(
            self.surfaces[view.EXPOSURE].coverage)
        self.assertTrue(counts)
        self.assertTrue(all(count > 0 for _s, count in counts))

    def test_no_chart_helper_mixes_two_dimensions(self):
        """The one rule that did not move when the encoding rule was retired.

        Every helper returns counts of parts. A function here that returned two
        dimensions together would be the composite arriving through the picture,
        which is the objection the arithmetic still enforces in scoring.py.
        """
        source = (Path(__file__).resolve().parent.parent / "src" / "interface"
                  / "dashboard.py").read_text()
        body = re.sub(r'""".*?"""', "", source, flags=re.S)
        body = re.sub(r"#[^\n]*", "", body)
        for forbidden in ("total", "weight", "composite", "normalis"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, body)


class TestTheRegionMapIsComplete(unittest.TestCase):
    """A country missing from a map reads as "no suppliers there".

    That is a different claim from "this label stopped matching the gazetteer",
    and the map cannot tell a reader which of the two happened. So the things
    that would cause a silent gap are asserted here rather than noticed later.
    """

    @classmethod
    def setUpClass(cls):
        from src.interface import dashboard
        cls.dash = dashboard
        cls.codes = [code for codes in dashboard.REGION_COUNTRIES.values()
                     for code in codes]

    def test_every_country_is_an_iso_3166_alpha_3_code(self):
        """Codes, not names. Names resolve by string match against a vendored
        gazetteer, so a country that gets renamed upstream stops matching and
        its fill disappears with no error. Czechia, Türkiye and Eswatini have
        all moved."""
        for code in self.codes:
            with self.subTest(code=code):
                self.assertRegex(code, r"^[A-Z]{3}$")

    def test_every_code_has_a_readable_name(self):
        # The table and the hover show names; a code with no name would render
        # as the code and read as a defect.
        for code in self.codes:
            with self.subTest(code=code):
                self.assertIn(code, self.dash.COUNTRY_NAME)

    def test_no_country_belongs_to_two_regions(self):
        # A country in two regions gets one arbitrary fill, and which one wins
        # depends on frame order.
        self.assertEqual(len(self.codes), len(set(self.codes)))

    def test_every_region_the_generator_can_emit_is_on_the_map(self):
        """The mapping is a hand-written dict beside a generated enum.

        A region added to the generator and not here would be a supplier region
        the map silently declines to draw.
        """
        from src.synthetic.config import REGIONS
        self.assertEqual(set(REGIONS), set(self.dash.REGION_COUNTRIES),
                         "the generator and the map disagree about which "
                         "regions exist")

    def test_a_region_with_no_countries_still_reaches_the_table(self):
        """The first version iterated the country mapping, so a region present
        in the data but missing from that dict vanished from the map AND the
        table, with nothing said."""
        from src import archetypes as A

        class Supplier:
            supplier_name, region = "Somebody Ltd", "antarctica"

        class Evidence:
            supplier_rows = (Supplier(),)

        class Result:
            evidence = {"AA-P-01": Evidence()}
            profiles, verdicts = {}, {}
            catalogue = A.catalogue(None)

        rows = self.dash.regions(Result())
        unmapped = [row for row in rows if row.region == "antarctica"]
        self.assertEqual(len(unmapped), 1)
        self.assertEqual(unmapped[0].countries, ())
        self.assertEqual(unmapped[0].suppliers, 1)
