"""The view model as data, with no UI framework involved.

This is where the autonomy claim is asserted, because keeping the model pure is
what makes it assertable at all. If an executed finding and a recommends finding
were only distinguished by styling, the claim would be checkable by screenshot
and nothing else.
"""
import unittest
from fractions import Fraction

from src import archetypes as A
from src import governance as gov
from src import ranking, scoring
from src.demand import USAGE_KNOWN, Usage
from src.interface import actions
from src.interface import model as view


def build(part="AA-P-01", on_hand=100, tooling="company",
          lead_times=((30, 45),), verdict="single_source"):
    usage = Usage(part, Fraction(1000), USAGE_KNOWN,
                  blocked_finished_good_units=1000, reasons=("fixture",))
    return scoring.score_part(
        part_number=part, verdict=verdict, rows=(), usage=usage,
        on_hand_units=on_hand, tooling_owner=tooling,
        lead_times=list(lead_times))


class Row:
    """A stand-in exploded row, so the model can be tested without a BOM."""

    def __init__(self, finished_good, qty):
        self.finished_good = finished_good
        self.qty_per_finished_good = Fraction(qty)


def evidence(part="AA-P-01"):
    return view.evidence_for(
        part,
        supplier_records=(("Braxton Industries", "south_asia"),
                          ("Oakhaven Mfg", "emea")),
        exploded_rows=(Row("FG-01", 4), Row("FG-99", 2)),
        demand_plan={"FG-01": 12000},
        lead_time_records=(("Braxton Inds", 41, 53),))


class TestAutonomyIsAnAffordance(unittest.TestCase):

    def test_an_executed_row_cannot_carry_a_control(self):
        # THE CLAIM MADE STRUCTURAL. Refused at construction, so it cannot be
        # reintroduced by a template change or a helpful refactor.
        with self.assertRaises(ValueError):
            view.Row(entity=view.PART, key="AA-P-01", sentence="x",
                     autonomy=gov.EXECUTES, evidence=evidence(),
                     controls=(view.Control(action="confirm",
                                            act_kind=gov.ACT_APPROVE,
                                            subject="AA-P-01"),))

    def test_a_recommends_row_may_carry_a_control(self):
        row = view.Row(entity=view.CLUSTER, key="Alpha Works", sentence="x",
                       autonomy=gov.RECOMMENDS,
                       controls=(view.Control(action="confirm",
                                              act_kind=gov.ACT_BULK_APPROVE,
                                              subject="Alpha Works"),))
        self.assertTrue(row.is_actionable)

    def test_no_part_row_is_actionable(self):
        profiles = [build("AA-P-01", tooling="supplier")]
        surface = view.exposure_surface(
            profiles, {"AA-P-01": "single_source"}, A.catalogue(None),
            {"AA-P-01": evidence()})
        for row in surface.all_rows():
            with self.subTest(part=row.key):
                self.assertEqual(row.controls, ())
                self.assertFalse(row.is_actionable)

    def test_every_confirm_row_is_actionable(self):
        # The mirror assertion. If neither surface had controls, the first test
        # would pass by the interface simply doing nothing.
        from src.concentration import analyse
        report = analyse(
            {"P1": "single_source", "P2": "single_source"},
            {"P1": (("Alpha Works", "EMEA"),),
             "P2": (("Alpha Works", "EMEA"),)})
        surface = view.confirm_surface(report)
        self.assertTrue(surface.rows)
        for row in surface.rows:
            with self.subTest(cluster=row.key):
                self.assertTrue(row.is_actionable)
                self.assertEqual(row.autonomy, gov.RECOMMENDS)


class TestEvidenceIsReachableAndReadOnly(unittest.TestCase):

    def test_every_part_row_carries_evidence(self):
        with self.assertRaises(ValueError):
            view.Row(entity=view.PART, key="AA-P-01", sentence="x",
                     autonomy=gov.EXECUTES, evidence=None)

    def test_evidence_names_the_supplier_rows_that_produced_the_verdict(self):
        found = evidence()
        self.assertEqual([r.supplier_name for r in found.supplier_rows],
                         ["Braxton Industries", "Oakhaven Mfg"])
        self.assertEqual([r.region for r in found.supplier_rows],
                         ["south_asia", "emea"])

    def test_evidence_shows_the_cross_file_name_join(self):
        # The two files spell the same supplier differently, and that join is
        # the most load-bearing inference in the pipeline. A reviewer has to be
        # able to see it happened.
        found = evidence()
        self.assertTrue(any("spell the same supplier differently" in note
                            for note in found.notes))
        self.assertTrue(any("Braxton Inds" in note for note in found.notes))

    def test_evidence_names_the_lead_time_record_used(self):
        found = evidence()
        self.assertEqual(found.lead_time_used.supplier_name,
                         "Braxton Industries")
        self.assertEqual(found.lead_time_used.quoted_lead_time_days, 41)

    def test_evidence_shows_finished_goods_and_quantities(self):
        rows = {r.finished_good: r for r in evidence().demand_rows}
        self.assertEqual(rows["FG-01"].qty_per_finished_good, "4")
        self.assertEqual(rows["FG-01"].annual_units, 12000)
        self.assertEqual(rows["FG-01"].contribution, "48000")

    def test_an_absent_finished_good_is_shown_as_absent_not_as_zero(self):
        rows = {r.finished_good: r for r in evidence().demand_rows}
        self.assertIsNone(rows["FG-99"].annual_units)
        self.assertEqual(rows["FG-99"].contribution, "")
        self.assertEqual(evidence().absent_finished_goods, ("FG-99",))

    def test_evidence_explains_why_a_contribution_is_missing(self):
        self.assertTrue(any("absent from the demand plan" in note
                            for note in evidence().notes))

    def test_evidence_carries_no_control_field(self):
        for forbidden in ("controls", "action", "editable", "on_change"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, view.Evidence.__dataclass_fields__)


class TestThreeSurfacesThreeRowEntities(unittest.TestCase):

    def surfaces(self):
        from src.concentration import analyse
        profiles = [build("AA-P-01", tooling="supplier", on_hand=None)]
        verdicts = {"AA-P-01": "single_source"}
        catalogue = A.catalogue(None)
        report = analyse(
            {"P1": "single_source", "P2": "single_source"},
            {"P1": (("Alpha Works", "EMEA"),),
             "P2": (("Alpha Works", "EMEA"),)})
        memberships = ranking.classify(profiles, verdicts, catalogue)
        return (
            view.exposure_surface(profiles, verdicts, catalogue,
                                  {"AA-P-01": evidence()}, report=report),
            view.find_out_surface(memberships, catalogue),
            view.confirm_surface(report),
        )

    def test_each_surface_has_exactly_one_row_entity(self):
        # THE STRUCTURAL ARGUMENT AGAINST MERGING THEM. A unified table has to
        # pick one entity, and the other two get denormalised.
        for surface in self.surfaces():
            with self.subTest(surface=surface.name):
                entities = {row.entity for row in surface.all_rows()}
                self.assertEqual(entities, {surface.row_entity})

    def test_the_three_row_entities_are_all_different(self):
        entities = [surface.row_entity for surface in self.surfaces()]
        self.assertEqual(entities, [view.PART, view.FIELD, view.CLUSTER])
        self.assertEqual(len(set(entities)), 3)

    def test_each_surface_states_its_own_question(self):
        questions = {surface.question for surface in self.surfaces()}
        self.assertEqual(len(questions), 3)

    def test_the_work_queue_row_is_a_field_not_a_part(self):
        # Stage 6 groups by archetype, which answers "what is undecided". This
        # answers "what should I go and get", and that is a list of trips.
        _, find_out, _ = self.surfaces()
        self.assertTrue(find_out.rows)
        for row in find_out.rows:
            with self.subTest(field=row.key):
                self.assertEqual(row.entity, view.FIELD)
                self.assertIn("parts", row.detail)

    def test_a_cluster_is_one_row_not_one_row_per_member(self):
        _, _, confirm = self.surfaces()
        cluster = [row for row in confirm.rows
                   if row.detail.get("members")][0]
        self.assertEqual(len(cluster.detail["members"]), 2)
        self.assertEqual(cluster.detail["member_count"], 2)
        self.assertEqual(
            len([row for row in confirm.rows if row.key == cluster.key]), 1)


class TestCoveragePanel(unittest.TestCase):

    def panel(self):
        from src.concentration import analyse
        profiles = [build("AA-P-01", tooling="supplier", verdict="made_in_house",
                          lead_times=())]
        report = analyse({"P1": "supplier_list_unknown"}, {})
        return view.coverage(profiles, report, None, A.catalogue(None))

    def test_it_reports_unconfirmed_supplier_lists(self):
        subjects = [note.subject for note in self.panel().notes]
        self.assertIn("unconfirmed supplier lists", subjects)

    def test_it_reports_not_applicable_counts_per_dimension(self):
        notes = [note for note in self.panel().notes
                 if "not applicable" in note.subject]
        self.assertTrue(notes)
        self.assertTrue(all(note.count > 0 for note in notes))

    def test_it_reports_that_magnitude_archetypes_are_disabled(self):
        subjects = [note.subject for note in self.panel().notes]
        self.assertIn("magnitude archetypes disabled", subjects)

    def test_it_disappears_from_the_notes_when_thresholds_are_set(self):
        from src.concentration import analyse
        panel = view.coverage([build()], analyse({}, {}),
                              {"version": "v1", "long_lead_days": 90},
                              A.catalogue(None))
        subjects = [note.subject for note in panel.notes]
        self.assertNotIn("magnitude archetypes disabled", subjects)

    def test_the_wording_is_neutral_and_not_a_warning(self):
        # These are properties of the data and deliberate design decisions, not
        # faults. Phrasing them as warnings trains a reader to dismiss them.
        for note in self.panel().notes:
            lowered = note.sentence.lower()
            with self.subTest(subject=note.subject):
                for alarm in ("warning", "error", "failed", "invalid",
                              "problem", "missing data", "incomplete!"):
                    self.assertNotIn(alarm, lowered)

    def test_not_applicable_is_explained_as_not_asking_rather_than_no(self):
        note = [n for n in self.panel().notes
                if "not applicable" in n.subject][0]
        self.assertIn("does not attach", note.sentence)


class TestSentenceComesFromTheRenderer(unittest.TestCase):

    def test_the_part_sentence_is_the_renderers_verbatim(self):
        from src.governance.render import render
        profile = build("AA-P-01", tooling="supplier")
        surface = view.exposure_surface(
            [profile], {"AA-P-01": "single_source"}, A.catalogue(None),
            {"AA-P-01": evidence()})
        row = surface.all_rows()[0]
        log = gov.DecisionLog()
        ranking.log_ranked(log, profile, "single_source",
                           list(row.detail["archetypes"]))
        self.assertEqual(row.sentence, render(list(log)[0]))

    def test_the_model_assembles_no_sentence_of_its_own(self):
        from codescan import code_of
        code = code_of(view, functions_only=True)
        for forbidden in ('f"{', "' + ", '" + '):
            with self.subTest(pattern=forbidden):
                self.assertNotIn(f"sentence={forbidden}", code)


class TestActionsHaveNoWritePath(unittest.TestCase):

    def control(self, action="confirm", requires_reason=False):
        return view.Control(
            action=action,
            act_kind=(gov.ACT_BULK_APPROVE if action == "confirm"
                      else gov.ACT_REJECT),
            subject="Alpha Works", requires_reason=requires_reason,
            member_count=9, reason_codes=view.CLUSTER_REASONS)

    def test_confirming_a_cluster_writes_one_event_with_member_count(self):
        log = gov.DecisionLog()
        actions.apply(log, self.control(), "r.okafor")
        self.assertEqual(len(log), 1)
        event = list(log)[0]
        self.assertEqual(event.member_count, 9)
        self.assertEqual(event.act_kind, gov.ACT_BULK_APPROVE)
        self.assertEqual(event.decided_by, "r.okafor")

    def test_an_anonymous_decision_is_refused(self):
        with self.assertRaises(ValueError):
            actions.apply(gov.DecisionLog(), self.control(), "   ")

    def test_a_rejection_requires_a_reason_code(self):
        with self.assertRaises(ValueError):
            actions.apply(gov.DecisionLog(),
                          self.control("reject", requires_reason=True),
                          "r.okafor")

    def test_other_requires_the_note_it_promises(self):
        with self.assertRaises(ValueError):
            actions.apply(gov.DecisionLog(),
                          self.control("reject", requires_reason=True),
                          "r.okafor", reason_code=gov.REASON_OTHER)

    def test_a_reason_code_not_offered_by_the_control_is_refused(self):
        with self.assertRaises(ValueError):
            actions.apply(gov.DecisionLog(),
                          self.control("reject", requires_reason=True),
                          "r.okafor", reason_code=gov.REASON_MERGE_CONFIRMED)

    def test_the_actions_module_imports_nothing_that_writes(self):
        # "Validation flags, never fixes" has to hold where fixing would feel
        # most natural: a reviewer looking at a missing figure they happen to
        # know is exactly the person who would type it in.
        from codescan import code_of
        code = code_of(actions)
        for forbidden in ("to_csv", "open(", "write", "pandas", "Path"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, code)


class TestDominanceLayout(unittest.TestCase):

    def test_dominating_archetypes_come_before_the_ones_they_dominate(self):
        profiles = [build("AA-P-01", tooling="supplier")]
        surface = view.exposure_surface(
            profiles, {"AA-P-01": "single_source"}, A.catalogue(None),
            {"AA-P-01": evidence()})
        placement = {group.name: index
                     for index, layer in enumerate(surface.layers)
                     for group in layer}
        self.assertLess(placement["correlated_resourcing_trap"],
                        placement["resourcing_trap"])

    def test_incomparable_archetypes_share_a_layer(self):
        profiles = [build("AA-P-01", tooling="supplier")]
        surface = view.exposure_surface(
            profiles, {"AA-P-01": "single_source"}, A.catalogue(None),
            {"AA-P-01": evidence()})
        self.assertTrue(any(len(layer) > 1 for layer in surface.layers))

    def test_no_group_carries_a_rank_number(self):
        # A "1., 2., 3." list is a total order asserted by typography, and it is
        # how the composite arrives through the back door.
        for forbidden in ("rank", "position", "index", "number", "score"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, view.Group.__dataclass_fields__)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
