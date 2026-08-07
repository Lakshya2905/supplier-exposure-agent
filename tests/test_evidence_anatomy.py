"""The six fields of an evidence record, and the rules around them.

DESIGN.md specifies the anatomy in more detail than the palette, because the
memorable claim in this product is "every claim shows its work". A record that
cites a row which does not hold the value is worse than one that cites nothing:
a reviewer who checks one citation, finds it right, and stops checking has been
given false confidence by the thing that exists to remove the need for trust.

So the tests here are about whether a citation can be FOLLOWED, not whether the
panel contains the right words.
"""
import unittest
from fractions import Fraction

from src.interface import model as view
from src.synthetic.model import (ANNUAL_UNITS, DEMAND_FILE, LEAD_TIMES_FILE,
                                 QUOTED_LEAD_TIME_DAYS, SUPPLIER_NAME,
                                 SUPPLIERS_FILE)

EXTRACTS = {
    SUPPLIERS_FILE: ("approved vendor list", "2026-07-28T18:00:00+00:00"),
    LEAD_TIMES_FILE: ("supplier quote history", "2026-07-17T18:00:00+00:00"),
    DEMAND_FILE: ("production plan", "2026-07-31T12:00:00+00:00"),
}


class Exploded:
    def __init__(self, finished_good, qty):
        self.finished_good = finished_good
        self.qty_per_finished_good = Fraction(qty)


def evidence(supplier_records=(("Braxton Industries", "south_asia", 7),),
             lead_time_records=(("Braxton Inds", 41, 53, 3),),
             exploded_rows=(Exploded("FG-01", 4),),
             demand_plan=None, extracts=None):
    return view.evidence_for(
        "AA-P-01",
        supplier_records=supplier_records,
        exploded_rows=exploded_rows,
        demand_plan={"FG-01": 12000} if demand_plan is None else demand_plan,
        lead_time_records=lead_time_records,
        extracts=EXTRACTS if extracts is None else extracts,
        demand_row_numbers={"FG-01": 1})


class TestEveryCitationCarriesTheSixFields(unittest.TestCase):

    def test_a_recorded_citation_names_its_file_row_column_system_and_date(self):
        citation = next(c for c in evidence().all_citations()
                        if c.field == SUPPLIER_NAME)
        self.assertEqual(citation.source_file, SUPPLIERS_FILE)
        self.assertEqual(citation.row, 7)
        self.assertEqual(citation.field, SUPPLIER_NAME)
        self.assertEqual(citation.system_of_record, "approved vendor list")
        self.assertEqual(citation.retrieved_at, "2026-07-28T18:00:00+00:00")
        self.assertEqual(citation.authority, view.RECORDED)

    def test_the_locator_is_the_inverse_link(self):
        # What a reviewer opens, and what the export carries so a raw line can
        # be traced back to the claims that used it.
        citation = next(c for c in evidence().all_citations()
                        if c.field == SUPPLIER_NAME)
        self.assertEqual(citation.locator, "suppliers.csv:7")

    def test_the_field_is_spelled_as_the_source_spells_it(self):
        # DESIGN.md: original column headers, no relabeling. The constants come
        # from the same module the readers use, so a rename moves both together.
        fields = {c.field for c in evidence().all_citations()}
        self.assertIn(SUPPLIER_NAME, fields)
        self.assertIn(QUOTED_LEAD_TIME_DAYS, fields)
        self.assertIn(ANNUAL_UNITS, fields)


class TestDerivedValuesCiteNoLine(unittest.TestCase):
    """A locator pointing at a row that does not hold the number is worse than
    none: a reviewer who follows it finds a different figure and cannot tell
    which of the two is wrong."""

    def test_a_contribution_is_marked_derived_and_names_its_operation(self):
        citation = next(c for c in evidence().all_citations()
                        if c.field == "contribution")
        self.assertEqual(citation.authority, view.DERIVED)
        self.assertEqual(citation.locator, "")
        self.assertIn(ANNUAL_UNITS, citation.derived_from)

    def test_a_recorded_citation_without_a_row_is_refused(self):
        with self.assertRaises(ValueError):
            view.Citation(field="x", value="1", authority=view.RECORDED)

    def test_a_derived_citation_that_cites_a_row_is_refused(self):
        with self.assertRaises(ValueError):
            view.Citation(field="x", value="1", authority=view.DERIVED,
                          source_file="suppliers.csv", row=3)


class TestTransformationsShowBothStrings(unittest.TestCase):

    def test_a_cross_file_merge_keeps_the_original_and_the_resolved(self):
        # Nobody can disagree with a result whose input has been discarded.
        merge = next(t for t in evidence().transformations
                     if t.kind == view.CROSS_FILE_MERGE)
        self.assertEqual(merge.original, "Braxton Inds")
        self.assertEqual(merge.resolved, "Braxton Industries")
        self.assertTrue(merge.rule)

    def test_a_duplicate_vendor_merge_says_it_changed_the_supplier_count(self):
        """Two rows of ONE file naming one supplier is the merge that moves the
        number the verdict turns on. A reviewer counting rows in the panel gets
        two where the sentence says one, and without this stated that gap looks
        like a bug in the sentence."""
        record = evidence(supplier_records=(
            ("Kestrel Corporation", "europe", 4),
            ("KESTREL CORP", "europe", 5)))
        merge = next(t for t in record.transformations
                     if t.kind == view.DUPLICATE_VENDOR_MERGE)
        self.assertTrue(merge.changes_supplier_count)
        self.assertIn("Kestrel Corporation", merge.original)
        self.assertIn("KESTREL CORP", merge.original)

    def test_the_duplicate_merge_resolves_to_the_key_not_a_chosen_spelling(self):
        # `names[0]` is whichever string sorted first, which would read as the
        # system having preferred one vendor record over the other.
        record = evidence(supplier_records=(
            ("Kestrel Corporation", "europe", 4),
            ("KESTREL CORP", "europe", 5)))
        merge = next(t for t in record.transformations
                     if t.kind == view.DUPLICATE_VENDOR_MERGE)
        self.assertEqual(merge.resolved, "kestrel corporation")


class TestContradictionsAreShownNeverResolved(unittest.TestCase):
    """Two lead time rows for one supplier that disagree are a question this
    tool has no basis to settle. Nothing in seed 42 produces one, which is
    exactly why the previous dict-comprehension join silently kept the last row
    for months without anybody noticing."""

    def test_two_disagreeing_rows_both_survive(self):
        record = evidence(lead_time_records=(
            ("Braxton Inds", 41, 53, 3),
            ("BRAXTON INDS", 90, 110, 4)))
        contradiction = record.contradictions[0]
        self.assertEqual(contradiction.field, QUOTED_LEAD_TIME_DAYS)
        self.assertEqual({c.value for c in contradiction.citations},
                         {"41", "90"})

    def test_both_sides_of_a_contradiction_are_followable(self):
        record = evidence(lead_time_records=(
            ("Braxton Inds", 41, 53, 3),
            ("BRAXTON INDS", 90, 110, 4)))
        locators = {c.locator for c in record.contradictions[0].citations}
        self.assertEqual(locators, {"lead_times.csv:3", "lead_times.csv:4"})

    def test_rows_that_agree_are_not_a_contradiction(self):
        # Two spellings of one supplier quoting the same figures is a duplicate
        # record, not a disagreement, and calling it one would fill the panel
        # with noise a reviewer has to dismiss.
        record = evidence(lead_time_records=(
            ("Braxton Inds", 41, 53, 3),
            ("BRAXTON INDS", 41, 53, 4)))
        self.assertEqual(record.contradictions, ())


class TestAbsenceIsAStateNotAnEmptyPanel(unittest.TestCase):

    def test_a_missing_supplier_row_says_which_source_was_pulled_and_when(self):
        """The manifest is what made `no record` sayable. Before it, "no
        supplier rows" could not be told apart from "nobody has looked"."""
        record = evidence(supplier_records=(), lead_time_records=())
        kinds = {kind for kind, _ in record.absences}
        self.assertIn("no_record", kinds)
        sentence = next(s for k, s in record.absences if k == "no_record")
        self.assertIn("approved vendor list", sentence)
        self.assertIn("2026-07-28", sentence)

    def test_a_finished_good_absent_from_the_plan_is_a_recorded_absence(self):
        record = evidence(exploded_rows=(Exploded("FG-01", 4),
                                         Exploded("FG-99", 2)))
        self.assertTrue(any("FG-99" in sentence
                            for _, sentence in record.absences))

    def test_an_absence_never_renders_as_zero(self):
        record = evidence(exploded_rows=(Exploded("FG-99", 2),),
                          demand_plan={})
        row = record.demand_rows[0]
        self.assertIsNone(row.annual_units)
        self.assertEqual(row.contribution, "")


class TestSourcesAreIdentityNeverATally(unittest.TestCase):

    def test_each_source_names_its_file_system_date_and_rows(self):
        entry = next(e for e in evidence().sources_used()
                     if e["source_file"] == SUPPLIERS_FILE)
        self.assertEqual(entry["system_of_record"], "approved vendor list")
        self.assertEqual(entry["retrieved_at"], "2026-07-28T18:00:00+00:00")
        self.assertEqual(entry["rows"], (7,))

    def test_derived_values_contribute_no_source(self):
        # A derived figure has no file, so counting it as one would inflate the
        # apparent amount of evidence behind a claim.
        files = {e["source_file"] for e in evidence().sources_used()}
        self.assertNotIn("", files)

    def test_one_row_cited_twice_is_listed_once(self):
        record = evidence(supplier_records=(
            ("Braxton Industries", "south_asia", 7),))
        entry = next(e for e in record.sources_used()
                     if e["source_file"] == SUPPLIERS_FILE)
        self.assertEqual(len(entry["rows"]), len(set(entry["rows"])))


class TestTheExportCarriesTheChainBothWays(unittest.TestCase):

    def test_every_locator_appears_in_the_plain_text(self):
        record = evidence()
        text = record.as_text()
        for citation in record.all_citations():
            if citation.locator:
                self.assertIn(citation.locator, text)

    def test_the_export_carries_the_retrieval_time(self):
        self.assertIn("2026-07-28T18:00:00+00:00", evidence().as_text())

    def test_the_export_carries_both_sides_of_every_transformation(self):
        text = evidence().as_text()
        self.assertIn("Braxton Inds", text)
        self.assertIn("Braxton Industries", text)


class TestTheManifestIsRequiredRatherThanDefaulted(unittest.TestCase):

    def test_a_file_with_no_manifest_row_is_refused_at_construction(self):
        """A blank as-of beside a value reads as "nothing to report" rather
        than as "nobody knows", which is the collapse this whole product
        refuses. Refused where it happens, not rendered as an empty cell."""
        with self.assertRaises(ValueError) as refusal:
            evidence(extracts={SUPPLIERS_FILE: ("a", "b")})
        self.assertIn(LEAD_TIMES_FILE, str(refusal.exception))


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
