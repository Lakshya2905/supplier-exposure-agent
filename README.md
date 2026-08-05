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

## Stage 2: BOM explosion

One row per (finished good, part), carrying quantity and the **set** of depths
at which the part appears. It does not aggregate, and there is deliberately no
rollup function: see below.

Quantities are `Fraction`. They multiply down three levels and then sum across
branches for common parts, and `Fraction` is exact under both. Floats would
give `11.999999999999998` against a hand-computed `12`, and the moment the
fixture needed a tolerance it would have stopped being an oracle.
`Fraction(11, 1) == 11` is `True`, so the fixture's assertions stay literal
integers. Rounding happens at display only.

Depth is a property of the **path**, not of the part. `LEAF-T01` in the fixture
sits at depth 1 and depth 2 under the same finished good and neither is more
correct, so `depths` is a set and `min_depth` / `max_depth` are derived from it.

A cycle raises `CycleError` naming the path rather than recursing until the
stack dies. A diamond, where a part is reached twice by different routes, is
ordinary and correct, and the two are distinguished by test.

**There is no rollup.** Summing `qty_per_finished_good` across finished goods
produces an unlabelled scalar with no unit, and the obvious next thing to do
with it is divide on-hand by it to get buffer cover, which would be wrong.
Annual usage needs the demand plan and carries the partial-demand upper-bound
rule, so it belongs in stage 4 as `annual_usage(rows, demand_plan)` returning a
value **and** a completeness flag. `rows_by_part()` keys the per-finished-good
rows; it does not sum them.

## Stage 3: single-source identification

**Supplier count is not an input. It is the output of a fuzzy match.** The two
files spell the same supplier differently, so before any verdict can be reached
the names have to be resolved into identities, and that resolution carries a
confidence. Which means the verdict table's inputs are themselves uncertain, and
that is what forces autonomy to be decided per finding rather than per stage.

Normalisation runs in two tiers, kept apart deliberately:

- **certain**, identical after deterministic canonicalisation (case,
  punctuation, whitespace, abbreviation expansion). Score 1.0. Applied in every
  reading and never shown to a reviewer, because "ACME CORP" versus "Acme Corp"
  is a formatting difference, not a judgment. Collapsing this tier into the
  uncertain one would send every part in the data to review.
- **uncertain**, similar but not identical. Carries a score, and is the only
  tier that can route a finding to the exception lane.

### The dual reading, again

Every finding is computed twice, once with uncertain merges applied and once
with them withheld. Agree, it executes. Disagree, it recommends and enters the
exception lane carrying both raw strings and the score that would settle it.

This is why no default merge direction is set, and the reason is not
squeamishness: **the safe direction inverts between the two joins.** A missed
merge in the supplier list overcounts sources and understates exposure, which
is expensive. A missed match in the lead-time join undercounts lead times and
overstates exposure, which is merely noisy. Leaning one way protects one join
and damages the other. Computing both does not have to choose.

### The threshold was set by the floors, not the other way round

The floors come from what the task requires. The threshold is the dial that
moves to meet them.

| | floor | why |
|---|---|---|
| recall | 0.99 | a missed merge understates exposure, and that is the error that stops a line |
| precision | 0.95 | a false merge manufactures a **phantom single source** and sends somebody to qualify a supplier that already exists |

Swept against the damage ledger:

| threshold | precision | recall |
|---|---|---|
| 0.90 | 0.917 | 1.000 |
| **0.95** | **1.000** | **1.000** |

0.90 was the starting point and it **failed the precision floor**, so the
threshold moved to 0.95. The floor did not move. `tests/test_grading.py`
asserts both floors at the shipped threshold and separately asserts that 0.90
still fails, so the reason for the change stays evidence rather than folklore.

Two findings from the sweep:

- **Recall is flat across every threshold.** Each variant the generator
  produces reaches an identical canonical key and merges at 1.0 regardless.
  So in this data the threshold is a precision dial and nothing else, and a
  recall floor is a guard against future damage ops rather than a live
  constraint.
- **Every false merge at 0.90 was the same pair of genuinely distinct
  suppliers** whose names differ by one letter, scoring 0.944. That pair is the
  generator's deliberate mirror trap, and at 0.90 it worked: an over-eager
  matcher merged them into a phantom single source.

Precision and recall are reported **separately, never as an F-score**, for the
same reason the five scoring dimensions stay separate. Alongside them is a
third number, because precision alone does not say what a false merge costs:
**verdict impact**, counting how many verdicts each false merge would actually
have changed. The same merge is invisible on a four-supplier part and a phantom
single source on a two-supplier part. Identical precision, entirely different
consequence, so the consequence is counted rather than inferred.

### Two disagreements, not one

A finding is undecidable in two independent ways, and both have to reach the
lane:

- **merge conflict**, the two clusterings produce different verdicts
- **readings conflict**, the clusterings agree, and what they agree on is
  `readings_disagree`, because the part is flagged `make` while carrying
  supplier rows

Comparing the clusterings alone catches only the first. Under the second, both
readings return `readings_disagree`, they match, and a finding whose verdict
literally means *nobody can tell* gets stamped `executes`. Four parts in the
generated data are exactly that case. A verdict of `readings_disagree` is
therefore disqualifying on its own, regardless of whether the readings agreed.

`readings_disagree` is also deliberately **absent from the severity order**. It
is not a level of exposure, it is the absence of a settled one, so it cannot be
ranked. The lane sorts on the concrete readings underneath it, which can be.

### Measured end to end

Against the generator's answer key at seed 42: **300 parts, 300 verdicts
matching truth, 296 executing automatically, 4 in the exception lane**, all four
genuine make-flag contradictions, ordered worst reading first.

**The merge-uncertain lane did not fire.** It is empty at the shipped threshold
because the normaliser resolved every case in this dataset: at 0.95 nothing here
is genuinely ambiguous. That is a finding, and it belongs next to the threshold
evidence above rather than in the known-gaps list.

It was tempting to engineer a supplier pair landing between 0.95 and 1.0 so the
lane had live traffic. That was rejected, because **the threshold is derived
from the floors, so fitting data to the threshold inverts the whole
derivation**: the number would stop being evidence about the normaliser and
start being a consequence of a case built to justify it. The coverage that is
correct here is the unit tests plus the committed golden, both pinned at 0.90
where the case is genuinely live.

A harder supplier-name distribution is a real thing to test, and it belongs in
the eval set at stage 8 as a **separate frozen scenario**, not in the primary
generator.

### The decision log renders, it does not store prose

**Store structured, render prose, never store the prose.** A log that stored its
own sentences could not be re-rendered when the wording improved, and the
wording is a deliverable here: it is what appears in the stage 7 review
interface and in any demo, so it is not a debug view.

`render(event)` turns any event into a sentence on demand, answering which part,
what verdict under which reading, the two raw strings, the score and threshold,
why the readings disagreed, what a human decided and why, and what stands now.
A clause it cannot answer is **omitted rather than invented**, and an unmapped
verdict renders as its bare code rather than as a guess.

Three golden renderings are committed under `tests/fixtures/`, so a wording
change arrives as a reviewable diff. Every event kind and every reason code in
the enum is asserted to render.

> SEA-P-0248: two rows spell a supplier 'Marrow Corporation' and 'Yarrow
> Corporation', matching at 0.94, which meets the 0.90 threshold. Treated as one
> supplier the part is one qualified supplier (single_source); treated as two it
> is more than one qualified supplier (multi_source), so the merge was routed
> for review rather than decided automatically.

### Self-agreement guard

`tests/test_identify.py` writes every expected verdict out by hand as a literal
string and **does not import the verdict table**. The generator uses that table
to assign truth and stage 3 uses it to classify observed data, so importing it
into the tests would let a wrong row be wrong in both places with the suite
agreeing.

## Stage 4: exposure scoring

Four dimensions per part, kept separate, with **no composite and nowhere to put
one**. The fifth dimension, concentration, is declared and its slot reserved
for stage 5.

| dimension | measure | unit | can abstain |
|---|---|---|---|
| Lead time to recover | quoted and p95 together | days | yes |
| Blast radius | finished-good units blocked, plus structural reach | finished good units | no, but bounded |
| Buffer cover | on-hand divided by daily consumption | days | yes |
| Portability | who owns the tooling | categorical | yes |
| Concentration | reserved for stage 5 | | not yet assessed |

**No banding.** Every dimension returns its raw measure. "Long lead" is a
threshold and a threshold is a judgment, so introducing one would smuggle a
modelling choice into a stage whose autonomy claim depends on having none. Both
lead-time columns are returned rather than one, for the same reason: choosing
quoted over p95 is a judgment, and at this stage the two give different
durations but not different answers, so they travel as a pair. That pair becomes
a live dual reading the moment stage 6 bands them.

### The bound direction inverts, from the identical missing row

Partial demand does not produce an abstention. It produces a **bound**, and
which way the bound points depends on where the number lands:

- **buffer cover** has usage in the **denominator**. Unrecorded demand can only
  reduce cover, so cover on known demand is an **upper bound**.
- **blast radius** has blocked units in the **numerator**. Unrecorded demand can
  only add, so blocked units on known demand are a **lower bound**.

Same finished good missing from the plan, opposite directions. So
`annual_usage` reports `partial` and names **no direction at all**; the
consuming dimension names it. Encoding the direction at the source would
hard-code one consumer's perspective into a function two consumers share, and
the second would read its bound backwards. This is the third time in this
system that the safe direction has turned out not to be constant.

One test asserts both directions on **one part with one missing row**, because
split across two tests the inversion is invisible.

### Six completeness states, because five would force a collapse

| state | meaning | routes to lane |
|---|---|---|
| `known` | exact | no |
| `upper_bound` | cover on partial demand | no |
| `lower_bound` | blocked units on partial demand | no |
| `cannot_tell` | a required input is absent | **yes** |
| `no_recovery_path` | no supplier at all | no |
| `not_applicable` | the dimension does not apply | no |

Autonomy is derived from completeness in **one function**, so routing can never
drift away from the value it routes. A bound is an answer *about* a bound and
executes.

`no_recovery_path` exists because `no_qualified_supplier` is not missing data.
Somebody checked the list and found nobody, so recovery time is undefined by
absence. Rendering that as "cannot tell" would file the most serious finding in
the dataset as a gap in a spreadsheet.

`not_applicable` exists for made-in-house parts, by the same argument. There is
no in-house capacity model anywhere in this data and there is not going to be
one, so a lane that keeps presenting in-house parts asks a reviewer to resolve
them with data that will never exist. **84 parts in the generated data land in
this state**, and every one of them would otherwise be sitting in the lane.

This is a **state and not a reason code the lane filters on**, chosen
deliberately. A filter would make `cannot_tell` stop meaning "routes to the
lane" and would put routing in a second place, where the next consumer that
forgets the filter silently re-admits all 84. One rule, one home.

### Missing on-hand versus a recorded zero

Blank means no record; `0` means counted and empty. One is a gap in a
spreadsheet and the other is the worst cover in the dataset, and the collapse
between them is never a decision anybody makes. It is a default: pandas reads an
integer column containing a blank as `float64`, so `0` becomes `0.0` and blank
becomes `NaN`, and the first `int(x or 0)` downstream fuses them permanently.

So `readers.py` reads **every column as a string** with
`keep_default_na=False` and converts explicitly, and `buffer_cover` branches on
`is None` as its first statement, before `on_hand` is touched by any
expression. The two are asserted unequal at every level of the result: value,
completeness, autonomy and reason string.

The same `keep_default_na=False` fixes the second trap in one stroke: a
`supplier_region` of `NA` is North America, and pandas reads it as `NaN`, which
would silently delete a region from stage 5's concentration analysis.

**A corner worth recording.** A part with a recorded zero on-hand whose only
finished good is absent from the demand plan still abstains. An empty buffer
runs out instantly under any positive consumption, so cover looks like an
obvious zero, but **absence is not zero**: an unrecorded finished good could
genuinely have no demand, and then the empty buffer never runs out and cover is
unbounded. Zero and unbounded are both live and the data cannot say which, so it
abstains rather than picking the likelier one.

### Unbounded is a value, not a missing one

A part with stock and no recorded consumption has unbounded cover. That is an
answer, and a division-by-zero would be the code mistaking an answer for an
error.

It is represented by a sentinel that is deliberately **neither `None` nor
`math.inf`**. `None` means "no value" everywhere else in the module, and
conflating them would file an answered dimension in the abstention lane. And
`inf` is a float that compares and arithmetics happily with everything, so it
would have been the one measure in the module that could be summed.

### No composite, enforced two ways

Blocking the `+` is the easy half. **What enables the `+` is normalisation.**
Twenty-six days and three assemblies cannot be added by anybody, but "0.8
lead-time risk" and "0.6 blast radius" add up beautifully and mean nothing. So
the guarantee has two halves and needs both:

1. no function returns a scalar combining dimensions, and the container exposes
   no `total`, `overall`, `score`, `weighted`, `rank` or `__add__`
2. **every measure keeps its unit**, no unit is a unitless range, and no
   dimension exposes a normalised, scaled, indexed or percentile variant of its
   value

The second is enforced at construction: a `DimensionScore` built with a unit
named `score`, `risk_index`, `normalised` or `percent` raises. Tests also assert
that real values leave the [0, 1] and [0, 100] ranges, which is what makes them
units rather than scores in disguise.

The source-scanning tests parse the **code only**, with docstrings and comments
stripped, because the docstrings in `scoring.py` discuss composites at length in
order to refuse them and a raw scan flags the explanations rather than the
violations.

### How the review interface shows five values without inviting a sum

The guarantee is structural rather than a matter of UI discipline. The units are
heterogeneous and stay that way, so no total is expressible. Specifically: no
radar or spider chart, because the enclosed area *is* a composite, drawn instead
of computed. No total column, no overall badge, no default sort, and sorting is
by one named dimension at a time with the interface stating which. Abstentions
render as the words "cannot tell", never as a blank, a dash or a zero, because
an empty cell invites a reader to substitute zero and zero is summable.

### Autonomy is per dimension per part

Not per stage. One part executes on blast radius and abstains on buffer cover
and portability in the same breath, and neither result contaminates the other.
The abstention lane groups by **dimension** rather than by part, because every
part missing the same field is resolved by one trip to the same system. It is a
separate lane from stage 3's, which sorts by exposure under the worse reading: a
dimension abstention has no competing readings to be worse than, so that
ordering would be meaningless here.

### Measured end to end

296 parts scored, 1184 dimension events, at seed 42:

| completeness | count |
|---|---|
| known | 856 |
| cannot_tell | 163 |
| not_applicable | 84 |
| lower_bound | 76 |
| upper_bound | 3 |
| no_recovery_path | 2 |

1021 dimension results execute and 163 abstain. The lane holds 107 buffer cover,
34 portability and 22 lead time to recover. All six completeness states occur in
real data rather than only in unit tests.

### Arithmetic

Quantities are `Fraction` and stay `Fraction`; demand is `int`; usage and cover
are therefore exact. **Nothing in scoring rounds**, so no dimension can drift by
accumulating rounding across a three-level explosion. Rounding happens at render
only. `100 x 365 / 1000` is `Fraction(73, 2)`, exactly 36.5 days, and the fixture
asserts it as an exact equality rather than with a tolerance.

`DAYS_PER_YEAR = 365` is a **declared modelling constant**, not a fact. Working
days would be roughly 250 and would give about 1.46 times the cover. It stays a
plain constant because stage 4 bands nothing, so the choice cannot change any
answer here. It becomes a dual reading the moment stage 6 bands cover.

## Autonomy levels

These are the product, not a detail.

| | |
|---|---|
| Explosion, joining, exposure identification | executes automatically |
| Correlation and concentration flagging | recommends, human confirms |
| Recommended actions | recommends permanently, never auto-selects |
| Supplier qualification | never. Out of scope by design. |

**Explosion's `executes` level is scoped, and the scope is the reason.** It runs
unattended because the BOM is structurally complete by construction: every edge
resolves to a part in the part master, and every part reaches at least one
finished good. That is why explosion has exactly one return shape and no
"cannot tell" path.

This is **not** a general claim that explosion is deterministic. Given a BOM
with an unresolvable parent or an orphan subtree it raises rather than answering
partially, and the autonomy level would not hold.

The completeness is **enforced, not documented**:
`tests/test_structural_completeness.py` asserts every edge resolves and every
part reaches a finished good, and asserts that no damage knob touches BOM
structure. If a structural knob is ever added, those fail loudly rather than
leaving an autonomy claim that has quietly stopped being true.

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

The placeholder landed with stage 3 and does exactly that. The four statuses,
the four act kinds, the decision-log envelope and two domain-neutral reason
codes are agent 1's, unchanged, down to the column named `sku_id` even though
this agent calls them parts: renaming it is precisely what would make the two
logs unjoinable. `kind` and `evidence` are additive agent-3 columns, so a
cross-agent join reads the envelope and simply does not see them.

Agent 1's other four reason codes are intake-specific, about docks and
packaging tiers. There is no dock and no tier here, and copying them literally
would degrade the vocabulary rather than share it. The enum marks which codes
are inherited and which are agent 3's, and **that marking is the migration
plan**: on extraction the inherited codes move to the shared package unchanged
and the agent-3 codes are promoted or left behind deliberately, one at a time.

The log is append-only, with no update and no delete. Any status other than
`proposed` requires a named decider, because an anonymous decision is not a
decision.

## Known gaps

Marked `@pytest.mark.xfail(strict=True)`, so the gap is visible, CI stays
green, and the test fails loudly the day someone fixes it without noticing.

- **Lead time to recover does not include qualification time.** The brief
  defines the dimension as how long to qualify an alternative *or* wait out the
  disruption, and the data carries quoted and p95 purchase lead times, so it
  answers the second half only. There is no qualification-lead-time field
  anywhere in the schema, so the first half is not merely uncomputed, it is
  unrepresentable. A part with a 30 day purchase lead time whose only supplier
  needs 40 weeks to qualify a replacement scores identically to one that can be
  resourced in a fortnight.
- **Fractional quantities and units of measure are not supported.** Every
  `qty_per_parent` is a whole number of pieces, so a BOM line of 0.5 metres of
  extrusion or 2.5 kg of compound cannot be represented. This is a limitation
  of the generator itself, chosen deliberately over a
  "stage-2-does-not-exist-yet" placeholder, which would fail the build the
  moment stage 2 lands rather than describing a real gap.

## What is deliberately not here

Stages 5 through 8: concentration detection, ranked output, review interface,
eval harness.

Out of scope permanently: cost optimisation, supplier scorecarding, negotiation
support, resourcing workflow. `annual_spend_usd` is carried as a display column
precisely so the temptation to rank by it stays visible and unacted upon.
