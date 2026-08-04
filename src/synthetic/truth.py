"""The answer key.

Records generator DECISIONS and raw assignments. It never records anything
requiring a traversal or a threshold.

So `assigned_lead_time_days = 294` belongs here and `is_long_lead` does not,
because "long" is a stage-4 threshold. Which finished good was dropped from the
demand plan belongs here; which parts thereby have partially known usage does
not, because answering that means walking the BOM, and if the answer key walked
the BOM then a bug in the walk and a bug in stage 2 could agree with each other.

The per-part verdict IS recorded, because the generator chose it.
"""
import hashlib
import json
from dataclasses import asdict, dataclass, field

from . import verdicts as V
from .model import PART_PREFIX, FG_PREFIX


@dataclass
class Truth:
    seed: int = 0
    config_hash: str = ""
    # emitted supplier string -> supplier_id
    supplier_variants: dict = field(default_factory=dict)
    # part -> supplier_id, spelled differently in the two files
    cross_file_divergences: list = field(default_factory=list)
    # genuinely distinct suppliers with confusingly similar names
    confusable_suppliers: list = field(default_factory=list)
    # (part, supplier_id) pairs whose lead time record was removed
    omitted_lead_times: list = field(default_factory=list)
    # part -> the messiness intents applied to it
    intents: dict = field(default_factory=dict)
    # part -> verdict from the lookup table
    verdicts: dict = field(default_factory=dict)
    absent_demand_finished_good: str = ""

    def record_variant(self, emitted_name, supplier_id):
        self.supplier_variants[emitted_name] = supplier_id

    def record_divergence(self, part, supplier_id, in_suppliers, in_lead_times):
        self.cross_file_divergences.append({
            "part_number": part, "supplier_id": supplier_id,
            "name_in_suppliers": in_suppliers,
            "name_in_lead_times": in_lead_times,
        })

    def record_confusable(self, a_id, b_id, a_name, b_name):
        self.confusable_suppliers.append({
            "a": {"supplier_id": a_id, "name": a_name},
            "b": {"supplier_id": b_id, "name": b_name},
        })

    def record_omitted_lead_time(self, part, supplier_id):
        self.omitted_lead_times.append(
            {"part_number": part, "supplier_id": supplier_id})

    def record_intent(self, part, intent):
        self.intents.setdefault(part, []).append(intent)

    def is_empty(self):
        """True when no damage was applied at all.

        Supplier variants are excluded: with the variant rate at zero every
        emitted name is the canonical one, so the map is an identity and
        carries no damage. Everything else being empty is the real signal.
        """
        return not (self.cross_file_divergences or self.confusable_suppliers
                    or self.omitted_lead_times or self.intents
                    or self.absent_demand_finished_good)

    def to_dict(self):
        return asdict(self)


def config_hash(config):
    payload = json.dumps(
        {k: v for k, v in sorted(vars(config).items())},
        sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def assign_verdicts(world, truth):
    """Record the verdict the generator's own construction implies.

    Uses the lookup table, which stage 3 will also use against observed CSVs.
    The per-row tests hard-code their expectations by hand precisely so this
    shared use cannot let a wrong row pass twice.
    """
    for part_number, part in world.parts.items():
        links = world.links_for(part_number)
        with_lead_time = {lt.supplier_id
                          for lt in world.lead_times_for(part_number)}
        n_with = len({l.supplier_id for l in links} & with_lead_time)
        truth.verdicts[part_number] = V.verdict(
            part.source_type, len(links), part.sourcing_list_status, n_with)
    return truth


def verdict_coverage(truth):
    """How many parts carry each verdict. Stage 1 asserts every table row and
    the disagreement case are represented, so no row ships untested."""
    counts = {}
    for verdict in truth.verdicts.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts


def write(truth, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(truth.to_dict(), indent=2, sort_keys=True))
