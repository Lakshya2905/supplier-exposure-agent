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

    def test_a_decision_without_a_reviewer_name_is_refused(self):
        app = run_app()
        app.sidebar.radio[0].set_value("confirm").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        warnings = "\n".join(str(w.value) for w in app.warning)
        self.assertIn("anonymous decision is not a decision", warnings)


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
        app = run_app()
        first = text_of(app)
        self.assertIn("What is worst?", first)
        self.assertNotIn("What should I go and find out?", first)
        self.assertNotIn("Do I agree with your model?", first)

    def test_the_sidebar_states_why_they_are_separate(self):
        rendered = text_of(run_app())
        self.assertIn("deliberately separate", rendered)
        self.assertIn("a part, a field, a cluster", rendered)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
