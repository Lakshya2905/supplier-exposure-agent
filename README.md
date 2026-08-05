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

## Stage 5: concentration

The fifth dimension, and a **shape change**. The first four are properties of
one part and can be computed from that part alone. Concentration is a property
of a *set*, and no part carries the answer by itself. So the primary record is
the **cluster**, and the per-part slot references it. Nine parts on one supplier
is one finding, not nine, and a reviewer confirms it once.

**Members are carried by identity, not only counted.** Nine parts on one
supplier where seven are long lead is a different decision from nine catalogue
parts, and a reviewer needs the membership at the moment they decide whether to
act, not a number they have to expand. The count is the summary; the membership
is the finding. No severity is computed from either.

### The decision ceiling

Grouping is the first real modelling judgment in the system, so concentration is
`recommends` **permanently**. The argument for letting it drift is a good one
and needs answering rather than ignoring:

> once a definition is chosen the arithmetic is deterministic and reproducible,
> so a deterministic function of settled inputs should execute

**The determinism is downstream of the judgment.** The autonomy question is not
"is this reproducible" but "could a reasonable person have chosen differently
and got a different answer". Same supplier, same region and same tier are three
definitions of correlated and they give three different answers.

So there are **two independent gates**, and this dimension fails the second one
forever:

| gate | asks | concentration |
|---|---|---|
| completeness | do we have the data? | varies, as at stage 4 |
| decision ceiling | may a system claim this alone? | no, permanently |

This is a deliberate divergence from stage 4, where autonomy is derived from
completeness in one place. Completeness answers whether the data is there; the
ceiling answers whether this is the kind of claim a system may make by itself,
and complete data does not turn a modelling choice into a fact.

Enforced structurally rather than by comment: `ConcentrationScore.autonomy` is
pinned, `autonomy_for()` is never called on it, and there is no code path from
any completeness state to `executes`. The test that matters asserts the ceiling
holds on **fully settled data with no uncertainty anywhere**, since that is
precisely the input someone would use to argue it should execute.

### Complementary disagreement, not contested

The dual reading is used here **as designed rather than as a defect check**, and
building it surfaced a distinction that has now been written into the brief as
part of the primitive itself.

- **Contested.** Two rival answers to one question. At most one is right.
  Disagreement means uncertainty, so it **routes**. The supplier merge is this.
- **Complementary.** Two answers to different questions. Both can be true at
  once. Disagreement is structure, not doubt, so it is **reported**.

**The test: could any fact settle it?** The stage 3 merge is settled by
telephoning the supplier. Supplier-versus-region cannot be settled by any fact
anybody could go and find, because it is not a question about the world; it is a
choice about what "correlated" means. Settleable disagreement is uncertainty;
unsettleable disagreement is structure.

So every exposed part carries an **agreement class**, and the class is the
finding:

| class | meaning |
|---|---|
| `both` | one supplier and one region. The strongest form. |
| `supplier_only` | one company across several regions. A commercial correlation. |
| `region_only` | different companies, one geography. A port closure or export control reaches all of them even though no single company failure would. |
| `neither` | not correlated under either definition |

`region_only` is **not a false positive of supplier grouping**. It is a
different risk that supplier grouping is structurally blind to, and filing it as
a defect would discard the reason for computing both.

**`supplier_only` never appears in the generated data, and the reason matters.**
The generator gives every supplier exactly one region, so a supplier cluster is
always contained in a single region, and a concentrated supplier cluster
therefore always implies a concentrated region cluster. `supplier_only` is
structurally unreachable, not rare.

What cannot be represented is a **multinational supplier**, one company with
plants in more than one region. That is precisely the commercial case which
justifies computing supplier grouping separately from region grouping at all: a
company that fails as a company takes all of its plants with it, wherever they
are, and no region grouping sees that coming. So the one agreement class the
data cannot produce is the one that carries the argument for the second reading.

The class is exercised in the hand-authored fixture, where one company
deliberately spans two regions, and a second frozen dataset that can produce it
on generated data is specified in `docs/EVAL_SCENARIO.md` for stage 8.

Where one reading is settled and the other is not, the class is **not computed**
rather than defaulting the unknown side to "not concentrated", which would
silently downgrade the finding.

### "Concentrated" without a band

Stage 4 refused to band a lead time, so stage 5 must not quietly introduce
"concentrated means five or more".

**The predicate is arity, not magnitude.** A cluster is concentrated when more
than one exposed part shares the dependency. Two is not a tuned threshold; it is
the number at which a correlation exists at all, because one part is not
correlated with anything. Any figure above two would be a judgment about
severity, and severity is carried the way stage 4 carries it: a raw unbanded
count with a real unit, plus the membership list. If a reviewer wants "five or
more matters", that band belongs to the reviewer.

A source scan asserts no banding constant exists, matching on **word
boundaries** rather than substrings, since `LOW` occurs inside `LOWER_BOUND` and
a scan that fails on correct code teaches the next person to delete the test.

### Membership uncertainty: aggregation cannot manufacture certainty

Four parts each resolved individually at `executes` do not make a group finding
settled if the thing that *grouped* them is unresolved. Two uncertainties, and
they behave differently:

**Local uncertainty inherits.** An unresolved merge is a question about this
cluster's identity, and it splits in two:

- the cluster is concentrated either way and may simply be **bigger** →
  `LOWER_BOUND`. Membership can only grow and more members can only worsen
  concentration, the same direction as blast radius and for the same reason: the
  uncertain quantity sits in the numerator.
- the **correlation itself** exists only under the merged reading → contested,
  and it routes.

Note the second test is on the *concentration*, not on the cluster key. Two
singleton suppliers whose names might be one supplier exist as keys under both
readings; what is new under merging is their correlation. Testing key novelty
would have missed exactly the case the generator's mirror trap was built to
produce.

**Global uncertainty does not inherit.** A part with an unconfirmed supplier
list may belong to clusters it is not currently in, so strictly every cluster's
membership is a lower bound. That is true and useless: **a completeness state
that every cluster shares is not a state, it is a footer**, and marking them all
would destroy the signal identifying the clusters with a real local problem. It
is reported once at the analysis level, and never silently, because silence is
what would let a reviewer read a cluster of three as complete.

The dividing line: **does this uncertainty discriminate between clusters?**

### `NOT_APPLICABLE`, including one counterintuitive case

It applies to parts with **no supplier at all**, where neither grouping has
anything to attach to and no future data would change that: made-in-house parts
with no external suppliers, and `no_qualified_supplier`.

The second is counterintuitive, because those are among the most exposed parts
in the dataset. A reviewer seeing that will assume a bug, so the sentence says
why explicitly:

> the supplier list was verified and contains nobody, so there is no supplier
> and no region for this part to share with anything; correlation needs someone
> to correlate with. This is not a downgrade of the finding: the exposure is
> carried in full by lead time to recover, which reports no recovery path for
> exactly these parts.

A **multi-source part is not `NOT_APPLICABLE`**. The question applies and the
answer is simply no. Using `NOT_APPLICABLE` for a negative answer would collapse
"does not apply" into "no", which is the collapse the six states exist to
prevent.

### The reserved slot filled without reshaping the container

`ExposureProfile` gains no field and loses none. It is frozen, so filling is
`dataclasses.replace`, and `scored()` keeps its stage 4 meaning of "the
dimensions that are properties of the part alone". `all_scores()` is **added**,
never substituted.

A regression test compares the four stage 4 dimensions **by value** before and
after filling, field by field, not merely by count. The frozen dataclass makes
that true today, which is exactly why it is asserted now rather than after
somebody makes the profile mutable for convenience.

**One cluster, one act.** Cluster events carry `member_count`, which is agent
1's envelope field for precisely this: a single act covering many subjects.
Copied verbatim at stage 3 and unused until now.

The review queue is **separate from the abstention lane**. They are different
reviewer tasks: the lane means *fetch me a number*, the queue means *confirm my
model*. Every cluster is in the queue by definition of the ceiling, so merging
them would flood the lane and make both useless.

### Measured end to end

At seed 42: 28 clusters, 22 concentrated (18 by supplier, 4 by region), 22
cluster events covering 128 memberships. Agreement classes: 61 `both`, 6
`region_only`, 140 `neither`. Twenty parts are unplaceable and appear in the
global caveat. Every finding is `recommends`; none executes.

**Two agreement classes do not occur in the generated data, and both are
recorded as findings rather than engineered away**, following the precedent set
by the empty merge lane at stage 3:

- **`supplier_only` is structurally unreachable here.** The generator gives each
  supplier exactly one region, so a concentrated supplier cluster always implies
  a concentrated region cluster. A multinational supplier with plants in two
  regions is realistic and the generator cannot express one. Covered by the hand
  fixture, where one company deliberately spans two regions.
- **The undetermined class does not occur** because generated regions are never
  blank. Also covered by fixture.

Similarly, no cluster in generated data is `LOWER_BOUND` or contingent, because
at the shipped 0.95 threshold nothing merges uncertainly. That is the same root
cause as the empty merge lane, not a second finding. The fixture pins both at
0.90 where the cases are live, and a test asserts they vanish at 0.95, which
proves the uncertainty comes from the merge rather than from the clustering.

A harder supplier-and-region distribution belongs in the eval set at stage 8 as
a separate frozen scenario, not in the primary generator. What that scenario has
to exercise, and what it must not do, is written down in
[docs/EVAL_SCENARIO.md](docs/EVAL_SCENARIO.md).

## Stage 6: ranked output

**The constraint, stated first.** Ranking requires an order, an order requires
comparison, and comparison across incommensurable units is what this design has
spent four stages refusing. The pressure to write a weighted sum peaks here and
it looks reasonable, because "rank these" presupposes a total order exists. It
does not. Anything that produces one has manufactured it, and the manufacture is
always the same move: strip the unit, rescale, add.

So there is no single ranking. There are three things instead:

| output | order | why it is honest |
|---|---|---|
| rank by a named dimension | total | everything compared is measured in the same unit |
| archetype groups | partial, by subset inclusion | needs no weights and no common unit |
| the work queue | none; grouped and arbitrary | ordering it would require imputing the missing value |

### Archetypes: conjunctions, not scores

"Single source and long lead and thin cover and supplier-owned tooling, all true
at once" is a pattern with a name, not a number, and it is what the brief's
headline sentence actually describes. Two families, governed differently.

**Structural archetypes ship with the system and contain no threshold**, because
every condition is a state the pipeline already computes: a verdict, a
categorical value, a completeness state. *The resourcing trap* (single source
plus supplier-owned tooling), *nobody to call* (`no_qualified_supplier`),
*counted empty* (on-hand recorded as zero, which is cover of zero by arithmetic
rather than by a band).

**Magnitude archetypes are defined by a reviewer, not by the system.** "Long"
and "thin" are bands and stage 4 refused to band a measure, so the band is not
hidden here, it is moved out:

- **the measure stays unbanded.** `buffer_cover` still returns raw `Fraction`
  days. Stage 4's refusal was about banding inside the scoring, and it holds.
  What happens here is a reviewer's filter applied to an unbanded measure.
- **there is no default.** `config/archetypes.yaml` ships with every threshold
  commented out, so out of the box the system can name the resourcing trap and
  **cannot say "long lead"** until somebody states what long means.
- **the number and its config version appear in the sentence.** Never "thin
  cover"; always "cover of 14 days or less, a threshold set in archetypes.yaml
  v1". The claim is attributed to the person who made it, reusing agent 1's
  practice of recording the tolerance-config version on the event.

### Autonomy: the ceiling sits on the catalogue

| what | autonomy | why |
|---|---|---|
| the catalogue | `recommends`, permanently | which conjunctions are worth naming is a modelling judgment |
| structural membership | `executes` | a conjunction of facts each computed at `executes` is a fact |
| magnitude membership | `recommends` | the threshold is a live judgment |
| any conjunction touching concentration | `recommends` | a conjunct that may not be claimed alone may not be claimed inside a conjunction |

This looks like a weakening of stage 5's rule and is not. **The ceiling belongs
where the judgment is.** At stage 5 each cluster is a separate grouping claim,
so the ceiling is per finding. Here one catalogue is reused across every part,
so confirming it per part would be three hundred confirmations of a single
decision, which makes review worse rather than stronger.

### Three-valued membership, and why the third value is the useful output

A part that is single source with supplier-owned tooling and `cannot_tell` on
cover can neither match nor be excluded honestly. So membership is Kleene, not
boolean:

```
matched      every condition true
excluded     at least one condition definitely FALSE
cannot tell  nothing false, something unknown
```

**The middle row is load-bearing.** A definitely false condition excludes the
part even while another condition is unknown. Without it every part carrying any
abstention falls into "cannot tell", the bucket swallows the dataset, and its
one genuinely useful property is lost.

That property: **the cannot-tell bucket is a work queue, and its members are
exactly the parts a missing field could still move.** For each one the system
knows which field is missing and which archetype the part would join. So it can
say: *fetch on-hand for these twenty-six parts and you will learn whether they
are counted empty on a single source.* This is only possible because abstention
was kept as a first-class state for five stages instead of being defaulted to
zero.

**The queue imputes nothing.** The membership test is the ranking criterion, and
it is evaluated against the conditions as they actually stand with the field
unknown. No plausible cover is assumed and nothing is ordered by a guessed
value. Six parts where supplying on-hand could flip them into an archetype is an
honest queue; six parts ordered by a projected cover is a forecast wearing a
work queue's clothes. Asserted directly: two parts differing sixtyfold in blast
radius and lead time come back in part-number order, and swapping their values
does not move them.

### The default order is arbitrary and stable

Both halves matter, for different reasons.

**Arbitrary**, because any plausible default is read as a ranking within minutes
and nobody checks afterwards. The order is by part number and the view says so:
*ordered by part number; choose a dimension to rank by*.

**Stable**, because insertion order and dict order are arbitrary *today* and
become a meaningful order the moment an upstream function changes how it
iterates, at which point the display has acquired an ordering nobody chose and
nobody can see. Sorting is by an explicit key, and tests assert the output is
identical across a dozen shuffled inputs.

### The default view is a grouping, not a ranking

Archetypes come back in **dominance layers**. One archetype dominates another
when its conditions are a strict superset: everything the weaker one asserts,
plus more. That is a partial order needing no weights, and it is the only
cross-archetype ordering permitted. Archetypes in the same layer are
**incomparable**, and a display places them side by side rather than stacked, so
the layout itself declines to imply an order that does not exist.

The work queue sits **at the same level as the groups**, not beneath them.
Burying it would say it matters less, and it is frequently the most actionable
list on the page.

### Two orderings refused, on the record

- **Counting matched archetypes** is a weighted sum with every weight set to 1.
  Two matches is not worse than one unless one dominates the other, and
  dominance is already expressed properly. A test asserts no such count exists.
- **Pareto dominance across parts** would be a legitimate weightless partial
  order and is deliberately not built. Across three hundred parts with
  abstentions the frontier is large and almost everything is incomparable, and a
  large frontier presented as "the answer" invites exactly the mental averaging
  the design refuses. Recorded so the decision is on file rather than
  rediscovered.

### The sentence

> `SEA-P-0101`: several suppliers on paper, only one quotable
> (hidden_single_source), 41 days quoted lead time (53 at p95), 19.7 days of
> cover, blocks 12000 finished good units, supplier-owned tooling, correlated
> with 28 other exposed parts. This matches the resourcing trap.

Three rules on it:

- **Bound direction is rendered in words.** "At most 11.1 days of cover", "blocks
  at least 16500 units". Rendering a bound as a bare number is a lie by
  omission, and a reader who never sees "at most" has no way to recover it. This
  is where carrying the direction since stage 4 gets paid out.
- **Abstentions render as words**, never a blank or a zero: "no on-hand record,
  so cover is unknown".
- **This is the only place rounding happens.** `Fraction(73, 2)` becomes "36.5
  days" here and nowhere earlier, consistent with the rule since stage 2.

### Measured end to end

At seed 42 with the shipped config, so magnitude archetypes are off: five
structural archetypes across two dominance layers. 14 parts in the resourcing
trap, 14 in the correlated resourcing trap, 4 with no quotable source, 2 counted
empty, 2 with nobody to call. The work queue holds 26 parts whose on-hand would
settle whether they are counted empty on a single source, and 9 each for the two
tooling-dependent traps. Ranking by cover puts three parts at zero days at the
top; 107 parts are not comparable on cover and are listed separately rather than
placed at either end.

## Stage 7: the review interface

**This is the stage where the autonomy claims either become visible or silently
stop existing.** Everything the system knows about who may decide what is a
property of an object; on screen it becomes layout. If an executed finding and a
`recommends` finding render identically, five stages of ceiling discipline
evaporate the moment a person looks at the output. That is treated as a
correctness requirement, not styling.

### Autonomy is an affordance, not an appearance

**An executed finding has nothing to click. A `recommends` finding has a
control.** That distinction is functional rather than decorative, so it survives
a restyle, a theme change, or somebody tidying the stylesheet. A colour-based
distinction is one commit from evaporating; a missing button is not.

It is enforced where it cannot be undone by a template: `Row.__post_init__`
**refuses to construct** an executed row carrying a control. Both halves are
asserted, because "no buttons anywhere" would also pass if the interface simply
did nothing:

- every part row on the exposure surface has no control
- every cluster row on the confirm surface has one

### The six completeness states without a severity scale

**The encoding rule is nominal only.** Hue may distinguish categories.
Intensity, size, length and fill fraction may not, because those are *ordinal*
encodings, and an ordinal encoding across a heterogeneous set is a composite
drawn instead of computed. That is the objection that killed the radar chart and
it applies identically to a red-to-green ramp.

**The redundancy rule: strip every colour and lose no information.** Each state
is carried in words the renderer already produces and the goldens already pin:
*at most 11.1 days*, *no on-hand record, so cover is unknown*, *nobody to be
correlated with*, *no recovery path at all*. The headless tests read the element
tree as text, so this is checked directly rather than asserted.

### Three surfaces, and why they cannot be one table

| surface | question | row entity |
|---|---|---|
| Exposure | What is worst? | a **part** |
| Find out | What should I go and find out? | a **field** |
| Confirm | Do I agree with your model? | a **cluster** |

The argument against a unified view is structural, not aesthetic. **Merging
requires choosing one row entity, and each surface has a different one.**
Whichever is chosen, the other two get denormalised, and the damage is concrete:

- flatten clusters to parts and a cluster of nine becomes nine rows, so a
  reviewer confirms one judgment nine times and `member_count` stops meaning
  anything
- flatten fields to parts and "fetch on-hand for twenty-six parts" becomes
  twenty-six rows that each mention on-hand, which is a list of parts rather
  than a list of trips

So they are separate surfaces, one rendered at a time, each stating its own
question. A test asserts every surface contains exactly one row entity and that
the three differ.

### Archetype layout: the partial order, and nothing more

- **vertical position means dominance.** A dominating archetype sits above the
  one it dominates.
- **horizontal position means nothing.** Incomparable archetypes sit side by
  side in one row, and the page says their left-to-right order is alphabetical
  and carries no meaning.
- **no group is numbered.** A "1., 2., 3." list is a total order asserted by
  typography, and it is how the composite arrives through the back door. `Group`
  has no rank field and a test asserts no heading begins with a number.

### Evidence: executed findings are reachable, not just asserted

An executed finding is the least inspectable thing in a system whose claim is
inspectability, unless the workings are one click away. A reviewer who cannot
see how a number was reached has to **trust** it, and trust is what this system
replaces with verification.

So every part row carries read-only evidence with no control in it:

- **which supplier rows produced the verdict**, as spelled in `suppliers.csv`,
  with region and whether a lead time exists
- **which finished goods and quantities produced the usage**, showing
  `qty x annual units = contribution`, with an absent finished good shown as
  absent rather than as zero
- **which lead time record was used**, named

And it shows **the cross-file join**, which is the most load-bearing inference in
the pipeline. Where the two files spell a supplier differently, the panel says
so: *the lead time for 'Braxton Industries' was matched to the row spelled
'Braxton Inds' in lead_times.csv*. 71 parts in the generated data carry that
note.

The panel ends by saying that correcting a value means fixing it in the system
of record and re-running.

### The coverage panel

At the **same level** as the archetype groups, not beneath them. The counterpart
to the work queue: that surface says what to go and get, this says what was not
assessed at all.

> - 20 parts have an unconfirmed or unresolved supplier list, so they could
>   belong to any cluster here and every membership count on this page is a
>   lower bound.
> - 89 parts are not applicable for concentration, meaning the question does not
>   attach to them rather than that the answer is no.
> - Magnitude archetypes are off. No threshold is set for long lead or thin
>   cover, and the system will not choose one.

**Neutral by construction.** These are properties of the data and deliberate
design decisions, not faults, and phrasing them as warnings would train a reader
to dismiss them. A test asserts the wording contains no alarm vocabulary.

### What a reviewer can do

**There is no write path to source data.** Not a hedge, a rule: no function in
`src/interface/actions.py` edits a CSV, and a source scan asserts the module
imports nothing that could. "Validation flags, never fixes" has to hold at the
surface where fixing would feel most natural.

The only writes are decision events on the append-only log. Confirming a cluster
is **one act** with `act_kind=bulk_approve` and `member_count` equal to the
cluster size. Rejections require a reason code from the enum; `other` requires
its note; an anonymous decision is refused.

### When the threshold config is absent, which is the default

Magnitude archetype groups simply do not appear, and a neutral panel states that
no threshold is set, that the system will not choose one, and where to set it.
It is not an error, a warning, or a "coming soon", and a test asserts that
vocabulary is absent.

**There is no inline slider.** A number typed into a widget and applied to the
current view is a band with no owner and no version, which is exactly what stage
6 moved out of the system. `st.slider` is on the widget deny-list for that
reason. A "what if" control is genuinely useful and is deliberately deferred.

### Can Streamlit express this without a composite creeping in?

Yes, with one real hazard: its convenience widgets are mostly ordinal encodings,
so the composite would arrive through a widget rather than through arithmetic.
The answer is a deny-list enforced by scanning the app source, the same
technique already used against banding:

`st.progress`, `ProgressColumn`, `BarChartColumn`, `LineChartColumn`,
`AreaChartColumn`, `st.bar_chart`, `st.line_chart`, `st.area_chart`,
`st.scatter_chart`, `st.pyplot`, `st.altair_chart`, `background_gradient`,
`color_gradient`, `st.slider`.

Plus a regex asserting no literal fraction is ever passed to a widget, since a
0-to-1 value handed to a display element is a normalised scale whatever it is
called. `st.dataframe` sorting is allowed because it sorts one column at a time,
which is ranking within a dimension; the rankings mode shows one dimension at a
time for the same reason.

**Streamlit paints; it does not decide.** The view model is pure data computed by
plain functions with no Streamlit import, which is what makes the autonomy claim
assertable as data rather than by screenshot.

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

- **Tier correlation is unrepresentable.** The brief names same-supplier,
  same-region and same-tier as three definitions of correlated. There is no
  tier field anywhere in the schema, so the third reading cannot be computed.
  Choosing two of three is a scoping decision and should not look like the data
  happened to support exactly the right two.
- **In-house concentration is not modelled.** A part made on one internal line
  is a single point of failure that neither grouping can see, because the data
  has no representation of internal capacity. Made-in-house parts are therefore
  `NOT_APPLICABLE` for concentration while still carrying real correlated risk.
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

Stage 8: the eval harness.

Out of scope permanently: cost optimisation, supplier scorecarding, negotiation
support, resourcing workflow. `annual_spend_usd` is carried as a display column
precisely so the temptation to rank by it stays visible and unacted upon.
