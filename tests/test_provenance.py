"""Where a value came from, and when it was pulled.

DESIGN.md's evidence anatomy asks every record to cite a source id, a system of
record and an as-of. Two of those three had no source in this dataset until
`sources.csv` existed, and the alternative on the table was to render them from
constants in the interface. That would have been the panel whose whole job is
proving nothing was invented inventing a provenance at render time, so the
generator emits them instead and the pipeline reads them like any other input.

The tests here are about the two properties that make the fields worth
rendering at all: the locator has to actually locate, and the as-of has to be
reproducible without being a clock reading.
"""
import csv
import unittest
from pathlib import Path

from src.readers import (read_demand_plan, read_demand_rows, read_lead_times,
                         read_sources, read_suppliers)
from src.generate_data import generate
from src.synthetic.config import GeneratorConfig
from src.synthetic.writers import (BOM_FILE, DEMAND_FILE, LEAD_TIMES_FILE,
                                   PART_MASTER_FILE, SOURCES_FILE,
                                   SUPPLIERS_FILE)

DESCRIBED_FILES = (BOM_FILE, DEMAND_FILE, LEAD_TIMES_FILE, PART_MASTER_FILE,
                   SUPPLIERS_FILE)


def build(tmp_path, seed=42):
    generate(GeneratorConfig(seed=seed), tmp_path, tmp_path / "truth.json")
    return tmp_path


def data_rows(path):
    """The file as a list, so a test can check a locator against the bytes."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestTheExtractManifest:

    def test_it_describes_every_input_file_and_nothing_else(self, tmp_path):
        # A manifest missing a file leaves that file's evidence with no as-of,
        # which is the state this whole file exists to end. A manifest naming a
        # file that does not exist is a citation to nowhere.
        sources = read_sources(build(tmp_path) / SOURCES_FILE)
        assert set(sources) == set(DESCRIBED_FILES)
        for name in sources:
            assert (tmp_path / name).exists()

    def test_it_does_not_describe_itself(self, tmp_path):
        # It is the only file that says where files came from, so a row about
        # itself would be the only self-certifying record in the set.
        assert SOURCES_FILE not in read_sources(build(tmp_path) / SOURCES_FILE)

    def test_every_file_names_a_system_of_record(self, tmp_path):
        for name, (system, _) in read_sources(
                build(tmp_path) / SOURCES_FILE).items():
            assert system, f"{name} has no system of record"

    def test_the_extracts_are_staggered(self, tmp_path):
        """An as-of that is the same on every record carries nothing.

        Five files pulled at one instant would make the field decoration: a
        reviewer could read it once and stop looking. Staggering them is what
        makes "the supplier list is a fortnight older than the plan" visible,
        which is the fact the field exists to carry.
        """
        stamps = [when for _, when in
                  read_sources(build(tmp_path) / SOURCES_FILE).values()]
        assert len(set(stamps)) == len(stamps)

    def test_the_as_of_is_not_a_clock_reading(self, tmp_path):
        """Two builds of the same seed agree, which a wall clock would not.

        `evals/` is frozen under a manifest of hashes. A generator that stamped
        `datetime.now()` would produce a different byte on every build, so the
        frozen set could never be rebuilt and checked against itself.
        """
        one = read_sources(build(tmp_path / "one") / SOURCES_FILE)
        two = read_sources(build(tmp_path / "two") / SOURCES_FILE)
        assert one == two


class TestALocatorActuallyLocates:
    """The row a record cites has to be the row that produced it.

    This is the test that makes the source id worth printing. A number beside a
    value that does not lead back to it is worse than no number, because a
    reviewer who checks one and finds it right will stop checking.
    """

    def test_a_supplier_records_row_holds_that_supplier(self, tmp_path):
        path = build(tmp_path) / SUPPLIERS_FILE
        rows = data_rows(path)
        for part, entries in read_suppliers(path).items():
            for name, region, row in entries:
                cited = rows[row - 1]
                assert cited["part_number"] == part
                assert cited["supplier_name"] == name
                assert cited["supplier_region"] == region

    def test_a_lead_time_records_row_holds_that_lead_time(self, tmp_path):
        path = build(tmp_path) / LEAD_TIMES_FILE
        rows = data_rows(path)
        for part, entries in read_lead_times(path).items():
            for name, quoted, p95, row in entries:
                cited = rows[row - 1]
                assert cited["part_number"] == part
                assert cited["supplier_name"] == name
                assert int(cited["quoted_lead_time_days"]) == quoted
                assert int(cited["lead_time_p95_days"]) == p95

    def test_the_row_survives_the_readers_sort(self, tmp_path):
        """The reader returns entries sorted by name, not in file order.

        So the locator cannot be recovered afterwards from an entry's position,
        which is exactly why it is attached during the read rather than derived
        later. If this ever became vacuous the assertion above would still pass
        while telling a reviewer to look at the wrong line.
        """
        path = build(tmp_path) / SUPPLIERS_FILE
        out_of_order = [
            entries for entries in read_suppliers(path).values()
            if [row for *_, row in entries] != sorted(row for *_, row in entries)
        ]
        assert out_of_order, (
            "no part's rows came back in a different order from the file, so "
            "this test is no longer checking anything")

    def test_the_demand_rows_and_the_demand_figures_describe_one_file(
            self, tmp_path):
        # Two reads of the same file, which is safe here only because the key
        # is the dict key both of them build. If they ever disagreed on which
        # finished goods exist, that argument would have quietly stopped
        # holding.
        path = build(tmp_path) / DEMAND_FILE
        assert set(read_demand_rows(path)) == set(read_demand_plan(path))

    def test_a_demand_row_holds_that_finished_good(self, tmp_path):
        path = build(tmp_path) / DEMAND_FILE
        rows = data_rows(path)
        for finished_good, row in read_demand_rows(path).items():
            assert rows[row - 1]["finished_good_part"] == finished_good


class TestTheManifestIsNotADifferentDatasetPerSeed:

    def test_a_second_seed_keeps_the_same_extract_shape(self, tmp_path):
        """Provenance is a property of the fictional IT landscape, not of the
        data, so it does not move when the parts do. A seed that reshuffled the
        systems of record would make the manifest look like a finding."""
        one = read_sources(build(tmp_path / "a", seed=42) / SOURCES_FILE)
        two = read_sources(build(tmp_path / "b", seed=43) / SOURCES_FILE)
        assert one == two


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
