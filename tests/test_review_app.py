"""The rendered interface, headless.

Two things are checked here that the model cannot check for itself: that the
painting does not reintroduce what the model refuses, and that no widget
smuggles in a normalised scale.
"""
import re
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "review_app.py"
SOURCE = APP.read_text()
DATA = APP.parent / "data"


def setUpModule():
    """data/ is gitignored and regenerated, so a fresh clone has none.

    The app reads the five CSVs a real consumer would have, so the test
    regenerates them from the documented seed rather than skipping, which would
    let the interface go unchecked in CI without anybody noticing.
    """
    if (DATA / "bom.csv").exists():
        return
    from src.generate_data import generate
    from src.synthetic.config import GeneratorConfig
    DATA.mkdir(parents=True, exist_ok=True)
    generate(GeneratorConfig(), DATA, DATA.parent / "truth" / "answer_key.json")

# WIDGETS THAT ENCODE MAGNITUDE AS LENGTH OR FRACTION. Each is a normalised
# scale by construction, which is the composite arriving through a widget rather
# than through arithmetic. `st.progress(0.8)` is literally a 0-to-1 bar; a
# progress column is the same thing inside a table; a colour ramp is an ordinal
# encoding of a heterogeneous set, which is the objection that killed the radar
# chart.
BANNED_WIDGETS = (
    "st.progress",
    "ProgressColumn",
    "BarChartColumn",
    "LineChartColumn",
    "AreaChartColumn",
    "st.bar_chart",
    "st.line_chart",
    "st.area_chart",
    "st.scatter_chart",
    "st.pyplot",
    "st.altair_chart",
    "background_gradient",
    "color_gradient",
    "st.slider",          # a threshold with no owner and no version
)


SCALE_STEPS = ("ui-xs", "ui-sm", "ui-base", "doc", "title")


def scale_px():
    """The declared type scale, resolved from :root, in pixels.

    Read rather than hard-coded: this helper exists so the assertions below can
    check the PROPERTY (a rendered size in px) while the stylesheet expresses it
    as a named step. The step values themselves are pinned separately.
    """
    root = SOURCE.split(":root {")[1].split("}")[0]
    return {name: float(re.search(rf"--{name}:\s*([\d.]+)rem", root).group(1)) * 16
            for name in SCALE_STEPS}


def resolved_font_px(block):
    """The font-size of a CSS block in px, following one var() indirection."""
    match = re.search(r"font-size:\s*var\(--([a-z-]+)\)", block)
    if match:
        return scale_px()[match.group(1)]
    literal = re.search(r"font-size:\s*([\d.]+)rem", block)
    return float(literal.group(1)) * 16 if literal else None


def run_app(timeout=90):
    app = AppTest.from_file(str(APP), default_timeout=timeout)
    return app.run()


def text_of(app):
    parts = []
    for collection in (app.markdown, app.title, app.subheader, app.header,
                       app.caption, app.info, app.warning, app.success):
        parts.extend(element.value for element in collection)
    return "\n".join(str(part) for part in parts)


class TestWidgetDenyList(unittest.TestCase):

    def test_no_banned_widget_appears_in_the_app(self):
        for widget in BANNED_WIDGETS:
            with self.subTest(widget=widget):
                # The deny-list is quoted in this file's own docstring and in
                # the constant above, so match a CALL rather than a mention.
                self.assertNotIn(f"{widget}(", SOURCE)

    def test_no_normalised_zero_to_one_value_is_passed_to_a_widget(self):
        # A fraction handed to a display widget is a normalised scale whatever
        # it is called.
        self.assertIsNone(re.search(r"st\.\w+\(\s*0\.\d+", SOURCE))

    def test_the_app_states_that_it_paints_and_does_not_decide(self):
        self.assertIn("paints the view model and decides nothing", SOURCE)

    def test_the_app_never_writes_to_source_data(self):
        for forbidden in ("to_csv(", "open(", ".write_text("):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, SOURCE)


class TestTheTypeScaleIsDeclaredOnce(unittest.TestCase):
    """Ten sizes with step ratios from 1.012 to 1.426 is a list, not a scale.

    The values are hand-written here rather than read from :root, so this is a
    pin and not a tautology. `scale_px()` reads them for the assertions that need
    a resolved size, which is a different job.
    """

    def test_the_scale_is_exactly_five_steps(self):
        self.assertEqual(scale_px(),
                         {"ui-xs": 12.0, "ui-sm": 13.0, "ui-base": 14.0,
                          "doc": 15.0, "title": 21.0})

    def test_no_rule_declares_a_size_outside_the_scale(self):
        """A literal font-size below :root is a sixth step nobody declared.

        This is the assertion that keeps the scale a scale. Without it the file
        drifts back to ten sizes one convenient exception at a time, which is how
        it got there the first time.
        """
        css = SOURCE.split('CONSOLE_CSS = """')[1].split('"""')[0]
        below_root = css.split(":root {")[1].split("}", 1)[1]
        self.assertEqual(re.findall(r"font-size:\s*([\d.]+rem)", below_root), [])

    def test_nothing_renders_below_twelve_pixels(self):
        # The floor, asserted on the resolved values rather than on the notation.
        self.assertGreaterEqual(min(scale_px().values()), 12.0)


class TestTheSpacingScaleIsDeclaredOnce(unittest.TestCase):
    """Thirty-eight distinct rem values shipped, five of them on any grid.

    That means the vertical rhythm was decided thirty-eight times. Hand-written
    here so this is a pin rather than a tautology.
    """

    #: Properties whose value is a rhythm decision and must come from the scale.
    SPACING_PROPERTIES = ("padding", "margin", "gap", "margin-top",
                          "margin-bottom", "margin-right", "margin-left")

    #: Literals that are NOT rhythm, each named so the exemption is deliberate
    #: rather than whatever happened to survive: two column widths sized to their
    #: content, the sidebar panel width, and one optical baseline nudge.
    EXEMPT = ("min-width: 6.6rem", "width: 4rem", "width: 16rem",
              "vertical-align: 0.06rem")

    def setUp(self):
        css = SOURCE.split('CONSOLE_CSS = """')[1].split('"""')[0]
        self.below_root = css[css.index("}", css.index(":root {")) + 1:]

    def test_the_scale_is_a_4px_base(self):
        root = SOURCE.split(":root {")[1].split("}")[0]
        steps = {name: float(value) * 16 for name, value in
                 re.findall(r"--space-([a-z0-9]+):\s*([\d.]+)rem", root)}
        self.assertEqual(steps, {"xs": 4.0, "sm": 8.0, "md": 12.0, "lg": 16.0,
                                 "xl": 24.0, "2xl": 32.0, "3xl": 48.0})

    def test_no_spacing_declaration_invents_a_value(self):
        for line in self.below_root.splitlines():
            stripped = line.strip()
            if stripped.startswith("/*") or "var(" in stripped:
                continue
            for prop in self.SPACING_PROPERTIES:
                if re.search(rf"\b{prop}\s*:[^;]*[\d.]+rem", stripped):
                    self.fail(f"spacing literal outside the scale: {stripped}")

    def test_every_surviving_rem_literal_is_a_named_exemption(self):
        """A literal that is not spacing still has to be accounted for.

        Otherwise the guard above passes while the file quietly regrows a second
        vocabulary in properties it does not police.
        """
        for line in self.below_root.splitlines():
            stripped = line.strip()
            if not re.search(r"[\d.]+rem", stripped) or stripped.startswith("/*"):
                continue
            accounted = "var(" in stripped or any(e in stripped
                                                  for e in self.EXEMPT)
            self.assertTrue(accounted, f"unaccounted rem literal: {stripped}")

    def test_the_panel_head_pull_cancels_the_panel_padding(self):
        """The head bleeds to the panel edge, so the two must agree exactly.

        They were 0.7/0.9 against a 0.7/0.9 padding. Moving the padding to the
        scale without moving the pull would have left the head inset by a few
        pixels, which is the kind of drift a scale is supposed to prevent rather
        than cause.
        """
        head = self.below_root.split(".panelhead {")[1].split("}")[0]
        panel = self.below_root.split(":has(> [data-testid=")[1].split("}")[0]
        padding = re.search(r"padding:\s*var\(--([a-z0-9-]+)\)", panel).group(1)
        self.assertIn(f"calc(var(--{padding}) * -1)", head)

    def test_the_panel_rule_targets_a_selector_that_exists(self):
        """The predecessor targeted a testid Streamlit 1.61 does not render.

        `[data-testid="stVerticalBlockBorderWrapper"]` matched nothing, so the
        panel's border, radius and background were Streamlit's defaults the whole
        time, including an 8px radius this design system says it does not use.
        Dead CSS is quieter than wrong CSS: the page looks deliberate and no
        assertion disagrees.

        The live hook is `:has()` on the marker this file emits itself, which is
        the same mechanism the sidebar already relies on for selected state.
        """
        # SCAN THE SELECTORS, NOT THE COMMENTS. The rewrite above explains which
        # testid was dead and why, so the dead name appears in this file as part
        # of its own refusal. A naive `assertNotIn(..., SOURCE)` finds the
        # explanation and reports it as the breach, which is corrections-log
        # entries 4 and 5 exactly. Strip comments first.
        # Strip /* ... */ SPANS, not lines that begin with a marker. This file
        # indents comment continuation lines, so a line-prefix filter leaves the
        # body of every multi-line comment in the text being scanned, which is
        # how the first version of this assertion failed on its own explanation.
        selectors = re.sub(r"/\*.*?\*/", "", self.below_root, flags=re.S)
        self.assertNotIn("stVerticalBlockBorderWrapper", selectors)
        self.assertIn(":has(> [data-testid=", selectors)


class TestExposureSurface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = run_app()

    def test_the_app_runs_without_exception(self):
        self.assertFalse(self.app.exception)

    def test_the_default_surface_asks_what_is_worst(self):
        self.assertIn("What is worst?", text_of(self.app))

    def test_executed_findings_render_no_button(self):
        # THE AUTONOMY CLAIM, CHECKED AT THE SURFACE. Every part on this page
        # executes, so a button anywhere here means the ceiling has evaporated
        # between the model and the paint.
        self.assertEqual(len(self.app.button), 0)

    def test_the_layout_explains_what_vertical_and_horizontal_mean(self):
        rendered = text_of(self.app)
        self.assertIn("dominate the groups below", rendered)
        self.assertIn("incomparable", rendered)
        self.assertIn("carries no meaning", rendered)

    def test_the_default_order_is_labelled_on_every_group(self):
        self.assertIn("ordered by part number", text_of(self.app))

    def test_no_group_heading_is_numbered(self):
        for element in self.app.subheader:
            with self.subTest(heading=element.value):
                self.assertIsNone(re.match(r"^\s*\d+[.)]", str(element.value)))

    def test_the_coverage_panel_is_present(self):
        self.assertIn("What this page does not cover", text_of(self.app))

    def test_the_coverage_panel_reports_the_disabled_thresholds(self):
        rendered = text_of(self.app)
        self.assertIn("Magnitude archetypes are off", rendered)
        self.assertIn("config/archetypes.yaml", rendered)

    def test_the_disabled_threshold_notice_is_not_phrased_as_a_failure(self):
        rendered = text_of(self.app).lower()
        for alarm in ("error", "failed", "not implemented", "coming soon"):
            with self.subTest(word=alarm):
                self.assertNotIn(alarm, rendered)

    def test_evidence_is_reachable_and_says_it_is_read_only(self):
        rendered = text_of(self.app)
        self.assertIn("Read only", rendered)
        self.assertIn("never writes to source data", rendered)

    def test_evidence_names_all_three_workings(self):
        rendered = text_of(self.app)
        self.assertIn("Supplier rows read for this part", rendered)
        self.assertIn("Finished goods and quantities behind the usage figure",
                      rendered)
        self.assertIn("Lead time record used", rendered)

    def test_the_interface_is_legible_with_no_colour_at_all(self):
        # Colour never carries information alone: strip it and nothing is lost,
        # which is also why the six completeness states are words.
        rendered = text_of(self.app)
        self.assertGreater(len(rendered), 2000)
        self.assertIn("days", rendered)


class TestFindOutSurface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app = run_app()
        app.sidebar.radio[0].set_value("find_out").run()
        cls.app = app

    def test_it_asks_what_to_go_and_find_out(self):
        self.assertIn("What should I go and find out?", text_of(self.app))

    def test_the_row_is_a_field_not_a_part(self):
        self.assertIn("One row per field to fetch, not per part",
                      text_of(self.app))

    def test_it_names_a_field_and_what_fetching_it_would_settle(self):
        rendered = text_of(self.app)
        self.assertIn("on_hand_units", rendered)
        self.assertIn("would settle whether", rendered)

    def test_it_forecasts_nothing(self):
        rendered = text_of(self.app).lower()
        for forbidden in ("estimated", "projected", "likely to be", "assumed"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, rendered)

    def test_it_offers_no_decision_control(self):
        # Fetching a field is not a decision, so there is nothing to record.
        self.assertEqual(len(self.app.button), 0)


class TestConfirmSurface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        cls.app = app

    def test_it_asks_whether_the_reviewer_agrees(self):
        self.assertIn("Do I agree with your model?", text_of(self.app))

    def test_it_says_the_system_will_not_decide_these_alone(self):
        self.assertIn("will not make alone", text_of(self.app))
        self.assertIn("however complete the data is", text_of(self.app))

    def test_every_cluster_offers_a_control(self):
        # The mirror of the exposure surface: recommends findings have controls
        # and executed ones do not, and both halves are asserted.
        self.assertGreater(len(self.app.button), 0)

    def test_a_cluster_is_confirmed_as_one_act(self):
        self.assertIn("members, confirmed as one act", text_of(self.app))

    def test_a_reason_code_selector_is_offered(self):
        self.assertGreater(len(self.app.selectbox), 0)

    # Regression: ISSUE-002 - the reason selector carried a blank first option,
    # so "no reason" looked like a reason a reviewer could pick. Choosing it
    # spent a click and returned the generic refusal.
    # Found by /qa on 2026-08-05
    # Report: .gstack/qa-reports/qa-report-supplier-exposure-agent-2026-08-05.md
    def test_no_reason_selector_offers_a_blank_choice(self):
        for selector in self.app.selectbox:
            self.assertNotIn("", list(selector.options),
                             "an unnamed reason is not a reason a reviewer "
                             "can choose")

    def test_every_reason_selector_starts_unset(self):
        for selector in self.app.selectbox:
            self.assertIsNone(selector.value,
                              "a reason must be chosen deliberately, never "
                              "carried in as a default")

    def test_a_decision_without_a_reviewer_name_is_refused(self):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        warnings = "\n".join(str(w.value) for w in app.warning)
        self.assertIn("anonymous decision is not a decision", warnings)

    # Regression: ISSUE-001 - the reviewer name was cleared by any navigation
    # away from this surface, so a reviewer who checked a figure on another
    # surface came back anonymous and their next decision was refused.
    # Found by /qa on 2026-08-05
    # Report: .gstack/qa-reports/qa-report-supplier-exposure-agent-2026-08-05.md
    def test_the_reviewer_name_survives_leaving_and_returning(self):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.sidebar.text_input[0].set_value("Ada Lovelace").run()

        app.sidebar.radio[0].set_value("exposure").run()
        app.sidebar.radio[0].set_value("confirm").run()

        self.assertEqual(app.sidebar.text_input[0].value, "Ada Lovelace",
                         "a reviewer who navigates away must not silently "
                         "become anonymous on returning")

    def test_the_panel_renders_before_the_first_decision(self):
        """A panel that appears only after a decision cannot teach it exists.

        The empty state is a RECORDED zero, the reviewer's own count of their own
        decisions, so a figure is honest here in a way it would not be for a
        measurement.
        """
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        self.assertIn("Decisions you recorded in this session",
                      [str(s.value) for s in app.subheader])
        self.assertIn("No decision has been recorded", text_of(app))

    def test_the_panel_says_the_record_is_session_scoped_and_unwritten(self):
        # An emptied log and a fresh session render identically unless the
        # wording separates them. Stated at full weight, not dimmed to a caption.
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        self.assertIn("this browser session only", text_of(app))
        self.assertIn("written to disk", text_of(app))

    def test_a_recorded_decision_appears_in_the_panel(self):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.sidebar.text_input[0].set_value("Ada Lovelace").run()
        app.button[0].click().run()

        rendered = text_of(app)
        self.assertNotIn("No decision has been recorded", rendered)
        self.assertIn("Accepted by Ada Lovelace", rendered)
        self.assertIn("covering 28 members", rendered,
                      "the panel must carry the arity of the act")

    def test_the_panel_states_the_denominator_and_declares_its_order(self):
        # The denominator leads, as it does on the exposure surface: what is
        # outstanding is the unknown. The order is declared because a linear list
        # with no stated order reads as a ranking.
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.sidebar.text_input[0].set_value("Ada Lovelace").run()
        app.button[0].click().run()

        rendered = text_of(app)
        self.assertIn("1 decision recorded", rendered)
        self.assertIn("still outstanding", rendered)
        self.assertIn("in the order they were recorded", rendered)

    def test_the_panel_offers_no_control(self):
        """Append-only means no undo and no delete.

        It also protects the tests above: a button here would shift the
        positional indices that reach the cluster controls.
        """
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        before = len(app.button)
        app.sidebar.text_input[0].set_value("Ada Lovelace").run()
        app.button[0].click().run()
        self.assertEqual(len(app.button), before,
                         "the panel added a control, or shifted the indices "
                         "three other tests depend on")

    def test_the_panel_assembles_no_prose_of_its_own(self):
        """Its wording is golden-pinned in the renderer, beside the coverage panel.

        `README.md` claims the interface displays the renderer's output and
        assembles nothing of its own. Writing these strings inline is the shortest
        path and it would make that claim false.
        """
        import ast
        tree = ast.parse(SOURCE)
        panel = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                     and n.name == "render_decision_panel")
        # Every string constant in the function, minus its docstring. A literal
        # long enough to be a sentence is prose the renderer should own.
        literals = [n.value for n in ast.walk(panel)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        prose = [s for s in literals[1:] if len(s) > 12]
        self.assertEqual(prose, [],
                         f"panel assembles its own prose: {prose}")

    def test_no_painter_shadows_a_module_level_helper(self):
        """A widget local named after a helper breaks every later call to it.

        `note = st.text_input("Note", ...)` inside render_confirm bound a
        function-local `note` for the whole function, so anything added below it
        that called the module's note() helper raised "TypeError: 'str' object is
        not callable" and pointed at itself rather than at the collision. The
        decision panel is appended to exactly that function.
        """
        import ast
        tree = ast.parse(SOURCE)
        helpers = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            bound = {t.id for node in ast.walk(fn)
                     if isinstance(node, ast.Assign)
                     for t in node.targets if isinstance(t, ast.Name)}
            with self.subTest(function=fn.name):
                self.assertFalse(
                    bound & (helpers - {fn.name}),
                    f"{fn.name} binds a local named after a module helper: "
                    f"{sorted(bound & (helpers - {fn.name}))}")

    def test_a_recorded_decision_carries_a_real_timestamp(self):
        """The app was stamping every decision at the Unix epoch.

        `actions.apply` defaults `at` to 1970-01-01 so that src/ and the tests
        stay deterministic, and nothing was overriding it. Nothing displayed the
        field, so the defect was invisible. The clock belongs at the interface,
        which is the only layer allowed to be nondeterministic.
        """
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.sidebar.text_input[0].set_value("Ada Lovelace").run()
        app.button[0].click().run()

        log = app.session_state["log"]
        self.assertEqual(len(log), 1)
        recorded = log.events()[0]
        self.assertNotEqual(recorded.at, "1970-01-01T00:00:00+00:00",
                            "a decision stamped at the epoch is not a record")
        self.assertTrue(recorded.at.startswith("20"),
                        f"expected a real ISO timestamp, got {recorded.at!r}")

    def test_the_clock_is_not_reachable_from_the_model_or_the_renderer(self):
        """Determinism is a property of src/, enforced rather than intended.

        `evals/` is frozen under a manifest and every rendered sentence is
        golden-pinned, so a clock anywhere under src/ would make one of those
        two either fake or unstable.
        """
        for module in ("src/governance/render.py", "src/interface/actions.py",
                       "src/interface/model.py"):
            source = (APP.parent / module).read_text()
            with self.subTest(module=module):
                self.assertNotIn("datetime.now", source)
                self.assertNotIn("time.time", source)
                self.assertNotIn("utcnow", source)

    def test_a_decision_after_navigating_away_and_back_is_recorded(self):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.sidebar.text_input[0].set_value("Ada Lovelace").run()
        app.sidebar.radio[0].set_value("find_out").run()
        app.sidebar.radio[0].set_value("confirm").run()

        app.button[0].click().run()
        self.assertFalse(app.exception)
        warnings = "\n".join(str(w.value) for w in app.warning)
        self.assertNotIn("anonymous decision is not a decision", warnings)
        self.assertTrue(any("Recorded:" in str(s.value) for s in app.success))


class TestBadgesAreNominal(unittest.TestCase):
    """A badge set with an order is a severity scale in disguise."""

    def test_the_badge_rule_declares_one_background_and_one_text_colour(self):
        block = SOURCE.split(".badge {")[1].split("}")[0]
        self.assertEqual(len(re.findall(r"\bbackground:", block)), 1)
        self.assertEqual(len(re.findall(r"(?<!-)\bcolor:", block)), 1)

    def test_only_form_distinguishes_the_badge_variants(self):
        """Two variants, and neither is a step on a scale.

        `open` marks that a row carries a control, `absent` marks that something
        is not established. Both are distinctions in KIND, and both are drawn
        with form (fill, border style) rather than intensity, so adding a third
        cannot accidentally build a ramp. The rule that matters is not the count
        of variants but that no variant is ordered against another.
        """
        variants = re.findall(r"\.badge\.(\w+)\s*{", SOURCE)
        self.assertEqual(sorted(variants), ["absent", "open"])
        for variant in variants:
            block = SOURCE.split(f".badge.{variant} {{")[1].split("}")[0]
            with self.subTest(variant=variant):
                self.assertNotIn("opacity", block,
                                 "opacity is intensity, and a dimmed chip "
                                 "reads as a lesser one")
                self.assertNotIn("font-size", block,
                                 "size is magnitude")
                self.assertNotIn("font-weight", block,
                                 "weight is magnitude")

    def test_the_category_palette_is_nominal_by_arithmetic(self):
        """The category palette has no hue at all, so it cannot carry an order.

        The predecessor of this test asserted equal HSL saturation and lightness
        strings and called that "no chip is darker, stronger or warmer than
        another". It passed while the claim was false, because HSL lightness is
        not perceptual lightness: in CIELAB the six completeness entries spanned
        15.3 L* points and sorted into a brightness ramp in declaration order.

        THE LESSON IS THE SHAPE OF THE BUG, NOT THE COLOUR SPACE. Restating the
        same assertion in OKLCH would repeat the category error one space over.
        A test must assert the PROPERTY. Here the property is now absolute and
        needs no colour arithmetic to check: no category-varying colour is
        emitted anywhere, so no reading of the set can produce an order.
        """
        import review_app
        self.assertFalse(hasattr(review_app, "CATEGORY_HUE"),
                         "a per-category hue map is the encoding this palette "
                         "refuses; the label carries the category")
        self.assertFalse(hasattr(review_app, "chip_colour"),
                         "nothing may compute a colour from a category name")
        for dead in ("COOL_BAND", "CHIP_SATURATION", "CHIP_LIGHTNESS"):
            with self.subTest(symbol=dead):
                self.assertFalse(hasattr(review_app, dead))

    def test_no_chip_carries_an_inline_colour(self):
        """Strip every colour and no information may be lost (CLAUDE.md).

        An inline style on a chip is how a category-keyed colour would return,
        and it would bypass the `.badge` rule that the stylesheet tests police.
        """
        import review_app
        from src import governance as gov
        for text in ("14 parts", "4 items", gov.EXECUTES, gov.RECOMMENDS,
                     "known", "upper_bound", "not_applicable", "region"):
            for kwargs in ({}, {"open_style": True}, {"absent": True}):
                with self.subTest(text=text, variant=kwargs):
                    self.assertNotIn("style=", review_app.badge(text, **kwargs))
                    self.assertNotIn("hsl(", review_app.badge(text, **kwargs))

    def test_an_absence_is_never_dimmed_or_shrunk(self):
        """Dimming an unknown says it matters less, which is the lie refused.

        The `absent` variant may differ from a plain chip only in border style.
        Any opacity, size or weight difference would make absence read as a
        lesser kind of presence.
        """
        block = SOURCE.split(".badge.absent {")[1].split("}")[0]
        for banned in ("opacity", "font-size", "font-weight"):
            with self.subTest(property=banned):
                self.assertNotIn(banned, block)
        # border-color is form; a bare color: would restyle the label itself.
        self.assertIsNone(re.search(r"(?<!-)\bcolor:", block),
                          "the label keeps the same text colour as any chip")
        self.assertIn("border-style: dashed", block,
                      "form, not colour, so it survives greyscale and print")

    def test_every_absence_kind_the_model_emits_has_a_label(self):
        """A kind with no label renders as an unexplained absence.

        This is the coupling that rots: the model gains a fourth coverage kind
        and the painter silently drops it, so a reader sees an absence with no
        statement of which kind it is.
        """
        import review_app
        from src.interface import model as view
        from src.pipeline import default_data_dir, run, surfaces
        built = surfaces(run(data_dir=default_data_dir()))
        kinds = {note.kind
                 for note in built[view.EXPOSURE].coverage.notes}
        self.assertTrue(kinds, "the fixture data must exercise some absence")
        for kind in kinds:
            with self.subTest(kind=kind):
                self.assertIn(kind, review_app.ABSENCE_LABEL)
                self.assertTrue(review_app.absence_chip(kind))

    def test_an_unrecognised_absence_kind_gets_no_label_rather_than_a_guess(self):
        import review_app
        self.assertEqual(review_app.absence_chip("something new"), "")
        self.assertEqual(review_app.absence_chip(""), "")

    def test_the_chip_label_is_legible_rather_than_a_dense_monogram(self):
        """0.68rem uppercase monospace was below the practical reading floor.

        All caps removes word shape and forces letter by letter reading, and a
        long category name would truncate. A truncated epistemic state is a
        wrong claim.
        """
        block = SOURCE.split(".badge {")[1].split("}")[0]
        self.assertGreaterEqual(resolved_font_px(block), 12.0,
                                "12px is the floor for any chip label")
        self.assertNotIn("text-transform: uppercase", block)
        self.assertNotIn("monospace", block,
                         "a category name is prose, not an identifier")
        self.assertNotIn("white-space: nowrap", block,
                         "a category name wraps rather than truncating")

    def test_no_badge_style_encodes_a_severity(self):
        """DECLARATIONS ONLY, with comments stripped and word boundaries.

        The sixth time this hazard has bitten in this repository, and always
        the same way: a system that refuses concepts by name contains those
        names in its refusals. "high" lives inside "high information per
        screen" and "red" inside "bordered", so a substring scan of the raw
        source flags the prose explaining the rule as a breach of it.
        """
        css = SOURCE.split("<style>")[1].split("</style>")[0]
        declarations = re.sub(r"/\*.*?\*/", " ", css, flags=re.S).lower()
        for word in ("danger", "warning", "critical", "severity", "risk",
                     "high", "low", "red", "amber", "green", "orange"):
            with self.subTest(word=word):
                self.assertIsNone(re.search(rf"\b{word}\b", declarations))
        for ramp in ("#d00", "#f00", "#ff0000", "#e74c3c", "#2ecc71"):
            with self.subTest(colour=ramp):
                self.assertNotIn(ramp, declarations)

    def test_the_label_carries_the_meaning_not_the_chip(self):
        # Legible with every colour stripped, which the plain-text check
        # already asserts for the page as a whole.
        rendered = text_of(run_app())
        self.assertIn("executes", rendered)
        self.assertIn("parts", rendered)


class TestStructuralViews(unittest.TestCase):
    """Both encode WHICH, never HOW MUCH."""

    def test_the_exposure_page_shows_a_blocking_matrix(self):
        rendered = text_of(run_app())
        self.assertIn("What each part blocks", rendered)
        self.assertIn("which, never how much", rendered)

    def test_the_confirm_page_shows_a_cluster_membership_grid(self):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        rendered = text_of(app)
        self.assertIn("Who sits with whom", rendered)
        self.assertIn("nothing here is ordered or scored", rendered)

    def test_the_matrix_marks_are_identical_so_nothing_reads_as_a_quantity(self):
        from src.interface import model as view
        from src.pipeline import run, surfaces
        result = run()
        surface = surfaces(result)[view.EXPOSURE]
        parts = sorted({row.key for layer in surface.layers for group in layer
                        for row in group.rows})
        goods, matrix = view.blocking_matrix(parts, surface.evidence_by_part)
        marks = {cell for row in matrix for key, cell in row.items()
                 if key != "part"}
        self.assertEqual(marks - {""}, {view.MARK},
                         "a second mark would be a magnitude encoding")

    def test_the_cluster_grid_holds_identifiers_and_no_numbers(self):
        from src.interface import model as view
        from src.pipeline import run
        grid = view.cluster_membership(run().report)
        self.assertTrue(grid)
        for row in grid:
            with self.subTest(part=row["part"]):
                self.assertEqual(set(row), {"part", "supplier", "region"})
                for value in row.values():
                    self.assertIsInstance(value, str)


class TestStandingLine(unittest.TestCase):

    def test_it_says_the_data_is_synthetic_and_the_figures_illustrative(self):
        # A reader who does not know the counts belong to one seed will read
        # one as a finding rather than as machinery firing.
        rendered = text_of(run_app())
        self.assertIn("Demonstration on synthetic data", rendered)
        self.assertIn("illustrative at seed 42", rendered)

    def test_it_links_to_the_source(self):
        self.assertIn("github.com/Lakshya2905/supplier-exposure-agent",
                      text_of(run_app()))

    def test_it_appears_once_and_carries_no_marketing_register(self):
        rendered = text_of(run_app())
        self.assertEqual(rendered.count("Demonstration on synthetic data"), 1)
        for adjective in ("powerful", "intelligent", "advanced", "seamless",
                          "comprehensive", "cutting-edge", "smart"):
            with self.subTest(word=adjective):
                self.assertNotIn(adjective, rendered.lower())


class TestSurfacesStaySeparate(unittest.TestCase):

    def test_only_one_surface_renders_at_a_time(self):
        # Asserted on the page HEADING rather than on substring absence. The
        # navigation now carries each surface's question as a subtitle, so the
        # words appear on every page; what must not appear twice is a surface.
        from src.interface import model as view
        app = run_app()
        headings = {str(element.value) for element in app.title}
        questions = headings & set(view.SURFACE_QUESTION.values())
        self.assertEqual(questions, {"What is worst?"},
                         "exactly one surface may render at a time")

    def test_the_sidebar_states_why_they_are_separate(self):
        rendered = text_of(run_app())
        self.assertIn("deliberately separate", rendered)
        self.assertIn("a part, a field, a cluster", rendered)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
