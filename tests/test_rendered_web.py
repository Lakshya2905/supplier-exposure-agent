"""What the SHIPPING page painted, asserted against what it claims.

`tests/test_rendered_page.py` measures `review_app.py`. docs/HANDOFF.md calls
that surface "not the deliverable any more", so until this module existed the
app a reader actually opens was measured by nothing in a browser. DESIGN.md's
Motion section names the consequence at the end of *The loading state pulsed for
six weeks*: "nothing measures `web/` in a browser. Pointing the rendered checks
at the Next.js app is what would have caught this on the day it shipped."

WHAT IT WOULD HAVE CAUGHT. `SkeletonText` and `SkeletonPlaceholder` resolve in
the browser to `animation: 3s ease-in-out infinite cds--skeleton`. That pulse
ran on all six surfaces for the whole of every load while the Motion section was
marked [SHIPPED] and claimed "zero animations, verified by source scan". Every
source-reading test was happy: the scan read this repository's stylesheets and
the animation was injected by the component library, where no source read
reaches.

**THE PULSE IS BACK, DELIBERATELY, AND THIS MODULE DOES NOT FORBID IT.** The
owner retired the no-skeleton rule on 2026-09-16 in favour of the v2 build
prompt, on the record, and DESIGN.md carries the decision and its cost. So the
assertion here is not "nothing animates" -- that would be this suite asserting a
rule that no longer exists. It is:

  nothing animates that the design has not accepted, by keyframe name
  nothing animates AT ALL for a reader who asked for less motion

The second is the load-bearing one. DESIGN.md says Carbon honouring
`prefers-reduced-motion: reduce` "is the only reason this is a cost rather than
an accessibility defect", and that sentence is the whole foundation of the
exception. It was verified by hand once. Now it is measured on every run.

MEASURED IN THE LOADING STATE, and that is the point rather than a detail. A
skeleton exists only while data is in flight: a probe that waited for the page
to settle would have found a clean document and reported one. So the first
request each surface makes is held open and the page read while it is provably
still waiting.

One boot for the whole module: one API, one frontend, one browser, four states
of six routes.
"""
import re
import unittest

from tests import rendered
from tests.rendered import (REDUCED, STATES, contrast, parse,
                            playwright_or_skip, web_build_or_skip, web_routes)

playwright_or_skip()   # decides skip-versus-fail before anything is served
web_build_or_skip()


class RenderedWeb(unittest.TestCase):
    """One browser session for the whole module."""

    readings = None

    sorting = None

    @classmethod
    def setUpClass(cls):
        if RenderedWeb.readings is None:
            measured = rendered.collect_web()
            RenderedWeb.readings = measured["states"]
            RenderedWeb.sorting = measured["sorting"]
        cls.readings = RenderedWeb.readings
        cls.sorting = RenderedWeb.sorting

    def states(self):
        """Every (route, state, probe) there is, loading included."""
        for route, states in self.readings.items():
            for state, probe in states.items():
                if probe is not None:
                    yield route, state, probe

    def settled(self):
        """The default context, once the run has arrived.

        Colour and boundary are properties of the paint and do not move with a
        motion preference, so they are read once rather than four times.
        """
        return [(route, states["settled"])
                for route, states in self.readings.items()]

    def asked_for_less_motion(self, state):
        return state.endswith(REDUCED)


class TestTheScanReachedTheRunningApp(RenderedWeb):
    """Named for the way a rendered check dies: quietly, measuring nothing.

    Every assertion below is a loop over what was measured, so an empty reading
    passes all of them. This class is the one that fails instead.
    """

    def test_every_route_the_navigation_declares_was_measured(self):
        self.assertEqual(sorted(self.readings), sorted(web_routes()))
        self.assertGreaterEqual(len(self.readings), 2)

    def test_the_loading_state_was_captured_on_every_route(self):
        """The state the defect lived in, and it is not caught by luck.

        The first request the surface makes is held open while the probe runs,
        so "the page was still waiting" is something this check enforces rather
        than something it hopes for. Without it a fast API would settle the page
        before anything was read and the pulse would be measured on a page that
        had stopped pulsing.

        THE FIRST REQUEST, NOT THE SCORE. Holding the score was a flake with a
        fast machine's name on it: What changed waits on `/api/runs` and the
        Decision log on `/api/decisions`, and either could arrive first. The
        first request is the one moment every surface is provably still in its
        initial state, because nothing has arrived yet.
        """
        for route, state, probe in self.states():
            if not state.startswith("loading"):
                continue
            with self.subTest(route=route, state=state):
                self.assertNotIn("error", probe, str(probe))
                self.assertTrue(
                    probe["busy"],
                    "the page was not waiting when it was measured, so a "
                    "loading-state defect could not have been seen")

    def test_no_state_went_unmeasured(self):
        # A None reading means the request was never intercepted, which is how
        # this whole module would come to assert nothing at all.
        for route, states in self.readings.items():
            for state, probe in states.items():
                with self.subTest(route=route, state=state):
                    self.assertIsNotNone(probe)

    def test_every_state_carries_a_real_document(self):
        for route, state, probe in self.states():
            with self.subTest(route=route, state=state):
                self.assertGreater(probe["elements"], 50)

    def test_the_settled_page_is_no_longer_waiting(self):
        for route, probe in self.settled():
            with self.subTest(route=route):
                self.assertFalse(probe["busy"])


class TestNothingAnimatesThatTheDesignHasNotAccepted(RenderedWeb):
    """Motion, measured on every element and both pseudo-elements.

    NOT "NOTHING ANIMATES". The loading state animates on purpose: the owner
    retired the no-skeleton rule on 2026-09-16 and DESIGN.md carries the
    decision, the objection it overruled and what it costs. A suite that went on
    asserting the retired rule would be enforcing a document that no longer says
    it, which is the mirror image of the failure this module exists for.

    So the question this asks is the one that survives the exception: is every
    keyframe running on the page one somebody accepted? A second Carbon
    component that animates for its own reasons is exactly what nothing in this
    repository can see, and it would arrive silently.
    """

    #: Accepted by name, hand-written, with what accepted it. Read as a list of
    #: decisions rather than a list of strings: adding a name here is adding a
    #: motion to the product, and it should be as awkward as that sounds.
    ACCEPTED = {
        "cds--skeleton":
            "the skeleton exception in DESIGN.md's Motion section, retired "
            "from the no-skeleton rule by the owner on 2026-09-16 in favour of "
            "the v2 build prompt, which asks for SkeletonText and "
            "SkeletonPlaceholder by name for this state",
    }

    def test_every_running_animation_is_one_the_design_accepted(self):
        for route, state, probe in self.states():
            if self.asked_for_less_motion(state):
                continue          # the class below asserts more than this one
            for animation in probe["animations"]:
                with self.subTest(route=route, state=state,
                                  element=animation["cls"] or animation["tag"]):
                    self.assertIn(
                        animation["name"], self.ACCEPTED,
                        f"{animation['tag']} {animation['cls']!r} on {route} "
                        f"({state}) runs {animation['name']} for "
                        f"{animation['duration']} x "
                        f"{animation['iterations']} on its "
                        f"{animation['pseudo']}, and nothing accepted that "
                        f"keyframe. Either it is a defect a source scan cannot "
                        f"see, or it is a decision, and a decision belongs in "
                        f"DESIGN.md before it belongs here")


class TestNothingAnimatesForAReaderWhoAskedForLessMotion(RenderedWeb):
    """The sentence the skeleton exception rests on, measured.

    DESIGN.md: "Carbon's own mixin honours `prefers-reduced-motion: reduce`,
    which is the only reason this is a cost rather than an accessibility
    defect." That is a claim about the rendered page under a preference nobody
    was testing, made once by hand, and it is carrying an exception to a rule.

    It is asserted here at its full strength -- **no** animation, not "fewer",
    not "the skeleton only" -- because the claim being relied on is that a
    reader who asks for stillness gets it.
    """

    def test_the_reduced_motion_context_was_actually_measured(self):
        for route, states in self.readings.items():
            with self.subTest(route=route):
                self.assertEqual(sorted(states), sorted(STATES))

    def test_no_element_or_pseudo_element_animates_under_reduce(self):
        for route, state, probe in self.states():
            if not self.asked_for_less_motion(state):
                continue
            for animation in probe["animations"]:
                with self.subTest(route=route, state=state,
                                  element=animation["cls"] or animation["tag"]):
                    self.fail(
                        f"{animation['tag']} {animation['cls']!r} on {route} "
                        f"({state}) still runs {animation['name']} for "
                        f"{animation['duration']} x {animation['iterations']}. "
                        f"The skeleton exception in DESIGN.md rests on this "
                        f"not happening")

class TestThisApplicationDeclaresNoMotionOfItsOwn(RenderedWeb):
    """The rule that survived the exception, read off the running page.

    `tests/test_web_motion.py` holds the same rule against `web/`'s `.scss`. This
    is the rendered half, and it reaches two places that scan cannot.
    """

    def test_no_rule_this_application_wrote_declares_motion(self):
        """WHAT THIS DOES NOT CLAIM, stated rather than left to be assumed.

        Carbon transitions its own controls on hover, focus and expand at 70ms
        to 300ms — the side nav links, the buttons, the header panel, the text
        inputs, the modal — and this does not assert those are absent, because
        they are not. DESIGN.md's Motion section records that measurement rather
        than claiming the page has none.

        ATTRIBUTION IS BY RULE, NEVER BY ELEMENT. A table cell carries
        `.cds--structured-list-td` and `.sea-figure` at once, and reading the
        second as ownership reports Carbon's 110ms colour fade as this
        repository's — the same mistake as flagging an expander chevron for
        having no chevron, which this suite has made once already.

        THE TWO PLACES THE `.scss` SCAN CANNOT REACH: the compiled bundle, and a
        `style={{transition}}` prop, which lands in an element's inline style
        and in no stylesheet at all.
        """
        for route, state, probe in self.states():
            for declared in probe["ownMotion"]:
                with self.subTest(route=route, state=state,
                                  what=declared["what"]):
                    self.fail(
                        f"{declared['what']} on {route} ({state}) declares "
                        f"motion in a {declared['where']}: "
                        f"{declared['transition'] or declared['animation']}. "
                        f"The only permitted state change is instantaneous")


class TestEveryPaintedColourIsAThemeToken(RenderedWeb):
    """The ramp check, restated for a surface with no ramp of its own.

    `globals.scss` says it: "there are no hex values in this file or in any
    component, because a hardcoded colour is how a design system stops being
    one." That is a claim about the source. This is the same claim about the
    pixel, which is where the Streamlit surface found two declared steps that
    were never painted at all.

    The declared set is whatever `--cds-*` resolves to in the live document,
    read from the browser rather than parsed, because a token may be written in
    any notation and only one of those gets painted.
    """

    def tokens(self):
        return {colour for _route, probe in self.settled()
                for colour in probe["tokens"]}

    def test_the_theme_resolved(self):
        self.assertGreater(len(self.tokens()), 20,
                           "no Carbon token resolved, so the assertion below "
                           "compares against an empty set and cannot fail")

    def test_no_text_is_painted_a_colour_the_theme_does_not_define(self):
        tokens = self.tokens()
        for route, probe in self.settled():
            for colour, samples in probe["painted"].items():
                with self.subTest(route=route, colour=colour):
                    self.assertIn(
                        colour, tokens,
                        f"{colour} is painted on {route} by {samples} and is "
                        f"not a value any --cds- token holds")

    def test_the_page_background_is_a_token_too(self):
        tokens = self.tokens()
        for route, probe in self.settled():
            with self.subTest(route=route):
                self.assertIn(probe["pageBackground"], tokens)


class TestEveryFieldHasAVisibleBoundaryOnScreen(RenderedWeb):
    """WCAG 1.4.11, on the surface that ships.

    The Streamlit version of this found every field drawing its border in the
    same colour as its own fill, at 1.04:1 — the name box a decision cannot be
    recorded without, invisible. Carbon draws ONE edge rather than four, so the
    check reads whichever sides are actually drawn instead of assuming a box.
    """

    NON_TEXT_CONTRAST = 3.0

    def fields(self):
        return [(route, field) for route, probe in self.settled()
                for field in probe["fields"]]

    def test_the_scan_found_the_fields(self):
        self.assertTrue(self.fields(),
                        "no input, select or textarea was found on any "
                        "surface, so the assertions below check nothing")

    def test_every_field_draws_at_least_one_edge(self):
        for route, field in self.fields():
            drawn = [side for side in field["sides"]
                     if side["width"] not in ("0px", "")]
            with self.subTest(route=route, field=field["cls"]):
                self.assertTrue(
                    drawn,
                    f"{field['cls']!r} on {route} is {field['width']}x"
                    f"{field['height']} and draws no border on any side, so "
                    f"the box has no edge")

    def test_every_drawn_edge_clears_three_to_one_against_its_own_fill(self):
        for route, field in self.fields():
            for side in field["sides"]:
                if side["width"] in ("0px", ""):
                    continue
                measured = contrast(parse(side["colour"]), parse(field["fill"]))
                with self.subTest(route=route, field=field["cls"],
                                  side=side["side"]):
                    self.assertGreaterEqual(
                        measured, self.NON_TEXT_CONTRAST,
                        f"the {side['side'].lower()} edge of {field['cls']!r} "
                        f"on {route} is {measured:.2f}:1 against the field's "
                        f"own fill")

    def test_every_drawn_edge_clears_three_to_one_against_the_surface(self):
        for route, field in self.fields():
            for side in field["sides"]:
                if side["width"] in ("0px", ""):
                    continue
                measured = contrast(parse(side["colour"]),
                                    parse(field["behind"]))
                with self.subTest(route=route, field=field["cls"],
                                  side=side["side"]):
                    self.assertGreaterEqual(
                        measured, self.NON_TEXT_CONTRAST,
                        f"the {side['side'].lower()} edge of {field['cls']!r} "
                        f"on {route} is {measured:.2f}:1 against what is "
                        f"behind it")


class TestTheTableRanksTheFigureAndNeverRanksAbsence(RenderedWeb):
    """Sorting a measure column, measured by clicking it.

    TWO DEFECTS, ONE CAUSE, NEITHER VISIBLE TO A SOURCE READ. `isSortable` with
    no comparator hands Carbon's default a rendered string:

      ascending on "How much of the build stops" put **900 above 12,000**,
      because the collator compares digit runs and a thousands separator ends
      the first one

      descending put **nine "not enough data to say" rows above 772.2 days**,
      because a letter sorts after a digit

    The second is the one this product cannot have: "Never impute a missing
    value in order to rank something. A list ordered by a guessed value is a
    forecast wearing a work queue's clothes." Nothing decided it; a locale
    collator did, and `web/` said only `isSortable`.
    """

    #: A cell carries a figure when a number can be read from it. The structural
    #: reading ("at least 1 finished good, none of them in the demand plan")
    #: deliberately carries no figure on this axis and must not be ranked on it,
    #: so it is identified by its own words rather than by its digits.
    NO_FIGURE = ("not enough data to say", "does not apply here",
                 "no supplier on file", "finished good")

    def has_figure(self, text):
        return not any(phrase in text for phrase in self.NO_FIGURE)

    def number(self, text):
        return float(re.sub(r"[^\d.]", "", text.split()[0]) or 0)

    def columns(self):
        return self.sorting.items()

    def test_a_measure_column_was_actually_sorted(self):
        self.assertTrue(self.sorting, "no column was measured")
        for column, reading in self.columns():
            with self.subTest(column=column):
                self.assertEqual(reading["ascending"]["ariaSort"], "ascending")
                self.assertEqual(reading["descending"]["ariaSort"], "descending")
                self.assertGreater(len(reading["ascending"]["cells"]), 3)

    def test_the_figures_are_ordered_by_their_value(self):
        """900 against 12,000, which is the defect stated as a property."""
        for column, reading in self.columns():
            for direction, expected in (("ascending", 1), ("descending", -1)):
                figures = [self.number(cell["text"])
                           for cell in reading[direction]["cells"]
                           if self.has_figure(cell["text"])]
                for first, second in zip(figures, figures[1:]):
                    with self.subTest(column=column, direction=direction,
                                      pair=(first, second)):
                        self.assertLessEqual(
                            (first - second) * expected, 0,
                            f"{first} then {second} reading {direction} down "
                            f"{column!r}: the column is ordered by something "
                            f"other than the number in it")

    def test_a_row_with_no_figure_is_not_ranked(self):
        """The direction-independence is the whole assertion.

        A row that moves when the sort direction flips is a row being compared,
        and there is nothing to compare: the figure is absent. So the unranked
        rows must appear in the same order at the same end either way.
        """
        for column, reading in self.columns():
            tails = {}
            for direction in ("ascending", "descending"):
                cells = reading[direction]["cells"]
                tails[direction] = [cell["part"] for cell in cells
                                    if not self.has_figure(cell["text"])]
                ranked = [index for index, cell in enumerate(cells)
                          if self.has_figure(cell["text"])]
                unranked = [index for index, cell in enumerate(cells)
                            if not self.has_figure(cell["text"])]
                with self.subTest(column=column, direction=direction):
                    if ranked and unranked:
                        self.assertLess(
                            max(ranked), min(unranked),
                            f"a part with no figure for {column!r} is sitting "
                            f"among the parts that have one")
            with self.subTest(column=column):
                self.assertEqual(
                    tails["ascending"], tails["descending"],
                    f"the unranked parts under {column!r} move when the sort "
                    f"direction flips, so they are being compared")

    def test_the_page_says_how_many_it_declined_to_rank(self):
        for column, reading in self.columns():
            unranked = [cell for cell in reading["ascending"]["cells"]
                        if not self.has_figure(cell["text"])]
            note = reading["ascending"]["note"]
            with self.subTest(column=column):
                if not unranked:
                    continue    # nothing to state
                self.assertIsNotNone(
                    note, f"{len(unranked)} parts were left out of the ordering "
                          f"under {column!r} and the page does not say so")
                self.assertIn(str(len(unranked)), note)
                self.assertIn(column.lower(), note.lower())


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
