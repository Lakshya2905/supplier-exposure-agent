"""The governance schema contracts, pinned against silent removal.

Expectations here are HAND-WRITTEN and nothing imports the value it checks. A pin
derived from the code under test asserts that the code equals itself, which is the
proxy failure this repo's corrections log is about: it passes while the property
it names has changed.

Two contracts are pinned here because an audit found nothing else pinning them at
any layer. `ENVELOPE_FIELDS` was referenced only by the method that consumes it,
and the reason-code tuples were referenced only by the validator that reads them,
so dropping a member of either was green everywhere.
"""
import unittest

from src import governance as gov

# The envelope, hand-written from docs/BRIEF.md and the comment above
# ENVELOPE_FIELDS. Agent 1 owns this list; agent 3 carries it verbatim.
EXPECTED_ENVELOPE = ("event_id", "at", "status", "decided_by", "reason_code",
                     "note", "act_id", "act_kind", "member_count", "sku_id",
                     "field", "value", "source_file")

# Hand-written from the source comments, which mark the boundary explicitly:
# the first two are inherited from agent 1 and must not be reworded, everything
# else is agent 3's migration surface.
EXPECTED_INHERITED_REASONS = ("source data wrong", "other (note below)")

EXPECTED_AGENT_3_REASONS = (
    "same supplier, merge confirmed",
    "different suppliers, merge rejected",
    "supplier list confirmed complete",
    "supplier list known incomplete",
    "make flag stale, part is purchased",
    "in-house capability confirmed",
    "on-hand counted, record added",
    "demand added for a finished good that had none",
    "tooling ownership confirmed",
    "correlation confirmed",
    "not correlated in practice",
    "grouping definition does not fit this case",
)


class TestTheEnvelopeIsTheCrossAgentJoin(unittest.TestCase):
    """The envelope is the only thing two agents' logs share.

    `sku_id` keeps agent 1's name even though this agent calls them parts,
    because renaming a column is what makes two logs unjoinable. Dropping one is
    the same defect and is quieter: a join keeps working and silently stops
    carrying a field, and no consumer in this repo would notice, because the only
    reader of the tuple is the method that builds the dict from it.
    """

    def test_the_envelope_is_exactly_agent_ones_field_set(self):
        self.assertEqual(tuple(gov.ENVELOPE_FIELDS), EXPECTED_ENVELOPE)

    def test_every_envelope_field_exists_on_the_event(self):
        # A name in the tuple with no attribute behind it would raise at
        # envelope() time, on a code path a reader reaches before any test does.
        for name in EXPECTED_ENVELOPE:
            with self.subTest(field=name):
                self.assertIn(name, gov.DecisionEvent.__dataclass_fields__)

    def test_the_envelope_carries_no_agent_3_column(self):
        # `kind` and `evidence` are additive agent-3 fields. They are deliberately
        # OUTSIDE the envelope so a cross-agent join does not see them, which is
        # why adding them did not split the schema. If either leaks in, the join
        # starts reading a column agent 1 never wrote.
        for additive in ("kind", "evidence"):
            with self.subTest(field=additive):
                self.assertNotIn(additive, gov.ENVELOPE_FIELDS)

    def test_an_event_renders_its_envelope_completely(self):
        event = gov.DecisionEvent(
            event_id=1, at="2026-08-04T10:02:00+00:00",
            status=gov.STATUS_APPROVED, sku_id="SEA-P-0248")
        self.assertEqual(tuple(event.envelope()), EXPECTED_ENVELOPE)


class TestTheReasonCodeVocabularyIsFixed(unittest.TestCase):
    """A dropped reason code silently narrows what a reviewer can say.

    `actions.apply` validates a submitted code against the control's offered
    codes, so removing one from the vocabulary does not raise anywhere. It just
    stops being offered, and the reviewer who needed it picks the closest
    remaining option instead. That is a worse outcome than a refusal, because the
    log then carries a reason the reviewer did not mean.
    """

    def test_the_inherited_codes_are_exactly_agent_ones_two(self):
        # These two are domain-neutral and shared. Rewording either forks the
        # vocabulary between two logs that are supposed to be joinable.
        self.assertEqual(tuple(gov.INHERITED_REASON_CODES),
                         EXPECTED_INHERITED_REASONS)

    def test_the_agent_3_codes_are_exactly_the_documented_migration_surface(self):
        self.assertEqual(tuple(gov.AGENT_3_REASON_CODES),
                         EXPECTED_AGENT_3_REASONS)

    def test_the_full_vocabulary_is_the_inherited_set_plus_agent_3s(self):
        self.assertEqual(
            tuple(gov.REASON_CODES),
            EXPECTED_INHERITED_REASONS + EXPECTED_AGENT_3_REASONS)

    def test_the_two_halves_do_not_overlap(self):
        # The boundary is the migration surface: on extraction each agent-3 code
        # is promoted or left behind, deliberately and one at a time. A code in
        # both halves would be promoted twice or not at all.
        self.assertFalse(
            set(gov.INHERITED_REASON_CODES) & set(gov.AGENT_3_REASON_CODES))

    def test_every_code_is_distinct(self):
        self.assertEqual(len(set(gov.REASON_CODES)), len(gov.REASON_CODES))


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
