# Supplier Exposure Agent

Agent 3 of a multi-agent supply chain system. Answers one question: which
single points of failure in a bill of materials would actually stop production,
ranked by how badly.

Synthetic data only. No real part numbers, no real supplier names, nothing
company-specific. See `docs/BRIEF.md` for the full spec.

**Stage 1 of 8 is built.** The remaining stages are listed in the brief and are
deliberately not scaffolded.

## Quickstart

```
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
python -m src.generate_data --seed 42
pytest -q
```

`data/` is gitignored and regenerated from the seed above, which is
deterministic and takes under a second. `evals/` and `tests/fixtures/` are
committed and frozen.

## Stage 1: the synthetic data generator

Builds a clean, fully consistent world first, then applies messiness as
explicit damage, recording every decision into an answer key. The single most
useful consequence: **with every messiness rate set to zero, the world is
perfectly consistent and the answer key is empty**, which is a real test rather
than an aspiration.

Output at seed 42: 300 parts, 4 finished goods, 3 levels, ~25 suppliers.

| file | what it is |
|---|---|
| `data/bom.csv` | parent-child edges with quantity. Depth is not precomputed. |
| `data/part_master.csv` | source type, sourcing list status, on-hand, tooling, spend |
| `data/suppliers.csv` | one row per part-supplier pair, names possibly variant |
| `data/lead_times.csv` | quoted and p95 days, not every pair present |
| `data/demand_plan.csv` | annual units per finished good, one deliberately absent |
| `truth/answer_key.json` | what the generator decided, for grading later stages |

Column semantics, and especially null semantics, are in
`docs/DATA_DICTIONARY.md`. The short version: an empty cell means no record
exists, `0` means somebody counted and found none, and collapsing the two is
the failure the data set is built to catch.

## The sourcing verdict

An explicit eleven-row lookup table in `src/synthetic/verdicts.py`, never
nested conditionals, with one test per row in `tests/test_verdict_table.py`.
Those tests hard-code their expectations by hand and do not import the table,
so a wrong row cannot be wrong in both places and agree with itself.

Two distinctions the table exists to preserve:

- a **verified** list with no suppliers is `no_qualified_supplier`, a real
  finding, and is not the same as nobody having checked
- an **unverified** list of one is not `single_source`, because it may really
  be a list of two

A `make` part that also carries supplier rows is a contradiction, and it takes
no side. Both readings are computed, stale-flag and genuine-dual-mode, and if
they differ the part goes to an exception lane ordered by exposure under the
worse reading.

## Autonomy levels

These are the product, not a detail.

| | |
|---|---|
| Explosion, joining, exposure identification | executes automatically |
| Correlation and concentration flagging | recommends, human confirms |
| Recommended actions | recommends permanently, never auto-selects |
| Supplier qualification | never. Out of scope by design. |

## Governance

**Option 2 from the brief**: a thin placeholder interface, not the shared
package. Option 1 is unavailable and this was verified rather than assumed:
`../intake-agent/packages/governance` does not exist, agent 1 being flat-layout
with no `pyproject.toml`, no `packages/`, and no governance module.

When the placeholder is written it will copy agent 1's reason-code vocabulary
and decision-log record shape **verbatim**. Diverging code is annoying;
diverging data formats are expensive, because the append-only decision records
are the thing anyone would eventually want to read across both agents.

Extraction into a genuinely shared package is deferred until after this agent
ships. The right shared interface is not visible until two real consumers
exist.

No governance code exists yet. It is not part of stage 1.

## Known gaps

Marked `@pytest.mark.xfail(strict=True)`, so the gap is visible, CI stays
green, and the test fails loudly the day someone fixes it without noticing.

- **Fractional quantities and units of measure are not supported.** Every
  `qty_per_parent` is a whole number of pieces, so a BOM line of 0.5 metres of
  extrusion or 2.5 kg of compound cannot be represented. This is a limitation
  of the generator itself, chosen deliberately over a
  "stage-2-does-not-exist-yet" placeholder, which would fail the build the
  moment stage 2 lands rather than describing a real gap.

## What is deliberately not here

Stages 2 through 8: BOM explosion, single-source identification from observed
data, the five scoring dimensions, concentration detection, ranked output,
review interface, eval harness. Stage 1 emits data and proves it is the data it
claims to be.

Out of scope permanently: cost optimisation, supplier scorecarding, negotiation
support, resourcing workflow. `annual_spend_usd` is carried as a display column
precisely so the temptation to rank by it stays visible and unacted upon.
